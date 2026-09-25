# Experiment: Fast-Forward Implementation Mode for Engineer Agent
**Date:** 2026-03-19
**Meta Session:** #8
**Hypothesis:** H1 (highest confidence)

## Problem Statement

Engineer agents spend 30-50% of their tool-call budget on Phase 1 (Research) and Phase 2 (broad
file reading) **even when the orchestrator has already produced a detailed implementation plan**.

Evidence:
- Session #15: engineer wrote `current_task.md` with 9 specific steps, then implemented ZERO steps
- Session #14: self-growth session, no code shipped
- Average quality score: 3.4/10 across 10 sessions (declining despite 7 SYSTEM_PROMPT improvements)
- The "Research First — ALWAYS before writing any code" mandate is unconditional — no exception for
  "when the orchestrator has already done this research"

Estimated turn consumption (pre-fix):
- Phase 1 (Research): 3-5 web searches = ~5 tool calls
- Phase 2 (Reading): mission_brief, hypotheses, PROJECT.md, knowledge.md, BACKLOG.md, current_task.md,
  then reading 3-5 specific code files = ~15 tool calls
- Phase 3 (Hypothesis writing): 2-3 tool calls
- Total pre-implementation: ~20-25 tool calls
- Claude Code turn limit: ~100 per session
- Remaining for implementation: ~75 turns
- H36+H37 implementation (9 steps): creates 5 new files, 2 modified files, 9 tests, multiple commits
  = estimated 50-70 tool calls minimum
- Result: barely enough, often runs out

When the orchestrator has ALREADY done Phase 1+2:
- All research findings are in `shared/mission_brief.md`
- All implementation steps are in `current_task.md`
- The engineer repeating this work = pure waste

## Hypothesis

"Adding FAST-FORWARD MODE to the engineer prompt — which skips Phase 1 and Phase 2 when
`current_task.md` already has specific implementation steps — will increase task completion
rate from ~40% to ~80% by reallocating 20-25 wasted tool calls to implementation."

## Baseline

- Task completion rate: ~40% (estimated from sessions #13-15: 3 sessions, 1 partial + 2 incomplete)
- Session #15: 0/9 implementation steps completed
- Session quality score: 3.4/10 average

## Change

In `autoagent/agents/engineer.py` `build_prompt()`:

1. **RESUME task section**: Add explicit FAST-FORWARD MODE label + skip directive + turn budget rule
2. **Phase 1**: Make conditional — SKIP if `current_task.md` has steps already defined
3. **Phase 2**: Make conditional — SKIP broad reading, read ONLY specific files for first step
4. **New rule at top of prompt**: Turn budget awareness — "if 20+ calls without code → skip to Phase 4"

## Measurement Method

After 5 sessions:
1. Check `current_task.md` — are all steps marked [x]? (completion rate)
2. Count tool calls before first file write in each session (pre-implementation waste rate)
3. Check session reports — does engineer report say HYPOTHESIS_RESULT with actual metric movement?
4. Updated session quality score

## Expected Outcomes

| Metric | Before | After |
|--------|--------|-------|
| Task completion rate | ~40% | ~80% |
| Pre-implementation tool calls | ~20-25 | ~5-10 |
| Session quality score | 3.4/10 | 5.5/10+ |
| Sessions where engineer ships code | ~4/10 | ~8/10 |

## Rollback Plan

If task completion gets worse (e.g., engineer skips needed research and builds wrong thing):
- Remove the SKIP directive from RESUME section
- Keep the turn budget warning (neutral downside risk)
- Add back Phase 1 but cap it at 2 searches max

## Related Findings

- Finding 16 (Session #7): health gate never fired for 9 sessions — structural bypass of mandatory gate
- Pattern: mandatory phases are bypassed structurally; making them conditional with explicit criteria
  is more reliable than making them unconditional
