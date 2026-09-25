#!/usr/bin/env python3
"""Tests for run_session integration, run_project, run_continuous, frontend detection, constraint gate."""
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

import registry

# Import engine/run.py explicitly — V1 root-level run.py shadows it
import importlib.util
_run_spec = importlib.util.spec_from_file_location(
    "engine_run", Path(__file__).parent / "run.py"
)
run_module = importlib.util.module_from_spec(_run_spec)
_run_spec.loader.exec_module(run_module)

run_session = run_module.run_session
detect_frontend_changes = run_module.detect_frontend_changes
_constraint_gate = run_module._constraint_gate

# Import engine/runner.py — higher-level session loops extracted from run.py
_runner_spec = importlib.util.spec_from_file_location(
    "engine_runner", Path(__file__).parent / "runner.py"
)
runner_module = importlib.util.module_from_spec(_runner_spec)
_runner_spec.loader.exec_module(runner_module)

run_project = runner_module.run_project
run_continuous = runner_module.run_continuous


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


# ── run_project ────────────────────────────────────────────────

def test_run_project_multi_session_exits_at_limit(tmp_path):
    """run_project with tasks_limit=3 runs exactly 3 work sessions and updates counter."""
    ctx = _make_ctx(tmp_path)
    ctx.counter_file.write_text(json.dumps({"count": 1}))

    # Bypass retry wrapper — launch_with_retry delegates to run_fn (run_session)
    def passthrough_launch(ctx, stype, snum, run_fn=None):
        return True

    with patch.object(runner_module, "launch_with_retry", side_effect=passthrough_launch) as mock_launch, \
         patch.object(runner_module, "budget_ok", return_value=True), \
         patch.object(runner_module, "generate_dashboard"):
        run_project(ctx, tasks_limit=3)

    assert mock_launch.call_count == 3
    # Counter file updated after each session
    counter = json.loads(ctx.counter_file.read_text())
    assert counter["count"] == 4  # started at 1, ran 3 sessions → 4


def test_run_project_counter_increments_correctly(tmp_path):
    """run_project increments counter even when run_session returns False (non-work success)."""
    ctx = _make_ctx(tmp_path)
    ctx.counter_file.write_text(json.dumps({"count": 4}))

    # Session 4 is work (non-multiple of 5), return False = failed work session
    # Session 5 is meta, return True
    # Session 6 is work, return True → work_done = 1, done
    call_count = [0]
    def fake_launch(ctx, stype, snum, run_fn=None):
        call_count[0] += 1
        if call_count[0] == 1:
            return False  # session 4 fails
        return True  # sessions 5, 6 succeed

    with patch.object(runner_module, "launch_with_retry", side_effect=fake_launch), \
         patch.object(runner_module, "budget_ok", return_value=True), \
         patch.object(runner_module, "generate_dashboard"):
        run_project(ctx, tasks_limit=1)

    # Session 4 (work, fails) → work_done=0
    # Session 5 (meta, succeeds) → work_done=0 (only work sessions count)
    # Session 6 (work, succeeds) → work_done=1 → exit
    assert call_count[0] == 3
    counter = json.loads(ctx.counter_file.read_text())
    assert counter["count"] == 7  # started at 4, ran 3 → next is 7


# ── run_session + pre_push_gate integration ──────────────────

def test_run_session_rejects_on_red_tests(tmp_path):
    """When pre_push_gate fails (tests red), run_session returns False."""
    ctx = _make_ctx(tmp_path)
    ctx.project_file.write_text(
        "# Project\n\n### Test Command\n```\npython3 -c \"exit(1)\"\n```\n"
    )

    with patch.object(run_module, "_pre_push_gate", return_value=False) as mock_gate, \
         patch("subprocess.Popen") as mock_popen:
        # Simulate successful Claude subprocess
        mock_proc = mock_popen.return_value
        mock_proc.stdout = iter([])
        mock_proc.wait.return_value = None
        mock_proc.returncode = 0

        result = run_session(ctx, "work", 99)

    assert result is False
    mock_gate.assert_called_once_with(ctx, 99)


