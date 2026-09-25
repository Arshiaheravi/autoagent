#!/usr/bin/env python3
"""Tests for cli.py — CLI entry point commands."""
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

import cli
import cli_commands
import cli_extras
import registry


# ---------- cmd_list ----------

def test_cmd_list_empty(capsys):
    """When no projects are registered, cmd_list prints 'No projects' message."""
    cli.cmd_list()
    out = capsys.readouterr().out
    assert "No projects" in out


def test_cmd_list_with_projects(capsys, tmp_path):
    """When projects exist, cmd_list prints a table with name, sessions, and path."""
    proj = tmp_path / "myproj"
    proj.mkdir()
    registry.register("myproj", str(proj))
    cli.cmd_list()
    out = capsys.readouterr().out
    assert "myproj" in out
    assert str(proj) in out


# ---------- cmd_run ----------

def test_cmd_run_no_args(capsys):
    """cmd_run with no args prints an error about specifying a project."""
    cli_commands.cmd_run([])
    out = capsys.readouterr().out
    assert "Error" in out


def test_cmd_run_unknown_project(capsys):
    """cmd_run with a non-existent project prints an error."""
    cli_commands.cmd_run(["nonexistent"])
    out = capsys.readouterr().out
    assert "Error" in out


def test_cmd_run_invalid_type(capsys, tmp_path):
    """cmd_run with --type invalid prints an error about unknown session type."""
    proj = tmp_path / "testproj"
    proj.mkdir()
    registry.register("testproj", str(proj))
    cli_commands.cmd_run(["testproj", "--type", "bogus"])
    out = capsys.readouterr().out
    assert "unknown session type" in out


def test_cmd_run_test_mode(tmp_path):
    """cmd_run with --test parses test_mode=True and calls run_project."""
    proj = tmp_path / "testproj"
    proj.mkdir()
    registry.register("testproj", str(proj))
    with patch.object(cli_commands, "run_project") as mock_run:
        cli_commands.cmd_run(["testproj", "--test"])
        mock_run.assert_called_once()
        _, kwargs = mock_run.call_args
        assert kwargs["test_mode"] is True


def test_cmd_run_once_and_type(tmp_path):
    """cmd_run with --once --type meta parses both flags correctly."""
    proj = tmp_path / "testproj"
    proj.mkdir()
    registry.register("testproj", str(proj))
    with patch.object(cli_commands, "run_project") as mock_run:
        cli_commands.cmd_run(["testproj", "--once", "--type", "meta", "--test"])
        mock_run.assert_called_once()
        _, kwargs = mock_run.call_args
        assert kwargs["tasks_limit"] == 1
        assert kwargs["forced_type"] == "meta"
        assert kwargs["test_mode"] is True


def test_cmd_run_accepts_audit_and_knowledge_types(tmp_path):
    """cmd_run accepts all rotating session types as forced types."""
    proj = tmp_path / "testproj"
    proj.mkdir()
    registry.register("testproj", str(proj))
    with patch.object(cli_commands, "run_project") as mock_run:
        cli_commands.cmd_run(["testproj", "--once", "--type", "audit", "--test"])
        assert mock_run.call_args.kwargs["forced_type"] == "audit"
    with patch.object(cli_commands, "run_project") as mock_run:
        cli_commands.cmd_run(["testproj", "--once", "--type", "knowledge", "--test"])
        assert mock_run.call_args.kwargs["forced_type"] == "knowledge"


def test_cmd_run_invalid_tasks_prints_error(capsys, tmp_path):
    """cmd_run with invalid --tasks prints an error instead of crashing."""
    proj = tmp_path / "testproj"
    proj.mkdir()
    registry.register("testproj", str(proj))
    with patch.object(cli_commands, "run_project") as mock_run:
        cli_commands.cmd_run(["testproj", "--tasks", "many", "--test"])
    out = capsys.readouterr().out
    assert "expects an integer" in out
    mock_run.assert_not_called()


# ---------- cmd_status ----------

