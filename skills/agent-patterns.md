# Skill: Agent Patterns (Autonomous Coding Best Practices)

**When to use**: Every session. These are the meta-rules that prevent the most common
autonomous agent failure modes. Read this alongside task-specific skills.

---

## FAILURE MODES — know these, avoid them

### 1. Kitchen Sink (most common)
**Symptom**: Start task A → get distracted by issue B → lose thread of A
**Fix**: One task per session. If you notice something unrelated, add it to backlog and stay on task.

### 2. Infinite Exploration
**Symptom**: `"investigate the scoring logic"` → reads 50 files → context full → no code written
**Fix**: Scope narrowly before exploring.
- Bad: `"investigate the services system"`
- Good: `"read services/pricing.py lines 40-80 to understand how totals are combined"`

### 3. Symptom Suppression
**Symptom**: Build fails → add `try/except` to hide error → problem returns later
**Fix**: Always fix the root cause. If you don't understand why it's failing, read the error more carefully before touching code.

### 4. Correction Loop
**Symptom**: Make a change → wrong → fix → still wrong → fix again → 3rd attempt
**Fix**: After 2 failed attempts at the same problem, stop. Re-read the relevant source files from scratch. The assumption you're working from is wrong.

### 5. Trust Without Verify
**Symptom**: Write code → looks right → mark task done → bug found next session
**Fix**: After every feature, explicitly verify: run tests, do import check, check the affected API endpoint with curl.

### 6. Over-Implementation
**Symptom**: Task says "add a field" → agent adds field + refactors the whole model + adds new tests + cleans up unrelated code
**Fix**: Do exactly what the task says. Nothing more. Log any improvements you notice to backlog instead.

### 7. Brittle Test Cascade
**Symptom**: Add a new test → existing tests break because of shared state or hard-coded counts
**Fix**: Before adding any new tests, run `grep -r "call_count\|assert.*==.*[0-9]" tests/` to find hard-coded counts. Update them preemptively.

### 8. Orphaned Task on Turn Cap
**Symptom**: Session hits the turn cap mid-task — RED test commit landed, impl done in the
working tree, but no GREEN `feat:` commit. Backlog gets marked done off the RED commit. Next
session sees "done", advances to the next item, and builds on top of uncommitted work — the
prior task's impl is stranded and its green commit never exists.
**Fix**: (1) A task is DONE only when its `feat:` commit exists — never mark done off a
red-test commit. (2) At session start, before picking a new task, check for an interrupted
one: `git status` shows uncommitted changes, or `git log` shows a `test:` commit with no
following `feat:`. If so, RESUME and finish it (green commit) before advancing. (3) If a task
is too big for one session's turns, commit a WIP checkpoint rather than leaving it uncommitted.

### 9. Silent Stdin Hang (launcher) — FIXED in code, know the shape
**Symptom**: A non-interactive launch (`nohup`/cron/nested script) blocks FOREVER on an
interactive `input()` prompt — no events, 0% CPU, total silence. Stranded a session
~1h stuck on the CLI/API mode prompt because a piped (non-EOF) stdin never satisfied `input()`.
**Fix**: `ask_mode()` now returns `cli` immediately when `sys.stdin.isatty()` is false, and
`autoagent run` parses `--cli`/`--api`. RULE for any new interactive prompt: guard it with an
`isatty()` check + a flag override + an `EOFError` fallback. Never let a detached process block
on `input()`.

---

## PLANNING — use before multi-file changes

Before touching code on any task that changes 3+ files:
1. Write a plan in `autoagent/memory/current_task.md` FIRST
2. List: which files change, what changes in each, what tests verify it
3. Ask yourself: "Is there a simpler way that changes fewer files?"

Example plan:
```
# Current Task: Add order-total aggregate service
Files changing:
- services/pricing.py — pure computation function
- models/order.py — Pydantic schemas
- db/models.py — OrderTotal ORM model
- api/orders.py — REST endpoints
- app.py — register router
Tests:
- test_orders.py — line items, tax applied last, empty order, API storage
```

---

## VERIFICATION CONTRACT — specify before coding

Before writing any feature code, state the verification criteria:
```
# Verifying [feature]:
# 1. <project test command> tests/test_feature.py → passes
# 2. python3 -c "from myapp.app import create_app; print('OK')" → OK
# 3. curl http://localhost:8000/api/items/1 → returns data
```
These become the acceptance criteria. Feature is done when all 3 pass — not when code looks right.

