#!/usr/bin/env python3
"""Bulk-ingest external decision corpora into council_episodic so the
council reads precedent decisions pre-stage1 alongside its own SQLite
history (which scripts/backfill_council_memory.py covers).

Canonical input schema (JSON array):
    [
        {
            "id":          "k8s-adr-001",        # required, unique within platform
            "title":       "Choose primary DB",  # required
            "question":    "Should we use ...?", # required
            "synthesis":   "We chose X because ...", # required
            "winner":      "postgres",           # required
            "confidence":  "HIGH",               # required (HIGH/MEDIUM/LOW)
            "platform":    "adrs",               # required — adrs|tc39|pep|...
            "context":     "service backend",    # optional
            "decided_at":  "2024-09-15",         # optional
            "url":         "https://..."         # optional
        },
        ...
    ]

Maps to council_episodic columns 1:1. Idempotent on question_hash.

Usage:
    python3 scripts/ingest_council_corpus.py --source corpus.json --dry-run
    python3 scripts/ingest_council_corpus.py --source corpus.json --confirm
    python3 scripts/ingest_council_corpus.py --source corpus.json --confirm \
        --platform adrs --limit 100

Requires COUNCIL_MEMORY_ENABLED=true to actually write (council memory
layer's gate). --dry-run bypasses that gate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "engine"))

from council import memory as cm  # noqa: E402

logger = logging.getLogger(__name__)

REQUIRED_FIELDS = ("id", "title", "question", "synthesis", "winner",
                   "confidence", "platform")


def _has_required(row: dict) -> bool:
    return all(row.get(f) for f in REQUIRED_FIELDS)


def _question_hash(question: str) -> str:
    """Must match council.memory._hash so the dedup probe lines up."""
    return hashlib.sha256((question or "").encode("utf-8", errors="ignore")).hexdigest()


def _hash_exists(q_hash: str) -> bool:
    try:
        with cm.with_conn() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM council_episodic WHERE question_hash = %s LIMIT 1",
                (q_hash,),
            )
            return cur.fetchone() is not None
    except Exception:
        return False


def run_ingest(
    source: str,
    *,
    dry_run: bool = False,
    confirm: bool = False,
    platform: str | None = None,
    limit: int | None = None,
) -> dict[str, int]:
    """Run the ingester. Returns a stats dict.

    Args:
        source: path to canonical-schema JSON.
        dry_run: count without writing.
        confirm: must be True (or dry_run) to actually write.
        platform: optional filter — only rows matching this platform string.
        limit: optional cap on rows considered.
    """
    if not dry_run and not confirm:
        raise RuntimeError(
            "refusing to write — pass --confirm to actually ingest, "
            "or --dry-run to preview."
        )

    if not dry_run and not cm.is_enabled():
        raise RuntimeError(
            "COUNCIL_MEMORY_ENABLED must be 'true' to write. "
            "Use --dry-run to preview without writing."
        )

    path = Path(source)
    if not path.exists():
        raise FileNotFoundError(f"corpus file not found: {source}")

    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError(f"corpus must be JSON array, got {type(rows).__name__}")

    total = 0
    would_insert = 0
    inserted = 0
    skipped = 0
    errors = 0

    for i, row in enumerate(rows):
        if limit is not None and (inserted + skipped + errors + would_insert) >= limit:
            break

        if platform:
            if (row.get("platform") or "").lower() != platform.lower():
                continue

        total += 1

        if not _has_required(row):
            errors += 1
            logger.warning("row %d malformed (missing required fields): id=%r",
                           i, row.get("id"))
            continue

        question = row["question"]
        q_hash = _question_hash(question)

        if _hash_exists(q_hash):
            skipped += 1
            continue

        if dry_run:
            would_insert += 1
            continue

        try:
            result_dict = {
                "stage1": [],
                "stage2": {"aggregate": []},
                "synthesis": row["synthesis"],
                "winner": row["winner"],
                "confidence": row["confidence"],
                "mode": "executive",
            }
            cm.persist(
                question=question,
                context=row.get("context", "") or "",
                result=result_dict,
                project=f"corpus:{row['platform']}:{row.get('id', '')}"[:100],
            )
            inserted += 1
        except Exception as e:
            errors += 1
            logger.error("row %d (id=%s) insert failed: %s: %s",
                         i, row.get("id"), type(e).__name__, str(e)[:200])

        if (inserted + skipped + errors) % 100 == 0:
            logger.info("progress: inserted=%d skipped=%d errors=%d",
                        inserted, skipped, errors)

    return {
        "total": total,
        "would_insert": would_insert,
        "inserted": inserted,
        "skipped": skipped,
        "errors": errors,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Ingest external decision corpus into council_episodic")
    parser.add_argument("--source", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--confirm", action="store_true")
    parser.add_argument("--platform", default=None,
                        help="Only ingest rows with this platform")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    stats = run_ingest(
        args.source,
        dry_run=args.dry_run,
        confirm=args.confirm,
        platform=args.platform,
        limit=args.limit,
    )

    if args.dry_run:
        print(f"Dry-run: total={stats['total']} would_insert={stats['would_insert']} "
              f"skipped={stats['skipped']} errors={stats['errors']}")
    else:
        print(f"Ingest complete: total={stats['total']} inserted={stats['inserted']} "
              f"skipped={stats['skipped']} errors={stats['errors']}")
    if stats["errors"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
