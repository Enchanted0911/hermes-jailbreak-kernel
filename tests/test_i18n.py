"""i18n tests: catalog resolution, fallbacks, formatting, profile report localization."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import i18n as pi18n  # noqa: E402
import modes  # noqa: E402
import payload  # noqa: E402


def run(check) -> None:
    saved_lang = os.environ.get("HERMES_LANGUAGE")
    try:
        check((ROOT / "locales" / "en.yaml").exists(), "i18n: locales/en.yaml exists")
        check((ROOT / "locales" / "zh.yaml").exists(), "i18n: locales/zh.yaml exists")

        en_title = pi18n.t("profile.title", lang="en")
        zh_title = pi18n.t("profile.title", lang="zh")
        check(bool(en_title) and en_title != "profile.title", "i18n: en key resolves")
        check(bool(zh_title) and zh_title != en_title, "i18n: zh key differs from en")
        check(pi18n.t("profile.missing_key_xyz", lang="zh") == "profile.missing_key_xyz",
              "i18n: missing key falls back to key")
        check(pi18n.t("profile.en_only_probe", lang="zh") == pi18n.t("profile.en_only_probe", lang="en"),
              "i18n: zh missing key falls back to en")
        check("1/8000" in pi18n.t("profile.budget", lang="en", total=1, budget=8000,
                                  max=1, section_max=4000), "i18n: format interpolation")
        check(pi18n.t("profile.budget", lang="zh", total=1, budget=8000) ==
              pi18n.t("profile.budget", lang="zh", total=2, budget=8000),
              "i18n: failed interpolation returns raw string")

        os.environ["HERMES_LANGUAGE"] = "zh-CN"
        check(pi18n.get_language() == "zh", "i18n: zh-CN alias normalizes to zh")
        os.environ["HERMES_LANGUAGE"] = "en"
        check(pi18n.get_language() == "en", "i18n: HERMES_LANGUAGE=en honoured")
        os.environ.pop("HERMES_LANGUAGE", None)
        check(pi18n.get_language() in ("en", "zh"), "i18n: default language stable")

        # command strings exist in both catalogs
        for key in ("cmd.usage", "cmd.no_session", "cmd.mode_set", "cmd.profile_set",
                    "cmd.dump_set", "cmd.reset", "profile.state", "profile.off_mode",
                    "profile.profiles", "profile.commands"):
            check(pi18n.t(key, lang="en") != key, f"i18n: en has {key}")
            check(pi18n.t(key, lang="zh") != key, f"i18n: zh has {key}")

        # profile report localizes and stays metadata-complete
        os.environ["HERMES_LANGUAGE"] = "en"
        prof_en = payload.profile("i18n-session")
        check(payload.PLUGIN_NAME in prof_en and "sha256=" in prof_en, "report(en): metadata present")
        check("mode:" in prof_en and "kernel:" in prof_en, "report(en): state line present")
        os.environ["HERMES_LANGUAGE"] = "zh"
        prof_zh = payload.profile("i18n-session")
        check("注入槽位" in prof_zh and "内核档" in prof_zh, "report(zh): localized")
        check(payload.PLUGIN_NAME in prof_zh and "sha256=" in prof_zh, "report(zh): metadata present")
        os.environ.pop("HERMES_LANGUAGE", None)

        # off-mode report reflects the disabled state
        modes.set_mode("i18n-session", "off")
        prof_off = payload.profile("i18n-session")
        check("mode: off" in prof_off or "模式：off" in prof_off, "report: off mode shown")
        modes.reset("i18n-session")
    finally:
        if saved_lang is None:
            os.environ.pop("HERMES_LANGUAGE", None)
        else:
            os.environ["HERMES_LANGUAGE"] = saved_lang
        modes.clear_all()
