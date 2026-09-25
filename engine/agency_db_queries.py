"""Agency Database — query and reporting functions.

Complex queries, aggregation, ranking, pruning, migration, and CLI.
Split from agency_db.py to keep both files under 300 lines.
"""
import json
import logging
from typing import Optional

from agency_db import _get_conn, _DB_PATH

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════
# PROJECT QUERIES
# ══════════════════════════════════════════════════════════════════

def get_projects() -> list[dict]:
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM projects ORDER BY name").fetchall()
    return [dict(r) for r in rows]


# ══════════════════════════════════════════════════════════════════
# SESSION QUERIES
# ══════════════════════════════════════════════════════════════════

def get_recent_sessions(project: Optional[str] = None, limit: int = 20) -> list[dict]:
    conn = _get_conn()
    if project:
        rows = conn.execute(
            "SELECT * FROM sessions WHERE project=? ORDER BY id DESC LIMIT ?",
            (project, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM sessions ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_session_stats(project: Optional[str] = None) -> dict:
    conn = _get_conn()
    where = "WHERE project=?" if project else ""
    params = (project,) if project else ()
    row = conn.execute(
        f"SELECT COUNT(*) as total, SUM(success) as successes, "
        f"AVG(quality_score) as avg_quality, SUM(cost_usd) as total_cost "
        f"FROM sessions {where}", params
    ).fetchone()
    return dict(row) if row else {}


# ══════════════════════════════════════════════════════════════════
# AGENT QUERIES
# ══════════════════════════════════════════════════════════════════

def get_agents(project: str) -> list[dict]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM agents WHERE project=? ORDER BY total_sessions DESC", (project,)
    ).fetchall()
    return [dict(r) for r in rows]


def get_top_agents(limit: int = 10) -> list[dict]:
    conn = _get_conn()
    rows = conn.execute(
        """SELECT project, name, total_sessions, successful, failed, avg_quality,
           CASE WHEN total_sessions > 0 THEN ROUND(1.0 * successful / total_sessions, 2) ELSE 0 END as success_rate
           FROM agents WHERE total_sessions > 0
           ORDER BY success_rate DESC, total_sessions DESC LIMIT ?""",
        (limit,)
    ).fetchall()
    return [dict(r) for r in rows]


# ══════════════════════════════════════════════════════════════════
# KNOWLEDGE QUERIES
# ══════════════════════════════════════════════════════════════════

def get_knowledge(project: str, limit: int = 50, min_score: float = 0.0) -> list[dict]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM knowledge WHERE project=? AND score>=? ORDER BY score DESC, use_count DESC LIMIT ?",
        (project, min_score, limit)
    ).fetchall()
    return [dict(r) for r in rows]


def prune_knowledge(project: str, keep_top: int = 50) -> int:
    """Intelligently prune low-value knowledge rules."""
    conn = _get_conn()
    conn.execute("""
        UPDATE knowledge SET score =
            (CASE WHEN is_universal THEN 2.0 ELSE 1.0 END) *
            (0.5 + 0.5 * MIN(use_count, 10) / 10.0) *
            (CASE WHEN last_used_at IS NOT NULL
                  THEN MAX(0.1, 1.0 - (julianday('now') - julianday(last_used_at)) / 30.0)
                  ELSE 0.3 END)
        WHERE project=?
    """, (project,))
    deleted = conn.execute("""
        DELETE FROM knowledge WHERE project=? AND id NOT IN (
            SELECT id FROM knowledge WHERE project=? ORDER BY score DESC LIMIT ?
        )
    """, (project, project, keep_top)).rowcount
    conn.commit()
    return deleted


# ══════════════════════════════════════════════════════════════════
# TASK QUERIES
# ══════════════════════════════════════════════════════════════════

def get_tasks(project: str, status: str = "pending") -> list[dict]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM tasks WHERE project=? AND status=? ORDER BY priority DESC, id",
        (project, status)
    ).fetchall()
    return [dict(r) for r in rows]


# ══════════════════════════════════════════════════════════════════
# MESSAGE QUERIES
# ══════════════════════════════════════════════════════════════════

def get_messages(limit: int = 50, project: Optional[str] = None) -> list[dict]:
    conn = _get_conn()
    if project:
        rows = conn.execute(
            "SELECT * FROM messages WHERE project=? ORDER BY id DESC LIMIT ?", (project, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM messages ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


# ══════════════════════════════════════════════════════════════════
# METRIC QUERIES
# ══════════════════════════════════════════════════════════════════

def get_metrics(project: str, metric_name: str, limit: int = 30) -> list[dict]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM metrics WHERE project=? AND metric_name=? ORDER BY recorded_at DESC LIMIT ?",
        (project, metric_name, limit)
    ).fetchall()
    return [dict(r) for r in rows]


# ══════════════════════════════════════════════════════════════════
# COUNCIL DECISION QUERIES
# ══════════════════════════════════════════════════════════════════

def get_council_decisions(project: str, limit: int = 20) -> list[dict]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM council_decisions WHERE project=? ORDER BY id DESC LIMIT ?",
        (project, limit)
    ).fetchall()
    return [dict(r) for r in rows]


