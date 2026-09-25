# Bug-sweep — deferred findings (need an owner decision)

From the 2026-07-08 exhaustive engine bug-sweep (8 finders → 33 candidates → 27
confirmed). The 13 clearly-correct ones are fixed in commit `5a05c00`. The 14
below are **confirmed real** but each changes a running system's safety/behavior
or needs a product decision, so they are NOT auto-applied. Ranked by how much
they'd bite.

## Act on these first

1. **`db_maintenance.py:7` — cascade-delete risk (MED, but severe blast radius).**
   `TEST_PROJECT_RE` matches tenant project names by *unanchored substring*
   (`test`/`demo`/`sample`/`fixture`/`tmp`, plus bare `testproject`). A real
   tenant named e.g. `demo-co`, `fixtures-api`, or anything containing `test`
   would be swept by the maintenance path — an irrecoverable multi-table cascade
   delete of that tenant's council_decisions / metrics / messages / tasks /
   knowledge / sessions / agents / projects. **Fix direction:** require an exact
   / anchored match (or an explicit `is_test` flag on the project), never a
   substring. Decide what officially marks a project disposable before tightening.

2. **`session_hooks.py:194` — security hooks don't actually block (HIGH).**
   PreToolUse hooks signal "block" with `sys.exit(1)`, but Claude Code only
   blocks a tool call on **exit code 2** — any other non-zero exit is
   non-blocking. So the gitignore/secret/syntax PreToolUse guards are effectively
   fail-open today. **Fix:** exit 2 on block. **Decision:** this flips a running
   autonomous engine from fail-open to fail-closed — confirm you want hard blocks
   before shipping (a false positive would halt a session).

3. **`self_improve_analyzers.py:327` — regression gate reads a dead field (HIGH,
   advisory-only).** `quality_gate_check` reads test counts from
   `quality.tests_after` (never exists → always 0), so the "did we delete/break
   tests" regression gate never triggers. Same wrong-key class as the fixed
   metric bug, but here it silently disables a safety check. It only writes a RULE
   to knowledge.md (doesn't hard-gate commits), hence deferred — but fixing the
   key restores the intended signal. **Decision:** whether this should become a
   hard gate.

## Security hardening (defense-in-depth guard tweaks — confirm each)

4. **`tool_inspector.py:39`** — `_BLOCKED_PATHS` misses `.env.local` /
   `.env.production` / `.env.development` (the `\.env(?!\.example)` alt matches
   only bare `.env`). Fix newly rejects those; confirm it won't break the
   Next.js scaffolder which legitimately writes `.env.local`.
5. **`tool_inspector.py:53`** — destructive-`rm` pattern only matches `-r`/`-rf`,
   missing `rm -fr`, `rm -R`, `rm --recursive` equivalents. Broaden carefully
   (proposed regex was over-broad).
6. **`session_helpers.py:239`** — `_pre_push_gate` whitelists only the first
   bare word of the test command; most real PROJECT.md commands bypass it, so the
   post-session test gate silently passes. Broadening it can start hard-blocking
   pushes — needs a rollout plan.

## Correctness / accuracy (lower blast radius, still owner calls)

7. **`post_session.py:66`** — the only live caller of `update_agent_stats` omits
   `quality`, folding 0 into the running avg_quality. Needs the quality value
   sourced into `run.py` scope (read sessions.json vs recompute) — a design call.
8. **`self_improve_analyzers.py:112`** — `share_*_across_projects` copies every
   project's knowledge/security RULEs into every other project's knowledge.md.
   In a multi-tenant world that's a **cross-tenant leak**; there's no
   owner/tenant-group concept yet to scope it. Decide the sharing boundary.
9. **`telegram_intake.py:646` / `session_helpers` test gate** — Telegram intake
   writes the test command to project.json, but the pre-push gate reads a
   `### Test Command` line from PROJECT.md, so the gate is a silent no-op for
   Telegram-scaffolded projects.
10. **`telegram_intake.py:547`** — project name = first ≤3 alphabetic words of
    the problem, no uniqueness/tenant scoping → name collisions across tenants
    (home dir + symlink + db + `/run <name>`). Needs a naming/scoping convention.
11. **`digest.py:32`** — `since_hours` only labels the string; `get_recent_sessions`
    does no time filtering (id DESC LIMIT 20), so the digest can over/under-report
    the window. Cosmetic (Telegram summary), but misleading.
12. **`task_graph.py:129`** — `find_ready()` treats a dependency id absent from
    the graph as `done=True` (fail-open) — a typo'd `depends:` silently unblocks.
    Likely intentional; confirm.
13. **`task_graph.py:324`** — `min_sequential_steps` uses the default
    `max_batch_size=3`, ignoring a configured size. Display-only (cli_extras).
14. **`worktree.py:220`** — `has_changes()` swallows all exceptions → False, and
    `cleanup_worktree` gates preservation on it, so an errored check could remove
    an unmerged worktree with changes. Safety-improving fix; implementation is
    ambiguous (fix in `has_changes` vs the caller).