def test_run_session_pushes_on_green_tests(tmp_path):
    """When pre_push_gate passes (tests green), run_session returns True."""
    ctx = _make_ctx(tmp_path)
    ctx.project_file.write_text(
        "# Project\n\n### Test Command\n```\npython3 -c \"exit(0)\"\n```\n"
    )

    with patch.object(run_module, "_pre_push_gate", return_value=True) as mock_gate, \
         patch("subprocess.Popen") as mock_popen:
        mock_proc = mock_popen.return_value
        mock_proc.stdout = iter([])
        mock_proc.wait.return_value = None
        mock_proc.returncode = 0

        result = run_session(ctx, "work", 99)

    assert result is True
    mock_gate.assert_called_once_with(ctx, 99)


def test_red_test_logs_to_knowledge(tmp_path):
    """Failed pre-push gate writes 'BLOCKED: tests red' to knowledge.md."""
    ctx = _make_ctx(tmp_path)
    ctx.project_file.write_text(
        "# Project\n\n### Test Command\n```\npython3 -c \"exit(1)\"\n```\n"
    )

    with patch.object(run_module, "_pre_push_gate", return_value=False), \
         patch("subprocess.Popen") as mock_popen:
        mock_proc = mock_popen.return_value
        mock_proc.stdout = iter([])
        mock_proc.wait.return_value = None
        mock_proc.returncode = 0

        run_session(ctx, "work", 42)

    knowledge = (ctx.memory_dir / "knowledge.md").read_text()
    assert "BLOCKED" in knowledge
    assert "tests red" in knowledge.lower() or "tests failed" in knowledge.lower()


def test_run_session_locks_during_work_unlocks_after(tmp_path):
    """Work sessions lock instruction files before Claude and unlock after."""
    ctx = _make_ctx(tmp_path)

    with patch.object(run_module, "lock_ctx_instruction_files") as mock_lock, \
         patch.object(run_module, "unlock_ctx_instruction_files") as mock_unlock, \
         patch.object(run_module, "_pre_push_gate", return_value=True), \
         patch("subprocess.Popen") as mock_popen:
        mock_proc = mock_popen.return_value
        mock_proc.stdout = iter([])
        mock_proc.wait.return_value = None
        mock_proc.returncode = 0

        run_session(ctx, "work", 99)

    mock_lock.assert_called_once_with(ctx)
    mock_unlock.assert_called_once_with(ctx)


def test_run_session_skips_lock_for_meta(tmp_path):
    """Meta sessions do NOT lock instruction files (they need to edit them)."""
    ctx = _make_ctx(tmp_path)

    with patch.object(run_module, "lock_ctx_instruction_files") as mock_lock, \
         patch.object(run_module, "unlock_ctx_instruction_files") as mock_unlock, \
         patch("subprocess.Popen") as mock_popen:
        mock_proc = mock_popen.return_value
        mock_proc.stdout = iter([])
        mock_proc.wait.return_value = None
        mock_proc.returncode = 0

        run_session(ctx, "meta", 99)

    mock_lock.assert_not_called()
    mock_unlock.assert_not_called()


def test_run_session_falls_back_on_structured_weekly_limit_error(tmp_path):
    """Structured Claude limit events should trigger model fallback."""
    ctx = _make_ctx(tmp_path)

    mock_proc = MagicMock()
    mock_proc.stdout = iter([
        json.dumps({
            "type": "error",
            "message": "Claude Opus weekly usage limit reached. Resets in 6 days.",
        }) + "\n",
    ])
    mock_proc.wait.return_value = None
    mock_proc.returncode = 1

    with patch.object(run_module, "_pre_push_gate", return_value=True), \
         patch("subprocess.Popen", return_value=mock_proc), \
         patch("model_fallback.run_fallback", return_value=(True, "gpt-5.4", "fallback ok")) as mock_fallback:
        result = run_session(ctx, "work", 99)

    assert result is True
    mock_fallback.assert_called_once()
    last_error = (ctx.memory_dir / "_last_session_error.txt").read_text(encoding="utf-8")
    assert "weekly usage limit reached" in last_error.lower()


def test_run_session_falls_back_on_assistant_extra_usage_banner(tmp_path):
    """Assistant-text usage banners should also trigger fallback on non-zero exit."""
    ctx = _make_ctx(tmp_path)

    mock_proc = MagicMock()
    mock_proc.stdout = iter([
        json.dumps({
            "type": "assistant",
            "message": {"content": [
                {"type": "text", "text": "You're out of extra usage. Resets 4pm (America/Toronto)."},
            ]},
        }) + "\n",
    ])
    mock_proc.wait.return_value = None
    mock_proc.returncode = 1

    with patch.object(run_module, "_pre_push_gate", return_value=True), \
         patch("subprocess.Popen", return_value=mock_proc), \
         patch("model_fallback.run_fallback", return_value=(True, "gpt-5.4", "fallback ok")) as mock_fallback:
        result = run_session(ctx, "work", 100)

    assert result is True
    mock_fallback.assert_called_once()
    last_error = (ctx.memory_dir / "_last_session_error.txt").read_text(encoding="utf-8")
    assert "out of extra usage" in last_error.lower()


