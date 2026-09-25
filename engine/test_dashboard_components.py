"""Tests for dashboard_components.py — replay HTML, comparison HTML, sparkline SVG."""
from dashboard_components import render_replay_html, render_comparison_html, _sparkline_svg


# ── render_replay_html ──────────────────────────────────────────────

def test_render_replay_html_produces_valid_html():
    """render_replay_html returns valid HTML with title, timeline, and event count."""
    events = [
        {"timestamp": "2026-03-31T10:00:00", "type": "session_start"},
        {"timestamp": "2026-03-31T10:01:00", "type": "tool_use", "action": "Read", "target": "file.py"},
        {"timestamp": "2026-03-31T10:02:00", "type": "session_end", "summary": "done"},
    ]
    html = render_replay_html("myproject", 42, events)

    assert "<!DOCTYPE html>" in html
    assert "Session #42 Replay" in html
    assert "myproject" in html
    assert "3 events" in html


def test_render_replay_html_error_event_has_error_class():
    """Events with error field get the replay-error CSS class."""
    events = [
        {"timestamp": "2026-03-31T10:00:00", "type": "tool_use", "action": "Bash",
         "target": "pytest", "error": "exit code 1"},
    ]
    html = render_replay_html("proj", 1, events)

    assert 'class="replay-event replay-error"' in html
    assert 'class="replay-error-msg"' in html
    assert "exit code 1" in html


def test_render_replay_html_no_error_no_error_class():
    """Events without error field do not get the replay-error CSS class."""
    events = [
        {"timestamp": "2026-03-31T10:00:00", "type": "tool_use", "action": "Read", "target": "f.py"},
    ]
    html = render_replay_html("proj", 1, events)

    assert 'class="replay-event replay-error"' not in html
    assert 'class="replay-error-msg"' not in html


def test_render_replay_html_extracts_time_from_iso():
    """Timestamps are trimmed to HH:MM:SS in the timeline."""
    events = [
        {"timestamp": "2026-03-31T14:30:45Z", "type": "session_start"},
    ]
    html = render_replay_html("proj", 1, events)

    assert "14:30:45" in html


def test_render_replay_html_empty_events():
    """render_replay_html handles empty event list gracefully."""
    html = render_replay_html("proj", 5, [])

    assert "Session #5 Replay" in html
    assert "0 events" in html


def test_render_replay_html_session_end_includes_summary():
    """session_end events include their summary in the description."""
    events = [
        {"timestamp": "2026-03-31T10:00:00", "type": "session_end", "summary": "all tests pass"},
    ]
    html = render_replay_html("proj", 1, events)

    assert "all tests pass" in html


# ── render_comparison_html ──────────────────────────────────────────

def test_render_comparison_html_with_multiple_projects():
    """render_comparison_html renders a table row per project with metrics."""
    projects = [
        {
            "name": "alpha",
            "metrics": {"total_sessions": 10, "latest_tests": 50, "avg_quality": 85, "test_trend": [40, 45, 50]},
            "backlog": {"total": 10, "done": 4},
        },
        {
            "name": "beta",
            "metrics": {"total_sessions": 5, "latest_tests": 20, "avg_quality": None, "test_trend": []},
            "backlog": {"total": 8, "done": 2},
        },
    ]
    html = render_comparison_html(projects)

    assert "alpha" in html
    assert "beta" in html
    assert "<table" in html
    # alpha: 10 sessions, 50 tests, quality 85, progress 40%
    assert ">10<" in html
    assert ">50" in html
    assert "85" in html
    assert "40%" in html
    # beta: quality is None → "—"
    assert "—" in html


def test_render_comparison_html_empty_list():
    """render_comparison_html with no projects renders header row only."""
    html = render_comparison_html([])

    assert "<table" in html
    assert "Project" in html
    assert "<tr>" in html


def test_render_comparison_html_includes_sparkline_when_enough_data():
    """Projects with 2+ test_trend values get an SVG sparkline."""
    projects = [
        {
            "name": "gamma",
            "metrics": {"total_sessions": 3, "latest_tests": 30, "test_trend": [10, 20, 30]},
            "backlog": {"total": 5, "done": 1},
        },
    ]
    html = render_comparison_html(projects)

    assert "<svg" in html
    assert "polyline" in html


def test_render_comparison_html_no_sparkline_for_single_value():
    """Projects with <2 test_trend values get no sparkline."""
    projects = [
        {
            "name": "delta",
            "metrics": {"total_sessions": 1, "latest_tests": 5, "test_trend": [5]},
            "backlog": {"total": 3, "done": 0},
        },
    ]
    html = render_comparison_html(projects)

    assert "<svg" not in html


# ── _sparkline_svg ──────────────────────────────────────────────────

def test_sparkline_svg_empty_returns_empty():
    """_sparkline_svg returns empty string for empty input."""
    assert _sparkline_svg([]) == ""


def test_sparkline_svg_single_value_returns_empty():
    """_sparkline_svg returns empty string for a single value (needs 2+ for a line)."""
    assert _sparkline_svg([42]) == ""


def test_sparkline_svg_two_values_produces_svg():
    """_sparkline_svg with 2 values returns valid SVG with a polyline."""
    svg = _sparkline_svg([10, 20])

    assert svg.startswith("<svg")
    assert "polyline" in svg
    assert "points=" in svg


def test_sparkline_svg_correct_point_count():
    """_sparkline_svg generates one point per value in the polyline."""
    svg = _sparkline_svg([1, 2, 3, 4, 5])

    # Extract points string
    import re
    m = re.search(r'points="([^"]+)"', svg)
    assert m
    points = m.group(1).strip().split()
    assert len(points) == 5


# ── render_agents_html ──────────────────────────────────────────────

def test_render_agents_html_produces_valid_html():
    """render_agents_html returns full HTML page with agent table and bar chart."""
    from dashboard_components import render_agents_html

    agents = [
        {"name": "coder", "project": "proj1", "total_sessions": 10,
         "successful": 8, "failed": 2, "success_rate": 0.80, "avg_quality": 85.0},
        {"name": "tester", "project": "proj1", "total_sessions": 5,
         "successful": 5, "failed": 0, "success_rate": 1.0, "avg_quality": 92.0},
    ]
    html = render_agents_html(agents)

    assert "<!DOCTYPE html>" in html
    assert "Agent Performance" in html
    assert "coder" in html
    assert "tester" in html
    assert "80%" in html
    assert "100%" in html
    assert "<table" in html


def test_render_agents_html_bar_chart():
    """render_agents_html includes visual bar elements proportional to session count."""
    from dashboard_components import render_agents_html

    agents = [
        {"name": "builder", "project": "p", "total_sessions": 20,
         "successful": 15, "failed": 5, "success_rate": 0.75, "avg_quality": 70.0},
    ]
    html = render_agents_html(agents)

    # Bar chart uses inline width style for visual representation
    assert "width:" in html
    assert "builder" in html


def test_render_agents_html_empty_agents():
    """render_agents_html with no agents shows empty state message."""
    from dashboard_components import render_agents_html

    html = render_agents_html([])

    assert "<!DOCTYPE html>" in html
    assert "No agent data" in html


def test_render_agents_html_handles_missing_quality():
    """render_agents_html handles agents with None avg_quality gracefully."""
    from dashboard_components import render_agents_html

    agents = [
        {"name": "newbie", "project": "p", "total_sessions": 1,
         "successful": 1, "failed": 0, "success_rate": 1.0, "avg_quality": None},
    ]
    html = render_agents_html(agents)

    assert "newbie" in html
    assert "100%" in html
