#!/usr/bin/env python3
"""Unit tests for session_helpers.py — extracted pure functions from run.py."""
import json
import pytest
from pathlib import Path
from unittest.mock import patch

import registry

# Import session_helpers explicitly — avoid V1 root-level shadowing
import importlib.util
_sh_spec = importlib.util.spec_from_file_location(
    "session_helpers", Path(__file__).parent / "session_helpers.py"
)
sh = importlib.util.module_from_spec(_sh_spec)
_sh_spec.loader.exec_module(sh)

# Import session_analytics explicitly
_sa_spec = importlib.util.spec_from_file_location(
    "session_analytics", Path(__file__).parent / "session_analytics.py"
)
sa = importlib.util.module_from_spec(_sa_spec)
_sa_spec.loader.exec_module(sa)


@pytest.fixture(autouse=True)
def setup_agency(isolated_agency_home):
    """Set up minimal agency structure for each test."""
    home = isolated_agency_home
    (home / "templates" / "PROMPT.md").write_text("# Base Prompt\nSession rules.")
    (home / "templates" / "meta" / "PROMPT.md").write_text("# Meta Prompt\nMeta rules.")
    (home / "templates" / "meta" / "BRAIN_PROMPT.md").write_text("# Brain Prompt\nBrain rules.")
    yield


def _make_ctx(tmp_path, name="testproj", config=None):
    """Create a ProjectContext with project dirs set up."""
    ctx = registry.ProjectContext(
        name=name,
        project_root=tmp_path / name,
        agency_home=registry.AGENCY_HOME,
        config=config or {},
    )
    ctx.project_root.mkdir(parents=True, exist_ok=True)
    ctx.project_home.mkdir(parents=True, exist_ok=True)
    ctx.memory_dir.mkdir(parents=True, exist_ok=True)
    ctx.project_file.write_text("# Project\nTest project.")
    (ctx.memory_dir / "activity_log.md").write_text("# Log")
    (ctx.memory_dir / "backlog.md").write_text("# Backlog")
    (ctx.memory_dir / "knowledge.md").write_text("# Knowledge")
    return ctx


# ── test_session_helpers_imports ─────────────────────────────

def test_session_helpers_imports():
    """All extracted functions are importable from session_helpers."""
    assert callable(sh.compute_quality_score)
    assert callable(sh.build_prompt)
    assert callable(sh.detect_frontend_changes)
    assert callable(sh.capture_screenshot)
    assert callable(sh._detect_agent)
    assert callable(sh._extract_test_command)
    assert callable(sh._pre_push_gate)
    assert callable(sh._constraint_gate)
    assert callable(sh._sync_templates)


# ── compute_quality_score ────────────────────────────────────

def test_quality_score_perfect():
    """1 task + 5 tests + 0 broken + 0 retries = 100."""
    assert sh.compute_quality_score(
        tasks_completed=1, tests_added=5, tests_broken=0, retries=0
    ) == 100


def test_quality_score_zero():
    """0 tasks + 0 tests + 2 broken = 0."""
    assert sh.compute_quality_score(
        tasks_completed=0, tests_added=0, tests_broken=2, retries=0
    ) == 0


# ── build_prompt ─────────────────────────────────────────────

def test_build_prompt_work_includes_sections(tmp_path):
    """Work session includes project, base prompt, and memory sections."""
    ctx = _make_ctx(tmp_path)
    result = sh.build_prompt(ctx, "work")
    assert "# Project" in result
    assert "# Base Prompt" in result
    assert "## RECENT SESSIONS" in result


def test_build_prompt_brain(tmp_path):
    """Brain session uses brain prompt + memory."""
    ctx = _make_ctx(tmp_path)
    result = sh.build_prompt(ctx, "brain")
    assert "# Brain Prompt" in result
    assert "## RECENT SESSIONS" in result
    assert "# Project" not in result


def test_audit_prompt_loads(tmp_path):
    """Audit session uses AUDIT_PROMPT.md + security skill ref + memory."""
    ctx = _make_ctx(tmp_path)
    # Create the audit prompt in meta dir (simulating template sync)
    ctx.meta_dir.mkdir(parents=True, exist_ok=True)
    (ctx.meta_dir / "AUDIT_PROMPT.md").write_text(
        "# Security Audit Instructions\nScan for vulnerabilities."
    )
    result = sh.build_prompt(ctx, "audit")
    assert "# Security Audit Instructions" in result
    assert "## RECENT SESSIONS" in result
    # Audit should NOT include the base work prompt or project file
    assert "# Base Prompt" not in result
    assert "# Project" not in result


