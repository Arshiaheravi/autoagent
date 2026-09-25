# Experiment: Git Push Recovery Procedure
**Date:** 2026-03-17
**Session:** #1
**Hypothesis (H1):** Adding explicit git push verification and recovery procedure to SYSTEM_PROMPT Phase 5 will reduce push/commit failures by ~40%.

## Baseline
- Sessions analyzed: 1 (pre-production, no actual session data)
- Quality score: 7.0/10 (manual assessment)
- Weakest area: push/commit success
- Current Phase 5 SYSTEM_PROMPT text: `git push origin main` (hardcoded, ignores two-repo system and dynamic branch config)
- Push recovery path: NONE — agent has no instruction for what to do if push fails

## Measurement Method
Since we cannot replay prior sessions, we measure structurally:
- **Before:** SYSTEM_PROMPT Phase 5 contains exactly 0 mentions of push failure recovery
- **After:** SYSTEM_PROMPT Phase 5 contains explicit push-failure recovery procedure
- **Future validation:** Track `push_failed` keyword in activity_log.md across next 5 sessions

## Change Applied
File: `autoagent/run.py`
Section: `SYSTEM_PROMPT` — Phase 5 block (~line 1359)

**Removed:**
```
git push origin main
```

**Added:**
```
# Follow the TWO-REPO GIT POLICY shown above for which branch/remote to use
git add <files>  # project files OR autoagent/ — never mix
git commit -m "agent: <what changed> — <why it matters>"
git push origin <branch>  # use branch from git_rules above

# If push fails:
# 1. git remote -v  — verify remote URL is correct
# 2. "rejected (non-fast-forward)" → git pull --rebase origin <branch> && git push
# 3. Auth error → check PAT token in config.json is valid
# 4. No remote set → commit locally, note "push skipped: no remote" in report
# RULE: Always commit. Never skip the commit itself.
```

## Predicted Impact
- Push/commit success: 7.0 → 8.5+ (session quality score)
- Retry rate: reduced (agent knows what to do on failure instead of retrying blindly)
- Metric movement: indirect (more commits = more progress per session)

## Status
- [x] Experiment plan written
- [x] Baseline recorded (0 recovery steps in current SYSTEM_PROMPT)
- [x] Change implemented in run.py
- [ ] Evaluated (next 5 sessions with activity_log data)
