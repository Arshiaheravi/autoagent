# CLAUDE.md

Guidance for Claude Code (claude.ai/code) when working in this repository.

## Output style

Sessions in this repo run **caveman mode** (terse: drop articles, filler,
pleasantries, hedging; fragments OK; technical terms exact; code/commit/security
text stays normal prose). Disable with "stop caveman" / "normal mode". A
claude-mem plugin captures tool-use observations to avoid re-reading files across
sessions; both are operator-side plugins, not part of the engine.

---

## What This Is

AutoAgent is a self-managing autonomous AI coding engine. Per project it picks
tasks from a backlog, builds features test-first, verifies, commits, and rewrites
its own prompts/skills from observed failures — no human in the loop during a
session. One engine manages many isolated projects; the same engine backs a
hosted multi-tenant deployment (each tenant is an isolated project with a scoped
skill/prompt surface).

## Running it

Driven by the `autoagent` CLI (`engine/cli.py`). Common commands:

```bash
autoagent init                          # first-time setup (~/.autoagent)
autoagent intake "idea"                 # interview → PROJECT.md, NORTH_STAR.md, agents, backlog
autoagent run <project> --once          # single session
autoagent run <project> --tasks N       # N sessions then stop
autoagent run <project>                 # run continuously (short cooldown)
autoagent run <project> --once --type meta   # force a session type
autoagent run <project> --test          # dry run: build the prompt, don't execute
autoagent list                          # projects + session counts
autoagent status <project>              # spend + recent activity
autoagent dashboard                     # live dashboard (localhost:8080)
autoagent org --strict                  # audit departments/agents/skills, fail on drift
```

## Architecture

**Entry point:** `engine/cli.py` → `runner.run_project` → `engine/run.py:run_session`
(~586 lines). `run.py` loads config, resolves the session type + model, assembles
the boot prompt + `--append-system-prompt` payload, spawns the Claude CLI as a
subprocess, streams JSON events, tracks cost, and regenerates the dashboard.
`launcher.py` (legacy root) is a self-healing wrapper around an older loop; the
CLI/engine path is the current one.

**Session types** (`engine/session_analytics.py:get_session_type`, keyed on
`session_num`): every multiple of 5 routes to a non-work type, the rest are WORK.
- **WORK** (default) — pick task, write tests first, implement, verify, commit
- **META** (`%5==0`, excl. below) — read recent failures, improve prompts/skills
- **BRAIN** (`%10`) — research the web for new techniques and adopt them
- **DEEP** (`%20`) — combined META + BRAIN
- **AUDIT** (`%25`) — security review + risk-backlog generation
- **KNOWLEDGE** (`%50`) — compile durable project knowledge

**Model routing:** `engine/models.py` is the single source of truth for Claude
model IDs and per-session-type tier defaults (`resolve_model(config, type)`).
Never hardcode `claude-*` strings elsewhere.

**Prompt stack:** the engine reads a per-project `PROMPT.md` (synced from
`templates/PROMPT.md`), plus `PROJECT.md`, `NORTH_STAR.md`, `skills/INDEX.md`,
and `skills/agent-patterns.md`. The hardened root `PROMPT-*.md` satellites
(WORK/VERIFICATION/CONTEXT/FAILURE/RECOVERY) feed the legacy root path — see
`docs/AGENTRIC_LAUNCH_REVIEW.md` for the consolidation plan.

**Memory system** (gitignored, agent-managed at runtime, per project):
`backlog.md`, `current_task.md`, `activity_log.md`, `knowledge.md`, `done.md`,
`north_star.md`.

**Skill library** (`skills/`, 46 `.md` files): `INDEX.md` routes task types to
skills; `agent-patterns.md` catalogs failure modes (Kitchen Sink, Infinite
Exploration, Symptom Suppression, …) with prevention rules. Project-domain skills
are hidden from generic tenants unless project-local or explicitly enabled
(`engine/org_model.py` + `templates/departments.json`).

**Agent teams:** 14 universal templates across 4 departments (Engineering,
Product & Design, Growth & Communications, Research & Intelligence); domain agents
are generated at intake. Backlog tasks tagged `[agent: name]` route to a specialist.

**Per-project config:** `PROJECT.md` (what to build, stack, test command, git,
hard rules), `NORTH_STAR.md` (the one metric), `config.json` (optional; model,
budget, interval — gitignored so tokens stay local).

## Session persistence

On conversation start, check `memory/active_session.md`: if it has unchecked
`- [ ]` items, resume from there; else start fresh. Task lists get written there,
updated as work completes, and reset to idle when done. A PostToolUse hook
auto-commits it so it survives crashes.

## Key design decisions

- Tasks are picked by North Star impact — no-metric refactors get skipped.
- Mandatory pre-commit gates: self-critique, audit checklist, all tests green,
  Playwright check if UI changed, explicit READY TO COMMIT: YES/NO.
- `knowledge.md` accrues ACCOMPLISHED/FAILED/RULE learnings read every session.
- The meta layer rewrites prompts/skills from observed failures — self-teaching.
- `sessions.json` holds per-session metadata for the dashboard.

## Tests

```bash
cd engine && python3 -X utf8 -m pytest . -q     # 1093 tests across 70 files
```
