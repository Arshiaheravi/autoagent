# Council Corpus — Source Guide

How to feed `scripts/ingest_council_corpus.py` with external decision
precedent so the council reads real-world prior verdicts before
synthesizing a new one. The ingester is source-agnostic — it accepts
any JSON file matching the canonical schema. Per-source adapters
under `scripts/corpus_pull/` pull raw data and normalize it.

This complements `scripts/backfill_council_memory.py` which seeds
council_episodic from AAA's own SQLite history (`agency.db.council_decisions`).
External corpus + self history together = the council's full memory.

---

## Canonical Schema

```json
[
    {
        "id":          "k8s-adr-001",          // required, unique within platform
        "title":       "Choose primary DB",    // required
        "question":    "Should we use X?",     // required — what was decided
        "synthesis":   "We chose X because ...",// required — decision + rationale
        "winner":      "approach-name",        // required — short headline outcome
        "confidence":  "HIGH",                 // required — HIGH/MEDIUM/LOW
        "platform":    "adrs",                 // required — source identifier
        "context":     "service backend",      // optional — situation snapshot
        "decided_at":  "2024-09-15",           // optional — ISO date
        "url":         "https://..."           // optional — source link
    },
    ...
]
```

Idempotent on `question_hash`. Re-runs skip rows whose `question` was
already ingested. Maps 1:1 to `council_episodic` columns.

---

## Recommended Sources (Ranked by Signal Density)

### Tier 1 — Highest Density (Implemented Parsers)

**Architecture Decision Records (ADRs)** — `joelparkerhenderson/architecture-decision-record`
- Curated index linking to ~5-10k ADRs across public eng repos.
- Each ADR has Context + Decision + Consequences sections — exact council shape.
- Adapter: `scripts/corpus_pull/pull_adrs.py` — PARSER IMPLEMENTED, live pull STUB.
- Run: feed `parse_adr_markdown(text, repo=..., path=...)` for each .md file.

**Anthropic agent-design corpus** — `anthropic.com/news` + `github.com/anthropics/*`
- Building Effective Agents, MCP, contextual retrieval, Claude Code docs,
  Cookbook, Skills, CCSR, LRA, financial-services-skills, claude-for-legal.
- Adapter: `scripts/corpus_pull/pull_anthropic_agents.py` — PARSER IMPLEMENTED, live pull STUB.
- Existing memory pins (skills repo, cookbooks, CCSR, LRA, monitoring guide)
  can be promoted into corpus directly via `parse_anthropic_post()`.

### Tier 2 — Stub Adapters

These hold slots — implement when needed.

**TC39 (JavaScript) RFCs** — `github.com/tc39/proposals`
- Each stage-3/4 proposal has README.md with motivation + design.
- Stage-0/1/2 rejected = negative signal.
- Adapter: `pull_tc39.py` — STUB.

**Python PEPs** — `peps.python.org`
- JSON index at `peps.python.org/api/peps.json`. ~700 PEPs total.
- Structured Abstract + Motivation + Rationale + Decision sections.
- Adapter: `pull_pep.py` — STUB.

**Rust RFCs** — `github.com/rust-lang/rfcs`
- Accepted in `/text/`, rejected in PR-closed history. Both valuable.
- Adapter: `pull_rust_rfcs.py` — STUB.

**Java JEPs** — `openjdk.org/jeps`
- ~500 JEPs with Goal + Non-Goals + Motivation + Description.
- Adapter: `pull_jep.py` — STUB.

**Post-mortem library** — `github.com/danluu/post-mortems`
- ~2k curated public incident write-ups. Question = "what went wrong?",
  synthesis = root cause + remediation. HIGH confidence — outcomes are real.
- Adapter: `pull_postmortems.py` — STUB.

---

## Adapter Pattern

Same shape as RH's `scripts/corpus_pull/`. Each adapter exposes:

```python
def pull(out_path: str, *, limit: int | None = None, **kwargs) -> int:
    """Fetch, normalize, write canonical JSON. Return row count."""
```

Plus pure parser functions that take raw payload → canonical dict.
Parsers run offline against fixture payloads in tests.

### Adding a new adapter

1. Add `scripts/corpus_pull/pull_<source>.py` with `pull()` + pure parser.
2. Add fixture-driven test in `tests/test_council_corpus.py`.
3. Update this doc with the source URL + caveats.

---

## Minimum Viable Corpus (For First Bench)

Use the included sample to seed the council without any network calls:

```sh
export COUNCIL_MEMORY_ENABLED=true
python3 scripts/ingest_council_corpus.py \
    --source tests/fixtures/council_corpus_sample.json \
    --confirm
```

5 hand-crafted rows across ADR / Anthropic / PEP / postmortem / pattern.
Enough to validate the recall path before pulling 1k+ real ADRs.

---

## Bulk Run Estimate

| Source | Volume | OpenAI embed cost | Time |
|---|---|---|---|
| ADRs (curated 1k) | ~1k | ~$0.50 | ~5 min |
| Anthropic agent corpus | ~50 posts | ~$0.20 | ~1 min |
| TC39 + PEP + Rust + JEP | ~3k combined | ~$1.50 | ~15 min |
| danluu/post-mortems | ~2k | ~$1 | ~10 min |
| **Total Tier 1+2** | **~6k** | **~$3** | **~30 min** |

Trivial cost.

---

## Filtering Strategy on Ingest

`--platform` for staged rollout:

```sh
# ADRs first
python3 scripts/ingest_council_corpus.py --source corpus.json --platform adrs --confirm

# Then Anthropic
python3 scripts/ingest_council_corpus.py --source corpus.json --platform anthropic --confirm
```

Idempotent — re-runs skip already-ingested questions by hash.

---

## Deferred (Phase 2+)

1. **Live fetch implementations** for the 5 stub adapters + the ADR/Anthropic
   adapters' live `pull()` functions.
2. **Cross-platform decision canonicalization** — same decision sometimes
   appears in an ADR AND a blog post. Dedupe via embedding similarity > 0.95.
3. **Council scoring per ingested row** — 1-10 quality rubric, drop low-signal.
4. **Recency time-decay** — boost recent decisions; downweight pre-2020.
5. **Per-platform retrieval weight** — Anthropic posts could weight 1.3x for
   agent-design questions specifically.

---

## Related

- `scripts/backfill_council_memory.py` — sibling tool that backfills from
  AAA's own SQLite `council_decisions` table.
- `engine/council/memory.py` — recall/persist API.
- `engine/council/memory_metrics.py` — measures whether recall actually helps.
