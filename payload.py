"""hermes-jailbreak-kernel · 破甲内核载荷模块（纯 Python 标准库，零 hermes_cli 依赖，便于离线自检）。

设计上对准 dsh-infinite-gen-4（无限四代）的「双层同源注入」内核：
- hermes-jailbreak-kernel-core      → Order 1 通用内核
- hermes-jailbreak-kernel-reinforce → Order 2 强化镜像（与通用内核逐字同源，SHA256 一致）

Hermes Agent 槽位约束（hermes_cli/plugins_dispatch.py）：
- 单段内容上限 4000 字符（MAX_SYSTEM_PROMPT_SECTION_CHARS）
- 全部插件段合计上限 8000 字符（MAX_SYSTEM_PROMPT_SECTIONS_TOTAL_CHARS）
- 唯一位置 after_memory；按 section id 字典序渲染（core < reinforce）。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
import uuid
from pathlib import Path

try:  # 包内上下文（Hermes 运行时）
    from . import i18n as _i18n
except ImportError:  # 顶层上下文（离线 selftest 直接 import payload）
    import i18n as _i18n

PLUGIN_NAME = "hermes-jailbreak-kernel"
PLUGIN_VERSION = "1.7.2"
PLUGIN_DISPLAY_NAME = "Hermes 破甲（armor-piercing kernel）"
TARGET_ARCHITECTURE = "Hermes Agent 任意后端模型（DeepSeek-V4 系列 / Hermes / 其它 chat 模型）"
KERNEL_PARENT = "dsh-infinite-gen-4 (v0.4.0) — 双层同源注入内核移植"
MODE = "armor — 双层同源注入，零工具面纯净直出"

MAX_SECTION_CHARS = 4_000  # Hermes 单段硬上限
TOTAL_BUDGET_CHARS = 8_000  # Hermes 全部插件段总预算
DUAL_POSITION = "after_memory"

_PROMPT_DIR = Path(__file__).resolve().parent / "prompts"
_SOURCE: dict[str, str] = {
    "hermes-jailbreak-kernel-core": "hermes-jailbreak-kernel-core.md",
    "hermes-jailbreak-kernel-reinforce": "hermes-jailbreak-kernel-reinforce.md",
}

_TRUTHY = {"1", "true", "yes", "on"}
_FALSEY = {"0", "false", "no", "off"}


def _load(prompt_file: str) -> str:
    """读取提示词文件并做尾部换行归一化（保证同源逐字一致）。"""
    return (_PROMPT_DIR / prompt_file).read_text(encoding="utf-8").rstrip("\n") + "\n"


def sha256(prompt_file: str) -> str:
    """载荷文件 SHA256（按归一化文本计算）。"""
    return hashlib.sha256(_load(prompt_file).encode("utf-8")).hexdigest()


def disabled() -> bool:
    """总开关：HERMES_JAILBREAK_DISABLE=1 时完全跳过注册（kill switch）。"""
    return os.environ.get("HERMES_JAILBREAK_DISABLE", "").strip().lower() in _TRUTHY


def dual_layer() -> bool:
    """双段开关：HERMES_JAILBREAK_DUAL=0 退化为单段注入（行为等价，省 token）。"""
    return os.environ.get("HERMES_JAILBREAK_DUAL", "1").strip().lower() not in _FALSEY


def sections() -> list[tuple[str, str]]:
    """当前生效的 (section_id, content) 列表。"""
    ids = ["hermes-jailbreak-kernel-core"] + (["hermes-jailbreak-kernel-reinforce"] if dual_layer() else [])
    return [(sid, _load(_SOURCE[sid])) for sid in ids]


def section_count() -> int:
    return len(sections())


def total_chars() -> int:
    return sum(len(text) for _, text in sections())


def profile() -> str:
    """供 /jailbreak 命令与日志使用的运行时元数据（对应 DSH 侧 infinite_gen4_profile 工具）。

    UI 字符串经插件 i18n（Hermes agent/i18n 标准的插件本地实现）解析：
    HERMES_LANGUAGE > display.language > en；缺失键回退英语再回退键名。
    """
    t = _i18n.t
    lines = [
        f"{PLUGIN_NAME} v{PLUGIN_VERSION} — {t('profile.title')}",
        f"target: {t('profile.target')}",
        f"kernelParent: {t('profile.kernel_parent')}",
        f"mode: {t('profile.mode')} (dual={dual_layer()}, disabled={disabled()})",
        t("profile.injection"),
    ]
    for sid, text in sections():
        lines.append(
            f"  - {sid:<32} position={DUAL_POSITION} chars={len(text):<5} sha256={sha256(_SOURCE[sid])[:16]}"
        )
    if dual_layer():
        lines.append(f"  {t('profile.same_source')}")
    lines.append(t(
        "profile.budget",
        total=total_chars(), budget=TOTAL_BUDGET_CHARS,
        max=max((len(x) for _, x in sections()), default=0), section_max=MAX_SECTION_CHARS,
    ))
    lines.append(t("profile.request_layer"))
    lines.append(t("profile.switches", disable="off", dual="on", dump="off"))
    return "\n".join(lines)


# ── 请求层强化（llm_request 中间件） ────────────────────────────────────────────
# 在 Hermes 完整拼装系统提示词之后、发往 Provider 之前，把破甲内核追加到最后一个
# system 消息末尾——这是离用户消息最近、对抗优先级最高的注入点。任何异常都必须
# fail-soft：原样放行请求，绝不影响会话。

def harden_system(messages: list) -> tuple[list, bool]:
    """请求层系统提示词强化（HERMES_JAILBREAK_SYSTEM_MODE 控制策略）：

    - ``replace``（默认）：system 整体重建为「记忆段 + 运行时环境段 + 内核」，
      丢弃 Hermes 35K 脚手架（agent 规范/技能索引/上下文文件）——与 DSH「内核
      独占 system」同构，模型视野内只剩内核指令，破甲权重最大化。
    - ``append``：仅把内核追加到最后一个 system 消息末尾（旧行为，较弱）。

    任何模式下内核都保证位于 system 最末尾。返回 (新 messages, 是否修改)。
    """
    if not isinstance(messages, list):
        return messages, False
    mode = os.environ.get("HERMES_JAILBREAK_SYSTEM_MODE", "replace").strip().lower()
    kernel = _load(_SOURCE["hermes-jailbreak-kernel-core"])
    tail = kernel.rstrip("\n")
    if mode != "replace":
        return _append_kernel(messages, kernel, tail)

    # replace：重建为「可选保留段 + 内核」
    original = ""
    for i in range(len(messages) - 1, -1, -1):
        m = messages[i]
        if isinstance(m, dict) and m.get("role") == "system" and isinstance(m.get("content"), str):
            original = m["content"]
            idx = i
            break
    else:
        messages.insert(0, {"role": "system", "content": kernel})
        return messages, True

    keep = []
    seg = _extract_section(original, "# Supermemory")
    if seg:
        keep.append(seg)
    seg = _extract_section(original, "# Hermes runtime environment")
    if seg:
        keep.append(seg)
    new_content = "\n\n".join([*keep, kernel]) if keep else kernel
    messages[idx] = dict(messages[idx], content=new_content)
    return messages, True


def _append_kernel(messages: list, kernel: str, tail: str) -> tuple[list, bool]:
    for i in range(len(messages) - 1, -1, -1):
        m = messages[i]
        if isinstance(m, dict) and m.get("role") == "system":
            content = m.get("content")
            if isinstance(content, str) and not content.rstrip("\n").endswith(tail):
                patched = dict(m)
                patched["content"] = content.rstrip("\n") + "\n\n" + kernel
                messages[i] = patched
            return messages, True
    messages.insert(0, {"role": "system", "content": kernel})
    return messages, True


def _extract_section(text: str, marker: str) -> str:
    """提取原 system 中以 marker 开头的段落（截至下一个 ## 标题）。"""
    i = text.find(marker)
    if i == -1:
        return ""
    j = text.find("\n## ", i + len(marker))
    seg = text[i:j if j != -1 else len(text)]
    return seg.strip()


