"""R4 analogical traversal tests — TDD red phase first.

R4 surfaces prior verdicts whose CONTEXT embedding matches the current
context, even when the QUESTION embedding doesn't clear MIN_SIM. Mirrors
Orus interview lift #2: skill learned days ago surfaces on an obliquely
related question because the situation matches.

These tests are written BEFORE recall_analogical() exists. They MUST fail
on first run (AttributeError on cm.recall_analogical). Implementation
follows in the green phase.
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


TEST_TAG = f"r4test_{uuid.uuid4().hex[:12]}"


# ── stubs ──────────────────────────────────────────────────────────────


def _stub_embed_from_chars(text: str) -> list[float]:
    """Deterministic per-character stub embedding, like test_council_memory."""
    vec = [0.0] * cm.EMBED_DIM
    for i, ch in enumerate(text[:cm.EMBED_DIM]):
        vec[i] = (ord(ch) % 97) / 97.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


@pytest.fixture(autouse=True)
def _patch_embed(monkeypatch):
    monkeypatch.setattr(cm, "embed", _stub_embed_from_chars)


@pytest.fixture
def memory_on(monkeypatch):
    monkeypatch.setenv("COUNCIL_MEMORY_ENABLED", "true")
    monkeypatch.setenv("COUNCIL_MEMORY_R4_ENABLED", "true")
    yield


@pytest.fixture(autouse=True)
def _cleanup_test_rows():
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
        "stage1": [{"name": "alice", "response": "ship"}],
        "stage2": {"aggregate": [{"name": "alice", "rank": 1}]},
        "synthesis": synthesis, "winner": winner, "confidence": confidence,
        "mode": "executive",
    }


# ── R4 contract tests ──────────────────────────────────────────────────


def test_r4_surfaces_context_match_when_question_far(memory_on):
    """Persist a verdict with a SPECIFIC context. Recall with a totally
    different question but the SAME context → R4 surfaces it even though
    question-sim is below the primary floor."""
    shared_context = (
        f"{TEST_TAG} context: refactoring engine/auth.py middleware "
        f"to support per-route token scoping with redis-backed rate limits"
    )
    cm.persist(
        question=f"{TEST_TAG} q-original: should we add per-route scoping?",
        context=shared_context,
        result=_fake_result(winner="bob"),
    )
    # Different question, same context. Stub embed shares the TEST_TAG
    # prefix so question-sim sits ~0.82 (artificial; real OpenAI on these
    # two strings would also exceed 0.70). Use a relaxed q_max to express
    # the intent: "ctx match surfaces a row whose question is materially
    # different (sim ≤ 0.85)".
    rows = cm.recall_analogical(
        question=f"{TEST_TAG} q-other: zzzz qqqq xxxx yyyy",
        context=shared_context,
        k=3, q_max_sim=0.85, c_min_sim=0.75,
    )
    assert len(rows) >= 1, "R4 must surface a row whose context matches"
    assert any(r["winner"] == "bob" for r in rows)
    # Each row reports BOTH a question_similarity and a context_similarity
    # so the caller can distinguish R4 hits from regular recall.
    for r in rows:
        assert "question_similarity" in r
        assert "context_similarity" in r
        assert r["context_similarity"] >= 0.75


def test_r4_separate_context_floor_env_overridable(memory_on, monkeypatch):
    """COUNCIL_MEMORY_R4_CTX_MIN_SIM env knob must be honored at call time
    (re-read on each call so test toggles work without re-imports)."""
    monkeypatch.setenv("COUNCIL_MEMORY_R4_CTX_MIN_SIM", "0.999")
    shared_context = f"{TEST_TAG} ctx-A " + "x" * 100
    cm.persist(question=f"{TEST_TAG} q1", context=shared_context, result=_fake_result())
    # Slightly different context → ctx-sim won't clear 0.999 floor → no result.
    rows = cm.recall_analogical(
        question=f"{TEST_TAG} q2 different question",
        context=shared_context + " mutated tail",
        k=3, q_max_sim=0.70,
    )
    assert rows == [], "Floor of 0.999 must reject anything not near-identical"


def test_r4_dedupes_against_primary_recall(memory_on):
    """When the SAME row would be returned by both recall_similar() and
    recall_analogical(), R4 must mark it so the caller can dedupe — by
    returning the row id consistently so the merge step works."""
    q = f"{TEST_TAG} dedupe-q"
    ctx = f"{TEST_TAG} dedupe-ctx"
    cm.persist(question=q, context=ctx, result=_fake_result())
    primary = cm.recall_similar(q + " ", ctx)  # near-q match
    analogical = cm.recall_analogical(
        question=f"{TEST_TAG} totally different",
        context=ctx,  # near-ctx match → same row
        k=5, q_max_sim=1.0, c_min_sim=0.5,  # generous so it returns
    )
    primary_ids = {r["id"] for r in primary}
    analogical_ids = {r["id"] for r in analogical}
    # Each row id surfaces in at most one set when caller passes the
    # exclude_ids hint — verify the exclude mechanism exists.
    analogical_excluded = cm.recall_analogical(
        question=f"{TEST_TAG} totally different",
        context=ctx,
        k=5, q_max_sim=1.0, c_min_sim=0.5,
        exclude_ids=list(primary_ids),
    )
    excluded_ids = {r["id"] for r in analogical_excluded}
    assert primary_ids.isdisjoint(excluded_ids), \
        "exclude_ids must filter rows already returned by primary recall"


def test_r4_disabled_by_default(monkeypatch):
    """COUNCIL_MEMORY_ENABLED=true alone is NOT enough — R4 needs its own
    explicit opt-in via COUNCIL_MEMORY_R4_ENABLED. The primary memory path
    can be on while R4 stays off."""
    monkeypatch.setenv("COUNCIL_MEMORY_ENABLED", "true")
    monkeypatch.delenv("COUNCIL_MEMORY_R4_ENABLED", raising=False)
    rows = cm.recall_analogical(
        question="q", context="ctx", k=3, c_min_sim=0.0,
    )
    assert rows == [], "R4 must short-circuit when its own gate is off"


def test_r4_off_when_context_empty(memory_on):
    """Empty context can't meaningfully match anything — R4 must no-op
    rather than degrading to a question-only recall (that's the primary
    path's job)."""
    cm.persist(question=f"{TEST_TAG} q", context="some context",
               result=_fake_result())
    rows = cm.recall_analogical(
        question=f"{TEST_TAG} different q",
        context="",  # nothing to anchor analogical on
        k=3, c_min_sim=0.0,
    )
    assert rows == []
