#!/usr/bin/env python3
"""Tests for dashboard_html.py — extracted HTML rendering functions."""
import pytest


@pytest.fixture(autouse=True)
def setup_agency(isolated_agency_home):
    yield


# ── Render project detail ──

def test_dashboard_html_renders_project():
    """render_project_html returns valid HTML with the project name."""
    import dashboard_html

    detail = {
        "name": "myproject",
        "sessions": [{"session": 1, "type": "work", "summary": "Built API",
                       "tests": {"after": 22}, "date": "2026-03-26"}],
        "metrics": {"total_sessions": 1, "work_sessions": 1, "latest_tests": 22,
                    "test_trend": [22]},
        "backlog": {"total": 5, "done": 1, "remaining": 4},
        "agents": [{"name": "architect", "description": "Builds systems"}],
    }
    html = dashboard_html.render_project_html(detail)
    assert "<!DOCTYPE html>" in html
    assert "myproject" in html
    assert "22" in html  # test count visible
    assert "architect" in html  # agent badge rendered


# ── Render overview ──

def test_dashboard_html_renders_overview():
    """render_dashboard_html includes all registered projects."""
    import dashboard_html

    projects = [
        {"name": "alpha", "sessions": 3, "path": "/tmp/a", "created": "2026-01-01"},
        {"name": "beta", "sessions": 7, "path": "/tmp/b", "created": "2026-02-01"},
    ]
    html = dashboard_html.render_dashboard_html(projects)
    assert "<!DOCTYPE html>" in html
    assert "alpha" in html
    assert "beta" in html
    assert html.count("project-card") >= 2


# ── Sparkline SVG ──

def test_sparkline_svg_values():
    """_sparkline_svg returns valid SVG with correct polyline point count."""
    import dashboard_html

    result = dashboard_html._sparkline_svg([10, 20, 30, 25, 40])
    assert result.startswith("<svg")
    assert "polyline" in result
    assert 'points="' in result
    # Should have 5 coordinate pairs
    points_str = result.split('points="')[1].split('"')[0]
    pairs = points_str.strip().split(" ")
    assert len(pairs) == 5


# ── Customer-facing plain language dashboard ──

def _make_customer_detail():
    """Helper: project detail with sessions, done.md features, and backlog."""
    return {
        "name": "recipe-app",
        "sessions": [
            {"session": 1, "type": "work", "summary": "Your users can now log in and create accounts",
             "tests": {"before": 0, "after": 12}, "date": "2026-03-26"},
            {"session": 2, "type": "work", "summary": "Recipe search is live — find any dish by ingredient",
             "tests": {"before": 12, "after": 25}, "date": "2026-03-26"},
            {"session": 3, "type": "meta", "summary": "Improved how the agent picks tasks",
             "tests": {"before": 25, "after": 25}, "date": "2026-03-26"},
            {"session": 4, "type": "work", "summary": "Shopping list feature is ready — add ingredients with one tap",
             "tests": {"before": 25, "after": 40}, "date": "2026-03-27"},
        ],
        "metrics": {"total_sessions": 4, "work_sessions": 3, "latest_tests": 40,
                    "test_trend": [12, 25, 25, 40]},
        "backlog": {"total": 10, "done": 4, "remaining": 6},
        "agents": [{"name": "chef-designer", "description": "Designs recipe UI"}],
        "features": [
            "User login and accounts",
            "Recipe search by ingredient",
            "Shopping list with one-tap add",
        ],
    }


def test_project_view_shows_plain_language():
    """Dashboard shows session summaries as plain-language milestones, not technical."""
    import dashboard_html
    detail = _make_customer_detail()
    html = dashboard_html.render_project_html(detail)
    # Should show user-facing milestone language
    assert "Your users can now log in" in html or "log in" in html.lower()
    assert "Recipe search is live" in html or "recipe search" in html.lower()
    # Should NOT show developer-style summaries
    assert "auth endpoints" not in html.lower()
    assert "CRUD" not in html