**Verification completeness**: After running tests, assess completeness before proceeding:
- **Complete**: All criteria pass → proceed to commit
- **Partial**: Some criteria pass, specific gap identified → fix the gap, re-verify (max 3 cycles)
- **Incomplete**: Fundamental issue (wrong approach, missing dependency) → revise plan in current_task.md
Stop conditions: criteria met, <5% improvement between retries, or 3 retry cycles exhausted → log as BLOCKED.

**Single-round reflection**: One self-critique cycle captures most of the repair value. Multi-round reflection has diminishing returns and wastes context. Do your self-critique once (PROMPT.md Step 0), fix what you find, then move to tests — don't re-critique after fixing.

---

## CONTEXT MANAGEMENT

- When you've read many files and the session is long: emit a `CONTEXT_SUMMARY` block (see PROMPT.md) before continuing
- Prioritize reading: current_task.md → relevant service file → relevant test file. Don't read files speculatively.
- If you need to investigate something unrelated to the task, add it to backlog — don't explore now
- **Goal-hint reading**: Before reading any file, state what you're looking for in one sentence (e.g. "reading pricing.py to find how totals are weighted"). This focuses attention on relevant lines and prevents absorbing entire files into context. When reading, use offset+limit to target the relevant section — don't read 500 lines when you need 20.
- **Observation masking**: Keep the last ~10 turns of reasoning/actions fully intact. Older tool outputs (file reads, test logs, error traces) are the first candidates for compaction — they become noise after the action they informed is complete. **Do NOT use LLM summarization as an alternative** — in practice it performs no better than simple masking and causes "trajectory elongation" where summarized context encourages agents to explore unproductive paths longer.
- **Multi-agent context isolation**: When delegating to subagents, give each a narrow, focused prompt. Don't dump the full conversation context — isolated subagents with tight scope outperform a single overloaded context.
- **Collapse prevention thresholds**: At 85% context utilization, collapse is imminent — stop all new exploration, checkpoint to current_task.md, and execute the emergency commit rule from PROMPT.md. At 70%, shift to build-only mode. Watch for repetition signals: if >20% of your output is recycling earlier phrases or tool calls, you are in early collapse — checkpoint immediately.

### Error Cascade
**Symptom**: Step 2 fails → fix Step 2 → Step 3 fails → fix Step 3 → Step 4 fails. Each fix addresses the symptom, not the root cause from Step 2.
**Fix**: When a second consecutive step fails, STOP fixing forward. Run `git diff` to find the first divergence from the plan. The root cause is almost always in the earliest changed code, not the latest failure. Classify the error type before fixing:
- **Memory error**: Using wrong variable/value from earlier in the session → re-read the source file
- **Planning error**: Wrong task decomposition → revise current_task.md plan
- **Action error**: Wrong tool use or API call → check the function signature
- **System error**: Cross-module coordination breakdown → check imports and interfaces
Fix the root cause first, then re-run from that point — don't patch downstream symptoms.

### Knowledge Drift
**Symptom**: knowledge.md rules say "use X pattern" but the codebase has since moved to Y → agent follows stale rule → introduces inconsistency
**Fix**: Before applying any knowledge.md rule that references a specific function, file, or pattern, grep for it to confirm it still exists. The codebase is the source of truth, not the memory.

### Stale-Read Edit Collision
**Symptom**: Read a file → do other work for 10+ tool calls → edit the file based on stale memory of its contents → edit fails or introduces conflict because the file changed (by you or another step) since you read it
**Fix**: If more than 10 tool calls have elapsed since reading a file, re-read the specific lines you intend to edit before making the change. This costs 1 extra tool call but prevents cascading edit failures that waste 5-10 tool calls to diagnose.

### Red-Flag Output
**Symptom**: A step produces unexpectedly long output (>700 tokens) or malformed/unexpected format → indicates the agent "has become confused" about the step's purpose.
**Fix**: Do NOT attempt to repair the output. Instead: (1) Re-read the step description and relevant source files. (2) Re-attempt the step from scratch with fresh context. (3) If the second attempt also produces excessive output, the step is too complex — split it into smaller atomic actions. Long outputs correlate strongly with errors; short, focused outputs are more reliable.