# ── run_continuous ──────────────────────────────────────────

def test_continuous_flag_runs_until_stopped(tmp_path):
    """--continuous flag loops sessions without exit until KeyboardInterrupt."""
    ctx = _make_ctx(tmp_path)
    ctx.counter_file.write_text(json.dumps({"count": 1}))

    call_count = [0]
    def fake_launch(ctx, stype, snum, run_fn=None):
        call_count[0] += 1
        if call_count[0] >= 5:
            raise KeyboardInterrupt
        return True

    with patch.object(runner_module, "launch_with_retry", side_effect=fake_launch), \
         patch.object(runner_module, "budget_ok", return_value=True), \
         patch.object(runner_module, "generate_dashboard"), \
         patch("time.sleep"):
        run_continuous([ctx])

    assert call_count[0] == 5


def test_continuous_respects_cooldown(tmp_path):
    """60s sleep between sessions in continuous mode."""
    ctx = _make_ctx(tmp_path)
    ctx.counter_file.write_text(json.dumps({"count": 1}))

    call_count = [0]
    def fake_launch(ctx, stype, snum, run_fn=None):
        call_count[0] += 1
        if call_count[0] >= 2:
            raise KeyboardInterrupt
        return True

    sleep_values = []
    def capture_sleep(seconds):
        sleep_values.append(seconds)

    with patch.object(runner_module, "launch_with_retry", side_effect=fake_launch), \
         patch.object(runner_module, "budget_ok", return_value=True), \
         patch.object(runner_module, "generate_dashboard"), \
         patch("time.sleep", side_effect=capture_sleep):
        run_continuous([ctx], cooldown=60)

    assert 60 in sleep_values


def test_continuous_until_time(tmp_path):
    """--until stops when current time passes the specified cutoff."""
    ctx = _make_ctx(tmp_path)
    ctx.counter_file.write_text(json.dumps({"count": 1}))

    from datetime import datetime, timedelta
    # Set cutoff to 1 second in the past — should stop immediately after first session
    past_cutoff = (datetime.now() - timedelta(seconds=1)).strftime("%H:%M")

    call_count = [0]
    def fake_launch(ctx, stype, snum, run_fn=None):
        call_count[0] += 1
        return True

    with patch.object(runner_module, "launch_with_retry", side_effect=fake_launch), \
         patch.object(runner_module, "budget_ok", return_value=True), \
         patch.object(runner_module, "generate_dashboard"), \
         patch("time.sleep"):
        run_continuous([ctx], until=past_cutoff)

    # Should have run 0 sessions since cutoff is already past
    assert call_count[0] == 0


def test_continuous_round_robin(tmp_path):
    """--all cycles through registered projects in round-robin order."""
    ctx1 = _make_ctx(tmp_path, name="proj1")
    ctx2 = _make_ctx(tmp_path, name="proj2")
    ctx1.counter_file.write_text(json.dumps({"count": 1}))
    ctx2.counter_file.write_text(json.dumps({"count": 1}))

    sessions_run = []
    call_count = [0]
    def fake_launch(ctx, stype, snum, run_fn=None):
        call_count[0] += 1
        sessions_run.append(ctx.name)
        if call_count[0] >= 4:
            raise KeyboardInterrupt
        return True

    with patch.object(runner_module, "launch_with_retry", side_effect=fake_launch), \
         patch.object(runner_module, "budget_ok", return_value=True), \
         patch.object(runner_module, "generate_dashboard"), \
         patch("time.sleep"):
        run_continuous([ctx1, ctx2])

    # Should alternate: proj1, proj2, proj1, proj2
    assert sessions_run == ["proj1", "proj2", "proj1", "proj2"]


# ── detect_frontend_changes ─────────────────────────────────

def test_detect_frontend_changes_html_edit(tmp_path):
    """Returns True when emitted events include edits to .html files."""
    events_file = tmp_path / "events.jsonl"
    import event_emitter
    event_emitter.emit(events_file, type="tool_use", action="editing", target="dashboard.html")
    event_emitter.emit(events_file, type="tool_use", action="writing", target="run.py")
    assert detect_frontend_changes(events_file) is True


