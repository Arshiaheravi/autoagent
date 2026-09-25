"""Tests for session_analytics.py — log_session_entry functional tests."""
import json
import threading
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import agency_db
from registry import ProjectContext
import session_analytics as sa


@pytest.fixture(autouse=True)
def _isolated_agency_db(tmp_path, monkeypatch):
    monkeypatch.setattr(agency_db, "_DB_PATH", tmp_path / "agency.db")
    monkeypatch.setattr(agency_db, "_local", threading.local())
    yield


# ── Helpers ──────────────────────────────────────────────────────────

def _make_ctx(tmp_path, name="testproj"):
    """Build a minimal ProjectContext for testing."""
    project_root = tmp_path / "repo"
    project_root.mkdir()
    agency_home = tmp_path / "agency"
    ctx = ProjectContext(name=name, project_root=project_root, agency_home=agency_home)
    ctx.ensure_dirs()
    ctx.project_file.write_text("# Test\n", encoding="utf-8")
    return ctx


def _mock_subprocess_run(git_log_msg="agent: built feature", git_diff_files="file.py\n"):
    """Return a side_effect that handles git log, git diff, and test commands."""
    def side_effect(cmd, **kwargs):
        mock = MagicMock()
        if isinstance(cmd, list) and "log" in cmd:
            mock.returncode = 0
            mock.stdout = git_log_msg
        elif isinstance(cmd, list) and "diff" in cmd:
            mock.returncode = 0
            mock.stdout = git_diff_files
        else:
            # test command — skip
            mock.returncode = 1
            mock.stdout = ""
        return mock
    return side_effect


# ── log_session_entry: writes JSON ─────────────────────────────────

def test_log_session_entry_writes_json(tmp_path):
    """log_session_entry creates sessions.json with correct entry structure."""
    ctx = _make_ctx(tmp_path)

    with patch.object(sa, "subprocess") as mock_sp:
        mock_sp.run.side_effect = _mock_subprocess_run(
            git_log_msg="agent: added health scoring",
            git_diff_files="services/health.py\ntests/test_health.py\n",
        )
        mock_sp.TimeoutExpired = TimeoutError
        sa.log_session_entry(ctx, session_num=42, session_type="work", success=True)

    assert ctx.sessions_file.exists()
    sessions = json.loads(ctx.sessions_file.read_text(encoding="utf-8"))
    assert len(sessions) == 1

    entry = sessions[0]
    assert entry["session"] == 42
    assert entry["type"] == "work"
    assert "health scoring" in entry["summary"]
    assert "services/health.py" in entry["files"]
    assert entry["tests"]["status"] in ("pass", "fail", "skip")
    db_sessions = agency_db.get_recent_sessions(ctx.name)
    assert len(db_sessions) == 1
    assert db_sessions[0]["session_num"] == 42


def test_log_session_entry_skips_duplicate(tmp_path):
    """If session_num already exists in sessions.json, entry is not duplicated."""
    ctx = _make_ctx(tmp_path)

    # Pre-populate with session 10
    existing = [{"session": 10, "type": "work", "summary": "already logged"}]
    ctx.sessions_file.write_text(json.dumps(existing), encoding="utf-8")

    with patch.object(sa, "subprocess") as mock_sp:
        mock_sp.run.side_effect = _mock_subprocess_run()
        mock_sp.TimeoutExpired = TimeoutError
        sa.log_session_entry(ctx, session_num=10, session_type="work", success=True)

    sessions = json.loads(ctx.sessions_file.read_text(encoding="utf-8"))
    assert len(sessions) == 1  # no duplicate added
    assert sessions[0]["summary"] == "already logged"
    assert agency_db.get_recent_sessions(ctx.name)[0]["session_num"] == 10


def test_log_session_entry_ghost_note(tmp_path):
    """When success=False but git commit exists, entry is marked as GHOST."""
    ctx = _make_ctx(tmp_path)

    with patch.object(sa, "subprocess") as mock_sp:
        mock_sp.run.side_effect = _mock_subprocess_run(
            git_log_msg="agent: partial work",
        )
        mock_sp.TimeoutExpired = TimeoutError
        sa.log_session_entry(ctx, session_num=7, session_type="work", success=False)

    sessions = json.loads(ctx.sessions_file.read_text(encoding="utf-8"))
    assert len(sessions) == 1
    assert "GHOST" in sessions[0].get("notes", "")


