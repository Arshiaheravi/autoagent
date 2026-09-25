#!/usr/bin/env python3
"""User Empathy Simulator — roleplay as the target user walking through the product.

Reports: confusion points, delight moments, drop-off risks, fix suggestions.
Triggered by feature flag `empathy_sim` + tasks tagged [ux].
"""
import logging
import os
import shutil
import subprocess
from pathlib import Path

from registry import ProjectContext

logger = logging.getLogger(__name__)

# Example personas, keyed by project name. A project with a matching name uses
# its persona automatically; any other project falls back to `custom_persona`
# (or the generic default in run_empathy_sim). Add your own project's persona
# here, or pass one at call time — these are just illustrative defaults.
PERSONAS = {
    "example-consumer-app": (
        "I'm a non-technical user trying this product for the first time. "
        "I use my phone for almost everything and give up fast when something "
        "is confusing. I want to get value in the first two minutes."
    ),
    "example-b2b-saas": (
        "I evaluate tools for a mid-size company. I'm skeptical of marketing "
        "claims and I need concrete ROI numbers, not pretty dashboards, before "
        "I'll recommend adopting anything."
    ),
    "autoagent": (
        "I'm a solo developer shipping a SaaS product. I work 12-hour days and "
        "can't keep up with bugs, tests, and feature requests. I heard about an "
        "AI agent that builds code overnight. Sounds too good to be true."
    ),
}


def run_empathy_sim(ctx: ProjectContext, custom_persona: str = "") -> str:
    """Simulate a target user walking through the product.

    Returns a UX audit with specific, actionable findings.
    """
    project_desc = ""
    if ctx.project_file.exists():
        project_desc = ctx.project_file.read_text(encoding="utf-8")[:800]

    persona = custom_persona or PERSONAS.get(ctx.name,
        "I'm a new user visiting this product for the first time. I have no context.")

    prompt = f"""You are roleplaying as this person:
"{persona}"

You just opened this product for the first time:
{project_desc}

Walk through the experience step by step. For each moment, report what you see,
think, and feel. Then summarize:

## First Impression (0-5 seconds)
What catches your eye? What's your gut reaction? Would you stay or bounce?

## Confusion Points
Where did you get lost? What's unclear? What jargon doesn't make sense to you?

## Delight Moments
What made you think "oh, this is cool" or "this actually helps me"?

## Drop-Off Risks
At what point would you close the tab? What's the friction?

## Missing Information
What questions do you have that the product doesn't answer?

## Fix Suggestions
5 specific, concrete improvements ranked by impact. Not vague — exact changes.
For each: what to change, where, and why it matters for someone like you.

Be brutally honest. You are the user, not a consultant trying to be nice."""

    claude = shutil.which("claude") or "claude"
    try:
        result = subprocess.run(
            [claude, "-p", prompt, "--max-turns", "1", "--output-format", "text"],
            capture_output=True, text=True, timeout=120,
            cwd=str(ctx.project_root), encoding="utf-8", errors="replace",
        )
        return result.stdout.strip() if result.returncode == 0 else "Empathy sim failed."
    except Exception as e:
        return f"Empathy sim error: {e}"


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    from registry import get, list_projects
    project = sys.argv[1] if len(sys.argv) > 1 else list_projects()[0]["name"]
    print(run_empathy_sim(get(project)))