def test_detect_frontend_changes_js_css(tmp_path):
    """Returns True when events include .js or .css file edits."""
    events_file = tmp_path / "events.jsonl"
    import event_emitter
    event_emitter.emit(events_file, type="tool_use", action="writing", target="app.js")
    assert detect_frontend_changes(events_file) is True

    events_file2 = tmp_path / "events2.jsonl"
    event_emitter.emit(events_file2, type="tool_use", action="editing", target="styles.css")
    assert detect_frontend_changes(events_file2) is True


def test_detect_frontend_changes_no_frontend(tmp_path):
    """Returns False when events contain only non-frontend file edits."""
    events_file = tmp_path / "events.jsonl"
    import event_emitter
    event_emitter.emit(events_file, type="tool_use", action="writing", target="models.py")
    event_emitter.emit(events_file, type="tool_use", action="reading", target="config.json")
    event_emitter.emit(events_file, type="session_start")
    assert detect_frontend_changes(events_file) is False


def test_detect_frontend_changes_empty(tmp_path):
    """Returns False when events file doesn't exist or is empty."""
    events_file = tmp_path / "events.jsonl"
    assert detect_frontend_changes(events_file) is False

    events_file.write_text("")
    assert detect_frontend_changes(events_file) is False


# ── _constraint_gate ──────────────────────────────────────────

def test_constraint_gate_detects_violations(tmp_path):
    """Constraint gate flags files matching NEVER rules in PROMPT.md."""
    ctx = _make_ctx(tmp_path)
    # Write a prompt file with a NEVER rule
    ctx.prompt_file.write_text(
        "# Prompt\n- NEVER `git add autoagent/` from project root\n"
    )

    # Mock git diff to return a violating file
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.stdout = "autoagent/memory/backlog.md\nengine/run.py\n"
        mock_run.return_value.returncode = 0
        violations = _constraint_gate(ctx)

    assert len(violations) == 1
    assert "autoagent/" in violations[0]["file"]


def test_constraint_gate_clean_when_no_violations(tmp_path):
    """Constraint gate returns empty list when no files match NEVER rules."""
    ctx = _make_ctx(tmp_path)
    ctx.prompt_file.write_text(
        "# Prompt\n- NEVER `git add autoagent/` from project root\n"
    )

    with patch("subprocess.run") as mock_run:
        mock_run.return_value.stdout = "engine/run.py\nengine/test_run.py\n"
        mock_run.return_value.returncode = 0
        violations = _constraint_gate(ctx)

    assert violations == []


def test_constraint_gate_no_prompt_file(tmp_path):
    """Constraint gate returns empty when prompt file doesn't exist."""
    ctx = _make_ctx(tmp_path)
    # Remove the prompt file
    if ctx.prompt_file.exists():
        ctx.prompt_file.unlink()
    violations = _constraint_gate(ctx)
    assert violations == []


# ── show_status ─────────────────────────────────────────────

def test_show_status_displays_analytics(tmp_path, capsys):
    """show_status prints session count, test growth, and recent sessions."""
    ctx = _make_ctx(tmp_path)
    ctx.sessions_file.write_text(json.dumps([
        {"session": 1, "type": "work", "summary": "Built feature A",
         "tests": {"before": 10, "after": 15, "status": "pass"}},
        {"session": 2, "type": "meta", "summary": "Improved prompts",
         "tests": {"before": 15, "after": 15, "status": "pass"}},
    ]))
    runner_module.show_status(ctx)
    out = capsys.readouterr().out
    assert "Sessions: 2" in out
    assert "Tests: 15" in out
    assert "+5 added" in out
    assert "Built feature A" in out
    assert "work: 1" in out


# ── runner.py extraction tests ──────────────────────────────

def test_runner_imports():
    """Functions extracted to runner.py can be imported directly from it."""
    runner_spec = importlib.util.spec_from_file_location(
        "engine_runner", Path(__file__).parent / "runner.py"
    )
    runner_mod = importlib.util.module_from_spec(runner_spec)
    runner_spec.loader.exec_module(runner_mod)
    assert callable(runner_mod.run_project)
    assert callable(runner_mod.run_continuous)
    assert callable(runner_mod.show_status)
    assert callable(runner_mod.ask_mode)
    assert callable(runner_mod.generate_dashboard)