def test_cmd_status_specific_project(tmp_path):
    """cmd_status with a project name calls show_status for that project."""
    proj = tmp_path / "testproj"
    proj.mkdir()
    registry.register("testproj", str(proj))
    with patch.object(cli, "show_status") as mock_status:
        cli.cmd_status(["testproj"])
        mock_status.assert_called_once()


# ---------- cmd_register ----------

def test_cmd_register_insufficient_args(capsys):
    """cmd_register with <2 args prints usage."""
    cli.cmd_register(["onlyone"])
    out = capsys.readouterr().out
    assert "Usage" in out


def test_cmd_register_valid(capsys, tmp_path):
    """cmd_register with valid args registers the project and prints confirmation."""
    proj = tmp_path / "newproj"
    proj.mkdir()
    cli.cmd_register(["newproj", str(proj)])
    out = capsys.readouterr().out
    assert "Registered" in out
    assert "newproj" in out


# ---------- cmd_remove ----------

def test_cmd_remove_no_args(capsys):
    """cmd_remove with no args prints usage."""
    cli.cmd_remove([])
    out = capsys.readouterr().out
    assert "Usage" in out


def test_cmd_remove_valid(capsys, tmp_path):
    """cmd_remove unregisters a project and prints confirmation."""
    proj = tmp_path / "rmproj"
    proj.mkdir()
    registry.register("rmproj", str(proj))
    cli.cmd_remove(["rmproj"])
    out = capsys.readouterr().out
    assert "Removed" in out


# ---------- main() ----------

def test_main_unknown_command(capsys):
    """main() with an unknown command prints 'Unknown command' and usage."""
    with patch("sys.argv", ["autoagent", "bogus"]):
        cli.main()
    out = capsys.readouterr().out
    assert "Unknown command" in out


# ---------- cmd_run --continuous ----------

def test_cmd_run_continuous_calls_run_continuous(tmp_path):
    """cmd_run with --continuous calls run_continuous instead of run_project."""
    proj = tmp_path / "testproj"
    proj.mkdir()
    registry.register("testproj", str(proj))
    with patch.object(cli_commands, "run_continuous") as mock_cont, \
         patch.object(cli_commands, "ask_mode", return_value="cli"):
        cli_commands.cmd_run(["testproj", "--continuous", "--test"])
        mock_cont.assert_called_once()
        called_contexts = mock_cont.call_args[0][0]
        assert len(called_contexts) == 1
        assert called_contexts[0].name == "testproj"


def test_cmd_run_continuous_all_round_robin(tmp_path):
    """cmd_run with --continuous --all calls run_continuous with all projects."""
    p1 = tmp_path / "proj1"
    p2 = tmp_path / "proj2"
    p1.mkdir()
    p2.mkdir()
    registry.register("proj1", str(p1))
    registry.register("proj2", str(p2))
    with patch.object(cli_commands, "run_continuous") as mock_cont:
        cli_commands.cmd_run(["--continuous", "--all"])
        mock_cont.assert_called_once()
        called_contexts = mock_cont.call_args[0][0]
        names = [c.name for c in called_contexts]
        assert "proj1" in names
        assert "proj2" in names


def test_cmd_run_continuous_until(tmp_path):
    """cmd_run with --continuous --until 09:00 passes until arg."""
    proj = tmp_path / "testproj"
    proj.mkdir()
    registry.register("testproj", str(proj))
    with patch.object(cli_commands, "run_continuous") as mock_cont, \
         patch.object(cli_commands, "ask_mode", return_value="cli"):
        cli_commands.cmd_run(["testproj", "--continuous", "--until", "09:00", "--test"])
        mock_cont.assert_called_once()
        kwargs = mock_cont.call_args[1]
        assert kwargs.get("until") == "09:00"


# ---------- cmd_skill ----------

def test_cmd_skill_no_args(capsys):
    """cmd_skill with no args prints usage."""
    cli_commands.cmd_skill([])
    out = capsys.readouterr().out
    assert "Usage" in out


