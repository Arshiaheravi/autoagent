#!/usr/bin/env python3
"""Backfill council_episodic (pgvector) from SQLite council_decisions.

Reads every row from the council_decisions table in agency.db (SQLite) and
replays it through engine.council.memory.persist() so historical verdicts
seed the pgvector recall table.

Usage:
    python3 scripts/backfill_council_memory.py [--dry-run] [--db PATH]

Env:
    COUNCIL_MEMORY_ENABLED=true   required to actually write
"""
from __future__ import annotations

import argparse
import hashlib
import logging
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

ENGINE = Path(__file__).resolve().parent.parent / "engine"
sys.path.insert(0, str(ENGINE))

DEFAULT_DB = Path.home() / ".autoagent" / "agency.db"


def _hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8", errors="ignore")).hexdigest()


def _persist(
    *,
    question: str,
    context: str,
    result: dict[str, Any],
    project: str | None = None,
    decision_id_legacy: int | None = None,
) -> int | None:
    from council.memory import persist
    return persist(
        question=question,
        context=context,
        result=result,
        project=project,
        decision_id_legacy=decision_id_legacy,
    )


def _check_existing_hash(question_hash: str) -> bool:
    from council.memory import with_conn
    with with_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM council_episodic WHERE question_hash = %s LIMIT 1",
            (question_hash,),
        )
        return cur.fetchone() is not None


def run_backfill(db_path: str, dry_run: bool = False) -> dict[str, int]:
    from council.memory import is_enabled

    if not dry_run and not is_enabled():
        raise RuntimeError(
            "COUNCIL_MEMORY_ENABLED must be set to 'true' to write. "
            "Use --dry-run to preview without writing."
        )

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, project, session_num, question, winner, confidence, synthesis "
        "FROM council_decisions ORDER BY id"
    ).fetchall()
    conn.close()

    total = len(rows)
    inserted = 0
    skipped = 0
    errors = 0
    would_insert = 0

    for i, row in enumerate(rows, 1):
        question = row["question"]
        q_hash = _hash(question)

        if not dry_run and _check_existing_hash(q_hash):
            skipped += 1
            if i % 50 == 0:
                logger.info("progress: %d/%d (inserted=%d skipped=%d errors=%d)",
                            i, total, inserted, skipped, errors)
            continue

        if dry_run:
            if _check_existing_hash(q_hash):
                skipped += 1
            else:
                would_insert += 1
            if i % 50 == 0:
                logger.info("progress [dry-run]: %d/%d (would_insert=%d skipped=%d)",
                            i, total, would_insert, skipped)
            continue

        result = {
            "synthesis": row["synthesis"],
            "winner": row["winner"],
            "confidence": row["confidence"],
            "mode": "executive",
            "stage1": [],
            "stage2": {"aggregate": []},
        }

        try:
            _persist(
                question=question,
                context="",
                result=result,
                project=row["project"],
                decision_id_legacy=row["id"],
            )
            inserted += 1
        except Exception as e:
            errors += 1
            logger.error("row %d (id=%s) failed: %s: %s",
                         i, row["id"], type(e).__name__, str(e)[:200])

        if i % 50 == 0:
            logger.info("progress: %d/%d (inserted=%d skipped=%d errors=%d)",
                        i, total, inserted, skipped, errors)

    stats = {
        "total": total,
        "inserted": inserted,
        "skipped": skipped,
        "errors": errors,
        "would_insert": would_insert,
    }

    summary = (
        f"Backfill complete: total={total} "
        f"inserted={inserted} skipped={skipped} errors={errors}"
    )
    if dry_run:
        summary = (
            f"Dry-run complete: total={total} "
            f"would_insert={would_insert} skipped={skipped}"
        )
    logger.info(summary)
    print(summary)

    return stats


def main():
    parser = argparse.ArgumentParser(description="Backfill council memory from SQLite")
    parser.add_argument("--dry-run", action="store_true",
                        help="Count what would be persisted without writing")
    parser.add_argument("--db", type=str, default=str(DEFAULT_DB),
                        help=f"Path to agency.db (default: {DEFAULT_DB})")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    stats = run_backfill(args.db, dry_run=args.dry_run)
    if stats["errors"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
