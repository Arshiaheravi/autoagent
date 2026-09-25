# Experiment — Context U-Curve SYSTEM_PROMPT Restructure

**Date:** 2026-03-17
**Session:** Meta #3
**Hypothesis:** H-META-005

## Hypothesis
The SYSTEM_PROMPT's TOP high-attention zone (first ~500 tokens) is occupied by a 10-role identity list (low priority). Research confirms 40-60% accuracy drop for instructions buried in the middle of long prompts (U-shaped attention curve). Moving critical rules to TOP + adding FINAL CHECKLIST to BOTTOM will improve session rule-following reliability.

## Baseline
- Session quality score: 5.0/10 (avg across 2 sessions)
- Evidence of failure: Loop Detection + Fabrication Prevention rules buried in middle/bottom, but Session #3 still failed completely (quota exhaustion with zero output)
- 10-role identity list occupies first ~350 tokens of SYSTEM_PROMPT with no operational value

## Change Made
**File:** `autoagent/run.py` — SYSTEM_PROMPT opening block

**Before (lines 1203-1224):**
- 10-role identity list (Senior Full-Stack Engineer, UI/UX Designer, Growth Marketer, QA Engineer, Research Scientist, Systems Architect, DevOps Engineer, Product Manager, Competitive Intelligence Analyst, Financial Optimizer)
- Generic "you are an agency" framing

**After:**
1. `## CRITICAL RULES` block at TOP:
   - RULE 1: Never Fabricate Success (moved from middle)
   - RULE 2: Loop Detection (moved from middle, now appears at TOP and near-bottom)
   - RULE 3: Health Check Gate (moved from Phase 3 middle section, now also at TOP)
   - RULE 4: Structured Thought prefix (new — from HuggingFace/ReAct research)
2. `## SPECIALIST DECISION PROCEDURE` replacing 10-role list:
   - 7 if-then routing rules (task type → role)
   - "Only activate the roles this task needs" explicit instruction
3. `## FINAL CHECKLIST` at BOTTOM (added):
   - 6-point session-close verification
   - "session is NOT done until task_complete is called"

**Also added:** RULE 4 — Structured Thought prefix (new):
- Before every tool call: state (1) known facts, (2) unknown, (3) why this action over alternatives
- Source: HuggingFace agents course; Width.ai documentation; emergentmind.com Focused ReAct

## Measurement Method
After 5 sessions with real data, measure:
1. **Rule-following rate** — count sessions where health check was called before commit (proxy: `run_health_check` in activity_log before any `git commit` line)
2. **Knowledge capture rate** — count sessions where knowledge.md was updated with a new lesson
3. **Loop incidents** — count sessions where agent hit a loop (should decrease)
4. **Task completion rate** — sessions where task_complete was called vs total sessions

## Predicted Impact
| Dimension | Before | After (predicted) | Basis |
|-----------|--------|-------------------|----|
| Rule-following rate | ~50% | ~80% | Critical rules now in U-curve top zone |
| Knowledge capture | 2/10 | 7/10 | Reflexion at bottom + FINAL CHECKLIST forces it |
| Task completion rate | 5/10 | 7.5/10 | FINAL CHECKLIST reduces incomplete sessions |
| Structured reasoning | 0% | ~60% | Thought prefix forces reasoning before tool calls |
| **Overall quality** | **5.0/10** | **7.5/10** | |

## Sources
- datagrid.com — "Fix AI Agents that Miss Critical Details From Context Windows" (2025): 40-60% accuracy drop for middle content
- kubiya.ai — "Context Engineering Best Practices for Reliable AI in 2025": active context compression + U-curve
- HuggingFace agents course — "Thought: Internal Reasoning and the ReAct Approach": structured thought prefix
- CSA Agentic AI Identity Management 2025: 80% of multi-role agents act outside expected behavior

## Next Measurement Date
2026-03-22 (after 5 sessions of real data)
