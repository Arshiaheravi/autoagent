#!/usr/bin/env python3
"""Red-to-Build Bridge — auto-create Build tasks from Hunter findings.

The core integration between AutoAgent (Build) and autonomous-hunter (Red).
When Hunter discovers a vulnerability, this bridge:
1. Creates a prioritized task in the Build backlog
2. Assigns the right agent based on vulnerability type
3. Includes reproduction evidence so the Build agent can fix it
4. Tracks fix status (finding_id → task_id → commit_hash)

Usage:
    from red_bridge import sync_findings, mark_verified
    new_tasks = sync_findings(ctx)     # Poll DB, create tasks
    mark_verified(finding_id, "abc123") # After Build fixes
"""
import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Hunter DB path — default location, overridable
HUNTER_DB = Path.home() / ".autoagent" / "hunter.db"

# Vuln type → recommended Build agent
_AGENT_MAP = {
    "sqli": "security-auditor",
    "sql_injection": "security-auditor",
    "xss": "frontend",
    "csrf": "security-auditor",
    "ssrf": "security-auditor",
    "idor": "security-auditor",
    "auth_bypass": "security-auditor",
    "cors": "security-auditor",
    "rce": "security-auditor",
    "lfi": "security-auditor",
    "open_redirect": "frontend",
    "info_disclosure": "security-auditor",
    "rate_limiting": "reliability-engineer",
    "default": "security-auditor",
}

# Severity → task priority
_PRIORITY_MAP = {
    "critical": "critical",
    "high": "high",
    "medium": "medium",
    "low": "low",
    "info": "low",
}


def _get_hunter_db(db_path: Path = HUNTER_DB) -> Optional[sqlite3.Connection]:
    """Connect to Hunter's findings database."""
    if not db_path.exists():
        logger.warning("Hunter DB not found at %s", db_path)
        return None
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        logger.error("Cannot connect to Hunter DB: %s", e)
        return None


def _get_agency_db():
    """Connect to the agency database."""
    from agency_db import _get_conn
    return _get_conn()


def _ensure_bridge_table():
    """Create the red_to_build_mappings table if it doesn't exist."""
    conn = _get_agency_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS red_to_build_mappings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            finding_id INTEGER NOT NULL,
            target_name TEXT,
            vuln_type TEXT,
            severity TEXT,
            task_id TEXT NOT NULL,
            project TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            verified_at TEXT,
            fix_commit_hash TEXT,
            UNIQUE(finding_id)
        )
    """)
    conn.commit()


def recommend_agent(vuln_type: str) -> str:
    """Map vulnerability type to the best Build agent."""
    vt = (vuln_type or "").lower().replace(" ", "_").replace("-", "_")
    return _AGENT_MAP.get(vt, _AGENT_MAP["default"])


def severity_to_priority(severity: str) -> str:
    """Map finding severity to task priority."""
    return _PRIORITY_MAP.get((severity or "").lower(), "medium")


def _already_synced(finding_id: int) -> bool:
    """Check if this finding was already bridged to a Build task."""
    conn = _get_agency_db()
    row = conn.execute(
        "SELECT id FROM red_to_build_mappings WHERE finding_id = ?",
        (finding_id,)
    ).fetchone()
    return row is not None


def sync_findings(ctx, hunter_db_path: Path = HUNTER_DB) -> list[dict]:
    """Poll Hunter's findings DB and create Build tasks for new findings.

    Returns list of newly created tasks.
    """
    _ensure_bridge_table()
    hunter = _get_hunter_db(hunter_db_path)
    if not hunter:
        return []

    try:
        rows = hunter.execute("""
            SELECT id, title, vuln_type, severity, confidence, endpoint,
                   evidence_request, evidence_response, description,
                   target_id
            FROM findings
            WHERE false_positive = 0
              AND (report_status IS NULL OR report_status = 'draft')
            ORDER BY
                CASE severity
                    WHEN 'critical' THEN 0
                    WHEN 'high' THEN 1
                    WHEN 'medium' THEN 2
                    WHEN 'low' THEN 3
                    ELSE 4
                END,
                confidence DESC
        """).fetchall()
    except Exception as e:
        logger.error("Failed to query Hunter findings: %s", e)
        return []
    finally:
        hunter.close()

    new_tasks = []
    backlog_file = ctx.memory_dir / "backlog.md"
    backlog = backlog_file.read_text(encoding="utf-8") if backlog_file.exists() else ""

    for row in rows:
        fid = row["id"]
        if _already_synced(fid):
            continue

        agent = recommend_agent(row["vuln_type"])
        priority = severity_to_priority(row["severity"])
        task_id = f"RED-{fid}"
        title = (row["title"] or f"{row['vuln_type']} vulnerability")[:80]

        # Build the task line
        task_line = (
            f"\n### {task_id}. Fix {row['vuln_type']}: {title} "
            f"[agent: {agent}] (priority: {priority})\n"
            f"- Severity: {row['severity']} | Confidence: {row['confidence']}\n"
            f"- Endpoint: {row['endpoint'] or 'unknown'}\n"
            f"- Evidence: {(row['description'] or '')[:200]}\n"
            f"- Source: Red Team finding #{fid}\n"
        )

        # Append to backlog
        backlog += task_line

        # Record the mapping
        agency = _get_agency_db()
        agency.execute("""
            INSERT OR IGNORE INTO red_to_build_mappings
                (finding_id, target_name, vuln_type, severity, task_id, project)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (fid, "", row["vuln_type"], row["severity"], task_id, ctx.name))
        agency.commit()

        new_tasks.append({
            "task_id": task_id,
            "finding_id": fid,
            "title": title,
            "severity": row["severity"],
            "agent": agent,
        })
        logger.info("Bridged finding #%d → task %s [%s]", fid, task_id, agent)

    # Write updated backlog
    if new_tasks:
        backlog_file.write_text(backlog, encoding="utf-8")

    return new_tasks


