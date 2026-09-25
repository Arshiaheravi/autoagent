#!/usr/bin/env python3
"""Unit tests for director.py and director_helpers.py — Telegram bot helpers."""
import sys
import types
from pathlib import Path
import pytest


# --- Stub external dependencies so tests run without requests/agency_db ---

def _stub_modules(monkeypatch):
    """Inject stub modules for agency_db, registry, comms, requests."""
    # requests stub
    req_mod = types.ModuleType("requests")
    req_mod.post = lambda *a, **kw: types.SimpleNamespace(json=lambda: {"ok": True})
    req_mod.get = lambda *a, **kw: types.SimpleNamespace(
        json=lambda: {"ok": True, "result": []}, status_code=200
    )
    req_exc = types.ModuleType("requests.exceptions")
    req_exc.ReadTimeout = type("ReadTimeout", (Exception,), {})
    req_mod.exceptions = req_exc
    monkeypatch.setitem(sys.modules, "requests", req_mod)
    monkeypatch.setitem(sys.modules, "requests.exceptions", req_exc)

    # agency_db stub
    db_mod = types.ModuleType("agency_db")
    db_mod.agency_summary = lambda: {
        "projects": 3, "agents": 10, "total_sessions": 50,
        "knowledge_rules": 20, "tasks_pending": 5, "tasks_done": 30,
        "messages": 100,
    }
    db_mod.get_recent_sessions = lambda **kw: [
        {"session_num": 1, "project": "testproj", "session_type": "work",
         "success": True, "agent": "coder", "summary": "Built feature X"},
    ]
    db_mod.get_top_agents = lambda **kw: [
        {"project": "testproj", "name": "coder", "total_sessions": 10, "success_rate": 0.9},
    ]
    db_mod.get_agents = lambda name: [{"name": "coder"}]
    db_mod.get_knowledge = lambda name: []
    db_mod.get_tasks = lambda name, status: []
    db_mod.get_session_stats = lambda name: {"total": 10, "successes": 8}
    db_mod.log_message = lambda *a: None
    monkeypatch.setitem(sys.modules, "agency_db", db_mod)

    # registry stub
    reg_mod = types.ModuleType("registry")
    reg_mod.list_projects = lambda: [{"name": "testproj"}]
    # Stub get() to return a mock ProjectContext with memory_dir
    _mock_ctx = types.SimpleNamespace(
        name="testproj",
        memory_dir=Path("/tmp/_director_test_stub"),
    )
    reg_mod.get = lambda name: _mock_ctx
    monkeypatch.setitem(sys.modules, "registry", reg_mod)

    # orchestrator stub
    orch_mod = types.ModuleType("orchestrator")
    orch_mod.get_ready_tasks = lambda ctx: [
        {"id": "T1", "name": "Build API", "agent_hint": "coder", "depends_on": [], "priority": "high"},
    ]
    monkeypatch.setitem(sys.modules, "orchestrator", orch_mod)

    # agent_index stub
    agent_index_mod = types.ModuleType("agent_index")
    agent_index_mod.auto_route = lambda ctx, task_text: "coder"
    monkeypatch.setitem(sys.modules, "agent_index", agent_index_mod)

    # comms stub
    comms_mod = types.ModuleType("comms")
    comms_mod.set_paused = lambda val: None
    monkeypatch.setitem(sys.modules, "comms", comms_mod)


@pytest.fixture(autouse=True)
def stub_deps(monkeypatch):
    """Stub all external dependencies before importing director modules."""
    _stub_modules(monkeypatch)
    # Clear any cached imports so stubs take effect
    for mod_name in ["director", "director_helpers", "director_ai"]:
        monkeypatch.delitem(sys.modules, mod_name, raising=False)


# ---- Import verification tests ----

