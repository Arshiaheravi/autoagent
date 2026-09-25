#!/usr/bin/env python3
"""Memory layer telemetry report — does recall actually help?

Usage:
    python3 scripts/memory_layer_report.py [--days N] [--project NAME]

Reads council_episodic, prints recall rate, verdict stability, and the
top-N most-recalled prior verdicts. Cheap — single rollup query + one
top-N query.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ENGINE = Path(__file__).resolve().parent.parent / "engine"
sys.path.insert(0, str(ENGINE))

from council.memory import with_conn  # noqa: E402
from council.memory_metrics import weekly_rollup  # noqa: E402


def _top_recalled(days: int, limit: int = 5) -> list[tuple]:
    """Most-cited prior verdicts in the window — the rows that recall has
    pulled into stage1 most often."""
    try:
        with with_conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT recalled_id::bigint, count(*)::int AS cite_count
                FROM council_episodic, unnest(recalled_ids) AS recalled_id
                WHERE ts >= now() - (%s::int * INTERVAL '1 day')
                GROUP BY recalled_id
                ORDER BY cite_count DESC
                LIMIT %s
                """,
                (days, limit),
            )
            return cur.fetchall()
    except Exception:
        return []


def _resolve_questions(ids: list[int]) -> dict[int, str]:
    if not ids:
        return {}
    try:
        with with_conn() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT id, question FROM council_episodic WHERE id = ANY(%s)",
                (ids,),
            )
            return {int(r[0]): r[1] for r in cur.fetchall()}
    except Exception:
        return {}


def main():
    parser = argparse.ArgumentParser(description="Memory layer telemetry report")
    parser.add_argument("--days", type=int, default=7, help="Lookback window")
    args = parser.parse_args()

    rollup = weekly_rollup(days=args.days)

    print(f"\n=== Memory Layer Report — last {rollup['days']}d ===\n")
    print(f"  convenes_total       : {rollup['convenes_total']}")
    print(f"  convenes_with_recall : {rollup['convenes_with_recall']}")
    print(f"  recall_rate          : {rollup['recall_rate']:.1%}")
    print(f"  avg_recalled_count   : {rollup['avg_recalled_count']:.2f}")
    print(f"  repeat_questions     : {rollup['repeat_questions']}")
    print(f"  verdict_stability_pct: {rollup['verdict_stability_pct']:.1f}%")

    top = _top_recalled(args.days, limit=5)
    if top:
        question_map = _resolve_questions([t[0] for t in top])
        print(f"\n  Top-{len(top)} cited prior verdicts:")
        for row_id, cite_count in top:
            q = (question_map.get(int(row_id)) or "")[:80]
            print(f"    id={row_id} cited={cite_count}× q='{q}'")
    print()

    if rollup["convenes_total"] == 0:
        print("(empty — no convenes in window. Flip COUNCIL_MEMORY_ENABLED=true "
              "and run a convene to seed.)")


if __name__ == "__main__":
    main()
