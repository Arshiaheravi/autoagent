#!/usr/bin/env python3
"""Per-agent memory and cross-agent performance tracking.

Each agent accumulates session history, learned patterns, and common failures.
Performance stats are used for routing tie-breaks.
"""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from registry import ProjectContext

logger = logging.getLogger(__name__)

_MEMORY_DIR = ".memory"
_PERFORMANCE_FILE = "_performance.json"
_MAX_RECENT_SESSIONS = 20
_MAX_PATTERNS = 15
_MAX_FAILURES = 10
_MAX_TECHNIQUES = 15


def _memory_dir(ctx: ProjectContext) -> Path:
    d = ctx.agents_dir / _MEMORY_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def _memory_file(ctx: ProjectContext, agent_name: str) -> Path:
    return _memory_dir(ctx) / f"{agent_name}.json"


def _performance_file(ctx: ProjectContext) -> Path:
    return _memory_dir(ctx) / _PERFORMANCE_FILE


# ── Per-Agent Memory ─────────────────────────────────────────────


def _default_memory(agent_name: str) -> dict:
    return {
        "agent": agent_name,
        "total_sessions": 0,
        "last_session": None,
        "success_rate": 0.0,
        "learned_patterns": [],
        "common_failures": [],
        "preferred_files": [],
        "recent_sessions": [],
        "techniques": [],
    }


def load_agent_memory(ctx: ProjectContext, agent_name: str) -> dict:
    """Load per-agent memory. Returns defaults if no memory exists."""
    f = _memory_file(ctx, agent_name)
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            pass
    return _default_memory(agent_name)


def save_agent_memory(ctx: ProjectContext, agent_name: str, memory: dict) -> None:
    """Save per-agent memory."""
    f = _memory_file(ctx, agent_name)
    try:
        f.write_text(json.dumps(memory, indent=2, default=str), encoding="utf-8")
    except Exception as e:
        logger.warning("Failed to save agent memory for %s: %s", agent_name, e)


def update_agent_memory(ctx: ProjectContext, agent_name: str,
                        session_num: int, success: bool,
                        summary: str = "", files_changed: Optional[list[str]] = None) -> None:
    """Append a session result to agent memory."""
    mem = load_agent_memory(ctx, agent_name)

    # Update counters
    mem["total_sessions"] += 1
    mem["last_session"] = datetime.now(timezone.utc).isoformat()

    # Rolling success rate
    total = mem["total_sessions"]
    old_rate = mem.get("success_rate", 0.0)
    mem["success_rate"] = round(((old_rate * (total - 1)) + (1.0 if success else 0.0)) / total, 3)

    # Append to recent sessions (keep last N)
    mem["recent_sessions"].append({
        "session": session_num,
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "success": success,
        "summary": summary[:200],
    })
    mem["recent_sessions"] = mem["recent_sessions"][-_MAX_RECENT_SESSIONS:]

    # Update preferred files (frequency-based top 10)
    if files_changed:
        file_freq: dict[str, int] = {}
        for f in mem.get("preferred_files", []):
            file_freq[f] = file_freq.get(f, 0) + 1
        for f in files_changed:
            file_freq[f] = file_freq.get(f, 0) + 1
        sorted_files = sorted(file_freq.items(), key=lambda x: x[1], reverse=True)
        mem["preferred_files"] = [f for f, _ in sorted_files[:10]]

    # Record failure pattern if session failed
    if not success and summary:
        failures = mem.get("common_failures", [])
        if summary not in failures:
            failures.append(summary[:150])
        mem["common_failures"] = failures[-_MAX_FAILURES:]

    save_agent_memory(ctx, agent_name, mem)


def record_technique(ctx: ProjectContext, agent_name: str, *,
                     technique: str, files_affected: list[str],
                     success: bool, session_num: int) -> None:
    """Store a structured technique entry in agent memory. Deduplicates by text."""
    mem = load_agent_memory(ctx, agent_name)
    techniques = mem.setdefault("techniques", [])
    # Deduplicate — skip if same technique text already exists
    if any(t["technique"] == technique for t in techniques):
        save_agent_memory(ctx, agent_name, mem)
        return
    techniques.append({
        "technique": technique,
        "files_affected": files_affected,
        "success": success,
        "session_num": session_num,
    })
    # Cap at max
    mem["techniques"] = techniques[-_MAX_TECHNIQUES:]
    save_agent_memory(ctx, agent_name, mem)


