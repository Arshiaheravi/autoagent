"""Tests for launcher.py — self-healing session retry with diagnostic context."""
import json
import subprocess
import textwrap
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

import importlib.util
_spec = importlib.util.spec_from_file_location(
    "launcher_v2", Path(__file__).parent / "launcher.py"
)
launcher = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(launcher)


# ── Helpers ──────────────────────────────────────────────────────────

def _make_ctx(tmp_path, name="testproject"):
    """Build a minimal ProjectContext for testing."""
    from registry import ProjectContext
    project_root = tmp_path / "repo"
    project_root.mkdir()
    agency_home = tmp_path / "agency"
    ctx = ProjectContext(name=name, project_root=project_root, agency_home=agency_home)
    ctx.ensure_dirs()
    # Write minimal PROJECT.md
    ctx.project_file.write_text("# Test Project\n", encoding="utf-8")
    return ctx


# ── build_repair_prompt ─────────────────────────────────────────────


def test_build_repair_prompt_contains_failure_reason():
    """The repair prompt must include the failure reason for Claude to diagnose."""
    prompt = launcher.build_repair_prompt(
        failure_reason="PRE-PUSH GATE: 3 tests failed",
        session_num=42,
        project_name="cultivOS",
    )
    assert "PRE-PUSH GATE: 3 tests failed" in prompt
    assert "42" in prompt
    assert "cultivOS" in prompt


def test_build_repair_prompt_includes_fix_instructions():
    """The repair prompt must instruct Claude to fix and verify."""
    prompt = launcher.build_repair_prompt(
        failure_reason="tests red",
        session_num=1,
        project_name="myapp",
    )
    assert "fix" in prompt.lower()
    assert "test" in prompt.lower()


def test_build_repair_prompt_limits_failure_reason_length():
    """Very long failure reasons are truncated to prevent prompt bloat."""
    long_reason = "x" * 10000
    prompt = launcher.build_repair_prompt(
        failure_reason=long_reason,
        session_num=1,
        project_name="proj",
    )
    # Should not contain the full 10000 chars
    assert len(prompt) < 8000


# ── launch_with_retry ───────────────────────────────────────────────


def test_launch_success_no_retry(tmp_path):
    """When run_fn succeeds on first try, no retry is attempted."""
    ctx = _make_ctx(tmp_path)
    call_count = {"n": 0}

    def mock_run(c, st, sn):
        call_count["n"] += 1
        return True

    result = launcher.launch_with_retry(
        ctx, "work", 1, run_fn=mock_run, max_retries=2
    )
    assert result is True
    assert call_count["n"] == 1


def test_launch_retries_on_failure(tmp_path):
    """When run_fn fails first, launcher repairs then retries once."""
    ctx = _make_ctx(tmp_path)
    calls = []

    def mock_run(c, st, sn, **kw):
        calls.append(sn)
        # Fail first attempt, succeed on retry after repair
        return len(calls) >= 2

    with patch.object(launcher, "run_repair_session", return_value=True):
        result = launcher.launch_with_retry(
            ctx, "work", 10, run_fn=mock_run, max_retries=3
        )
    assert result is True
    assert len(calls) == 2


def test_launch_gives_up_after_max_retries(tmp_path):
    """After repair + retry fails, launcher returns False."""
    ctx = _make_ctx(tmp_path)
    calls = []

    def always_fail(c, st, sn, **kw):
        calls.append(1)
        return False

    with patch.object(launcher, "run_repair_session", return_value=True):
        result = launcher.launch_with_retry(
            ctx, "work", 5, run_fn=always_fail, max_retries=2
        )
    assert result is False
    # Original attempt + 1 retry after repair = 2 calls (no agent files = no fallback chain)
    assert len(calls) == 2


def test_launch_logs_heal_attempts(tmp_path):
    """Each retry attempt is logged to memory/self_heal_log.md."""
    ctx = _make_ctx(tmp_path)
    call_count = {"n": 0}

    def fail_then_pass(c, st, sn):
        call_count["n"] += 1
        return call_count["n"] >= 2

    with patch.object(launcher, "run_repair_session", return_value=True):
        launcher.launch_with_retry(
            ctx, "work", 7, run_fn=fail_then_pass, max_retries=2
        )

    heal_log = ctx.memory_dir / "self_heal_log.md"
    assert heal_log.exists()
    content = heal_log.read_text(encoding="utf-8")
    assert "Attempt 1" in content
    assert "session #7" in content.lower() or "#7" in content


def test_launch_skips_retry_for_non_work_sessions(tmp_path):
    """Meta/brain/deep sessions don't get retried — only work sessions."""
    ctx = _make_ctx(tmp_path)

    def always_fail(c, st, sn):
        return False

    result = launcher.launch_with_retry(
        ctx, "meta", 5, run_fn=always_fail, max_retries=2
    )
    assert result is False
    # No heal log should be written for non-work sessions
    heal_log = ctx.memory_dir / "self_heal_log.md"
    assert not heal_log.exists()


# ── run_repair_session ──────────────────────────────────────────────