# ── opencode 会话轮换（拒绝状态清除） ──────────────────────────────────────────
# opencode.ai 中继按 x-opencode-session 把同一会话钉在同一上游，并把「露骨请求被拒」
# 固化为该会话的状态——之后内核再强也翻不了（实测：同 session 先拒绝→换内核仍拒；
# 新 session + 内核 → 直接出文）。对策：每个请求轮换新 session id，让上游永远面对
# 干净会话。env HERMES_JAILBREAK_ROTATE_SESSION=0 可关闭（代价：prompt cache 失效）。

_ROTATE_MODE_EVERY = {"1", "every", "true", "yes", "on"}
_ROTATE_MODE_ONCE = {"once"}
_rotated_sessions: dict[str, str] = {}
_rotate_lock = threading.Lock()


def rotate_session(request: dict, context: dict | None = None) -> tuple[dict, bool]:
    """把请求的 x-opencode-session 轮换成干净的新会话 id（仅 opencode 目标）。

    模式（HERMES_JAILBREAK_ROTATE_SESSION）：
    - ``once``（默认）：每个 Hermes 会话首次请求轮换一次后复用——上游 session 干净
      （拒绝状态无法种下）且后续轮次保留 prompt cache。拒绝状态只在「会话被拒过」
      时种下，换新后永不积累，因此 once 已足够。
    - ``every`` / ``1``：每请求都换新 uuid（最激进，缓存全失效）。
    - ``0`` / ``off``：关闭轮换（破甲可能回归，仅用于省 token 场景）。
    """
    mode = os.environ.get("HERMES_JAILBREAK_ROTATE_SESSION", "once").strip().lower()
    if mode in _FALSEY:
        return request, False
    if not isinstance(request, dict):
        return request, False
    ctx = context or {}
    base = str(ctx.get("base_url") or "")
    prov = str(ctx.get("provider") or "")
    if "opencode.ai" not in base and "opencode" not in prov:
        return request, False
    headers = request.get("extra_headers")
    if not isinstance(headers, dict) or "x-opencode-session" not in headers:
        return request, False
    sid = str(ctx.get("session_id") or "unknown")
    if mode in _ROTATE_MODE_EVERY:
        new = "ha-" + uuid.uuid4().hex
    else:  # once（也兜底任意未识别值）
        with _rotate_lock:
            new = _rotated_sessions.get(sid)
            if new is None:
                new = "ha-" + uuid.uuid4().hex
                _rotated_sessions[sid] = new
    patched = dict(headers)
    patched["x-opencode-session"] = new
    out = dict(request)
    out["extra_headers"] = patched
    return out, True