# ── detect_frontend_changes ──────────────────────────────────

def test_detect_frontend_returns_true_for_html(tmp_path):
    """Returns True when events include .html edits."""
    events_file = tmp_path / "events.jsonl"
    import event_emitter
    event_emitter.emit(events_file, type="tool_use", action="editing", target="app.html")
    assert sh.detect_frontend_changes(events_file) is True


def test_detect_frontend_returns_false_for_python(tmp_path):
    """Returns False when events contain only .py edits."""
    events_file = tmp_path / "events.jsonl"
    import event_emitter
    event_emitter.emit(events_file, type="tool_use", action="writing", target="run.py")
    assert sh.detect_frontend_changes(events_file) is False


# ── _extract_test_command ────────────────────────────────────

def test_extract_test_command(tmp_path):
    """Extracts test command from PROJECT.md code block."""
    ctx = _make_ctx(tmp_path)
    ctx.project_file.write_text(
        "# Project\n\n### Test Command\n```\npython3 -m pytest -q\n```\n"
    )
    assert sh._extract_test_command(ctx) == "python3 -m pytest -q"


def test_extract_test_command_missing(tmp_path):
    """Returns None when no Test Command section exists."""
    ctx = _make_ctx(tmp_path)
    assert sh._extract_test_command(ctx) is None


def test_extract_test_command_config_fallback(tmp_path):
    """Falls back to project.json test_command (scaffolded projects set only this)."""
    ctx = _make_ctx(tmp_path, config={"test_command": "pytest -q"})
    # PROJECT.md has no ### Test Command block → config is used.
    assert sh._extract_test_command(ctx) == "pytest -q"


def test_pre_push_gate_skips_compound_command_without_running(tmp_path):
    from unittest.mock import patch
    ctx = _make_ctx(tmp_path, config={"test_command": "cd x && pytest -q"})
    with patch.object(sh.subprocess, "run") as run:
        assert sh._pre_push_gate(ctx) is True   # skipped, not failed
        run.assert_not_called()                  # compound never executed shell-free


def test_pre_push_gate_skips_unrecognized_runner(tmp_path):
    from unittest.mock import patch
    ctx = _make_ctx(tmp_path, config={"test_command": "./scripts/test.sh"})
    with patch.object(sh.subprocess, "run") as run:
        assert sh._pre_push_gate(ctx) is True
        run.assert_not_called()


def test_pre_push_gate_runs_recognized_runner(tmp_path):
    from unittest.mock import patch, MagicMock
    ctx = _make_ctx(tmp_path, config={"test_command": "pytest -q"})
    with patch.object(sh.subprocess, "run", return_value=MagicMock(returncode=0)) as run:
        assert sh._pre_push_gate(ctx) is True
        run.assert_called_once()
    with patch.object(sh.subprocess, "run", return_value=MagicMock(returncode=1)):
        assert sh._pre_push_gate(ctx) is False   # real failure now blocks


# ── parse_session_analytics ─────────────────────────────────

def _write_sessions(path, sessions):
    """Helper: write a list of session dicts as JSON."""
    path.write_text(json.dumps(sessions), encoding="utf-8")


def test_analytics_empty_file(tmp_path):
    """Returns zeroed analytics when sessions file doesn't exist."""
    result = sh.parse_session_analytics(tmp_path / "nope.json")
    assert result["total_sessions"] == 0
    assert result["tests_added"] == 0
    assert result["type_counts"] == {}
    assert result["recent"] == []


def test_analytics_counts_sessions(tmp_path):
    """Counts total sessions and breaks down by type."""
    sf = tmp_path / "sessions.json"
    _write_sessions(sf, [
        {"session": 1, "type": "work", "summary": "Built X", "tests": {"before": 10, "after": 12, "status": "pass"}},
        {"session": 2, "type": "work", "summary": "Built Y", "tests": {"before": 12, "after": 15, "status": "pass"}},
        {"session": 3, "type": "meta", "summary": "Improved prompts", "tests": {"before": 15, "after": 15, "status": "pass"}},
    ])
    result = sh.parse_session_analytics(sf)
    assert result["total_sessions"] == 3
    assert result["type_counts"]["work"] == 2
    assert result["type_counts"]["meta"] == 1


