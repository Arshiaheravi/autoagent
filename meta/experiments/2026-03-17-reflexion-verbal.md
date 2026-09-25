# Experiment: Reflexion Verbal Phase 6 + Mandatory Pre-Commit Gate

**Date:** 2026-03-17
**Session:** Meta #2
**Hypothesis:** H-META-003 (extended) + H-META-004 (new)

## Hypotheses Being Tested

**H-META-003 (verbal Reflexion):**
Replacing Phase 6 numeric self-critique (1-3) with Reflexion-style verbal articulation
will improve knowledge capture quality and carry forward better lessons per session.

**H-META-004 (mandatory pre-commit gate):**
Adding a mandatory `run_health_check` call in Phase 3 before any `git commit`
will reduce commits of broken code (improving commit quality dimension of session score).

## Research Basis

- **Shinn et al., NeurIPS 2023 (Reflexion):** Verbal self-reflection improves coding +11% (HumanEval),
  reasoning +20% (HotPotQA), decision-making +22% (AlfWorld) with zero fine-tuning. 96.5% of cases
  converge within 3 Reflexion iterations. Paper: arxiv 2303.11366.

- **DORA 2025 (Google):** 90% AI adoption increase → 91% increase in code review time when no
  mandatory verification gate exists. Quality gates embedded in agent instructions (not skippable)
  drive long-term quality improvements.

## Baseline (Pre-Change)

- knowledge.md structured sections: EMPTY ("to be filled by agent")
- Commit quality score: 6/10 (weakest dimension)
- Phase 6 format: numeric 1-3 scores with no required verbal output
- Pre-commit gate: none — agent could `git commit` without running health check

## Change Applied

**File:** `autoagent/run.py`

1. **Phase 3** — added HEALTH CHECK GATE rule: "Before ANY `git commit`, call `run_health_check`
   first. If it fails → go to Phase 3.5 immediately. No exceptions."

2. **Phase 6 Step E** — replaced numeric 1-3 scores with 4-question Reflexion verbal template:
   - ACCOMPLISHED (what changed specifically)
   - FAILED (exact root cause, not symptom)
   - DIFFERENT (one concrete behavior change)
   - RULE (transferable lesson for knowledge.md)

## Measurement Method

After 5 sessions with real data, evaluate:

**H-META-003 (verbal Reflexion):**
- Indicator A: Does knowledge.md project patterns/validation sections get populated? (yes/no per session)
- Indicator B: Do "Lessons Learned" entries contain specific root causes vs vague observations?
  (count entries with named root cause vs total entries)
- Target: 80%+ of knowledge.md entries contain specific root cause (vs current ~40%)

**H-META-004 (mandatory pre-commit gate):**
- Indicator A: Does activity_log show `health_check: PASS` before commit entries?
- Indicator B: Count sessions where tests failed AFTER commit vs before
- Target: Zero "committed broken code" events in next 5 sessions

## Predicted Impact

| Dimension | Before | Predicted After |
|-----------|--------|-----------------|
| Commit quality | 6/10 | 8.5/10 |
| Knowledge capture | 2/10 | 7/10 |
| Session-over-session learning | ~0 (no verbal lessons) | compounding |
| **Overall quality score** | **5.0/10 avg** | **7.5/10** |

## Next Measurement Date

2026-03-22 (after 5 sessions)