def test_project_view_shows_progress_percent():
    """Dashboard shows backlog progress as a human-readable percentage."""
    import dashboard_html
    detail = _make_customer_detail()
    html = dashboard_html.render_project_html(detail)
    # 4 done out of 10 total = 40%
    assert "40%" in html


def test_project_view_shows_feature_names():
    """Dashboard lists completed features by name from the features list, not commit hashes."""
    import dashboard_html
    detail = _make_customer_detail()
    html = dashboard_html.render_project_html(detail)
    # Features should appear as named items
    assert "User login and accounts" in html
    assert "Recipe search by ingredient" in html
    assert "Shopping list" in html


def test_project_view_hides_developer_jargon():
    """Dashboard HTML must not contain developer jargon terms."""
    import dashboard_html
    detail = _make_customer_detail()
    html = dashboard_html.render_project_html(detail)
    import re
    jargon_terms = ["endpoint", "middleware", "fixture", "migration",
                    "refactor", "subprocess", "stderr", "stdout"]
    for term in jargon_terms:
        # Use word boundary to avoid false positives (e.g. "transform" matching "orm")
        assert not re.search(r'\b' + re.escape(term) + r'\b', html, re.IGNORECASE), \
            f"Dashboard contains developer jargon: '{term}'"


# ── Multi-project comparison table ──

def _make_comparison_projects():
    """Helper: 3 projects with varying metrics for comparison testing."""
    return [
        {
            "name": "alpha",
            "metrics": {"total_sessions": 10, "latest_tests": 50, "test_trend": [10, 20, 30, 40, 50], "avg_quality": 72},
            "backlog": {"total": 8, "done": 5, "remaining": 3},
        },
        {
            "name": "beta",
            "metrics": {"total_sessions": 25, "latest_tests": 120, "test_trend": [30, 60, 90, 100, 120], "avg_quality": 85},
            "backlog": {"total": 12, "done": 9, "remaining": 3},
        },
        {
            "name": "gamma",
            "metrics": {"total_sessions": 3, "latest_tests": 15, "test_trend": [5, 10, 15], "avg_quality": None},
            "backlog": {"total": 6, "done": 1, "remaining": 5},
        },
    ]


def test_comparison_table_renders():
    """When 3+ projects exist, render_comparison_html produces an HTML table with project rows and metric columns."""
    import dashboard_html
    projects = _make_comparison_projects()
    html = dashboard_html.render_comparison_html(projects)
    assert "<table" in html
    # All 3 project names in the table
    assert "alpha" in html
    assert "beta" in html
    assert "gamma" in html
    # Metric columns: sessions, tests, quality, progress
    assert "50" in html  # alpha latest_tests
    assert "120" in html  # beta latest_tests
    assert "85" in html  # beta avg_quality
    # Table rows — one per project (header + 3 data rows)
    assert html.count("<tr") >= 4


def test_comparison_sparklines():
    """Each project row in the comparison table includes a sparkline SVG for test growth."""
    import dashboard_html
    projects = _make_comparison_projects()
    html = dashboard_html.render_comparison_html(projects)
    # Each project with 2+ trend points should have an SVG sparkline
    assert html.count("<svg") >= 2  # alpha and beta have 5-point trends
    assert "polyline" in html


# ── Component extraction tests ──

def test_comparison_renders_from_components():
    """render_comparison_html can be imported from dashboard_components directly."""
    import dashboard_components
    projects = _make_comparison_projects()
    html = dashboard_components.render_comparison_html(projects)
    assert "<table" in html
    assert "alpha" in html
    assert "beta" in html
    # Also verify sparkline is importable from components
    svg = dashboard_components._sparkline_svg([10, 20, 30])
    assert "<svg" in svg


def test_dashboard_html_under_300_lines():
    """dashboard_html.py must stay under 300 lines after the split."""
    from pathlib import Path
    src = Path(__file__).resolve().parent / "dashboard_html.py"
    line_count = len(src.read_text().splitlines())
    assert line_count <= 300, f"dashboard_html.py is {line_count} lines — must be ≤300"
