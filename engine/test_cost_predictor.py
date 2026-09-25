#!/usr/bin/env python3
"""Tests for cost_predictor.py — session cost estimation."""
import json
import os
import sys
import pytest
from pathlib import Path

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


def _make_ctx(tmp_path, name="testproj", config=None):
    ctx = registry.ProjectContext(
        name=name,
        project_root=tmp_path / name,
        agency_home=registry.AGENCY_HOME,
        config=config or {},
    )
    ctx.project_root.mkdir(parents=True, exist_ok=True)
    ctx.project_home.mkdir(parents=True, exist_ok=True)
    ctx.memory_dir.mkdir(parents=True, exist_ok=True)
    return ctx


def _write_sessions(ctx, sessions):
    """Write sessions.json for a project."""
    sf = ctx.project_home.parent.parent / "projects" / ctx.name
    sf.mkdir(parents=True, exist_ok=True)
    # sessions.json lives at ctx.sessions_file (in .autoagent/)
    ctx.sessions_file.write_text(json.dumps(sessions), encoding="utf-8")


# ── Tests ─────────────────────────────────────────────────────

def test_predict_session_cost_uses_history(tmp_path):
    """Prediction uses average cost from recent sessions."""
    from cost_predictor import predict_session_cost
    ctx = _make_ctx(tmp_path)
    sessions = [
        {"session": 1, "type": "work", "cost_usd": 0.50},
        {"session": 2, "type": "work", "cost_usd": 0.30},
        {"session": 3, "type": "work", "cost_usd": 0.40},
    ]
    _write_sessions(ctx, sessions)
    result = predict_session_cost(ctx, "work")
    assert "estimated_cost" in result
    assert abs(result["estimated_cost"] - 0.40) < 0.01  # avg of 0.50, 0.30, 0.40


def test_predict_with_no_history_returns_default(tmp_path):
    """When no sessions exist, return a sensible default estimate."""
    from cost_predictor import predict_session_cost
    ctx = _make_ctx(tmp_path)
    _write_sessions(ctx, [])
    result = predict_session_cost(ctx, "work")
    assert result["estimated_cost"] > 0
    assert result["confidence"] == "low"


def test_predict_filters_by_session_type(tmp_path):
    """Prediction uses only sessions matching the requested type."""
    from cost_predictor import predict_session_cost
    ctx = _make_ctx(tmp_path)
    sessions = [
        {"session": 1, "type": "work", "cost_usd": 0.50},
        {"session": 2, "type": "meta", "cost_usd": 0.10},
        {"session": 3, "type": "work", "cost_usd": 0.30},
    ]
    _write_sessions(ctx, sessions)
    result = predict_session_cost(ctx, "work")
    assert abs(result["estimated_cost"] - 0.40) < 0.01  # avg of work only


def test_predict_blocks_over_budget(tmp_path):
    """When predicted cost exceeds remaining budget, recommend=skip."""
    from cost_predictor import predict_session_cost
    ctx = _make_ctx(tmp_path, config={"daily_limit_usd": 1.0})
    sessions = [
        {"session": 1, "type": "work", "cost_usd": 2.00},
        {"session": 2, "type": "work", "cost_usd": 2.50},
    ]
    _write_sessions(ctx, sessions)
    # Write budget showing $0.50 already spent today
    ctx.budget_file.write_text(json.dumps({"2026-04-06": 0.80}))
    result = predict_session_cost(ctx, "work", daily_limit=1.0, spent_today=0.80)
    assert result["recommend"] == "skip"


def test_predict_allows_under_budget(tmp_path):
    """When predicted cost fits in remaining budget, recommend=proceed."""
    from cost_predictor import predict_session_cost
    ctx = _make_ctx(tmp_path, config={"daily_limit_usd": 10.0})
    sessions = [
        {"session": 1, "type": "work", "cost_usd": 0.30},
        {"session": 2, "type": "work", "cost_usd": 0.40},
    ]
    _write_sessions(ctx, sessions)
    result = predict_session_cost(ctx, "work", daily_limit=10.0, spent_today=1.0)
    assert result["recommend"] == "proceed"


def test_predict_uses_last_10_sessions_only(tmp_path):
    """Only the last 10 matching sessions are used for the average."""
    from cost_predictor import predict_session_cost
    ctx = _make_ctx(tmp_path)
    # 15 work sessions — first 5 are expensive (should be ignored), last 10 cheap
    sessions = [{"session": i, "type": "work", "cost_usd": 5.0} for i in range(1, 6)]
    sessions += [{"session": i, "type": "work", "cost_usd": 0.20} for i in range(6, 16)]
    _write_sessions(ctx, sessions)
    result = predict_session_cost(ctx, "work")
    assert result["estimated_cost"] < 1.0  # should be ~0.20, not skewed by old expensive sessions


def test_predict_returns_confidence_high_with_many_sessions(tmp_path):
    """Confidence is high when 5+ matching sessions exist."""
    from cost_predictor import predict_session_cost
    ctx = _make_ctx(tmp_path)
    sessions = [{"session": i, "type": "work", "cost_usd": 0.30} for i in range(1, 8)]
    _write_sessions(ctx, sessions)
    result = predict_session_cost(ctx, "work")
    assert result["confidence"] == "high"


def test_predict_returns_confidence_medium_with_few_sessions(tmp_path):
    """Confidence is medium when 2-4 matching sessions exist."""
    from cost_predictor import predict_session_cost
    ctx = _make_ctx(tmp_path)
    sessions = [{"session": i, "type": "work", "cost_usd": 0.30} for i in range(1, 4)]
    _write_sessions(ctx, sessions)
    result = predict_session_cost(ctx, "work")
    assert result["confidence"] == "medium"
