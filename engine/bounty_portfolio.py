#!/usr/bin/env python3
"""Bounty Portfolio — track and optimize bug bounty target selection.

Stores HackerOne submissions in SQLite, computes per-program ROI,
and recommends which targets to prioritize.

Usage:
    from bounty_portfolio import log_submission, get_portfolio_stats, recommend_targets
    log_submission("shopify", "xss", "medium", 500.0, "accepted")
    stats = get_portfolio_stats()
    targets = recommend_targets(n=5)
"""
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


def _get_conn():
    """Get agency database connection and ensure bounty table exists."""
    from agency_db import _get_conn as get_connection
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bounty_submissions (
            id INTEGER PRIMARY KEY,
            target TEXT NOT NULL,
            program TEXT,
            vuln_type TEXT,
            severity TEXT,
            finding_id INTEGER,
            submitted_at TEXT DEFAULT (datetime('now')),
            status TEXT DEFAULT 'pending',
            payout_usd REAL DEFAULT 0,
            response_days INTEGER,
            notes TEXT
        )
    """)
    conn.commit()
    return conn


def log_submission(
    target: str,
    vuln_type: str,
    severity: str,
    payout: float = 0.0,
    status: str = "pending",
    program: Optional[str] = None,
    finding_id: Optional[int] = None,
    response_days: Optional[int] = None,
    notes: str = "",
) -> int:
    """Record a HackerOne submission.

    Returns:
        The row ID of the new submission.
    """
    conn = _get_conn()
    cur = conn.execute(
        """INSERT INTO bounty_submissions
           (target, program, vuln_type, severity, finding_id, status, payout_usd, response_days, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (target, program or target, vuln_type, severity, finding_id,
         status, payout, response_days, notes),
    )
    conn.commit()
    logger.info("Logged bounty submission #%d: %s/%s [%s]", cur.lastrowid, target, vuln_type, status)
    return cur.lastrowid


def get_portfolio_stats() -> dict:
    """Overall portfolio statistics.

    Returns:
        dict with total_submissions, acceptance_rate, total_payouts,
        avg_payout_by_severity, status_breakdown.
    """
    conn = _get_conn()

    total = conn.execute("SELECT COUNT(*) FROM bounty_submissions").fetchone()[0]
    if total == 0:
        return {
            "total_submissions": 0,
            "acceptance_rate": 0.0,
            "total_payouts": 0.0,
            "avg_payout_by_severity": {},
            "status_breakdown": {},
        }

    accepted = conn.execute(
        "SELECT COUNT(*) FROM bounty_submissions WHERE status = 'accepted'"
    ).fetchone()[0]

    total_payouts = conn.execute(
        "SELECT COALESCE(SUM(payout_usd), 0) FROM bounty_submissions"
    ).fetchone()[0]

    # Avg payout by severity (only accepted)
    avg_by_severity = {}
    for row in conn.execute(
        """SELECT severity, AVG(payout_usd) as avg_p, COUNT(*) as cnt
           FROM bounty_submissions WHERE status = 'accepted'
           GROUP BY severity ORDER BY avg_p DESC"""
    ):
        avg_by_severity[row[0]] = {"avg_payout": round(row[1], 2), "count": row[2]}

    # Status breakdown
    status_breakdown = {}
    for row in conn.execute(
        "SELECT status, COUNT(*) FROM bounty_submissions GROUP BY status"
    ):
        status_breakdown[row[0]] = row[1]

    return {
        "total_submissions": total,
        "acceptance_rate": round(accepted / total, 3) if total else 0.0,
        "total_payouts": round(total_payouts, 2),
        "avg_payout_by_severity": avg_by_severity,
        "status_breakdown": status_breakdown,
    }


def get_program_roi(target: str) -> dict:
    """Per-program stats for a specific target.

    Returns:
        dict with submissions, accepted, rejected, duplicate,
        avg_response_days, total_payout, acceptance_rate.
    """
    conn = _get_conn()

    rows = conn.execute(
        "SELECT * FROM bounty_submissions WHERE target = ?", (target,)
    ).fetchall()

    if not rows:
        return {"target": target, "submissions": 0, "message": "No submissions found"}

    total = len(rows)
    accepted = sum(1 for r in rows if r["status"] == "accepted")
    rejected = sum(1 for r in rows if r["status"] == "rejected")
    duplicate = sum(1 for r in rows if r["status"] == "duplicate")
    total_payout = sum(r["payout_usd"] or 0 for r in rows)

    response_days = [r["response_days"] for r in rows if r["response_days"] is not None]
    avg_response = round(sum(response_days) / len(response_days), 1) if response_days else None

    return {
        "target": target,
        "submissions": total,
        "accepted": accepted,
        "rejected": rejected,
        "duplicate": duplicate,
        "avg_response_days": avg_response,
        "total_payout": round(total_payout, 2),
        "acceptance_rate": round(accepted / total, 3) if total else 0.0,
    }


def recommend_targets(n: int = 5) -> list[dict]:
    """Rank targets by estimated ROI.

    Score = acceptance_rate * avg_payout.
    Targets with fewer than 1 accepted submission get a penalty.

    Returns:
        Sorted list of dicts with target, score, acceptance_rate, avg_payout, submissions.
    """
    conn = _get_conn()

    targets = conn.execute(
        "SELECT DISTINCT target FROM bounty_submissions"
    ).fetchall()

    scored = []
    for row in targets:
        target = row[0]
        stats = get_program_roi(target)
        if stats["submissions"] == 0:
            continue

        avg_payout = stats["total_payout"] / stats["accepted"] if stats.get("accepted", 0) > 0 else 0
        acceptance_rate = stats["acceptance_rate"]

        # Confidence adjustment: penalize targets with very few submissions
        confidence = min(stats["submissions"] / 5.0, 1.0)
        score = acceptance_rate * avg_payout * confidence

        scored.append({
            "target": target,
            "score": round(score, 2),
            "acceptance_rate": acceptance_rate,
            "avg_payout": round(avg_payout, 2),
            "submissions": stats["submissions"],
            "accepted": stats.get("accepted", 0),
            "total_payout": stats["total_payout"],
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:n]


def analyze_vuln_type_performance() -> dict:
    """Analyze which vulnerability types perform best.

    Returns:
        dict keyed by vuln_type with acceptance_rate, avg_payout,
        total_submissions, total_accepted, total_payout.
    """
    conn = _get_conn()

    rows = conn.execute(
        """SELECT vuln_type,
                  COUNT(*) as total,
                  SUM(CASE WHEN status='accepted' THEN 1 ELSE 0 END) as accepted,
                  COALESCE(SUM(payout_usd), 0) as total_payout,
                  AVG(CASE WHEN status='accepted' THEN payout_usd END) as avg_accepted_payout
           FROM bounty_submissions
           GROUP BY vuln_type
           ORDER BY total_payout DESC"""
    ).fetchall()

    result = {}
    for r in rows:
        vtype = r[0] or "unknown"
        total = r[1]
        accepted = r[2]
        result[vtype] = {
            "total_submissions": total,
            "total_accepted": accepted,
            "acceptance_rate": round(accepted / total, 3) if total else 0.0,
            "total_payout": round(r[3], 2),
            "avg_payout": round(r[4], 2) if r[4] else 0.0,
        }

    return result