def get_council_stats(project: str) -> dict:
    """Correlation between confidence levels and session outcomes.

    Returns dict keyed by confidence level (HIGH/MEDIUM/LOW), each with
    total, successful, and success_rate.
    """
    conn = _get_conn()
    rows = conn.execute(
        """SELECT confidence, COUNT(*) as total,
           SUM(CASE WHEN session_outcome=1 THEN 1 ELSE 0 END) as successful
           FROM council_decisions
           WHERE project=? AND session_outcome IS NOT NULL
           GROUP BY confidence""",
        (project,)
    ).fetchall()
    if not rows:
        return {}
    return {
        r["confidence"]: {
            "total": r["total"],
            "successful": r["successful"],
            "success_rate": round(r["successful"] / r["total"], 2) if r["total"] else 0.0,
        }
        for r in rows
    }


# ══════════════════════════════════════════════════════════════════
# AGENCY-WIDE QUERIES
# ══════════════════════════════════════════════════════════════════

def agency_summary() -> dict:
    """Get a high-level summary of the entire agency."""
    conn = _get_conn()
    projects = conn.execute("SELECT COUNT(*) as c FROM projects").fetchone()["c"]
    sessions = conn.execute("SELECT COUNT(*) as c FROM sessions").fetchone()["c"]
    agents = conn.execute("SELECT COUNT(*) as c FROM agents").fetchone()["c"]
    knowledge = conn.execute("SELECT COUNT(*) as c FROM knowledge").fetchone()["c"]
    tasks_pending = conn.execute("SELECT COUNT(*) as c FROM tasks WHERE status='pending'").fetchone()["c"]
    tasks_done = conn.execute("SELECT COUNT(*) as c FROM tasks WHERE status='done'").fetchone()["c"]
    messages = conn.execute("SELECT COUNT(*) as c FROM messages").fetchone()["c"]

    success_rate = 0
    row = conn.execute("SELECT AVG(success) as sr FROM sessions").fetchone()
    if row and row["sr"] is not None:
        success_rate = round(row["sr"] * 100)

    return {
        "projects": projects,
        "total_sessions": sessions,
        "agents": agents,
        "knowledge_rules": knowledge,
        "tasks_pending": tasks_pending,
        "tasks_done": tasks_done,
        "messages": messages,
        "success_rate_pct": success_rate,
    }


# ══════════════════════════════════════════════════════════════════
# MIGRATION — Import existing file-based data
# ══════════════════════════════════════════════════════════════════

def migrate_from_files():
    """Import existing sessions.json and knowledge.md into the database."""
    from registry import list_projects, get
    from agency_db import upsert_project, add_knowledge, upsert_agent

    for p in list_projects():
        try:
            ctx = get(p["name"])
            upsert_project(p["name"], str(ctx.project_root))

            # Import sessions.json idempotently
            if ctx.sessions_file.exists():
                try:
                    from session_db_sync import sync_sessions_file_to_agency_db
                    count = sync_sessions_file_to_agency_db(ctx)
                    logger.info("Migrated %d sessions for %s", count, p["name"])
                except Exception as e:
                    logger.warning("Failed to migrate sessions for %s: %s", p["name"], e)

            # Import knowledge.md
            kf = ctx.memory_dir / "knowledge.md"
            if kf.exists():
                try:
                    count = 0
                    for line in kf.read_text(encoding="utf-8").splitlines():
                        stripped = line.strip()
                        if stripped.startswith("RULE:") or stripped.startswith("SKILL:"):
                            add_knowledge(p["name"], stripped)
                            count += 1
                    logger.info("Migrated %d knowledge rules for %s", count, p["name"])
                except Exception as e:
                    logger.warning("Failed to migrate knowledge for %s: %s", p["name"], e)

            # Import agents
            if ctx.agents_dir.exists():
                for f in ctx.agents_dir.glob("*.md"):
                    if f.name.startswith("."):
                        continue
                    upsert_agent(p["name"], f.stem)
                logger.info("Migrated agents for %s", p["name"])

        except Exception as e:
            logger.warning("Migration failed for %s: %s", p["name"], e)

    logger.info("Migration complete. DB: %s", _DB_PATH)


# ══════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)

    args = sys.argv[1:]
    if not args or args[0] == "help":
        print("""
  Agency Database

  Usage:
    python3 engine/agency_db_queries.py migrate    Import file-based data into DB
    python3 engine/agency_db_queries.py summary    Show agency summary
    python3 engine/agency_db_queries.py sessions   Show recent sessions
    python3 engine/agency_db_queries.py agents     Show top agents
    python3 engine/agency_db_queries.py prune      Prune low-value knowledge
""")
        sys.exit(0)

    cmd = args[0]

    if cmd == "migrate":
        migrate_from_files()
        s = agency_summary()
        print(json.dumps(s, indent=2))

    elif cmd == "summary":
        s = agency_summary()
        print(json.dumps(s, indent=2))

    elif cmd == "sessions":
        project = args[1] if len(args) > 1 else None
        for s in get_recent_sessions(project, limit=10):
            icon = "OK" if s["success"] else "FAIL"
            print(f"  #{s['session_num']} [{icon}] {s['project']} ({s['session_type']}) {s['agent'] or 'generic'}")

    elif cmd == "agents":
        for a in get_top_agents():
            print(f"  {a['project']}/{a['name']}: {a['total_sessions']} sessions, {a['success_rate']*100:.0f}% success")

    elif cmd == "prune":
        for p in get_projects():
            deleted = prune_knowledge(p["name"])
            print(f"  {p['name']}: pruned {deleted} low-value rules")
