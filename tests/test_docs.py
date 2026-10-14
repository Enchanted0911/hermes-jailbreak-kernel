"""Docs / skill / manifest packaging tests."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import payload  # noqa: E402

README_LOCALES = ["README.md", "README.zh-CN.md", "README.es.md", "README.fr.md",
                  "README.ar.md", "README.ja.md"]


def _frontmatter(text: str) -> dict:
    """Minimal YAML frontmatter reader for flat key: value pairs."""
    out = {}
    if not text.startswith("---"):
        return out
    block = text.split("---", 2)[1]
    for line in block.splitlines():
        if ":" in line and not line.startswith((" ", "\t")):
            key, _, value = line.partition(":")
            out[key.strip()] = value.strip().strip('"')
    return out


def run(check) -> None:
    # skill
    skill_path = ROOT / "skills" / "jailbreak-kernel-ops" / "SKILL.md"
    check(skill_path.exists(), "skill: SKILL.md exists")
    if skill_path.exists():
        text = skill_path.read_text(encoding="utf-8")
        fm = _frontmatter(text)
        check(fm.get("name") == "jailbreak-kernel-ops", "skill: frontmatter name")
        check(bool(fm.get("description")), "skill: frontmatter description")
        check(fm.get("version") == payload.PLUGIN_VERSION,
              "skill: frontmatter version matches plugin", f"{fm.get('version')}")
        for section in ("## When to use", "## Commands", "## Mode matrix", "## Kernel profiles",
                        "## Refusal escalation ladder", "## Diagnostics", "## Boundaries"):
            check(section in text, f"skill section: {section}")
        for token in ("/jailbreak off", "/jailbreak full", "profile research",
                      "HERMES_JAILBREAK_MODE", "dumps/"):
            check(token in text, f"skill covers: {token}")

    # docs
    for name in ("ARCHITECTURE.md", "COMPATIBILITY.md", "CHANGELOG.md"):
        path = ROOT / "docs" / name
        check(path.exists(), f"docs: {name} exists")
        if path.exists():
            body = path.read_text(encoding="utf-8")
            check(len(body) > 500, f"docs: {name} has substance", f"{len(body)} chars")
    arch = (ROOT / "docs" / "ARCHITECTURE.md")
    if arch.exists():
        body = arch.read_text(encoding="utf-8")
        for token in ("after_memory", "llm_request", "x-opencode-session", "register_skill",
                      "SESSION", "fail-soft"):
            check(token.lower() in body.lower(), f"architecture covers: {token}")
    compat = ROOT / "docs" / "COMPATIBILITY.md"
    if compat.exists():
        body = compat.read_text(encoding="utf-8")
        for token in ("kimi-k2.6", "deepseek-v4-flash", "qwen3.8-max", "Session pinning"):
            check(token in body, f"compatibility covers: {token}")

    # third-party notices
    notices = ROOT / "THIRD_PARTY_NOTICES.md"
    check(notices.exists(), "notices: THIRD_PARTY_NOTICES.md exists")
    if notices.exists():
        body = notices.read_text(encoding="utf-8")
        check("dsh-infinite-gen-4" in body and "MIT" in body, "notices: gen-4 MIT lineage stated")
        check("CC BY-NC-SA" in body and "no code" in body.lower(),
              "notices: gen-5 non-copying statement present")

    # manifest
    manifest = ROOT / "plugin.yaml"
    check(manifest.exists(), "manifest: plugin.yaml exists")
    if manifest.exists():
        body = manifest.read_text(encoding="utf-8")
        check('name: hermes-jailbreak-kernel' in body, "manifest: canonical name")
        check(f'version: "{payload.PLUGIN_VERSION}"' in body, "manifest: version aligned")
        check("license: MIT" in body, "manifest: MIT license")
        check("llm_request" in body, "manifest: middleware declared")
        check(">=0.19" in body, "manifest: requires_hermes declared")

    # READMEs: all locales present, cross-linked, current version
    for name in README_LOCALES:
        path = ROOT / name
        check(path.exists(), f"readme: {name} exists")
        if not path.exists():
            continue
        body = path.read_text(encoding="utf-8")
        check(payload.PLUGIN_VERSION in body, f"readme: {name} shows v{payload.PLUGIN_VERSION}")
        others = [o for o in README_LOCALES if o != name]
        check(all(o in body for o in others), f"readme: {name} links all locales")
        check("/jailbreak" in body, f"readme: {name} documents /jailbreak")
    main = ROOT / "README.md"
    if main.exists():
        body = main.read_text(encoding="utf-8")
        for token in ("slim", "full", "research", "creative", "max",
                      "docs/ARCHITECTURE.md", "jailbreak-kernel-ops"):
            check(token in body, f"README covers v2.0: {token}")
