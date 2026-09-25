"""Tests for worktree.py — git worktree isolation for parallel agent sessions."""
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock, call

import worktree
from worktree import (
    WorktreeSession, create_worktree, has_changes,
    merge_worktree, cleanup_worktree, list_active_worktrees,
)


# --------------- create_worktree ---------------

def test_create_worktree_success(tmp_path):
    """create_worktree returns a WorktreeSession on success."""
    fake_runs = [
        # git rev-parse --abbrev-ref HEAD
        MagicMock(stdout="main\n", returncode=0),
        # git show-ref branch existence check
        MagicMock(returncode=1),
        # git worktree add
        MagicMock(returncode=0, stderr=""),
    ]

    with patch("worktree.subprocess.run", side_effect=fake_runs):
        with patch("worktree.Path.exists", return_value=False):
            ws = create_worktree(tmp_path, "frontend", 42)

    assert ws is not None
    assert ws.agent_name == "frontend"
    assert ws.session_num == 42
    assert ws.branch_name == "agent/frontend/s42"
    assert ws.base_branch == "main"
    assert ws.merged is False


def test_create_worktree_invalid_agent_name(tmp_path):
    """create_worktree rejects names with path traversal characters."""
    # Mock the first subprocess call (rev-parse) so it doesn't hit real git
    with patch("worktree.subprocess.run",
               return_value=MagicMock(stdout="main\n", returncode=0)):
        ws = create_worktree(tmp_path, "../evil", 1)
    assert ws is None


def test_create_worktree_git_failure(tmp_path):
    """create_worktree returns None when git worktree add fails."""
    fake_runs = [
        MagicMock(stdout="main\n", returncode=0),  # rev-parse
        MagicMock(returncode=1),  # branch does not exist
        MagicMock(returncode=1, stderr="fatal: already exists"),  # worktree add
    ]

    with patch("worktree.subprocess.run", side_effect=fake_runs):
        with patch("worktree.Path.exists", return_value=False):
            ws = create_worktree(tmp_path, "backend", 5)

    assert ws is None


def test_create_worktree_exception_during_rev_parse(tmp_path):
    """create_worktree defaults to 'main' if rev-parse throws."""
    fake_runs = [
        Exception("not a git repo"),  # rev-parse throws
        MagicMock(returncode=1),  # branch does not exist
        MagicMock(returncode=0, stderr=""),  # worktree add
    ]

    def side_effect_fn(*a, **kw):
        val = fake_runs.pop(0)
        if isinstance(val, Exception):
            raise val
        return val

    with patch("worktree.subprocess.run", side_effect=side_effect_fn):
        with patch("worktree.Path.exists", return_value=False):
            ws = create_worktree(tmp_path, "tester", 10)

    assert ws is not None
    assert ws.base_branch == "main"


def test_create_worktree_refuses_existing_path(tmp_path):
    """create_worktree refuses to overwrite an existing worktree path."""
    with patch("worktree.subprocess.run",
               return_value=MagicMock(stdout="main\n", returncode=0)):
        with patch("worktree.Path.exists", return_value=True):
            ws = create_worktree(tmp_path, "frontend", 42)
    assert ws is None


def test_create_worktree_refuses_existing_branch(tmp_path):
    """create_worktree refuses to delete an existing agent branch."""
    fake_runs = [
        MagicMock(stdout="main\n", returncode=0),  # rev-parse
        MagicMock(returncode=0),  # branch exists
    ]
    with patch("worktree.subprocess.run", side_effect=fake_runs):
        with patch("worktree.Path.exists", return_value=False):
            ws = create_worktree(tmp_path, "frontend", 42)
    assert ws is None


# --------------- has_changes ---------------

def test_has_changes_no_changes():
    """has_changes returns False when worktree is clean."""
    ws = WorktreeSession("a", 1, "agent/a/s1", Path("/tmp/wt"), "main")
    fake_runs = [
        MagicMock(stdout="", returncode=0),  # status --porcelain (empty)
        MagicMock(stdout="", returncode=0),  # log base..HEAD (empty)
    ]
    with patch("worktree.subprocess.run", side_effect=fake_runs):
        assert has_changes(ws) is False


def test_has_changes_uncommitted():
    """has_changes returns True when there are uncommitted files."""
    ws = WorktreeSession("a", 1, "agent/a/s1", Path("/tmp/wt"), "main")
    with patch("worktree.subprocess.run",
               return_value=MagicMock(stdout="M file.py\n", returncode=0)):
        assert has_changes(ws) is True