def test_log_session_entry_strips_agent_prefix(tmp_path):
    """Git commit messages with 'agent: ' prefix get cleaned in summary."""
    ctx = _make_ctx(tmp_path)

    with patch.object(sa, "subprocess") as mock_sp:
        mock_sp.run.side_effect = _mock_subprocess_run(
            git_log_msg="agent: added new feature",
        )
        mock_sp.TimeoutExpired = TimeoutError
        sa.log_session_entry(ctx, session_num=1, session_type="work", success=True)

    sessions = json.loads(ctx.sessions_file.read_text(encoding="utf-8"))
    # Should strip "agent: " prefix
    assert sessions[0]["summary"] == "added new feature"


def test_log_session_entry_no_sessions_file(tmp_path):
    """When sessions.json doesn't exist, log_session_entry creates it."""
    ctx = _make_ctx(tmp_path)
    assert not ctx.sessions_file.exists()

    with patch.object(sa, "subprocess") as mock_sp:
        mock_sp.run.side_effect = _mock_subprocess_run()
        mock_sp.TimeoutExpired = TimeoutError
        sa.log_session_entry(ctx, session_num=1, session_type="meta", success=True)

    assert ctx.sessions_file.exists()
    sessions = json.loads(ctx.sessions_file.read_text(encoding="utf-8"))
    assert len(sessions) == 1
    assert sessions[0]["type"] == "meta"


# ── compute_task_impact_score ─────────────────────────────────

def test_log_session_entry_includes_impact_score(tmp_path):
    """log_session_entry writes impact_score into the session entry."""
    ctx = _make_ctx(tmp_path)

    with patch.object(sa, "subprocess") as mock_sp:
        mock_sp.run.side_effect = _mock_subprocess_run(
            git_log_msg="agent: added tests",
        )
        mock_sp.TimeoutExpired = TimeoutError
        sa.log_session_entry(ctx, session_num=1, session_type="work", success=True)

    sessions = json.loads(ctx.sessions_file.read_text(encoding="utf-8"))
    assert "impact_score" in sessions[0]
    assert 0 <= sessions[0]["impact_score"] <= 10


# ── compute_task_impact_score ─────────────────────────────────

def test_task_impact_score_perfect():
    """All positive signals → maximum score 10."""
    score = sa.compute_task_impact_score(
        tests_added=5, quality_delta=30, commit_produced=True, regressions=0,
    )
    assert score == 10


def test_task_impact_score_zero():
    """No tests, no quality change, no commit, regressions → 0."""
    score = sa.compute_task_impact_score(
        tests_added=0, quality_delta=0, commit_produced=False, regressions=3,
    )
    assert score == 0


def test_task_impact_score_tests_only():
    """Tests added but no commit, no quality change → tests_added points only."""
    score = sa.compute_task_impact_score(
        tests_added=3, quality_delta=0, commit_produced=False, regressions=0,
    )
    # tests_added=3 → 2 pts, quality_delta=0 → 0, commit=False → 0, no_regressions → 2
    assert score == 4


def test_task_impact_score_commit_only():
    """Commit produced but nothing else notable → commit + no_regressions points."""
    score = sa.compute_task_impact_score(
        tests_added=0, quality_delta=0, commit_produced=True, regressions=0,
    )
    # tests=0 → 0, quality=0 → 0, commit=True → 2, no_regressions → 2
    assert score == 4


def test_task_impact_score_regressions_reduce():
    """Regressions take away the no_regressions bonus."""
    score = sa.compute_task_impact_score(
        tests_added=5, quality_delta=20, commit_produced=True, regressions=1,
    )
    # tests=3, quality=2, commit=2, regressions → 0 (not 2)
    assert score == 7


def test_task_impact_score_clamped_at_10():
    """Even with extreme values, score never exceeds 10."""
    score = sa.compute_task_impact_score(
        tests_added=100, quality_delta=100, commit_produced=True, regressions=0,
    )
    assert score == 10


def test_task_impact_score_negative_quality():
    """Negative quality_delta → 0 quality points (not negative)."""
    score = sa.compute_task_impact_score(
        tests_added=0, quality_delta=-20, commit_produced=True, regressions=0,
    )
    # tests=0, quality=0, commit=2, no_regressions=2
    assert score == 4


# ── format_session_label ────────────────────────────────────

def test_format_session_label_full():
    """All fields present → rich label."""
    label = sa.format_session_label(
        session_num=192, agent="frontend", task="Fix mobile overflow",
        files_count=3, test_count=12, success=True,
    )
    assert "#192" in label
    assert "[frontend]" in label
    assert "Fix mobile overflow" in label
    assert "3 files" in label
    assert "12 tests" in label
    assert "OK" in label


