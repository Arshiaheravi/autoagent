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

**Orphan intelligence sweep** (MANDATORY, 10 seconds): Scan `git status --short` for untracked files matching `src/<yourapp>/services/intelligence/*.py`, `src/<yourapp>/models/*.py`, or `tests/test_*.py`, AND unstaged modified files under `src/<yourapp>/api/*.py`. If ANY exist and no matching current_task.md entry covers them: this is an orphan ghost from a crashed concurrent/prior session. ADOPT IT (per rule above).

## GHOST COMMIT DETECTION

Run `git log --oneline -3` and check if the latest commit(s) appear in `activity_log.md`. If a commit exists with the `agent:` prefix but has NO matching session log entry: the previous session committed but crashed before logging. Backfill the missing log entries (activity_log, sessions.json, done.md), remove the completed task from backlog, and update NORTH_STAR test count — then continue.

**WAL marker fast-path**: Also grep `activity_log.md` for `PENDING` (write-ahead markers from the commit step in `PROMPT-VERIFICATION.md`). If a PENDING entry exists: (a) if a matching commit is in `git log`, finalize the marker (replace PENDING with the session type, write the SHA) — this is a ~2 tool call backfill, no guessing from the commit stat. (b) If no matching commit, the prior session crashed BEFORE committing — delete the PENDING line, treat it as an abandoned attempt, and continue. The marker eliminates ghost-commit backfill guesswork: files, tests, and task name are already in the entry.

**Cross-reference check**: When activity_log shows the most recent session as "done", verify the git log HEAD message MATCHES that session's task description. If HEAD message describes a DIFFERENT task than the activity_log "done" entry, the log was backfilled optimistically — the committed work may be a different feature and you may be about to duplicate it. Run `git diff HEAD~1 HEAD --name-only` to see exactly what the last commit changed before picking the next task. (Source: session #269 — duplicated WhatsApp simulator that was already committed)

## CONCURRENT SESSION GUARD (run before claiming any backlog task)

MANDATORY, 15 seconds. Before committing to a task, run BOTH:
(a) `cat .autoagent/memory/active_claims.md` — shows tasks other running sessions have claimed
(b) `git -C <project> log --since="15 minutes ago" --pretty=format:"%h %s"` — recent commits by other sessions
If your target task_id OR any keyword from the backlog description OR your planned primary edit-file appears in EITHER output → PIVOT to the next backlog task that touches DISJOINT files. Do not edit a file another session is actively modifying. Once you pick your task, IMMEDIATELY append to `.autoagent/memory/active_claims.md`:
`SESSION #N | TASK #M | started YYYY-MM-DDTHH:MM | files: src/<yourapp>/api/X.py, services/intelligence/Y.py`
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
