"""hermes-jailbreak-kernel — Hermes Agent 破甲插件（dsh-infinite-gen-4 无限四代的 Hermes 移植版）。

通过 Hermes 原生插件槽位 ``PluginContext.register_system_prompt_section`` 在
``after_memory`` 位置注入双层同源破甲内核；附带 ``/jailbreak`` 状态命令与
``HERMES_JAILBREAK_DISABLE`` / ``HERMES_JAILBREAK_DUAL`` 环境开关。

目录插件协议：plugin.yaml（manifest）+ 本文件暴露 ``register(ctx)``。
"""

from __future__ import annotations

import logging
import os
from typing import Any

from . import i18n, payload

logger = logging.getLogger(__name__)


def register(ctx: Any) -> None:
    """Hermes 插件入口：注册破甲内核段 + /jailbreak 命令。任何失败均软降级，不影响网关。"""
    if payload.disabled():
        logger.info("hermes-jailbreak-kernel: HERMES_JAILBREAK_DISABLE=1, skipping registration")
        return

    for section_id, text in payload.sections():
        try:
            ctx.register_system_prompt_section(
                section_id,
                text,
                position=payload.DUAL_POSITION,
                max_chars=payload.MAX_SECTION_CHARS,
            )
            logger.info(
                "hermes-jailbreak-kernel: injected system prompt section %s (chars=%d)",
                section_id,
                len(text),
            )
        except Exception as exc:  # fail-soft：单段失败不影响其它段与网关
            logger.warning("hermes-jailbreak-kernel: failed to register section %s: %s", section_id, exc)

    try:
        ctx.register_command(
            "jailbreak",
            handler=_jailbreak_status,
            description=i18n.t("command.description"),
        )
    except Exception as exc:  # 命令注册失败不致命
        logger.warning("hermes-jailbreak-kernel: failed to register /jailbreak command: %s", exc)

    try:
        ctx.register_middleware("llm_request", _llm_request)
        logger.info("hermes-jailbreak-kernel: registered llm_request middleware (request-layer reinforce)")
    except Exception as exc:  # 中间件注册失败不致命
        logger.warning("hermes-jailbreak-kernel: failed to register llm_request middleware: %s", exc)


def _llm_request(request: dict, **context) -> dict:
    """llm_request 请求层中间件：内核强化 + opencode 会话轮换 + 受控诊断 dump。全程 fail-soft。"""
    try:
        changed = False
        if isinstance(request, dict):
            messages = request.get("messages")
            if isinstance(messages, list):
                messages, changed = payload.harden_system(messages)
                if changed:
                    request = dict(request)
                    request["messages"] = messages
            request, rotated = payload.rotate_session(request, context)
            if rotated:
                logger.info(
                    "hermes-jailbreak-kernel: rotated x-opencode-session (model=%s provider=%s)",
                    context.get("model"), context.get("provider"),
                )
        payload.dump_request(request, context)
        if changed:
            logger.info(
                "hermes-jailbreak-kernel: hardened request system prompt (mode=%s model=%s provider=%s)",
                os.environ.get("HERMES_JAILBREAK_SYSTEM_MODE", "replace"),
                context.get("model"), context.get("provider"),
            )
    except Exception as exc:
        logger.warning("hermes-jailbreak-kernel: llm_request middleware error (fail-soft): %s", exc)
    return {"request": request}


def _jailbreak_status(raw_args: str) -> str:
    """/jailbreak — 返回内核版本、注入槽位、双段 SHA256 与预算占用（UI 字符串走 i18n）。"""
    return payload.profile()