def test_format_session_label_no_agent():
    """Missing agent → no bracket section."""
    label = sa.format_session_label(
        session_num=10, agent="", task="Add tests",
        files_count=1, test_count=5, success=True,
    )
    assert "#10" in label
    assert "[]" not in label
    assert "Add tests" in label


def test_format_session_label_failure():
    """success=False → FAIL in label."""
    label = sa.format_session_label(
        session_num=5, agent="coder", task="Break things",
        files_count=0, test_count=0, success=False,
    )
    assert "FAIL" in label
    assert "OK" not in label


def test_format_session_label_no_task():
    """No task name → generic fallback."""
    label = sa.format_session_label(
        session_num=7, agent="", task="",
        files_count=0, test_count=0, success=True,
    )
    assert "#7" in label


def test_format_session_label_truncates_long_task():
    """Very long task name gets truncated."""
    long_task = "A" * 200
    label = sa.format_session_label(
        session_num=1, agent="", task=long_task,
        files_count=0, test_count=0, success=True,
    )
    assert len(label) < 250


def test_log_session_entry_reads_current_task(tmp_path):
    """log_session_entry extracts task name from current_task.md for richer summary."""
    ctx = _make_ctx(tmp_path)
    # Write a current_task.md with a task name
    (ctx.memory_dir / "current_task.md").write_text(
        "# Current Task: Fix mobile overflow\n- [x] Step 1\n", encoding="utf-8"
    )

    with patch.object(sa, "subprocess") as mock_sp:
        mock_sp.run.side_effect = _mock_subprocess_run(
            git_log_msg="agent: fix mobile overflow",
            git_diff_files="app.py\nstyle.css\n",
        )
        mock_sp.TimeoutExpired = TimeoutError
        sa.log_session_entry(ctx, session_num=99, session_type="work", success=True,
                             agent="frontend")

    sessions = json.loads(ctx.sessions_file.read_text(encoding="utf-8"))
    entry = sessions[0]
    assert entry["agent"] == "frontend"
    assert entry["task"] == "Fix mobile overflow"
    assert entry["session"] == 99


# ── _parse_test_command (shell=True removal) ────────────────

def test_parse_test_command_splits_cd_and_cmd():
    """'cd /some/dir && python3 -m pytest ...' → ('/some/dir', ['python3', '-m', 'pytest', ...])."""
    raw = 'cd /Users/me/repo/engine && python3 -m pytest test_foo.py test_bar.py -q'
    cwd, cmd_list = sa._parse_test_command(raw)
    assert cwd == "/Users/me/repo/engine"
    assert cmd_list == ["python3", "-m", "pytest", "test_foo.py", "test_bar.py", "-q"]


def test_parse_test_command_no_cd():
    """Plain command without cd → cwd=None, command split into list."""
    raw = "python3 -m pytest tests/ -q"
    cwd, cmd_list = sa._parse_test_command(raw)
    assert cwd is None
    assert cmd_list == ["python3", "-m", "pytest", "tests/", "-q"]


def test_parse_test_command_multiline_cd():
    """Multiline command with cd on first line."""
    raw = "cd /some/dir && python3 -m pytest test_a.py \\\ntest_b.py -q"
    cwd, cmd_list = sa._parse_test_command(raw)
    assert cwd == "/some/dir"
    assert "python3" in cmd_list


def test_log_session_entry_no_shell_true(tmp_path):
    """log_session_entry must NOT use shell=True for running tests."""
    ctx = _make_ctx(tmp_path)
    # Write PROJECT.md with a test command
    ctx.project_file.write_text(
        "### Test Command\n```\ncd /tmp && python3 -m pytest test_foo.py -q\n```\n",
        encoding="utf-8",
    )

    calls = []
    original_run = sa.subprocess.run

    def spy_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        mock = MagicMock()
        mock.returncode = 0
        mock.stdout = "1 passed"
        return mock

    with patch.object(sa.subprocess, "run", side_effect=spy_run):
        sa.log_session_entry(ctx, session_num=200, session_type="work", success=True)

    # Find the test command call (not git log/diff which are already list-based)
    test_calls = [(c, kw) for c, kw in calls if isinstance(c, list) and "pytest" in str(c)]
    shell_calls = [(c, kw) for c, kw in calls if kw.get("shell") is True]
    assert len(shell_calls) == 0, f"shell=True used in: {shell_calls}"
    assert len(test_calls) >= 1, "Test command should be called as a list"
