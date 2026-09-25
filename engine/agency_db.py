#!/usr/bin/env python3
"""Agency Database — persistent state for the entire agency.

Replaces fragile JSON/markdown files with a real SQLite database.
Stores sessions, agents, knowledge, tasks, communications, and metrics.

Location: ~/.autoagent/agency.db

Write operations (CRUD core) live here.
Read/query operations live in agency_db_queries.py.
"""
import json
import logging
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Control DB path derives from the Tenant SSoT — same root as registry.AGENCY_HOME,
# so relocating a tenant (AUTOAGENT_HOME) moves its projects AND its DB together.
# (Previously hardcoded ~/.autoagent, which silently ignored AUTOAGENT_HOME.)
from tenant import current_tenant  # noqa: E402

_DB_PATH = current_tenant().db_path
_local = threading.local()


def _tenant_id() -> str:
    """Owning tenant for rows written by this process.

    Ambient (per-tenant container = one tenant per process). Every INSERT stamps
    it so the eventual shared-Postgres + RLS cutover (Fork B) is a connection-layer
    change, not a schema/code change. INVARIANT: a SQLite file is never shared
    across tenants — the file (now) or RLS (later) is the read boundary, so reads
    don't filter on tenant_id. Do not co-mingle tenants in one SQLite DB.
    """
    return current_tenant().tenant_id


def _get_conn() -> sqlite3.Connection:
    """Get thread-local database connection."""
    if not hasattr(_local, "conn") or _local.conn is None:
        _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _local.conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA foreign_keys=ON")
        _init_schema(_local.conn)
    return _local.conn


def _init_schema(conn: sqlite3.Connection):
    """Create tables if they don't exist."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS projects (
            name TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL DEFAULT 'default',
            path TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            config TEXT DEFAULT '{}'
        );
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id TEXT NOT NULL DEFAULT 'default',
            project TEXT NOT NULL REFERENCES projects(name),
            session_num INTEGER NOT NULL,
            session_type TEXT NOT NULL,
            agent TEXT,
            success INTEGER NOT NULL DEFAULT 0,
            started_at TEXT DEFAULT (datetime('now')),
            finished_at TEXT,
            tests_before INTEGER DEFAULT 0,
            tests_after INTEGER DEFAULT 0,
            files_changed TEXT DEFAULT '[]',
            summary TEXT DEFAULT '',
            cost_usd REAL DEFAULT 0.0,
            quality_score INTEGER DEFAULT 0,
            success_source TEXT DEFAULT 'explicit'
        );
        CREATE TABLE IF NOT EXISTS agents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id TEXT NOT NULL DEFAULT 'default',
            project TEXT NOT NULL REFERENCES projects(name),
            name TEXT NOT NULL,
            display_name TEXT,
            total_sessions INTEGER DEFAULT 0,
            successful INTEGER DEFAULT 0,
            failed INTEGER DEFAULT 0,
            avg_quality REAL DEFAULT 0.0,
            last_session_at TEXT,
            keywords TEXT DEFAULT '[]',
            owned_files TEXT DEFAULT '[]',
            UNIQUE(project, name)
        );
        CREATE TABLE IF NOT EXISTS knowledge (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id TEXT NOT NULL DEFAULT 'default',
            project TEXT NOT NULL REFERENCES projects(name),
            rule TEXT NOT NULL,
            source TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now')),
            last_used_at TEXT,
            use_count INTEGER DEFAULT 0,
            score REAL DEFAULT 1.0,
            is_universal INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id TEXT NOT NULL DEFAULT 'default',
            project TEXT NOT NULL REFERENCES projects(name),
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            agent_hint TEXT,
            status TEXT DEFAULT 'pending',
            priority INTEGER DEFAULT 0,
            depends_on TEXT DEFAULT '[]',
            created_at TEXT DEFAULT (datetime('now')),
            completed_at TEXT,
            session_id INTEGER REFERENCES sessions(id)
        );
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id TEXT NOT NULL DEFAULT 'default',
            direction TEXT NOT NULL,
            message_type TEXT DEFAULT 'notify',
            project TEXT,
            agent TEXT,
            content TEXT NOT NULL,
            reply_to INTEGER REFERENCES messages(id),
            telegram_msg_id INTEGER,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id TEXT NOT NULL DEFAULT 'default',
            project TEXT NOT NULL REFERENCES projects(name),
            metric_name TEXT NOT NULL,
            value REAL NOT NULL,
            recorded_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS council_decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id TEXT NOT NULL DEFAULT 'default',
            project TEXT NOT NULL REFERENCES projects(name),
            session_num INTEGER NOT NULL,
            question TEXT NOT NULL,
            winner TEXT DEFAULT '',
            confidence TEXT DEFAULT 'MEDIUM',
            synthesis TEXT DEFAULT '',
            session_outcome INTEGER,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_sessions_project ON sessions(project, started_at);
        CREATE INDEX IF NOT EXISTS idx_sessions_agent ON sessions(agent);
        CREATE INDEX IF NOT EXISTS idx_knowledge_project ON knowledge(project, score);
        CREATE INDEX IF NOT EXISTS idx_tasks_project_status ON tasks(project, status);
        CREATE INDEX IF NOT EXISTS idx_metrics_project ON metrics(project, metric_name, recorded_at);
    """)
    _ensure_column(conn, "sessions", "success_source", "TEXT DEFAULT 'explicit'")
    # Backfill tenant_id on DBs created before multi-tenant scoping (Fork B).
    for _t in ("projects", "sessions", "agents", "knowledge", "tasks",
               "messages", "metrics", "council_decisions"):
        _ensure_column(conn, _t, "tenant_id", "TEXT NOT NULL DEFAULT 'default'")
    conn.commit()


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str):
    """Add a column to an existing SQLite table when a newer schema needs it."""
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


