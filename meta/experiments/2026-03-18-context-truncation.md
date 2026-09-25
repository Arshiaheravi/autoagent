# Experiment — Context Truncation to Reduce Quota Exhaustion
**Date:** 2026-03-18
**Session:** Meta #6
**Hypothesis:** H1 — Truncating large unbounded context files reduces per-session token usage by ~40%, reducing quota exhaustion rate

## Baseline
- Session quality score: 4.5/10 (avg, improving trend)
- Quota exhaustion rate: 2 out of last 5 sessions lost (40%)
- north_star.md: ~15,000 chars, loaded in full every orchestrator session
- hypotheses.md: ~8,000 chars, loaded in full every orchestrator session
- knowledge.md: ~7,000 chars, loaded in full by build_context()
- Estimated orchestrator initial prompt tokens: 40,000-60,000 before any work

## Change Made
**File 1:** `autoagent/agents/orchestrator.py` — `build_orchestrator_prompt()`
- north_star.md: was unlimited, now capped at last 4000 chars
- hypotheses.md: was unlimited, now capped at last 3000 chars
- decisions.md: was unlimited, now capped at last 2000 chars
- backlog: was unlimited, now capped at last 3000 chars

**File 2:** `autoagent/run.py` — `build_context()`
- knowledge.md: was unlimited, now capped at last 5000 chars

**File 3:** `autoagent/run.py` — SYSTEM_PROMPT
- Removed duplicate "## Loop Detection" and "## Fabrication Prevention" sections (~400 tokens)
- These sections already appear as RULE 1 + RULE 2 in CRITICAL RULES at top

## Justification
- north_star.md grows ~1500 chars per session (Session #9 close added another 800 chars)
- After 9 sessions, north_star.md alone exceeds 15,000 chars
- Most important content is the CURRENT diagnosis (last 2000 chars), not historical entries
- Files are append-only, so tail truncation preserves the most recent/relevant content
- Duplicate SYSTEM_PROMPT sections add ~400 tokens of noise per call with zero additional instruction value

## Measurement Method
1. Count quota-exhausted sessions in next 5 runs vs. prior 5 (was 2/5 = 40%)
2. Target: ≤ 1/5 sessions quota-exhausted after this change
3. Session quality score after 5 more sessions — target: 6.0+/10

## Expected Impact
| Metric | Before | After |
|--------|--------|-------|
| Quota exhaustion rate | 40% (2/5 sessions) | ≤20% (1/5 sessions) |
| Orchestrator initial tokens | ~50,000 | ~30,000 (-40%) |
| Session quality score | 4.5/10 | 6.0+/10 |
