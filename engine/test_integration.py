#!/usr/bin/env python3
"""Integration tests — full intake -> run cycle."""
import json
import os
import shutil
import pytest
from pathlib import Path
from unittest.mock import patch
from io import StringIO

import registry


@pytest.fixture(autouse=True)
def setup_agency(isolated_agency_home):
    """Set up a minimal agency structure for each test."""
    home = isolated_agency_home
    # Shared skills
    (home / "skills" / "coding.md").write_text("# Coding")
    (home / "skills" / "testing.md").write_text("# Testing")
    # Universal agent templates
    for agent in ["architect", "test-writer", "frontend", "infra", "ux-researcher", "educator"]:
        (home / "templates" / "agents" / f"{agent}.md").write_text(
            f"# {agent.replace('-', ' ').title()}\n\nYou are the {agent} for {{{{project_name}}}}.\n"
        )
    # Shared prompt templates
    (home / "templates" / "PROMPT.md").write_text("# Universal PROMPT\nSession rules here.")
    (home / "templates" / "meta" / "PROMPT.md").write_text("# Meta prompt")
    (home / "templates" / "meta" / "BRAIN_PROMPT.md").write_text("# Brain prompt")
    yield


@pytest.fixture(autouse=True)
def _claude_binary_present():
    """Make the `claude` CLI look installed so run_session() proceeds under a
    mocked subprocess.Popen. Keeps these tests environment-independent — clean
    CI has no `claude` binary, which would otherwise short-circuit run_session."""
    import shutil
    _real_which = shutil.which

    def _which(cmd, *args, **kwargs):
        if str(cmd).endswith("claude") or cmd == run_module.CLAUDE:
            return "/usr/local/bin/claude"
        return _real_which(cmd, *args, **kwargs)

    with patch("shutil.which", side_effect=_which):
        yield


import intake

# Import engine/run.py explicitly — the V1 root-level run.py shadows it
# when pytest adds rootdir to sys.path
import importlib.util
_run_spec = importlib.util.spec_from_file_location(
    "engine_run", Path(__file__).parent / "run.py"
)
run_module = importlib.util.module_from_spec(_run_spec)
_run_spec.loader.exec_module(run_module)

_runner_spec = importlib.util.spec_from_file_location(
    "engine_runner", Path(__file__).parent / "runner.py"
)
runner_module = importlib.util.module_from_spec(_runner_spec)
_runner_spec.loader.exec_module(runner_module)


def _create_test_project(tmp_path):
    """Helper: create a project via setup_project and return the context."""
    project_root = tmp_path / "testproject"
    project_root.mkdir()
    return intake.setup_project(
        name="testproject",
        project_root=project_root,
        project_md="# Project: TestProject\n\nA test project.",
        north_star_md="# North Star\n\nShip fast.",
        backlog_md="# Backlog\n\n- [ ] Build feature A [agent: architect]\n- [ ] Write tests",
        tech_stack="Python",
        test_command="echo 'no tests yet'",
    )


# ── Test 1: setup_project() then run_project(test_mode=True) succeeds ──

def test_intake_then_run_test_mode(tmp_path, capsys):
    """After setup_project(), run_project(test_mode=True) should succeed without error."""
    ctx = _create_test_project(tmp_path)

    # run_project in test_mode doesn't spawn Claude — it just validates the setup
    runner_module.run_project(ctx, test_mode=True)

    captured = capsys.readouterr()
    assert "DRY RUN" in captured.out
    assert "Everything looks good" in captured.out
    # Should report prompt length and found skills
    assert "Prompt length" in captured.out
    assert "Skills found" in captured.out
    assert "Memory files" in captured.out


# ── Test 2: after setup_project, all required files exist for run_session ──

