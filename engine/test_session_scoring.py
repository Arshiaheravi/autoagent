"""Tests for session_scoring.py — labels, quality/impact scoring, health heuristics."""
import json
from session_scoring import (
    format_session_label, compute_quality_score, compute_task_impact_score,
    _session_is_noop, health_auto_meta,
)


def test_format_session_label_full():
    label = format_session_label(42, agent="backend", task="Add auth", files_count=3, test_count=5, success=True)
    assert "#42" in label
    assert "[backend]" in label
    assert '"Add auth"' in label
    assert "3 files" in label
    assert "5 tests" in label
    assert "OK" in label


def test_format_session_label_failure():
    label = format_session_label(1, success=False)
    assert "FAIL" in label
    assert "OK" not in label


def test_format_session_label_truncates_long_task():
    label = format_session_label(1, task="A" * 100)
    assert "…" in label


def test_compute_quality_score_perfect():
    score = compute_quality_score(tasks_completed=1, tests_added=5, tests_broken=0, retries=0)
    assert score == 100


def test_compute_quality_score_zero():
    score = compute_quality_score(tasks_completed=0, tests_added=0, tests_broken=3, retries=5)
    assert score == 0


def test_compute_quality_score_clamped():
    score = compute_quality_score(tasks_completed=0, tests_added=0, tests_broken=10, retries=10)
    assert score == 0


def test_compute_task_impact_max():
    score = compute_task_impact_score(tests_added=5, quality_delta=25, commit_produced=True, regressions=0)
    assert score == 10


def test_compute_task_impact_zero():
    score = compute_task_impact_score(tests_added=0, quality_delta=0, commit_produced=False, regressions=1)
    assert score == 0


def test_session_is_noop_no_files():
    assert _session_is_noop({"files": []}) is True
    assert _session_is_noop({}) is True


def test_session_is_noop_with_files():
    assert _session_is_noop({"files": ["a.py"], "tests": {"status": "pass"}}) is False


def test_session_is_noop_failed_tests():
    assert _session_is_noop({"files": ["a.py"], "tests": {"status": "fail"}}) is True


def test_health_auto_meta_no_file(tmp_path):
    assert health_auto_meta(tmp_path / "nope.json") is False


def test_health_auto_meta_three_noops(tmp_path):
    f = tmp_path / "sessions.json"
    sessions = [{"files": [], "tests": {"status": "skip"}} for _ in range(5)]
    f.write_text(json.dumps(sessions))
    assert health_auto_meta(f) is True


def test_health_auto_meta_healthy(tmp_path):
    f = tmp_path / "sessions.json"
    sessions = [{"files": ["a.py"], "tests": {"status": "pass"}} for _ in range(5)]
    f.write_text(json.dumps(sessions))
    assert health_auto_meta(f) is False