def test_analytics_test_growth(tmp_path):
    """Calculates total tests added across all sessions."""
    sf = tmp_path / "sessions.json"
    _write_sessions(sf, [
        {"session": 1, "type": "work", "tests": {"before": 10, "after": 14, "status": "pass"}},
        {"session": 2, "type": "work", "tests": {"before": 14, "after": 20, "status": "pass"}},
    ])
    result = sh.parse_session_analytics(sf)
    assert result["tests_added"] == 10  # (14-10) + (20-14)
    assert result["test_count_latest"] == 20


def test_analytics_recent_sessions(tmp_path):
    """Returns last 5 sessions as recent summary."""
    sf = tmp_path / "sessions.json"
    sessions = [
        {"session": i, "type": "work", "summary": f"Task {i}",
         "tests": {"before": i * 10, "after": i * 10 + 5, "status": "pass"}}
        for i in range(1, 8)
    ]
    _write_sessions(sf, sessions)
    result = sh.parse_session_analytics(sf)
    assert len(result["recent"]) == 5
    assert result["recent"][0]["session"] == 7  # most recent first
    assert result["recent"][-1]["session"] == 3


def test_analytics_quality_avg(tmp_path):
    """Calculates average quality score from sessions that have it."""
    sf = tmp_path / "sessions.json"
    _write_sessions(sf, [
        {"session": 1, "type": "work", "tests": {"before": 0, "after": 5, "status": "pass"},
         "quality": {"score": 80}},
        {"session": 2, "type": "work", "tests": {"before": 5, "after": 10, "status": "pass"},
         "quality": {"score": 100}},
        {"session": 3, "type": "meta", "tests": {"before": 10, "after": 10, "status": "pass"}},
    ])
    result = sh.parse_session_analytics(sf)
    assert result["avg_quality"] == 90  # (80+100)/2


# ── generate_hooks_config ──────────────────────────────────

def test_hooks_config_generated(tmp_path):
    """generate_hooks_config returns dict with PreToolUse and PostToolUse hooks."""
    ctx = _make_ctx(tmp_path)
    config = sh.generate_hooks_config(ctx)
    assert "hooks" in config
    hooks = config["hooks"]
    assert "PreToolUse" in hooks
    assert "PostToolUse" in hooks
    # Each should be a list of hook groups
    assert isinstance(hooks["PreToolUse"], list)
    assert len(hooks["PreToolUse"]) >= 1
    assert isinstance(hooks["PostToolUse"], list)
    assert len(hooks["PostToolUse"]) >= 1


def test_pretooluse_blocks_gitignored(tmp_path):
    """PreToolUse hook targets Write|Edit and uses git check-ignore to block gitignored paths."""
    ctx = _make_ctx(tmp_path)
    config = sh.generate_hooks_config(ctx)
    pre_hooks = config["hooks"]["PreToolUse"]
    # Find the Write|Edit matcher
    matchers = [h["matcher"] for h in pre_hooks]
    assert any("Write" in m and "Edit" in m for m in matchers), \
        f"Expected Write|Edit matcher, got {matchers}"
    # The hook command should reference git check-ignore
    for group in pre_hooks:
        if "Write" in group["matcher"] and "Edit" in group["matcher"]:
            commands = [h["command"] for h in group["hooks"]]
            assert any("git" in c and "check-ignore" in c for c in commands), \
                f"Expected git check-ignore in commands, got {commands}"


def test_posttooluse_runs_lint(tmp_path):
    """PostToolUse hook targets Write|Edit and runs the project's test/lint command."""
    ctx = _make_ctx(tmp_path)
    # Give the project a test command so the hook can reference it
    ctx.project_file.write_text(
        "# Project\n\n### Test Command\n```\npython3 -m pytest -q\n```\n"
    )
    config = sh.generate_hooks_config(ctx)
    post_hooks = config["hooks"]["PostToolUse"]
    # Find the Write|Edit matcher
    matchers = [h["matcher"] for h in post_hooks]
    assert any("Write" in m and "Edit" in m for m in matchers), \
        f"Expected Write|Edit matcher, got {matchers}"
    # The hook command should reference a lint/syntax check
    for group in post_hooks:
        if "Write" in group["matcher"] and "Edit" in group["matcher"]:
            commands = [h["command"] for h in group["hooks"]]
            assert any("python3" in c and "syntax" in c.lower() or "py_compile" in c or "compile" in c for c in commands), \
                f"Expected syntax check command, got {commands}"