def test_intake_creates_runnable_project(tmp_path):
    """After setup_project(), all files needed by run_session/build_prompt must exist."""
    ctx = _create_test_project(tmp_path)

    # Simulate what run_session does: sync templates then build prompt
    run_module._sync_templates(ctx)

    # Core files that build_prompt reads
    assert ctx.project_file.exists(), "PROJECT.md missing"
    assert ctx.north_star_file.exists(), "NORTH_STAR.md missing"

    # PROMPT.md must be accessible (synced from templates)
    assert ctx.prompt_file.exists() or (ctx.project_home / "PROMPT.md").exists(), \
        "PROMPT.md not accessible"

    # Memory files that build_prompt reads via tail()
    assert (ctx.memory_dir / "activity_log.md").exists(), "activity_log.md missing"
    assert (ctx.memory_dir / "backlog.md").exists(), "backlog.md missing"
    assert (ctx.memory_dir / "knowledge.md").exists(), "knowledge.md missing"
    assert (ctx.memory_dir / "current_task.md").exists(), "current_task.md missing"
    assert (ctx.memory_dir / "done.md").exists(), "done.md missing"

    # project.json with config
    pj = ctx.project_home / "project.json"
    assert pj.exists(), "project.json missing"
    data = json.loads(pj.read_text())
    assert "model" in data
    assert "session_max_turns" in data

    # Agents directory populated
    assert ctx.agents_dir.exists()
    assert (ctx.agents_dir / "architect.md").exists(), "architect agent missing"
    assert (ctx.agents_dir / "orchestrator.md").exists(), "orchestrator missing"

    # build_prompt should succeed without errors
    prompt = run_module.build_prompt(ctx, "work")
    assert len(prompt) > 100, "Prompt suspiciously short"
    assert "TestProject" in prompt


# ── Test 3: symlink resolves all paths ──

def test_symlink_resolves_all_paths(tmp_path):
    """The .autoagent symlink should make PROJECT.md, memory/*, and PROMPT.md readable."""
    ctx = _create_test_project(tmp_path)

    # Sync templates so PROMPT.md is in project_home
    run_module._sync_templates(ctx)

    project_root = tmp_path / "testproject"
    symlink = project_root / ".autoagent"

    # Symlink must exist and point to project_home
    assert symlink.is_symlink(), ".autoagent symlink not created"
    assert symlink.resolve() == ctx.project_home.resolve(), \
        f"Symlink target mismatch: {symlink.resolve()} != {ctx.project_home.resolve()}"

    # PROJECT.md readable via symlink
    project_md_via_symlink = symlink / "PROJECT.md"
    assert project_md_via_symlink.exists(), "PROJECT.md not readable via symlink"
    assert "TestProject" in project_md_via_symlink.read_text()

    # PROMPT.md readable via symlink (synced from templates)
    prompt_via_symlink = symlink / "PROMPT.md"
    assert prompt_via_symlink.exists(), "PROMPT.md not readable via symlink"

    # Memory files readable via symlink
    for mem_file in ["backlog.md", "current_task.md", "activity_log.md", "knowledge.md", "done.md"]:
        mem_path = symlink / "memory" / mem_file
        assert mem_path.exists(), f"memory/{mem_file} not readable via symlink"
        # Verify content is actually readable (not just the path existing)
        content = mem_path.read_text()
        assert isinstance(content, str) and len(content) > 0, \
            f"memory/{mem_file} is empty or unreadable via symlink"

    # NORTH_STAR.md readable via symlink
    ns_via_symlink = symlink / "NORTH_STAR.md"
    assert ns_via_symlink.exists(), "NORTH_STAR.md not readable via symlink"


# ── Tests 4-6: run_session emits events to live_events.jsonl ──

import event_emitter


def _fake_popen_events(events):
    """Create a mock Popen that yields stream-json lines."""
    from unittest.mock import MagicMock
    proc = MagicMock()
    proc.stdout = iter([json.dumps(e) + "\n" for e in events])
    proc.wait.return_value = None
    proc.returncode = 0
    return proc


def test_run_session_emits_start_event(tmp_path):
    """After run_session, live_events.jsonl should have a session_start event."""
    ctx = _create_test_project(tmp_path)
    run_module._sync_templates(ctx)
    # Clean any leftover events from prior tests (shared project_home)
    if ctx.events_file.exists():
        ctx.events_file.unlink()

    # Fake Claude CLI that returns a simple result
    fake_events = [
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "done"}]}},
        {"type": "result", "cost_usd": 0.01},
    ]
    with patch("subprocess.Popen", return_value=_fake_popen_events(fake_events)):
        run_module.run_session(ctx, "work", 1)

    events_file = ctx.events_file
    assert events_file.exists(), "live_events.jsonl not created"
    events = event_emitter.read_events(events_file)
    start_events = [e for e in events if e.get("type") == "session_start"]
    assert len(start_events) >= 1, f"No session_start event found. Events: {events}"
    assert start_events[0]["session"] == 1
    assert start_events[0]["project"] == "testproject"


