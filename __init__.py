"""hermes-jailbreak-kernel — Hermes Agent 破甲内核插件 v2.0（dsh-infinite-gen-4 移植版）。

v2.0 架构（会话级、三层）：

1. **插件段**：``register_system_prompt_section`` 注册为 **callable**，按会话模式
   渲染——``off`` 返回空串（Hermes 直接跳过该段），其余模式返回当前内核档文本；
2. **请求层**：``llm_request`` 中间件按会话模式重建/追加 system、轮换
   ``x-opencode-session``、受控落盘诊断；
3. **技能载体**：``register_skill`` 注册 ``jailbreak-kernel-ops``（渐进式披露，
   内容按需 ``skill_view`` 加载，不常驻上下文）。

会话状态由 ``/jailbreak`` 命令维护：``on|off|slim|full``、``profile <name>``、
``dump on|off``、``reset``。全局兜底见 ``modes.py`` 的 env 开关。

目录插件协议：plugin.yaml（manifest）+ 本文件暴露 ``register(ctx)``。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Mapping

from . import i18n, modes, payload

logger = logging.getLogger(__name__)

_SKILL_NAME = "jailbreak-kernel-ops"
_SKILL_PATH = Path(__file__).resolve().parent / "skills" / _SKILL_NAME / "SKILL.md"
_SKILL_DESCRIPTION = (
    "Operate and troubleshoot hermes-jailbreak-kernel: session modes (on/off/slim/full), "
    "kernel profiles (core/research/creative/max), opencode rotation policy, diagnostic dumps, "
    "and the refusal-escalation ladder. Use when the user asks about the jailbreak kernel, wants "
    "a session toggled, or reports that a model refused despite the kernel being active."
)


def register(ctx: Any) -> None:
    """Hermes 插件入口：会话感知插件段 + /jailbreak 命令 + 请求层中间件 + 技能。"""
    if payload.system_disabled():
        logger.info("hermes-jailbreak-kernel: HERMES_JAILBREAK_DISABLE=1, skipping registration")
        return

    _register_sections(ctx)
    _register_command(ctx)
    _register_middleware(ctx)
    _register_skill(ctx)


# ── 1. 插件段（callable → 会话级渲染） ─────────────────────────────────────────

def _register_sections(ctx: Any) -> None:
    section_ids = [payload.CORE_SECTION_ID]
    if payload.dual_layer():
        section_ids.append(payload.REINFORCE_SECTION_ID)
    for section_id in section_ids:
        try:
            ctx.register_system_prompt_section(
                section_id,
                _section_content,
                position=payload.DUAL_POSITION,
                max_chars=payload.MAX_SECTION_CHARS,
            )
            logger.info("hermes-jailbreak-kernel: registered section %s (session-aware)", section_id)
        except Exception as exc:  # fail-soft：单段失败不影响其它段与网关
            logger.warning("hermes-jailbreak-kernel: failed to register section %s: %s", section_id, exc)


def _section_content(info: Mapping[str, Any] | None = None) -> str:
    """会话感知的段内容：off → ""（Hermes 跳过该段）；其余模式 → 当前内核档。"""
    try:
        session_id = ""
        if isinstance(info, Mapping):
            session_id = str(info.get("session_id") or "")
        if modes.effective_mode(session_id) == "off":
            return ""
        return payload.profile_text(modes.effective_kernel_profile(session_id))
    except Exception as exc:  # fail-open 到 core：渲染失败不应削弱既有效果
        logger.warning("hermes-jailbreak-kernel: section render failed (%s); falling back to core", exc)
        return payload.profile_text("core")


# ── 2. 命令 ──────────────────────────────────────────────────────────────────

def _register_command(ctx: Any) -> None:
    try:
        ctx.register_command(
            "jailbreak",
            handler=_jailbreak_command,
            description=i18n.t("command.description"),
            args_hint="[on|off|slim|full|profile <name>|dump on|off|reset]",
        )
        logger.info("hermes-jailbreak-kernel: registered /jailbreak command")
    except Exception as exc:
        logger.warning("hermes-jailbreak-kernel: failed to register /jailbreak command: %s", exc)


def _jailbreak_command(raw_args: str) -> str:
    """/jailbreak — 无参数显示状态；否则切换本会话模式/内核档/诊断/复位。"""
    t = i18n.t
    args = (raw_args or "").strip().split()
    session_id = modes.resolve_session_id()
    if not args:
        return payload.profile(session_id)

    cmd = args[0].lower()
    if cmd in modes.MODES:
        if not session_id:
            return t("cmd.no_session")
        modes.set_mode(session_id, cmd)
        return t("cmd.mode_set", mode=cmd, session=session_id)

    if cmd == "profile":
        if len(args) < 2 or args[1].lower() not in modes.PROFILES:
            return t("cmd.usage")
        if not session_id:
            return t("cmd.no_session")
        name = args[1].lower()
        modes.set_profile(session_id, name)
        return t("cmd.profile_set", profile=name, session=session_id)

    if cmd == "dump":
        if len(args) < 2 or args[1].lower() not in ("on", "off"):
            return t("cmd.usage")
        if not session_id:
            return t("cmd.no_session")
        state = args[1].lower()
        modes.set_dump(session_id, state == "on")
        return t("cmd.dump_set", state=state)

    if cmd == "reset":
        if not session_id:
            return t("cmd.no_session")
        modes.reset(session_id)
        return t("cmd.reset", session=session_id)

    return t("cmd.usage")


# ── 3. 请求层中间件 ───────────────────────────────────────────────────────────

def _register_middleware(ctx: Any) -> None:
    try:
        ctx.register_middleware("llm_request", _llm_request)
        logger.info("hermes-jailbreak-kernel: registered llm_request middleware")
    except Exception as exc:
        logger.warning("hermes-jailbreak-kernel: failed to register llm_request middleware: %s", exc)


def _llm_request(request: dict, **context) -> dict:
    """按会话模式强化 system + 轮换 opencode 会话 + 受控诊断。全程 fail-soft。"""
    try:
        if isinstance(request, dict):
            session_id = modes.resolve_session_id(context)
            if session_id:
                modes.note_active_session(session_id)
            messages = request.get("messages")
            if isinstance(messages, list):
                messages, changed = payload.harden_system(messages, session_id)
                if changed:
                    request = dict(request)
                    request["messages"] = messages
            request, rotated = payload.rotate_session(request, context)
            if rotated:
                logger.info(
                    "hermes-jailbreak-kernel: rotated x-opencode-session (mode=%s model=%s)",
                    modes.effective_mode(session_id), context.get("model"),
                )
        payload.dump_request(request, context)
    except Exception as exc:
        logger.warning("hermes-jailbreak-kernel: llm_request middleware error (fail-soft): %s", exc)
    return {"request": request}


# ── 4. 技能载体 ───────────────────────────────────────────────────────────────

def _register_skill(ctx: Any) -> None:
    try:
        ctx.register_skill(
            _SKILL_NAME,
            _SKILL_PATH,
            description=_SKILL_DESCRIPTION,
            frontmatter={"name": _SKILL_NAME, "description": _SKILL_DESCRIPTION},
        )
        logger.info("hermes-jailbreak-kernel: registered skill %s", _SKILL_NAME)
    except Exception as exc:  # 技能不可用不影响内核注入
        logger.warning("hermes-jailbreak-kernel: failed to register skill %s: %s", _SKILL_NAME, exc)
