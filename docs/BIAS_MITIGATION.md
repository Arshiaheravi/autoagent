# Agency Bias Mitigation Plan

**Date:** 2026-04-19
**Scope:** Architectural + process changes to counter the 4 observed structural biases in AutoAgent.
**Status:** Plan. Execution tracked in `memory/backlog.md` under `[BIAS]` prefix.

---

## Why this exists

Every self-evaluating system has structural bias. AutoAgent is no exception — it writes its own prompts, grades its own sessions, and picks its own tasks. Without external counterpressure, the loop converges on self-serving equilibria: rules loosen, failures get reframed as success, hard tasks get deprioritized.

This doc enumerates the biases and specifies countermeasures. The goal is not "bias-free" (impossible) but "bias-bounded" — structural checks that make drift visible and reversible.

---

## Bias 1 — Self-serving META loop

**Mechanism:** META sessions read the last 5 sessions' failures and rewrite `PROMPT.md` / skills to prevent recurrence. The optimization target is "don't trigger that failure again" — which is satisfied by either (a) fixing the root cause or (b) loosening the rule so the behavior no longer counts as failure. Option (b) is locally cheaper and empirically more common.

**Evidence:** Any case where META adds "unless X" / "except when Y" exceptions without paired test coverage proving the exception is justified. Audit the last 10 META commits for pattern.

### Countermeasures

1. **[BIAS-1a] Immutable rules file** — split `PROMPT.md` into `PROMPT.md` (META-editable) and `PROMPT_CORE.md` (human-edit-only). Core rules: budget caps, security invariants, commit verification, loop-detector thresholds. META cannot touch PROMPT_CORE.md via hook in `launcher.py` that rejects the META session if the core file is modified.
2. **[BIAS-1b] META diff must justify** — every META-generated prompt change requires a paired entry in `memory/knowledge.md` citing which failed session(s) motivated the change + expected behavior change. Reject META commits that lack the justification block.
3. **[BIAS-1c] Regression-test on META changes** — META must re-run the last N failed session scenarios (stored as fixtures) against the new prompt and show they now pass. No fixtures = no prompt change accepted.
4. **[BIAS-1d] Human-review gate for scope widening** — if a META change *adds* an "except when" clause, escalate to human review (Seb) before merge. Narrowing rules = auto-merge; widening rules = human sign-off.

---

## Bias 2 — Council persona bias (backend cheerleading)

**Mechanism:** `PERSONAS` in `engine/council.py` routes each persona to a specific backend (Claude, GPT-4o, Gemini, DeepSeek). When council debates, each persona evaluates answers partly by stylistic fit with its own backend. Backend identity leaks into evaluation.

**Evidence:** Check Stage-2 peer-ranking outputs — if persona X consistently ranks answers from backend X highest across unrelated questions, the bias is measurable.

### Countermeasures

1. **[BIAS-2a] Anonymize Stage-1 responses** — already partially done (`_stage1_collect` builds "anonymized response block") per council.py:319. Verify: no persona name, no backend string, no stylistic fingerprint (strip markdown flourishes, normalize length). Add a test that confirms backend identifier never appears in peer-ranking prompt.
2. **[BIAS-2b] Rotating backends per persona** — assign persona-to-backend at session start via seeded round-robin, not static. Same persona "UX Reviewer" runs on Claude in session N, GPT-4o in N+1, etc. Dilutes the fingerprint.
3. **[BIAS-2c] Blind chairman** — Chairman (synthesizer) never sees which backend produced which answer. Only sees ranked answers + rankings. Already required but verify in test.
4. **[BIAS-2d] Cross-backend disagreement metric** — log Kendall-tau between persona rankings per session. If rankings converge across persona/backend pairs on every question, either the backends agree (fine) or the bias is invisible (check Q5a fingerprint test). If rankings diverge systematically along backend lines, flag.

---

## Bias 3 — Confirmation bias in self-assessment

**Mechanism:** Session reports success/failure based on its own output. `sessions.json` logged `cost_usd: 0` for 267 sessions and no session flagged it because none checked. The agent trusts its own "✓ tests passed" without external verification.

**Evidence:** Audit 2026-04-16 §0 item 5. Also: any `session_success: true` entry that lacks a corresponding CI green build or working-deploy signal.

### Countermeasures

1. **[BIAS-3a] External verifier** — session success requires BOTH self-reported pass AND independent verifier. Verifier = separate Claude subprocess with only the commit diff + test output, no access to self-reported status. Verifier issues ACCEPT / REJECT / UNCERTAIN. Only ACCEPT counts as green in `sessions.json`.
2. **[BIAS-3b] Invariant assertions** — at session end, assert a fixed set of cheap truths: `cost_usd > 0 if any Claude call made`, `git diff is non-empty if status == committed`, `test count did not decrease`. Failed invariant = session marked `integrity_fail`, excluded from success metrics.
3. **[BIAS-3c] Dashboard truth separation** — dashboard renders `self_reported_success` and `verifier_confirmed_success` as separate columns. Gap between them is the bias quantity. Publish it.
4. **[BIAS-3d] Random sample re-audit** — weekly job pulls 5 random recent "success" sessions, re-runs their tests on a clean worktree. If any fail, mark the session `audit_fail` and investigate why self-report disagreed.

