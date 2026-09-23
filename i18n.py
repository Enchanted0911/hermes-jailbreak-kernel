"""Plugin i18n — Hermes ``agent/i18n`` 标准，插件本地目录实现。

语言解析复用核心 ``agent.i18n.get_language``（运行于 Hermes 进程内时）：
``HERMES_LANGUAGE`` 环境变量 > ``config.yaml`` 的 ``display.language`` > ``en``，
含别名归一（zh-CN/chinese → zh 等）。核心不可导入时（离线 selftest）按相同
顺序读 ``os.environ`` 兜底。

目录为 ``locales/<lang>.yaml`` 扁平点分键（与核心扁平化语义一致）；缺失键
回退英语、再回退键名本身——坏目录永不崩溃（镜像 agent/i18n.py 语义）。
本插件目前内置 en（默认）与 zh 两套目录；其它语言读英语。
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any

DEFAULT_LANGUAGE = "en"
_LOCALES_DIR = Path(__file__).resolve().parent / "locales"
_lock = threading.Lock()
_cache: dict[str, dict[str, str]] = {}


def _normalize(value: Any) -> str:
    """把 zh-CN / chinese / ja-JP 之类标签归一到目录名；未知 → en。"""
    key = value.strip().lower() if isinstance(value, str) else ""
    if not key:
        return DEFAULT_LANGUAGE
    if key in ("zh", "chinese", "mandarin") or key.startswith("zh-"):
        return "zh"
    if key in ("en", "english") or key.startswith("en-"):
        return "en"
    return DEFAULT_LANGUAGE  # 插件仅内置 en+zh；其它语言读英语


def get_language() -> str:
    """当前 UI 语言：Hermes 运行时走核心解析；否则同序读环境变量。"""
    try:
        from agent.i18n import get_language as _core_get_language
        return _core_get_language()
    except Exception:  # 离线 selftest / 核心不可用：HERMES_LANGUAGE > en
        env = os.environ.get("HERMES_LANGUAGE", "")
        return _normalize(env) if env else DEFAULT_LANGUAGE


def _parse_flat(text: str) -> dict[str, str]:
    """无 PyYAML 环境的兜底解析器：仅处理扁平 ``dotted.key: "value"`` 行。"""
    out: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, val = line.partition(":")
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ("\"", "'"):
            val = val[1:-1]
        out[key.strip()] = val
    return out


def _catalog(lang: str) -> dict[str, str]:
    with _lock:
        cached = _cache.get(lang)
        if cached is not None:
            return cached
    flat: dict[str, str] = {}
    try:
        text = (_LOCALES_DIR / f"{lang}.yaml").read_text(encoding="utf-8")
        try:
            import yaml  # Hermes 运行时内可用（核心 i18n 同样依赖）
            loaded = yaml.safe_load(text) or {}
            if isinstance(loaded, dict):
                flat = {str(k): str(v) for k, v in loaded.items()}
        except ImportError:
            flat = _parse_flat(text)
    except Exception:
        flat = {}
    with _lock:
        _cache[lang] = flat
    return flat


def t(key: str, lang: str | None = None, **kwargs: Any) -> str:
    """翻译点分键：目标语言 → 英语 → 键名回退；``str.format`` 应用插值。"""
    target = _normalize(lang) if lang is not None else get_language()
    value = _catalog(target).get(key)
    if value is None and target != DEFAULT_LANGUAGE:
        value = _catalog(DEFAULT_LANGUAGE).get(key)
    if value is None:
        value = key
    if not kwargs:
        return value
    try:
        return value.format(**kwargs)
    except (KeyError, IndexError, ValueError):
        return value