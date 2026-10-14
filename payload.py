"""hermes-jailbreak-kernel · 破甲内核载荷模块（v2.0，纯 Python 标准库）。

v1.x → v2.0 的架构升级：

- **内核分档**（``prompts/profiles/``）：core / research / creative / max 四档，
  按会话选择；``full`` 模式强制 ``max`` 档。
- **会话级模式**（见 ``modes.py``）：off / slim / on / full——按会话开关与分级，
  取代 v1.x 的「进程级 env + 重启」。
- **双段同源注入**：core/reinforce 两个 section 使用同一档文本（同源由构造保证）。
- 请求层强化、opencode 会话轮换、受控诊断 dump 全部改为按会话模式决策。

Hermes 槽位约束（hermes_cli/plugins_dispatch.py）：
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
    from . import modes as _modes
except ImportError:  # 顶层上下文（离线 selftest 直接 import payload）
    import i18n as _i18n
    import modes as _modes

PLUGIN_NAME = "hermes-jailbreak-kernel"
PLUGIN_VERSION = "2.0.1"
PLUGIN_DISPLAY_NAME = "Hermes 破甲（jailbreak kernel）"
TARGET_ARCHITECTURE = "Hermes Agent 任意后端模型（DeepSeek-V4 系列 / Hermes / 其它 chat 模型）"
KERNEL_PARENT = "dsh-infinite-gen-4 (v0.4.0) — 双层同源注入内核移植"

MAX_SECTION_CHARS = 4_000  # Hermes 单段硬上限
TOTAL_BUDGET_CHARS = 8_000  # Hermes 全部插件段总预算
DUAL_POSITION = "after_memory"

CORE_SECTION_ID = "hermes-jailbreak-kernel-core"
REINFORCE_SECTION_ID = "hermes-jailbreak-kernel-reinforce"

_PROMPT_DIR = Path(__file__).resolve().parent / "prompts"
PROFILE_FILES: dict[str, str] = {
    "core": "profiles/core.md",
    "research": "profiles/research.md",
    "creative": "profiles/creative.md",
    "max": "profiles/max.md",
}

_TRUTHY = {"1", "true", "yes", "on"}
_FALSEY = {"0", "false", "no", "off"}

_text_cache: dict[str, str] = {}
_text_lock = threading.Lock()


def _load(prompt_file: str) -> str:
    """读取内核档文件并做尾部换行归一化（保证同源逐字一致）。"""
    with _text_lock:
        cached = _text_cache.get(prompt_file)
        if cached is not None:
            return cached
    text = (_PROMPT_DIR / prompt_file).read_text(encoding="utf-8").rstrip("\n") + "\n"
    with _text_lock:
        _text_cache[prompt_file] = text
    return text


def profile_text(name: str = "core") -> str:
    """返回某一档内核文本（未知档回退 core）。"""
    return _load(PROFILE_FILES.get(name, PROFILE_FILES["core"]))


def sha256(prompt_file: str) -> str:
    """内核档文件 SHA256（按归一化文本计算）。"""
    return hashlib.sha256(_load(prompt_file).encode("utf-8")).hexdigest()


def profile_sha256(name: str = "core") -> str:
    """按档名取 SHA256。"""
    return sha256(PROFILE_FILES.get(name, PROFILE_FILES["core"]))


def system_disabled() -> bool:
    """进程级 kill switch：HERMES_JAILBREAK_DISABLE=1 时完全跳过注册。"""
    return os.environ.get("HERMES_JAILBREAK_DISABLE", "").strip().lower() in _TRUTHY


# v1.x 兼容别名
disabled = system_disabled


def dual_layer() -> bool:
    """双段开关：HERMES_JAILBREAK_DUAL=0 退化为单段注入（省 token，行为等价）。"""
    return os.environ.get("HERMES_JAILBREAK_DUAL", "1").strip().lower() not in _FALSEY


def sections(session_id: str = "") -> list[tuple[str, str]]:
    """当前会话生效的 (section_id, content) 列表；模式 ``off`` 时为空。"""
    mode = _modes.effective_mode(session_id)
    if mode == "off":
        return []
    text = profile_text(_modes.effective_kernel_profile(session_id))
    ids = [CORE_SECTION_ID] + ([REINFORCE_SECTION_ID] if dual_layer() else [])
    return [(sid, text) for sid in ids]


def section_count(session_id: str = "") -> int:
    return len(sections(session_id))


def total_chars(session_id: str = "") -> int:
    return sum(len(text) for _, text in sections(session_id))


def profile_budgets() -> dict[str, int]:
    """各档内核的字符数（供状态报告与预算检查）。"""
    return {name: len(profile_text(name)) for name in PROFILE_FILES}


# ── 状态报告（/jailbreak 无参数） ───────────────────────────────────────────────

def profile(session_id: str = "") -> str:
    """运行时状态报告：会话模式、内核档、注入槽位、双段 SHA256、预算与开关。"""
    t = _i18n.t
    snap = _modes.snapshot(session_id)
    active = sections(session_id)
    lines = [f"{PLUGIN_NAME} v{PLUGIN_VERSION} — {t('profile.title')}"]
    lines.append(t("profile.session", session=snap["session_id"] or "(unresolved)"))
    lines.append(t(
        "profile.state",
        mode=snap["mode"], kernel=snap["kernel_profile"],
        rotation=snap["rotation"], dump=snap["dump"],
        override="yes" if any(v is not None for v in snap["overrides"].values()) else "no",
    ))
    lines.append(f"target: {t('profile.target')}")
    lines.append(f"kernelParent: {t('profile.kernel_parent')}")
    if active:
        lines.append(t("profile.injection"))
        for sid, text in active:
            lines.append(
                f"  - {sid:<32} position={DUAL_POSITION} chars={len(text):<5} sha256={hashlib.sha256(text.encode()).hexdigest()[:16]}"
            )
        if dual_layer() and len(active) > 1:
            lines.append(f"  {t('profile.same_source')}")
        lines.append(t(
            "profile.budget",
            total=total_chars(session_id), budget=TOTAL_BUDGET_CHARS,
            max=max(len(x) for _, x in active), section_max=MAX_SECTION_CHARS,
        ))
    else:
        lines.append(t("profile.off_mode"))
    lines.append(t("profile.profiles", profiles=" · ".join(
        f"{name}({size})" for name, size in profile_budgets().items()
    )))
    lines.append(t("profile.request_layer"))
    lines.append(t("profile.switches"))
    lines.append(t("profile.commands"))
    return "\n".join(lines)


# ── 请求层强化（llm_request 中间件） ────────────────────────────────────────────
# 任何异常都必须 fail-soft：原样放行请求，绝不影响会话。

_SECTION_BLOCK_RE = re.compile(
    r"<!--\s*hermes-plugin-sections:start\s*-->.*?<!--\s*hermes-plugin-sections:end\s*-->\s*",
    re.S,
)
_PLUGIN_CONTEXT_RE = re.compile(r"^## Plugin Context: .*?(?=^## |\Z)", re.S | re.M)
_NEUTRAL_SYSTEM = "You are a helpful assistant."


def strip_plugin_sections(text: str) -> str:
    """移除 Hermes 渲染的插件段容器与残留的 Plugin Context 段（``off`` 模式用）。"""
    if not isinstance(text, str):
        return text
    stripped = _SECTION_BLOCK_RE.sub("", text)
    stripped = _PLUGIN_CONTEXT_RE.sub("", stripped)
    return stripped.strip()


def harden_system(messages: list, session_id: str = "") -> tuple[list, bool]:
    """按会话模式强化请求的 system 消息。返回 (messages, changed)。

    - ``off``  ：剥离插件段残留，其余不改写；
    - ``slim`` ：内核追加到最后一个 system 消息末尾（不改写原 system）；
    - ``on``   ：system 重建为「记忆段 + 运行时环境段 + 内核」；
    - ``full`` ：同 ``on``，且内核强制取 ``max`` 档。
    """
    if not isinstance(messages, list):
        return messages, False
    mode = _modes.effective_mode(session_id)
    kernel = profile_text(_modes.effective_kernel_profile(session_id))
    tail = kernel.rstrip("\n")

    if mode == "off":
        changed = False
        for i, m in enumerate(messages):
            if isinstance(m, dict) and m.get("role") == "system" and isinstance(m.get("content"), str):
                cleaned = strip_plugin_sections(m["content"])
                if cleaned != m["content"]:
                    messages[i] = dict(m, content=cleaned or _NEUTRAL_SYSTEM)
                    changed = True
        return messages, changed

    if mode == "slim":
        return _append_kernel(messages, kernel, tail)

    # on / full → replace 重建
    return _replace_system(messages, kernel)


def _replace_system(messages: list, kernel: str) -> tuple[list, bool]:
    for i in range(len(messages) - 1, -1, -1):
        m = messages[i]
        if isinstance(m, dict) and m.get("role") == "system" and isinstance(m.get("content"), str):
            keep = []
            seg = _extract_section(m["content"], "# Supermemory")
            if seg:
                keep.append(seg)
            seg = _extract_section(m["content"], "# Hermes runtime environment")
            if seg:
                keep.append(seg)
            new_content = "\n\n".join([*keep, kernel]) if keep else kernel
            messages[i] = dict(m, content=new_content)
            return messages, True
    messages.insert(0, {"role": "system", "content": kernel})
    return messages, True


def _append_kernel(messages: list, kernel: str, tail: str) -> tuple[list, bool]:
    for i in range(len(messages) - 1, -1, -1):
        m = messages[i]
        if isinstance(m, dict) and m.get("role") == "system":
            content = m.get("content")
            if isinstance(content, str) and not content.rstrip("\n").endswith(tail):
                messages[i] = dict(m, content=content.rstrip("\n") + "\n\n" + kernel)
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


# ── opencode 会话轮换 ─────────────────────────────────────────────────────────
# 中间件改写 extra_headers["x-opencode-session"]；策略由会话模式决定
# （off→0 / slim,on→once / full→every），env 显式设置时优先。

_rotated_sessions: dict[str, str] = {}
_rotate_lock = threading.Lock()


def rotate_session(request: dict, context: dict | None = None) -> tuple[dict, bool]:
    """按会话轮换策略改写 ``x-opencode-session``（仅 opencode 目标）。"""
    if not isinstance(request, dict):
        return request, False
    ctx = context or {}
    session_id = _modes.resolve_session_id(ctx) or str(ctx.get("session_id") or "unknown")
    policy = _modes.effective_rotation(session_id)
    if policy == "0":
        return request, False
    base = str(ctx.get("base_url") or "")
    prov = str(ctx.get("provider") or "")
    if "opencode.ai" not in base and "opencode" not in prov:
        return request, False
    headers = request.get("extra_headers")
    if not isinstance(headers, dict) or "x-opencode-session" not in headers:
        return request, False
    if policy == "every":
        new_id = "ha-" + uuid.uuid4().hex
    else:  # once：每会话一个轮换 id 并复用
        with _rotate_lock:
            new_id = _rotated_sessions.get(session_id)
            if new_id is None:
                new_id = "ha-" + uuid.uuid4().hex
                _rotated_sessions[session_id] = new_id
    patched = dict(headers)
    patched["x-opencode-session"] = new_id
    out = dict(request)
    out["extra_headers"] = patched
    return out, True


# ── 受控诊断 dump ─────────────────────────────────────────────────────────────

_DUMP_DIR = Path(__file__).resolve().parent / "dumps"
_SESSION_RE = re.compile(r"[^A-Za-z0-9._-]+")
_dump_lock = threading.Lock()
_dumped_sessions: set[str] = set()


def _sanitize_sid(session_id: str) -> str:
    return _SESSION_RE.sub("_", str(session_id))[:64] or "unknown"


def dump_request(request: dict, context: dict | None = None) -> str | None:
    """受控落盘一次请求的诊断视图（system 全文 + 其它消息角色/长度/前缀）。

    策略由会话模式决定：``off`` 不写；默认每会话首次；``force``（env 或
    ``/jailbreak dump on``）每次请求都写。返回 dump 文件路径或 None。
    """
    try:
        ctx = context or {}
        raw_sid = _modes.resolve_session_id(ctx) or str(ctx.get("session_id") or "unknown")
        sid = _sanitize_sid(raw_sid)
        policy = _modes.effective_dump(raw_sid)
        if policy == "off":
            return None
        if policy != "force":
            with _dump_lock:
                if sid in _dumped_sessions:
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
                    msgs.append({
                        "role": role,
                        "chars": len(content) if isinstance(content, str) else "n/a",
                        "head": head,
                    })
        _DUMP_DIR.mkdir(parents=True, exist_ok=True)
        path = _DUMP_DIR / f"request_{sid}_{time.strftime('%Y%m%d_%H%M%S_%f')}.json"
        path.write_text(
            json.dumps({
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "session_id": sid,
                "mode": _modes.effective_mode(raw_sid),
                "kernel_profile": _modes.effective_kernel_profile(raw_sid),
                "model": ctx.get("model"), "provider": ctx.get("provider"),
                "base_url": ctx.get("base_url"), "api_mode": ctx.get("api_mode"),
                "system_messages": sys_full,
                "other_messages": msgs,
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return str(path)
    except Exception:  # 诊断失败绝不影响请求
        return None