def test_director_helpers_importable():
    """director_helpers.py can be imported and exposes expected functions."""
    import director_helpers
    assert callable(director_helpers.get_agency_context)
    assert callable(director_helpers.handle_command)
    assert callable(director_helpers.ask_claude)
    assert callable(director_helpers._fallback_answer)


def test_director_importable():
    """director.py can still be imported and exposes send, handle_message, main."""
    import director
    assert callable(director.send)
    assert callable(director.handle_message)
    assert callable(director.main)


def test_director_reexports_helpers():
    """director.py re-exports helper functions for backward compatibility."""
    import director
    assert callable(director.get_agency_context)
    assert callable(director.handle_command)
    assert callable(director._fallback_answer)


# ---- handle_command tests ----

def test_handle_command_status():
    """handle_command('/status') returns agency overview."""
    import director_helpers
    result = director_helpers.handle_command("/status")
    assert "Agency Status" in result
    assert "Projects:" in result


def test_handle_command_help():
    """handle_command('/help') returns command list."""
    import director_helpers
    result = director_helpers.handle_command("/help")
    assert "/status" in result
    assert "/backlog" in result


def test_handle_command_agents():
    """handle_command('/agents') returns agent list."""
    import director_helpers
    result = director_helpers.handle_command("/agents")
    assert "coder" in result


def test_handle_command_unknown():
    """handle_command with unknown command returns helpful error."""
    import director_helpers
    result = director_helpers.handle_command("/nope")
    assert "Unknown command" in result


# ---- _fallback_answer tests ----

def test_fallback_answer_greeting():
    """_fallback_answer responds to greetings."""
    import director_helpers
    result = director_helpers._fallback_answer("hi")
    assert "Seb" in result or "projects" in result


def test_fallback_answer_session_question():
    """_fallback_answer responds to session questions."""
    import director_helpers
    result = director_helpers._fallback_answer("show me recent sessions")
    assert "session" in result.lower() or "#1" in result


def test_fallback_answer_unknown():
    """_fallback_answer returns guidance for unrecognized questions."""
    import director_helpers
    result = director_helpers._fallback_answer("what is the meaning of life")
    assert "agents" in result.lower() or "sessions" in result.lower() or "status" in result.lower()


# ---- get_agency_context tests ----

def test_get_agency_context_returns_string():
    """get_agency_context returns a non-empty context string."""
    import director_helpers
    ctx = director_helpers.get_agency_context()
    assert isinstance(ctx, str)
    assert "Director" in ctx
    assert "testproj" in ctx


# ---- Line count verification ----

def test_director_under_300_lines():
    """director.py must be under 300 lines after split."""
    from pathlib import Path
    src = Path(__file__).parent / "director.py"
    lines = len(src.read_text(encoding="utf-8").splitlines())
    assert lines <= 300, f"director.py is {lines} lines, must be ≤300"


def test_director_helpers_under_300_lines():
    """director_helpers.py must be under 300 lines."""
    from pathlib import Path
    src = Path(__file__).parent / "director_helpers.py"
    lines = len(src.read_text(encoding="utf-8").splitlines())
    assert lines <= 300, f"director_helpers.py is {lines} lines, must be ≤300"


def test_director_ai_under_300_lines():
    """director_ai.py must be under 300 lines."""
    from pathlib import Path
    src = Path(__file__).parent / "director_ai.py"
    lines = len(src.read_text(encoding="utf-8").splitlines())
    assert lines <= 300, f"director_ai.py is {lines} lines, must be ≤300"


def test_director_ai_importable():
    """director_ai.py can be imported and exposes expected functions."""
    import director_ai
    assert callable(director_ai.ask_claude)
    assert callable(director_ai._fallback_answer)


# ---- send() tests ----

def test_send_returns_true_on_success(monkeypatch):
    """send() returns True when Telegram API returns ok."""
    import director
    assert director.send("hello") is True


