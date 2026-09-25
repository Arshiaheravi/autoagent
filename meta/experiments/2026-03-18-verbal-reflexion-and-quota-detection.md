# Experiment: Verbal Reflexion Schema + Quota Detection
**Date:** 2026-03-18
**Session:** Meta #4
**Hypotheses tested:** H1 (primary)

## Problem
Two compounding failures were identified:
1. `task_complete` tool schema had `self_critique` as numeric integer fields (1-3), which contradicts Phase 6's verbal Reflexion instruction. Agents take the schema's path of least resistance: fill numbers, skip verbal output. Result: `knowledge.md` Project Patterns and Validation Commands sections stayed empty for 7 sessions.
2. Quota exhaustion ("You're out of extra usage") produced non-empty stdout, bypassing the `if not stdout:` guard in all agent `run()` functions. Result: quota errors were treated as successful (but empty) agent outputs, corrupting session reports.

## Baseline (pre-change)
- Average session quality score: 4.6/10
- knowledge.md Project Patterns section: empty (7 sessions)
- Quota error detection: zero — treated as success with empty output
- Sessions lost to quota: ≥1 (Session #3 product run)

## Changes Made

### Change 1 — task_complete schema (run.py)
**File:** `autoagent/run.py` lines ~703-744
**What:** Removed `self_critique` object with 4 integer fields (research_depth, code_quality, self_growth, task_completion). Replaced with `verbal_reflexion` string field.
- `verbal_reflexion` is now **required** in the JSON schema
- Description enforces 4-answer format: ACCOMPLISHED / FAILED / DIFFERENT / RULE
- Each answer requires specific information density: 2+ sentences, exact file/function/error names
- Task_complete description updated to include "(8) Phase 6 Reflexion written to knowledge.md AND provided in verbal_reflexion field"
- Research basis: Shinn et al. NeurIPS 2023 — richer verbal reflections (explanation + corrected solution + instructions) outperform thin ones; verbal 78.6% → 97.1% accuracy

### Change 2 — Quota detection (all 5 agent files)
**Files:** `autoagent/agents/orchestrator.py`, `engineer.py`, `researcher.py`, `designer.py`, `qa.py`, `strategist.py`
**What:** Added `_QUOTA_STRINGS` list and `_is_quota_error()` helper to each agent.
- After getting stdout, check if it contains quota error strings ("out of extra usage", "usage limit", "quota exceeded", "resets 2am", "resets 8pm")
- If quota detected: save a minimal labelled report + return `{"success": False, "error": "quota_exhausted", "quota": True}`
- orchestrator.py: quota causes early session abort with clear print message
- run.py NorthStar loop: checks `result.get("quota")` after each specialist — breaks loop if quota hit mid-session instead of running remaining agents into quota too
- Research basis: Google Cloud 2025 — circuit breaker pattern; How2.sh "timeout envelopes" — return partial results with user-visible note rather than hard failure

## Expected Improvement
| Dimension | Before | After (predicted) |
|-----------|--------|-------------------|
| knowledge.md capture | 0% populated | 60-80% populated |
| Quota error detection | 0% | 100% |
| Complete session losses from quota | ≥1/5 sessions | 0/5 sessions |
| Session quality score | 4.6/10 | 6.5/10 |

## Measurement Method (after 5 sessions)
1. Check knowledge.md Project Patterns and Validation Commands sections — are they populated?
2. Check session reports — do quota errors show "QUOTA EXHAUSTED" label vs. "completed" label?
3. Count sessions where all agents completed vs. sessions that aborted mid-session
4. Look for verbal_reflexion content in activity logs (do task_complete calls include rich text?)
