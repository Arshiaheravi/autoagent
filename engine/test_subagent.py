"""Tests for subagent.py — isolated subagent spawning and parallel execution."""
import json
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock
from dataclasses import dataclass

import subagent
from subagent import (
    SubagentResult, _find_claude, build_subagent_prompt,
    spawn_subagent, spawn_parallel_subagents,
)


# --------------- _find_claude ---------------

def test_find_claude_found_on_path():
    """_find_claude returns the path from shutil.which if available."""
    with patch("subagent.shutil.which", return_value="/usr/local/bin/claude"):
        assert _find_claude() == "/usr/local/bin/claude"


def test_find_claude_not_found():
    """_find_claude returns 'claude' as fallback when not found."""
    with patch("subagent.shutil.which", return_value=None):
        with patch("subagent.sys.platform", "darwin"):
            assert _find_claude() == "claude"


def test_find_claude_windows_fallback():
    """_find_claude checks APPDATA/npm on Windows."""
    with patch("subagent.shutil.which", return_value=None):
        with patch("subagent.sys.platform", "win32"):
            with patch("subagent.os.environ", {"APPDATA": "/fake"}):
                with patch("subagent.os.path.exists", return_value=True):
                    result = _find_claude()
                    assert "claude.cmd" in result


# --------------- build_subagent_prompt ---------------

def _make_ctx(tmp_path):
    """Create a minimal ProjectContext for testing."""
    from registry import ProjectContext
    agency_home = tmp_path / "agency"
    agency_home.mkdir()
    (agency_home / "templates").mkdir(parents=True)
    (agency_home / "projects" / "testproj").mkdir(parents=True)
    return ProjectContext(name="testproj", project_root=tmp_path,
                          agency_home=agency_home)


def test_build_subagent_prompt_includes_task(tmp_path):
    """build_subagent_prompt includes the task text in the output."""
    ctx = _make_ctx(tmp_path)
    with patch("orchestrator.build_agent_boot_prompt", return_value="BOOT"):
        prompt = build_subagent_prompt("Fix the tests", "tester", ctx)

    assert "Fix the tests" in prompt
    assert "SUBAGENT TASK" in prompt


def test_build_subagent_prompt_includes_parent_context(tmp_path):
    """build_subagent_prompt includes parent context when provided."""
    ctx = _make_ctx(tmp_path)
    with patch("orchestrator.build_agent_boot_prompt", return_value="BOOT"):
        prompt = build_subagent_prompt(
            "Write tests", "tester", ctx,
            parent_context="The module uses async IO"
        )

    assert "The module uses async IO" in prompt


def test_build_subagent_prompt_no_parent_context(tmp_path):
    """build_subagent_prompt omits parent context line when empty."""
    ctx = _make_ctx(tmp_path)
    with patch("orchestrator.build_agent_boot_prompt", return_value="BOOT"):
        prompt = build_subagent_prompt("Write tests", None, ctx)

    assert "Context from parent agent:" not in prompt


# --------------- spawn_subagent ---------------

def test_spawn_subagent_success(tmp_path):
    """spawn_subagent returns success with parsed output on rc=0."""
    ctx = _make_ctx(tmp_path)
    stream_output = "\n".join([
        json.dumps({"type": "assistant", "message": {"content": [
            {"type": "text", "text": "Done!"}
        ]}}),
        json.dumps({"type": "result", "cost_usd": 0.05}),
    ])

    fake_result = MagicMock(returncode=0, stdout=stream_output, stderr="")

    with patch("subagent.build_subagent_prompt", return_value="PROMPT"):
        with patch("subagent._find_claude", return_value="claude"):
            with patch("subagent.subprocess.run", return_value=fake_result):
                result = spawn_subagent(ctx, "Fix bug", agent_name="fixer")

    assert result.success is True
    assert result.agent_name == "fixer"
    assert result.cost_usd == 0.05
    assert "Done!" in result.output