def mark_verified(finding_id: int, commit_hash: str, hunter_db_path: Path = HUNTER_DB):
    """Mark a finding as fixed after Build resolves it."""
    now = datetime.now().isoformat()

    # Update bridge table
    agency = _get_agency_db()
    agency.execute("""
        UPDATE red_to_build_mappings
        SET verified_at = ?, fix_commit_hash = ?
        WHERE finding_id = ?
    """, (now, commit_hash, finding_id))
    agency.commit()

    # Update Hunter's findings table
    hunter = _get_hunter_db(hunter_db_path)
    if hunter:
        try:
            hunter.execute("""
                UPDATE findings
                SET report_status = 'verified'
                WHERE id = ?
            """, (finding_id,))
            hunter.commit()
        except Exception:
            pass
        finally:
            hunter.close()

    logger.info("Finding #%d verified — commit %s", finding_id, commit_hash)


def get_unverified_findings() -> list[dict]:
    """Get all Red findings that haven't been fixed by Build yet."""
    _ensure_bridge_table()
    conn = _get_agency_db()
    rows = conn.execute("""
        SELECT finding_id, target_name, vuln_type, severity, task_id, project, created_at
        FROM red_to_build_mappings
        WHERE verified_at IS NULL
        ORDER BY
            CASE severity
                WHEN 'critical' THEN 0 WHEN 'high' THEN 1
                WHEN 'medium' THEN 2 ELSE 3
            END
    """).fetchall()
    return [dict(r) for r in rows]


def council_triage(finding: dict) -> dict:
    """Run the LLM Council to evaluate a finding before HackerOne submission.

    Bull: argues this is a valid, impactful finding worth submitting
    Bear: argues it's a false positive, duplicate, or low impact
    Pragmatist: realistic assessment of acceptance probability + recommended severity

    Returns: {"submit": bool, "recommended_severity": str, "confidence": str, "reasoning": str}
    """
    from council import convene_council

    vuln_type = finding.get("vuln_type", "unknown")
    severity = finding.get("severity", "medium")
    endpoint = finding.get("endpoint", "unknown")
    evidence = finding.get("evidence", finding.get("description", "No evidence provided"))

    question = (
        f"Should we submit this security finding to a bug bounty program?\n\n"
        f"Vulnerability type: {vuln_type}\n"
        f"Severity: {severity}\n"
        f"Endpoint: {endpoint}\n"
        f"Evidence: {str(evidence)[:500]}\n\n"
        f"Bull: argue this is a valid, impactful finding worth submitting.\n"
        f"Bear: argue it's a false positive, duplicate, or low impact.\n"
        f"Pragmatist: give a realistic assessment of acceptance probability "
        f"and recommend the appropriate severity (critical/high/medium/low).\n\n"
        f"The chairman must end with a clear SUBMIT or NO-SUBMIT recommendation."
    )

    result = convene_council(question)

    if "error" in result:
        return {
            "submit": False,
            "recommended_severity": severity,
            "confidence": "LOW",
            "reasoning": f"Council error: {result['error']}",
        }

    synthesis = result.get("synthesis", "")
    confidence = result.get("confidence", "MEDIUM")

    # Parse submit/no-submit from synthesis
    synthesis_upper = synthesis.upper()
    submit = "NO-SUBMIT" not in synthesis_upper and "NO SUBMIT" not in synthesis_upper and (
        "SUBMIT" in synthesis_upper
    )

    # Parse recommended severity from synthesis
    recommended_severity = severity  # default to original
    for sev in ("critical", "high", "medium", "low"):
        if f"severity: {sev}" in synthesis.lower() or f"severity should be {sev}" in synthesis.lower() or f"recommend {sev}" in synthesis.lower():
            recommended_severity = sev
            break

    return {
        "submit": submit,
        "recommended_severity": recommended_severity,
        "confidence": confidence,
        "reasoning": synthesis[:800] if synthesis else "No synthesis produced.",
    }