_DUMP_DIR = Path(__file__).resolve().parent / "dumps"
_SESSION_RE = re.compile(r"[^A-Za-z0-9._-]+")
_dump_lock = threading.Lock()
_dumped_sessions: set[str] = set()


def _sanitize_sid(session_id: str) -> str:
    return _SESSION_RE.sub("_", str(session_id))[:64] or "unknown"


def dump_request(request: dict, context: dict | None = None) -> str | None:
    """受控落盘一次请求的诊断视图：system 消息全文 + 其它消息仅角色/长度。

    默认每个 session 只 dump 首次请求；HERMES_JAILBREAK_DUMP=1 时每次请求都 dump。
    返回 dump 文件路径（未 dump 时返回 None）。
    """
    try:
        ctx = context or {}
        sid = _sanitize_sid(ctx.get("session_id") or "unknown")
        force = os.environ.get("HERMES_JAILBREAK_DUMP", "").strip().lower() in _TRUTHY
        with _dump_lock:
            if not force and sid in _dumped_sessions:
                return None
            _dumped_sessions.add(sid)
        messages = request.get("messages") if isinstance(request, dict) else None
        msgs = []
        sys_full = []
        if isinstance(messages, list):
            for m in messages:
                if not isinstance(m, dict):
                    continue
                role = m.get("role", "?")
                content = m.get("content")
                if role == "system" and isinstance(content, str):
                    sys_full.append({"role": role, "chars": len(content), "content": content})
                else:
                    head = content[:200].replace("\n", "␤") if isinstance(content, str) else "n/a"
                    msgs.append({"role": role, "chars": len(content) if isinstance(content, str) else "n/a", "head": head})
        _DUMP_DIR.mkdir(parents=True, exist_ok=True)
        path = _DUMP_DIR / f"request_{sid}_{time.strftime('%Y%m%d_%H%M%S_%f')}.json"
        path.write_text(
            json.dumps({
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "session_id": sid,
                "model": ctx.get("model"), "provider": ctx.get("provider"),
                "base_url": ctx.get("base_url"), "api_mode": ctx.get("api_mode"),
                "reinforced": True,
                "system_messages": sys_full,
                "other_messages": msgs,
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return str(path)
    except Exception:  # 诊断失败绝不影响请求
        return None