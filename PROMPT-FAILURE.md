# AutoAgent — Failure (tool-call errors, retry caps, budget tiers, doom loops)

When a tool fails, a test fails, or budget drops — this file governs. Companion: `PROMPT-RECOVERY.md` for crash/concurrency, `PROMPT-CONTEXT.md` for compaction.

## WHEN A TOOL CALL FAILS OR RETURNS UNEXPECTED RESULTS
Do NOT retry the same call. Instead:

**Step 1 — Classify the failure type**:
- **Interface misuse**: schema violation — malformed JSON, missing required fields, wrong type → re-read the API/function signature
- **Initialization**: tool/import/config not available → fix setup first
- **Parameter**: wrong argument format or value → check allowed enums, bounds, and constraints
- **Execution**: tool ran but produced wrong output → check the logic, not the call
- **Partial execution**: tool returned incomplete output (truncated, missing fields) → check if the operation needs continuation or a larger context/timeout
- **Semantic misuse**: valid call that is unproductive or off-task → reconsider whether this tool/approach advances the goal
- **Result-interpretation**: output was correct but you misread it → re-read the raw output
- **Re-entrant failure**: fix for step N caused step N+1 to fail, which cascaded further → STOP fixing forward, trace back to first divergence (see Error Cascade pattern #8 in agent-patterns.md)

**Step 1.5 — Classify recoverability** (linked to ERR early-step recovery):
- **RETRYABLE**: timeout, rate limit, transient network error, stale file state → retry with 2-attempt max. If both miss, your mental model is wrong — re-read from scratch (ERR geometric cascade: 80% recovery at attempt 2 → 30% at attempt 4 → collapse)
- **TERMINAL**: auth failure, missing resource/file, schema mismatch, dependency not installed → zero retries, fix the root cause immediately
Only retry RETRYABLE failures. TERMINAL failures that are retried waste 2+ tool calls for guaranteed re-failure.

**Step 2 — Recover with the right approach for the category**:
1. List 2–3 hypotheses for the failure, ranked by likelihood
2. Check the most likely hypothesis first (read the error message literally — it usually names the cause)
3. **Failure-conditioned knowledge search**: before guessing a fix, search knowledge.md for the SPECIFIC function name, test name, or error type from the failure. A past fix for the exact function is stronger than a generic rule.
4. Try a different approach if the first hypothesis was wrong
If the failure repeats a second time, stop and write to current_task.md: "BLOCKED: [what failed] — [hypotheses checked]". Then pick a different approach or log it as a known issue.

**When feeding failure output back into a fix**: State "The specific failing step was [X], it failed because [Y], and the fix should address [Z]" — not raw stack traces.

**Diff-level provenance**: When tests fail after a code change, run `git diff` to see exactly what changed. Trace from the changed lines to the failing assertion. Never debug from memory — the diff is authoritative.

## LOOP EXIT CONDITIONS
Before entering any refinement loop (e.g. fix-test-retry cycle), define the acceptance criterion:
- "Pass: all tests green" — concrete and measurable
- "Pass: Playwright check returns 0 failures" — concrete and measurable
- "Pass: feature works as described in current_task.md step N" — concrete
If no criterion exists, stop looping after 2 retries and log the blocker to current_task.md instead of looping indefinitely.

**Anti-patterns**:
- Never retry an identical failure — change the approach first
- Never assume context carries forward between compactions — current_task.md is the shared state
- If a loop produces the same error twice, classify it as BLOCKED immediately

**Tool necessity gate**: Before making a tool call, ask: "Is this call necessary to advance the current step?" If the answer is uncertain, skip it — more tool calls ≠ better outcomes (Agentic Tool Use survey 2604.00835). Assess necessity, not just non-redundancy.

**MCE crossover: budget-gated necessity** (tool necessity gate + budget-aware exploration): Budget tier determines the necessity bar for every tool call — **>70%**: standard gate ("is this necessary?"); **30-70%**: must justify in ≤5 words before calling; **<30%**: SKIP unless this call directly produces the current step's done-condition. At low budget, informational reads and exploratory greps are ghost-session risk. (Source: arxiv 2604.02547 behavioral drivers + budget-aware exploration)

**Redundancy check**: Before making a tool call, check if it's semantically similar to a call in the last 3 turns. Don't re-read files you just read, re-run passing tests, or re-grep for found content.
**MCE crossover: scale checks together** (verification scaling + redundancy): When a change qualifies for "light" or "skip" self-critique (single-file <20 lines, config/docs), ALSO skip the redundancy check. Both checks scale to the same change scope — spending tokens on redundancy analysis for a 3-line config edit is wasteful. One scope assessment, two check waivers. (Source: MCE synthesis — arxiv 2602.03485 + arxiv 2603.19896)

## FAILURE HANDLING — Budget Tier Table

| Budget remaining | Retry cap | 1st failure action | 2nd failure action |
|------------------|-----------|---------------------|---------------------|
| >30% | 3 | Try fix, re-run | Alternate approach, re-run |
| 20–30% | 1 | Read error, apply single fix, re-run | PARTIAL commit (see below) |
| <20% | 1 | Read error, apply single fix, re-run | EMERGENCY commit tier 2 |

**PARTIAL commit** (budget 20–30%, still failing):
```
git add <files>
git commit -m "PARTIAL: agent: <feature> — test failing: <test_name>"
git push
```
Next session detects PARTIAL prefix and resumes.

**EMERGENCY commit** (budget <20%, fixes exhausted): stop retrying. Commit what you have. Partial progress in git > lost work.

## Doom-loop detection
- Cap fix-test-retry at 3 iterations per failing test (reduced per Budget Tier Table above when budget is lower). After 3 failures, re-read source and test from scratch.
- If total tool calls exceed 80, emit CONTEXT_SUMMARY and assess whether remaining work fits in context. If not, checkpoint and stop.
- If you undo a change made <5 tool calls ago, STOP and re-read relevant files.
- **Error budget**: If you accumulate more than 10 errors across the session, STOP — checkpoint and move on.

**Early-step recovery**: If your first two fix attempts both miss, your mental model is wrong — re-read the failing code and test from scratch instead of trying a third variation.

**MCE crossover: step-1 fast-fail** (doom-loop cap + early-step recovery): If the FIRST step of a task fails twice, your mental model was wrong BEFORE you even started. Do NOT apply the 3-retry cap — treat any 2nd failure on step 1 as a BLOCKED signal immediately. Re-read the task definition in current_task.md AND grep for the target files from scratch. The cost of a wrong step-1 assumption compounds through every subsequent step. (Source: XAI Coding Failures arxiv 2603.05941 — 43.8% of planning failures could be prevented by re-grounding before implementation)

## Budget-aware exploration
- **Budget >70%**: Explore freely
- **Budget 30-70%**: Focus — stop exploring, build the current step
- **Budget <30%**: Exploit only — finish current step, checkpoint, do not start new exploration

**Trajectory structure over trajectory length** (arxiv 2604.02547): Agent success is driven by STRUCTURE (gather context → build → validate), not by minimizing tool call count. A structured 80-call session beats an unstructured 40-call one. Never sacrifice the gather→build→validate sequence to reduce step count. Per-step rule: gather first, build second, verify third — always in that order.

## EMERGENCY COMMIT — anti-ghost-session rule
Ghost sessions happen when code is WRITTEN but tests are NEVER RUN before context exhaustion. TWO tiers:

**TIER 1 — Tests passed (budget <30%):**
1. COMMIT AND PUSH IMMEDIATELY — do not wait for full verification gate, frontend check, or logging
2. Write activity_log + sessions.json + clear current_task.md with whatever context remains
3. Ghost detection backfills missing logs next session (see `PROMPT-RECOVERY.md`)

**TIER 2 — Tests not yet run (budget <20%):**
1. Stage all changed files: `git add [specific files]`
2. Commit with "PARTIAL:" prefix — e.g., `git commit -m "PARTIAL: agent: add risk map endpoint — tests not run"`
3. Push immediately — partial code > no code
4. Next session ghost detection picks it up, runs tests, fixes failures, re-commits

Root cause of ghost sessions: code written → tests NEVER RUN → context dies. Fix: run tests after EACH FUNCTION (test-gating per step, see `PROMPT-WORK.md`), not after all code is written. Tier 2 is the safety net when test-gating is skipped. (Sessions #249, #253, #259 all crashed before test step.)

**Trajectory length warning**: If total tool calls exceed 60, you are likely in a failure trajectory (failing attempts use 4× the resources of successful ones — arxiv 2604.03515). Emit CONTEXT_SUMMARY, reassess, and consider whether to simplify scope or emergency-commit what you have.