def share_red_knowledge() -> int:
    """When a vuln pattern is found on one target, check all other targets.

    Example: CORS misconfig found on target A -> scan targets B, C, D for same pattern.

    Creates new tasks: "[RED-XCHECK] Test {vuln_type} on {target}"
    Returns count of cross-check tasks created.
    """
    _ensure_bridge_table()
    conn = _get_agency_db()

    # Get all vuln_types with their associated targets
    rows = conn.execute("""
        SELECT vuln_type, target_name, project
        FROM red_to_build_mappings
        WHERE vuln_type IS NOT NULL AND target_name IS NOT NULL
        ORDER BY vuln_type
    """).fetchall()

    if not rows:
        return 0

    # Group findings by vuln_type
    vuln_targets: dict[str, set[str]] = {}
    vuln_projects: dict[str, set[str]] = {}
    for row in rows:
        vt = row["vuln_type"] if isinstance(row, sqlite3.Row) else row[0]
        target = row["target_name"] if isinstance(row, sqlite3.Row) else row[1]
        project = row["project"] if isinstance(row, sqlite3.Row) else row[2]
        if not vt or not target:
            continue
        vuln_targets.setdefault(vt, set()).add(target)
        vuln_projects.setdefault(vt, set()).add(project or "")

    # Get all known targets from the bridge table
    all_targets_rows = conn.execute("""
        SELECT DISTINCT target_name FROM red_to_build_mappings
        WHERE target_name IS NOT NULL AND target_name != ''
    """).fetchall()
    all_targets = {
        (r["target_name"] if isinstance(r, sqlite3.Row) else r[0])
        for r in all_targets_rows
    }

    # Check for existing cross-check tasks to avoid duplicates
    existing = conn.execute("""
        SELECT task_id FROM red_to_build_mappings
        WHERE task_id LIKE 'RED-XCHECK-%'
    """).fetchall()
    existing_ids = {
        (r["task_id"] if isinstance(r, sqlite3.Row) else r[0])
        for r in existing
    }

    created = 0
    for vt, tested_targets in vuln_targets.items():
        if len(tested_targets) < 2:
            continue  # Need 2+ hits across different targets to trigger

        untested = all_targets - tested_targets
        for target in untested:
            task_id = f"RED-XCHECK-{vt}-{target}"[:80]
            if task_id in existing_ids:
                continue

            # Record the cross-check task in the bridge table
            try:
                conn.execute("""
                    INSERT OR IGNORE INTO red_to_build_mappings
                        (finding_id, target_name, vuln_type, severity, task_id, project)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    -1,  # synthetic finding_id for cross-checks
                    target,
                    vt,
                    "medium",  # default severity for cross-checks
                    task_id,
                    "",  # project TBD
                ))
                created += 1
                existing_ids.add(task_id)
                logger.info("[RED-XCHECK] Test %s on %s", vt, target)
            except Exception as e:
                logger.warning("Failed to create cross-check task: %s", e)

    if created:
        conn.commit()

    return created


def get_bridge_stats() -> dict:
    """Summary stats for the Red-to-Build bridge."""
    _ensure_bridge_table()
    conn = _get_agency_db()
    total = conn.execute("SELECT COUNT(*) FROM red_to_build_mappings").fetchone()[0]
    verified = conn.execute("SELECT COUNT(*) FROM red_to_build_mappings WHERE verified_at IS NOT NULL").fetchone()[0]
    by_severity = {}
    for row in conn.execute("SELECT severity, COUNT(*) as c FROM red_to_build_mappings GROUP BY severity"):
        by_severity[row[0]] = row[1]
    return {
        "total_findings": total,
        "verified": verified,
        "pending": total - verified,
        "by_severity": by_severity,
    }


def compute_red_metrics() -> dict:
    """Compute time-to-fix metrics per severity level.

    Returns: {"total", "fixed", "pending", "avg_fix_hours": {severity: float}, "oldest_unfixed": dict|None}
    """
    _ensure_bridge_table()
    conn = _get_agency_db()
    # Avg fix time per severity (only verified findings)
    avg_rows = conn.execute("""
        SELECT severity,
               AVG((julianday(verified_at) - julianday(created_at)) * 24) as avg_hours
        FROM red_to_build_mappings
        WHERE verified_at IS NOT NULL AND created_at IS NOT NULL
        GROUP BY severity
    """).fetchall()
    avg_fix_hours = {r[0]: round(r[1], 2) for r in avg_rows if r[0]}
    # Oldest unfixed finding
    oldest = conn.execute("""
        SELECT finding_id, severity, vuln_type, task_id, created_at
        FROM red_to_build_mappings
        WHERE verified_at IS NULL
        ORDER BY created_at ASC LIMIT 1
    """).fetchone()
    oldest_unfixed = dict(oldest) if oldest else None
    # Totals
    total = conn.execute("SELECT COUNT(*) FROM red_to_build_mappings").fetchone()[0]
    fixed = conn.execute("SELECT COUNT(*) FROM red_to_build_mappings WHERE verified_at IS NOT NULL").fetchone()[0]
    return {"total": total, "fixed": fixed, "pending": total - fixed,
            "avg_fix_hours": avg_fix_hours, "oldest_unfixed": oldest_unfixed}