def test_run_repair_session_calls_subprocess(tmp_path):
    """run_repair_session spawns Claude CLI with the repair prompt."""
    ctx = _make_ctx(tmp_path)

    with patch.object(launcher, "subprocess") as mock_mod:
        mock_mod.run.return_value = MagicMock(returncode=0, stdout="FIXED")
        mock_mod.TimeoutExpired = subprocess.TimeoutExpired
        result = launcher.run_repair_session(
            ctx, "tests failed", session_num=3
        )
    assert result is True
    assert mock_mod.run.called
    # Check Claude was invoked
    call_args = mock_mod.run.call_args
    cmd = call_args[0][0]
    assert any("claude" in str(c).lower() for c in cmd)


def test_run_repair_session_returns_false_on_failure(tmp_path):
    """If the repair session fails (non-zero exit), returns False."""
    ctx = _make_ctx(tmp_path)

    with patch.object(launcher, "subprocess") as mock_mod:
        mock_mod.run.return_value = MagicMock(returncode=1, stdout="COULD_NOT_FIX")
        mock_mod.TimeoutExpired = subprocess.TimeoutExpired
        result = launcher.run_repair_session(
            ctx, "constraint violation", session_num=5
        )
    assert result is False


# ── launch_parallel ────────────────────────────────────────────────


def _backlog_3_independent_1_dependent():
    """Backlog: T1, T2, T3 independent; T4 depends on T1."""
    return textwrap.dedent("""\
        - [ ] [T1] Build login page [agent: frontend]
        - [ ] [T2] Add user model [agent: backend]
        - [ ] [T3] Write README [agent: docs]
        - [ ] [T4] Integration tests (depends: T1)
    """)


def test_parallel_batch_detection(tmp_path):
    """3 independent + 1 dependent task → first batch has 3 tasks."""
    ctx = _make_ctx(tmp_path)
    backlog = ctx.memory_dir / "backlog.md"
    backlog.write_text(_backlog_3_independent_1_dependent(), encoding="utf-8")

    # Mock run_session and worktree functions — we only test batch detection
    with patch.object(launcher, "launch_with_retry", return_value=True), \
         patch("worktree.create_worktree") as mock_create, \
         patch("worktree.merge_worktree", return_value=True), \
         patch("worktree.cleanup_worktree"), \
         patch("run.run_session", return_value=True) as mock_run:
        mock_create.return_value = MagicMock(
            worktree_dir=tmp_path / "wt", branch_name="agent/x/s1"
        )
        results = launcher.launch_parallel(ctx, session_num=100, max_parallel=3)

    # First batch should contain exactly T1, T2, T3 (all independent)
    task_names = [r["task"] for r in results]
    assert len(results) == 3
    assert "Build login page" in task_names
    assert "Add user model" in task_names
    assert "Write README" in task_names


def test_parallel_worktree_lifecycle(tmp_path):
    """Multi-task batch: creates worktree per task, runs, merges, cleans up."""
    ctx = _make_ctx(tmp_path)
    backlog = ctx.memory_dir / "backlog.md"
    backlog.write_text(textwrap.dedent("""\
        - [ ] [T1] Task A [agent: alpha]
        - [ ] [T2] Task B [agent: beta]
    """), encoding="utf-8")

    fake_ws = MagicMock()
    fake_ws.worktree_dir = tmp_path / "wt"
    fake_ws.branch_name = "agent/alpha/s100"

    with patch("worktree.create_worktree", return_value=fake_ws) as mock_create, \
         patch("worktree.merge_worktree", return_value=True) as mock_merge, \
         patch("worktree.cleanup_worktree") as mock_cleanup, \
         patch("run.run_session", return_value=True) as mock_run:
        results = launcher.launch_parallel(ctx, session_num=100, max_parallel=3)

    # 2 tasks → 2 worktrees created, 2 sessions run, 2 merges, 2 cleanups
    assert mock_create.call_count == 2
    assert mock_run.call_count == 2
    assert mock_merge.call_count == 2
    assert mock_cleanup.call_count == 2
    assert all(r["success"] for r in results)


def test_parallel_single_task_no_worktree(tmp_path):
    """Single ready task uses launch_with_retry, no worktree created."""
    ctx = _make_ctx(tmp_path)
    backlog = ctx.memory_dir / "backlog.md"
    backlog.write_text("- [ ] [T1] Solo task\n", encoding="utf-8")

    with patch.object(launcher, "launch_with_retry", return_value=True) as mock_lwr, \
         patch("worktree.create_worktree") as mock_create:
        results = launcher.launch_parallel(ctx, session_num=50)

    assert len(results) == 1
    assert results[0]["success"] is True
    assert results[0]["task"] == "Solo task"
    mock_lwr.assert_called_once()
    mock_create.assert_not_called()


def test_parallel_empty_backlog(tmp_path):
    """No backlog file → returns empty list."""
    ctx = _make_ctx(tmp_path)
    # No backlog.md written
    results = launcher.launch_parallel(ctx, session_num=1)
    assert results == []


def test_parallel_cyclic_graph_returns_empty(tmp_path):
    """Cyclic dependencies → returns empty list (sequential fallback)."""
    ctx = _make_ctx(tmp_path)
    backlog = ctx.memory_dir / "backlog.md"
    backlog.write_text(textwrap.dedent("""\
        - [ ] [T1] Task A (depends: T2)
        - [ ] [T2] Task B (depends: T1)
    """), encoding="utf-8")

    results = launcher.launch_parallel(ctx, session_num=1)
    assert results == []
