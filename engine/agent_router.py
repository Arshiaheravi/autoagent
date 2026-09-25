#!/usr/bin/env python3
"""Agent Router — pick the best agent for a task based on historical success rates.

Pure query functions against agency_db sessions table.
No side effects, no file I/O beyond the database read.
"""
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Agents below this success rate are deprioritized
MIN_SUCCESS_RATE = 0.40
MIN_AGENT_SESSIONS = 5


def get_agent_success_rate(project: str, agent_name: str, task_type: str) -> float:
    """Compute an agent's success rate for a given session type.

    Returns float between 0.0 and 1.0. Returns 0.0 if no sessions found.
    """
    from agency_db import _get_conn

    conn = _get_conn()
    row = conn.execute(
        """SELECT COUNT(*) as total,
                  SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as wins
           FROM sessions
           WHERE project = ? AND agent = ? AND session_type = ?""",
        (project, agent_name, task_type),
    ).fetchone()

    total = row["total"] if row else 0
    if total == 0:
        return 0.0
    return row["wins"] / total


def get_agent_session_count(project: str, agent_name: str, task_type: str) -> int:
    """Return how many matching sessions exist for an agent/task type."""
    from agency_db import _get_conn

    conn = _get_conn()
    row = conn.execute(
        "SELECT COUNT(*) as total FROM sessions WHERE project=? AND agent=? AND session_type=?",
        (project, agent_name, task_type),
    ).fetchone()
    return int(row["total"] if row else 0)


def pick_best_agent(
    project: str,
    task_type: str,
    candidates: list[str],
) -> Optional[str]:
    """Pick the best agent from candidates based on success rate history.

    Returns the agent name with the highest success rate for this task type.
    Ties broken by total session count (more experience = more confidence).
    Agents below MIN_SUCCESS_RATE (40%) are deprioritized.
    Returns None if no candidate has any session history.
    """
    scored = []
    for agent in candidates:
        rate = get_agent_success_rate(project, agent, task_type)
        count = get_agent_session_count(project, agent, task_type)

        scored.append((agent, rate, count))

    # Filter out agents without enough history to make a routing decision
    with_history = [(a, r, c) for a, r, c in scored if c >= MIN_AGENT_SESSIONS]
    if not with_history:
        return None

    # Separate into above-threshold and below-threshold
    above = [(a, r, c) for a, r, c in with_history if r >= MIN_SUCCESS_RATE]
    pool = above if above else with_history  # fall back to all if none above threshold

    # Sort by success rate desc, then session count desc (tiebreak)
    pool.sort(key=lambda x: (x[1], x[2]), reverse=True)

    return pool[0][0]


def maybe_swap_agent(project: str, agent_name: str, session_type: str,
                     agents_dir: Path) -> str:
    """If current agent is underperforming, swap to a better one. Returns agent name."""
    rate = get_agent_success_rate(project, agent_name, session_type)
    count = get_agent_session_count(project, agent_name, session_type)
    if count < MIN_AGENT_SESSIONS:
        return agent_name
    if rate >= MIN_SUCCESS_RATE:
        return agent_name
    if not agents_dir.is_dir():
        return agent_name
    # Exclude orchestrator.md — it's the routing role, not a task specialist
    # (mirrors list_agents / org_model). Otherwise it can be swapped in to run
    # a work task.
    candidates = [f.stem for f in agents_dir.glob("*.md") if f.stem != "orchestrator"]
    better = pick_best_agent(project, session_type, candidates)
    if better and better != agent_name:
        logger.info("Routing: %s (%.0f%%) → %s", agent_name, rate * 100, better)
        return better
    return agent_name
