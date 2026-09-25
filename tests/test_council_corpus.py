"""TDD: external corpus ingester for council_episodic.

Where backfill_council_memory.py replays AAA's own SQLite history,
ingest_council_corpus.py feeds council_episodic with EXTERNAL precedent
decisions — ADRs, RFC outcomes, Anthropic agent-design blog posts, etc.

Each row becomes a synthetic prior verdict the council reads pre-stage1
on similar questions. Same recall infra, same R4 traversal.

Tests must fail before scripts/ingest_council_corpus.py exists.
"""
from __future__ import annotations

import json
import math
import sys
import uuid
from pathlib import Path

import pytest

ENGINE = Path(__file__).resolve().parent.parent / "engine"
sys.path.insert(0, str(ENGINE))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from council import memory as cm  # noqa: E402


TEST_TAG = f"cctest_{uuid.uuid4().hex[:10]}"


def _stub_embed(text: str) -> list[float]:
    vec = [0.0] * cm.EMBED_DIM
    for i, ch in enumerate(text[:cm.EMBED_DIM]):
        vec[i] = (ord(ch) % 97) / 97.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


@pytest.fixture(autouse=True)
def _patch_embed(monkeypatch):
    monkeypatch.setattr(cm, "embed", _stub_embed)


@pytest.fixture
def memory_on(monkeypatch):
    monkeypatch.setenv("COUNCIL_MEMORY_ENABLED", "true")
    yield


def _purge():
    try:
        with cm.with_conn() as c, c.cursor() as cur:
            cur.execute("DELETE FROM council_episodic WHERE question LIKE %s",
                        (f"{TEST_TAG}%",))
            c.commit()
    except Exception:
        pass


@pytest.fixture(autouse=True)
def _cleanup():
    _purge()
    yield
    _purge()


def _make_corpus(tmp_path: Path, n: int = 3) -> Path:
    rows = []
    for i in range(n):
        rows.append({
            "id": f"{TEST_TAG}-{i}",
            "title": f"ADR {i}: choose database",
            "question": f"{TEST_TAG} should we use Postgres or MySQL for {i}",
            "synthesis": "Chose Postgres for JSONB + extension ecosystem.",
            "winner": "postgres",
            "confidence": "HIGH",
            "platform": "adrs",
            "context": "service backend selection",
            "decided_at": "2024-09-01",
            "url": f"https://example.com/adr/{i}",
        })
    path = tmp_path / "corpus.json"
    path.write_text(json.dumps(rows))
    return path


# ── RED tests ──────────────────────────────────────────────────


def test_module_exists():
    from scripts import ingest_council_corpus  # noqa: F401


def test_dry_run_no_writes(memory_on, tmp_path):
    from scripts.ingest_council_corpus import run_ingest
    corpus = _make_corpus(tmp_path, n=3)
    stats = run_ingest(str(corpus), dry_run=True)
    assert stats["total"] == 3
    assert stats["would_insert"] == 3
    assert stats["inserted"] == 0
    with cm.with_conn() as c, c.cursor() as cur:
        cur.execute("SELECT count(*) FROM council_episodic WHERE question LIKE %s",
                    (f"{TEST_TAG}%",))
        assert cur.fetchone()[0] == 0


def test_real_insert_writes_to_council_episodic(memory_on, tmp_path):
    from scripts.ingest_council_corpus import run_ingest
    corpus = _make_corpus(tmp_path, n=3)
    stats = run_ingest(str(corpus), confirm=True)
    assert stats["inserted"] == 3
    with cm.with_conn() as c, c.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM council_episodic WHERE question LIKE %s",
            (f"{TEST_TAG}%",))
        assert cur.fetchone()[0] == 3


def test_idempotent_skip_on_question_hash(memory_on, tmp_path):
    from scripts.ingest_council_corpus import run_ingest
    corpus = _make_corpus(tmp_path, n=3)
    s1 = run_ingest(str(corpus), confirm=True)
    assert s1["inserted"] == 3
    s2 = run_ingest(str(corpus), confirm=True)
    assert s2["inserted"] == 0
    assert s2["skipped"] == 3


def test_requires_confirm_to_write(tmp_path):
    """memory_on NOT applied here — also test refusal without flag."""
    from scripts.ingest_council_corpus import run_ingest
    corpus = _make_corpus(tmp_path, n=2)
    with pytest.raises(RuntimeError, match="confirm"):
        run_ingest(str(corpus))


