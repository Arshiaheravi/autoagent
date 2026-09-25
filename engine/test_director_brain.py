#!/usr/bin/env python3
"""Tests for director_brain.py."""
import sys
import types


def test_ask_brain_uses_council_when_available(monkeypatch):
    council = types.ModuleType("council")
    seen = {}
    council.convene_council = lambda question, context="", chairman_prompt=None: seen.update({"question": question, "context": context}) or {
        "winner": "Codex",
        "confidence": "HIGH",
        "synthesis": "Recommendation:\n1. Do the entropy checker first.\nConfidence: HIGH",
    }
    helpers = types.ModuleType("director_helpers")
    helpers.get_agency_context = lambda: "Agency context"
    director_ai = types.ModuleType("director_ai")
    director_ai.ask_claude = lambda question: "Claude answer"
    director_ai._fallback_answer = lambda question: "Fallback answer"

    monkeypatch.setitem(sys.modules, "council", council)
    monkeypatch.setitem(sys.modules, "director_helpers", helpers)
    monkeypatch.setitem(sys.modules, "director_ai", director_ai)
    monkeypatch.delitem(sys.modules, "director_brain", raising=False)

    import director_brain
    result = director_brain.ask_brain("What next?", active_project="autoagent")
    assert "entropy checker" in result
    assert "Recommendation" not in result
    assert "Confidence" not in result
    assert "Active ship: autoagent" in seen["context"]


def test_ask_brain_falls_back_when_council_errors(monkeypatch):
    council = types.ModuleType("council")
    council.convene_council = lambda question, context="", chairman_prompt=None: {"error": "Not enough council members responded"}
    helpers = types.ModuleType("director_helpers")
    helpers.get_agency_context = lambda: "Agency context"
    director_ai = types.ModuleType("director_ai")
    director_ai.ask_claude = lambda question: "Claude fallback"
    director_ai._fallback_answer = lambda question: "DB fallback"

    monkeypatch.setitem(sys.modules, "council", council)
    monkeypatch.setitem(sys.modules, "director_helpers", helpers)
    monkeypatch.setitem(sys.modules, "director_ai", director_ai)
    monkeypatch.delitem(sys.modules, "director_brain", raising=False)

    import director_brain
    assert director_brain.ask_brain("What next?") == "Claude fallback"


def test_ask_brain_greeting_is_terse(monkeypatch):
    council = types.ModuleType("council")
    council.convene_council = lambda question, context="": (_ for _ in ()).throw(AssertionError("council should not run"))
    helpers = types.ModuleType("director_helpers")
    helpers.get_agency_context = lambda: "Agency context"
    director_ai = types.ModuleType("director_ai")
    director_ai.ask_claude = lambda question: (_ for _ in ()).throw(AssertionError("claude should not run"))
    director_ai._fallback_answer = lambda question: (_ for _ in ()).throw(AssertionError("fallback should not run"))

    monkeypatch.setitem(sys.modules, "council", council)
    monkeypatch.setitem(sys.modules, "director_helpers", helpers)
    monkeypatch.setitem(sys.modules, "director_ai", director_ai)
    monkeypatch.delitem(sys.modules, "director_brain", raising=False)

    import director_brain
    result = director_brain.ask_brain("hello")
    assert result == "Agency shell is up. How could I help you today?"


def test_naturalize_reply_flattens_lists(monkeypatch):
    council = types.ModuleType("council")
    council.convene_council = lambda question, context="", chairman_prompt=None: (_ for _ in ()).throw(AssertionError("council should not run"))
    helpers = types.ModuleType("director_helpers")
    helpers.get_agency_context = lambda: "Agency context"
    director_ai = types.ModuleType("director_ai")
    director_ai.ask_claude = lambda question: "Claude fallback"
    director_ai._fallback_answer = lambda question: "DB fallback"

    monkeypatch.setitem(sys.modules, "council", council)
    monkeypatch.setitem(sys.modules, "director_helpers", helpers)
    monkeypatch.setitem(sys.modules, "director_ai", director_ai)
    monkeypatch.delitem(sys.modules, "director_brain", raising=False)

    import director_brain
    result = director_brain._naturalize_reply("**Recommendation:**\n1. Fix agent routing.\n2. Check session #26.\nConfidence: HIGH")
    assert result == "Fix agent routing. Check session #26."
