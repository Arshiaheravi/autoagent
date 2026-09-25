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
