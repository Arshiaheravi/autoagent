"""Tests for red_bridge.py — time-to-fix metrics for Red findings."""
import pytest
import agency_db
import red_bridge


@pytest.fixture(autouse=True)
def _fresh_db(tmp_path, monkeypatch):
    """Each test gets a fresh SQLite database."""
    monkeypatch.setattr(agency_db, "_DB_PATH", tmp_path / "test.db")
    agency_db._local.conn = None
    yield
    agency_db._local.conn = None


def _insert_mapping(finding_id, severity="high", created_at="2026-04-01 10:00:00",
                     verified_at=None, vuln_type="sqli"):
    """Helper: insert a red_to_build_mappings row with known timestamps."""
    red_bridge._ensure_bridge_table()
    conn = red_bridge._get_agency_db()
    conn.execute("""
        INSERT INTO red_to_build_mappings
            (finding_id, target_name, vuln_type, severity, task_id, project, created_at, verified_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (finding_id, "test-target", vuln_type, severity, f"RED-{finding_id}",
          "test-project", created_at, verified_at))
    conn.commit()


# ── compute_red_metrics ──────────────────────────────────────────


def test_red_metrics_time_to_fix():
    """Core test: avg fix time per severity is computed correctly."""
    # Fixed in 2 hours
    _insert_mapping(1, severity="critical",
                    created_at="2026-04-01 10:00:00",
                    verified_at="2026-04-01 12:00:00")
    # Fixed in 4 hours
    _insert_mapping(2, severity="critical",
                    created_at="2026-04-01 10:00:00",
                    verified_at="2026-04-01 14:00:00")
    # Fixed in 24 hours
    _insert_mapping(3, severity="high",
                    created_at="2026-04-01 10:00:00",
                    verified_at="2026-04-02 10:00:00")
    # Unfixed — should appear in oldest_unfixed
    _insert_mapping(4, severity="medium",
                    created_at="2026-04-01 08:00:00")

    metrics = red_bridge.compute_red_metrics()

    # Avg fix time for critical = (2+4)/2 = 3.0 hours
    assert metrics["avg_fix_hours"]["critical"] == pytest.approx(3.0)
    # Avg fix time for high = 24.0 hours
    assert metrics["avg_fix_hours"]["high"] == pytest.approx(24.0)
    # Medium has no fixes — should not appear in avg_fix_hours
    assert "medium" not in metrics["avg_fix_hours"]

    # Oldest unfixed is finding 4
    assert metrics["oldest_unfixed"]["finding_id"] == 4
    assert metrics["oldest_unfixed"]["severity"] == "medium"

    # Total counts
    assert metrics["total"] == 4
    assert metrics["fixed"] == 3
    assert metrics["pending"] == 1


def test_red_metrics_empty_table():
    """No findings at all → sensible defaults."""
    metrics = red_bridge.compute_red_metrics()
    assert metrics["total"] == 0
    assert metrics["fixed"] == 0
    assert metrics["pending"] == 0
    assert metrics["avg_fix_hours"] == {}
    assert metrics["oldest_unfixed"] is None


def test_red_metrics_all_fixed():
    """All findings verified → no oldest_unfixed."""
    _insert_mapping(1, severity="low",
                    created_at="2026-04-01 10:00:00",
                    verified_at="2026-04-01 11:00:00")
    metrics = red_bridge.compute_red_metrics()
    assert metrics["pending"] == 0
    assert metrics["oldest_unfixed"] is None
    assert metrics["avg_fix_hours"]["low"] == pytest.approx(1.0)


def test_red_metrics_all_pending():
    """No fixes yet → avg_fix_hours empty, oldest_unfixed populated."""
    _insert_mapping(1, severity="high", created_at="2026-04-01 10:00:00")
    _insert_mapping(2, severity="high", created_at="2026-04-02 10:00:00")
    metrics = red_bridge.compute_red_metrics()
    assert metrics["avg_fix_hours"] == {}
    assert metrics["oldest_unfixed"]["finding_id"] == 1


def test_recommend_agent():
    """Existing function — sanity check."""
    assert red_bridge.recommend_agent("sqli") == "security-auditor"
    assert red_bridge.recommend_agent("rate_limiting") == "reliability-engineer"
    assert red_bridge.recommend_agent("unknown_type") == "security-auditor"


def test_severity_to_priority():
    """Existing function — sanity check."""
    assert red_bridge.severity_to_priority("critical") == "critical"
    assert red_bridge.severity_to_priority("info") == "low"
    assert red_bridge.severity_to_priority("") == "medium"


# ── End-to-end Red loop ────────────────────────────────────────────


def _create_hunter_db(db_path, findings):
    """Create a mock Hunter DB with a findings table and insert rows."""
    import sqlite3 as _sql
    conn = _sql.connect(str(db_path))
    conn.execute("""
        CREATE TABLE findings (
            id INTEGER PRIMARY KEY,
            title TEXT,
            vuln_type TEXT,
            severity TEXT,
            confidence REAL,
            endpoint TEXT,
            evidence_request TEXT,
            evidence_response TEXT,
            description TEXT,
            target_id INTEGER,
            false_positive INTEGER DEFAULT 0,
            report_status TEXT
        )
    """)
    for f in findings:
        conn.execute("""
            INSERT INTO findings (id, title, vuln_type, severity, confidence,
                                  endpoint, description, false_positive, report_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0, NULL)
        """, (f["id"], f["title"], f["vuln_type"], f["severity"],
              f["confidence"], f["endpoint"], f["description"]))
    conn.commit()
    conn.close()


class _MockCtx:
    """Minimal project context for sync_findings."""
    def __init__(self, memory_dir, name="test-project"):
        self.memory_dir = memory_dir
        self.name = name


def test_red_to_build_full_cycle(tmp_path):
    """End-to-end: Hunter finding → sync → backlog task → mark_verified → closed."""
    # 1. Create mock Hunter DB with a synthetic SQLi finding
    hunter_db = tmp_path / "hunter.db"
    _create_hunter_db(hunter_db, [{
        "id": 42,
        "title": "SQL injection on /api/login",
        "vuln_type": "sqli",
        "severity": "critical",
        "confidence": 0.95,
        "endpoint": "/api/login",
        "description": "Parameter 'username' vulnerable to blind SQLi",
    }])

    # 2. Set up mock context with a memory dir containing an empty backlog
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir()
    backlog_file = memory_dir / "backlog.md"
    backlog_file.write_text("# Backlog\n", encoding="utf-8")
    ctx = _MockCtx(memory_dir)

    # 3. Run sync_findings — should create one task from the finding
    new_tasks = red_bridge.sync_findings(ctx, hunter_db_path=hunter_db)

    assert len(new_tasks) == 1
    task = new_tasks[0]
    assert task["task_id"] == "RED-42"
    assert task["finding_id"] == 42
    assert task["severity"] == "critical"
    assert task["agent"] == "security-auditor"

    # 4. Verify the backlog file was updated with the task
    backlog_content = backlog_file.read_text(encoding="utf-8")
    assert "RED-42" in backlog_content
    assert "sqli" in backlog_content
    assert "SQL injection on /api/login" in backlog_content

    # 5. Verify the bridge table recorded the mapping
    assert red_bridge._already_synced(42)

    # 6. Verify re-running sync_findings doesn't create duplicates
    new_tasks_2 = red_bridge.sync_findings(ctx, hunter_db_path=hunter_db)
    assert len(new_tasks_2) == 0

    # 7. Verify finding shows up as unverified
    unverified = red_bridge.get_unverified_findings()
    assert any(f["finding_id"] == 42 for f in unverified)

    # 8. Mark the finding as verified (simulating Build agent fixing it)
    red_bridge.mark_verified(42, "abc123def", hunter_db_path=hunter_db)

    # 9. Verify the bridge table is updated
    conn = red_bridge._get_agency_db()
    row = conn.execute(
        "SELECT verified_at, fix_commit_hash FROM red_to_build_mappings WHERE finding_id = ?",
        (42,)
    ).fetchone()
    assert row is not None
    assert row["verified_at"] is not None
    assert row["fix_commit_hash"] == "abc123def"

    # 10. Verify finding no longer appears as unverified
    unverified_after = red_bridge.get_unverified_findings()
    assert not any(f["finding_id"] == 42 for f in unverified_after)

    # 11. Verify Hunter DB was updated to 'verified' status
    import sqlite3 as _sql
    hconn = _sql.connect(str(hunter_db))
    hconn.row_factory = _sql.Row
    hrow = hconn.execute("SELECT report_status FROM findings WHERE id = 42").fetchone()
    hconn.close()
    assert hrow["report_status"] == "verified"

    # 12. Verify bridge stats reflect the closed loop
    stats = red_bridge.get_bridge_stats()
    assert stats["total_findings"] == 1
    assert stats["verified"] == 1
    assert stats["pending"] == 0
