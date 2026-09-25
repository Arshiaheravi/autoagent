"""Wire-in tests for R4 + primary recall through format_recall_block().

Verifies the merge step that executive.py uses to combine recall_similar()
output with recall_analogical() output into a single context-prepend block.
"""
from __future__ import annotations

import math
import sys
import uuid
from pathlib import Path

import pytest

ENGINE = Path(__file__).resolve().parent.parent / "engine"
sys.path.insert(0, str(ENGINE))

from council import memory as cm  # noqa: E402


TEST_TAG = f"wire_{uuid.uuid4().hex[:12]}"


def _stub_embed(text: str) -> list[float]:
    vec = [0.0] * cm.EMBED_DIM
    for i, ch in enumerate(text[:cm.EMBED_DIM]):
        vec[i] = (ord(ch) % 97) / 97.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


@pytest.fixture(autouse=True)
def _patch_embed(monkeypatch):
    monkeypatch.setattr(cm, "embed", _stub_embed)


def _purge():
    try:
        with cm.with_conn() as c, c.cursor() as cur:
            cur.execute("DELETE FROM council_episodic WHERE question LIKE %s",
                        (f"{TEST_TAG}%",))
            c.commit()
    except Exception:
        pass


@pytest.fixture(autouse=True)
def _cleanup_rows():
    _purge()
    yield
    _purge()


@pytest.fixture
def memory_on(monkeypatch):
    monkeypatch.setenv("COUNCIL_MEMORY_ENABLED", "true")
    monkeypatch.setenv("COUNCIL_MEMORY_R4_ENABLED", "true")
    yield


def _fake_result(winner: str = "alice", confidence: str = "HIGH") -> dict:
    return {
        "stage1": [], "stage2": {"aggregate": []},
        "synthesis": f"verdict by {winner}",
        "winner": winner, "confidence": confidence, "mode": "executive",
    }


def test_format_block_handles_primary_rows():
    """Primary rows carry a single `similarity` field — block must render."""
    rows = [{"id": 1, "similarity": 0.9, "question": "q1",
             "winner": "alice", "confidence": "HIGH", "synthesis": "ship"}]
    out = cm.format_recall_block(rows)
    assert "## Prior similar council verdicts" in out
    assert "sim=0.90" in out
    assert "alice" in out


def test_format_block_handles_r4_rows():
    """R4 rows carry both question_similarity AND context_similarity.
    format_recall_block must accept either shape so executive.py can merge
    one list of dicts in either format."""
    rows = [{"id": 2,
             "question_similarity": 0.55, "context_similarity": 0.88,
             "question": "q2", "winner": "bob", "confidence": "MEDIUM",
             "synthesis": "consider"}]
    out = cm.format_recall_block(rows)
    # R4 rows surface their context-sim signal so the council can weight
    # them differently from primary recall.
    assert "ctx=0.88" in out or "context_similarity" in out or "ctx_sim=0.88" in out
    assert "bob" in out


def test_executive_recall_helper_merges_dedup(memory_on):
    """The internal helper that executive.py uses must:
    1. Call recall_similar() first.
    2. Pass the resulting ids as exclude_ids to recall_analogical().
    3. Return a single merged list with primary rows first, analogical after.
    """
    q = f"{TEST_TAG} alpha unique question"
    ctx = f"{TEST_TAG} shared-context-token-XYZ"
    # Row that primary recall will find.
    cm.persist(question=q, context=ctx, result=_fake_result(winner="alice"))
    # Row that ONLY R4 can find — different question, same context.
    cm.persist(
        question=f"{TEST_TAG} beta totally-different-question",
        context=ctx,
        result=_fake_result(winner="bob"),
    )

    merged = cm.recall_combined(
        question=q + " ",  # near-q so primary finds the alice row
        context=ctx,
        k=5,
    )
    winners = [r.get("winner") for r in merged]
    assert "alice" in winners, "primary recall must surface alice"
    assert "bob" in winners, "R4 must surface bob via context match"
    # Dedupe: alice must appear EXACTLY once even though her context
    # matches too.
    assert winners.count("alice") == 1


def test_combined_disabled_returns_empty(monkeypatch):
    monkeypatch.delenv("COUNCIL_MEMORY_ENABLED", raising=False)
    out = cm.recall_combined(question="q", context="c", k=3)
    assert out == []
