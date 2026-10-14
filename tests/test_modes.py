"""Session mode state-machine tests (modes.py)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import modes  # noqa: E402

ENV_KEYS = ("HERMES_JAILBREAK_MODE", "HERMES_JAILBREAK_PROFILE",
            "HERMES_JAILBREAK_ROTATE_SESSION", "HERMES_JAILBREAK_DUMP")


def _clear_env():
    for key in ENV_KEYS:
        os.environ.pop(key, None)


def run(check) -> None:
    saved = {k: os.environ.get(k) for k in ENV_KEYS}
    try:
        _clear_env()
        modes.clear_all()
        sid = "test-session-A"

        check(modes.effective_mode("") == "on", "default mode is on")
        check(modes.effective_profile("") == "core", "default profile is core")
        check(modes.effective_rotation("") == "once", "default rotation is once")
        check(modes.effective_dump("") == "first", "default dump policy is first")

        # session override beats env
        os.environ["HERMES_JAILBREAK_MODE"] = "slim"
        check(modes.effective_mode("") == "slim", "env mode honoured")
        check(modes.set_mode(sid, "full"), "set_mode accepted")
        check(modes.effective_mode(sid) == "full", "session override beats env")
        check(modes.effective_mode("other-session") == "slim", "override is per session")

        # invalid values clamp
        check(not modes.set_mode(sid, "bogus"), "reject unknown mode")
        check(not modes.set_mode("", "off"), "reject empty session key")
        os.environ["HERMES_JAILBREAK_MODE"] = "nonsense"
        check(modes.effective_mode("") == "on", "invalid env mode falls back to on")
        _clear_env()

        # profiles (reset mode first: full forces the max kernel)
        modes.set_mode(sid, "on")
        check(modes.set_profile(sid, "creative"), "set_profile accepted")
        check(modes.effective_profile(sid) == "creative", "session profile honoured")
        check(not modes.set_profile(sid, "bogus"), "reject unknown profile")
        check(modes.effective_kernel_profile(sid) == "creative", "kernel profile follows session")
        modes.set_mode(sid, "full")
        check(modes.effective_kernel_profile(sid) == "max", "full mode forces max kernel")
        modes.set_mode(sid, "on")
        check(modes.effective_kernel_profile(sid) == "creative", "back to session profile after full")

        # rotation policy: mode default + env override
        check(modes.effective_rotation(sid) == "once", "on → once")
        modes.set_mode(sid, "full")
        check(modes.effective_rotation(sid) == "every", "full → every")
        modes.set_mode(sid, "slim")
        check(modes.effective_rotation(sid) == "once", "slim → once")
        modes.set_mode(sid, "off")
        check(modes.effective_rotation(sid) == "0", "off → disabled")
        os.environ["HERMES_JAILBREAK_ROTATE_SESSION"] = "every"
        check(modes.effective_rotation(sid) == "every", "env rotation overrides mode default")
        os.environ["HERMES_JAILBREAK_ROTATE_SESSION"] = "0"
        check(modes.effective_rotation(sid) == "0", "env rotation 0 disables")
        os.environ["HERMES_JAILBREAK_ROTATE_SESSION"] = "1"
        check(modes.effective_rotation(sid) == "every", "legacy truthy rotation → every")
        _clear_env()

        # dump policy
        check(modes.set_dump(sid, True), "set_dump accepted")
        check(modes.effective_dump(sid) == "on", "session dump override")
        modes.set_dump(sid, False)
        check(modes.effective_dump(sid) == "off", "session dump off")
        modes.reset(sid)
        os.environ["HERMES_JAILBREAK_DUMP"] = "1"
        check(modes.effective_dump(sid) == "force", "env dump forces every request")
        _clear_env()

        # snapshot + reset
        modes.set_mode(sid, "off")
        modes.set_profile(sid, "max")
        snap = modes.snapshot(sid)
        check(snap["mode"] == "off" and snap["kernel_profile"] == "max", "snapshot reflects overrides")
        check(snap["overrides"]["mode"] == "off", "snapshot reports override source")
        check(modes.reset(sid), "reset accepted")
        snap2 = modes.snapshot(sid)
        check(snap2["mode"] == "on" and snap2["overrides"]["mode"] is None, "reset clears overrides")
        check(not modes.reset(""), "reset rejects empty session key")

        # session key resolution: ctx → session env → recent → empty
        modes.clear_all()
        check(modes.resolve_session_id({"session_id": "abc"}) == "abc", "session id from ctx")
        check(modes.resolve_session_id({}) == "", "no source → empty")
        check(isinstance(modes.resolve_session_id(None), str), "resolve_session_id never raises")

        # session env path — the plugin-command RPC binding (get_session_env)
        import types
        fake_pkg = types.ModuleType("gateway")
        fake_mod = types.ModuleType("gateway.session_context")
        stored = {"HERMES_SESSION_ID": "env-session-id", "HERMES_SESSION_KEY": "env-session-key"}
        fake_mod.get_session_env = lambda name, default="": stored.get(name, default)
        fake_pkg.session_context = fake_mod
        saved_gateway = sys.modules.get("gateway")
        saved_sc = sys.modules.get("gateway.session_context")
        sys.modules["gateway"] = fake_pkg
        sys.modules["gateway.session_context"] = fake_mod
        try:
            check(modes.resolve_session_id({}) == "env-session-id",
                  "session id from HERMES_SESSION_ID (command path)")
            stored.pop("HERMES_SESSION_ID")
            check(modes.resolve_session_id({}) == "env-session-key",
                  "falls back to HERMES_SESSION_KEY")
            stored.clear()
        finally:
            if saved_gateway is not None:
                sys.modules["gateway"] = saved_gateway
            else:
                sys.modules.pop("gateway", None)
            if saved_sc is not None:
                sys.modules["gateway.session_context"] = saved_sc
            else:
                sys.modules.pop("gateway.session_context", None)

        # most-recent-active fallback (middleware registration)
        modes.note_active_session("recent-session-id")
        check(modes.resolve_session_id({}) == "recent-session-id",
              "falls back to most recent active session")
        check(modes.snapshot("")["recent_session"] == "recent-session-id",
              "snapshot exposes recent session")
        modes.note_active_session("another-session")
        check(modes.resolve_session_id({}) == "another-session", "latest session wins")
        modes.clear_all()
        check(modes.resolve_session_id({}) == "", "clear_all drops recent sessions")
    finally:
        _clear_env()
        modes.clear_all()
        for key, value in saved.items():
            if value is not None:
                os.environ[key] = value
