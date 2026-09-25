#!/usr/bin/env python3
"""Tests for usage tracking module."""
import json
import pytest
from pathlib import Path
from datetime import date

import registry
from usage import (
    record_session_usage,
    get_today_usage,
    get_weekly_usage,
    get_all_time_usage,
    format_tokens,
    format_duration,
    show_usage,
    show_usage_all,
)


@pytest.fixture(autouse=True)
def setup_agency(isolated_agency_home):
    yield


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


def _mock_result_event(
    input_tokens=1000,
    output_tokens=500,
    cache_read=5000,
    cache_creation=2000,
    cost_usd=0.05,
    duration_ms=30000,
):
    return {
        "type": "result",
        "total_cost_usd": cost_usd,
        "duration_ms": duration_ms,
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_read_input_tokens": cache_read,
            "cache_creation_input_tokens": cache_creation,
        },
    }


# ── format_tokens ────────────────────────────────────────────

def test_format_tokens_millions():
    assert format_tokens(1_500_000) == "1.5M"


def test_format_tokens_thousands():
    assert format_tokens(45_000) == "45K"


def test_format_tokens_small():
    assert format_tokens(500) == "500"


# ── format_duration ──────────────────────────────────────────

def test_format_duration_seconds():
    assert format_duration(45_000) == "45s"


def test_format_duration_minutes():
    assert format_duration(180_000) == "3m 0s"


def test_format_duration_hours():
    assert format_duration(3_720_000) == "1h 2m"


# ── record_session_usage ─────────────────────────────────────

def test_record_creates_file(tmp_path):
    ctx = _make_ctx(tmp_path)
    event = _mock_result_event()
    record_session_usage(ctx, event)

    uf = ctx.project_home / "usage.json"
    assert uf.exists()
    data = json.loads(uf.read_text())
    today = str(date.today())
    assert today in data
    assert data[today]["sessions"] == 1
    assert data[today]["input_tokens"] == 1000
    assert data[today]["output_tokens"] == 500


def test_record_accumulates(tmp_path):
    ctx = _make_ctx(tmp_path)
    record_session_usage(ctx, _mock_result_event(input_tokens=1000))
    record_session_usage(ctx, _mock_result_event(input_tokens=2000))

    data = json.loads((ctx.project_home / "usage.json").read_text())
    today = str(date.today())
    assert data[today]["sessions"] == 2
    assert data[today]["input_tokens"] == 3000


def test_record_with_model_usage(tmp_path):
    """modelUsage field overrides usage field when present."""
    ctx = _make_ctx(tmp_path)
    event = {
        "type": "result",
        "total_cost_usd": 0.10,
        "duration_ms": 5000,
        "usage": {
            "input_tokens": 100,
            "output_tokens": 50,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
        },
        "modelUsage": {
            "claude-opus-4-6[1m]": {
                "inputTokens": 5000,
                "outputTokens": 2000,
                "cacheReadInputTokens": 10000,
                "cacheCreationInputTokens": 3000,
                "costUSD": 0.10,
            }
        },
    }
    record_session_usage(ctx, event)

    data = json.loads((ctx.project_home / "usage.json").read_text())
    today = str(date.today())
    assert data[today]["input_tokens"] == 5000
    assert data[today]["output_tokens"] == 2000
    assert data[today]["cache_read_tokens"] == 10000


# ── get_today_usage ──────────────────────────────────────────

def test_get_today_empty(tmp_path):
    ctx = _make_ctx(tmp_path)
    u = get_today_usage(ctx)
    assert u["sessions"] == 0
    assert u["total_tokens"] == 0


def test_get_today_with_data(tmp_path):
    ctx = _make_ctx(tmp_path)
    record_session_usage(ctx, _mock_result_event())
    u = get_today_usage(ctx)
    assert u["sessions"] == 1
    assert u["total_tokens"] > 0


# ── get_weekly_usage ─────────────────────────────────────────

def test_get_weekly_aggregates(tmp_path):
    ctx = _make_ctx(tmp_path)
    # Write data for today
    record_session_usage(ctx, _mock_result_event(input_tokens=1000))
    record_session_usage(ctx, _mock_result_event(input_tokens=2000))

    weekly = get_weekly_usage(ctx)
    assert weekly["sessions"] == 2
    assert weekly["input_tokens"] == 3000


# ── get_all_time_usage ───────────────────────────────────────

def test_get_all_time(tmp_path):
    ctx = _make_ctx(tmp_path)
    record_session_usage(ctx, _mock_result_event())
    total = get_all_time_usage(ctx)
    assert total["sessions"] == 1
    assert total["active_days"] == 1


# ── show_usage (smoke test) ─────────────────────────────────

def test_show_usage_no_crash(tmp_path, capsys):
    ctx = _make_ctx(tmp_path)
    record_session_usage(ctx, _mock_result_event())
    show_usage(ctx, "today")
    out = capsys.readouterr().out
    assert "testproj" in out
    assert "Sessions" in out
