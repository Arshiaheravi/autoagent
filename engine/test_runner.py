"""Tests for runner.py — session orchestration, status display, dashboard generation."""
import json
from pathlib import Path
from unittest.mock import patch, MagicMock, call

import pytest

import importlib.util as _ilu

_spec = _ilu.spec_from_file_location("runner_mod", Path(__file__).parent / "runner.py")
runner = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(runner)

from registry import ProjectContext


# ── Helpers ──────────────────────────────────────────────────────────

def _make_ctx(tmp_path, name="testproject"):
    """Build a minimal ProjectContext for testing."""
    project_root = tmp_path / "repo"
    project_root.mkdir(parents=True)
    agency_home = tmp_path / "agency"
    ctx = ProjectContext(name=name, project_root=project_root, agency_home=agency_home)
    ctx.ensure_dirs()
    ctx.project_file.write_text("# Test Project\n", encoding="utf-8")
    return ctx


# ── generate_dashboard ───────────────────────────────────────────────

def test_generate_dashboard_writes_html(tmp_path):
    """generate_dashboard replaces __SESSIONS_DATA__ in template and writes dashboard file."""
    ctx = _make_ctx(tmp_path)
    # Create template
    tpl_dir = ctx.agency_home / "templates"
    tpl_dir.mkdir(parents=True, exist_ok=True)
    tpl_file = tpl_dir / "dashboard.template.html"
    tpl_file.write_text("<html>__SESSIONS_DATA__</html>", encoding="utf-8")
    # Create sessions.json
    sessions = [{"session": 1, "summary": "test"}]
    ctx.sessions_file.write_text(json.dumps(sessions), encoding="utf-8")

    runner.generate_dashboard(ctx)

    assert ctx.dashboard_file.exists()
    content = ctx.dashboard_file.read_text(encoding="utf-8")
    assert "__SESSIONS_DATA__" not in content
    assert '"session": 1' in content


def test_generate_dashboard_no_sessions_file(tmp_path):
    """generate_dashboard does nothing when sessions.json is missing."""
    ctx = _make_ctx(tmp_path)
    runner.generate_dashboard(ctx)
    assert not ctx.dashboard_file.exists()


def test_generate_dashboard_no_template(tmp_path):
    """generate_dashboard does nothing when both template locations are missing."""
    ctx = _make_ctx(tmp_path)
    ctx.sessions_file.write_text("[]", encoding="utf-8")
    # Patch the V1 fallback path to a non-existent location
    with patch.object(runner.Path, "__new__", wraps=Path.__new__):
        # The function checks two template locations — override __file__ to break the fallback
        import types
        original_file = runner.__file__
        runner.__file__ = str(tmp_path / "nonexistent" / "runner.py")
        try:
            runner.generate_dashboard(ctx)
        finally:
            runner.__file__ = original_file
    assert not ctx.dashboard_file.exists()


# ── show_status ──────────────────────────────────────────────────────

def test_show_status_prints_project_name(tmp_path, capsys):
    """show_status output includes the project name."""
    ctx = _make_ctx(tmp_path)
    runner.show_status(ctx)
    out = capsys.readouterr().out
    assert "testproject" in out


def test_show_status_prints_budget(tmp_path, capsys):
    """show_status prints today's budget spend and limit."""
    ctx = _make_ctx(tmp_path)
    ctx.config["daily_limit_usd"] = 10.0
    from datetime import date
    today = str(date.today())
    ctx.budget_file.parent.mkdir(parents=True, exist_ok=True)
    ctx.budget_file.write_text(json.dumps({today: 2.5}), encoding="utf-8")

    runner.show_status(ctx)
    out = capsys.readouterr().out
    assert "2.5" in out


def test_show_status_handles_missing_budget(tmp_path, capsys):
    """show_status works when budget file doesn't exist."""
    ctx = _make_ctx(tmp_path)
    runner.show_status(ctx)
    out = capsys.readouterr().out
    assert "$0.00" in out or "0.0" in out


