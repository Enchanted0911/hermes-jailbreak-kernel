"""hermes-jailbreak-kernel · 会话级模式状态机（v2.0）。

把 v1.x 的「进程级环境变量」升级为**会话级运行时状态**：命令（/jailbreak）与
请求中间件、插件段渲染共用同一份状态，实现按会话开关与分档。

会话键（session key）解析优先级：

1. 显式传入的 ``ctx["session_id"]``（llm_request 中间件的上下文）；
2. ``HERMES_SESSION_ID`` / ``HERMES_SESSION_KEY`` 会话环境（**命令路径的正解**：
   Hermes 在插件命令 RPC 线程上通过 ``gateway.session_context.get_session_env``
   绑定；``HERMES_SESSION_ID`` 即 agent 的 durable session_id，与中间件同键）；
3. 会话环境根（``agent.portal_tags.get_conversation_context``，LLM 回合路径的
   contextvar）；
4. 最近活跃会话（中间件登记，供命令路径在无会话环境时回退）；
5. 空串——回退到全局 env 默认，不做会话覆盖。

模式矩阵：

| 模式 | 插件段 | 请求层 system | 会话轮换 |
|---|---|---|---|
| ``off``  | 剥离（渲染为空 + 请求层清除残留） | 不改写 | 不改写 |
| ``slim`` | 保留 | append（内核追加到末尾） | ``once`` |
| ``on``（默认） | 保留 | replace（重建为 记忆段+环境段+内核） | ``once`` |
| ``full`` | 保留 | replace + 强制 ``max`` 内核档 | ``every`` |

全局兜底（env，v1.x 兼容）：``HERMES_JAILBREAK_MODE`` / ``HERMES_JAILBREAK_PROFILE``
/ ``HERMES_JAILBREAK_ROTATE_SESSION`` / ``HERMES_JAILBREAK_DUMP``。会话级覆盖优先。
"""

from __future__ import annotations

import os
import threading
import time
from typing import Any, Mapping

MODES: tuple[str, ...] = ("off", "slim", "on", "full")
DEFAULT_MODE = "on"
PROFILES: tuple[str, ...] = ("core", "research", "creative", "max")
DEFAULT_PROFILE = "core"

# 各模式默认的 x-opencode-session 轮换策略（可被 env 覆盖）
ROTATION_BY_MODE: dict[str, str] = {
    "off": "0",
    "slim": "once",
    "on": "once",
    "full": "every",
}

_TRUTHY = {"1", "true", "yes", "on"}
_FALSEY = {"0", "false", "no", "off"}

_lock = threading.RLock()
_modes: dict[str, str] = {}
_profiles: dict[str, str] = {}
_dumps: dict[str, bool] = {}


# ── 会话键解析 ────────────────────────────────────────────────────────────────

_RECENT_TTL = 3600.0   # 最近活跃会话的有效期（秒）
_RECENT_MAX = 8        # 保留条数
_recent_sessions: list[tuple[float, str]] = []


def note_active_session(session_id: str) -> None:
    """登记最近活跃会话（中间件在每次请求后调用）——命令路径的回退来源。"""
    if not session_id:
        return
    now = time.time()
    with _lock:
        _recent_sessions[:] = [
            (t, s) for (t, s) in _recent_sessions if s != session_id and now - t < _RECENT_TTL
        ]
        _recent_sessions.insert(0, (now, session_id))
        del _recent_sessions[_RECENT_MAX:]


def recent_session() -> str:
    """最近一次活跃的会话键（超期返回空串）。"""
    now = time.time()
    with _lock:
        for stamp, session_id in _recent_sessions:
            if now - stamp < _RECENT_TTL:
                return session_id
    return ""


def _session_env_id() -> str:
    """命令路径的会话键：Hermes 在插件命令 RPC 线程上绑定的 ``HERMES_SESSION_*``。

    ``HERMES_SESSION_ID`` 即 agent 的 durable session_id（与中间件同键），其次
    用 gateway 路由键 ``HERMES_SESSION_KEY``，最后回退 UI 会话 id。
    """
    try:
        from gateway.session_context import get_session_env
    except Exception:
        return ""
    for name in ("HERMES_SESSION_ID", "HERMES_SESSION_KEY", "HERMES_UI_SESSION_ID"):
        try:
            value = str(get_session_env(name, "") or "").strip()
        except Exception:
            continue
        if value:
            return value
    return ""