def test_run_session_emits_tool_events(tmp_path):
    """tool_use events from Claude CLI should be logged to live_events.jsonl."""
    ctx = _create_test_project(tmp_path)
    run_module._sync_templates(ctx)
    if ctx.events_file.exists():
        ctx.events_file.unlink()

    fake_events = [
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Write", "input": {"file_path": "src/app.py"}},
        ]}},
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Bash", "input": {"command": "pytest"}},
        ]}},
        {"type": "result", "cost_usd": 0.02},
    ]
    with patch("subprocess.Popen", return_value=_fake_popen_events(fake_events)):
        run_module.run_session(ctx, "work", 2)

    events = event_emitter.read_events(ctx.events_file)
    tool_events = [e for e in events if e.get("type") == "tool_use"]
    assert len(tool_events) >= 2, f"Expected 2+ tool_use events, got {len(tool_events)}: {tool_events}"
    # Check first tool event has expected fields
    assert tool_events[0]["action"] == "writing"
    assert tool_events[0]["target"] == "src/app.py"


def test_run_session_emits_end_event(tmp_path):
    """After run_session completes, live_events.jsonl should have a session_end event."""
    ctx = _create_test_project(tmp_path)
    run_module._sync_templates(ctx)
    if ctx.events_file.exists():
        ctx.events_file.unlink()

    fake_events = [
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "done"}]}},
        {"type": "result", "cost_usd": 0.01},
    ]
    with patch("subprocess.Popen", return_value=_fake_popen_events(fake_events)):
        run_module.run_session(ctx, "work", 3)

    events = event_emitter.read_events(ctx.events_file)
    end_events = [e for e in events if e.get("type") == "session_end"]
    assert len(end_events) >= 1, f"No session_end event found. Events: {events}"
    assert end_events[0]["session"] == 3
    assert end_events[0]["project"] == "testproject"


# ── Tests 7-9: Multi-project isolation ──────────────────────────


def _register_three_projects(tmp_path):
    """Register 3 projects with distinct roots and return their contexts."""
    projects = []
    for name in ["alpha", "beta", "gamma"]:
        root = tmp_path / name
        root.mkdir()
        ctx = intake.setup_project(
            name=name,
            project_root=root,
            project_md=f"# Project: {name}\n\nProject {name} description.",
            north_star_md=f"# North Star\n\nShip {name} fast.",
            backlog_md=f"# Backlog\n\n- [ ] Build {name} feature",
            tech_stack="Python",
            test_command=f"echo '{name} tests'",
        )
        projects.append(ctx)
    return projects


def test_multi_project_isolated_paths(tmp_path):
    """3 registered projects have completely separate memory, sessions, and events paths."""
    projects = _register_three_projects(tmp_path)

    paths_seen = {"memory": set(), "sessions": set(), "events": set(), "home": set()}
    for ctx in projects:
        paths_seen["memory"].add(str(ctx.memory_dir))
        paths_seen["sessions"].add(str(ctx.sessions_file))
        paths_seen["events"].add(str(ctx.events_file))
        paths_seen["home"].add(str(ctx.project_home))

    # All 3 projects have unique paths — no overlap
    for key, s in paths_seen.items():
        assert len(s) == 3, f"{key} paths are not unique: {s}"

    # Each project's memory dir exists and has its own backlog content
    for ctx in projects:
        assert ctx.memory_dir.exists()
        backlog = (ctx.memory_dir / "backlog.md").read_text()
        assert ctx.name in backlog, f"Backlog for {ctx.name} doesn't contain project name"


def test_multi_project_independent_test_mode(tmp_path, capsys):
    """run_project(test_mode=True) works independently for each of 3 projects."""
    projects = _register_three_projects(tmp_path)

    for ctx in projects:
        runner_module.run_project(ctx, test_mode=True)

    captured = capsys.readouterr()
    # Each project should appear in the dry-run output
    for name in ["alpha", "beta", "gamma"]:
        assert f"DRY RUN for {name}" in captured.out, \
            f"DRY RUN not found for {name} in output"


def test_multi_project_events_isolation(tmp_path):
    """Events emitted for one project don't appear in another project's events file."""
    projects = _register_three_projects(tmp_path)

    # Sync templates for all projects (needed by run_session)
    for ctx in projects:
        run_module._sync_templates(ctx)
        if ctx.events_file.exists():
            ctx.events_file.unlink()

    # Run a fake session for each project with distinct session numbers
    fake_events = [
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "done"}]}},
        {"type": "result", "cost_usd": 0.01},
    ]
    for i, ctx in enumerate(projects):
        with patch("subprocess.Popen", return_value=_fake_popen_events(fake_events)):
            run_module.run_session(ctx, "work", 100 + i)

    # Verify each project's events only contain that project's data
    for i, ctx in enumerate(projects):
        events = event_emitter.read_events(ctx.events_file)
        project_names = {e.get("project") for e in events}
        assert project_names == {ctx.name}, \
            f"Project {ctx.name} events contain other projects: {project_names}"
        sessions = {e.get("session") for e in events if e.get("session") is not None}
        assert 100 + i in sessions, \
            f"Project {ctx.name} missing expected session {100 + i}, got {sessions}"