# ══════════════════════════════════════════════════════════════════
# PROJECTS
# ══════════════════════════════════════════════════════════════════

def upsert_project(name: str, path: str, config: Optional[dict] = None):
    conn = _get_conn()
    conn.execute(
        "INSERT INTO projects (name, tenant_id, path, config) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(name) DO UPDATE SET path=excluded.path, config=excluded.config",
        (name, _tenant_id(), path, json.dumps(config or {}))
    )
    conn.commit()


# ══════════════════════════════════════════════════════════════════
# SESSIONS
# ══════════════════════════════════════════════════════════════════

def log_session(project: str, session_num: int, session_type: str,
                agent: Optional[str] = None, success: bool = False,
                tests_before: int = 0, tests_after: int = 0,
                files_changed: Optional[list] = None, summary: str = "",
                cost_usd: float = 0.0, quality_score: int = 0,
                success_source: str = "explicit") -> int:
    conn = _get_conn()
    cur = conn.execute(
        """INSERT INTO sessions (tenant_id, project, session_num, session_type, agent, success,
           tests_before, tests_after, files_changed, summary, cost_usd, quality_score,
           success_source, finished_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
        (_tenant_id(), project, session_num, session_type, agent, int(success),
         tests_before, tests_after, json.dumps(files_changed or []),
         summary, cost_usd, quality_score, success_source)
    )
    conn.commit()
    return cur.lastrowid


def upsert_session(project: str, session_num: int, session_type: str,
                   agent: Optional[str] = None, success: bool = False,
                   tests_before: int = 0, tests_after: int = 0,
                   files_changed: Optional[list] = None, summary: str = "",
                   cost_usd: float = 0.0, quality_score: int = 0,
                   success_source: str = "explicit") -> int:
    """Insert or update one project/session_num row.

    This is the idempotent path used when syncing sessions.json into SQLite.
    log_session() remains append-only for callers that intentionally record
    independent events.
    """
    conn = _get_conn()
    rows = conn.execute(
        "SELECT id FROM sessions WHERE project=? AND session_num=? ORDER BY id DESC",
        (project, session_num),
    ).fetchall()
    files_json = json.dumps(files_changed or [])
    if rows:
        keep_id = int(rows[0]["id"])
        duplicate_ids = [int(row["id"]) for row in rows[1:]]
        conn.execute(
            """UPDATE sessions SET
               session_type=?, agent=?, success=?, tests_before=?, tests_after=?,
               files_changed=?, summary=?, cost_usd=?, quality_score=?,
               success_source=?,
               finished_at=datetime('now')
               WHERE id=?""",
            (session_type, agent, int(success), tests_before, tests_after,
             files_json, summary, cost_usd, quality_score, success_source, keep_id),
        )
        _delete_session_duplicates(conn, keep_id, duplicate_ids)
        conn.commit()
        return keep_id
    return log_session(
        project, session_num, session_type, agent=agent, success=success,
        tests_before=tests_before, tests_after=tests_after,
        files_changed=files_changed, summary=summary,
        cost_usd=cost_usd, quality_score=quality_score,
        success_source=success_source,
    )


def _delete_session_duplicates(conn: sqlite3.Connection, keep_id: int,
                               duplicate_ids: list[int]) -> int:
    """Delete duplicate session rows after retargeting task references."""
    if not duplicate_ids:
        return 0
    placeholders = ",".join("?" for _ in duplicate_ids)
    conn.execute(
        f"UPDATE tasks SET session_id=? WHERE session_id IN ({placeholders})",
        [keep_id, *duplicate_ids],
    )
    return conn.execute(
        f"DELETE FROM sessions WHERE id IN ({placeholders})",
        duplicate_ids,
    ).rowcount


def rebuild_agent_stats_from_sessions(project: Optional[str] = None) -> int:
    """Recalculate agent summary rows from the sessions table."""
    conn = _get_conn()
    where = "WHERE project=? AND agent IS NOT NULL AND agent != ''" if project else "WHERE agent IS NOT NULL AND agent != ''"
    params = (project,) if project else ()
    rows = conn.execute(
        f"""SELECT project, agent, COUNT(*) as total,
                   SUM(CASE WHEN success=1 THEN 1 ELSE 0 END) as successful,
                   SUM(CASE WHEN success=1 THEN 0 ELSE 1 END) as failed,
                   ROUND(AVG(quality_score), 1) as avg_quality,
                   MAX(COALESCE(finished_at, started_at)) as last_session_at
            FROM sessions {where}
            GROUP BY project, agent""",
        params,
    ).fetchall()
    for row in rows:
        upsert_agent(row["project"], row["agent"])
        conn.execute(
            """UPDATE agents SET total_sessions=?, successful=?, failed=?,
               avg_quality=?, last_session_at=?
               WHERE project=? AND name=?""",
            (
                row["total"], row["successful"] or 0, row["failed"] or 0,
                row["avg_quality"] or 0.0, row["last_session_at"],
                row["project"], row["agent"],
            ),
        )
    conn.commit()
    return len(rows)


# ══════════════════════════════════════════════════════════════════
# AGENTS
# ══════════════════════════════════════════════════════════════════

def upsert_agent(project: str, name: str, display_name: str = "",
                 keywords: Optional[list] = None, owned_files: Optional[list] = None):
    conn = _get_conn()
    conn.execute(
        """INSERT INTO agents (tenant_id, project, name, display_name, keywords, owned_files)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(project, name) DO UPDATE SET
           display_name=excluded.display_name, keywords=excluded.keywords,
           owned_files=excluded.owned_files""",
        (_tenant_id(), project, name, display_name or name, json.dumps(keywords or []),
         json.dumps(owned_files or []))
    )
    conn.commit()


def update_agent_stats(project: str, name: str, success: bool, quality: int = 0):
    conn = _get_conn()
    # Update avg_quality as running average: new_avg = (old_avg * old_count + new_value) / new_count
    conn.execute(
        """UPDATE agents SET
           avg_quality = CASE WHEN total_sessions > 0
               THEN ROUND((avg_quality * total_sessions + ?) / (total_sessions + 1), 1)
               ELSE ? END,
           total_sessions = total_sessions + 1,
           successful = successful + ?,
           failed = failed + ?,
           last_session_at = datetime('now')
           WHERE project=? AND name=?""",
        (quality, float(quality), int(success), int(not success), project, name)
    )
    conn.commit()


# ══════════════════════════════════════════════════════════════════
# KNOWLEDGE
# ══════════════════════════════════════════════════════════════════

def add_knowledge(project: str, rule: str, source: str = "",
                  is_universal: bool = False) -> int:
    conn = _get_conn()
    existing = conn.execute(
        "SELECT id FROM knowledge WHERE project=? AND rule=?", (project, rule)
    ).fetchone()
    if existing:
        conn.execute("UPDATE knowledge SET use_count=use_count+1, last_used_at=datetime('now') WHERE id=?",
                     (existing["id"],))
        conn.commit()
        return existing["id"]
    cur = conn.execute(
        "INSERT INTO knowledge (tenant_id, project, rule, source, is_universal) VALUES (?, ?, ?, ?, ?)",
        (_tenant_id(), project, rule, source, int(is_universal))
    )
    conn.commit()
    return cur.lastrowid


# ══════════════════════════════════════════════════════════════════
# TASKS
# ══════════════════════════════════════════════════════════════════

def add_task(project: str, title: str, description: str = "",
             agent_hint: str = "", priority: int = 0) -> int:
    conn = _get_conn()
    cur = conn.execute(
        "INSERT INTO tasks (tenant_id, project, title, description, agent_hint, priority) VALUES (?, ?, ?, ?, ?, ?)",
        (_tenant_id(), project, title, description, agent_hint, priority)
    )
    conn.commit()
    return cur.lastrowid


def update_task(task_id: int, status: str, session_id: Optional[int] = None):
    conn = _get_conn()
    if status == "done":
        conn.execute("UPDATE tasks SET status=?, completed_at=datetime('now'), session_id=? WHERE id=?",
                     (status, session_id, task_id))
    else:
        conn.execute("UPDATE tasks SET status=? WHERE id=?", (status, task_id))
    conn.commit()


# ══════════════════════════════════════════════════════════════════
# MESSAGES
# ══════════════════════════════════════════════════════════════════

def log_message(direction: str, content: str, message_type: str = "notify",
                project: str = "", agent: str = "", reply_to: Optional[int] = None) -> int:
    conn = _get_conn()
    cur = conn.execute(
        """INSERT INTO messages (tenant_id, direction, content, message_type, project, agent, reply_to)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (_tenant_id(), direction, content, message_type, project, agent, reply_to)
    )
    conn.commit()
    return cur.lastrowid


