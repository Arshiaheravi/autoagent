#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Session analytics, cost tracking, hooks config, and session logging."""
import json
import re
import shlex
import subprocess
from datetime import date, datetime, timedelta
from pathlib import Path

from registry import ProjectContext
from session_scoring import (  # noqa: F401 — backward compat re-exports
    format_session_label, compute_quality_score, compute_task_impact_score,
    health_auto_meta, _session_is_noop,
)


# ── Cost summaries ───────────────────────────────────────────
def lifetime_cost_summary(budget_file: Path) -> float:
    """Sum all date entries in daily_budget.json."""
    if not budget_file.exists(): return 0.0
    try: data = json.loads(budget_file.read_text(encoding="utf-8"))
    except Exception: return 0.0
    return sum(v for v in data.values() if isinstance(v, (int, float)))


def weekly_cost_summary(budget_file: Path) -> float:
    """Sum last 7 days in daily_budget.json."""
    if not budget_file.exists(): return 0.0
    try: data = json.loads(budget_file.read_text(encoding="utf-8"))
    except Exception: return 0.0
    cutoff = date.today() - timedelta(days=7)
    total = 0.0
    for k, v in data.items():
        if not isinstance(v, (int, float)): continue
        try: d = date.fromisoformat(k)
        except ValueError: continue
        if d > cutoff: total += v
    return total


# ── Session analytics ────────────────────────────────────────
def parse_session_analytics(sessions_file: Path) -> dict:
    """Parse sessions.json → {total_sessions, tests_added, test_count_latest, type_counts, avg_quality, recent}."""
    empty = {
        "total_sessions": 0, "tests_added": 0, "test_count_latest": 0,
        "type_counts": {}, "avg_quality": 0, "recent": [],
    }
    if not sessions_file.exists():
        return empty
    try:
        sessions = json.loads(sessions_file.read_text(encoding="utf-8"))
    except Exception:
        return empty
    if not sessions:
        return empty

    total = len(sessions)
    type_counts = {}
    tests_added = 0
    test_count_latest = 0
    quality_scores = []

    for s in sessions:
        stype = s.get("type", "work")
        type_counts[stype] = type_counts.get(stype, 0) + 1

        tests = s.get("tests", {})
        before = tests.get("before", 0) or 0
        after = tests.get("after", 0) or 0
        if after > before:
            tests_added += after - before
        if after > 0:
            test_count_latest = after

        q = s.get("quality", {})
        if isinstance(q, dict) and q.get("score") is not None:
            quality_scores.append(q["score"])

    avg_quality = round(sum(quality_scores) / len(quality_scores)) if quality_scores else 0

    recent = []
    for s in reversed(sessions[-5:]):
        recent.append({
            "session": s.get("session", 0),
            "type": s.get("type", "work"),
            "summary": s.get("summary", ""),
        })

    return {
        "total_sessions": total,
        "tests_added": tests_added,
        "test_count_latest": test_count_latest,
        "type_counts": type_counts,
        "avg_quality": avg_quality,
        "recent": recent,
    }


# ── Session filtering ────────────────────────────────────────
def filter_sessions(sessions_file: Path, session_type: str | None = None,
                    last_n: int | None = None, search: str | None = None) -> list[dict]:
    """Filter sessions by type, recency, and/or search term (order: type → search → last_n)."""
    if not sessions_file.exists(): return []
    try: sessions = json.loads(sessions_file.read_text(encoding="utf-8"))
    except Exception: return []
    if not sessions: return []
    result = list(sessions)
    if session_type: result = [s for s in result if s.get("type") == session_type]
    if search:
        term = search.lower()
        result = [s for s in result if term in s.get("summary", "").lower()]
    if last_n is not None and last_n > 0: result = result[-last_n:]
    return result


# ── Infrastructure-level session logging ─────────────────────
def _extract_test_command(ctx: ProjectContext) -> str | None:
    """Parse the test command from PROJECT.md (code block under ### Test Command)."""
    if not ctx.project_file.exists():
        return None
    content = ctx.project_file.read_text(encoding="utf-8")
    m = re.search(r'###\s*Test Command\s*\n```[^\n]*\n(.+?)\n```', content, re.DOTALL)
    if not m:
        return None
    return m.group(1).strip()


def _parse_test_command(raw: str) -> tuple[str | None, list[str]]:
    """Parse 'cd /dir && cmd args' → (cwd, [cmd, args]) without shell=True."""
    # Normalize continuation lines
    text = raw.replace("\\\n", " ")
    # Match 'cd <path> &&' prefix
    m = re.match(r'^cd\s+(\S+)\s*&&\s*(.+)$', text, re.DOTALL)
    if m:
        return m.group(1), shlex.split(m.group(2).strip())
    return None, shlex.split(text.strip())


