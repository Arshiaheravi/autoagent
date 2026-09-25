#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Post-session hooks: code review, agent memory, self-improvement, notifications."""
import logging
import subprocess

from registry import ProjectContext

logger = logging.getLogger(__name__)


def _log_knowledge(ctx: ProjectContext, entry: str):
    """Append a rule entry to knowledge.md."""
    kf = ctx.memory_dir / "knowledge.md"
    existing = kf.read_text(encoding="utf-8") if kf.exists() else ""
    kf.write_text(existing + entry, encoding="utf-8")


def run_post_session_hooks(ctx: ProjectContext, session_num: int,
                           session_type: str, success: bool,
                           agent_name: str = ""):
    """Run all post-session hooks: reviews, agent memory, self-improve, notify."""
    # Codex code review — independent second opinion before ship
    if success and session_type == "work":
        try:
            from council import codex_review
            codex_review(ctx, session_num, _log_knowledge)
        except Exception as e:
            logger.debug("Codex review skipped: %s", e)

    # UX review — council evaluates frontend changes
    if success and session_type == "work":
        try:
            from council import ux_review
            ux_review(ctx, session_num, _log_knowledge)
        except Exception as e:
            logger.debug("UX review skipped: %s", e)

    # Design council: visual review on frontend changes
    if success and session_type == "work":
        try:
            diff_check = subprocess.run(
                ["git", "diff", "--stat", "HEAD~1"], cwd=str(ctx.project_root),
                capture_output=True, text=True, timeout=10,
            ).stdout
            has_frontend = any(ext in diff_check for ext in [".tsx", ".jsx", ".css", ".html", ".vue", ".svelte"])
            if has_frontend:
                from council import design_council
                dr = design_council(ctx, session_num, log_fn=_log_knowledge)
                if dr["status"] == "issues":
                    print(f"  [Design Council] Score: {dr['score']:.1f}/10 — improvements needed")
                elif dr["status"] == "pass":
                    print(f"  [Design Council] Score: {dr['score']:.1f}/10 — looks good")
        except Exception:
            pass

    # Update per-agent memory and cross-agent performance
    if agent_name:
        try:
            from agent_memory import update_agent_memory, update_performance
            from agency_db import update_agent_stats, upsert_agent
            update_agent_memory(ctx, agent_name, session_num, success,
                                summary=f"{session_type} session #{session_num}")
            update_performance(ctx, agent_name, success)
            upsert_agent(ctx.name, agent_name)
            update_agent_stats(ctx.name, agent_name, success)
        except Exception:
            pass  # memory update is non-critical

    # Self-improvement: quality gate, metrics, skill generation
    try:
        from self_improve import post_session_improve
        post_session_improve(ctx)
    except Exception:
        pass

    # Auto-refresh activity_log.md from sessions.json
    try:
        import json
        from activity_log import append_activity_log_entry
        sf = ctx.sessions_file
        if sf.exists():
            entries = json.loads(sf.read_text(encoding="utf-8"))
            latest = next((e for e in reversed(entries) if e.get("session") == session_num), None)
            if latest:
                append_activity_log_entry(
                    ctx.memory_dir / "activity_log.md",
                    session_type=latest.get("type", session_type),
                    summary=latest.get("summary", f"Session #{session_num}"),
                    files=latest.get("files", []),
                )
    except Exception as e:
        logger.debug("Activity log auto-refresh skipped: %s", e)

    # Notify the operator via Telegram
    try:
        from comms import session_complete
        ct = ctx.memory_dir / "current_task.md"
        _t = ct.read_text(encoding="utf-8").split("\n", 1)[0].replace("# Current Task:", "").strip() if ct.exists() else ""
        session_complete(ctx.name, session_num, session_type, success, agent=agent_name, summary=_t)
    except Exception:
        pass
