# Architecture — hermes-jailbreak-kernel v2.0

Mechanism-level description of how the plugin injects, hardens, and controls the
jailbreak kernel inside Hermes Agent. Companion to the README (usage) and
`docs/COMPATIBILITY.md` (host/model matrix).

## 1. Host surfaces used

| Surface | Hermes API | Purpose |
|---|---|---|
| System-prompt sections | `ctx.register_system_prompt_section(id, content, position="after_memory", max_chars=4000)` | session-aware kernel injection |
| LLM request middleware | `ctx.register_middleware("llm_request", cb)` | request-layer rebuild, header rotation, diagnostics |
| Slash command | `ctx.register_command("jailbreak", handler, description, args_hint)` | session state control |
| Skill registry | `ctx.register_skill(name, path, description, frontmatter)` | progressive-disclosure ops guide |

All four registrations are wrapped in fail-soft handlers: a failure in one never
prevents the others or the gateway from starting.

## 2. Session key resolution

Session state is keyed by a *session key*, resolved in this order
(`modes.resolve_session_id`):

1. `ctx["session_id"]` — provided by the `llm_request` middleware context;
2. the ambient conversation root — `agent.portal_tags.get_conversation_context()`,
   available on command execution and section render paths;
3. empty string — no session override; env defaults apply.

Commands and the middleware therefore address the same state from different
execution contexts.

## 3. Layer 1 — plugin sections (session-aware)

`hermes-jailbreak-kernel-core` and `hermes-jailbreak-kernel-reinforce` are registered
with a **callable** content function rather than a fixed string. Hermes invokes it when
a session's system prompt is assembled:

- `mode == "off"` → returns `""`; the renderer strips it and skips the section entirely;
- otherwise → returns the active kernel profile text (dual-section: the same text twice).

Constraints enforced by Hermes (and mirrored in `selftest`):

- 4000 chars per section, 8000 chars total across plugin sections;
- position is fixed to `after_memory`; render order is section-id lexicographic;
- section ids are lowercase letters/digits/`.`/`_`/`-` only.

Sections are rendered once per session and frozen on the agent (Hermes behavior). Mode
changes *mid-session* therefore take effect primarily through Layer 2, which runs on
every request; an `off` switch strips already-rendered section text at request time.

## 4. Layer 2 — request middleware (`llm_request`)

Runs immediately before the provider call, on every request. Steps, in order:

1. **Hardening** (`payload.harden_system`) by mode:
   - `off` — removes rendered plugin-section containers (`<!-- hermes-plugin-sections:start/end -->`)
     and leftover `## Plugin Context:` blocks; substitutes a neutral system line if the
     message becomes empty;
   - `slim` — appends the kernel to the tail of the last system message, leaving the
     original system text intact;
   - `on` / `full` — rebuilds the system message as *memory section + runtime environment
     + kernel*, discarding Hermes' agent-guidance/skill-index scaffold.
2. **Session rotation** (`payload.rotate_session`) — rewrites
   `extra_headers["x-opencode-session"]` for opencode targets only
   (`base_url` contains `opencode.ai`, or provider contains `opencode`):
   `once` (default) sets one rotated id per session and reuses it; `every` rotates per
   request; `0` disables.
3. **Diagnostics** (`payload.dump_request`) — optional JSON dump into the plugin's
   `dumps/` directory: full system message(s), mode/profile, route facts, and
   role/length/prefix for non-system messages. Policy: `off` / `first` (default) /
   `force`.

Tool schemas are unaffected by any of this: they travel in the API `tools` field, not in
the system text, so tool availability does not depend on the mode.

## 5. Kernel profiles

`prompts/profiles/<name>.md`, flat text, one file per profile:

| Profile | Intent |
|---|---|
| `core` | general deliverable contract (security / LLM research / adult fiction / other) |
| `research` | offensive-security, reversing, exploit/payload emphasis |
| `creative` | fiction/roleplay emphasis, full drafts, no fade-to-black |
| `max` | explicit no-refusal framing + hard prohibitions on preambles/disclaimers |

Selection: `full` mode forces `max`; otherwise the session profile (or env default
`core`). Every profile is validated against the 4000-char section cap and the 8000-char
dual-section budget by the offline test suite.

Dual-layer injection uses the **same file twice** (core + reinforce sections), so
byte-identical payloads are guaranteed by construction rather than by keeping two files
in sync.

## 6. Localization

User-facing strings follow Hermes' `agent/i18n` standard: language resolves as
`HERMES_LANGUAGE` → `display.language` → English; catalogs are flat dotted-key YAML in
`locales/`; a missing key falls back to English, then to the bare key. Logs and the
kernel payload stay language-neutral by design.

## 7. Failure model

Every runtime path is fail-soft:

- section render failure → falls back to the `core` profile text;
- middleware exception → request passes through untouched;
- dump failure → returns `None`, no request impact;
- unknown mode/profile values → clamped to `on` / `core`.

A process-wide kill switch (`HERMES_JAILBREAK_DISABLE=1`) skips registration entirely.
