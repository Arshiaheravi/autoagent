#!/usr/bin/env python3
"""Weekly Creative Brief — what shipped, content ideas, opportunities.

Generates a marketing-ready brief every week (or on demand).
Output: ~/.autoagent/memory/weekly_brief.md + Telegram notification.
"""
import json
import logging
import os
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from registry import list_projects, get, AGENCY_HOME

logger = logging.getLogger(__name__)


def _call(prompt: str, timeout: int = 180) -> str:
    claude = shutil.which("claude") or "claude"
    try:
        r = subprocess.run(
            [claude, "-p", prompt, "--max-turns", "1", "--output-format", "text"],
            capture_output=True, text=True, timeout=timeout,
            cwd=str(Path.home()), encoding="utf-8", errors="replace")
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception as e:
        logger.warning("Creative brief failed: %s", e)
        return ""


def generate_brief(days: int = 7) -> str:
    """Generate the weekly creative brief.

    Covers: what shipped, social content ideas, feature spotlight,
    partnership idea, next week focus.
    """
    # Collect recent activity
    activity = {}
    contexts = {}
    for p in list_projects():
        ctx = get(p["name"])
        if ctx.project_file.exists():
            contexts[p["name"]] = ctx.project_file.read_text(encoding="utf-8")[:400]
        if ctx.sessions_file.exists():
            try:
                sessions = json.loads(ctx.sessions_file.read_text(encoding="utf-8"))
                cutoff = (datetime.now() - timedelta(days=days)).isoformat()[:10]
                recent = [s for s in sessions if s.get("date", "") >= cutoff and s.get("success")]
                if recent:
                    lines = [f"  {s.get('summary','')[:80]}" for s in recent[-8:] if s.get("summary")]
                    activity[p["name"]] = "\n".join(lines)
            except Exception:
                pass

    if not activity:
        return "No activity this week."

    prompt = f"""You are the creative director for an AI development agency.

## Projects
{chr(10).join(f'**{n}**: {c}' for n, c in contexts.items())}

## This Week's Completed Work
{chr(10).join(f'**{n}**:{chr(10)}{s}' for n, s in activity.items())}

Write a punchy weekly brief:

### What Shipped
3-5 highlights. Lead with impact, not implementation. "Users can now..." not "Added function..."

### Social Content Ideas
3 Twitter/X thread ideas. Each: hook line + 3 bullet talking points. Make them shareable.

### Feature Spotlight
1 feature to demo or blog about. Include: who it's for, what problem it solves, one screenshot idea.

### Partnership Opportunity
1 specific company or community to reach out to. Why they'd care. What we'd propose.

### Next Week Focus
What should the agency prioritize? Be decisive — pick ONE thing per project.

Keep each section under 80 words. No filler."""

    brief = _call(prompt)
    if not brief:
        return "Brief generation failed."

    # Save
    bf = AGENCY_HOME / "memory" / "weekly_brief.md"
    bf.parent.mkdir(parents=True, exist_ok=True)
    bf.write_text(f"# Weekly Brief — {datetime.now().strftime('%Y-%m-%d')}\n\n{brief}\n", encoding="utf-8")

    # Telegram summary
    try:
        from comms import _send
        _send(f"📋 <b>Weekly Creative Brief</b>\n\n{brief[:1500]}")
    except Exception:
        pass

    logger.info("Creative brief generated (%d chars)", len(brief))
    return brief


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    print(generate_brief(days))