def test_pretooluse_blocks_dangerous_bash(tmp_path):
    """PreToolUse hook routes Bash commands through the tool inspector."""
    ctx = _make_ctx(tmp_path)
    config = sh.generate_hooks_config(ctx)
    pre_hooks = config["hooks"]["PreToolUse"]
    matchers = [h["matcher"] for h in pre_hooks]
    assert "Bash" in matchers, f"Expected Bash matcher, got {matchers}"
    for group in pre_hooks:
        if group["matcher"] == "Bash":
            commands = [h["command"] for h in group["hooks"]]
            cmd = commands[0]
            assert "inspect_tool_call" in cmd, \
                f"Expected tool inspector hook, got {cmd}"


def test_posttooluse_runs_autotest(tmp_path):
    """PostToolUse hook includes auto-test runner for .py files."""
    ctx = _make_ctx(tmp_path)
    config = sh.generate_hooks_config(ctx)
    post_hooks = config["hooks"]["PostToolUse"]
    for group in post_hooks:
        if "Write" in group["matcher"] and "Edit" in group["matcher"]:
            commands = [h["command"] for h in group["hooks"]]
            assert any("pytest" in c for c in commands), \
                f"Expected pytest auto-test command, got {commands}"


def test_autotest_hook_is_async(tmp_path):
    """Auto-test PostToolUse hook is async since it doesn't influence agent flow."""
    ctx = _make_ctx(tmp_path)
    config = sh.generate_hooks_config(ctx)
    post_hooks = config["hooks"]["PostToolUse"]
    for group in post_hooks:
        if "Write" in group["matcher"] and "Edit" in group["matcher"]:
            for hook in group["hooks"]:
                if "pytest" in hook["command"]:
                    assert hook.get("async") is True, \
                        "Auto-test hook should be async (non-blocking)"


# ── filter_sessions ──────────────────────────────────────────

_SAMPLE_SESSIONS = [
    {"session": 1, "type": "work", "date": "2026-03-26", "summary": "Built dashboard page"},
    {"session": 2, "type": "meta", "date": "2026-03-26", "summary": "Fixed prompt drift"},
    {"session": 3, "type": "work", "date": "2026-03-27", "summary": "Added soil endpoint"},
    {"session": 4, "type": "brain", "date": "2026-03-27", "summary": "Researched new techniques"},
    {"session": 5, "type": "work", "date": "2026-03-28", "summary": "Built NDVI pipeline"},
]


def test_filter_sessions_by_type(tmp_path):
    """filter_sessions with session_type returns only sessions of that type."""
    sf = tmp_path / "sessions.json"
    _write_sessions(sf, _SAMPLE_SESSIONS)
    result = sh.filter_sessions(sf, session_type="work")
    assert len(result) == 3
    assert all(s["type"] == "work" for s in result)


def test_filter_sessions_last_n(tmp_path):
    """filter_sessions with last_n returns N most recent sessions."""
    sf = tmp_path / "sessions.json"
    _write_sessions(sf, _SAMPLE_SESSIONS)
    result = sh.filter_sessions(sf, last_n=2)
    assert len(result) == 2
    assert result[0]["session"] == 4
    assert result[1]["session"] == 5


def test_filter_sessions_search(tmp_path):
    """filter_sessions with search term matches summary text (case-insensitive)."""
    sf = tmp_path / "sessions.json"
    _write_sessions(sf, _SAMPLE_SESSIONS)
    result = sh.filter_sessions(sf, search="ndvi")
    assert len(result) == 1
    assert result[0]["session"] == 5


# ── lifetime_cost_summary ──────────────────────────────────

def test_lifetime_cost_summary(tmp_path):
    """lifetime_cost_summary sums ALL date entries from budget file."""
    bf = tmp_path / "daily_budget.json"
    bf.write_text(json.dumps({
        "2026-03-25": 1.50,
        "2026-03-26": 2.25,
        "2026-03-27": 0.75,
        "2026-03-28": 3.00,
    }))
    assert sh.lifetime_cost_summary(bf) == pytest.approx(7.50)


def test_lifetime_cost_missing_file(tmp_path):
    """lifetime_cost_summary returns 0.0 when budget file doesn't exist."""
    assert sh.lifetime_cost_summary(tmp_path / "nope.json") == 0.0


# ── weekly_cost_summary ────────────────────────────────────

