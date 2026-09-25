"""Tests for cross-session failure pattern detector."""
import pytest
from failure_patterns import detect_failure_patterns


SAMPLE_LOG = """
## 2026-04-09 — FEATURE
DONE: Added session timeout guard
IMPACT: Prevents hung sessions

## 2026-04-08 — FEATURE
DONE: Added backlog scorer
FAILED: ImportError in run.py — circular import between run.py and post_session.py
IMPACT: Future sessions pick better tasks

## 2026-04-07 — FEATURE
DONE: Added health endpoint
FAILED: ImportError in dashboard_server.py — circular import between cli.py and dashboard
IMPACT: External monitoring

## 2026-04-06 — FEATURE
DONE: Added diff summary
BLOCKED: Playwright not installed — skipped frontend check
IMPACT: Post-session logging improved

## 2026-04-05 — FEATURE
DONE: Split test files
FAILED: KeyError in dashboard rendering — missing 'quality_score' key in session dict
IMPACT: Tests pass after split

## 2026-04-04 — FEATURE
DONE: Added pre-compact hook
FAILED: ImportError in launcher.py — circular import with session_helpers
IMPACT: Context preserved
"""


def test_detect_patterns_finds_clusters():
    results = detect_failure_patterns(SAMPLE_LOG)
    assert isinstance(results, list)
    assert len(results) > 0
    # ImportError appears 3 times — should be the top cluster
    import_cluster = [r for r in results if "ImportError" in r["error_type"]]
    assert len(import_cluster) == 1
    assert import_cluster[0]["count"] >= 3
    assert isinstance(import_cluster[0]["sessions"], list)


def test_detect_patterns_empty_log():
    results = detect_failure_patterns("")
    assert results == []


def test_detect_patterns_single_failure():
    log = """
## 2026-04-01 — FEATURE
DONE: Something
FAILED: TimeoutError in run.py — session exceeded 30 minutes
"""
    results = detect_failure_patterns(log)
    assert len(results) == 1
    assert results[0]["error_type"] == "TimeoutError"
    assert results[0]["count"] == 1