# ── run_project (test_mode) ──────────────────────────────────────────

def test_run_project_test_mode_prints_info(tmp_path, capsys):
    """run_project with test_mode=True prints dry run info and returns without running sessions."""
    ctx = _make_ctx(tmp_path)
    # Create minimal memory dir with a .md file
    (ctx.memory_dir / "backlog.md").write_text("# Backlog\n", encoding="utf-8")
    # Create a skill file
    (ctx.agency_home / "skills").mkdir(parents=True, exist_ok=True)
    (ctx.agency_home / "skills" / "coding.md").write_text("# Coding\n", encoding="utf-8")

    runner.run_project(ctx, test_mode=True)
    out = capsys.readouterr().out
    assert "DRY RUN" in out
    assert "testproject" in out
    assert "Everything looks good" in out


def test_run_project_test_mode_does_not_call_run_session(tmp_path):
    """run_project with test_mode=True never calls run_session or launch_with_retry."""
    ctx = _make_ctx(tmp_path)
    with patch.object(runner, "launch_with_retry") as mock_launch:
        runner.run_project(ctx, test_mode=True)
        mock_launch.assert_not_called()


# ── run_project (tasks_limit) ────────────────────────────────────────

def test_run_project_tasks_limit_stops_after_n(tmp_path, capsys):
    """run_project with tasks_limit=2 stops after 2 successful work sessions."""
    ctx = _make_ctx(tmp_path)

    with patch.object(runner, "budget_ok", return_value=True), \
         patch.object(runner, "launch_with_retry", return_value=True), \
         patch.object(runner, "generate_dashboard"), \
         patch.object(runner, "get_session_type", return_value="work"):
        runner.run_project(ctx, tasks_limit=2)

    out = capsys.readouterr().out
    assert "2 sessions completed" in out


def test_run_project_non_work_sessions_dont_count(tmp_path, capsys):
    """Non-work sessions (meta, brain) don't count toward tasks_limit."""
    ctx = _make_ctx(tmp_path)
    # First 2 calls return "meta", then "work" twice
    type_sequence = iter(["meta", "meta", "work", "work"])

    with patch.object(runner, "budget_ok", return_value=True), \
         patch.object(runner, "launch_with_retry", return_value=True), \
         patch.object(runner, "generate_dashboard"), \
         patch.object(runner, "get_session_type", side_effect=lambda n: next(type_sequence)):
        runner.run_project(ctx, tasks_limit=2)

    out = capsys.readouterr().out
    assert "2 sessions completed" in out
    # Counter file should show we ran 4 sessions total (2 meta + 2 work)
    counter = json.loads(ctx.counter_file.read_text())
    assert counter["count"] == 5  # started at 1, ran 4 sessions


def test_run_project_saves_counter(tmp_path):
    """run_project persists the session counter to counter_file after each session."""
    ctx = _make_ctx(tmp_path)

    with patch.object(runner, "budget_ok", return_value=True), \
         patch.object(runner, "launch_with_retry", return_value=True), \
         patch.object(runner, "generate_dashboard"), \
         patch.object(runner, "get_session_type", return_value="work"):
        runner.run_project(ctx, tasks_limit=1)

    counter = json.loads(ctx.counter_file.read_text())
    assert counter["count"] == 2  # started at 1, ran 1 session


def test_run_project_resumes_counter(tmp_path):
    """run_project resumes from persisted counter instead of starting at 1."""
    ctx = _make_ctx(tmp_path)
    ctx.counter_file.parent.mkdir(parents=True, exist_ok=True)
    ctx.counter_file.write_text(json.dumps({"count": 50}), encoding="utf-8")

    with patch.object(runner, "budget_ok", return_value=True), \
         patch.object(runner, "launch_with_retry", return_value=True) as mock_launch, \
         patch.object(runner, "generate_dashboard"), \
         patch.object(runner, "get_session_type", return_value="work"):
        runner.run_project(ctx, tasks_limit=1)

    # launch_with_retry should have been called with session_num=50
    assert mock_launch.call_args[0][2] == 50