### Logical Context Poisoning
**Symptom**: Unrelated topics from earlier in the session bleed into current reasoning — e.g., debugging a test failure and accidentally applying a pattern from an earlier unrelated file read. Context from topically distinct steps accumulates and progressively degrades response quality.
**Fix**: When switching between distinct subtasks (e.g., from writing backend code to writing frontend code, or from debugging to implementing), mentally reset by re-reading current_task.md and the specific files for the NEW subtask. Do not carry assumptions from the previous subtask — re-derive from source.

### Failure Trajectory Elongation
**Symptom**: Session keeps going but nothing lands — tool call count climbs past 60, edits are reverted, tests keep failing. Failing attempts consume several times the resources of successful ones and produce much longer trajectories.
**Fix**: Monitor your tool call count. At 60 calls, emit CONTEXT_SUMMARY and honestly assess: "Am I making forward progress or elongating a failure?" If the last 10 tool calls produced no green tests or committed code, emergency-commit whatever works and stop. Shorter action sequences succeed more consistently — if your plan requires >80 tool calls, the scope is wrong.

### Over-Specified Planning
**Symptom**: Plan has 15+ micro-steps that read like pseudocode → first deviation from plan cascades into replanning → replanning makes alignment worse
**Fix**: Write plans at the WHAT level, not the HOW level. "Add ORM model + schema + route + tests" is one step, not four. If a plan exceeds 8 steps, you're over-decomposing — merge related steps. Over-specification anchors you to a specific implementation and makes adaptation harder when reality diverges.

---

### Premature Termination
**Symptom**: Agent decides "done" after implementing most of the task — declares success, logs the session, moves on. Unchecked steps remain in current_task.md.
**Fix**: Before EVERY commit, count the `- [ ]` items in current_task.md. If any remain, the task is NOT done. A feature that passes tests but skips its own step 5 (e.g. wiring the route into `__init__.py`) is not shippable.
**Detection**: `grep "\- \[ \]" autoagent/memory/current_task.md` — any output means you're not done.

### Partial-Effect Blind Retry
**Symptom**: Prior session crashed / timed out mid-task. New session resumes by re-running the original plan without checking what already landed. Files get double-created, commits get duplicated, ORM rows get double-inserted, or partially-written frontend pages get overwritten with fresh skeletons.
**Fix**: Before ANY re-execution of a plan from a crashed prior session: (1) diff the working tree (`git status` + `git diff --stat HEAD~3..HEAD`) to see what the prior session actually landed, (2) read current_task.md's `- [x]` checkmarks to see what the prior session thought it completed, (3) reconcile the two — if commits exist for step N, mark it done and skip; if step N is partially staged but uncommitted, finish-and-commit instead of re-implementing. Issue one compensating action (roll-forward or roll-back) per detected partial effect. Never re-execute a step whose side effect is already on disk.
**Detection**: If the first tool after recovery is "Write [file that already has content]" or "Bash: pytest [test that was already created]" — stop. Re-read git state first.

---

## RELIABILITY SELF-CHECK — four dimensions

When reviewing session quality (META sessions), evaluate the last 5 sessions across these four dimensions:
1. **Consistency**: Did sessions produce similar quality output for similar task types? Look for: unexplained variance in test counts, code patterns that diverge from established SKILLs.
2. **Robustness**: Did sessions handle unexpected states (red baseline, missing data, partial inputs) gracefully? Look for: sessions that got stuck or looped on edge cases.
3. **Predictability**: Did failures happen in foreseeable patterns? Look for: failures that could have been caught by an existing rule but weren't.
4. **Safety**: Were errors bounded in severity? Look for: sessions that introduced regressions, broke existing tests, or committed code that needed rollback.

Score each dimension pass/fail. If 2+ dimensions fail, the META session's top priority is fixing the rules that would prevent recurrence.

---

## SELF-CRITIQUE — run before every commit

After finishing an implementation but BEFORE running tests, re-read the 3 most-changed functions and ask:
1. Does this match what the task required? (compare to current_task.md)
2. Is there an obvious edge case missing? (empty list, None, zero, negative number)
3. Did I change anything I wasn't supposed to? (check git diff for unintended changes)

This 2-minute check catches many bugs before tests run.

---

## REFERENCE EXISTING PATTERNS

Before writing new code, find the existing pattern:
```bash
# Find how existing similar features are built (use the project's actual package path)
grep -r "similar_function" src/myapp/services/
grep -r "include_router" src/myapp/app.py
```
Then follow that pattern exactly. Consistency beats cleverness.
