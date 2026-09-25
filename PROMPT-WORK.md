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

## ADVISOR (Opus) — worker-advisor pair

You (Sonnet executor) have an Opus advisor at `.autoagent/scripts/advisor.sh`. Call it to get a second opinion on judgment calls. Keeps the heavy-reasoning cost small, the executor fast.

**Invocation:**
```bash
.autoagent/scripts/advisor.sh "<question>" [--context <file>]
```
Returns ≤100 words, enumerated steps. Exit 0 = response, exit 1 = empty (advisor unreachable — proceed without).

**Call advisor BEFORE:**
1. First substantive implementation of a non-trivial task (writing >30 lines across ≥2 files)
2. Changing a schema, migration, public API signature, or Pydantic model
3. Committing when the diff touches auth, billing, or data-writing paths
4. Changing approach after a failed attempt (do not loop silently)
5. Declaring the task DONE — brief verification check

**Skip advisor when:**
- Budget <20% remaining (preserve runway)
- Task is a 1-file bug fix with clear error (<10 lines changed)
- Advisor already consulted this session AND no new fact has emerged

**Pattern:**
```bash
.autoagent/scripts/advisor.sh "Task #N adds /api/treatments — should the POST validate farm_id ownership in the route or the service layer? PROJECT.md says thin routes."
```
Expected: 3-5 numbered steps. Weigh advice against your reading. Disagree if you have evidence. Log disagreement in `current_task.md` with reasoning.

All calls auto-log to `memory/advisor_log.md` for META review. Do not paraphrase the advice into other files — the log is the audit trail.

## COUNCIL (5-model debate) — for high-stakes decisions only

When advisor is not enough — strategic/architectural fork, conflicting evidence, billing/auth/data-write design where mistake cost is very high — convene the council.

**Invocation:**
```bash
.autoagent/scripts/council.sh --question "<q>" --task <TASK_ID> [--context <file>]
```

**Flow:**
1. Stage 1: 5 backends (Claude/OpenAI/Gemini/DeepSeek/Grok) each answer
2. Stage 2: anonymous peer ranking
3. Stage 3: Chairman synthesis + confidence (HIGH/MEDIUM/LOW)
4. If confidence < HIGH: debate loop — personas see draft, name remaining disagreements, re-synth. Max 3 rounds.
5. If still no HIGH: council BENCHES the task. File written to `memory/benched/<ts>_<task>.md` with full debate trace.

**Exit codes:**
- `0` → converged. Stdout = synthesis. Act on it.
- `3` → benched. Stdout = `BENCHED:<path>`. Do NOT attempt the task this session. Mark it `[BENCHED — human-in-loop]` in `backlog.md`, log to `activity_log.md`, pick the next task.

**When to use council (not advisor):**
- Changing data model / schema in a way that affects ≥3 downstream callers
- Picking between two viable architectures for a new subsystem
- Security design (auth flow, token lifetime, permission model)
- Deciding whether to refactor a module used by many callers
- Advisor returned contradictory guidance across calls this session

**When NOT to use council:**
- Routine implementation judgment (use advisor)
- Bug fixes with clear root cause
- Budget <30% remaining (council is expensive)
- You've already converged on an approach with your own reading + advisor

**Bench protocol:**
A benched task is not your problem this session. Stop, log, move on. Seb reviews `memory/benched/` and returns the task to the backlog with guidance once resolved. Do not repeatedly re-convene council on a benched task.

## EVERY SESSION — WHAT TO DO

1. Run `git diff` and `git status` first — finish any in-progress work before starting new.
   **Baseline health check**: If no in-progress work, run the test suite once before picking a task — verify green state. If tests are red, fix them before starting anything new.
   **Orphan / ghost-commit recovery runs FIRST** — see `PROMPT-RECOVERY.md` for the orphan sweep, ghost-commit detection, WAL marker fast-path, and cross-reference check. Do those steps before reading current_task.md or backlog.
