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
