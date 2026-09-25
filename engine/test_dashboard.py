#!/usr/bin/env python3
"""Tests for dashboard_server.py — data API, HTML rendering, sparklines, screenshots."""
import json
import pytest
from pathlib import Path

import registry


@pytest.fixture(autouse=True)
def setup_agency(isolated_agency_home):
    home = isolated_agency_home
    yield


@pytest.fixture
def project_with_sessions(tmp_path):
    """A registered project with session history."""
    proj = tmp_path / "testproj"
    proj.mkdir()
    ctx = registry.register("testproj", proj)
    ctx.ensure_dirs()
    (ctx.project_home / "PROJECT.md").write_text("# Test")
    (ctx.project_home / "NORTH_STAR.md").write_text("# Star")
    (ctx.memory_dir / "backlog.md").write_text("- [ ] task 1\n- [ ] task 2\n- [x] done task")
    (ctx.memory_dir / "current_task.md").write_text("# Current Task: (none)")
    (ctx.memory_dir / "activity_log.md").write_text("# Log\n## 2026-03-26 — FEATURE\nDONE: Built thing")
    (ctx.memory_dir / "done.md").write_text("# Done\n- Built thing")

    sessions = [
        {"session": 1, "type": "work", "date": "2026-03-26", "summary": "Farm CRUD",
         "tests": {"before": 1, "after": 22, "status": "pass"}, "files": ["api/farms.py"]},
        {"session": 2, "type": "work", "date": "2026-03-26", "summary": "Soil API",
         "tests": {"before": 22, "after": 36, "status": "pass"}, "files": ["api/soil.py"]},
        {"session": 3, "type": "meta", "date": "2026-03-26", "summary": "Improved prompts",
         "tests": {"before": 36, "after": 36, "status": "pass"}, "files": ["PROMPT.md"]},
        {"session": 4, "type": "work", "date": "2026-03-26", "summary": "NDVI service",
         "tests": {"before": 36, "after": 58, "status": "pass"}, "files": ["services/crop/ndvi.py"]},
    ]
    ctx.sessions_file.write_text(json.dumps(sessions), encoding="utf-8")

    # Session counter
    ctx.counter_file.write_text(json.dumps({"count": 5}))

    # Agents
    ctx.agents_dir.mkdir(exist_ok=True)
    (ctx.agents_dir / "crop-analyst.md").write_text("# Crop Analyst")
    (ctx.agents_dir / "architect.md").write_text("# Architect")
    return ctx


# ── Dashboard data API ──

import dashboard_server


def test_get_projects_data(project_with_sessions):
    data = dashboard_server.get_projects_data()
    assert len(data) == 1
    p = data[0]
    assert p["name"] == "testproj"
    assert p["sessions"] == 5
    assert p["path"] is not None


def test_get_project_detail(project_with_sessions):
    detail = dashboard_server.get_project_detail("testproj")
    assert detail is not None
    assert detail["name"] == "testproj"
    assert len(detail["sessions"]) == 4
    assert detail["metrics"]["total_sessions"] == 4
    assert detail["metrics"]["latest_tests"] == 58
    assert detail["metrics"]["work_sessions"] == 3


def test_get_project_detail_nonexistent():
    detail = dashboard_server.get_project_detail("nope")
    assert detail is None


def test_get_project_detail_includes_backlog_stats(project_with_sessions):
    detail = dashboard_server.get_project_detail("testproj")
    assert detail["backlog"]["total"] == 3  # 2 unchecked + 1 checked
    assert detail["backlog"]["done"] == 1
    assert detail["backlog"]["remaining"] == 2


def test_get_project_detail_includes_agents(project_with_sessions):
    detail = dashboard_server.get_project_detail("testproj")
    assert len(detail["agents"]) == 2
    agent_names = {a["name"] for a in detail["agents"]}
    assert "crop-analyst" in agent_names


def test_get_project_detail_test_trend(project_with_sessions):
    detail = dashboard_server.get_project_detail("testproj")
    trend = detail["metrics"]["test_trend"]
    # Should be list of test counts per session
    assert trend == [22, 36, 36, 58]


# ── Dashboard HTML generation ──

def test_render_dashboard_html():
    html = dashboard_server.render_dashboard_html([
        {"name": "proj1", "sessions": 5, "path": "/tmp/p1", "created": "2026-01-01"},
    ])
    assert "proj1" in html
    assert "<!DOCTYPE html>" in html


def test_render_project_html():
    detail = {
        "name": "testproj",
        "sessions": [{"session": 1, "type": "work", "summary": "Built thing",
                       "tests": {"after": 22}, "date": "2026-03-26"}],
        "metrics": {"total_sessions": 1, "work_sessions": 1, "latest_tests": 22,
                    "test_trend": [22]},
        "backlog": {"total": 5, "done": 1, "remaining": 4},
        "agents": [{"name": "analyst", "description": "Analyzes"}],
    }
    html = dashboard_server.render_project_html(detail)
    assert "testproj" in html
    assert "22" in html  # test count
    assert "<!DOCTYPE html>" in html


# ── Multi-project dashboard ──

def test_dashboard_shows_multiple_projects(tmp_path):
    """Register 2 projects, dashboard HTML has both names."""
    p1 = tmp_path / "alpha"
    p2 = tmp_path / "beta"
    p1.mkdir()
    p2.mkdir()
    ctx1 = registry.register("alpha", p1)
    ctx1.ensure_dirs()
    ctx1.counter_file.write_text(json.dumps({"count": 3}))
    ctx2 = registry.register("beta", p2)
    ctx2.ensure_dirs()
    ctx2.counter_file.write_text(json.dumps({"count": 7}))

    projects = dashboard_server.get_projects_data()
    html = dashboard_server.render_dashboard_html(projects)
    assert "alpha" in html
    assert "beta" in html
    assert html.count("project-card") >= 2