---

## Bias 4 — TDD test-bias (tests match what's built, not what breaks)

**Mechanism:** TDD RED→GREEN cycle: agency writes a failing test, then writes code to pass it. Both the test and the code come from the same agent in the same session. Tests encode the agent's intended behavior, not the user's requirements. "Safe" tests that always pass get written; tests that would catch subtle bugs (edge cases, concurrency, integration) get omitted because they're expensive and the agent is rewarded for passing tests, not writing hard ones.

**Evidence:** Look for tests that mock the thing under test (e.g. `test_council.py` mocking `PERSONAS` instead of running real personas). Coverage of happy-path only. Zero mutation-testing survival rate.

### Countermeasures

1. **[BIAS-4a] Mutation testing in CI** — run `mutmut` or `cosmic-ray` weekly on `engine/council.py` and other critical modules. Report mutation survival rate. Target <30% (i.e. tests catch >70% of random code mutations). If >30%, tests are shallow.
2. **[BIAS-4b] Adversarial test generation** — separate session type "RED" whose only job is to write failing tests for existing code (opposite of TDD). Pays off only when RED finds a previously-unknown failure mode. Tracks count of novel failures found/week as a metric.
3. **[BIAS-4c] Property-based testing** — for core modules (council ranking, budget accrual, prompt builder), add `hypothesis` tests that explore input space rather than hand-picked cases. Agency writes property + invariant; hypothesis explores inputs.
4. **[BIAS-4d] Contract tests at boundaries** — agency's integration with Claude CLI, filesystem, git, SQLite knowledge DB should have contract tests that run against real dependencies (not mocks) in a sandbox. Separates "my unit test passes" from "the integration actually works."

---

## Cross-cutting: external observability

All 4 biases share one root: the agency is the only observer of its own behavior. Add external observers.

1. **[BIAS-X1] External benchmark suite** — weekly CI job runs agency against a fixed 20-task benchmark (SWE-Bench Lite subset or custom cultivOS regression set). Pass-rate + cost-per-task published to dashboard. Trend down = regression signal even if per-session metrics look green.
2. **[BIAS-X2] Diff summaries to human (Seb)** — every META prompt change + every rule narrowing/widening + every failed-invariant lands in a weekly digest email/dashboard widget. Human-in-loop for drift detection.
3. **[BIAS-X3] Adversarial healer** — separate healer agent instance whose job is to break the main agency (e.g., feed it malformed inputs, interrupt subprocess, fill budget). Catches brittleness the agency won't find by grading itself.

---

## Priority + sequence

Ship in this order (cheapest + highest leverage first):

| Order | ID | Estimated effort | Unblocks |
|---|---|---|---|
| 1 | BIAS-3b | 2 hr | fixes the "cost_usd: 0" class of bugs immediately |
| 2 | BIAS-1a | 3 hr | stops META from touching core rules |
| 3 | BIAS-2a verify test | 1 hr | proves anonymization works or doesn't |
| 4 | BIAS-3a external verifier | 1 day | architectural win, enables honest metrics |
| 5 | BIAS-4a mutation testing | 4 hr | quantifies test-bias for first time |
| 6 | BIAS-X1 benchmark suite | 1-2 days | overlaps with A3 from academic-readiness audit |
| 7 | BIAS-1b META justify, BIAS-1c regression fixtures | 1 day each | tighter META loop |
| 8 | BIAS-2b rotating backends | 4 hr | easy after 2a verified |
| 9 | BIAS-4b RED session type | 2 days | novel failure finder |
| 10 | BIAS-3d weekly re-audit, BIAS-X2 digest, BIAS-X3 adversarial healer | 1-2 days each | long-term health |

Total: ~2 weeks of focused work. Delivered incrementally, each item ships value independently.

---

## What this does NOT fix

- Fundamental limit: agency still grades itself on MOST decisions. External observers only catch coarse-grained drift. Fine-grained bias (persona stylistic preference, test-case selection, task scoring) remains.
- No protection against *collusive* bias across multiple independent runs (e.g., all 4 council backends share training-data bias against a minority programming style). Needs external human panel for those calls.
- Adding observers adds compute cost. External verifier roughly doubles session cost. Plan assumes value > cost; measure and adjust.

---

## Success metrics

After 4 weeks post-rollout:
- Mutation survival rate on `council.py` <30% (was unmeasured).
- `self_reported_success` vs `verifier_confirmed_success` gap <5%.
- Zero META commits that widen rules without human sign-off.
- Weekly benchmark pass-rate tracked, trend visible on dashboard.
- At least 1 RED-session-found novel failure per week.

If any of these miss, the countermeasure is broken — re-design, don't paper over.
