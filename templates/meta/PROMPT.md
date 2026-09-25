# Meta-Agent Instructions — Improve the System

## YOUR JOB THIS SESSION
You are NOT building features. You are improving the autoagent system itself.
Read what went wrong. Find patterns. Fix the instructions. Make the next sessions better.

## STEP 0 — CHECK FOR STAGED WORK
Before anything else: read `autoagent/PROJECT.md` for the git repo path (under "Git Repos"), then:
`git -C "[PROJECT_REPO_PATH]" status --short`

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

## STEP 2 — DIAGNOSE
For each failure pattern, ask:
- Is there a rule missing from `autoagent/PROMPT.md`?
- Is there a rule that's too vague and needs to be more specific?
- Is this a task-specific failure that belongs in a skill file?
- Does a new skill file need to be created?
- Is the backlog ordered wrong (wrong priorities)?

## STEP 2.5 — KNOWLEDGE PROMOTION CHECK
Review `autoagent/memory/knowledge.md` for rules that have matured:
- **Promotion criteria**: A rule is promotable if it's (a) 3+ sessions old, (b) validated by zero related failures since written, and (c) generalizable beyond one specific bug.
- **Where to promote**: If the rule applies to all sessions → add to `autoagent/PROMPT.md`. If task-specific → add to the relevant `autoagent/skills/[type].md`. If it's a file-pattern trigger → add to `autoagent/skills/INDEX.md`.
- **After promoting**: Add a `[PROMOTED → file.md]` tag to the original knowledge.md entry so it's not re-promoted. Do NOT delete the original — it serves as audit trail.
- **Goal**: 1-2 promotions per META session. If no rules qualify, skip this step.
(Source: alirezarezvani/claude-skills self-improving-agent pattern — memory → rule → enforced promotion lifecycle)

## STEP 2.7 — MEMORY EVICTION
Run the memory eviction to keep context lean:
```python
from engine.memory import run_eviction
result = run_eviction(Path("autoagent/memory"))
```
Or equivalently via CLI if available. This archives:
- **knowledge.md** entries older than 30 days → `knowledge_archive.md`
- **activity_log.md** entries beyond the last 30 → `activity_log_archive.md`

Archives are plain text and searchable — nothing is deleted. Log eviction counts in the session activity entry if any entries were archived.

## STEP 3 — FIX

### Fix PROMPT.md rules
Open `autoagent/PROMPT.md`. Find the relevant section. Add or update the rule.
Be specific — "run tests" is worse than "run `py -m pytest tests/ -q --ignore=tests/test_e2e.py`"

### Fix or create skill files
If the failure was task-specific (always happens during coding, always happens during research):
- Open the relevant `autoagent/skills/[type].md`
- Add the rule where it would be seen first
- If no skill file exists for this failure type → CREATE one

### Reorder backlog
Open `autoagent/memory/backlog.md`.
Move highest value unchecked tasks to the top.
Remove tasks that are no longer relevant.
Add tasks you noticed are missing but should be done.

### Update knowledge.md
If you found a pattern about the codebase that isn't in `autoagent/memory/knowledge.md`, add it.

### Prune cross-project pollution (mandatory each META session)
External hooks inject foreign rules into knowledge.md without project-scope check. Sweep and delete:
- Lines under headers `# Shared from other projects` / `# Security findings from other projects`
- `RULE: [VISUAL CHECK]` / `RULE: [STUCK]` / `RULE: [INTEGRITY]` / `RULE: [UX REVIEW]` markers
- `METRIC:` lines with bogus aggregate stats (e.g. "0% success", "0 avg tests")
- Duplicate RULEs (same date + same body appearing twice)
- Rules referencing paths or stacks outside this project (e.g. `council.backends`, `engine/run.py`, V1-only paths, other projects' frameworks)

## STEP 4 — COMMIT
Read `autoagent/PROJECT.md` for the git repo path, then:
```bash
git -C "[PROJECT_REPO_PATH]" add .autoagent/
git -C "[PROJECT_REPO_PATH]" commit -m "meta: [what you improved] — [why]"
git -C "[PROJECT_REPO_PATH]" push origin [BRANCH]
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

## INSTRUCTION FILE QUALITY GATE
Before adding ANY rule to PROMPT.md or a skill file, ask:
- **Is this inferable from the codebase?** If an agent could figure it out by reading the code or running a command, don't add it. Only include non-inferable details (specific tooling, custom build commands, project-specific conventions). Research shows verbose instruction files increase token cost by 20%+ while reducing success rates by 3%. (Source: arxiv 2602.11988)
- **Is this preventing a real failure?** Every rule must trace to a concrete past failure or a measured risk. "Good practice" is not sufficient justification.
- **Is this shorter than 3 sentences?** If a rule needs more, it belongs in a skill file, not PROMPT.md.

## WHAT TO AVOID
- Don't add rules for things that never failed — only fix real problems
- Don't make rules longer for the sake of it — shorter and clearer is better
- Don't restructure files unnecessarily — targeted edits only