def test_dashboard_project_links_work():
    """Clicking project card navigates to ?project=name."""
    projects = [
        {"name": "myproj", "sessions": 2, "path": "/tmp/mp", "created": "2026-01-01"},
    ]
    html = dashboard_server.render_dashboard_html(projects)
    assert "?project=myproj" in html


def test_dashboard_empty_state():
    """No projects shows helpful message."""
    html = dashboard_server.render_dashboard_html([])
    assert "No projects registered" in html
    assert "autoagent intake" in html


# ── Live panel / auto-refresh HTML ──

def test_project_html_has_live_panel():
    """Rendered project HTML includes an 'active-session' div for the live session panel."""
    detail = {
        "name": "testproj",
        "sessions": [{"session": 1, "type": "work", "summary": "Built thing",
                       "tests": {"after": 22}, "date": "2026-03-26"}],
        "metrics": {"total_sessions": 1, "work_sessions": 1, "latest_tests": 22,
                    "test_trend": [22]},
        "backlog": {"total": 5, "done": 1, "remaining": 4},
        "agents": [{"name": "analyst", "description": "Analyzes"}],
    }
    html = dashboard_server.render_project_html(detail)
    assert "active-session" in html, "Project HTML must include an 'active-session' div"


def test_project_html_has_auto_refresh():
    """Rendered project HTML includes refresh/SSE script for auto-updating."""
    detail = {
        "name": "testproj",
        "sessions": [{"session": 1, "type": "work", "summary": "Built thing",
                       "tests": {"after": 22}, "date": "2026-03-26"}],
        "metrics": {"total_sessions": 1, "work_sessions": 1, "latest_tests": 22,
                    "test_trend": [22]},
        "backlog": {"total": 5, "done": 1, "remaining": 4},
        "agents": [{"name": "analyst", "description": "Analyzes"}],
    }
    html = dashboard_server.render_project_html(detail)
    # Must have SSE EventSource for live updates AND a refresh/reload fallback
    assert "EventSource" in html, "Project HTML must include EventSource for SSE"
    assert "reload" in html, "Project HTML must include auto-refresh fallback"


def test_dashboard_js_has_eventsource():
    """Rendered project HTML includes EventSource JavaScript for live updates."""
    detail = {
        "name": "testproj",
        "sessions": [{"session": 1, "type": "work", "summary": "Built thing",
                       "tests": {"after": 22}, "date": "2026-03-26"}],
        "metrics": {"total_sessions": 1, "work_sessions": 1, "latest_tests": 22,
                    "test_trend": [22]},
        "backlog": {"total": 5, "done": 1, "remaining": 4},
        "agents": [{"name": "analyst", "description": "Analyzes"}],
    }
    html = dashboard_server.render_project_html(detail)
    assert "EventSource" in html
    assert "/events" in html


# ── Sparkline SVG ──

def test_sparkline_svg_empty_returns_empty():
    """Empty list returns empty string."""
    assert dashboard_server._sparkline_svg([]) == ""


def test_sparkline_svg_single_value_returns_empty():
    """Single value (< 2 points) returns empty string — can't draw a line."""
    assert dashboard_server._sparkline_svg([42]) == ""


def test_sparkline_svg_multiple_values_returns_valid_svg():
    """Multiple values produce an SVG with a polyline element."""
    result = dashboard_server._sparkline_svg([10, 20, 30, 25])
    assert result.startswith("<svg")
    assert "polyline" in result
    assert 'points="' in result
    # Should have 4 coordinate pairs
    points_str = result.split('points="')[1].split('"')[0]
    pairs = points_str.strip().split(" ")
    assert len(pairs) == 4


# ── Screenshot thumbnails in dashboard ──

def test_screenshot_shown_in_dashboard():
    """Sessions with screenshot_path render an img thumbnail in the session table."""
    detail = {
        "name": "testproj",
        "sessions": [
            {"session": 1, "type": "work", "summary": "Added dashboard",
             "tests": {"before": 10, "after": 15}, "date": "2026-03-28",
             "screenshot_path": "screenshots/session_1.png"},
            {"session": 2, "type": "work", "summary": "Backend fix",
             "tests": {"before": 15, "after": 18}, "date": "2026-03-28"},
        ],
        "metrics": {"total_sessions": 2, "work_sessions": 2, "latest_tests": 18,
                    "test_trend": [15, 18]},
        "backlog": {"total": 3, "done": 1, "remaining": 2},
        "agents": [],
    }
    html = dashboard_server.render_project_html(detail)
    # Session 1 has screenshot — should render an img or thumbnail link
    assert "screenshot" in html.lower(), "Dashboard should render screenshot for sessions that have one"
    assert "session_1.png" in html, "Dashboard should reference the screenshot file"


def test_screenshot_not_shown_when_absent():
    """Sessions without screenshot_path don't render any broken img tags."""
    detail = {
        "name": "testproj",
        "sessions": [
            {"session": 1, "type": "work", "summary": "Backend fix",
             "tests": {"before": 10, "after": 15}, "date": "2026-03-28"},
        ],
        "metrics": {"total_sessions": 1, "work_sessions": 1, "latest_tests": 15,
                    "test_trend": [15]},
        "backlog": {"total": 2, "done": 0, "remaining": 2},
        "agents": [],
    }
    html = dashboard_server.render_project_html(detail)
    assert "<img" not in html, "No img tags when no sessions have screenshots"
