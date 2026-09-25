#!/usr/bin/env python3
"""Tests for activity_log.py — auto-refresh hook for activity_log.md."""
import time
from pathlib import Path

from activity_log import append_activity_log_entry


def test_activity_log_appends_entry(tmp_path):
    """Entry appended in correct format with DONE/IMPACT/FILES lines."""
    log_path = tmp_path / "activity_log.md"
    log_path.write_text("# activity log\n\n## 2026-04-30 12:00 — FEATURE\nDONE: old entry\n", encoding="utf-8")

    append_activity_log_entry(
        log_path,
        session_type="work",
        summary="Added retry logic to launcher",
        files=["engine/retry.py", "engine/test_retry.py"],
    )

    content = log_path.read_text(encoding="utf-8")
    assert "## 2026-" in content
    assert "DONE: Added retry logic to launcher" in content
    assert "FILES: engine/retry.py, engine/test_retry.py" in content
    assert content.index("DONE: Added retry logic") < content.index("DONE: old entry")


def test_activity_log_lag_under_24h_after_session(tmp_path):
    """After append, file mtime is within last 60 seconds (proves freshness)."""
    log_path = tmp_path / "activity_log.md"
    log_path.write_text("# activity log\n", encoding="utf-8")

    append_activity_log_entry(
        log_path,
        session_type="meta",
        summary="Improved prompt wording",
        files=["PROMPT.md"],
    )

    mtime = log_path.stat().st_mtime
    assert time.time() - mtime < 60


def test_activity_log_handles_missing_file(tmp_path):
    """Creates activity_log.md if it doesn't exist."""
    log_path = tmp_path / "activity_log.md"
    assert not log_path.exists()

    append_activity_log_entry(
        log_path,
        session_type="work",
        summary="Initial feature",
        files=["engine/new.py"],
    )

    assert log_path.exists()
    content = log_path.read_text(encoding="utf-8")
    assert "# activity log" in content
    assert "DONE: Initial feature" in content
    assert "FILES: engine/new.py" in content
