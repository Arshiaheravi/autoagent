"""Tests for trace_capture numeric session ordering (was lexicographic)."""
from pathlib import Path

from trace_capture import _session_id, _prune_traces


def test_session_id_parses_number():
    assert _session_id(Path("session_7.jsonl")) == 7
    assert _session_id(Path("session_142.jsonl")) == 142
    assert _session_id(Path("garbage.jsonl")) == -1  # guarded, no crash


def test_prune_keeps_numerically_newest(tmp_path):
    # 12 traces; keep 10. Oldest two (1, 2) must go — NOT session_10/11 which a
    # lexicographic sort would have deleted (session_10 < session_2 as strings).
    for n in range(1, 13):
        (tmp_path / f"session_{n}.jsonl").write_text("{}", encoding="utf-8")
    _prune_traces(tmp_path, keep=10)
    remaining = {int(p.stem.split("_")[1]) for p in tmp_path.glob("session_*.jsonl")}
    assert remaining == set(range(3, 13))   # 3..12 kept
    assert 1 not in remaining and 2 not in remaining
    assert 12 in remaining and 11 in remaining and 10 in remaining
