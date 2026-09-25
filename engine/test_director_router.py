#!/usr/bin/env python3
"""Tests for the terminal shell router."""
import sys
import types


def _stub_registry(monkeypatch):
    registry = types.ModuleType("registry")
    registry.list_projects = lambda: [
        {"name": "autoagent"},
        {"name": "StockCards"},
        {"name": "KitchenIntelligence"},
    ]
    monkeypatch.setitem(sys.modules, "registry", registry)
    monkeypatch.delitem(sys.modules, "director_router", raising=False)


def test_route_focus_project(monkeypatch):
    _stub_registry(monkeypatch)
    import director_router
    decision = director_router.route_shell_input("/ship StockCards", director_router.ShellState())
    assert decision.kind == "response"
    assert decision.state.active_project == "StockCards"


def test_route_next_task_uses_active_project(monkeypatch):
    _stub_registry(monkeypatch)
    import director_router
    decision = director_router.route_shell_input("what's next?", director_router.ShellState(active_project="autoagent"))
    assert decision.kind == "command"
    assert decision.payload == "/orchestrator autoagent"
    assert decision.status == "routing..."


def test_route_run_command_sets_focus(monkeypatch):
    _stub_registry(monkeypatch)
    import director_router
    decision = director_router.route_shell_input("run autoagent", director_router.ShellState())
    assert decision.kind == "command"
    assert decision.payload == "/run autoagent"
    assert decision.state.active_project == "autoagent"


def test_route_next_task_without_focus_prompts_for_ship(monkeypatch):
    _stub_registry(monkeypatch)
    import director_router
    decision = director_router.route_shell_input("what's next?", director_router.ShellState())
    assert decision.kind == "response"
    assert "No ship is in focus" in decision.response


def test_route_status_uses_orchestrator_when_ship_is_focused(monkeypatch):
    _stub_registry(monkeypatch)
    import director_router
    decision = director_router.route_shell_input("status update", director_router.ShellState(active_project="StockCards"))
    assert decision.kind == "command"
    assert decision.payload == "/orchestrator StockCards"
    assert decision.status == "checking route..."


def test_route_projects_question(monkeypatch):
    _stub_registry(monkeypatch)
    import director_router
    decision = director_router.route_shell_input("what projects do we have?", director_router.ShellState())
    assert decision.kind == "command"
    assert decision.payload == "/projects"
    assert decision.status == "checking ships..."


def test_route_run_it_uses_active_project(monkeypatch):
    _stub_registry(monkeypatch)
    import director_router
    decision = director_router.route_shell_input("run it", director_router.ShellState(active_project="autoagent"))
    assert decision.kind == "command"
    assert decision.payload == "/run autoagent"
    assert decision.state.active_project == "autoagent"


def test_route_brain_injects_focused_project(monkeypatch):
    _stub_registry(monkeypatch)
    import director_router
    decision = director_router.route_shell_input("we're getting ready to ship", director_router.ShellState(active_project="autoagent"))
    assert decision.kind == "brain"
    assert decision.payload == "For autoagent, we're getting ready to ship"


def test_prompt_text(monkeypatch):
    _stub_registry(monkeypatch)
    import director_router
    assert director_router.prompt_text(director_router.ShellState()) == "bridge> "
    assert director_router.prompt_text(director_router.ShellState(active_project="autoagent")) == "bridge:autoagent> "
