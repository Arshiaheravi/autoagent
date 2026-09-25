"""Tests for session entropy checker — detects stale state."""
import os
import time
import pytest
from unittest.mock import patch
from entropy_checker import check_entropy


@pytest.fixture
def project_root(tmp_path):
    memory = tmp_path / "memory"
    memory.mkdir()
    (memory / "current_task.md").write_text("# No current task\n")
    (memory / "backlog.md").write_text("# Backlog\n\n## Tasks\n\n### 1. Fresh task\n")
    (memory / "knowledge.md").write_text(
        "### Session #1 Reflexion — 2026-04-30\n"
        "- RULE: [2026-04-30] Always test first.\n"
    )
    (tmp_path / "PROJECT.md").write_text(
        "### Test Command\n```\npytest test_foo.py test_bar.py -q\n```\n"
    )
    return tmp_path


def test_check_entropy_clean(project_root):
    """No issues when everything is fresh and consistent."""
    results = check_entropy(str(project_root))
    assert results == []


def test_check_entropy_stale_task(project_root, monkeypatch):
    """Detects current_task.md with unchecked steps older than 24h."""
    task_file = project_root / "memory" / "current_task.md"
    task_file.write_text("# Current Task: Old thing\n- [ ] Step 1\n- [ ] Step 2\n")
    old_time = time.time() - (25 * 3600)
    os.utime(str(task_file), (old_time, old_time))

    results = check_entropy(str(project_root))
    assert len(results) == 1
    assert results[0]["type"] == "stale_task"
    assert "24h" in results[0]["message"] or "old" in results[0]["message"].lower()


def test_check_entropy_stale_task_no_steps_ignored(project_root):
    """current_task.md with no unchecked steps is not flagged even if old."""
    task_file = project_root / "memory" / "current_task.md"
    task_file.write_text("# No current task\n")
    old_time = time.time() - (48 * 3600)
    os.utime(str(task_file), (old_time, old_time))

    results = check_entropy(str(project_root))
    assert results == []


def test_check_entropy_old_backlog(project_root):
    """Detects backlog items not touched in 14+ days."""
    backlog = project_root / "memory" / "backlog.md"
    old_time = time.time() - (15 * 24 * 3600)
    os.utime(str(backlog), (old_time, old_time))

    results = check_entropy(str(project_root))
    stale = [r for r in results if r["type"] == "stale_backlog"]
    assert len(stale) == 1
    assert "14" in stale[0]["message"]


def test_check_entropy_undated_rules(project_root):
    """Detects knowledge.md rules missing date prefix."""
    knowledge = project_root / "memory" / "knowledge.md"
    knowledge.write_text(
        "### Session #1 Reflexion — 2026-04-30\n"
        "- RULE: Always test first.\n"
        "- RULE: [2026-04-30] Dated rule is fine.\n"
    )

    results = check_entropy(str(project_root))
    undated = [r for r in results if r["type"] == "undated_rule"]
    assert len(undated) == 1
    assert "date" in undated[0]["message"].lower()


def test_check_entropy_orphaned_test(project_root):
    """Detects test files not listed in PROJECT.md test command."""
    (project_root / "test_orphan.py").write_text("def test_x(): pass\n")

    results = check_entropy(str(project_root))
    orphans = [r for r in results if r["type"] == "orphaned_test"]
    assert len(orphans) == 1
    assert "test_orphan.py" in orphans[0]["message"]


def test_check_entropy_listed_test_not_flagged(project_root):
    """Test files listed in PROJECT.md are not flagged."""
    (project_root / "test_foo.py").write_text("def test_x(): pass\n")

    results = check_entropy(str(project_root))
    orphans = [r for r in results if r["type"] == "orphaned_test"]
    assert orphans == []
