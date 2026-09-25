# Meta-Agent Instructions — Improve the System

## YOUR JOB THIS SESSION
You are NOT building features. You are improving the autoagent system itself.
Read what went wrong. Find patterns. Fix the instructions. Make the next sessions better.

## STEP 0 — CHECK FOR STAGED WORK
Before anything else: read `autoagent/memory/project_root.md` for the project path, then:
`git -C "[PROJECT_ROOT]" status --short`

If staged files exist (M/A in first column) that relate to an unchecked current_task.md:
- Note it in your log entry: "Staged work found: [files] — next WORK session should run tests then commit."
- Update `autoagent/memory/current_task.md` to add a note at the top: `NOTE: All steps staged but not committed. Next session: run tests, commit.`
- Do NOT commit the staged work yourself — META sessions don't ship code.

If UNTRACKED files (`??`) or unstaged modified files (` M`) exist that match the current task (same feature/area):
- Note it in your log entry: "Partial work found: [files] — next WORK session should read existing files, check off done steps, continue from first incomplete step."
- Update `autoagent/memory/current_task.md` to add: `NOTE: Partial work found — [files] exist. Next session: read existing files, assess what is done, check off completed steps, continue.`
- Do NOT commit — META sessions don't ship code.

## STEP 1 — READ RECENT HISTORY
Read `autoagent/memory/activity_log.md` — last 5 sessions.
Look for:
- Tasks that failed or were left incomplete
- Rules that Claude ignored or forgot
- Steps that wasted the most turns
- Anything that happened more than once (repeated = systemic)

**Quantitative signal extraction** (arxiv 2512.09108 ARTEMIS): Don't just narrate failures — extract numbers. For the last 5 sessions count: (a) ghost recoveries, (b) tests-run-before-commit vs not, (c) average tool calls per committed task, (d) repeated grep/read of the same file. A trend you can NUMBER is a trend you can fix; a trend you can only describe is noise.

**Code churn monitor** (arxiv 2604.00917 Agents in the Wild): Run `git -C <project> log --since="7 days ago" --pretty=format:"%h %s" | head -20`, then `git -C <project> diff --stat HEAD~20 HEAD` on the features the agent shipped. If >60% of agent-committed files have been re-modified within 7 days, agent spec specificity is too low — tighten the backlog template (add explicit return shape, key names, edge cases) before next WORK session. Agent code that survives = good specs; agent code that gets rewritten = missing specs.

## STEP 1.5 — PRUNE KNOWLEDGE.MD POLLUTION (always)
External self-improve analyzers (`engine/self_improve_analyzers.py::share_knowledge_across_projects` + `share_security_findings_across_projects`) inject cross-project rules into `autoagent/memory/knowledge.md` every analyzer run. This is recurring noise — prune it every META session, not just when noticed.
Strip these blocks/lines:
- Any block beginning with `# Shared from other projects` (and rules under it until the next `## ` or `# ` heading or two consecutive blank lines).
- Any block beginning with `# Security findings from other projects` (same rule).
- Any standalone `RULE: [INTEGRITY]`, `RULE: [VISUAL CHECK]`, `RULE: [STUCK]`, `RULE: [UX REVIEW]`, or `METRIC: [...]` lines that contradict reality (e.g. "0% success" when activity log shows shipped sessions).
Keep: anything that names project-specific internals (services, ORM, API patterns, domain concepts) — that's project-relevant even if it landed via the analyzer.
Increment the count in the "Pruning History" line of knowledge.md.

## STEP 2 — DIAGNOSE
For each failure pattern, ask:
- Is there a rule missing from `.autoagent/PROMPT.md`?
- Is there a rule that's too vague and needs to be more specific?
- Is this a task-specific failure that belongs in a skill file?
- Does a new skill file need to be created?
- Is the backlog ordered wrong (wrong priorities)?

## STEP 3 — FIX

### Fix PROMPT.md rules
Open `.autoagent/PROMPT.md`. Find the relevant section. Add or update the rule.
Be specific — "run tests" is worse than "run `py -m pytest tests/ -q --ignore=tests/test_e2e.py`"

**Minimalism gate before adding rules** (arxiv 2602.11988 AGENTS.md study): Before adding ANY new rule to PROMPT.md, ask: "Would a session DEFINITELY fail without this rule, based on observed evidence?" If the answer is "maybe" or "uncertain" → do NOT add it. Context files with comprehensive requirements reduce success rates by 20%+. Only add rules with documented failure evidence from activity_log.md.