# ── Codex Review ──────────────────────────────────────────────

def test_codex_review_lgtm(tmp_path, isolated_agency_home):
    """codex_review returns lgtm when Codex approves the diff."""
    from council import codex_review

    ctx = registry.ProjectContext(
        name="testproj",
        project_root=tmp_path / "testproj",
        agency_home=isolated_agency_home,
        config={},
    )
    ctx.project_root.mkdir(parents=True, exist_ok=True)
    ctx.ensure_dirs()

    with patch("council.reviews._call_codex", return_value="LGTM — code looks clean."), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value.stdout = "+def foo():\n+    return 42\n"
        mock_run.return_value.returncode = 0

        result = codex_review(ctx, session_num=1)
        assert result["status"] == "lgtm"


def test_codex_review_issues_found(tmp_path, isolated_agency_home):
    """codex_review returns issues when Codex flags problems."""
    from council import codex_review

    ctx = registry.ProjectContext(
        name="testproj",
        project_root=tmp_path / "testproj",
        agency_home=isolated_agency_home,
        config={},
    )
    ctx.project_root.mkdir(parents=True, exist_ok=True)
    ctx.ensure_dirs()

    logged = []

    def mock_log(ctx, entry):
        logged.append(entry)

    with patch("council.reviews._call_codex", return_value="ISSUES FOUND\n- Missing error handling in foo()"), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value.stdout = "+def foo():\n+    return 42\n"
        mock_run.return_value.returncode = 0

        result = codex_review(ctx, session_num=5, log_fn=mock_log)
        assert result["status"] == "issues"
        assert len(logged) == 1
        assert "CODEX REVIEW" in logged[0]


def test_codex_review_no_diff(tmp_path, isolated_agency_home):
    """codex_review skips when there is no diff."""
    from council import codex_review

    ctx = registry.ProjectContext(
        name="testproj",
        project_root=tmp_path / "testproj",
        agency_home=isolated_agency_home,
        config={},
    )
    ctx.project_root.mkdir(parents=True, exist_ok=True)
    ctx.ensure_dirs()

    with patch("subprocess.run") as mock_run:
        mock_run.return_value.stdout = ""
        mock_run.return_value.returncode = 0

        result = codex_review(ctx, session_num=1)
        assert result["status"] == "skipped"


def test_codex_review_api_unavailable(tmp_path, isolated_agency_home):
    """codex_review skips gracefully when OpenAI API is unavailable."""
    from council import codex_review

    ctx = registry.ProjectContext(
        name="testproj",
        project_root=tmp_path / "testproj",
        agency_home=isolated_agency_home,
        config={},
    )
    ctx.project_root.mkdir(parents=True, exist_ok=True)
    ctx.ensure_dirs()

    with patch("council.reviews._call_codex", return_value=""), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value.stdout = "+def foo():\n+    return 42\n"
        mock_run.return_value.returncode = 0

        result = codex_review(ctx, session_num=1)
        assert result["status"] == "skipped"


# ── UX Review ─────────────────────────────────────────────────

def test_ux_review_pass(tmp_path, isolated_agency_home):
    """ux_review returns pass when UX is solid."""
    from council import ux_review

    ctx = registry.ProjectContext(
        name="testproj",
        project_root=tmp_path / "testproj",
        agency_home=isolated_agency_home,
        config={},
    )
    ctx.project_root.mkdir(parents=True, exist_ok=True)
    ctx.ensure_dirs()

    diff = "diff --git a/src/app/page.tsx b/src/app/page.tsx\n+<h1>Hello</h1>"
    with patch("council.reviews._call_claude", return_value="UX PASS — clean layout."), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value.stdout = diff
        mock_run.return_value.returncode = 0

        result = ux_review(ctx, session_num=1)
        assert result["status"] == "pass"


