#!/usr/bin/env python3
"""Tests for syncing sessions.json into agency.db."""
import json
import threading

import pytest

import agency_db
from registry import ProjectContext
from session_db_sync import infer_success, sync_session_entry_to_agency_db, sync_sessions_file_to_agency_db


def _make_ctx(tmp_path, name="proj"):
    project_root = tmp_path / "repo"
    project_root.mkdir()
    agency_home = tmp_path / "agency"
    ctx = ProjectContext(name=name, project_root=project_root, agency_home=agency_home)
    ctx.ensure_dirs()
    return ctx


def test_sync_session_entry_upserts_db(tmp_path, monkeypatch):
    monkeypatch.setattr(agency_db, "_DB_PATH", tmp_path / "agency.db")
    monkeypatch.setattr(agency_db, "_local", threading.local())
    ctx = _make_ctx(tmp_path)
    entry = {
        "session": 7,
        "type": "work",
        "agent": "frontend",
        "success": True,
        "summary": "fixed layout",
        "files": ["app.css"],
        "tests": {"before": 2, "after": 5},
        "quality": {"score": 88},
        "cost_usd": 1.25,
    }

    sid = sync_session_entry_to_agency_db(ctx, entry)
    assert sid is not None
    sessions = agency_db.get_recent_sessions("proj")
    assert len(sessions) == 1
    assert sessions[0]["session_num"] == 7
    assert sessions[0]["agent"] == "frontend"
    assert sessions[0]["success"] == 1
    assert sessions[0]["tests_after"] == 5
    assert sessions[0]["quality_score"] == 88
    assert sessions[0]["success_source"] == "explicit"


def test_infer_success_for_legacy_entries():
    assert infer_success({"tests": {"status": "pass"}}) == (True, "inferred")
    assert infer_success({"notes": "GHOST - crashed"}) == (False, "inferred")
    assert infer_success({"quality": {"score": 82}}) == (True, "inferred")
    assert infer_success({"files": ["app.py"]}) == (True, "inferred")


def test_infer_success_parses_explicit_string_false_values():
    assert infer_success({"success": "false"}) == (False, "explicit")
    assert infer_success({"success": "0"}) == (False, "explicit")
    assert infer_success({"success": "failed"}) == (False, "explicit")
    assert infer_success({"success": "true"}) == (True, "explicit")


def test_sync_sessions_file_is_idempotent_and_rebuilds_agent_stats(tmp_path, monkeypatch):
    monkeypatch.setattr(agency_db, "_DB_PATH", tmp_path / "agency.db")
    monkeypatch.setattr(agency_db, "_local", threading.local())
    ctx = _make_ctx(tmp_path)
    ctx.sessions_file.write_text(json.dumps([
        {"session": 1, "type": "work", "agent": "architect", "success": True},
        {"session": 2, "type": "work", "agent": "architect", "success": False},
    ]), encoding="utf-8")

    assert sync_sessions_file_to_agency_db(ctx) == 2
    assert sync_sessions_file_to_agency_db(ctx) == 2
    assert len(agency_db.get_recent_sessions("proj", limit=10)) == 2
    assert {s["success_source"] for s in agency_db.get_recent_sessions("proj", limit=10)} == {"explicit"}
    agent = agency_db.get_agents("proj")[0]
    assert agent["name"] == "architect"
    assert agent["total_sessions"] == 2
    assert agent["successful"] == 1
    assert agent["failed"] == 1


def test_sync_legacy_entry_marks_success_inferred(tmp_path, monkeypatch):
    monkeypatch.setattr(agency_db, "_DB_PATH", tmp_path / "agency.db")
    monkeypatch.setattr(agency_db, "_local", threading.local())
    ctx = _make_ctx(tmp_path)
    entry = {
        "session": 3,
        "type": "work",
        "agent": "architect",
        "tests": {"status": "pass"},
    }

    sync_session_entry_to_agency_db(ctx, entry)
    session = agency_db.get_recent_sessions("proj")[0]
    assert session["success"] == 1
    assert session["success_source"] == "inferred"


def test_sync_sessions_file_raises_invalid_json_when_requested(tmp_path):
    ctx = _make_ctx(tmp_path)
    ctx.sessions_file.write_text("{not json", encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        sync_sessions_file_to_agency_db(ctx, raise_errors=True)


def test_sync_sessions_file_raises_non_list_when_requested(tmp_path):
    ctx = _make_ctx(tmp_path)
    ctx.sessions_file.write_text(json.dumps({"session": 1}), encoding="utf-8")

    with pytest.raises(ValueError):
        sync_sessions_file_to_agency_db(ctx, raise_errors=True)
