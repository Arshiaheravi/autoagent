#!/usr/bin/env python3
"""Tests for the terminal director shell."""
import sys
import types


def _stub_director_helpers(monkeypatch):
    helpers = types.ModuleType("director_helpers")
    helpers.handle_command = lambda cmd: "<b>Agency Status</b>\nReady"
    brain = types.ModuleType("director_brain")
    brain.ask_brain = lambda text, active_project=None: f"<b>Brain</b>: {text} ({active_project})"
    router = types.ModuleType("director_router")

    class ShellState:
        def __init__(self, active_project=None):
            self.active_project = active_project

    router.ShellState = ShellState
    router.prompt_text = lambda state: "bridge> "
    def _route_shell_input(text, state):
        if text == "/quit":
            return types.SimpleNamespace(kind="quit", payload="", response="", state=state, status="")
        return types.SimpleNamespace(
            kind="command" if text.startswith("/") else "brain",
            payload="/status" if text.startswith("/") else text,
            response="",
            state=state,
            status="processing..." if text.startswith("/") else "thinking...",
        )
    router.route_shell_input = _route_shell_input
    monkeypatch.setitem(sys.modules, "director_helpers", helpers)
    monkeypatch.setitem(sys.modules, "director_brain", brain)
    monkeypatch.setitem(sys.modules, "director_router", router)
    monkeypatch.delitem(sys.modules, "director_shell", raising=False)


def test_render_terminal_strips_html(monkeypatch):
    _stub_director_helpers(monkeypatch)
    import director_shell
    rendered = director_shell.render_terminal("<b>Agency</b><br/>Ready")
    assert rendered == "Agency\nReady"


def test_route_input_command(monkeypatch):
    _stub_director_helpers(monkeypatch)
    import director_shell
    assert "Agency Status" in director_shell.route_input("/HELP")


def test_route_input_freetext(monkeypatch):
    _stub_director_helpers(monkeypatch)
    import director_shell
    assert "Brain" in director_shell.route_input("hello")


def test_handle_turn_passes_active_project_to_brain(monkeypatch):
    _stub_director_helpers(monkeypatch)
    import director_shell
    response, state, status = director_shell.handle_turn("hello", director_shell.ShellState(active_project="autoagent"))
    assert "autoagent" in response
    assert state.active_project == "autoagent"
    assert status == "thinking..."


def test_route_input_quit(monkeypatch):
    _stub_director_helpers(monkeypatch)
    import director_shell
    assert director_shell.route_input("/quit") is None


def test_status_text_for_command(monkeypatch):
    _stub_director_helpers(monkeypatch)
    import director_shell
    _, _, status = director_shell.handle_turn("/status", director_shell.ShellState())
    assert status == "processing..."


def test_status_text_for_freetext(monkeypatch):
    _stub_director_helpers(monkeypatch)
    import director_shell
    _, _, status = director_shell.handle_turn("hello", director_shell.ShellState())
    assert status == "thinking..."


def test_status_text_for_quit(monkeypatch):
    _stub_director_helpers(monkeypatch)
    import director_shell
    monkeypatch.setattr(director_shell, "route_shell_input", lambda text, state: types.SimpleNamespace(kind="quit", payload="", response="", state=state, status=""))
    _, _, status = director_shell.handle_turn("/quit", director_shell.ShellState())
    assert status == ""
