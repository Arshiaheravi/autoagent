# Experiment: Dynamic Replanning in Phase 3.5
**Date:** 2026-03-19
**Meta-Agent Session:** #10
**Hypothesis:** H-META-023 (Finding 23)

## Hypothesis
Adding a REPLAN CHECK step to Phase 3.5 — where the agent re-reads remaining `current_task.md` steps after a health check failure and asks "does this failure invalidate any future step?" — will reduce cascading mid-task failures and lift task completion rate.

## Baseline (pre-change)
- Phase 3.5: 5 steps. No replanning logic.
- Agent behavior when health check fails: reads error, retries fix, no check of downstream steps.
- Estimated cascading failure rate: unknown, but anecdotally visible in sessions where step 3 fix breaks step 5's assumptions.
- Task completion rate (post FAST-FORWARD fix): ~75%

## Change Made
`autoagent/run.py` Phase 3.5 — Added step 2 "REPLAN CHECK — MANDATORY":
> Re-read remaining `- [ ]` steps in `current_task.md`. Ask explicitly: "Does this failure invalidate any future step or change its approach?" If yes → call `update_current_task` with corrected remaining steps BEFORE fixing anything.

## Research Basis
- arxiv 2503.09572v3 (PLAN-AND-ACT, 2025): Dynamic replanning after each executor step lifted WebArena-Lite completion 9.85% → 57.58% (+48pp). The Execute→Replan→Execute loop is the key architectural pattern.
- arxiv 2503.13657v1 (Why Multi-Agent Systems Fail): "step repetition" and "incomplete verification" are the #1 and #3 failure modes. Replanning addresses both.
- Cost: 1-2 extra tool calls per Phase 3.5 invocation (re-read + conditional update). Budget-neutral for most sessions.

## Predicted Impact
| Metric | Before | After (predicted) |
|--------|--------|-------------------|
| Task completion rate | ~75% | ~85% |
| Cascading step failures | occasional | rare |
| Session quality score | 7.0 | 7.5 |

## Measurement Method
After 5 product sessions:
1. Check `current_task.md` at end of each session — count `[x]` vs `[ ]` steps
2. Look for Phase 3.5 patterns in session reports — did replanning appear?
3. Count sessions where all planned steps completed (vs partial completion)
4. Update quality_score_history in growth_metrics.json

## Status
IMPLEMENTED — 2026-03-19 03:01