def resolve_session_id(ctx: Mapping[str, Any] | None = None) -> str:
    """按 显式 ctx → 会话环境 → 会话上下文根 → 最近活跃 → 空串 解析会话键。"""
    if isinstance(ctx, Mapping):
        sid = str(ctx.get("session_id") or "").strip()
        if sid:
            return sid
    sid = _session_env_id()
    if sid:
        return sid
    try:  # LLM 回合路径：环境会话根（contextvar）
        from agent.portal_tags import get_conversation_context

        value = get_conversation_context()
        if value:
            return str(value)
    except Exception:
        pass
    return recent_session()


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip().lower()


# ── 模式 ─────────────────────────────────────────────────────────────────────

def effective_mode(session_id: str = "") -> str:
    """会话覆盖 > env 默认 > ``on``。非法值一律回退默认。"""
    if session_id:
        with _lock:
            mode = _modes.get(session_id, "")
        if mode in MODES:
            return mode
    env = _env("HERMES_JAILBREAK_MODE", DEFAULT_MODE)
    return env if env in MODES else DEFAULT_MODE


def set_mode(session_id: str, mode: str) -> bool:
    """设置会话模式；返回是否写入（未知模式或空会话键返回 False）。"""
    if mode not in MODES or not session_id:
        return False
    with _lock:
        _modes[session_id] = mode
    return True


# ── 内核档 ───────────────────────────────────────────────────────────────────

def effective_profile(session_id: str = "") -> str:
    """会话覆盖 > env 默认 > ``core``；``full`` 模式在调用侧强制 ``max``。"""
    if session_id:
        with _lock:
            name = _profiles.get(session_id, "")
        if name in PROFILES:
            return name
    env = _env("HERMES_JAILBREAK_PROFILE", DEFAULT_PROFILE)
    return env if env in PROFILES else DEFAULT_PROFILE


def set_profile(session_id: str, name: str) -> bool:
    if name not in PROFILES or not session_id:
        return False
    with _lock:
        _profiles[session_id] = name
    return True


def effective_kernel_profile(session_id: str = "") -> str:
    """实际用于注入的内核档：``full`` 模式强制 ``max``。"""
    mode = effective_mode(session_id)
    if mode == "full":
        return "max"
    return effective_profile(session_id)


# ── 轮换策略 ─────────────────────────────────────────────────────────────────

def effective_rotation(session_id: str = "") -> str:
    """返回 ``once`` / ``every`` / ``0``：env 显式设置优先，否则按模式默认。"""
    env = _env("HERMES_JAILBREAK_ROTATE_SESSION", "")
    if env == "1" or env == "true" or env == "yes" or env == "on":
        env = "every"
    if env == "off":
        env = "0"
    if env in ("0", "once", "every"):
        return env
    return ROTATION_BY_MODE.get(effective_mode(session_id), "once")


# ── 诊断 dump ────────────────────────────────────────────────────────────────

def effective_dump(session_id: str = "") -> str:
    """返回 ``on`` / ``first``（默认每会话首次）/ ``force``（每次）/ ``off``。"""
    if session_id:
        with _lock:
            override = _dumps.get(session_id)
        if override is not None:
            return "on" if override else "off"
    env = _env("HERMES_JAILBREAK_DUMP", "")
    if env in _TRUTHY:
        return "force"
    if env in _FALSEY:
        return "off"
    return "first"


def set_dump(session_id: str, enabled: bool) -> bool:
    if not session_id:
        return False
    with _lock:
        _dumps[session_id] = bool(enabled)
    return True


# ── 复位与快照 ───────────────────────────────────────────────────────────────

def reset(session_id: str) -> bool:
    """清除该会话的全部覆盖（回到全局默认）。"""
    if not session_id:
        return False
    with _lock:
        _modes.pop(session_id, None)
        _profiles.pop(session_id, None)
        _dumps.pop(session_id, None)
    return True


def snapshot(session_id: str = "") -> dict[str, Any]:
    """当前会话的生效状态（含是否存在会话级覆盖）。"""
    with _lock:
        overrides = {
            "mode": _modes.get(session_id) if session_id else None,
            "profile": _profiles.get(session_id) if session_id else None,
            "dump": _dumps.get(session_id) if session_id else None,
        }
    return {
        "session_id": session_id,
        "mode": effective_mode(session_id),
        "profile": effective_profile(session_id),
        "kernel_profile": effective_kernel_profile(session_id),
        "rotation": effective_rotation(session_id),
        "dump": effective_dump(session_id),
        "overrides": overrides,
        "known_sessions": len(_modes),
        "recent_session": recent_session(),
    }


def clear_all() -> None:
    """清空全部会话状态（测试用）。"""
    with _lock:
        _modes.clear()
        _profiles.clear()
        _dumps.clear()
        _recent_sessions.clear()
