# AutoAgent — Main Instructions (routing index)

This file is an index. Each session concern lives in its own focused file. Read the file for the concern you're on — don't load all five.

## Read order (every session)
1. `.autoagent/PROJECT.md` — project rules, codebase conventions, git paths, test commands
2. `.autoagent/skills/agent-patterns.md` — failure modes that kill sessions
3. Jump to the PROMPT-*.md file matching the current session concern.

## Files by session concern

- **PROMPT-RECOVERY.md** — FIRST. Orphan sweep, ghost-commit detection, WAL marker fast-path, active_claims protocol, concurrent-wake exit, session-number collision.
- **PROMPT-WORK.md** — task selection (impact score), TDD two-commit proof, current_task.md workflow, session invariants, feature/composition rules, skill routing, step-by-step execution.
- **PROMPT-CONTEXT.md** — CONTEXT_SUMMARY gate, checkpoint density, memory stratification, compression paradox, knowledge.md RULE admission, memory pruning.
- **PROMPT-FAILURE.md** — tool-call failure classification, retry caps, budget tier table, PARTIAL/EMERGENCY commits, doom-loop detection, trajectory-length warning.
- **PROMPT-VERIFICATION.md** — LAST. Self-critique scaling, multi-disciplinary audit, test + frontend gates, VERIFICATION REPORT, commit order, WAL finalize, MINIMUM VIABLE LOG, SESSION COMPLETE gate, activity_log/sessions.json/knowledge.md logging, API key protocol, "DONE" definition.

## Canonical flow within a session

1. **RECOVERY** first — orphan sweep, ghost-commit check, concurrent-session guard, claim-protocol.
2. **WORK** — pick task (impact score), write TDD tests (Commit 1), implement (Commit 2), follow session invariants.
3. **CONTEXT** discipline throughout — checkpoint every ~15 calls, memory stratification, eviction over abbreviation.
4. **FAILURE** handling whenever tools fail or budget drops — classify, apply retry cap per budget tier, PARTIAL/EMERGENCY-commit if exhausted.
5. **VERIFICATION** gate before commit — self-critique → audit → tests → frontend → VERIFICATION REPORT → commit → WAL finalize → MINIMUM VIABLE LOG.