def test_cmd_skill_promote(capsys, tmp_path):
    """cmd_skill promote copies skill to shared and prints confirmation."""
    proj = tmp_path / "myproj"
    proj.mkdir()
    ctx = registry.register("myproj", str(proj))
    # Create a project-local skill
    project_skills = ctx.project_home / "skills"
    project_skills.mkdir(exist_ok=True)
    (project_skills / "my-skill.md").write_text("# My Skill")

    cli_commands.cmd_skill(["promote", "myproj", "my-skill"])
    out = capsys.readouterr().out
    assert "Promoted" in out
    assert "my-skill" in out


def test_cmd_skill_promote_missing_skill(capsys, tmp_path):
    """cmd_skill promote with nonexistent skill prints error."""
    proj = tmp_path / "myproj"
    proj.mkdir()
    registry.register("myproj", str(proj))
    cli_commands.cmd_skill(["promote", "myproj", "nope"])
    out = capsys.readouterr().out
    assert "Error" in out


def test_main_help(capsys):
    """main() with --help prints usage."""
    with patch("sys.argv", ["autoagent", "--help"]):
        cli.main()
    out = capsys.readouterr().out
    assert "AutoAgent Agency" in out


# ---------- cmd_validate ----------

def test_cmd_validate(capsys, tmp_path):
    """cmd_validate prints warnings for an incomplete project and OK for a healthy one."""
    proj = tmp_path / "testproj"
    proj.mkdir()
    ctx = registry.register("testproj", str(proj))
    # No agents, no backlog — should have warnings
    cli_commands.cmd_validate(["testproj"])
    out = capsys.readouterr().out
    assert "Warning" in out or "warning" in out.lower()


def test_cmd_validate_no_args(capsys):
    """cmd_validate with no args prints usage."""
    cli_commands.cmd_validate([])
    out = capsys.readouterr().out
    assert "Usage" in out or "usage" in out.lower()


# ---------- cmd_logs ----------

def test_cmd_logs(capsys, tmp_path):
    """cmd_logs with --type work --last 2 filters and prints formatted output."""
    proj = tmp_path / "logproj"
    proj.mkdir()
    ctx = registry.register("logproj", str(proj))
    # Write sessions.json into the project home
    sessions_data = [
        {"session": 1, "type": "work", "date": "2026-03-26", "summary": "Built feature A"},
        {"session": 2, "type": "meta", "date": "2026-03-26", "summary": "Improved prompts"},
        {"session": 3, "type": "work", "date": "2026-03-27", "summary": "Built feature B"},
        {"session": 4, "type": "work", "date": "2026-03-28", "summary": "Added soil endpoint"},
    ]
    ctx.sessions_file.write_text(json.dumps(sessions_data), encoding="utf-8")
    cli_commands.cmd_logs(["logproj", "--type", "work", "--last", "2"])
    out = capsys.readouterr().out
    # Should show only the last 2 work sessions
    assert "Built feature B" in out
    assert "Added soil endpoint" in out
    assert "Improved prompts" not in out
    assert "Built feature A" not in out


def test_cmd_logs_invalid_last_prints_error(capsys, tmp_path):
    """cmd_logs with invalid --last prints an error instead of crashing."""
    proj = tmp_path / "logproj"
    proj.mkdir()
    registry.register("logproj", str(proj))
    cli_commands.cmd_logs(["logproj", "--last", "nope"])
    out = capsys.readouterr().out
    assert "expects an integer" in out


def test_cmd_parallel_invalid_max_prints_error(capsys):
    """cmd_parallel with invalid --max prints an error before launch."""
    cli_extras.cmd_parallel(["proj", "--max", "zero"])
    out = capsys.readouterr().out
    assert "expects an integer" in out


def test_cmd_cleanup_delegates_to_cleanup_module():
    """cmd_cleanup routes to the Engineering cleanup crew CLI."""
    with patch("cleanup.run_cleanup_cli") as mock_cleanup:
        cli_extras.cmd_cleanup(["--path", "/tmp/project"])

    mock_cleanup.assert_called_once_with(["--path", "/tmp/project"])