def test_run_project_forced_type_overrides_schedule(tmp_path):
    """run_project with forced_type uses that type instead of get_session_type."""
    ctx = _make_ctx(tmp_path)

    with patch.object(runner, "budget_ok", return_value=True), \
         patch.object(runner, "launch_with_retry", return_value=True) as mock_launch, \
         patch.object(runner, "generate_dashboard"):
        # Use forced_type="work" so tasks_limit=1 stops after 1 session
        runner.run_project(ctx, tasks_limit=1, forced_type="work")

    assert mock_launch.call_args[0][1] == "work"
    # Verify get_session_type was NOT used (forced_type takes precedence)
    # The session type passed to launch_with_retry is the forced one
    assert mock_launch.call_count == 1


# ── run_continuous ───────────────────────────────────────────────────

def test_run_continuous_empty_contexts(capsys):
    """run_continuous prints message and returns immediately with empty list."""
    runner.run_continuous([])
    out = capsys.readouterr().out
    assert "No projects" in out


def test_run_continuous_round_robin(tmp_path):
    """run_continuous cycles through projects in round-robin order."""
    ctx1 = _make_ctx(tmp_path / "a", name="alpha")
    ctx2 = _make_ctx(tmp_path / "b", name="beta")

    call_log = []

    def fake_launch(ctx, stype, num, run_fn=None):
        call_log.append(ctx.name)
        if len(call_log) >= 4:
            raise KeyboardInterrupt  # stop after 4 calls
        return True

    with patch.object(runner, "budget_ok", return_value=True), \
         patch.object(runner, "launch_with_retry", side_effect=fake_launch), \
         patch.object(runner, "generate_dashboard"), \
         patch("time.sleep"):
        runner.run_continuous([ctx1, ctx2], cooldown=0)

    assert call_log == ["alpha", "beta", "alpha", "beta"]


def test_run_continuous_skips_over_budget(tmp_path):
    """run_continuous skips projects that are over budget."""
    ctx1 = _make_ctx(tmp_path / "a", name="alpha")
    ctx2 = _make_ctx(tmp_path / "b", name="beta")

    call_log = []
    call_count = [0]

    def fake_budget(ctx):
        # alpha is always over budget, beta is ok
        return ctx.name != "alpha"

    def fake_launch(ctx, stype, num, run_fn=None):
        call_log.append(ctx.name)
        call_count[0] += 1
        if call_count[0] >= 2:
            raise KeyboardInterrupt
        return True

    with patch.object(runner, "budget_ok", side_effect=fake_budget), \
         patch.object(runner, "launch_with_retry", side_effect=fake_launch), \
         patch.object(runner, "generate_dashboard"), \
         patch("time.sleep"):
        runner.run_continuous([ctx1, ctx2], cooldown=0)

    # Only beta should have been launched
    assert all(name == "beta" for name in call_log)


def test_run_continuous_cutoff_stops(tmp_path):
    """run_continuous with --until stops when the time is reached."""
    ctx = _make_ctx(tmp_path)

    # Simulate: _past_cutoff returns False first, then True
    call_count = [0]
    original_now = runner.datetime.now

    def fake_launch(ctx, stype, num, run_fn=None):
        call_count[0] += 1
        return True

    with patch.object(runner, "budget_ok", return_value=True), \
         patch.object(runner, "launch_with_retry", side_effect=fake_launch), \
         patch.object(runner, "generate_dashboard"), \
         patch("time.sleep"):
        # Use a cutoff time that's already past
        from datetime import datetime
        now = datetime.now()
        past_time = f"{now.hour:02d}:{now.minute:02d}"
        runner.run_continuous([ctx], cooldown=0, until=past_time)

    # Should have stopped immediately (0 sessions) due to cutoff
    assert call_count[0] == 0
