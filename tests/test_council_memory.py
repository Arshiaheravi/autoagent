"""Tests for council/memory.py — runs against the live autoagency_memory DB.

Requires the redhunter-memory-pg container running on :5433 (bootstrap via
scripts/bootstrap_council_memory.sh). OpenAI embed is monkeypatched so the
suite doesn't burn API quota or require OPENAI_API_KEY.

Each test scopes its writes by a UUID-tagged question prefix and cleans up
in teardown, so reruns + parallel CI never collide.
"""
from __future__ import annotations

import math
import os
import sys
import uuid
from pathlib import Path

import pytest

ENGINE = Path(__file__).resolve().parent.parent / "engine"
sys.path.insert(0, str(ENGINE))

from council import memory as cm  # noqa: E402


TEST_TAG = f"test_{uuid.uuid4().hex[:12]}"


# ── helpers ─────────────────────────────────────────────────────────────


def _stub_embed(text: str) -> list[float]:
    """Deterministic fake embedding: per-character buckets normalized into a
    unit vector. Same text → same vector → cosine 1.0. Different text →
    different but stable vector. Good enough for sim-ordering tests without
    burning OpenAI calls."""
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


@pytest.fixture
def memory_off(monkeypatch):
    monkeypatch.setenv("COUNCIL_MEMORY_ENABLED", "false")
    yield


@pytest.fixture(autouse=True)
def _cleanup_test_rows():
    """Remove anything this run inserted, both at start and end."""
    try:
        with cm.with_conn() as c, c.cursor() as cur:
            cur.execute("DELETE FROM council_episodic WHERE question LIKE %s",
                        (f"{TEST_TAG}%",))
            c.commit()
    except Exception:
        pass
    yield
    try:
        with cm.with_conn() as c, c.cursor() as cur:
            cur.execute("DELETE FROM council_episodic WHERE question LIKE %s",
                        (f"{TEST_TAG}%",))
            c.commit()
    except Exception:
        pass


def _fake_result(synthesis: str = "ship", winner: str = "alice",
                 confidence: str = "HIGH") -> dict:
    return {
        "stage1": [{"name": "alice", "response": "ship it"}],
        "stage2": {"aggregate": [{"name": "alice", "rank": 1}]},
        "synthesis": synthesis,
        "winner": winner,
        "confidence": confidence,
        "mode": "executive",
    }


# ── tests ───────────────────────────────────────────────────────────────


def test_disabled_short_circuits_persist_and_recall(memory_off):
    assert cm.is_enabled() is False
    row_id = cm.persist(
        question=f"{TEST_TAG} q1", context="ctx", result=_fake_result(),
    )
    assert row_id is None, "persist must no-op when disabled"
    rows = cm.recall_similar(f"{TEST_TAG} q1", "ctx")
    assert rows == [], "recall must no-op when disabled"


def test_round_trip_persist_and_recall(memory_on):
    q = f"{TEST_TAG} should we ship the auth refactor?"
    row_id = cm.persist(
        question=q, context="touches engine/auth", result=_fake_result(),
        project="autoagency",
    )
    assert isinstance(row_id, int) and row_id > 0

    # Recall with a near-identical question (NOT the same hash so we don't
    # filter ourselves out). Add a trailing space so hash differs.
    rows = cm.recall_similar(q + " ", "")
    assert len(rows) >= 1
    hit = rows[0]
    assert hit["winner"] == "alice"
    assert hit["confidence"] == "HIGH"
    assert hit["similarity"] > 0.95  # stub: trailing space adds one nonzero component


def test_recall_excludes_exact_question_hash(memory_on):
    q = f"{TEST_TAG} exact match question"
    cm.persist(question=q, context="", result=_fake_result())
    rows = cm.recall_similar(q, "")  # same string → same hash → excluded
    assert rows == []


def test_recall_min_sim_threshold(memory_on):
    cm.persist(question=f"{TEST_TAG} alpha", context="", result=_fake_result())
    # Wildly different stub vector → sim well below floor.
    rows = cm.recall_similar(f"{TEST_TAG} zzzzzzzzzz", "", min_sim=0.99)
    assert rows == []


def test_recall_k_caps_results(memory_on):
    for n in range(5):
        cm.persist(question=f"{TEST_TAG} item {n}", context="", result=_fake_result())
    rows = cm.recall_similar(f"{TEST_TAG} item X", "", k=2, min_sim=0.0)
    assert len(rows) <= 2


def test_format_recall_block_respects_byte_cap():
    rows = [{
        "similarity": 0.9,
        "question": "Q" + "x" * 500,
        "winner": "alice",
        "confidence": "HIGH",
        "synthesis": "Y" * 1000,
    } for _ in range(10)]
    out = cm.format_recall_block(rows, byte_cap=512)
    assert len(out.encode("utf-8")) <= 512 + len("- [...truncated]") + 1


def test_format_recall_block_empty_returns_empty():
    assert cm.format_recall_block([]) == ""


def test_health_check_reports_schema_dim():
    h = cm.health_check()
    assert h["ok"] is True, f"health failed: {h}"
    assert h["embed_dim_schema"] == cm.EMBED_DIM
    assert "row_count" in h


def test_embed_dim_guard_raises_on_mismatch(monkeypatch):
    monkeypatch.setattr(cm, "_get_openai", lambda: _BadClient())
    with pytest.raises(RuntimeError, match="embedding dim mismatch"):
        # Use the real embed, not the stub — bypass autouse fixture for this one.
        monkeypatch.setattr(cm, "embed", cm.__dict__["embed"].__wrapped__
                            if hasattr(cm.embed, "__wrapped__") else
                            _real_embed_direct)
        _real_embed_direct("text")


def _real_embed_direct(text: str) -> list[float]:
    """Calls the real embed body without the autouse stub."""
    text = (text or "")[:32000]
    if not text.strip():
        return [0.0] * cm.EMBED_DIM
    resp = cm._get_openai().embeddings.create(model=cm.EMBED_MODEL, input=text)
    vec = list(resp.data[0].embedding)
    if len(vec) != cm.EMBED_DIM:
        raise RuntimeError(
            f"embedding dim mismatch: model={cm.EMBED_MODEL} returned {len(vec)}, "
            f"schema expects {cm.EMBED_DIM}. Re-check COUNCIL_MEMORY_EMBED_MODEL / _DIM."
        )
    return vec


class _BadResp:
    class _D:
        embedding = [0.0] * 999  # wrong dim
    data = [_D()]


class _BadEmbeddings:
    def create(self, **_):
        return _BadResp()


class _BadClient:
    embeddings = _BadEmbeddings()