def log_session_entry(ctx: ProjectContext, session_num: int,
                      session_type: str, success: bool, agent: str = "",
                      cost_usd: float = 0.0, model: str = ""):
    """Append session entry to sessions.json (infrastructure fallback if agent didn't log)."""
    sessions = []
    if ctx.sessions_file.exists():
        try:
            sessions = json.loads(ctx.sessions_file.read_text(encoding="utf-8"))
        except Exception:
            sessions = []

    # If agent already logged this session, enrich it with infrastructure-known
    # cost + model (agent always writes cost_usd: 0.0 because it can't know its
    # own cost mid-session). This is the fix for B7 (audit 2026-04-16 §0 item 5):
    # 267 sessions logged cost_usd: 0 because only the agent was writing.
    for s in sessions:
        if s.get("session") == session_num:
            updated = False
            if "success" not in s or s.get("success") != bool(success):
                s["success"] = bool(success)
                updated = True
            if agent and not s.get("agent"):
                s["agent"] = agent
                updated = True
            if cost_usd and cost_usd > 0 and (s.get("cost_usd", 0.0) or 0.0) == 0.0:
                s["cost_usd"] = round(float(cost_usd), 4)
                updated = True
            if model and not s.get("model"):
                s["model"] = model
                updated = True
            if updated:
                ctx.sessions_file.write_text(
                    json.dumps(sessions, indent=2), encoding="utf-8",
                )
            try:
                from session_db_sync import sync_session_entry_to_agency_db
                sync_session_entry_to_agency_db(ctx, s, success=success)
            except Exception:
                pass
            return

    # Extract task name from current_task.md (if present)
    task_name = ""
    ct = ctx.memory_dir / "current_task.md"
    if ct.exists():
        first = ct.read_text(encoding="utf-8").split("\n", 1)[0]
        if first.startswith("# Current Task:"):
            task_name = first.replace("# Current Task:", "").strip()

    # Extract summary from latest git commit (if agent committed)
    summary = ""
    files_changed = []
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%s"],
            cwd=str(ctx.project_root), capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            summary = result.stdout.strip()
            if summary.lower().startswith("agent: "):
                summary = summary[7:]
    except Exception:
        pass

    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD~1", "HEAD"],
            cwd=str(ctx.project_root), capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            files_changed = [f for f in result.stdout.strip().splitlines() if f]
    except Exception:
        pass

    # Count tests via test command
    test_count = 0
    test_status = "skip"
    raw_cmd = _extract_test_command(ctx)
    if raw_cmd and session_type == "work":
        try:
            cwd, cmd_list = _parse_test_command(raw_cmd)
            result = subprocess.run(
                cmd_list, cwd=cwd or str(ctx.project_root),
                capture_output=True, text=True, timeout=300,
            )
            test_status = "pass" if result.returncode == 0 else "fail"
            m = re.search(r'(\d+) passed', result.stdout)
            if m:
                test_count = int(m.group(1))
        except Exception:
            test_status = "skip"

    # Determine if this was a ghost (success=False but commit exists)
    is_ghost = not success and summary != ""

    entry = {
        "session": session_num,
        "date": date.today().isoformat(),
        "time": datetime.now().strftime("%H:%M"),
        "type": session_type,
        "agent": agent,
        "success": bool(success),
        "task": task_name,
        "summary": summary or format_session_label(
            session_num, agent=agent, task=task_name or session_type,
            files_count=len(files_changed), test_count=test_count, success=success),
        "files": files_changed,
        "cost_usd": round(float(cost_usd or 0.0), 4), "model": model,
        "tests": {
            "before": 0,
            "after": test_count,
            "status": test_status,
        },
        "frontend": {
            "status": "skip",
            "checks": 0,
            "failures": 0,
            "notes": "Logged by infrastructure (agent did not log)",
        },
    }
    if is_ghost:
        entry["notes"] = "GHOST — agent committed but crashed before logging"

    # Task impact score — derive from available infrastructure data
    prev_tc = next((s.get("tests", {}).get("after", 0) or 0
                     for s in reversed(sessions)
                     if (s.get("tests", {}).get("after", 0) or 0) > 0), 0)
    entry["impact_score"] = compute_task_impact_score(
        tests_added=max(test_count - prev_tc, 0) if test_count else 0,
        quality_delta=0, commit_produced=summary != "",
        regressions=1 if test_status == "fail" else 0,
    )

    sessions.append(entry)
    ctx.sessions_file.write_text(
        json.dumps(sessions, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    try:
        from session_db_sync import sync_session_entry_to_agency_db
        sync_session_entry_to_agency_db(ctx, entry, success=success)
    except Exception:
        pass
    label = format_session_label(session_num, agent=agent, task=task_name or session_type,
                                  files_count=len(files_changed), test_count=test_count, success=success)
    print(f"  [AutoAgent] {label} logged to sessions.json")


# ── Session type ──────────────────────────────────────────────
def get_session_type(session_num: int) -> str:
    if session_num % 50 == 0: return "knowledge"
    if session_num % 25 == 0: return "audit"
    if session_num % 20 == 0: return "deep"
    if session_num % 10 == 0: return "brain"
    if session_num % 5  == 0: return "meta"
    return "work"


# ── Hooks config (moved to session_hooks.py) ─────────────────
from session_hooks import generate_hooks_config, generate_hooks_settings_json, write_hooks_config  # noqa: F401 — backward compat