def test_requires_memory_enabled(tmp_path, monkeypatch):
    monkeypatch.setenv("COUNCIL_MEMORY_ENABLED", "false")
    from scripts.ingest_council_corpus import run_ingest
    corpus = _make_corpus(tmp_path, n=2)
    with pytest.raises(RuntimeError, match="COUNCIL_MEMORY_ENABLED"):
        run_ingest(str(corpus), confirm=True)


def test_platform_filter(memory_on, tmp_path):
    from scripts.ingest_council_corpus import run_ingest
    rows = [
        {"id": f"{TEST_TAG}-adr", "title": "x", "question": f"{TEST_TAG} adr q",
         "synthesis": "s", "winner": "a", "confidence": "HIGH",
         "platform": "adrs"},
        {"id": f"{TEST_TAG}-rfc", "title": "x", "question": f"{TEST_TAG} rfc q",
         "synthesis": "s", "winner": "b", "confidence": "HIGH",
         "platform": "tc39"},
    ]
    corpus = tmp_path / "mixed.json"
    corpus.write_text(json.dumps(rows))
    stats = run_ingest(str(corpus), confirm=True, platform="adrs")
    assert stats["inserted"] == 1


def test_malformed_row_tolerated(memory_on, tmp_path):
    from scripts.ingest_council_corpus import run_ingest
    corpus = _make_corpus(tmp_path, n=2)
    rows = json.loads(corpus.read_text())
    rows.append({"id": f"{TEST_TAG}-bad", "title": "missing question/synthesis"})
    corpus.write_text(json.dumps(rows))
    stats = run_ingest(str(corpus), confirm=True)
    assert stats["inserted"] == 2
    assert stats["errors"] == 1


# ── ADR parser ─────────────────────────────────────────────────


ADR_SAMPLE = """# 0042. Use Postgres for primary store

* Status: accepted
* Date: 2024-09-15

## Context

We need a durable relational store that supports JSONB and pgvector.
The candidates were Postgres, MySQL, and CockroachDB.

## Decision

We will use Postgres 17 with the pgvector extension.

## Consequences

- Vector recall works in the same DB as transactional state.
- One operational footprint instead of two.
"""


def test_adr_parser_extracts_canonical_schema():
    from scripts.corpus_pull.pull_adrs import parse_adr_markdown
    row = parse_adr_markdown(ADR_SAMPLE,
                             repo="acme/architecture",
                             path="docs/adr/0042-postgres.md")
    assert row["platform"] == "adrs"
    assert "Postgres" in row["title"]
    assert "JSONB" in row["question"] or "JSONB" in row["context"]
    assert "Postgres 17" in row["synthesis"]
    assert row["winner"].lower().startswith("postgres") or \
        row["winner"].lower() == "accepted"
    assert row["confidence"] in ("HIGH", "MEDIUM", "LOW")
    assert "acme/architecture" in row["url"]


def test_adr_parser_skips_files_without_context_or_decision():
    """File missing the structured sections shouldn't yield a row."""
    from scripts.corpus_pull.pull_adrs import parse_adr_markdown
    row = parse_adr_markdown("# random doc with no ADR sections",
                             repo="x", path="x.md")
    assert row is None


# ── Anthropic parser ───────────────────────────────────────────


ANTHROPIC_SAMPLE = {
    "title": "Building effective agents",
    "url": "https://www.anthropic.com/news/building-effective-agents",
    "published_at": "2024-12-19",
    "content": (
        "When to use agents: agentic systems trade latency and cost for "
        "better task performance, and you should consider whether the "
        "tradeoff makes sense. We recommend starting with the simplest "
        "solution and increasing complexity when needed. The basic "
        "building block of agentic systems is an LLM enhanced with "
        "augmentations such as retrieval, tools, and memory."
    ),
}


def test_anthropic_parser_extracts_canonical_schema():
    from scripts.corpus_pull.pull_anthropic_agents import parse_anthropic_post
    row = parse_anthropic_post(ANTHROPIC_SAMPLE)
    assert row["platform"] == "anthropic"
    assert row["title"] == "Building effective agents"
    assert "agentic" in row["question"].lower() or \
        "agentic" in row["synthesis"].lower()
    assert "anthropic.com" in row["url"]
    assert row["confidence"] in ("HIGH", "MEDIUM", "LOW")


def test_anthropic_parser_skips_empty_content():
    from scripts.corpus_pull.pull_anthropic_agents import parse_anthropic_post
    assert parse_anthropic_post({"title": "x", "url": "y", "content": ""}) is None