def test_spawn_subagent_parses_file_changes(tmp_path):
    """spawn_subagent tracks files from Write/Edit tool_use blocks."""
    ctx = _make_ctx(tmp_path)
    stream_output = "\n".join([
        json.dumps({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Write", "input": {"file_path": "/a/b.py"}},
            {"type": "tool_use", "name": "Edit", "input": {"file_path": "/a/c.py"}},
            {"type": "tool_use", "name": "Write", "input": {"file_path": "/a/b.py"}},  # dup
        ]}}),
    ])
    fake_result = MagicMock(returncode=0, stdout=stream_output, stderr="")

    with patch("subagent.build_subagent_prompt", return_value="PROMPT"):
        with patch("subagent._find_claude", return_value="claude"):
            with patch("subagent.subprocess.run", return_value=fake_result):
                result = spawn_subagent(ctx, "task")

    assert result.files_changed == ["/a/b.py", "/a/c.py"]  # deduped


def test_spawn_subagent_timeout(tmp_path):
    """spawn_subagent returns error result on timeout."""
    ctx = _make_ctx(tmp_path)

    with patch("subagent.build_subagent_prompt", return_value="PROMPT"):
        with patch("subagent._find_claude", return_value="claude"):
            with patch("subagent.subprocess.run",
                       side_effect=subprocess.TimeoutExpired("claude", 600)):
                result = spawn_subagent(ctx, "slow task", timeout_seconds=600)

    assert result.success is False
    assert "timed out" in result.error


def test_spawn_subagent_exception(tmp_path):
    """spawn_subagent returns error result on unexpected exception."""
    ctx = _make_ctx(tmp_path)

    with patch("subagent.build_subagent_prompt", return_value="PROMPT"):
        with patch("subagent._find_claude", return_value="claude"):
            with patch("subagent.subprocess.run",
                       side_effect=OSError("no such file")):
                result = spawn_subagent(ctx, "task")

    assert result.success is False
    assert "no such file" in result.error


def test_spawn_subagent_malformed_json(tmp_path):
    """spawn_subagent handles non-JSON lines gracefully."""
    ctx = _make_ctx(tmp_path)
    stream_output = "not json\n{bad json too\n"
    fake_result = MagicMock(returncode=0, stdout=stream_output, stderr="")

    with patch("subagent.build_subagent_prompt", return_value="PROMPT"):
        with patch("subagent._find_claude", return_value="claude"):
            with patch("subagent.subprocess.run", return_value=fake_result):
                result = spawn_subagent(ctx, "task")

    assert result.success is True
    assert "not json" in result.output


# --------------- spawn_parallel_subagents ---------------

def test_spawn_parallel_subagents_runs_each_task(tmp_path):
    """spawn_parallel_subagents creates worktrees, spawns, merges, cleans up."""
    ctx = _make_ctx(tmp_path)
    tasks = [
        {"task": "Fix A", "agent": "fixer", "session_num": 100},
        {"task": "Fix B", "agent": "tester", "session_num": 101},
    ]

    from worktree import WorktreeSession
    fake_ws = WorktreeSession("x", 1, "agent/x/s1", tmp_path / "wt", "main")

    with patch("worktree.create_worktree", return_value=fake_ws) as mock_create:
        with patch("subagent.spawn_subagent",
                   return_value=SubagentResult("x", "t", True)) as mock_spawn:
            with patch("worktree.merge_worktree") as mock_merge:
                with patch("worktree.cleanup_worktree") as mock_cleanup:
                    results = spawn_parallel_subagents(ctx, tasks)

    assert len(results) == 2
    assert mock_create.call_count == 2
    assert mock_spawn.call_count == 2
    assert mock_merge.call_count == 2  # both succeeded
    assert mock_cleanup.call_count == 2


def test_spawn_parallel_subagents_skips_merge_on_failure(tmp_path):
    """spawn_parallel_subagents skips merge when subagent fails."""
    ctx = _make_ctx(tmp_path)
    tasks = [{"task": "Fail", "agent": "buggy"}]

    from worktree import WorktreeSession
    fake_ws = WorktreeSession("x", 1, "agent/x/s1", tmp_path / "wt", "main")

    with patch("worktree.create_worktree", return_value=fake_ws):
        with patch("subagent.spawn_subagent",
                   return_value=SubagentResult("x", "t", False, error="crash")):
            with patch("worktree.merge_worktree") as mock_merge:
                with patch("worktree.cleanup_worktree") as mock_cleanup:
                    results = spawn_parallel_subagents(ctx, tasks)

    assert results[0].success is False
    mock_merge.assert_not_called()  # no merge on failure
    mock_cleanup.assert_called_once()  # still cleaned up