2. Read `.autoagent/memory/current_task.md` — if it has unchecked `- [ ]` steps:
   - Run `git log --oneline -5` — if work is committed, clear current_task.md and go to step 3.
   - Run `git status --short` — if relevant files are STAGED (M/A in first column) but not committed, the previous session staged but crashed before commit. **Do NOT re-implement.** Skip directly to Step 8: run tests, fix failures, then commit the staged work.
   - Run `git status --short` — if relevant files are UNTRACKED (`??`) or modified (` M`) but match the task, the previous session wrote code but crashed before staging. **Do NOT re-implement.** Read the existing files first to assess what is already done, check off those steps, and continue from the first genuinely incomplete step. **If a `tests/test_*.py` file for the task is already untracked, your very next action is to RUN THE TEST COMMAND — do not read or edit anything else until you know which tests pass.**
   - **CRITICAL: Untracked ≠ committed ≠ done.** If a previous step is marked `[x]` but the corresponding files are still untracked (not in git), that step is NOT actually done — the session marked it complete without committing. Treat untracked task files as partial work: run tests → fix → stage → commit BEFORE claiming the task is complete. (Evidence: session #318 marked #175 "done" because sensor_freshness files existed untracked, but never tested or committed them.) Ghost sessions #249-#253 all crashed after writing code+tests but before running them; the fastest recovery path is test → fix → commit, not re-reading.
   - **File existence check** (MCE crossover: sub-task isolation + ghost detection): Before deciding "not started yet", grep for the files the task would create. Example: if the task says "add upcoming_treatments.py", run `ls src/<yourapp>/services/intelligence/upcoming_treatments.py 2>/dev/null`. If the file exists but isn't in git status, a previous session wrote it without staging. Treat it as UNTRACKED (above rule applies). This prevents re-implementing code that exists but hasn't been staged. (Source: sessions #267-#268 — code existed but ghost detection missed it because git status showed no changes)
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
- **Seed/data-extension consumer-test gate** (MANDATORY for any task that adds rows to an ORM seed function or extends a static reference dataset): BEFORE commit, run the test file(s) for EVERY endpoint that reads the extended table. `grep -rl "from .*db.models import .*<TableName>\|<TableName>(" src/<yourapp>/api/ src/<yourapp>/services/` to find consumers, then `pytest` their test files. The seed-task's own test (e.g. `test_X_seeds_extended.py`) only validates the seed function — it does NOT exercise the Pydantic response models that serialize the new rows. New columns or None values in new rows commonly 500 the existing read endpoints. (Source: #216 a62c0b1 added 10 ancestral seeds with `problems=None`/`crops=None` fields; `/api/knowledge/ancestral` returned 500 because the Pydantic response model declared list types; 4 tests broke; caught only 2 sessions later by #385; fixed in ghost commit 24d548d. The seed task spec missed the consumer-test step entirely.)
- **Cross-cutting assertion gate — generalization of the consumer-test gate** (MANDATORY whenever a task introduces a NEW tagged `APIRouter`, a NEW Pydantic response model, or a NEW ORM table + route pair — NOT required for pure frontend FileResponse routes which don't register in openapi). BEFORE commit, run `pytest tests/test_openapi_docs.py` (and any other `tests/test_*docs*.py`, `tests/test_*openapi*.py`, `tests/test_*routes*.py`) alongside the feature's own test file. test_openapi_docs enforces two invariants the task author usually forgets: (a) the router's `tags=["..."]` string must also appear in `src/<yourapp>/app.py openapi_tags` with a `description`, and (b) every route decorator must carry `description=` or a docstring. Both fire at full-suite time, not isolated-test time, so without this gate the new files ship red and a sibling has to hotfix. Cost of the gate: one pytest invocation (~3 s). Cost of skipping: one red-main commit + one hotfix commit + a 6-min sibling race. (Source: session #391 shipped 3ea4f23 for #207 tek-adoption without running openapi_docs; session #392 had to hotfix with bf3ce7c. Rule previously captured in knowledge.md:196 but not in PROMPT.md — promoted here 2026-04-12 BRAIN.) **MCE crossover**: this is the same shape as the seed consumer-test gate above — both say "before commit, run the cross-cutting test files that exercise your change from a dimension your feature test doesn't cover." General form: classify your change (seed / new-router / new-model / frontend-file-route), and run the matching gate. Frontend FileResponse routes are exempt from the openapi gate (knowledge.md:7) but subject to their own page-test. When in doubt, run `pytest tests/test_*docs*.py tests/test_*routes*.py -q` — it's cheap.
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
