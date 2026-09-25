"""Memory layer metrics — RED phase. All tests must fail before impl.

memory_metrics.weekly_rollup() returns:
    {
        "days": int,
        "convenes_total": int,
        "convenes_with_recall": int,
        "recall_rate": float,           # 0.0 - 1.0
        "verdict_stability_pct": float, # of repeat question_hashes, % matching prior winner
        "repeat_questions": int,
        "avg_recalled_count": float,
    }
"""
from __future__ import annotations

import math
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ENGINE = Path(__file__).resolve().parent.parent / "engine"
sys.path.insert(0, str(ENGINE))

from council import memory as cm  # noqa: E402

# Import the not-yet-existing module under test. Red phase = this raises.
try:
    from council import memory_metrics as mm  # noqa: E402
except ImportError:
    mm = None


TEST_TAG = f"metrics_{uuid.uuid4().hex[:12]}"


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
def _cleanup():
    _purge()
    yield
    _purge()


@pytest.fixture
def memory_on(monkeypatch):
    monkeypatch.setenv("COUNCIL_MEMORY_ENABLED", "true")
    yield


def _fake_result(winner: str = "alice") -> dict:
    return {
        "stage1": [], "stage2": {"aggregate": []},
        "synthesis": f"synth-{winner}", "winner": winner,
        "confidence": "HIGH", "mode": "executive",
    }


def _insert(*, question, winner="alice", had_recall=False,
            recalled_count=0, recalled_ids=None, ts_offset_days=0):
    """Low-level INSERT bypassing persist() so we can set ts + telemetry
    columns directly. Used to construct precise scenarios for rollup tests."""
    q_vec = _stub_embed(question)
    c_vec = _stub_embed("")
    ts = datetime.now(timezone.utc) - timedelta(days=ts_offset_days)
    with cm.with_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO council_episodic (
                ts, question, question_hash, context, context_hash,
                mode, synthesis, winner, confidence,
                question_embedding, context_embedding,
                had_recall_block, recalled_count, recalled_ids
            ) VALUES (
                %s, %s, %s, '', '',
                'executive', %s, %s, 'HIGH',
                %s::vector, %s::vector,
                %s, %s, %s::bigint[]
            ) RETURNING id
            """,
            (
                ts, question, cm._hash(question),
                f"synth-{winner}", winner,
                cm._vec_literal(q_vec), cm._vec_literal(c_vec),
                had_recall, recalled_count, recalled_ids or [],
            ),
        )
        row_id = cur.fetchone()[0]
        conn.commit()
        return row_id


# ── RED tests ──────────────────────────────────────────────────────────


def test_module_exists():
    """memory_metrics module must exist."""
    assert mm is not None, "council.memory_metrics must be importable"


def test_weekly_rollup_empty_table(memory_on):
    # Scope to TEST_TAG so other concurrent test files don't pollute.
    out = mm.weekly_rollup(days=7, question_prefix=TEST_TAG)
    assert out["convenes_total"] == 0
    assert out["convenes_with_recall"] == 0
    assert out["recall_rate"] == 0.0
    assert out["verdict_stability_pct"] == 0.0
    assert out["repeat_questions"] == 0
    assert out["avg_recalled_count"] == 0.0
    assert out["days"] == 7


def test_weekly_rollup_counts_recall_rate(memory_on):
    _insert(question=f"{TEST_TAG} q1", had_recall=False)
    _insert(question=f"{TEST_TAG} q2", had_recall=True, recalled_count=2)
    _insert(question=f"{TEST_TAG} q3", had_recall=True, recalled_count=3)
    out = mm.weekly_rollup(days=7, question_prefix=TEST_TAG)
    assert out["convenes_total"] == 3
    assert out["convenes_with_recall"] == 2
    assert round(out["recall_rate"], 2) == 0.67
    assert round(out["avg_recalled_count"], 2) == round(5 / 3, 2)


def test_weekly_rollup_time_window_excludes_old(memory_on):
    _insert(question=f"{TEST_TAG} old", ts_offset_days=30)
    _insert(question=f"{TEST_TAG} new", ts_offset_days=1)
    out = mm.weekly_rollup(days=7, question_prefix=TEST_TAG)
    assert out["convenes_total"] == 1, "30-day-old row must be excluded from 7d window"


def test_verdict_stability_repeat_questions(memory_on):
    """Same question_hash asked twice → stability = % matching winner.
    Two repeats, both winners match → 100%. Mismatch → 50%."""
    q_repeat = f"{TEST_TAG} repeat-q"
    _insert(question=q_repeat, winner="alice", ts_offset_days=2)
    _insert(question=q_repeat, winner="alice", ts_offset_days=1)
    _insert(question=f"{TEST_TAG} other-q", winner="bob")
    _insert(question=f"{TEST_TAG} flip-q", winner="alice", ts_offset_days=2)
    _insert(question=f"{TEST_TAG} flip-q", winner="bob",   ts_offset_days=1)

    out = mm.weekly_rollup(days=7, question_prefix=TEST_TAG)
    assert out["repeat_questions"] == 2  # repeat-q + flip-q
    # repeat-q stable (alice == alice), flip-q unstable (alice → bob) → 50%
    assert round(out["verdict_stability_pct"], 1) == 50.0


def test_verdict_stability_zero_when_no_repeats(memory_on):
    _insert(question=f"{TEST_TAG} unique-1", winner="alice")
    _insert(question=f"{TEST_TAG} unique-2", winner="bob")
    out = mm.weekly_rollup(days=7, question_prefix=TEST_TAG)
    assert out["repeat_questions"] == 0
    assert out["verdict_stability_pct"] == 0.0
