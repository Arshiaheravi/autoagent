"""Tests for scripts/backfill_council_memory.py — council memory backfill.

Uses a tmp_path SQLite fixture as the source DB. Monkeypatches
engine.council.memory.persist and embed to avoid real Postgres / OpenAI calls.
Cleanup follows the UUID-tagged prefix pattern from test_council_memory.py.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
ENGINE = Path(__file__).resolve().parent.parent / "engine"
sys.path.insert(0, str(ENGINE))
sys.path.insert(0, str(SCRIPTS))

TEST_TAG = f"backfill_test_{uuid.uuid4().hex[:12]}"


def _create_source_db(db_path: Path, rows: list[dict]) -> Path:
    """Create a minimal SQLite DB with council_decisions table and rows."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            name TEXT PRIMARY KEY,
            path TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            config TEXT DEFAULT '{}'
        )
    """)
    conn.execute(
        "INSERT OR IGNORE INTO projects (name, path) VALUES (?, ?)",
        ("testproj", "/tmp/test"),
    )
    conn.execute("""
        CREATE TABLE IF NOT EXISTS council_decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project TEXT NOT NULL REFERENCES projects(name),
            session_num INTEGER NOT NULL,
            question TEXT NOT NULL,
            winner TEXT DEFAULT '',
            confidence TEXT DEFAULT 'MEDIUM',
            synthesis TEXT DEFAULT '',
            session_outcome INTEGER,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    for r in rows:
        conn.execute(
            "INSERT INTO council_decisions (project, session_num, question, winner, confidence, synthesis) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                r.get("project", "testproj"),
                r.get("session_num", 1),
                r["question"],
                r.get("winner", "alice"),
                r.get("confidence", "HIGH"),
                r.get("synthesis", "do it"),
            ),
        )
    conn.commit()
    conn.close()
    return db_path


def _sample_rows(n: int = 3) -> list[dict]:
    return [
        {
            "question": f"{TEST_TAG} question_{i}",
            "winner": f"model_{i}",
            "confidence": "HIGH",
            "synthesis": f"synthesis for q{i}",
            "project": "testproj",
            "session_num": i + 1,
        }
        for i in range(n)
    ]


@pytest.fixture
def source_db(tmp_path):
    return _create_source_db(tmp_path / "agency.db", _sample_rows(3))


@pytest.fixture
def source_db_5(tmp_path):
    return _create_source_db(tmp_path / "agency.db", _sample_rows(5))


class TestBackfillCouncilMemory:

    def test_dry_run_counts_without_writing(self, source_db, monkeypatch):
        """Dry-run should count rows but never call persist."""
        monkeypatch.setenv("COUNCIL_MEMORY_ENABLED", "true")
        persist_calls = []

        def fake_persist(**kwargs):
            persist_calls.append(kwargs)
            return len(persist_calls)

        import backfill_council_memory as bcm
        monkeypatch.setattr(bcm, "_persist", fake_persist)
        monkeypatch.setattr(bcm, "_check_existing_hash", lambda h: False)

        stats = bcm.run_backfill(str(source_db), dry_run=True)

        assert persist_calls == [], "dry-run must NOT call persist"
        assert stats["would_insert"] == 3
        assert stats["skipped"] == 0

    def test_skips_existing_question_hash(self, source_db, monkeypatch):
        """Rows whose question_hash already exists in council_episodic are skipped."""
        monkeypatch.setenv("COUNCIL_MEMORY_ENABLED", "true")
        persist_calls = []

        def fake_persist(**kwargs):
            persist_calls.append(kwargs)
            return len(persist_calls)

        existing_hash = hashlib.sha256(
            f"{TEST_TAG} question_0".encode()
        ).hexdigest()

        import backfill_council_memory as bcm
        monkeypatch.setattr(bcm, "_persist", fake_persist)
        monkeypatch.setattr(
            bcm,
            "_check_existing_hash",
            lambda h: h == existing_hash,
        )

        stats = bcm.run_backfill(str(source_db), dry_run=False)

        assert stats["inserted"] == 2
        assert stats["skipped"] == 1
        assert len(persist_calls) == 2

    def test_inserts_new_rows(self, source_db, monkeypatch):
        """With empty council_episodic, all SQLite rows should be persisted."""
        monkeypatch.setenv("COUNCIL_MEMORY_ENABLED", "true")
        persist_calls = []

        def fake_persist(**kwargs):
            persist_calls.append(kwargs)
            return len(persist_calls)

        import backfill_council_memory as bcm
        monkeypatch.setattr(bcm, "_persist", fake_persist)
        monkeypatch.setattr(bcm, "_check_existing_hash", lambda h: False)

        stats = bcm.run_backfill(str(source_db), dry_run=False)

        assert stats["inserted"] == 3
        assert stats["skipped"] == 0
        assert stats["errors"] == 0
        assert len(persist_calls) == 3

        for call in persist_calls:
            assert "question" in call
            assert "result" in call
            assert call["result"]["mode"] == "executive"

    def test_requires_enabled_env_var(self, source_db, monkeypatch):
        """Script must fail fast when COUNCIL_MEMORY_ENABLED is not true."""
        monkeypatch.setenv("COUNCIL_MEMORY_ENABLED", "false")

        import backfill_council_memory as bcm

        with pytest.raises(RuntimeError, match="COUNCIL_MEMORY_ENABLED"):
            bcm.run_backfill(str(source_db), dry_run=False)

    def test_handles_persist_failure_gracefully(self, source_db, monkeypatch):
        """If persist raises on one row, script logs error and continues."""
        monkeypatch.setenv("COUNCIL_MEMORY_ENABLED", "true")
        call_count = 0

        def flaky_persist(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise Exception("simulated DB error")
            return call_count

        import backfill_council_memory as bcm
        monkeypatch.setattr(bcm, "_persist", flaky_persist)
        monkeypatch.setattr(bcm, "_check_existing_hash", lambda h: False)

        stats = bcm.run_backfill(str(source_db), dry_run=False)

        assert stats["inserted"] == 2
        assert stats["errors"] == 1
        assert stats["skipped"] == 0
