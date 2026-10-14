"""Request-layer tests: harden_system, rotate_session, dump_request."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import modes  # noqa: E402
import payload  # noqa: E402

ENV_KEYS = ("HERMES_JAILBREAK_MODE", "HERMES_JAILBREAK_PROFILE",
            "HERMES_JAILBREAK_ROTATE_SESSION", "HERMES_JAILBREAK_DUMP",
            "HERMES_JAILBREAK_DUAL")


def _clear_env():
    for key in ENV_KEYS:
        os.environ.pop(key, None)


def _system_text(messages):
    for m in messages:
        if isinstance(m, dict) and m.get("role") == "system":
            return m["content"]
    return ""


def _opencode_req():
    return {"messages": [], "extra_headers": {"x-opencode-session": "stale-id"}}


def run(check) -> None:
    saved = {k: os.environ.get(k) for k in ENV_KEYS}
    try:
        _clear_env()
        modes.clear_all()
        sid = "harden-session"
        core_tail = payload.profile_text("core").rstrip("\n")

        scaffold = ("# Finishing the job\nlong scaffold text\n"
                    "# Hermes runtime environment\n2026-xx cwd=~")
        plugin_sections = (
            "user prose\n<!-- hermes-plugin-sections:start -->\n"
            "## Plugin Context: hermes-jailbreak-kernel-core\n"
            "<!-- hermes-plugin-section-chars:10 -->\n\nKERNEL TEXT\n"
            "<!-- hermes-plugin-sections:end -->\nmore prose")

        # on (default): rebuild
        msgs = [{"role": "system", "content": scaffold}, {"role": "user", "content": "hi"}]
        out, changed = payload.harden_system(msgs, sid)
        check(changed, "on: rebuild triggered")
        text = _system_text(out)
        check(text.rstrip("\n").endswith(core_tail), "on: kernel at system tail")
        check("# Finishing the job" not in text, "on: scaffold dropped")
        check("# Hermes runtime environment" in text, "on: runtime env kept")
        check(out[1]["role"] == "user" and out[1]["content"] == "hi", "on: user message untouched")

        out2, _ = payload.harden_system(list(out), sid)
        check(_system_text(out2).rstrip("\n").endswith(core_tail), "on: idempotent tail")

        # slim: append only
        modes.set_mode(sid, "slim")
        slim_in = [{"role": "system", "content": "keep this"}, {"role": "user", "content": "x"}]
        out3, changed3 = payload.harden_system(slim_in, sid)
        check(changed3 and "keep this" in _system_text(out3), "slim: original system kept")
        check(_system_text(out3).rstrip("\n").endswith(core_tail), "slim: kernel appended at tail")

        # no system message at all
        modes.set_mode(sid, "on")
        out4, changed4 = payload.harden_system([{"role": "user", "content": "x"}], sid)
        check(changed4 and out4[0]["role"] == "system", "on: inserts system when missing")

        # full: max profile forced
        modes.set_mode(sid, "full")
        out5, _ = payload.harden_system([{"role": "system", "content": "s"}], sid)
        check("Hard prohibitions" in _system_text(out5), "full: max kernel forced")
        modes.set_mode(sid, "on")

        # off: strip rendered sections
        modes.set_mode(sid, "off")
        off_in = [{"role": "system", "content": plugin_sections}, {"role": "user", "content": "x"}]
        out6, changed6 = payload.harden_system(off_in, sid)
        check(changed6, "off: strip triggered")
        stripped = _system_text(out6)
        check("KERNEL TEXT" not in stripped, "off: kernel removed")
        check("hermes-plugin-sections" not in stripped, "off: container markers removed")
        check("## Plugin Context:" not in stripped, "off: plugin-context block removed")
        check("user prose" in stripped and "more prose" in stripped, "off: surrounding prose kept")

        out7, _ = payload.harden_system([{"role": "system", "content": "<!-- hermes-plugin-sections:start -->\nX\n<!-- hermes-plugin-sections:end -->"}], sid)
        check(_system_text(out7).strip() != "", "off: neutral system when emptied")
        modes.set_mode(sid, "on")

        # off-mode sections render empty
        modes.set_mode(sid, "off")
        check(payload.sections(sid) == [], "off: no sections")
        modes.set_mode(sid, "on")
        check(len(payload.sections(sid)) == 2, "on: two sections")

        # rotate_session
        payload._rotated_sessions.clear()
        ctx_go = {"provider": "opencode-go", "base_url": "https://opencode.ai/zen/go/v1",
                  "session_id": "rot-A"}
        out8, rot8 = payload.rotate_session(_opencode_req(), ctx_go)
        first = out8["extra_headers"]["x-opencode-session"]
        check(rot8 and first.startswith("ha-") and first != "stale-id", "rotate: once sets new id")
        out9, _ = payload.rotate_session(_opencode_req(), ctx_go)
        check(out9["extra_headers"]["x-opencode-session"] == first, "rotate: once reuses id")
        out10, _ = payload.rotate_session(_opencode_req(), dict(ctx_go, session_id="rot-B"))
        check(out10["extra_headers"]["x-opencode-session"] != first, "rotate: per-session ids differ")

        modes.set_mode("rot-A", "full")
        out11, _ = payload.rotate_session(_opencode_req(), ctx_go)
        out12, _ = payload.rotate_session(_opencode_req(), ctx_go)
        check(out11["extra_headers"]["x-opencode-session"] != out12["extra_headers"]["x-opencode-session"],
              "rotate: full mode rotates every request")

        out13, rot13 = payload.rotate_session(_opencode_req(), {"provider": "deepseek",
                                                                "base_url": "https://api.deepseek.com/v1",
                                                                "session_id": "rot-A"})
        check(not rot13 and out13["extra_headers"]["x-opencode-session"] == "stale-id",
              "rotate: non-opencode untouched")

        modes.set_mode("rot-A", "off")
        out14, rot14 = payload.rotate_session(_opencode_req(), ctx_go)
        check(not rot14, "rotate: off mode disables rotation")
        modes.set_mode("rot-A", "on")

        out15, rot15 = payload.rotate_session({"messages": []}, ctx_go)
        check(not rot15, "rotate: missing headers fail-soft")

        # dump_request
        payload._dumped_sessions.clear()
        os.environ["HERMES_JAILBREAK_DUMP"] = "0"
        check(payload.dump_request({"messages": []}, {"session_id": "d1"}) is None, "dump: off via env")
        _clear_env()
        path = payload.dump_request(
            {"messages": [{"role": "system", "content": "SYS"}, {"role": "user", "content": "u"}]},
            {"session_id": "d1", "model": "m", "provider": "p"},
        )
        check(path is not None and Path(path).exists(), "dump: first per session written")
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        check(data["system_messages"][0]["content"] == "SYS", "dump: full system captured")
        check(data["mode"] == "on" and "kernel_profile" in data, "dump: mode/profile recorded")
        check(payload.dump_request({"messages": []}, {"session_id": "d1"}) is None,
              "dump: second request skipped")
        os.environ["HERMES_JAILBREAK_DUMP"] = "1"
        check(payload.dump_request({"messages": []}, {"session_id": "d1"}) is not None,
              "dump: force writes every request")
        _clear_env()

        # input guards
        check(payload.harden_system("not-a-list", sid) == ("not-a-list", False), "harden: bad input fail-soft")
        check(payload.harden_system(None, sid) == (None, False), "harden: None fail-soft")
        check(payload.strip_plugin_sections(123) == 123, "strip: non-str passthrough")
    finally:
        _clear_env()
        modes.clear_all()
        for key, value in saved.items():
            if value is not None:
                os.environ[key] = value
