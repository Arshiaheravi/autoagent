#!/usr/bin/env python3
"""Tests for post_session.py — post-session hooks."""
import json
import os
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))

import registry


# ── Fixtures ──────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def setup_agency(tmp_path, monkeypatch):
    agency = tmp_path / "agency"
    agency.mkdir()
    (agency / "agency.json").write_text("{}")
    monkeypatch.setenv("AUTOAGENT_HOME", str(agency))
    monkeypatch.setattr(registry, "AGENCY_HOME", agency)


def _make_ctx(tmp_path, name="testproj"):
    ctx = registry.ProjectContext(
        name=name,
        project_root=tmp_path / name,
        agency_home=registry.AGENCY_HOME,
        config={},
    )
    ctx.project_root.mkdir(parents=True, exist_ok=True)
    ctx.project_home.mkdir(parents=True, exist_ok=True)
    ctx.memory_dir.mkdir(parents=True, exist_ok=True)
    return ctx


# ── Tests ─────────────────────────────────────────────────────

def test_log_knowledge_appends(tmp_path):
    """_log_knowledge appends entries to knowledge.md without overwriting."""
    from post_session import _log_knowledge
    ctx = _make_ctx(tmp_path)
    kf = ctx.memory_dir / "knowledge.md"
    kf.write_text("existing content\n")
    _log_knowledge(ctx, "\nNEW RULE\n")
    assert "existing content" in kf.read_text()
    assert "NEW RULE" in kf.read_text()


def test_log_knowledge_creates_file(tmp_path):
    """_log_knowledge creates knowledge.md if it doesn't exist."""
    from post_session import _log_knowledge
    ctx = _make_ctx(tmp_path)
    kf = ctx.memory_dir / "knowledge.md"
    if kf.exists():
        kf.unlink()
    _log_knowledge(ctx, "first entry")
    assert kf.exists()
    assert "first entry" in kf.read_text()


@patch("post_session.logger")
def test_run_post_session_hooks_skips_on_failure(mock_log, tmp_path):
    """When success=False, codex/UX reviews are skipped (they gate on success)."""
    from post_session import run_post_session_hooks
    ctx = _make_ctx(tmp_path)
    # Should not raise even with no council/comms modules
    run_post_session_hooks(ctx, 10, "work", success=False, agent_name="")


@patch("post_session.logger")
def test_run_post_session_hooks_skips_non_work(mock_log, tmp_path):
    """Meta sessions skip codex/UX reviews (they gate on session_type='work')."""
    from post_session import run_post_session_hooks
    ctx = _make_ctx(tmp_path)
    run_post_session_hooks(ctx, 10, "meta", success=True, agent_name="")


def test_run_post_session_hooks_calls_agent_memory(tmp_path):
    """When agent_name is provided, agent memory functions are called."""
    from post_session import run_post_session_hooks
    ctx = _make_ctx(tmp_path)
    mock_update_mem = MagicMock()
    mock_update_perf = MagicMock()
    mock_upsert = MagicMock()
    mock_stats = MagicMock()
    with patch.dict("sys.modules", {
        "agent_memory": MagicMock(update_agent_memory=mock_update_mem, update_performance=mock_update_perf),
        "agency_db": MagicMock(update_agent_stats=mock_stats, upsert_agent=mock_upsert),
    }):
        run_post_session_hooks(ctx, 10, "work", success=True, agent_name="coder")
    mock_update_mem.assert_called_once()
    mock_upsert.assert_called_once_with(ctx.name, "coder")


def test_run_post_session_hooks_no_agent_skips_memory(tmp_path):
    """When agent_name is empty, agent memory block is skipped entirely."""
    from post_session import run_post_session_hooks
    ctx = _make_ctx(tmp_path)
    mock_update_mem = MagicMock()
    with patch.dict("sys.modules", {
        "agent_memory": MagicMock(update_agent_memory=mock_update_mem),
    }):
        run_post_session_hooks(ctx, 10, "work", success=True, agent_name="")
    mock_update_mem.assert_not_called()


def test_run_post_session_hooks_telegram_notify(tmp_path):
    """Telegram notification is called with task summary from current_task.md."""
    from post_session import run_post_session_hooks
    ctx = _make_ctx(tmp_path)
    ct = ctx.memory_dir / "current_task.md"
    ct.write_text("# Current Task: Build dashboard\n- [x] step 1")
    mock_complete = MagicMock()
    with patch.dict("sys.modules", {
        "comms": MagicMock(session_complete=mock_complete),
    }):
        run_post_session_hooks(ctx, 10, "work", success=True, agent_name="coder")
    mock_complete.assert_called_once()
    call_args = mock_complete.call_args
    assert call_args[0][0] == ctx.name  # project name
    assert "Build dashboard" in call_args[1].get("summary", "") or "Build dashboard" in str(call_args)


def test_run_post_session_hooks_self_improve_called(tmp_path):
    """Self-improve is always called regardless of session type."""
    from post_session import run_post_session_hooks
    ctx = _make_ctx(tmp_path)
    mock_improve = MagicMock()
    with patch.dict("sys.modules", {
        "self_improve": MagicMock(post_session_improve=mock_improve),
    }):
        run_post_session_hooks(ctx, 10, "meta", success=True, agent_name="")
    mock_improve.assert_called_once_with(ctx)
