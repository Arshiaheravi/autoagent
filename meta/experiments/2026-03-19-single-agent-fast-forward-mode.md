# Experiment — 2026-03-19 — Single-Agent FAST-FORWARD MODE

**Meta Session:** #9
**Hypothesis:** Adding FAST-FORWARD MODE to `build_context()` in `run.py` (the single-agent path)
will eliminate the same research front-loading anti-pattern that was fixed in `engineer.py` (Session #8),
raising session completion rate from ~75% to ~88%.

## Problem

Session #8 meta fixed the multi-agent engineer path (`engineer.py` `build_prompt()`).
But the single-agent path (`run.py` SYSTEM_PROMPT + `build_context()`) was NOT fixed:

- `build_context()` line 1551: Detects current_task.md but injects "RESUME THIS TASK FIRST" — no SKIP instruction
- SYSTEM_PROMPT Phase 1 (line 1345): "PHASE 1: Research First (ALWAYS before writing any code)" — unconditional
- SYSTEM_PROMPT Phase 2 (line 1353): "PHASE 2: Read & Plan" — no SKIP condition

Result: A single agent running via run.py with a planned current_task.md still front-loads
research (Phase 1) and broad reading (Phase 2) before implementing — same anti-pattern as before.

## Research Basis

- **Anthropic context engineering (2026)**: "Good context engineering means finding the smallest
  possible set of high-signal tokens that maximize the likelihood of some desired outcome."
  And: "Just-in-time context strategies where agents dynamically load data via tools rather than
  preprocessing everything upfront." — Direct validation of FAST-FORWARD MODE approach.

- **TheAgentCompany benchmark (arXiv 2412.14161)**: 30% task completion on real workplace tasks.
  Session completion remains the industry's hardest problem — every optimization matters.

- **Plan-execution separation (arxiv 2512.08769)**: "Hierarchical access with enforced separation
  between planning, querying, and execution reduces impact of prompt injection and goal manipulation."
  The orchestrator IS the planning phase. Engineer repeating it = structural anti-pattern.

## Baseline

- Session quality score: 7.0/10 (average of last 2 sessions: Sessions #10 product + #8 meta)
- Task completion: Session #10 completed fully (current_task.md empty), quality improving
- The SYSTEM_PROMPT Phase 1 "ALWAYS" mandate was unconditional for ALL 10 sessions

## Changes Made

### Change 1 — build_context() FAST-FORWARD MODE
**File:** `autoagent/run.py` lines ~1551-1580
- Reads `task_content` first, checks `"- [ ]" in task_content`
- When `has_planned_steps = True`: injects "⚡ FAST-FORWARD MODE" section with explicit SKIP instructions
  and ≤5 read budget constraint
- When `has_planned_steps = False`: keeps original "RESUME THIS TASK FIRST" message

### Change 2 — SYSTEM_PROMPT Phase 1 conditional
**File:** `autoagent/run.py` SYSTEM_PROMPT
- Changed "PHASE 1: Research First (ALWAYS before writing any code)" to conditional
- Added: "⚡ SKIP THIS ENTIRE PHASE if context shows 'FAST-FORWARD MODE'"
- Added 2-search cap for new tasks
- Research basis: Anthropic context engineering 2026

### Change 3 — SYSTEM_PROMPT Phase 2 conditional
**File:** `autoagent/run.py` SYSTEM_PROMPT
- Added: "⚡ SKIP broad exploration if context shows 'FAST-FORWARD MODE'"
- Research basis: same as above

### Change 4 — knowledge.md Project Patterns populated
**File:** `autoagent/knowledge.md`
- Replaced placeholder "[The agent will fill this in]" in Project Patterns + Known Issues sections
- Added 9 real project patterns (route registration, ticker resolution, test runner, etc.)
- Added 7 real known issues/gotchas
- These sections have been placeholder for 10+ sessions — now populated from actual codebase knowledge

## Predicted Impact

| Dimension | Before | After (predicted) |
|-----------|--------|-------------------|
| Single-agent front-loading | ~20-25 tool calls wasted | ~5 tool calls for reading |
| Session completion rate | ~75% (after Session #8 fix) | ~88% |
| Session quality score | 7.0/10 | 7.5-8.0/10 |
| knowledge.md health check | Patterns still placeholder | All sections populated |

## Measurement Method

After next 3 product sessions:
1. If current_task.md has steps at session START → check if FAST-FORWARD MODE appears in build_context output
2. Check session completion: are `[x]` marks present at end?
3. Track pre-implementation tool call count (compare before vs after)
4. Run health check: should now detect populated Validation Commands + Project Patterns