def inject_agent_memory_context(ctx: ProjectContext, agent_name: str,
                                 max_chars: int = 500) -> str:
    """Generate a memory context string for boot prompt injection.

    Includes last 3 sessions, top patterns, top failures.
    """
    mem = load_agent_memory(ctx, agent_name)
    if mem["total_sessions"] == 0:
        return ""

    parts = [f"## Your session history ({mem['total_sessions']} sessions, {mem['success_rate']:.0%} success)"]

    # Last 3 sessions
    recent = mem.get("recent_sessions", [])[-3:]
    if recent:
        parts.append("Recent:")
        for s in recent:
            status = "OK" if s["success"] else "FAILED"
            parts.append(f"  #{s['session']} [{status}] {s['summary'][:80]}")

    # Top learned patterns
    patterns = mem.get("learned_patterns", [])[:3]
    if patterns:
        parts.append("Learned:")
        for p in patterns:
            parts.append(f"  - {p[:80]}")

    # Successful techniques
    techniques = [t for t in mem.get("techniques", []) if t.get("success")]
    if techniques:
        parts.append("Techniques that worked for you before:")
        for t in techniques[-5:]:
            parts.append(f"  - {t['technique'][:80]}")

    # Common failures (as warnings)
    failures = mem.get("common_failures", [])[:2]
    if failures:
        parts.append("Watch out for:")
        for f in failures:
            parts.append(f"  - {f[:80]}")

    result = "\n".join(parts)
    return result[:max_chars]


# ── Cross-Agent Performance Tracking ─────────────────────────────


def _load_performance(ctx: ProjectContext) -> dict:
    f = _performance_file(ctx)
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"updated": None, "agents": {}}


def _save_performance(ctx: ProjectContext, data: dict) -> None:
    f = _performance_file(ctx)
    try:
        data["updated"] = datetime.now(timezone.utc).isoformat()
        f.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    except Exception as e:
        logger.warning("Failed to save performance data: %s", e)


def update_performance(ctx: ProjectContext, agent_name: Optional[str],
                       success: bool, quality_score: Optional[int] = None,
                       was_fallback: bool = False) -> None:
    """Update cross-agent performance tracker."""
    if not agent_name:
        return
    perf = _load_performance(ctx)
    agents = perf.setdefault("agents", {})
    entry = agents.setdefault(agent_name, {
        "total_sessions": 0, "successful": 0, "failed": 0,
        "avg_quality_score": 0, "fallback_count": 0,
    })

    entry["total_sessions"] += 1
    if success:
        entry["successful"] += 1
    else:
        entry["failed"] += 1
    if was_fallback:
        entry["fallback_count"] += 1
    if quality_score is not None:
        old_avg = entry.get("avg_quality_score", 0)
        total = entry["total_sessions"]
        entry["avg_quality_score"] = round(((old_avg * (total - 1)) + quality_score) / total)

    _save_performance(ctx, perf)


def get_agent_performance(ctx: ProjectContext, agent_name: str) -> dict:
    """Get performance stats for one agent."""
    perf = _load_performance(ctx)
    return perf.get("agents", {}).get(agent_name, {
        "total_sessions": 0, "successful": 0, "failed": 0,
        "avg_quality_score": 0, "fallback_count": 0,
    })


def rank_agents_by_performance(ctx: ProjectContext) -> list[tuple[str, float]]:
    """Rank all agents by success_rate. Used for routing tie-breaks."""
    perf = _load_performance(ctx)
    ranked = []
    for name, stats in perf.get("agents", {}).items():
        total = stats.get("total_sessions", 0)
        if total == 0:
            continue
        rate = stats.get("successful", 0) / total
        ranked.append((name, rate))
    ranked.sort(key=lambda x: x[1], reverse=True)
    return ranked
