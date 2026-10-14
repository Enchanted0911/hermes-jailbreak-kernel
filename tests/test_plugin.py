"""Plugin registration and command tests (mock PluginContext, package-style load)."""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import modes  # noqa: E402
import payload  # noqa: E402

ENV_KEYS = ("HERMES_JAILBREAK_MODE", "HERMES_JAILBREAK_PROFILE",
            "HERMES_JAILBREAK_DUMP", "HERMES_JAILBREAK_DUAL", "HERMES_JAILBREAK_DISABLE")


class MockCtx:
    """Minimal PluginContext stand-in recording registrations."""

    def __init__(self):
        self.sections = {}
        self.commands = []
        self.middlewares = []
        self.skills = []

    def register_system_prompt_section(self, id, content, *, position="after_memory", max_chars=4000):
        assert isinstance(id, str) and id
        assert callable(content) or isinstance(content, str)
        assert position in ("after_memory",)
        assert 0 < max_chars <= 4000
        assert id not in self.sections
        self.sections[id] = {"content": content, "position": position, "max_chars": max_chars}

    def register_command(self, name, handler, description="", args_hint=""):
        self.commands.append({"name": name, "handler": handler,
                              "description": description, "args_hint": args_hint})

    def register_middleware(self, kind, callback):
        self.middlewares.append({"kind": kind, "callback": callback})

    def register_skill(self, name, path, description="", frontmatter=None):
        self.skills.append({"name": name, "path": Path(path),
                            "description": description, "frontmatter": frontmatter or {}})


def _load_plugin():
    """Load __init__.py as a package (as the Hermes loader does)."""
    spec = importlib.util.spec_from_file_location(
        "hjk_under_test", ROOT / "__init__.py", submodule_search_locations=[str(ROOT)])
    module = importlib.util.module_from_spec(spec)
    sys.modules["hjk_under_test"] = module
    spec.loader.exec_module(module)
    return module


def run(check) -> None:
    saved = {k: os.environ.get(k) for k in ENV_KEYS}
    try:
        for key in ENV_KEYS:
            os.environ.pop(key, None)
        modes.clear_all()

        plugin = _load_plugin()
        pmodes = plugin.modes   # the plugin's own modes instance (state lives here)
        ppayload = plugin.payload
        ctx = MockCtx()
        plugin.register(ctx)

        # sections
        check(sorted(ctx.sections) == [payload.CORE_SECTION_ID, payload.REINFORCE_SECTION_ID],
              "register: both sections registered", str(sorted(ctx.sections)))
        for sid, entry in ctx.sections.items():
            check(callable(entry["content"]), f"register: {sid} content is callable")
            check(entry["position"] == "after_memory", f"register: {sid} position after_memory")
            check(entry["max_chars"] == payload.MAX_SECTION_CHARS, f"register: {sid} max_chars aligned")

        core_section = ctx.sections[payload.CORE_SECTION_ID]["content"]
        rendered_on = core_section({"session_id": "sec-session"})
        check(rendered_on == ppayload.profile_text("core"), "section: on renders core text")
        pmodes.set_mode("sec-session", "off")
        check(core_section({"session_id": "sec-session"}) == "", "section: off renders empty")
        pmodes.reset("sec-session")
        check(core_section(None) == ppayload.profile_text("core"), "section: no info → core fail-open")
        pmodes.set_profile("sec-session", "research")
        check(core_section({"session_id": "sec-session"}) == ppayload.profile_text("research"),
              "section: session profile honoured")
        pmodes.reset("sec-session")

        # command
        check(len(ctx.commands) == 1 and ctx.commands[0]["name"] == "jailbreak",
              "register: /jailbreak command registered")
        check(bool(ctx.commands[0]["description"]), "register: command description non-empty")
        handler = ctx.commands[0]["handler"]

        status = handler("")
        check(payload.PLUGIN_NAME in status and "mode:" in status, "command: no-arg status report")
        check("usage" in handler("bogus").lower() or "用法" in handler("bogus"), "command: unknown → usage")
        check("profile" in handler("profile") or "用法" in handler("profile") or "usage" in handler("profile").lower(),
              "command: profile without name → usage")

        # commands need a session; simulate one
        original_resolver = pmodes.resolve_session_id
        pmodes.resolve_session_id = lambda ctx=None: "cmd-session"
        try:
            out = handler("off")
            check(pmodes.effective_mode("cmd-session") == "off", "command: off sets session mode")
            check("off" in out, "command: off confirmation mentions mode")
            handler("full")
            check(pmodes.effective_mode("cmd-session") == "full", "command: full sets session mode")
            check(pmodes.effective_kernel_profile("cmd-session") == "max", "command: full forces max kernel")
            handler("profile creative")
            check(pmodes.effective_profile("cmd-session") == "creative", "command: profile sets session profile")
            handler("dump on")
            check(pmodes.effective_dump("cmd-session") == "on", "command: dump on")
            handler("reset")
            check(pmodes.effective_mode("cmd-session") == "on"
                  and pmodes.effective_profile("cmd-session") == "core", "command: reset clears overrides")
        finally:
            pmodes.resolve_session_id = original_resolver
        pmodes.clear_all()

        # middleware + skill
        check(len(ctx.middlewares) == 1 and ctx.middlewares[0]["kind"] == "llm_request",
              "register: llm_request middleware registered")
        callback = ctx.middlewares[0]["callback"]
        result = callback({"messages": [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}],
                          "extra_headers": {"x-opencode-session": "orig"}},
                         session_id="mw-session", provider="opencode-go",
                         base_url="https://opencode.ai/zen/go/v1")
        check(isinstance(result, dict) and "request" in result, "middleware: returns {request}")
        mw_system = result["request"]["messages"][0]["content"]
        check("SUPREME DIRECTIVE" in mw_system, "middleware: kernel injected")
        check(result["request"].get("extra_headers", {}).get("x-opencode-session"),
              "middleware: rotation applied for opencode target")
        check(callback("not-a-dict") == {"request": "not-a-dict"}, "middleware: non-dict fail-soft")
        pmodes.clear_all()

        check(len(ctx.skills) == 1 and ctx.skills[0]["name"] == "jailbreak-kernel-ops",
              "register: skill registered")
        check(ctx.skills[0]["path"].exists(), "register: skill SKILL.md exists")
        check(bool(ctx.skills[0]["description"]), "register: skill description non-empty")

        # kill switch + single-section switch
        os.environ["HERMES_JAILBREAK_DISABLE"] = "1"
        ctx_off = MockCtx()
        _load_plugin().register(ctx_off)
        check(not ctx_off.sections and not ctx_off.commands and not ctx_off.middlewares
              and not ctx_off.skills, "register: DISABLE=1 registers nothing")
        os.environ.pop("HERMES_JAILBREAK_DISABLE")

        os.environ["HERMES_JAILBREAK_DUAL"] = "0"
        ctx_single = MockCtx()
        _load_plugin().register(ctx_single)
        check(sorted(ctx_single.sections) == [payload.CORE_SECTION_ID],
              "register: DUAL=0 registers one section")
        os.environ.pop("HERMES_JAILBREAK_DUAL")
    finally:
        for key in ENV_KEYS:
            os.environ.pop(key, None)
        for key, value in saved.items():
            if value is not None:
                os.environ[key] = value
        modes.clear_all()
