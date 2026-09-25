"""Tests for churn_tracker — per-file modification frequency from git log."""

import subprocess
from pathlib import Path

from churn_tracker import compute_churn_score


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


def test_churn_score_stable_files(tmp_path):
    """Files modified only once have low churn scores."""
    _init_repo(tmp_path)
    (tmp_path / "stable.py").write_text("x = 1")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "add stable")

    result = compute_churn_score(tmp_path, last_n_commits=20)

    assert isinstance(result, dict)
    assert "files" in result
    stable_entry = [f for f in result["files"] if f["path"] == "stable.py"]
    assert len(stable_entry) == 1
    assert stable_entry[0]["modifications"] == 1


def test_churn_score_high_churn(tmp_path):
    """Files modified many times get higher churn counts."""
    _init_repo(tmp_path)
    for i in range(5):
        (tmp_path / "hot.py").write_text(f"x = {i}")
        _git(tmp_path, "add", ".")
        _git(tmp_path, "commit", "-m", f"change {i}")

    result = compute_churn_score(tmp_path, last_n_commits=20)

    hot_entry = [f for f in result["files"] if f["path"] == "hot.py"]
    assert len(hot_entry) == 1
    assert hot_entry[0]["modifications"] == 5
    # Hot file should be first (sorted descending)
    assert result["files"][0]["path"] == "hot.py"


def test_churn_score_empty_repo(tmp_path):
    """Empty repo with no commits returns empty file list."""
    _git(tmp_path, "init")

    result = compute_churn_score(tmp_path, last_n_commits=20)

    assert isinstance(result, dict)
    assert result["files"] == []
