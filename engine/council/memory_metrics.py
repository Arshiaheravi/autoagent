"""Memory layer metrics — measures whether recall actually helps convenes.

Two signals matter:
  - recall_rate: % of convenes that had a prior verdict surfaced.
  - verdict_stability_pct: of repeat questions (same question_hash seen
    twice in the window), % where the winner matched the prior decision.
    Climbing stability = recall is anchoring the council.

Designed to be cheap — single SELECT for the rollup, one CTE for the
repeat-question logic. Safe to call on a hot DB.
"""
from __future__ import annotations

import logging
from typing import Any

from .memory import with_conn

logger = logging.getLogger(__name__)


def weekly_rollup(
    days: int = 7,
    *,
    question_prefix: str | None = None,
) -> dict[str, Any]:
    """Return aggregate memory-layer metrics over the last `days` days.

    Args:
        days: lookback window in days. Default 7.
        question_prefix: optional LIKE filter — only count rows whose
            question starts with this prefix. Used by tests to scope by
            their TEST_TAG. None = no filter (production rollup).

    Returns:
        {
            "days": int,
            "convenes_total": int,
            "convenes_with_recall": int,
            "recall_rate": float,            # 0.0 - 1.0
            "verdict_stability_pct": float,  # 0.0 - 100.0
            "repeat_questions": int,
            "avg_recalled_count": float,
        }
    """
    empty: dict[str, Any] = {
        "days": days,
        "convenes_total": 0,
        "convenes_with_recall": 0,
        "recall_rate": 0.0,
        "verdict_stability_pct": 0.0,
        "repeat_questions": 0,
        "avg_recalled_count": 0.0,
    }
    try:
        # 1) Aggregate convene counts + recall rate over the window.
        prefix_clause = "AND question LIKE %s" if question_prefix else ""
        params: list[Any] = [days]
        if question_prefix:
            params.append(f"{question_prefix}%")

        with with_conn() as conn, conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    count(*)::int AS convenes_total,
                    coalesce(sum(CASE WHEN had_recall_block THEN 1 ELSE 0 END), 0)::int
                        AS convenes_with_recall,
                    coalesce(avg(recalled_count), 0.0)::float AS avg_recalled_count
                FROM council_episodic
                WHERE ts >= now() - (%s::int * INTERVAL '1 day')
                {prefix_clause}
                """,
                params,
            )
            total, with_recall, avg_recalled = cur.fetchone()
            total = int(total or 0)
            with_recall = int(with_recall or 0)
            avg_recalled = float(avg_recalled or 0.0)

            # 2) Verdict-stability over repeat questions in the window.
            cur.execute(
                f"""
                WITH window_rows AS (
                    SELECT question_hash, winner, ts,
                           row_number() OVER (
                               PARTITION BY question_hash ORDER BY ts DESC
                           ) AS rn
                    FROM council_episodic
                    WHERE ts >= now() - (%s::int * INTERVAL '1 day')
                    {prefix_clause}
                ),
                repeats AS (
                    SELECT question_hash,
                           (SELECT winner FROM window_rows wr2
                            WHERE wr2.question_hash = wr.question_hash
                            AND wr2.rn = 1) AS latest_winner,
                           (SELECT winner FROM window_rows wr2
                            WHERE wr2.question_hash = wr.question_hash
                            AND wr2.rn = 2) AS prior_winner,
                           count(*) AS occurrences
                    FROM window_rows wr
                    GROUP BY question_hash
                    HAVING count(*) >= 2
                )
                SELECT count(*)::int AS repeat_questions,
                       coalesce(
                           sum(CASE WHEN latest_winner = prior_winner THEN 1 ELSE 0 END),
                           0
                       )::int AS stable_count
                FROM repeats
                """,
                params,
            )
            repeat_questions, stable_count = cur.fetchone()
            repeat_questions = int(repeat_questions or 0)
            stable_count = int(stable_count or 0)

    except Exception as e:
        logger.warning("memory_metrics.weekly_rollup failed: %s: %s",
                       type(e).__name__, str(e)[:200])
        return empty

    recall_rate = (with_recall / total) if total else 0.0
    stability = (100.0 * stable_count / repeat_questions) if repeat_questions else 0.0

    return {
        "days": days,
        "convenes_total": total,
        "convenes_with_recall": with_recall,
        "recall_rate": round(recall_rate, 4),
        "verdict_stability_pct": round(stability, 2),
        "repeat_questions": repeat_questions,
        "avg_recalled_count": round(avg_recalled, 4),
    }


__all__ = ["weekly_rollup"]