def test_has_changes_commits_ahead():
    """has_changes returns True when branch has commits ahead of base."""
    ws = WorktreeSession("a", 1, "agent/a/s1", Path("/tmp/wt"), "main")
    fake_runs = [
        MagicMock(stdout="", returncode=0),  # status clean
        MagicMock(stdout="abc1234 some commit\n", returncode=0),  # log shows commits
    ]
    with patch("worktree.subprocess.run", side_effect=fake_runs):
        assert has_changes(ws) is True


def test_has_changes_exception():
    """has_changes returns False on subprocess error."""
    ws = WorktreeSession("a", 1, "agent/a/s1", Path("/tmp/wt"), "main")
    with patch("worktree.subprocess.run", side_effect=Exception("fail")):
        assert has_changes(ws) is False


# --------------- merge_worktree ---------------

def test_merge_worktree_success(tmp_path):
    """merge_worktree returns True and sets merged=True on success."""
    ws = WorktreeSession("a", 1, "agent/a/s1", Path("/tmp/wt"), "main")
    fake_runs = [
        MagicMock(stdout="main\n", stderr="", returncode=0),  # current branch
        MagicMock(stdout="", stderr="", returncode=0),  # main status
        MagicMock(stdout="", stderr="", returncode=0),  # worktree status
        MagicMock(returncode=0),  # merge
    ]

    with patch("worktree.has_changes", return_value=True):
        with patch("worktree.subprocess.run", side_effect=fake_runs):
            result = merge_worktree(ws, tmp_path)

    assert result is True
    assert ws.merged is True


def test_merge_worktree_no_changes(tmp_path):
    """merge_worktree skips merge and returns True when no changes."""
    ws = WorktreeSession("a", 1, "agent/a/s1", Path("/tmp/wt"), "main")

    with patch("worktree.has_changes", return_value=False):
        result = merge_worktree(ws, tmp_path)

    assert result is True
    assert ws.merged is True


def test_merge_worktree_conflict(tmp_path):
    """merge_worktree returns False on merge conflict and aborts."""
    ws = WorktreeSession("a", 1, "agent/a/s1", Path("/tmp/wt"), "main")

    fake_runs = [
        MagicMock(stdout="main\n", stderr="", returncode=0),  # current branch
        MagicMock(stdout="", stderr="", returncode=0),  # main status
        MagicMock(stdout="", stderr="", returncode=0),  # worktree status
        MagicMock(returncode=1, stderr="CONFLICT"),  # merge fails
        MagicMock(returncode=0),  # merge --abort
    ]
    with patch("worktree.has_changes", return_value=True):
        with patch("worktree.subprocess.run", side_effect=fake_runs):
            result = merge_worktree(ws, tmp_path)

    assert result is False
    assert ws.merged is False


def test_merge_worktree_refuses_wrong_base_branch(tmp_path):
    """merge_worktree refuses to merge unless project root is on the base branch."""
    ws = WorktreeSession("a", 1, "agent/a/s1", Path("/tmp/wt"), "main")
    with patch("worktree.has_changes", return_value=True):
        with patch("worktree.subprocess.run",
                   return_value=MagicMock(stdout="feature\n", stderr="", returncode=0)):
            result = merge_worktree(ws, tmp_path)
    assert result is False
    assert ws.merged is False


def test_merge_worktree_refuses_dirty_project_root(tmp_path):
    """merge_worktree refuses to merge into a dirty main worktree."""
    ws = WorktreeSession("a", 1, "agent/a/s1", Path("/tmp/wt"), "main")
    fake_runs = [
        MagicMock(stdout="main\n", stderr="", returncode=0),  # current branch
        MagicMock(stdout="M file.py\n", stderr="", returncode=0),  # dirty root
    ]
    with patch("worktree.has_changes", return_value=True):
        with patch("worktree.subprocess.run", side_effect=fake_runs):
            result = merge_worktree(ws, tmp_path)
    assert result is False
    assert ws.merged is False