def test_ux_review_issues(tmp_path, isolated_agency_home):
    """ux_review returns issues when UX problems found."""
    from council import ux_review

    ctx = registry.ProjectContext(
        name="testproj",
        project_root=tmp_path / "testproj",
        agency_home=isolated_agency_home,
        config={},
    )
    ctx.project_root.mkdir(parents=True, exist_ok=True)
    ctx.ensure_dirs()

    logged = []

    def mock_log(ctx, entry):
        logged.append(entry)

    diff = "diff --git a/src/app/page.tsx b/src/app/page.tsx\n+<div style='font-size:8px'>"
    with patch("council.reviews._call_claude", return_value="UX ISSUES\n- Text too small for mobile"), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value.stdout = diff
        mock_run.return_value.returncode = 0

        result = ux_review(ctx, session_num=3, log_fn=mock_log)
        assert result["status"] == "issues"
        assert len(logged) == 1
        assert "UX REVIEW" in logged[0]


def test_ux_review_skips_non_frontend(tmp_path, isolated_agency_home):
    """ux_review skips when diff has no frontend files."""
    from council import ux_review

    ctx = registry.ProjectContext(
        name="testproj",
        project_root=tmp_path / "testproj",
        agency_home=isolated_agency_home,
        config={},
    )
    ctx.project_root.mkdir(parents=True, exist_ok=True)
    ctx.ensure_dirs()

    diff = "diff --git a/engine/run.py b/engine/run.py\n+# python only"
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.stdout = diff
        mock_run.return_value.returncode = 0

        result = ux_review(ctx, session_num=1)
        assert result["status"] == "skipped"


# ── Multi-model backend dispatch ──────────────────────────────

def test_stage1_routes_to_correct_backends(isolated_agency_home):
    """_stage1_collect dispatches to the right backend for each persona."""
    from council import _stage1_collect

    calls = {"claude": [], "codex": [], "gemini": [], "deepseek": []}

    def mock_claude(prompt, **kw):
        calls["claude"].append(True)
        return "Claude response"

    def mock_codex(prompt, **kw):
        calls["codex"].append(True)
        return "Codex response"

    def mock_gemini(prompt, **kw):
        calls["gemini"].append(True)
        return "Gemini response"

    def mock_deepseek(prompt, **kw):
        calls["deepseek"].append(True)
        return "DeepSeek response"

    with patch("council.executive._call_claude", mock_claude), \
         patch("council.executive._call_codex", mock_codex), \
         patch("council.executive._call_gemini", mock_gemini), \
         patch("council.executive._call_deepseek", mock_deepseek):
        results = _stage1_collect("Test question")

    backends_used = {r["backend"] for r in results}
    assert "claude" in backends_used
    assert "openai" in backends_used
    assert "gemini" in backends_used
    assert "deepseek" in backends_used
    assert len(calls["claude"]) >= 1
    assert len(calls["codex"]) >= 1
    assert len(calls["gemini"]) >= 1
    assert len(calls["deepseek"]) >= 1


def test_gemini_graceful_skip_no_key(isolated_agency_home):
    """_call_gemini returns empty string when no API key set."""
    from council import _call_gemini
    with patch.dict(os.environ, {"GEMINI_API_KEY": ""}, clear=False):
        result = _call_gemini("test")
        assert result == ""


def test_deepseek_graceful_skip_no_key(isolated_agency_home):
    """_call_deepseek returns empty string when no API key set."""
    from council import _call_deepseek
    with patch.dict(os.environ, {"DEEPSEEK_API_KEY": ""}, clear=False):
        result = _call_deepseek("test")
        assert result == ""


def test_stage2_ranking_falls_back_when_claude_empty(isolated_agency_home):
    """Peer ranking should fall back to another backend when Claude is unavailable."""
    from council import _stage2_rank

    stage1 = [
        {"name": "The Bull", "response": "Bull answer"},
        {"name": "Codex", "response": "Codex answer"},
    ]
    ranking = "FINAL RANKING:\n1. Response B\n2. Response A"

    with patch("council.backends._call_claude", return_value=""), \
         patch("council.backends._call_codex", return_value=ranking):
        result = _stage2_rank("Ship it?", stage1)

    assert result["aggregate"][0]["label"] == "B"
    assert result["aggregate"][0]["name"] == "Codex"


def test_stage3_synthesis_falls_back_when_claude_empty(isolated_agency_home):
    """Chairman synthesis should fall back to another backend when Claude is unavailable."""
    from council import _stage3_synthesize

    stage1 = [
        {"name": "The Bull", "response": "Upside is good."},
        {"name": "Codex", "response": "Risk is manageable."},
    ]
    stage2 = {"aggregate": [{"name": "Codex", "avg_position": 1.0}]}

    with patch("council.backends._call_claude", return_value=""), \
         patch("council.backends._call_codex", return_value="Ship it carefully. Confidence: HIGH"):
        result = _stage3_synthesize("Ship it?", stage1, stage2)

    assert "Ship it carefully" in result
