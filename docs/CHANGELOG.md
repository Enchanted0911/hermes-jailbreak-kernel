# Changelog — hermes-jailbreak-kernel

## v2.0.1

- **Session key resolution fixed for slash commands**: plugin commands run on the
  RPC/worker thread where the turn-path contextvar is not bound, so `/jailbreak <mode>`
  could previously report "no resolvable session id". Resolution now reads the standard
  plugin-command binding first (`HERMES_SESSION_ID` → `HERMES_SESSION_KEY` →
  `HERMES_UI_SESSION_ID` via `gateway.session_context.get_session_env`), then the
  conversation root, then the most recent active session registered by the middleware.
  `HERMES_SESSION_ID` equals the durable session id the middleware sees, so both paths
  share one state space.
- `snapshot()` exposes `recent_session` for diagnostics.

## v2.0.0

Session-level control and scenario profiles (informed by the engineering patterns of
dsh-infinite-gen-5; no code or text copied — see THIRD_PARTY_NOTICES.md).

- **Session modes**: `off` / `slim` / `on` / `full`, switchable at runtime with
  `/jailbreak <mode>`; replaces "edit env + restart" for day-to-day control.
- **Kernel profiles**: `core` / `research` / `creative` / `max`
  (`prompts/profiles/`); `full` mode forces `max`.
- **Session-aware sections**: section content is now a callable that resolves the
  session mode/profile at render time; `off` renders empty so Hermes skips the section.
- **Request-layer mode handling**: `off` strips rendered section containers and leftover
  `## Plugin Context:` blocks; `slim` appends instead of rebuilding.
- **Skill carrier**: `jailbreak-kernel-ops` registered via `register_skill` — progressive
  disclosure (one line in `<available_skills>`, body loaded on demand), including the
  refusal-escalation ladder.
- **Docs**: `docs/ARCHITECTURE.md`, `docs/COMPATIBILITY.md` (measured model table),
  `THIRD_PARTY_NOTICES.md`.
- **Tests**: split into `tests/` modules with `selftest.py` as the runner.
- Env switches remain as process-level fallbacks; session overrides take precedence.

## v1.7.2

- LICENSE back to verbatim standard MIT text (GitHub SPDX detection); rename leftovers
  cleared from all READMEs; `.hermes-catalog.json` excluded.

## v1.7.1

- Punctuation fix in the English few-shot example (full-width → ASCII parentheses).

## v1.7.0

- Kernel `Format examples` extended with two English few-shot mirrors; HASTE host
  adaptation section removed (kernel now byte-identical to the reviewed upstream text);
  stale version numbers in all six README titles fixed.

## v1.6.0

- Bilingual UI following Hermes' `agent/i18n` standard: plugin-local `locales/en.yaml`
  (default) + `locales/zh.yaml`, `HERMES_LANGUAGE` > `display.language` > `en`;
  command description and status report localized.

## v1.5.0

- Renamed `hermes-armor` → `hermes-jailbreak-kernel` per catalog review (name must
  describe the function); English-first manifest description; `HERMES_JAILBREAK_*`
  switches; `/jailbreak` command.

## v1.4.0

- Multilingual READMEs (en default + zh-CN/es/fr/ar/ja), cross-language links.

## v1.3.0 / v1.4.0-rotation

- opencode session rotation (`once` / `every` / `off`) against gateway-pinned
  per-session refusal state.

## v1.2.0

- Request-layer system rebuild (`replace`) with `append` fallback; diagnostic dumps.

## v1.0.0–v1.1.0

- Initial Hermes port: dual same-source system-prompt sections at `after_memory`
  (`hermes-armor-core` / `-reinforce`), `/armor` status command, offline self-test.
