#!/usr/bin/env python3
"""Agency DB audit and safe pruning helpers."""
import re
from typing import Iterable


# Name pattern for *disposable* projects. Note this is NEVER sufficient on its
# own to delete — prune_test_data also requires the project to be UNREGISTERED
# (a registered project is a live tenant and is never pruned, whatever its name).
# `testproject` is anchored to a whole name so it can't match e.g. "mytestprojectx".
TEST_PROJECT_RE = re.compile(r"(^|[-_])(test|demo|sample|fixture|tmp)([-_]|$)|^testproject\d*$", re.I)
LOW_CONFIDENCE_MIN_SESSIONS = 5


def _is_disposable(name: str, registered: set[str]) -> bool:
    """A project is disposable only if its name looks like a test project AND it
    is not currently registered. Registration is the tenant-safety boundary: a
    live client is never deleted, even if it's named 'acme-test' or 'demo-co'."""
    return bool(TEST_PROJECT_RE.search(name)) and name not in registered


def _registered_project_names() -> set[str]:
    try:
        from registry import list_projects
        return {p["name"] for p in list_projects()}
    except Exception:
        return set()


def _db_project_names() -> set[str]:
    from agency_db import _get_conn
    conn = _get_conn()
    return {r["name"] for r in conn.execute("SELECT name FROM projects").fetchall()}


def _row_count(table: str, projects: Iterable[str]) -> int:
    names = list(projects)
    if not names:
        return 0
    from agency_db import _get_conn
    conn = _get_conn()
    placeholders = ",".join("?" for _ in names)
    return conn.execute(
        f"SELECT COUNT(*) as c FROM {table} WHERE project IN ({placeholders})",
        names,
    ).fetchone()["c"]


def _agent_confidence_rows() -> list[dict]:
    from agency_db import _get_conn
    conn = _get_conn()
    rows = conn.execute("""
        SELECT project, agent, COUNT(*) as total,
               SUM(CASE WHEN success=1 THEN 1 ELSE 0 END) as successful,
               SUM(CASE WHEN success_source='explicit' THEN 1 ELSE 0 END) as explicit_count,
               SUM(CASE WHEN success_source='inferred' THEN 1 ELSE 0 END) as inferred_count
        FROM sessions
        WHERE agent IS NOT NULL AND agent != ''
        GROUP BY project, agent
        ORDER BY total DESC
    """).fetchall()
    result = []
    for row in rows:
        total = row["total"] or 0
        explicit_count = row["explicit_count"] or 0
        confidence = "high" if total >= 20 and explicit_count / max(total, 1) >= 0.5 else (
            "medium" if total >= LOW_CONFIDENCE_MIN_SESSIONS else "low"
        )
        result.append({
            "project": row["project"],
            "agent": row["agent"],
            "total": total,
            "successful": row["successful"] or 0,
            "explicit_count": explicit_count,
            "inferred_count": row["inferred_count"] or 0,
            "success_rate": round((row["successful"] or 0) / total, 2) if total else 0.0,
            "confidence": confidence,
        })
    return result


def audit_database() -> dict:
    """Return a read-only health report for agency.db."""
    from agency_db import _get_conn
    conn = _get_conn()
    registered = _registered_project_names()
    db_projects = _db_project_names()
    test_projects = sorted(p for p in db_projects if _is_disposable(p, registered))
    orphan_projects = sorted(db_projects - registered) if registered else []
    missing_db_projects = sorted(registered - db_projects) if registered else []
    duplicates = [
        dict(r) for r in conn.execute("""
            SELECT project, session_num, COUNT(*) as count
            FROM sessions
            GROUP BY project, session_num
            HAVING COUNT(*) > 1
            ORDER BY count DESC, project, session_num
        """).fetchall()
    ]
    success_sources = {
        r["success_source"] or "unknown": r["count"]
        for r in conn.execute("""
            SELECT COALESCE(success_source, 'unknown') as success_source, COUNT(*) as count
            FROM sessions GROUP BY COALESCE(success_source, 'unknown')
        """).fetchall()
    }
    agent_rows = _agent_confidence_rows()
    low_confidence_agents = [
        r for r in agent_rows
        if r["confidence"] == "low" or r["inferred_count"] > r["explicit_count"]
    ]
    totals = {
        "projects": conn.execute("SELECT COUNT(*) as c FROM projects").fetchone()["c"],
        "sessions": conn.execute("SELECT COUNT(*) as c FROM sessions").fetchone()["c"],
        "agents": conn.execute("SELECT COUNT(*) as c FROM agents").fetchone()["c"],
    }
    return {
        "totals": totals,
        "registered_projects": sorted(registered),
        "db_projects": sorted(db_projects),
        "test_projects": test_projects,
        "orphan_projects": orphan_projects,
        "missing_db_projects": missing_db_projects,
        "duplicate_sessions": duplicates,
        "success_sources": success_sources,
        "low_confidence_agents": low_confidence_agents,
    }