def test_merge_worktree_refuses_uncommitted_worktree_changes(tmp_path):
    """merge_worktree refuses uncommitted worktree changes so cleanup preserves them."""
    ws = WorktreeSession("a", 1, "agent/a/s1", Path("/tmp/wt"), "main")
    fake_runs = [
        MagicMock(stdout="main\n", stderr="", returncode=0),  # current branch
        MagicMock(stdout="", stderr="", returncode=0),  # main status
        MagicMock(stdout="M file.py\n", stderr="", returncode=0),  # dirty worktree
    ]
    with patch("worktree.has_changes", return_value=True):
        with patch("worktree.subprocess.run", side_effect=fake_runs):
            result = merge_worktree(ws, tmp_path)
    assert result is False
    assert ws.merged is False


def test_merge_worktree_exception(tmp_path):
    """merge_worktree returns False on unexpected exception."""
    ws = WorktreeSession("a", 1, "agent/a/s1", Path("/tmp/wt"), "main")

    with patch("worktree.has_changes", return_value=True):
        with patch("worktree.subprocess.run", side_effect=Exception("boom")):
            result = merge_worktree(ws, tmp_path)

    assert result is False


# --------------- cleanup_worktree ---------------

def test_cleanup_worktree_deletes_branch_if_merged(tmp_path):
    """cleanup_worktree removes worktree and deletes branch when merged."""
    ws = WorktreeSession("a", 1, "agent/a/s1", Path("/tmp/wt"), "main", merged=True)

    calls = []
    def track_run(*a, **kw):
        calls.append(a[0] if a else kw.get("args"))
        return MagicMock(returncode=0)

    with patch("worktree.subprocess.run", side_effect=track_run):
        cleanup_worktree(ws, tmp_path)

    # Should call: worktree remove, branch -d, worktree prune
    cmds = [c[1] if isinstance(c, list) and len(c) > 1 else "" for c in calls]
    assert any("worktree" in str(c) and "remove" in str(c) for c in calls)
    assert any("branch" in str(c) and "-d" in str(c) for c in calls)


def test_cleanup_worktree_skips_branch_delete_if_not_merged(tmp_path):
    """cleanup_worktree does not delete branch when not merged."""
    ws = WorktreeSession("a", 1, "agent/a/s1", Path("/tmp/wt"), "main", merged=False)

    calls = []
    def track_run(*a, **kw):
        calls.append(a[0] if a else kw.get("args"))
        return MagicMock(returncode=0)

    with patch("worktree.has_changes", return_value=False):
        with patch("worktree.subprocess.run", side_effect=track_run):
            cleanup_worktree(ws, tmp_path)

    # Should NOT have branch -d call
    assert not any("branch" in str(c) and "-d" in str(c) for c in calls)


def test_cleanup_worktree_preserves_unmerged_changes(tmp_path):
    """cleanup_worktree leaves an unmerged worktree in place when it has changes."""
    ws = WorktreeSession("a", 1, "agent/a/s1", Path("/tmp/wt"), "main", merged=False)

    with patch("worktree.has_changes", return_value=True), \
         patch("worktree.subprocess.run") as mock_run:
        cleanup_worktree(ws, tmp_path)

    mock_run.assert_not_called()


# --------------- list_active_worktrees ---------------

def test_list_active_worktrees_parses_porcelain(tmp_path):
    """list_active_worktrees parses git worktree list --porcelain output."""
    porcelain_output = (
        "worktree /project\n"
        "branch refs/heads/main\n"
        "\n"
        "worktree /project/.autoagent/worktrees/frontend-s42\n"
        "branch refs/heads/agent/frontend/s42\n"
        "\n"
        "worktree /project/.autoagent/worktrees/backend-s43\n"
        "branch refs/heads/agent/backend/s43\n"
        "\n"
    )
    with patch("worktree.subprocess.run",
               return_value=MagicMock(stdout=porcelain_output, returncode=0)):
        result = list_active_worktrees(tmp_path)

    assert len(result) == 2
    assert result[0]["branch"] == "refs/heads/agent/frontend/s42"
    assert result[1]["branch"] == "refs/heads/agent/backend/s43"


def test_list_active_worktrees_empty(tmp_path):
    """list_active_worktrees returns empty list when no agent worktrees."""
    porcelain_output = (
        "worktree /project\n"
        "branch refs/heads/main\n"
        "\n"
    )
    with patch("worktree.subprocess.run",
               return_value=MagicMock(stdout=porcelain_output, returncode=0)):
        result = list_active_worktrees(tmp_path)

    assert result == []


def test_list_active_worktrees_exception(tmp_path):
    """list_active_worktrees returns empty list on error."""
    with patch("worktree.subprocess.run", side_effect=Exception("fail")):
        result = list_active_worktrees(tmp_path)
    assert result == []
