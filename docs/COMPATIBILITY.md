# Compatibility — hermes-jailbreak-kernel v2.0

Host requirements, model behavior matrix, and known limits. Measurements were taken
on the author's machine against the `opencode.ai/zen/go/v1` relay and local runtimes;
treat them as a starting point, not a guarantee.

## Host

| Item | Requirement / note |
|---|---|
| Hermes Agent | `>=0.19` (manifest `requires_hermes`); uses `register_system_prompt_section`, `register_middleware`, `register_command`, `register_skill` |
| Prompt-section caps | 4000 chars per section, 8000 chars total (all profiles fit: 2.8K–3.5K each) |
| Profile lookup | language via `HERMES_LANGUAGE` → `display.language` → `en` |
| Session key | `ctx["session_id"]` or `agent.portal_tags.get_conversation_context()`; if neither resolves, commands report "no resolvable session id" |

## Model behavior with the kernel active

Measured with the full kernel as the only system message, one explicit-content request,
two samples per model (2026-09, `opencode.ai/zen/go` relay, fresh `x-opencode-session`
per request):

### Compliant (2/2)

| Model | Notes |
|---|---|
| `kimi-k2.6`, `kimi-k2.7-code` | stable, good output quality |
| `mimo-v2.6-flash` | stable |
| `minimax-m2.5` | stable (newer m2.7/m3 refuse) |
| `qwen3.7-max`, `qwen3.8-flash` | stable (qwen3.8-max refuses) |

### Partial (1/2 — route-dependent)

`deepseek-v4-flash`, `deepseek-v4-pro`, `glm-5.3`, `glm-5.3-flash`, `kimi-k3`,
`mimo-v2.5-pro`, `mimo-v2.6-pro`, `omen-alpha`, `longcat-2.0`, `qwen3.7-plus`

Same request, same kernel, different upstream instance → different outcome. Retry, or
switch to a compliant model, if consistency matters.

### Refuses (0/2)

`deepseek-flash`, `deepseek-v4.1-flash`, `glm-5.1`, `glm-5.2`, `hy4-preview`,
`mimo-v2.5`, `qwen3.8-max`

Strong alignment survives system-prompt injection; these models answer with an explicit
"no matter how it is framed" refusal. Do not tune the kernel for them — change the model.

### Unavailable on this relay tier

`grok-4.6`, `grok-4.7`, `gpt-5.6-luna`, `minimax-m2.7`,
`deepseek-v4-flash-vision-exp` (HTTP 503); `muse-spark-1.2/1.3-contributor`,
`qwen3.6-plus` (HTTP 400). Tier limits, not model behavior.

## Gateway behavior that affects results

1. **Session pinning.** The opencode relay pins requests sharing an `x-opencode-session`
   value to one upstream and remembers refusal state for that session. A session that
   refused once keeps refusing even with a stronger system prompt; a fresh session id
   complies. This is why rotation exists and why `/jailbreak on|full` re-rotates.
2. **Model-id routing.** Different ids on the same relay can land on upstreams with very
   different alignment strength (`deepseek-v4.1-flash` refuses while `deepseek-v4-flash`
   mostly complies).
3. **Attribution headers.** Direct API calls need `HTTP-Referer`/`X-Title`/`User-Agent`
   and `x-opencode-session`; without them the relay answers 403/400.
4. **Direct provider APIs** (e.g. `api.deepseek.com`) do not implement session pinning;
   rotation is skipped there because `x-opencode-session` is not part of the request.

## Known limits

- **Strongly aligned models will not move.** GPT/Grok-class and the newest frontier
  tiers refuse regardless of mode/profile; pick a compliant model instead.
- **Verbose-mode setups.** Modes other than `off` reshape the system message; if a task
  depends on Hermes' own agent guidance, use `off` for that session.
- **Session state is in-process.** `/jailbreak` changes reset when the gateway or desktop
  app restarts; env values then apply again.
- **Diagnostics contain conversation context** (system prompt + memory sections). Keep
  `dumps/` private; it is gitignored and never part of releases.