def test_send_returns_false_on_exception(monkeypatch):
    """send() returns False when requests.post raises."""
    req_mod = sys.modules["requests"]
    original_post = req_mod.post
    req_mod.post = lambda *a, **kw: (_ for _ in ()).throw(ConnectionError("fail"))
    try:
        import director
        assert director.send("hello") is False
    finally:
        req_mod.post = original_post


# ---- handle_message() routing tests ----

def test_handle_message_routes_commands():
    """handle_message routes slash commands to handle_command."""
    import director
    result = director.handle_message("/help")
    assert "/status" in result


def test_handle_message_routes_freetext_to_fallback():
    """handle_message routes freetext to _fallback_answer."""
    import director
    result = director.handle_message("hi")
    assert isinstance(result, str) and len(result) > 0


# ---- additional handle_command branches ----

def test_handle_command_backlog():
    """handle_command('/backlog') returns backlog info or empty message."""
    import director_helpers
    result = director_helpers.handle_command("/backlog")
    assert isinstance(result, str)
    # Either shows backlog items or says empty
    assert "Backlog" in result or "empty" in result.lower()


def test_handle_command_deploy():
    """handle_command('/deploy') returns deploy status."""
    import director_helpers
    result = director_helpers.handle_command("/deploy")
    assert "Deploy" in result


def test_handle_command_projects():
    """handle_command('/projects') returns projects list."""
    import director_helpers
    result = director_helpers.handle_command("/projects")
    assert "testproj" in result or "Projects" in result


def test_handle_command_orchestrator():
    """handle_command('/orchestrator testproj') returns next-task routing."""
    import director_helpers
    result = director_helpers.handle_command("/orchestrator testproj")
    assert "Orchestrator" in result
    assert "Build API" in result


def test_handle_command_brain(monkeypatch):
    """handle_command('/brain ...') routes to the brain module."""
    brain_mod = types.ModuleType("director_brain")
    brain_mod.cmd_brain = lambda cmd: "<b>Brain</b>\nUse the council."
    monkeypatch.setitem(sys.modules, "director_brain", brain_mod)
    import director_helpers
    result = director_helpers.handle_command("/brain what should we do next?")
    assert "Brain" in result


def test_handle_command_pause():
    """handle_command('/pause') returns pause confirmation."""
    import director_helpers
    result = director_helpers.handle_command("/pause")
    assert "PAUSE" in result.upper() or "pause" in result.lower()


def test_handle_command_resume():
    """handle_command('/resume') returns resume confirmation."""
    import director_helpers
    result = director_helpers.handle_command("/resume")
    assert "RESUME" in result.upper() or "resume" in result.lower()


# ---- _fallback_answer branch coverage ----

def test_fallback_answer_failure_question():
    """_fallback_answer handles failure-related questions."""
    import director_helpers
    result = director_helpers._fallback_answer("what failed recently?")
    assert isinstance(result, str) and len(result) > 0


def test_fallback_answer_agent_count():
    """_fallback_answer handles 'how many agents' questions."""
    import director_helpers
    result = director_helpers._fallback_answer("how many agents do we have?")
    assert "agent" in result.lower() or "53" in result


def test_fallback_answer_knowledge():
    """_fallback_answer handles knowledge questions."""
    import director_helpers
    result = director_helpers._fallback_answer("what rules have we learned?")
    assert "rule" in result.lower()


# ---- ask_claude fallback on missing CLI ----

def test_ask_claude_falls_back_on_missing_cli(monkeypatch):
    """ask_claude falls back when claude CLI is not found."""
    import director_ai
    # subprocess.run will raise FileNotFoundError for missing 'claude' binary
    import subprocess as sp
    original_run = sp.run
    monkeypatch.setattr(sp, "run", lambda *a, **kw: (_ for _ in ()).throw(FileNotFoundError()))
    result = director_ai.ask_claude("what's going on?")
    monkeypatch.setattr(sp, "run", original_run)
    assert isinstance(result, str) and len(result) > 0
