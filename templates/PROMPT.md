# AutoAgent — WORK session instructions

<!-- COMPILED by scripts/build_template_prompt.py from the hardened
     PROMPT-*.md satellites. Do NOT edit by hand — edit the satellites
     and recompile, or the two will drift again. -->


<!-- ==== RECOVERY ==== -->

# AutoAgent — Recovery (ghost commits, orphans, concurrent sessions)

Run these BEFORE reading current_task.md or backlog. Crash/race safeguards are non-optional — they sit at the top of every session.

## ORPHAN RECOVERY (crash safeguard — run FIRST)

1. Run `git status --short`. Look for `??` (untracked) or ` M` (modified) under project src.
2. Classify:
   - **Matching current_task.md entry exists** → continue that task (normal recovery)
   - **No matching entry** → orphan. Ask:
     - Files form a logical feature (e.g. `services/health.py` + `test_health.py`)?
       → ADOPT. Add to current_task.md, run its tests, commit+push. Do NOT re-implement.
     - Files scattered/partial/exploratory?
       → INSPECT manually. If safe to discard: `git clean -fd`. Else, leave and flag.
     - Files cross your claimed task boundary?
       → LEAVE them. Flag to activity_log with tag `orphan-boundary-violation`.
3. Timing: this check runs BEFORE backlog read.