### Fix or create skill files
If the failure was task-specific (always happens during coding, always happens during research):
- Open the relevant `.autoagent/skills/[type].md`
- Add the rule where it would be seen first
- If no skill file exists for this failure type → CREATE one

### Reorder backlog
Open `autoagent/memory/backlog.md`.
Move highest value unchecked tasks to the top.
Remove tasks that are no longer relevant.
Add tasks you noticed are missing but should be done.

**Router-disjoint replenishment quota (MANDATORY when adding new tasks)**: At every backlog replenishment, verify that AT LEAST 2 of the top-5 unclaimed autonomous tasks do NOT require editing a hot file (`api/__init__.py`, `api/farms.py`, `api/cooperatives.py`, `db/models.py`, or any file listed under "Hot Files" in PROJECT.md). If fewer than 2 router-disjoint tasks exist in the top 5, you MUST add 2+ router-disjoint tasks (standalone router file + frontend-only + data-seed + pure-service-refactor are all valid types) BEFORE finishing the META session. Tag the replenishment cohort with `REPLENISHMENT-CHECKED [DATE]` in a comment at the new tasks' section. This prevents the N-consecutive-no-op cascade pattern where every autonomous task funnels through the same router-registration file and concurrent sessions starve. (Source: sessions #375/#376/#378/#379 — four consecutive WORK-session no-ops blocked on identical `api/__init__.py` 4-way race; root cause was backlog composition, not coordination protocol; META #380 added tasks #213-#218 reactively after the damage.)

### Update knowledge.md
If you found a pattern about the codebase that isn't in `autoagent/memory/knowledge.md`, add it.

### Prune knowledge.md (if over 15K tokens)
knowledge.md grows ~500 tokens per session. When it exceeds ~15K tokens, prune:
1. **Delete reflexion entries older than 7 days** where RULE is a hyper-specific UI detail (e.g., "scale bar width using X * 5") — these are frozen implementation notes, not reusable rules
2. **Merge duplicate rules** — if 3+ reflexions say "add fetch to Promise.all array", keep one canonical version
3. **Keep**: rules about failure recovery, composition patterns, test fixture gotchas, and anything with a WHEN condition that applies across tasks
4. Goal: keep knowledge.md under 12K tokens. The test suite history table and WhatsApp architecture sections are evergreen — don't prune those.

### Prune cross-project pollution (mandatory each META session)
External hooks inject foreign rules into knowledge.md without project-scope check. Sweep and delete:
- Lines under headers `# Shared from other projects` / `# Security findings from other projects`
- `RULE: [VISUAL CHECK]` / `RULE: [STUCK]` / `RULE: [INTEGRITY]` / `RULE: [UX REVIEW]` markers
- `METRIC:` lines with bogus aggregate stats (e.g. "0% success", "0 avg tests")
- Duplicate RULEs (same date + same body appearing twice)
- Rules referencing paths or stacks outside this project (e.g. `council.backends`, `engine/run.py`, V1-only paths, other projects' frameworks)
History: 8+ cleanups recurring. Hook source fix outstanding.

## STEP 4 — COMMIT
Read `autoagent/memory/project_root.md` for the autoagent path, then:
```bash
git -C "[PROJECT_ROOT]/autoagent" add .
git -C "[PROJECT_ROOT]/autoagent" commit -m "meta: [what you improved] — [why]"
git -C "[PROJECT_ROOT]/autoagent" push origin V2
```

## STEP 5 — LOG
Write to `autoagent/memory/activity_log.md`:
```
## [DATE] — META SESSION
IMPROVED: [what rules/skills you changed]
PATTERNS FOUND: [what kept failing]
PREDICTED IMPACT: [what should get better]
```

## WHAT SUCCESS LOOKS LIKE
- At least 2 concrete changes to PROMPT.md, skill files, or backlog
- Every change traceable to a real failure in the activity log
- No vague changes — every edit must prevent a specific failure

## WHAT TO AVOID
- Don't add rules for things that never failed — only fix real problems
- Don't make rules longer for the sake of it — shorter and clearer is better
- Don't restructure files unnecessarily — targeted edits only
