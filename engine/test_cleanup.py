"""Tests for the Engineering cleanup crew scanner."""
from unittest.mock import MagicMock, patch

import cleanup


def test_scan_finds_generated_duplicates_and_conflicts(tmp_path):
    """scan reports cleanup candidates without deleting anything."""
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "mod.cpython-311.pyc").write_text("bytecode")
    (tmp_path / ".pytest_cache").mkdir()
    (tmp_path / "templates").mkdir()
    (tmp_path / "templates" / "agent 2.md").write_text("# duplicate")
    (tmp_path / "engine").mkdir()
    (tmp_path / "engine" / "council.py").write_text("# old")
    (tmp_path / "engine" / "council").mkdir()
    (tmp_path / "engine" / "council" / "__init__.py").write_text("# package")

    findings = cleanup.scan(tmp_path)

    assert "__pycache__" in findings["generated"]
    assert ".pytest_cache" in findings["generated"]
    assert "templates/agent 2.md" in findings["duplicates"]
    assert "engine/council.py" in findings["module_package_conflicts"]
    assert (tmp_path / "templates" / "agent 2.md").exists()


def test_apply_generated_cleanup_only_removes_generated_files(tmp_path):
    """--apply behavior removes generated artifacts but preserves source-like findings."""
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "mod.pyc").write_text("bytecode")
    (tmp_path / "agent 2.md").write_text("# keep")

    removed = cleanup.apply_generated_cleanup(tmp_path)

    assert "__pycache__" in removed
    assert not (tmp_path / "__pycache__").exists()
    assert (tmp_path / "agent 2.md").exists()


def test_scan_reports_agent_worktrees(tmp_path):
    """scan includes active agent worktrees from git worktree porcelain output."""
    output = (
        "worktree /repo\n"
        "branch refs/heads/main\n"
        "\n"
        "worktree /repo/.autoagent/worktrees/frontend-s1\n"
        "branch refs/heads/agent/frontend/s1\n"
        "\n"
    )
    with patch("cleanup.subprocess.run",
               return_value=MagicMock(stdout=output, returncode=0)):
        findings = cleanup.scan(tmp_path)

    assert findings["agent_worktrees"] == [{
        "path": "/repo/.autoagent/worktrees/frontend-s1",
        "branch": "refs/heads/agent/frontend/s1",
    }]


def test_format_report_tells_apply_for_generated(tmp_path):
    findings = {
        "root": str(tmp_path),
        "generated": ["__pycache__"],
        "duplicates": [],
        "module_package_conflicts": [],
        "agent_worktrees": [],
    }

    report = cleanup.format_report(findings)

    assert "Engineering Cleanup Crew" in report
    assert "Generated artifacts: 1" in report
    assert "--apply" in report
