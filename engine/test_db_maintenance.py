#!/usr/bin/env python3
"""Tests for agency DB maintenance/audit helpers."""
import threading

import agency_db
import db_maintenance


def test_audit_database_reports_test_orphan_and_confidence(tmp_path, monkeypatch):
    monkeypatch.setattr(agency_db, "_DB_PATH", tmp_path / "agency.db")
    monkeypatch.setattr(agency_db, "_local", threading.local())
    monkeypatch.setattr(db_maintenance, "_registered_project_names", lambda: {"real"})

    agency_db.upsert_project("real", "/real")
    agency_db.upsert_project("testproject", "/tmp/test")
    agency_db.upsert_project("orphan", "/tmp/orphan")
    agency_db.upsert_session("real", 1, "work", agent="coder", success=True)
    agency_db.upsert_session("real", 2, "work", agent="coder", success=True,
                             success_source="inferred")

    report = db_maintenance.audit_database()
    assert "testproject" in report["test_projects"]
    assert sorted(report["orphan_projects"]) == ["orphan", "testproject"]
    assert report["success_sources"]["explicit"] == 1
    assert report["success_sources"]["inferred"] == 1
    assert report["low_confidence_agents"][0]["agent"] == "coder"
    assert "Agency DB Audit" in db_maintenance.format_audit(report)


def test_prune_test_data_dry_run_does_not_delete(tmp_path, monkeypatch):
    monkeypatch.setattr(agency_db, "_DB_PATH", tmp_path / "agency.db")
    monkeypatch.setattr(agency_db, "_local", threading.local())
    agency_db.upsert_project("testproject", "/tmp/test")
    agency_db.upsert_session("testproject", 1, "work", agent="architect")

    result = db_maintenance.prune_test_data(apply=False)
    assert result["projects"] == ["testproject"]
    assert result["rows"]["sessions"] == 1
    assert agency_db.get_projects()[0]["name"] == "testproject"


def test_prune_test_data_apply_deletes_rows(tmp_path, monkeypatch):
    monkeypatch.setattr(agency_db, "_DB_PATH", tmp_path / "agency.db")
    monkeypatch.setattr(agency_db, "_local", threading.local())
    agency_db.upsert_project("testproject", "/tmp/test")
    agency_db.upsert_session("testproject", 1, "work", agent="architect")

    result = db_maintenance.prune_test_data(apply=True)
    assert result["applied"] is True
    assert agency_db.get_projects() == []


def test_prune_never_deletes_a_registered_tenant(tmp_path, monkeypatch):
    # A live tenant named like a test project ("acme-test") must NOT be pruned —
    # registration is the safety boundary. Guards against a cascade-delete of a
    # paying client whose name happens to match the disposable pattern.
    monkeypatch.setattr(agency_db, "_DB_PATH", tmp_path / "agency.db")
    monkeypatch.setattr(agency_db, "_local", threading.local())
    monkeypatch.setattr(db_maintenance, "_registered_project_names",
                        lambda: {"acme-test", "demo-co"})
    agency_db.upsert_project("acme-test", "/clients/acme-test")
    agency_db.upsert_project("demo-co", "/clients/demo-co")
    agency_db.upsert_project("testproject", "/tmp/throwaway")  # unregistered → disposable
    agency_db.upsert_session("acme-test", 1, "work", agent="coder", success=True)

    result = db_maintenance.prune_test_data(apply=True)
    assert result["projects"] == ["testproject"]           # only the unregistered one
    names = {p["name"] for p in agency_db.get_projects()}
    assert names == {"acme-test", "demo-co"}               # both live tenants survive


def test_is_disposable_requires_unregistered():
    reg = {"acme-test"}
    assert db_maintenance._is_disposable("testproject", reg) is True
    assert db_maintenance._is_disposable("acme-test", reg) is False   # registered
    assert db_maintenance._is_disposable("mytestprojectx", reg) is False  # not a whole-name match
    assert db_maintenance._is_disposable("realclient", reg) is False


def test_dedupe_sessions_dry_run_does_not_delete(tmp_path, monkeypatch):
    monkeypatch.setattr(agency_db, "_DB_PATH", tmp_path / "agency.db")
    monkeypatch.setattr(agency_db, "_local", threading.local())
    agency_db.upsert_project("real", "/real")
    agency_db.log_session("real", 1, "work", agent="coder")
    agency_db.log_session("real", 1, "work", agent="coder")

    result = db_maintenance.dedupe_sessions(apply=False)

    assert result["duplicate_rows"] == 1
    assert result["groups"][0]["project"] == "real"
    assert len(agency_db.get_recent_sessions("real", limit=10)) == 2


def test_dedupe_sessions_apply_deletes_duplicate_rows_and_rebuilds_stats(tmp_path, monkeypatch):
    monkeypatch.setattr(agency_db, "_DB_PATH", tmp_path / "agency.db")
    monkeypatch.setattr(agency_db, "_local", threading.local())
    agency_db.upsert_project("real", "/real")
    old_id = agency_db.log_session("real", 1, "work", agent="coder", success=False)
    keep_id = agency_db.log_session("real", 1, "work", agent="coder", success=True)
    task_id = agency_db.add_task("real", "Task")
    agency_db.update_task(task_id, "done", session_id=old_id)

    result = db_maintenance.dedupe_sessions(apply=True)

    assert result["deleted_rows"] == 1
    sessions = agency_db.get_recent_sessions("real", limit=10)
    assert len(sessions) == 1
    assert sessions[0]["id"] == keep_id
    assert agency_db.get_tasks("real", status="done")[0]["session_id"] == keep_id
    agent = agency_db.get_agents("real")[0]
    assert agent["total_sessions"] == 1
    assert agent["successful"] == 1
