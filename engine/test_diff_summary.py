"""Tests for diff_summary — session diff summarizer."""

import subprocess
from pathlib import Path

from diff_summary import summarize_session_diff


def _git(repo, *args):
    """Run a git command in repo."""
    subprocess.run(["git", "-C", str(repo)] + list(args),
                   capture_output=True, check=True)


def _init_repo(tmp_path):
    """Create a git repo with one initial commit."""
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "test@test.com")
    _git(tmp_path, "config", "user.name", "Test")
    (tmp_path / "README.md").write_text("# hello")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "initial commit")


def test_summarize_diff_with_changes(tmp_path):
    """After one commit touching a file, summary includes the file name and commit message."""
    _init_repo(tmp_path)
    # Make a change and commit
    (tmp_path / "app.py").write_text("print('hello')")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "feat: add greeting")

    result = summarize_session_diff(tmp_path)

    assert "app.py" in result
    assert "feat: add greeting" in result


def test_summarize_diff_clean_repo(tmp_path):
    """Clean repo with no recent changes returns a 'no changes' message."""
    _init_repo(tmp_path)

    result = summarize_session_diff(tmp_path, last_n=0)

    assert "no changes" in result.lower() or "clean" in result.lower()


def test_summarize_diff_multiple_commits(tmp_path):
    """Multiple commits are all captured in the summary."""
    _init_repo(tmp_path)
    # Two commits
    (tmp_path / "a.py").write_text("a = 1")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "add module a")

    (tmp_path / "b.py").write_text("b = 2")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "add module b")

    result = summarize_session_diff(tmp_path, last_n=2)

    assert "a.py" in result
    assert "b.py" in result
    assert "add module a" in result
    assert "add module b" in result