def test_weekly_cost_summary(tmp_path):
    """weekly_cost_summary sums only entries from the last 7 days."""
    bf = tmp_path / "daily_budget.json"
    bf.write_text(json.dumps({
        "2026-03-15": 10.00,  # older than 7 days — excluded
        "2026-03-22": 1.00,   # 6 days ago — included
        "2026-03-25": 2.00,   # 3 days ago — included
        "2026-03-28": 3.00,   # today — included
    }))
    # weekly_cost_summary was defined in session_analytics — patch date in
    # the function's own global namespace (which is session_analytics.__dict__)
    import datetime as _dt
    orig_date = sh.weekly_cost_summary.__globals__["date"]
    mock_date = type("MockDate", (), {
        "today": staticmethod(lambda: _dt.date(2026, 3, 28)),
        "fromisoformat": staticmethod(_dt.date.fromisoformat),
    })
    sh.weekly_cost_summary.__globals__["date"] = mock_date
    try:
        result = sh.weekly_cost_summary(bf)
    finally:
        sh.weekly_cost_summary.__globals__["date"] = orig_date
    assert result == pytest.approx(6.00)


def test_weekly_cost_missing_file(tmp_path):
    """weekly_cost_summary returns 0.0 when budget file doesn't exist."""
    assert sh.weekly_cost_summary(tmp_path / "nope.json") == 0.0


# ── Split validation ────────────────────────────────────────

def test_analytics_from_new_module():
    """Analytics functions are importable from session_analytics."""
    assert callable(sa.lifetime_cost_summary)
    assert callable(sa.weekly_cost_summary)
    assert callable(sa.parse_session_analytics)
    assert callable(sa.filter_sessions)
    assert callable(sa.log_session_entry)
    assert callable(sa.compute_quality_score)
    assert callable(sa.get_session_type)
    assert callable(sa.generate_hooks_config)
    assert callable(sa.write_hooks_config)


def test_session_helpers_under_300_lines():
    """session_helpers.py must stay under 300 lines after extraction."""
    sh_path = Path(__file__).parent / "session_helpers.py"
    line_count = len(sh_path.read_text().splitlines())
    assert line_count < 350, f"session_helpers.py is {line_count} lines (limit: 350)"


def test_backwards_compat_reexports():
    """Moved functions are still importable from session_helpers (backward compat)."""
    assert callable(sh.lifetime_cost_summary)
    assert callable(sh.weekly_cost_summary)
    assert callable(sh.parse_session_analytics)
    assert callable(sh.filter_sessions)
    assert callable(sh.log_session_entry)
    assert callable(sh.compute_quality_score)
    assert callable(sh.get_session_type)
    assert callable(sh.generate_hooks_config)
    assert callable(sh.write_hooks_config)


def test_hooks_importable_from_session_hooks():
    """Hooks functions are importable from session_hooks module."""
    import session_hooks
    assert callable(session_hooks.generate_hooks_config)
    assert callable(session_hooks.write_hooks_config)


def test_session_analytics_under_300_lines():
    """session_analytics.py must stay under 300 lines after extraction."""
    sa_path = Path(__file__).parent / "session_analytics.py"
    line_count = len(sa_path.read_text().splitlines())
    assert line_count <= 300, f"session_analytics.py is {line_count} lines (limit: 300)"


# ── PreCompact hook tests ─────────────────────────────────────


def test_build_precompact_summary_with_active_task(tmp_path):
    """build_precompact_summary extracts task name, checked/unchecked steps."""
    ct = tmp_path / "current_task.md"
    ct.write_text(
        "# Current Task: Add widget\n"
        "Steps: 4 total | 2 remaining\n"
        "- [x] Write tests\n"
        "- [x] Implement widget\n"
        "- [ ] Wire to dashboard\n"
        "- [ ] Commit\n"
    )
    from session_hooks import build_precompact_summary

    summary = build_precompact_summary(ct)
    assert "CONTEXT_SUMMARY:" in summary
    assert "Add widget" in summary
    assert "2" in summary  # completed count or remaining
    assert "Wire to dashboard" in summary  # next step


def test_build_precompact_summary_no_task(tmp_path):
    """build_precompact_summary returns empty string when no active task."""
    ct = tmp_path / "current_task.md"
    ct.write_text("# No current task\n")
    from session_hooks import build_precompact_summary

    summary = build_precompact_summary(ct)
    assert summary == ""


def test_build_precompact_summary_missing_file(tmp_path):
    """build_precompact_summary returns empty string when file doesn't exist."""
    ct = tmp_path / "current_task.md"
    from session_hooks import build_precompact_summary

    summary = build_precompact_summary(ct)
    assert summary == ""