# ══════════════════════════════════════════════════════════════════
# METRICS
# ══════════════════════════════════════════════════════════════════

def record_metric(project: str, metric_name: str, value: float):
    conn = _get_conn()
    conn.execute(
        "INSERT INTO metrics (tenant_id, project, metric_name, value) VALUES (?, ?, ?, ?)",
        (_tenant_id(), project, metric_name, value)
    )
    conn.commit()


# ══════════════════════════════════════════════════════════════════
# COUNCIL DECISIONS
# ══════════════════════════════════════════════════════════════════

def log_council_decision(project: str, session_num: int, question: str,
                         winner: str = "", confidence: str = "MEDIUM",
                         synthesis: str = "") -> int:
    conn = _get_conn()
    cur = conn.execute(
        """INSERT INTO council_decisions (tenant_id, project, session_num, question, winner, confidence, synthesis)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (_tenant_id(), project, session_num, question, winner, confidence, synthesis)
    )
    conn.commit()
    return cur.lastrowid


def update_council_outcome(decision_id: int, session_success: bool):
    conn = _get_conn()
    conn.execute("UPDATE council_decisions SET session_outcome=? WHERE id=?",
                 (int(session_success), decision_id))
    conn.commit()


# ══════════════════════════════════════════════════════════════════
# BACKWARD-COMPATIBLE RE-EXPORTS from agency_db_queries
# ══════════════════════════════════════════════════════════════════

from agency_db_queries import (  # noqa: E402
    get_projects, get_recent_sessions, get_session_stats,
    get_agents, get_top_agents,
    get_knowledge, prune_knowledge,
    get_tasks, get_messages, get_metrics,
    get_council_decisions, get_council_stats,
    agency_summary, migrate_from_files,
)
