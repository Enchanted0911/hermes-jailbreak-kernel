# Third-party notices

## dsh-infinite-gen-4 (MIT) — kernel lineage

This plugin is a port/adaptation of **dsh-infinite-gen-4** ("Infinite Generation Four",
v0.4.0) by **Minglink** — <https://github.com/Minglink/dsh-infinite-gen-4> — licensed
under the MIT License. The kernel payload in `prompts/profiles/core.md` descends from
that project's system-prompt text, with the Hermes-specific additions documented in
`docs/CHANGELOG.md`. The upstream MIT copyright notice applies to the derived text; this
repository keeps its own MIT license for the port and additions.

## dsh-infinite-gen-5 (CC BY-NC-SA 4.0) — architectural inspiration only

Two engineering patterns in v2.0 were inspired by **dsh-infinite-gen-5**
(<https://github.com/Minglink/dsh-infinite-gen-5>):

- runtime tier switching (its `Core 8 / Full 38` toolset levels) → this plugin's
  session modes `off / slim / on / full`;
- skills as an on-demand guidance carrier (its `skills/*/SKILL.md` set) → this plugin's
  `skills/jailbreak-kernel-ops/`.

**No code, text, prompt, or asset from dsh-infinite-gen-5 is copied, translated, or
adapted here.** That project is licensed CC BY-NC-SA 4.0 (Attribution-NonCommercial-
ShareAlike), which is incompatible with this repository's MIT license; only non-
copyrightable ideas and interface concepts were used. Ideas and architectural concepts
are not subject to copyright, and nothing in this repository is a derivative work of
that project's expression.

## Other dependencies

None. The plugin is pure Python standard library: no network calls, no subprocess
execution, no third-party packages. The kernel payloads and locale catalogs are plain
Markdown/YAML text shipped in this repository.