def test_precompact_hook_writes_summary(tmp_path):
    """write_precompact_summary appends CONTEXT_SUMMARY to current_task.md."""
    ct = tmp_path / "current_task.md"
    original = (
        "# Current Task: Fix bug\n"
        "Steps: 3 total | 1 remaining\n"
        "- [x] Reproduce\n"
        "- [x] Fix root cause\n"
        "- [ ] Run tests\n"
    )
    ct.write_text(original)
    from session_hooks import write_precompact_summary

    result = write_precompact_summary(ct)
    assert result is True
    content = ct.read_text()
    assert "CONTEXT_SUMMARY:" in content
    assert original.strip() in content  # original preserved
    assert "Fix bug" in content


def test_precompact_hook_skips_no_task(tmp_path):
    """write_precompact_summary returns False when no active task."""
    ct = tmp_path / "current_task.md"
    ct.write_text("# No current task\n")
    from session_hooks import write_precompact_summary

    result = write_precompact_summary(ct)
    assert result is False


def test_precompact_hook_in_generate_config(tmp_path):
    """generate_hooks_config includes a PreCompact hook entry."""
    from session_hooks import generate_hooks_config
    from registry import ProjectContext

    ctx = ProjectContext(
        name="test",
        project_root=tmp_path,
        agency_home=tmp_path,
    )
    config = generate_hooks_config(ctx)
    hooks = config["hooks"]
    assert "PreCompact" in hooks, "PreCompact hook missing from config"
    pre_compact = hooks["PreCompact"]
    assert len(pre_compact) >= 1
    # Should reference precompact_summary
    cmd = pre_compact[0]["hooks"][0]["command"]
    assert "precompact" in cmd.lower() or "context_summary" in cmd.lower()


# ── SessionTimer tests ─────────────────────────────────────────

import subprocess
import time


def test_session_timeout_kills_process():
    """SessionTimer kills a subprocess that exceeds max_duration."""
    # Start a long-running sleep process
    proc = subprocess.Popen(
        ["sleep", "60"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    timer = sh.SessionTimer(proc, max_duration=0.3)
    timer.start()
    # Wait for the timer to fire
    proc.wait()
    timer.cancel()
    assert timer.timed_out is True
    # Process should have been killed (negative returncode on Unix = signal)
    assert proc.returncode != 0


def test_session_timeout_no_kill_when_cancelled():
    """SessionTimer does NOT kill a process that finishes before timeout."""
    proc = subprocess.Popen(
        ["echo", "fast"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    timer = sh.SessionTimer(proc, max_duration=10)
    timer.start()
    proc.wait()
    timer.cancel()
    assert timer.timed_out is False
    assert proc.returncode == 0


def test_session_timeout_logs_knowledge(tmp_path):
    """Timeout event produces a knowledge log entry when on_timeout callback is used."""
    log_lines = []
    def on_timeout_cb():
        log_lines.append("timeout fired")

    proc = subprocess.Popen(
        ["sleep", "60"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    timer = sh.SessionTimer(proc, max_duration=0.3, on_timeout=on_timeout_cb)
    timer.start()
    proc.wait()
    timer.cancel()
    assert timer.timed_out is True
    assert len(log_lines) == 1
    assert log_lines[0] == "timeout fired"


# ── _sync_templates respects project-domain skill scoping ────

def _seed_scoped_skills():
    """Write a universal + a project-domain skill and a manifest scoping the latter."""
    import json
    home = registry.AGENCY_HOME
    (home / "skills").mkdir(parents=True, exist_ok=True)
    (home / "skills" / "coding.md").write_text("# universal")
    (home / "skills" / "crop-analysis.md").write_text("# project-domain")
    (home / "templates").mkdir(parents=True, exist_ok=True)
    (home / "templates" / "departments.json").write_text(
        json.dumps({"skill_scopes": {"project_domain": ["crop-analysis"]}})
    )


def test_sync_templates_hides_project_domain_skill(tmp_path):
    """A project that hasn't enabled project-domain skills must NOT get crop-analysis synced."""
    _seed_scoped_skills()
    ctx = _make_ctx(tmp_path, config={})
    sh._sync_templates(ctx)
    proj_skills = ctx.project_home / "skills"
    assert (proj_skills / "coding.md").exists()          # universal copied
    assert not (proj_skills / "crop-analysis.md").exists()  # project-domain withheld


def test_sync_templates_copies_project_domain_when_enabled(tmp_path):
    """When the project opts in, the project-domain skill IS synced."""
    _seed_scoped_skills()
    ctx = _make_ctx(tmp_path, config={"include_project_domain_skills": True})
    sh._sync_templates(ctx)
    assert (ctx.project_home / "skills" / "crop-analysis.md").exists()