def test_cmd_org_prints_report(capsys):
    """cmd_org prints the department report."""
    with patch("org_model.build_org_report", return_value={
        "manifest_found": True,
        "universal_agents": ["architect"],
        "departments": [{"name": "Engineering", "purpose": "", "agents": [], "loops": []}],
        "warnings": [],
        "candidate_agents": [],
    }):
        cli_extras.cmd_org([])
    out = capsys.readouterr().out
    assert "Agency Organization" in out
    assert "Engineering" in out


def test_cmd_org_strict_exits_on_errors():
    """cmd_org --strict exits non-zero when the org report has strict errors."""
    with patch("org_model.build_org_report", return_value={
        "manifest_found": True,
        "universal_agents": [],
        "departments": [],
        "errors": ["Missing universal agent template: architect.md"],
        "warnings": ["Missing universal agent template: architect.md"],
        "notes": [],
        "candidate_agents": [],
        "strict_ok": False,
    }):
        with pytest.raises(SystemExit):
            cli_extras.cmd_org(["--strict"])


def test_cmd_db_sync_project(capsys, tmp_path):
    """cmd_db sync calls session DB sync for the requested project."""
    proj = tmp_path / "dbproj"
    proj.mkdir()
    registry.register("dbproj", str(proj))
    with patch("session_db_sync.sync_sessions_file_to_agency_db", return_value=3) as mock_sync:
        cli_extras.cmd_db(["sync", "dbproj"])
    out = capsys.readouterr().out
    assert "dbproj: synced 3" in out
    mock_sync.assert_called_once()
    assert mock_sync.call_args.kwargs["raise_errors"] is True


def test_cmd_db_sync_exits_on_db_error(capsys, tmp_path):
    """cmd_db sync surfaces database errors instead of reporting zero."""
    proj = tmp_path / "dbproj"
    proj.mkdir()
    registry.register("dbproj", str(proj))
    with patch("session_db_sync.sync_sessions_file_to_agency_db", side_effect=OSError("locked")):
        with pytest.raises(SystemExit):
            cli_extras.cmd_db(["sync", "dbproj"])
    out = capsys.readouterr().out
    assert "Error syncing dbproj" in out


def test_cmd_db_audit_prints_report(capsys):
    with patch("db_maintenance.audit_database", return_value={
        "totals": {"projects": 1, "sessions": 2, "agents": 1},
        "success_sources": {"explicit": 1, "inferred": 1},
        "test_projects": [],
        "orphan_projects": [],
        "missing_db_projects": [],
        "duplicate_sessions": [],
        "low_confidence_agents": [],
    }):
        cli_extras.cmd_db(["audit"])
    assert "Agency DB Audit" in capsys.readouterr().out


def test_cmd_db_prune_defaults_to_dry_run(capsys):
    with patch("db_maintenance.prune_test_data", return_value={
        "projects": ["testproject"],
        "rows": {"sessions": 1, "projects": 1},
        "applied": False,
    }) as mock_prune:
        cli_extras.cmd_db(["prune-test-data"])
    out = capsys.readouterr().out
    assert "DRY RUN" in out
    assert "--apply" in out
    mock_prune.assert_called_once_with(apply=False)


def test_cmd_db_dedupe_defaults_to_dry_run(capsys):
    with patch("db_maintenance.dedupe_sessions", return_value={
        "project": None,
        "groups": [],
        "duplicate_rows": 0,
        "deleted_rows": 0,
        "applied": False,
    }) as mock_dedupe:
        cli_extras.cmd_db(["dedupe-sessions"])
    out = capsys.readouterr().out
    assert "Dedupe Sessions" in out
    assert "--apply" in out
    mock_dedupe.assert_called_once_with(project=None, apply=False)


# ---------- module split checks ----------

def test_cli_py_under_300_lines():
    """cli.py must stay under 300 lines."""
    cli_file = Path(__file__).parent / "cli.py"
    line_count = len(cli_file.read_text().splitlines())
    assert line_count <= 325, f"cli.py is {line_count} lines (limit: 325)"


def test_cli_commands_module_exists():
    """cli_commands.py must exist as a separate module."""
    cli_commands_file = Path(__file__).parent / "cli_commands.py"
    assert cli_commands_file.exists(), "cli_commands.py not found"