def duplicate_session_groups(project: str | None = None) -> list[dict]:
    """Return duplicate project/session groups with newest row selected as keeper."""
    from agency_db import _get_conn
    conn = _get_conn()
    where = "WHERE project=?" if project else ""
    params = (project,) if project else ()
    groups = conn.execute(
        f"""
        SELECT project, session_num, COUNT(*) as count
        FROM sessions
        {where}
        GROUP BY project, session_num
        HAVING COUNT(*) > 1
        ORDER BY count DESC, project, session_num
        """,
        params,
    ).fetchall()
    result = []
    for group in groups:
        ids = [
            int(r["id"]) for r in conn.execute(
                "SELECT id FROM sessions WHERE project=? AND session_num=? ORDER BY id DESC",
                (group["project"], group["session_num"]),
            ).fetchall()
        ]
        result.append({
            "project": group["project"],
            "session_num": group["session_num"],
            "count": group["count"],
            "keep_id": ids[0],
            "remove_ids": ids[1:],
        })
    return result


def dedupe_sessions(project: str | None = None, apply: bool = False) -> dict:
    """Dry-run or collapse duplicate project/session rows, preserving newest rows."""
    groups = duplicate_session_groups(project)
    duplicate_rows = sum(len(group["remove_ids"]) for group in groups)
    deleted = 0
    if apply and groups:
        from agency_db import _delete_session_duplicates, _get_conn, rebuild_agent_stats_from_sessions
        conn = _get_conn()
        for group in groups:
            deleted += _delete_session_duplicates(conn, group["keep_id"], group["remove_ids"])
        conn.commit()
        rebuild_agent_stats_from_sessions(project)
    return {
        "project": project,
        "groups": groups,
        "duplicate_rows": duplicate_rows,
        "deleted_rows": deleted,
        "applied": bool(apply),
    }


def _delete_project_rows(projects: list[str], apply: bool = False) -> dict:
    from agency_db import _get_conn
    conn = _get_conn()
    tables = ["council_decisions", "metrics", "messages", "tasks", "knowledge", "sessions", "agents", "projects"]
    counts = {table: _row_count(table, projects) for table in tables if table != "projects"}
    counts["projects"] = len(projects)
    if apply and projects:
        placeholders = ",".join("?" for _ in projects)
        for table in tables:
            key = "name" if table == "projects" else "project"
            conn.execute(f"DELETE FROM {table} WHERE {key} IN ({placeholders})", projects)
        conn.commit()
    return {"projects": projects, "rows": counts, "applied": bool(apply)}


def prune_test_data(apply: bool = False) -> dict:
    """Dry-run or delete rows for disposable test/demo projects.

    Only deletes projects that name-match the test pattern AND are NOT registered
    — so a live tenant is never cascade-deleted regardless of its name.
    """
    registered = _registered_project_names()
    projects = sorted(p for p in _db_project_names() if _is_disposable(p, registered))
    return _delete_project_rows(projects, apply=apply)


def prune_orphans(apply: bool = False) -> dict:
    """Dry-run or delete DB projects no longer present in agency.json."""
    registered = _registered_project_names()
    projects = sorted(_db_project_names() - registered) if registered else []
    return _delete_project_rows(projects, apply=apply)


def format_audit(report: dict) -> str:
    lines = ["", "  Agency DB Audit", "  " + "-" * 48]
    totals = report.get("totals", {})
    lines.append(f"  Projects: {totals.get('projects', 0)}")
    lines.append(f"  Sessions: {totals.get('sessions', 0)}")
    lines.append(f"  Agents:   {totals.get('agents', 0)}")
    lines.append(f"  Success source: {report.get('success_sources', {})}")
    for label, key in (
        ("Test/demo projects", "test_projects"),
        ("Orphan DB projects", "orphan_projects"),
        ("Registry projects missing from DB", "missing_db_projects"),
    ):
        values = report.get(key, [])
        lines.append(f"  {label}: {', '.join(values) if values else 'none'}")
    duplicates = report.get("duplicate_sessions", [])
    lines.append(f"  Duplicate project/session rows: {len(duplicates)}")
    low = report.get("low_confidence_agents", [])
    lines.append(f"  Low-confidence agent stats: {len(low)}")
    for item in low[:10]:
        lines.append(
            f"    - {item['project']}/{item['agent']}: "
            f"{item['total']} sessions, {item['explicit_count']} explicit, "
            f"{item['inferred_count']} inferred"
        )
    lines.append("")
    return "\n".join(lines)


def format_prune_result(result: dict, label: str) -> str:
    mode = "APPLIED" if result.get("applied") else "DRY RUN"
    projects = result.get("projects", [])
    lines = ["", f"  {label} ({mode})", "  " + "-" * 48]
    lines.append(f"  Projects: {', '.join(projects) if projects else 'none'}")
    for table, count in result.get("rows", {}).items():
        if count:
            lines.append(f"  {table}: {count}")
    lines.append("")
    return "\n".join(lines)


def format_dedupe_result(result: dict) -> str:
    mode = "APPLIED" if result.get("applied") else "DRY RUN"
    lines = ["", f"  Dedupe Sessions ({mode})", "  " + "-" * 48]
    if result.get("project"):
        lines.append(f"  Project: {result['project']}")
    lines.append(f"  Duplicate groups: {len(result.get('groups', []))}")
    lines.append(f"  Duplicate rows to remove: {result.get('duplicate_rows', 0)}")
    if result.get("applied"):
        lines.append(f"  Deleted rows: {result.get('deleted_rows', 0)}")
    for group in result.get("groups", [])[:10]:
        lines.append(
            f"    - {group['project']} #{group['session_num']}: "
            f"keep {group['keep_id']}, remove {group['remove_ids']}"
        )
    lines.append("")
    return "\n".join(lines)
