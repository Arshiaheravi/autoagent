# Skill: Claude API / Anthropic SDK

## WHEN TO USE THIS SKILL
Read this before building any feature that calls the Anthropic API or uses the Agent SDK.
Locate the project's API call sites from `.autoagent/PROJECT.md` (services + routes layout) before editing.

## MODEL SELECTION

Current family (IDs are complete as-is — never append date suffixes except Haiku's full ID):

| Task complexity | Model | Price $/1M in→out | Why |
|---|---|---|---|
| Simple Q&A, classification, routing | `claude-haiku-4-5` | 1 → 5 | Cheapest, fastest, 200K context |
| Most tasks (production default) | `claude-sonnet-5` | 3 → 15 | Near-Opus quality on coding/agentic at Sonnet cost |
| Complex reasoning, agent work | `claude-opus-4-8` | 5 → 25 | Highest Opus-tier capability, 1M context |
| Hardest long-horizon / most demanding | `claude-fable-5` | 10 → 50 | Most capable model; different API surface (see below) |

**Default to `claude-opus-4-8` for new agent features unless the user picks a cheaper tier.** Reach for `claude-fable-5` only when explicitly requested — it costs above Opus-tier and behaves differently.

Older aliases still active if pinning is needed: `claude-opus-4-7`, `claude-opus-4-6`, `claude-sonnet-4-6`. Retired (404): `claude-3-7-sonnet`, `claude-3-5-haiku`, `claude-3-opus`.

## THINKING / EFFORT

- **Opus 4.8 / Sonnet 5 / Fable 5**: adaptive only. `thinking: {type: "adaptive"}`. `budget_tokens` and sampling params (`temperature`/`top_p`/`top_k`) return **400** — remove them.
- **Sonnet 5**: omitting `thinking` runs adaptive by default; set `{type: "disabled"}` to turn off.
- **Opus 4.8**: omitting `thinking` runs without thinking — set `{type: "adaptive"}` explicitly.
- **Fable 5**: thinking is always on — omit the param entirely. An explicit `{type: "disabled"}` returns 400. Raw chain of thought is never returned; `display: "summarized"` gets a readable summary (default is `"omitted"` = empty thinking text).
- **Effort**: `output_config: {effort: "low"|"medium"|"high"|"xhigh"|"max"}`. Default = `high`. `xhigh` = best for coding/agentic on Opus 4.7/4.8, Sonnet 5, Fable 5. `max` supported on Opus 4.6+, Sonnet 5, Fable 5 — errors on Haiku 4.5.
- Older `claude-opus-4-6` / `claude-sonnet-4-6`: adaptive recommended, `budget_tokens` deprecated (not 400).

## STREAMING

Always stream when:
- Input or output may be long
- `max_tokens` is high (>16K non-streaming risks SDK HTTP timeout; 128K ceiling needs streaming)
- Response feeds a UI (chat, live commentary)

```python
with client.messages.stream(...) as stream:
    for text in stream.text_stream:
        yield text
    final = stream.get_final_message()
```

## PYTHON SDK PATTERNS

```python
import anthropic

client = anthropic.Anthropic()  # resolves ANTHROPIC_API_KEY or `ant auth login` profile

# Standard call
message = client.messages.create(
    model="claude-opus-4-8",
    max_tokens=16000,
    messages=[{"role": "user", "content": "..."}],
)

# With adaptive thinking
message = client.messages.create(
    model="claude-opus-4-8",
    max_tokens=16000,
    thinking={"type": "adaptive"},
    output_config={"effort": "high"},
    messages=[{"role": "user", "content": "..."}],
)
```

## FABLE 5 EXTRAS

Only when explicitly targeting `claude-fable-5`:
- **`refusal` stop reason**: safety classifiers may decline (HTTP 200, `stop_reason: "refusal"`, empty or partial `content`). Check `stop_reason` before reading `content[0]`.
- **Opt into fallbacks by default**: `betas=["server-side-fallback-2026-06-01"]` + `fallbacks=[{"model": "claude-opus-4-8"}]` on `client.beta.messages.create` — a declined request is re-served by the fallback model in the same call.
- **30-day data retention required** — not available under zero-data-retention orgs (400 on every request otherwise).
- Same tokenizer as Opus 4.8 (token counts ~unchanged from 4.7/4.8).

## TOOL USE

- Always parse tool inputs with `json.loads()` — never raw string match (escaping varies across 4.6+/Fable)
- Don't reimplement SDK helpers — use built-in tool runner / manual-loop patterns
- Don't define custom types for SDK data structures — SDK exports them all

## COMMON PITFALLS

- Opus 4.8 / Sonnet 5 / Fable 5 do NOT support assistant message prefills → 400; use structured outputs (`output_config: {format: {...}}`) instead
- Don't use `output_format` parameter — deprecated; use `output_config: {format: {...}}`
- Don't truncate inputs silently — log a warning and handle gracefully
- Keep `ANTHROPIC_API_KEY` in `.env`, never hardcode

## SURFACE SELECTION

| Use case | Surface |
|---|---|
| Single response (chat, commentary) | Claude API direct |
| Multi-step pipeline you control | Claude API + tool use |
| Agent with file/web/terminal access | Claude API agentic loop / Agent SDK |
| Stateful long-running agent, server-managed | Managed Agents (Beta) |

## MANAGED AGENTS (Beta)

Use Managed Agents for persistent stateful agents with Anthropic-hosted execution (bash, file ops, code execution run in a container). **Not available on Bedrock, Vertex, or Foundry.**

Key concepts:
- **Agents** are persistent, versioned objects — `model`/`system`/`tools` live here. Create once, reference by ID.
- **Sessions** reference a pre-created agent + an environment; each provisions a container workspace.
- **Environments** are reusable container-config templates.
- Server runs the agent loop; your code streams events and answers tool/confirmation requests.

Mandatory flow: **Agent (once) → Session (every run)**. Never put `model`/`tools` on the session.

```python
import anthropic
client = anthropic.Anthropic()

# ONE-TIME SETUP — create once, store agent.id + env.id
env = client.beta.environments.create(
    name="dev-env", config={"type": "cloud", "networking": {"type": "unrestricted"}},
)
agent = client.beta.agents.create(
    name="Coding Assistant",
    model="claude-opus-4-8",
    tools=[{"type": "agent_toolset_20260401"}],
)

# RUNTIME — every run references the stored IDs
session = client.beta.sessions.create(agent=agent.id, environment_id=env.id)
client.beta.sessions.events.send(
    session_id=session.id,
    events=[{"type": "user.message", "content": [{"type": "text", "text": "..."}]}],
)
with client.beta.sessions.events.stream(session_id=session.id) as stream:
    for event in stream:
        ...  # break on session.status_idle (terminal stop_reason) or session.status_terminated
```

For full detail (outcomes, vaults, MCP, multiagent) invoke the bundled `claude-api` skill or WebFetch platform.claude.com/docs/en/managed-agents.

## SERVER-SIDE COMPACTION (Beta)

Long-running conversations auto-summarize near the context limit. When compaction fires:
- Anthropic replaces earlier turns with a compressed summary
- **You must preserve `response.content` blocks** (append full content, not just `.text`) to survive compaction
- Beta header `compact-2026-01-12`; different from client-side compaction in Claude Code

## SKILL CREATOR PRINCIPLES (from skill-creator SKILL.md)
When writing new agent skill files:
- Make the description **pushy** — passive descriptions cause undertriggering
- Explain the **why** (theory of mind) instead of rigid ALL-CAPS demands
- Keep prompts lean — remove unproductive instructions
- Generalize from feedback rather than overfitting to examples
- Three-level loading: metadata always loaded, SKILL.md on trigger, resources as needed