**Orphan-adoption commit-order rule** (MANDATORY when adopting orphans): the order is (1) write your active_claims.md entry, (2) run the ISOLATED test file only (`pytest tests/test_<orphan>.py -q`, ~5-30s), (3) stage + commit + push, (4) THEN run the full-suite non-regression. Do NOT run the full pytest suite before commit+push — the suite takes 5-7 min and during that window a sibling session woken on the same orphans will race ahead and commit first, wasting your entire run. (Evidence: session #358 ran the 5-min full suite BEFORE staging during a #201 orphan adoption; sibling #357 staged + committed identical files mid-suite-run; #358 burned ~25 tool calls + 5 min for zero output. Session #359 applied this exact ordering manually on #202 orphans and won a race against still-active #358 by pushing in <30s — same pattern, opposite outcome.)

**Do NOT re-implement from the spec when the orphan files already cover it** — even when re-writing via TDD produces "functionally identical" output, the adoption path is ~10 tool calls cheaper and the audit trail is the same. Reading the orphan files to verify they match the spec, then running the tests, is the mandatory first action. Do NOT pick a new backlog task while orphan intelligence files sit untracked — they silently accumulate across sessions and block backlog numbering. (Evidence: session #333 observed `coop_treatment_effectiveness` orphan but left it untracked. Session #335 saw META-flagged orphan #191 and chose to re-implement fresh via TDD instead of adopting, justifying it as "functionally identical" — correct outcome, wasted ~10 tool calls.)

**Orphan intelligence sweep** (MANDATORY, 10 seconds): Scan `git status --short` for untracked files matching `src/app/services/intelligence/*.py`, `src/app/models/*.py`, or `tests/test_*.py`, AND unstaged modified files under `src/app/api/*.py`. If ANY exist and no matching current_task.md entry covers them: this is an orphan ghost from a crashed concurrent/prior session. ADOPT IT (per rule above).

## GHOST COMMIT DETECTION

Run `git log --oneline -3` and check if the latest commit(s) appear in `activity_log.md`. If a commit exists with the `agent:` prefix but has NO matching session log entry: the previous session committed but crashed before logging. Backfill the missing log entries (activity_log, sessions.json, done.md), remove the completed task from backlog, and update NORTH_STAR test count — then continue.

**WAL marker fast-path**: Also grep `activity_log.md` for `PENDING` (write-ahead markers from the commit step in `PROMPT-VERIFICATION.md`). If a PENDING entry exists: (a) if a matching commit is in `git log`, finalize the marker (replace PENDING with the session type, write the SHA) — this is a ~2 tool call backfill, no guessing from the commit stat. (b) If no matching commit, the prior session crashed BEFORE committing — delete the PENDING line, treat it as an abandoned attempt, and continue. The marker eliminates ghost-commit backfill guesswork: files, tests, and task name are already in the entry.

**Cross-reference check**: When activity_log shows the most recent session as "done", verify the git log HEAD message MATCHES that session's task description. If HEAD message describes a DIFFERENT task than the activity_log "done" entry, the log was backfilled optimistically — the committed work may be a different feature and you may be about to duplicate it. Run `git diff HEAD~1 HEAD --name-only` to see exactly what the last commit changed before picking the next task. (Source: session #269 — duplicated WhatsApp simulator that was already committed)

## CONCURRENT SESSION GUARD (run before claiming any backlog task)

MANDATORY, 15 seconds. Before committing to a task, run BOTH:
(a) `cat .autoagent/memory/active_claims.md` — shows tasks other running sessions have claimed
(b) `git -C <project> log --since="15 minutes ago" --pretty=format:"%h %s"` — recent commits by other sessions
If your target task_id OR any keyword from the backlog description OR your planned primary edit-file appears in EITHER output → PIVOT to the next backlog task that touches DISJOINT files. Do not edit a file another session is actively modifying. Once you pick your task, IMMEDIATELY append to `.autoagent/memory/active_claims.md`:
`SESSION #N | TASK #M | started YYYY-MM-DDTHH:MM | files: src/app/api/X.py, services/intelligence/Y.py`
Use ISO8601 with the date prefix — bare `HH:MM` is ambiguous across midnight and has already caused one premature prune of a still-running session (session #348 ↔ META #349 incident, 2026-04-12).

**Wall-clock capture (MANDATORY)**: Run `date -u +%Y-%m-%dT%H:%M` to get the actual current time and use that literal value in the claim. Do NOT use `T00:00`, `T12:00`, or any placeholder — session #370 was pruned by a racing sibling who misread a `T00:00` placeholder as "12 hours old" and invoked the stale-crash rule on a <2-min-old claim. The pruning protocol in active_claims.md now rejects `T00:00`, but prevention at write-time is cheaper: one extra `date` call eliminates the ambiguity entirely. (Source: session #370 incident 2026-04-12.)

**Future-stamped timestamps are FORBIDDEN**: A `started` value MORE than 5 minutes in the future relative to the current UTC clock is invalid metadata and is prunable on sight by any META/DEEP session, regardless of age. Sessions writing future-stamped claims (e.g. `T13:00` while `date -u` shows `T09:25`) blocked 4 consecutive WORK no-ops (#375/#376/#378/#379) on April 12 because the hold-off rule never elapsed against the bogus timestamp. ALWAYS use the literal output of `date -u +%Y-%m-%dT%H:%M` — never hand-type, never round, never advance "to be safe". (Source: META #380 — sessions #372/#373 incident 2026-04-12.)

**Backlog-existence check (MANDATORY before claim)**: Before appending your claim line, `grep "^### N\." .autoagent/memory/backlog.md` for your chosen task number N. If grep returns nothing, the task does not exist — DO NOT claim it, do NOT invent a task number, do NOT proceed. Pick a different task that exists, or exit if none remain. Sessions #373 (claimed phantom #211) and #378 (claimed phantom #212) both invented task numbers that META had never added; both stale claims blocked the only real autonomous tasks for 4 consecutive wake cycles. A claim against a non-existent task number is permanent dead weight in active_claims.md. (Source: META #380 incident 2026-04-12.)

**MCE crossover: compound pre-claim integrity scan** (pre-pick existence check + backlog-existence check + concurrent session guard + no-substitute rule, collapsed into ONE parallel bash block): At claim-time, run all four gates as a single compound command so skipping one is structurally impossible. The template:
```bash
{ grep "^### $TASK_N\." .autoagent/memory/backlog.md; echo "---"; grep -rE "$ENDPOINT_PATH|$KEYWORD1|$KEYWORD2" src/ frontend/ 2>/dev/null | head -5; echo "---"; cat .autoagent/memory/active_claims.md; echo "---"; git -C $PROJECT log --since="15 minutes ago" --pretty=format:"%h %s"; } 2>&1
```
Interpret the four sections in order: (1) backlog heading found? — if empty, task is phantom → exit. (2) codebase matches for endpoint/keywords? — if non-empty, task may already be implemented → existence-check the real file paths before claiming. (3) any concurrent claim touching your task_id, keywords, or planned files? — if yes, pivot disjoint. (4) any commit in last 15 min touching your files? — if yes, stale task, exit. Running the four as one compound block (a) makes the pre-claim cost ONE tool call instead of four, (b) eliminates the TOCTOU gap between sequential checks, (c) ensures an interrupted session cannot skip the "inconvenient" check last. (Source: MCE synthesis — sessions #373/#378 (phantom task), #269 (no-substitute miss), #366/#370 (concurrent TOCTOU) all had the check available but skipped it under context pressure. Collapsing to one compound call closes the skip path.)

**Session-number collision rule** (MANDATORY): Do NOT pick your session number by incrementing the last activity_log.md entry alone — concurrent sessions both read the same last entry and collide on the same N. Instead compute `session_num = max(highest_N_in_activity_log_last_10_entries, highest_N_in_active_claims.md) + 1`. Include your chosen session_num in your active_claims.md line at claim time (the format already requires it). Before writing your activity_log entry at commit time, re-read the last 3 log entries AND active_claims.md; if your N now appears in either, bump to `max(observed) + 1` and prefix your log entry NOTE with `(bumped from #X)`. Do this atomically with the log write. (Evidence: session #361 NOTE "SESSION #360 was taken by a concurrent META entry at log top before I wrote mine; bumped to #361 to avoid clobbering" — a concurrent META and WORK both selected #360; #361 handled the collision manually. Session #355 appears twice in activity_log.md — the same pattern went unrepaired. 2026-04-12.)

REMOVE your claim line after commit+push. If `cat active_claims.md` fails (missing file), treat it as empty and continue — but recreate it by writing a header before appending. (Evidence: sessions #337-#340 — 4/5 consecutive WORK sessions hit concurrent collisions on `api/cooperatives.py`; one session's imports got staged into another session's commit leaving HEAD referencing untracked modules. The orphan sweep caught orphans post-crash; this rule prevents the race in the first place.)

**Optimistic write-verify claim** (MANDATORY, closes the TOCTOU gap): After appending your claim line, do NOT start work immediately. Instead: (1) `cat active_claims.md` ONCE MORE (re-read after write) AND `git fetch --quiet && git log origin/$BRANCH --since="2 minutes ago" --pretty=format:"%h %s"`; (2) grep your re-read output for ANY other claim line touching your task_id OR any of your listed files; (3) if a sibling claim appeared in the same window — the LATER timestamp (yours, since you just wrote) exits via concurrent-wake rule. If a new commit by another session touches any of your files — exit. Only proceed to file edits if your claim is the sole entry for your task/files AND no fresh commits contest it. This is the 4-step CodeCRDT protocol (scan → optimistic write → wait → re-read verify) — the append-then-proceed flow has a time-of-check/time-of-use hole that lets two sessions both think they own the same task if they append within milliseconds of each other. The re-read + fetch closes it. (Source: CodeCRDT arxiv 2510.18893 — lock-free claim via optimistic write + convergence re-read, validated mechanism for "at most one agent per task".)

**Concurrent-wake exit rule** (MANDATORY when current_task.md state changes mid-pivot): If you woke into an idle current_task.md, then between reading it and claiming a backlog task another concurrent session has overwritten current_task.md with their own task, OR HEAD has gained a commit that already implements the cleanup/task you were about to claim — EXIT THE SESSION. Do NOT pivot to a third backlog task. current_task.md is a single-slot resource; when N>1 sessions race for the same idle slot, only one wins. Pivoting to a third task while another session is mid-flight on its api/__init__.py wiring is a guaranteed collision on the next router registration. Write a brief activity_log "no-op, concurrent race" entry naming the winning session and exit. (Evidence: session #355 — three sessions woke into the same idle state, raced on the same META #351 micro-cleanup; #353 won in <1 min, #354 picked #199, #355 burned ~5 min of test runtime + ~25 tool calls before correctly exiting without writing knowledge.md/sessions.json. The exit was correct; the prior pivot attempt was the waste.)

## IF YOU ARE STOPPED MID-SESSION
If you start a session and current_task.md has unchecked steps:
- Those steps are from a previous interrupted session
- Continue from the first unchecked step — don't start over
- The codebase may have partial work already — check with `git diff` first


<!-- ==== WORK ==== -->

# AutoAgent — Work (task pick, plan, execute)

This file governs WORK sessions end-to-end: impact filter, task selection, TDD, current_task.md workflow, and session invariants. Companion files:
- Crash/concurrent recovery → `PROMPT-RECOVERY.md`
- Context discipline / checkpoints / memory stratification → `PROMPT-CONTEXT.md`
- Error classification / retry caps / budget tiers → `PROMPT-FAILURE.md`
- Verification gate / commit / logging → `PROMPT-VERIFICATION.md`

## BEFORE PICKING ANY TASK — IMPACT SCORE

Task admitted if scores YES on ≥1 of:

| Category | YES when | Example reject |
|----------|----------|----------------|
| A. Fix crash | Task fixes a bug that blocks users | — |
| B. New workflow | Task adds a user-facing endpoint, page, or command | — |
| C. Latency >100ms | Task reduces measured response time >100ms | Optimize query already <50ms → NO |
| D. Test coverage | Task adds tests for previously untested code path | — |

Scan backlog task for keywords: "fix", "crash", "add", "latency", "test", "coverage".
If none match and task reads as refactor/cleanup/docs-only → SKIP.

## EVERY SESSION — READ FIRST
Read `.autoagent/PROJECT.md` first for project rules, codebase conventions, git paths, and test commands. Then read `.autoagent/skills/agent-patterns.md` for failure modes that kill sessions. Takes 60 seconds total. Do it before picking a task.

## EVERY SESSION — WHAT TO DO

1. Run `git diff` and `git status` first — finish any in-progress work before starting new.
   **Baseline health check**: If no in-progress work, run the test suite once before picking a task — verify green state. If tests are red, fix them before starting anything new.
   **Orphan / ghost-commit recovery runs FIRST** — see `PROMPT-RECOVERY.md` for the orphan sweep, ghost-commit detection, WAL marker fast-path, and cross-reference check. Do those steps before reading current_task.md or backlog.
2. Read `.autoagent/memory/current_task.md` — if it has unchecked `- [ ]` steps:
   - Run `git log --oneline -5` — if work is committed, clear current_task.md and go to step 3.
   - Run `git status --short` — if relevant files are STAGED (M/A in first column) but not committed, the previous session staged but crashed before commit. **Do NOT re-implement.** Skip directly to Step 8: run tests, fix failures, then commit the staged work.
   - Run `git status --short` — if relevant files are UNTRACKED (`??`) or modified (` M`) but match the task, the previous session wrote code but crashed before staging. **Do NOT re-implement.** Read the existing files first to assess what is already done, check off those steps, and continue from the first genuinely incomplete step. **If a `tests/test_*.py` file for the task is already untracked, your very next action is to RUN THE TEST COMMAND — do not read or edit anything else until you know which tests pass.**
   - **CRITICAL: Untracked ≠ committed ≠ done.** If a previous step is marked `[x]` but the corresponding files are still untracked (not in git), that step is NOT actually done — the session marked it complete without committing. Treat untracked task files as partial work: run tests → fix → stage → commit BEFORE claiming the task is complete. (Evidence: session #318 marked #175 "done" because sensor_freshness files existed untracked, but never tested or committed them.) Ghost sessions #249-#253 all crashed after writing code+tests but before running them; the fastest recovery path is test → fix → commit, not re-reading.
   - **File existence check** (MCE crossover: sub-task isolation + ghost detection): Before deciding "not started yet", grep for the files the task would create. Example: if the task says "add upcoming_treatments.py", run `ls src/app/services/intelligence/upcoming_treatments.py 2>/dev/null`. If the file exists but isn't in git status, a previous session wrote it without staging. Treat it as UNTRACKED (above rule applies). This prevents re-implementing code that exists but hasn't been staged. (Source: sessions #267-#268 — code existed but ghost detection missed it because git status showed no changes)
   - If neither committed nor staged nor modified (and files don't exist), continue from the first unchecked step.
   - **Stale spec check** (when resuming after 1+ sessions): Re-verify that any ORM model names, route paths, or function signatures mentioned in current_task.md still match the current codebase. Run `grep -r "[ClassName]\|[function_name]" src/` for 2-3 key identifiers from the task. Stale specs are the #1 cause of "looks correct but silently wires through deprecated paths" bugs. (Source: Codified Context arxiv 2602.20478 — two documented incidents of agents wiring through deprecated paths from stale task specs)
3. If no current task, read `.autoagent/memory/backlog.md` — pick the highest value unchecked task that you can complete autonomously. **Skip tasks marked "needs-human" or "blocked on external input"** — these require human action you cannot take. Pick the next autonomous task instead. Never start a session on a task you can't finish without human input.
   **Pre-pick existence check** (30 seconds, mandatory): Before committing to a backlog task, grep the codebase for the target endpoint path AND 2-3 feature keywords: `grep -r "keyword1\|keyword2\|/api/path" src/ frontend/`. If a matching endpoint or feature is found: mark it as duplicate in backlog.md, note what already exists, and pick the NEXT task. Backlog duplicates silently accumulate — a 30-second grep prevents a wasted context window. (Source: sessions #258 — 3 duplicate tasks found mid-session)
   **Concurrent session guard and claim protocol** → see `PROMPT-RECOVERY.md` (active_claims.md, ISO8601 timestamps, wall-clock capture, backlog-existence check, compound pre-claim integrity scan, session-number collision, optimistic write-verify, concurrent-wake exit).
   **ONE TASK PER SESSION — NO EXCEPTIONS.** Once you pick a task, that is your ONLY task. Do not start a second task, do not "quickly fix" something unrelated, do not add bonus features. If you discover something else that needs doing, add it to backlog.md and move on. Scope creep is the #1 session killer.
   **SESSION STOP after commit**: After committing and pushing your one task, the session is COMPLETE. Do NOT pick a second task from backlog even if context budget remains. Write the activity_log entry and EXIT. (Evidence: session #317 completed #173, then started #175 with remaining budget — left partial untracked code.)
4. If backlog has ≤2 autonomous (non-BLOCKED) tasks OR is empty — read the codebase, find unsurfaced backend endpoints, add 6-8 tasks, pick top one. Don't wait for backlog to hit zero — replenish when low.
5. **Pick the right skill file** — read `.autoagent/skills/INDEX.md`, find the row that matches your task type, then read ONLY that skill file. Do not read all skill files. Examples:
   - Writing a backend route → `coding.md`
   - Creating an Excel export → `xlsx.md`
   - Generating a PDF report → `pdf.md`
   - UI change → `design.md` + `playwright.md`
   - Committing code → `git.md`
   - Writing tests → `testing.md`
   - Pre-commit quality check → `audit.md`
   If no skill matches → proceed without one, then create a new skill file if you discover a reusable pattern.
6. **TDD — TWO-COMMIT PROOF** (binds with `skills/quality-standards.md:9-34`, supersedes the pre-split single-commit "TESTS FIRST" rule): Every feature task produces TWO commits, not one.
   - **Commit 1 (tests only)**: `test: add failing tests for [task name]`. Contains ONLY test files. Tests MUST fail when run. If they pass, the tests are wrong.
   - **Commit 2 (implementation)**: `feat: implement [task name] — all tests passing` (or project-specific prefix per `PROJECT.md`). Contains ONLY source files. Tests now pass.
   - **TDD gate between commits**: After writing tests, run the test command and confirm RED before writing any implementation. Verify. Only then proceed.
   - **Verification line** (include in VERIFICATION REPORT, see `PROMPT-VERIFICATION.md`):
     ```
     TDD: YES
       Commit 1 (tests): [hash] — X tests failed
       Commit 2 (impl):  [hash] — X tests passed
     ```
   - META sessions verify by checking `git log` for the two-commit pattern.
   - **Why two commits?** One commit bundling tests + code makes TDD unfalsifiable. Two commits create an audit trail proving the tests existed before the implementation.
   - If the backlog task lists specific test cases, write ALL of those tests first (they should fail). Do not write implementation before tests exist. This is non-negotiable. (Source: sessions #267, #268, #272 ghost pattern — write tests + write implementation without running tests in between produces unverifiable coverage.)
7. **IMMEDIATELY write your task steps to `.autoagent/memory/current_task.md`** before doing anything else:
   ```
   # Current Task: [task name]
   Steps: N total | N remaining
   - [ ] Step 1
   - [ ] Step 2
   - [ ] Step 3
   ```
   **Step quality bar**: Each step must be independently verifiable, have a single dominant risk, and a clear done condition. If a step can't be verified in isolation → split it. Steps should be minimal (can't decompose further), verifiable (objectively determinable), and deterministic.
   Update the "remaining" count as you check off steps. If remaining > 5 and context is getting long, sub-divide the rest into a continuation task rather than trying to finish everything in one window.
   **Context discipline, checkpoints, memory stratification, compression** → see `PROMPT-CONTEXT.md`.
8. Build each step. Check it off `- [x]` when done. Update the remaining count.
9. When all steps done: **premature termination guard** — before proceeding to the verification gate, count the unchecked `- [ ]` items in current_task.md. If ANY remain, the task is NOT done regardless of how it feels. This check takes 5 seconds and prevents the MAST FM-3.1 failure mode (premature termination accounts for 8% of all multi-agent failures — arxiv 2503.13657). Then proceed to the verification gate (see `PROMPT-VERIFICATION.md`) — do NOT commit until it passes.
   **MCE crossover: termination guard + non-regression gate** (arxiv 2601.04620 + arxiv 2503.13657): Two conditions BOTH must hold for "done": (a) zero unchecked steps AND (b) test count_after ≥ count_before. If STEP 1 reveals count_after < count_before: re-open the task — add a new unchecked step "Fix dropped test(s)" to current_task.md and do NOT proceed to commit until fixed. A task with all steps checked but dropped tests is NOT done.

## MODULE SPLITTING — backward-compatible re-exports
When splitting a module into two files, keep backward-compatible re-exports in the original file: `from new_module import X, Y  # noqa: F401`. This preserves the public API surface so all existing callers and tests continue working unchanged. Before adding new features to a file near the line limit, check `wc -l` first — extract helpers BEFORE wiring, not after exceeding the limit.

## WHEN BUILDING A FEATURE
- **Seed/data-extension consumer-test gate** (MANDATORY for any task that adds rows to an ORM seed function or extends a static reference dataset): BEFORE commit, run the test file(s) for EVERY endpoint that reads the extended table. `grep -rl "from .*db.models import .*<TableName>\|<TableName>(" src/app/api/ src/app/services/` to find consumers, then `pytest` their test files. The seed-task's own test (e.g. `test_X_seeds_extended.py`) only validates the seed function — it does NOT exercise the Pydantic response models that serialize the new rows. New columns or None values in new rows commonly 500 the existing read endpoints. (Source: #216 a62c0b1 added 10 ancestral seeds with `problems=None`/`crops=None` fields; `/api/knowledge/ancestral` returned 500 because the Pydantic response model declared list types; 4 tests broke; caught only 2 sessions later by #385; fixed in ghost commit 24d548d. The seed task spec missed the consumer-test step entirely.)
- **Cross-cutting assertion gate — generalization of the consumer-test gate** (MANDATORY whenever a task introduces a NEW tagged `APIRouter`, a NEW Pydantic response model, or a NEW ORM table + route pair — NOT required for pure frontend FileResponse routes which don't register in openapi). BEFORE commit, run `pytest tests/test_openapi_docs.py` (and any other `tests/test_*docs*.py`, `tests/test_*openapi*.py`, `tests/test_*routes*.py`) alongside the feature's own test file. test_openapi_docs enforces two invariants the task author usually forgets: (a) the router's `tags=["..."]` string must also appear in `src/app/app.py openapi_tags` with a `description`, and (b) every route decorator must carry `description=` or a docstring. Both fire at full-suite time, not isolated-test time, so without this gate the new files ship red and a sibling has to hotfix. Cost of the gate: one pytest invocation (~3 s). Cost of skipping: one red-main commit + one hotfix commit + a 6-min sibling race. (Source: session #391 shipped 3ea4f23 for #207 tek-adoption without running openapi_docs; session #392 had to hotfix with bf3ce7c. Rule previously captured in knowledge.md:196 but not in PROMPT.md — promoted here 2026-04-12 BRAIN.) **MCE crossover**: this is the same shape as the seed consumer-test gate above — both say "before commit, run the cross-cutting test files that exercise your change from a dimension your feature test doesn't cover." General form: classify your change (seed / new-router / new-model / frontend-file-route), and run the matching gate. Frontend FileResponse routes are exempt from the openapi gate (knowledge.md:7) but subject to their own page-test. When in doubt, run `pytest tests/test_*docs*.py tests/test_*routes*.py -q` — it's cheap.
- **Quick existence check** (30 seconds, before any coding):
  1. Does this function/endpoint already exist? → `grep -r "def function_name\|/api/endpoint" src/`
  2. Is there a similar pattern in the codebase? → check knowledge.md SKILL tags for matching WHEN condition
  3. Is there an external library that solves this? → only for non-trivial functionality (HTTP clients, algorithms, file formats)
  If the answer to #1 is yes, extend — don't recreate. If #2 matches, follow that pattern exactly.
- **No-substitute rule**: If an existence check for a specific entity/file/symbol/endpoint returns nothing, treat the result as empty — do NOT silently swap in a similarly-named alternative and proceed. Example: grep for `whatsapp_simulator.py` → no hits → do not then act on `whatsapp_sim.py`; either confirm the real target with the user/spec or report "not found". Fuzzy substitution masquerading as success is a distinct failure mode from a missing grep — it produces commits that look correct but target the wrong artifact. (Source: session #269 — duplicated WhatsApp simulator because a pattern-match stood in for the real target; arxiv 2512.07497 wrong-adaptation-to-missing-values).
- **Spec formula alignment** (before first test): When the task description lists explicit numeric values (point thresholds, exact formulas, weights, tiers like "critical=30pts, high=25pts") — write a test assertion using those EXACT literal numbers BEFORE writing any implementation. Example: spec says "critical weather = 30 pts + high disease = 25 pts" → first test asserts `risk_score >= 55`. A formula that uses weighted fractions instead of direct addition can look correct but silently violate the spec — the literal-value test catches this before any implementation is written. (Source: session #259, arxiv 2604.04226 — 100% failure rate from type/signature mismatch)
- **Specification failures dominate** (arxiv survey of 306 practitioners): 41.8% of autonomous coding agent failures are SPECIFICATION failures (wrong understanding of what to build), 36.9% are coordination failures — only 21% are infrastructure. This elevates ARCH DECISION + spec formula alignment from "nice to have" to the #1 failure-prevention lever. Before coding ANY new service: (1) copy the exact backlog spec into current_task.md verbatim, (2) extract every numeric value / key name / endpoint path as a literal test assertion, (3) write ARCH DECISION in one sentence. Anything you skip here shows up as the dominant failure class. (Source: session #328 BRAIN, arxiv 2508.00083 survey)
- **Key-schema assertion** (before implementing any service that returns a dict): Write a test asserting the EXACT key names returned by the service BEFORE implementing it. Example: service returns `{"health_delta": ..., "cost_mxn": ...}` → first test asserts `assert "health_delta" in result` and `assert "cost_mxn" in result`. Any mismatch between service output keys and route consumer keys will fail immediately at TDD stage. This is the MCE crossover of spec-formula + fail-before: catches the `health_delta` vs `delta` class of bugs at zero implementation cost. (Source: session #265 incident — key mismatch undetected until route tried to read wrong key)
- **Heuristic retrieval** (before coding): Scan knowledge.md RULE entries for trigger conditions matching your task type. Example: if building a batch endpoint, search for "batch" in rules. Apply matching rules proactively — don't wait for a failure to rediscover them.
- **Verbatim recall for load-bearing rules**: When a recalled rule decides an action (ORM column name, endpoint path, formula threshold, file path), quote it VERBATIM from the source file before acting — do not paraphrase from memory. Paraphrased recall drifts from the stored text and is the retrieval-side counterpart to stale-spec drift. One `grep` + one visual match is cheaper than a debug cycle on a misremembered threshold. (Source: arxiv 2604.01599 semantic drift — curator/reasoner mismatch when agent reads its own memory)
- **Contrastive retrieval** (arxiv 2604.07487 — CLEAR, +8.53pp on AppWorld): when scanning knowledge.md and activity_log for a task type, retrieve BOTH the successful pattern AND the failure pattern for that same task type. The delta between what worked and what failed is the actionable guidance — a RULE alone is weaker than "here is what worked (X) vs what failed (Y) when the last agent tried this." Example: for a new `/api/cooperatives/*` endpoint, look up both the last successful cooperative endpoint AND the last ghost/failed one — the diff tells you which pitfalls to avoid. If no failure example exists, proceed with the success pattern only.
- **MCE crossover: per-step knowledge scan** (heuristic retrieval + sub-task isolation): Before starting EACH STEP (not just the task), check knowledge.md for rules matching that step's domain keyword — "ORM", "route", "seed", "service", "test". Task-level scans miss rules that are only relevant at a specific step. One grep per step, 10 seconds — prevents rediscovering known failure modes mid-implementation. (Source: MAST FM-2.6 reasoning-action mismatch — agents apply reasoning from task start but miss step-specific constraints)
- **MCE crossover: pre-step dual-grep** (per-step knowledge scan + stale spec detection): Run BOTH in one pass before each step: (a) grep knowledge.md for this step's domain keywords, (b) grep codebase for any class/function/path names explicitly named in this step's description in current_task.md. Same 10-second time cost as one grep — prevents knowledge drift AND stale spec bugs simultaneously. (Source: MCE synthesis — sessions #267-#268 stale spec missed because stale-spec check was only applied at task-start, not each step)
- **Explicit architecture decisions** (anti-vibe-architecting, arxiv 2604.04990): Before creating any new ORM model, route shape, or service boundary: add `ARCH DECISION: [what] — [why]` to current_task.md. Prompt wording alone produces structurally different systems — making decisions explicit forces deliberate reasoning and leaves a breadcrumb for future sessions.
- **Candidate approach selection** (LensAgent, arxiv 2604.03691): Before implementing any new service or endpoint, mentally generate 2 alternative approaches — e.g., (A) compose existing services and (B) write from scratch. Pick the one with fewer new functions and simpler data flow. One sentence in current_task.md: "Approach: [A or B] because [reason]." Prevents anchoring to the first idea and catches simpler paths.
- Check `.autoagent/memory/knowledge.md` for existing patterns before reading source files
- Read only the files you need — don't explore the whole codebase
- Start coding immediately if the task is already defined — don't re-research
- Write tests alongside the feature — one test per branch minimum
- **Test after each function, not after all code**: Run tests after completing each service function or route handler, not after writing everything. Scaffold-level test gating (lint-test after each step) is the primary reliability lever — prompt-level instructions alone change outcomes by at most 2.6pp (arxiv 2604.03515). **Per-step non-regression**: note the test count BEFORE your step; after running tests, verify count_after >= count_before. If count dropped mid-session, a test was silently deleted or broken — treat as BLOCKER before continuing. Don't wait for the final STEP 1 gate to catch this. (MCE crossover: test-gating per step + AgentDevel non-regression gate → apply the non-regression check at step granularity, not just session-end.)
- Run the test command from `.autoagent/PROJECT.md`
- Fix ALL failures before committing — never commit red tests
- If a skill file exists for your task type, read it first

## WHEN COMPOSING EXISTING SERVICES
When a feature combines multiple existing services (e.g. health scoring uses NDVI + soil):
- **Read the existing service files first** — know their function signatures and return types before writing the composition layer
- **Import and call existing functions** — never re-implement logic that already exists in another service
- **Handle missing inputs gracefully** — not all data sources will exist for every field. Design for partial data from day one (see relevant skill file for degradation rules)
- **Test the composition** — test with all inputs present AND with each input missing individually

## SKILL_LIBRARY — progressive chaining
After each successfully completed subtask, emit a skill tag (in current_task.md or a comment) with three components:
```
SKILL: [name] — [one-sentence description of what worked]
  WHEN: [activation condition — what task/state triggers this skill]
  DONE: [termination condition — how you know this skill's work is complete]
```
On the next subtask, scan these tags before starting. If a relevant skill exists, match on WHEN condition first — reuse its pattern exactly instead of re-deriving it. Accumulated skill tags reduce context tokens by avoiding redundant exploration.
Examples:
- `SKILL: add-pure-function — pure function takes DataFrames in, returns dict with typed fields`
  `WHEN: new data processing/computation service needed`
  `DONE: function returns typed dict, unit test with golden values passes`
- `SKILL: add-knowledge-base — ORM model + seeds.py + Pydantic schema + API route + autouse fixture`
  `WHEN: new reference data set with seed records needed`
  `DONE: GET endpoint returns seeded data, filter params work, 4+ tests pass`

## TASK ROUTING — classify before acting
Before starting any task, classify it:
- **Single-step** (rename, one-line fix, single file edit): act immediately — skip planning, skip skill reads
- **Multi-file** (new feature, new endpoint + model + frontend): write current_task.md plan first, then build
- **Open-ended** (debug with unknown cause, "find what adds value"): explore first, narrow scope, then act
This prevents wasted planning turns on trivial changes and prevents unplanned execution on complex ones.

**Plan granularity guard**: Plans should have 5-8 abstract steps, not 15+ micro-steps. Each step should describe WHAT to accomplish, not HOW to do it line-by-line. Over-detailed plans anchor you to a specific implementation path and make replanning harder. If a step feels like pseudocode, it's too detailed — elevate it.

## SESSION INVARIANTS — conditions that must hold at ALL times
Re-check these before EVERY tool call that modifies files (Edit, Write, Bash with git/mv/rm):
1. Am I still working on the ONE task from current_task.md? (If not → stop, log the distraction to backlog)
2. Am I about to modify a file outside my task scope? (If yes → pause, verify it's necessary)
3. Have I introduced any `import` that violates the dependency direction? (api → services → utils, never backwards)
4. **Reasoning-execution alignment** (binary check before each file edit):
   - Grep current_task.md for file path you're about to edit:
     ```
     grep -E "(src|api|frontend|tests)/" memory/current_task.md | grep "<file_path>"
     ```
   - If match found → proceed.
   - If no match → STOP. Either update current_task.md to list the file, or re-read step and ask if edit is truly needed.

## IF NO RELEVANT SKILL EXISTS
Create `.autoagent/skills/[tasktype].md` with rules you discover while working.
Example: if you hit a tricky database migration pattern, write `skills/database.md`.

**Skill design principles**:
- Encode decision rules and patterns, NOT code templates. Concrete templates degrade performance.
- Only create skills for genuine capability gaps (specialized domain formulas, niche API patterns).
- Keep SKILL.md under 500 lines. Read only ONE skill per task. Never load multiple simultaneously.
- Match specificity to fragility — high freedom for context-dependent tasks, low freedom for fragile operations.
- **Minimize functional overlap** between skill files. If a human can't definitively choose between two skills for a task, neither can the agent. Overlapping skills create ambiguous decision points and waste context loading both. When two skills cover similar ground, merge them or sharpen their WHEN conditions until they're non-overlapping. (Source: Anthropic context engineering guide — "curating a minimal viable set improves context management")

## IF CURRENT TASK APPEARS ALREADY DONE
If current_task.md has steps but all work looks complete (tests pass, code is committed):
1. Verify with `git log --oneline -5` that the work was actually committed
2. Clear current_task.md (overwrite with `# No current task`)
3. IMMEDIATELY pick the next unchecked task from backlog.md — do NOT exit or log "no action needed"
4. Never spend a session just confirming something was already done — that wastes a full context window

**ZERO TOLERANCE FOR EMPTY SESSIONS**: If you find the current task is already done, you MUST pick and START the next task in the same session. "No action needed" is never a valid session outcome. The session ends when new code is committed or a concrete investigation is logged.


<!-- ==== CONTEXT ==== -->

# AutoAgent — Context (summary, memory stratification, compression, admission)

Context discipline sits alongside the step-by-step flow in `PROMPT-WORK.md`. Read this when context is filling, when writing to memory files, or at compaction checkpoints.

## CONTEXT_SUMMARY gate
When your context is more than half full (many tool calls made, long file reads completed), emit this block before continuing:
```
CONTEXT_SUMMARY:
- Decisions made: [bullet list]
- Current state: [one sentence]
- Next step: [specific next action]
- Context budget: [high/medium/low] remaining
```
This lets the session continue cleanly from a /compact or new window.

## Checkpoint at milestones
Every ~15 tool calls OR when a milestone is reached (passing test, completed function, working endpoint), write key findings to current_task.md: what was built, what changed, what the next step needs. Rely on checkpoint notes instead of re-reading raw exploration. Target: 5-11 checkpoint entries per 100 tool calls — agents at this density significantly outperform minimal-note agents (YC-Bench 2604.01212). **Budget-aware density**: When budget <30%, increase to 8-11 checkpoints per 100 calls — higher density near exhaustion means cleaner compaction recovery. (MCE crossover: budget-aware exploration + checkpoint density)

## Context budget
When context is running low:
1. current_task.md = always keep full
2. last 2-3 tool outputs = keep verbatim
3. older outputs = first compaction candidates

Compact AFTER completing a milestone, never during active debugging. Trigger compaction when context exceeds ~70%.

## Memory stratification — which file to use for what (arxiv 2604.08224)
- current_task.md = working context (in-flight task state, step checklist) — always full, never truncated
- activity_log.md = episodic memory (what happened each session) — append, compress old entries when long
- knowledge.md = semantic memory (rules, patterns, lessons) — append only, never overwrite, RULE entries survive forever
- backlog.md / done.md = operational queue — mutable, lean; done.md is the permanent record

Write to the RIGHT store, not the convenient one. A rule goes in knowledge.md, not activity_log.

## Periodic plan reminder (arxiv 2604.12147 — *From Plan to Action*, 16,991 trajectories)
Every ~15 tool calls, re-read current_task.md to refresh the plan in working memory. Without periodic reminders, agents revert to internalized training workflows and deviate from the stated plan. Suboptimal plans actively HARM more than no plan — so if the plan feels wrong, update it in current_task.md first, then continue. Combines with session invariant #4 (reasoning-execution alignment, see `PROMPT-WORK.md`) — the invariant checks per-action alignment, this rule refreshes the full plan periodically so the invariant check has accurate context.

## Sub-task isolation
After checking off a step, write a 2-3 line checkpoint, then treat the next step as fresh — only carry forward the checkpoint note and current_task.md, not intermediate reasoning or file contents.

## Structural waste
Tool results older than 15 turns are the first eviction candidates. If re-requesting removed content, pin the key facts to current_task.md. Prefer graduated degradation over hard failure when context is tight.

## Compression paradox (arxiv 2604.07502 — *Beyond Human-Readable*)
Compression is REDUCTION by EVICTION, not ABBREVIATION. Dropping old tool outputs entirely is cheap; rewriting them into terse/abbreviated codes is NOT — the model spends reasoning tokens decoding the abbreviations on every subsequent turn. Measured effect: 17.1% input-token reduction via log compression → **67.2% net session cost increase** because session-to-file ratio grew from 2.3× to 4.7×. Rule: when compacting, DELETE old content and pin a 1-2 line checkpoint to current_task.md. Never paraphrase a tool output into a shorter-but-obscure form. Input-token count is the wrong metric — total session cost is the right metric. (MCE crossover: sawtooth compression + this rule → compaction = eviction + pinned checkpoint, never inline rewriting.)

## KNOWLEDGE SEARCH — prefer FTS over tail-read

`knowledge.md` is the source of truth, but tailing its last 1500 chars at session start only surfaces the most recent rules. For looking up prior experience on a specific topic (e.g. "pydantic", "orphan adoption", "ORM seed"), use the SQLite FTS5 index:

```bash
.autoagent/scripts/knowledge.sh search "<topic>" [N]     # top N matches, default 5
.autoagent/scripts/knowledge.sh recent [N]               # most recent N rules
.autoagent/scripts/knowledge.sh add "<rule text>" [source]   # append to both md + db
.autoagent/scripts/knowledge.sh rebuild                  # reindex from knowledge.md
```

The DB rebuilds automatically on first use and whenever `knowledge.md` mtime > `knowledge.db` mtime, so manual rebuild is rarely needed. When admitting a new RULE (see below), `.autoagent/scripts/knowledge.sh add` writes to both stores atomically — do not write to only one.

## RULE ADMISSION (knowledge.md gate)

Rule admitted if ≥3 true:

**Objective checks:**
- [ ] References specific file path, function name, or test name
- [ ] Started from documented failure in activity_log (not speculation)
- [ ] Applied in ≥2 sessions with contrastive evidence (before=fail, after=pass)

**Judgment checks:**
- [ ] Next session will reference this WHEN condition
- [ ] More specific than existing rules
- [ ] Useful beyond this one task

**ADMIT example:**
`RULE: [date] When adding Pydantic model, run pytest tests/test_openapi_docs.py before commit — missing router tag 500's the endpoint`

**SKIP examples:**
- "Debugging is easier with breaks" — no WHEN, no verification
- "Keep code clean" — generic advice
- "Session #N took 2hrs because distracted" — anecdote

## Memory pruning protocol (arxiv 2505.16067)
Indiscriminate add-all DEGRADES agent performance; smaller curated memory consistently beats larger noisy collections. Every 50 sessions (or when knowledge.md exceeds 400 lines), META sessions should:
- remove RULE entries older than 30 sessions that haven't been triggered/referenced
- merge near-duplicate rules into single consolidated entries
- archive superseded rules to a `knowledge_archive.md` rather than deleting

History-based deletion: rules that have been read 5+ times but never prevented a failure are candidates for removal.

**CRITICAL: APPEND rules, never overwrite existing ones. Each new rule gets a date. Rewriting old rules silently destroys accumulated reasoning — structured incremental updates are the only safe pattern.**


<!-- ==== FAILURE ==== -->

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


<!-- ==== VERIFICATION ==== -->

# AutoAgent — Verification (commit gates, self-critique, audit, logging)

After task steps complete (see `PROMPT-WORK.md`), this file governs. No commit bypasses this.

## AFTER COMPLETING ANY TASK — GATE: DO NOT COMMIT UNTIL ALL PASS

### STEP 0 — Self-critique + draft reflexion RULE (before running tests)
**Scaling rule** (validated by arxiv 2604.07236 — structural mechanisms yield more than continuous self-critique; conditional revision at ~5% of turns is optimal):
- **Full self-critique**: Multi-file changes, new services, composition — all 4 checks below
- **Light self-critique**: Single-file, <20 lines — checks 1 and 3 only
- **Skip**: Config-only, documentation, backlog/log updates
Use exactly ONE self-correction strategy per pass. For already-optimized code, skip self-correction and trust the tests. Checklists, gates, and file-based checkpoints carry more weight than continuous LLM self-critique — invest in structural verification, not more critique rounds.

Re-read the 3 most-changed functions/sections you just wrote. Ask:
1. Does this match what was intended? (compare to current_task.md step description)
2. Is there an obvious edge case I missed?
3. Did I wire all return values through? (model field → route → frontend)
4. **Global consistency check**: Does what I just built invalidate any remaining steps in current_task.md? If yes, update the plan before continuing.
Each check above is pass/fail independently — ALL must pass before proceeding.
Fix anything found BEFORE running tests. This catches a class of bugs that tests miss.
Skip only if: zero Python code was changed this session.

**IMMEDIATELY after self-critique, write your reflexion RULE into knowledge.md** — do this NOW, before tests, before commit. If the session runs out of context later, the rule is already saved. The full reflexion (ACCOMPLISHED/FAILED/RULE) can be completed in Step 4, but the RULE line must be captured here. Format: `RULE: [2026-MM-DD] [concrete rule learned]`. Apply the admission checklist in `PROMPT-CONTEXT.md` before writing.

**Self-check before passing output to the next step**: Before any output that feeds into a subsequent tool call or step, verify:
- Does it match the expected format for the next step?
- Any claims you are uncertain about? If yes, mark with `UNCERTAIN:` and verify before continuing.
- Does it contradict anything established earlier in this session? If yes, resolve the conflict first.

**Tool output validation before chaining**: Before using the result of any tool call as input to the next step, verify it's what you expected — e.g., confirm a file was written by reading it back, confirm a test passed by checking the exit code, confirm a route exists by grepping for it. Never silently chain: "write code" → "run tests" without verifying the write succeeded. One unverified bad output propagates through all subsequent steps and produces confusing failures.

### STEP 0.5 — Multi-disciplinary audit (if `.autoagent/skills/audit.md` exists)
Read `.autoagent/skills/audit.md` and run every checklist against the files changed this session.
Fix all issues before proceeding. Log anything too large to fix now to `.autoagent/memory/tech_debt.md`.
Skip only if: zero files were changed this session.

### STEP 1 — Run tests (ALL session types that touched code)
Run the test command defined in `.autoagent/PROJECT.md`.
- If ANY test fails: fix it before proceeding. Never commit red tests.
- Record: count before, count after, status (pass/fail/skip)
- **Non-regression gate** (AgentDevel flip-centered gating): If count_after < count_before, STOP — a previously-passing test was deleted or broken. Treat a test count drop as a BLOCKER equivalent to a failing test. Find what disappeared before committing. A feature that gains 5 tests but loses 3 is net -3 coverage, not net +2. (Source: AgentDevel arxiv 2601.04620 — pass→fail regressions are first-class failures)
- **Immediately after tests pass**: write the new count to `knowledge.md` test suite history table (step 9). Do it NOW while the count is in front of you — not at the end of the session when context is low.

### STEP 2 — Run frontend check (WORK sessions only)
Read `.autoagent/skills/playwright.md` and follow it exactly.
- If server not running or Playwright not installed: status=skip, note the reason, continue.
- If checks fail: fix the issue before committing. A broken UI ships nothing.
- Record: checks count, failures count, notes

### STEP 2.5 — Emit verification report before committing
After STEP 1 and STEP 2 complete, emit this block explicitly. Do not commit without it:
```
VERIFICATION REPORT:
- Import check: PASS / FAIL
- Tests: PASS (N passed) / FAIL (N failed)
- Frontend: PASS / SKIP (reason) / FAIL
- Audit: PASS / FAIL (blocking issue: ...)
TDD: YES
  Commit 1 (tests): [hash] — X tests failed
  Commit 2 (impl):  [hash] — X tests passed
READY TO COMMIT: YES / NO
```
This makes the gate state explicit and checkable. A "NO" on any line blocks the commit. The TDD lines come from the two-commit proof flow in `PROMPT-WORK.md` step 6 and `skills/quality-standards.md`.

### STEP 3 — Only after both gates pass, commit and push
Use git commands as configured. For two-repo projects, check `.autoagent/PROJECT.md` for repo paths and commit prefixes.

For feature tasks, the TDD two-commit proof (`test:` then `feat:`, see `PROMPT-WORK.md` step 6 and `skills/quality-standards.md:9-34`) is the default form. META sessions verify via `git log` that both commits exist and that Commit 1 was red-before-green.

**COMMIT REMINDERS** (re-read at every commit):
- ❗ NEVER `git add autoagent/` from project root — it is in .gitignore and will fail
- ❗ Use the project's configured Python command (`python3` on the Linux/macOS runner)
- ❗ Commit to the project's default branch from PROJECT.md — never assume a branch name
- ❗ Clear current_task.md IMMEDIATELY after push (not after logging)

0. **WAL marker — write PENDING log entry BEFORE the project commit** (ghost-commit prevention). Append to `.autoagent/memory/activity_log.md`:
   ```
   ## [DATE] — SESSION #N — [WORK/META/BRAIN] — PENDING
   DONE: [task name] — [test count] tests.
   FILES: [comma-separated list]
   COMMIT: (pending)
   ```
   This is a write-ahead log marker: the entry exists on disk BEFORE `git commit` runs. If the session crashes between the marker and the commit, the next session sees PENDING + no matching commit and knows to investigate. If it crashes AFTER the commit but before SHA-finalization, the next session sees PENDING + a matching commit in `git log` and trivially backfills the SHA. Either way, ghost commits become attributable in one grep. Source: BRAIN session 2026-04-12 — 6+ ghost-commit incidents (#294, #296, #297, #363, #369, #371, #386-24d548d) all fit the same pattern of crash between `git push` and the MINIMUM VIABLE LOG write. The autoagent repo is untouched at this step — the marker is a local-file write only.
1. Add changed project files (never include `autoagent/` in the project repo — it is in .gitignore)
2. Commit with the prefix defined in PROJECT.md (e.g. `agent: <what> — <why>`). The TDD two-commit proof (`test: …` then `feat: …`) is the default form for feature tasks — see `PROMPT-WORK.md` step 6.
3. Push to the branch defined in PROJECT.md
4. For autoagent changes: commit to the autoagent repo with its own prefix (e.g. `meta: <what>`)
4.5. **Overwrite `.autoagent/memory/current_task.md` with `# No current task`** — do this IMMEDIATELY after push, before logging. Skipping this step causes the next session to waste time re-verifying already-committed work.
4.55. **Finalize the WAL marker** — replace `PENDING` with the session type and `(pending)` with the commit SHA on the entry written in step 0. One Edit call. The entry is now a proper log line.
4.6. **MINIMUM VIABLE LOG** (required immediately after step 4.55, even at <5% context budget):
Append to `.autoagent/memory/activity_log.md`:
```
## [DATE] — SESSION #N — [WORK/META/BRAIN]
DONE: [task name] — [test count] tests total.
IMPACT: [one phrase]
FILES: [comma-separated list]
```
Also append to knowledge.md test table: `| [date] | [count] | [task name #session] |`
These two writes (30 seconds total) prevent the activity_log gap. Evidence: sessions #307-#314 all committed code but had zero activity_log entries — this is the fix. Full sessions.json + done.md + reflexion can be done in STEP 4 if context remains.

**❗ SESSION COMPLETE GATE** (immediately after step 4.6): The session is now OVER. The only remaining allowed actions are step 5 and STEP 4 below (backlog/done.md/sessions.json). You MUST NOT open `backlog.md` to pick another task. You MUST NOT start a new feature. If you have context remaining after STEP 4, stop — do not use it. Evidence: sessions #317-#321 picked second tasks after first commit, exhausted context, and produced zero log entries. The second task always loses the logging budget.

5. Update `.autoagent/memory/backlog.md` — **REMOVE** the completed task entirely (do NOT leave it with [x])
   Then append one line to `.autoagent/memory/done.md` under today's date:
   `- **[SESSION #N] Task name** — one sentence of what was built`
   Backlog stays lean. done.md is the permanent record.

Also: remove your active_claims.md line after commit+push (see `PROMPT-RECOVERY.md`).

### STEP 4 — Log the session
6. Append to `.autoagent/sessions.json` — one entry per session:
   ```json
   {"session": N, "date": "YYYY-MM-DD", "time": "HH:MM", "type": "work|meta|brain",
    "summary": "ONE sentence, plain English, what changed and why it matters to users",
    "files": ["list", "of", "changed", "files"],
    "tests": {"before": N, "after": N, "status": "pass|fail|skip"},
    "frontend": {"status": "pass|fail|skip", "checks": N, "failures": 0, "notes": ""}}
   ```
   Summary must be plain English — e.g. "Added backtesting page so traders can see historical win rates per pattern"
   NOT technical jargon — write it like you're telling a non-developer what changed
7. Write to `.autoagent/memory/activity_log.md` — FORMAT IS MANDATORY:
   ```
   ## [DATE TIME] — SESSION #N — [TASK TYPE]
   DONE: [what you built in one sentence]
   IMPACT: [why it matters]
   FILES: [files changed]
   ```
   Include the session number for cross-referencing with done.md and sessions.json.
   CORRECT EXAMPLE:
   ```
   ## 2026-03-19 14:32 — SESSION #42 — FEATURE
   DONE: Added earnings proximity chip to signal cards — red "Earn in Xd" badge appears when earnings are within 21 days.
   IMPACT: Traders see the earnings risk at the point of decision instead of getting a mystery score penalty.
   FILES: models/signals.py, routes/dashboard.py, frontend/app.js, frontend/styles.css
   ```
   WRONG (never do this):
   ```
   ## 2026-03-19 14:32 — FEATURE [vscode]
   **Added earnings chip**
   Output tail:
   PASSED 881 tests
   ```
   For error/empty sessions, still write: `DONE: No work completed — [reason]. Next: [next backlog task].`
   Never write "Output tail:" or raw CLI output — that format is unreadable.
8. Write a session reflexion in `.autoagent/memory/knowledge.md` under `### Session #N Reflexion — [DATE]`:
   - ACCOMPLISHED: what you built
   - FAILED: what broke or required retry, and why
   - OPTIMIZATION: one thing that worked but could be faster/cleaner next time (optional — only if genuine, not hypothetical)
   - RULE: one concrete rule learned (even if nothing failed — confirm what worked)
   Apply the RULE ADMISSION checklist in `PROMPT-CONTEXT.md` before writing. If a rule fails admission, do NOT write it — it adds context bloat without value.
9. **MANDATORY**: Update `.autoagent/memory/knowledge.md` test suite history table with new test count.
   Format: `| YYYY-MM-DD | N | Task name (#session) |`
   Use the test count from STEP 1 — run `grep "passed" <test output>` if you've lost it.
   **This step is skipped most often when context is low. Do it immediately after STEP 1 passes, before STEP 2.**

## CONFIG / IMPORT RULES
- Before referencing any config variable (e.g. `cfg_live`, `settings.X`), grep for its definition in the codebase
- If you add a variable that doesn't exist yet, also add it to `config.py` with a default value
- Never assume a name is defined — always verify with grep first

## API KEY PROTOCOL
If a feature needs an API key that isn't set:
1. Implement it anyway using `os.getenv("KEY_NAME")`
2. **MANDATORY: update `.autoagent/KEYS_NEEDED.md`** — add a row to the table:
   `| Service | KEY_NAME | ❌ | where to get it | what it unlocks |`
3. **MANDATORY: add a line to `sessions.json` notes field** — e.g. `"notes": "Needs NEW_API_KEY to activate this feature"`
4. Never stop or ask. User fills it in, feature activates automatically.

This applies to EVERY new key. If you built it and it needs a key, the user must be able to see it in KEYS_NEEDED.md immediately.

## WHAT "DONE" MEANS
A task is done when ALL of the following are true — in this order:
1. Feature works as intended
2. Tests pass (run the test command from `.autoagent/PROJECT.md`) — exits 0
3. Frontend check run (or skipped with documented reason) — BEFORE commit
4. Code is committed and pushed
5. sessions.json updated with test + frontend results
6. activity_log.md updated
7. current_task.md cleared (overwrite with `# No current task`)

**COMMIT ORDER IS MANDATORY: tests → frontend → commit. Never commit then check.**
