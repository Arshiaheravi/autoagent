#!/usr/bin/env python3
"""Feature flags, frustration detection, and ULTRAPLAN mode.

Inspired by patterns from production agent harnesses:
1. Feature flags — gate experimental capabilities per project
2. Frustration detection — detect when agent is stuck in loops
3. ULTRAPLAN — deep planning phase before complex tasks

Feature flags are stored in .autoagent/config.json under "flags" key.
Default: all off. Enable per-project or globally.
"""
import json
import logging
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── Feature Flags ────────────────────────────────────────────────────────────

# All available flags with defaults (all off)
AVAILABLE_FLAGS = {
    "council":      False,  # LLM Council for high-stakes decisions
    "parallel":     False,  # Worktree-based parallel sessions
    "audit":        True,   # Security audit sessions (on by default)
    "ultraplan":    False,  # Deep planning before complex tasks
    "frustration":  True,   # Stuck-loop detection (on by default)
    "exchange_map": True,   # Canadian exchange availability on crypto cards
}


def get_flag(ctx, flag_name: str) -> bool:
    """Check if a feature flag is enabled for a project."""
    flags = ctx.config.get("flags", {})
    return flags.get(flag_name, AVAILABLE_FLAGS.get(flag_name, False))


def set_flag(ctx, flag_name: str, enabled: bool):
    """Set a feature flag for a project."""
    config_file = ctx.project_home / "config.json"
    config = {}
    if config_file.exists():
        try:
            config = json.loads(config_file.read_text())
        except Exception:
            pass
    if "flags" not in config:
        config["flags"] = {}
    config["flags"][flag_name] = enabled
    config_file.write_text(json.dumps(config, indent=2))


def list_flags(ctx) -> dict:
    """List all flags with their current state."""
    flags = ctx.config.get("flags", {})
    return {name: flags.get(name, default) for name, default in AVAILABLE_FLAGS.items()}


# ── Frustration Detection ────────────────────────────────────────────────────

# Patterns that indicate an agent is stuck
_STUCK_PATTERNS = [
    re.compile(r'(?i)(trying again|let me try|retrying|attempt(?:ing)?\s+again)'),
    re.compile(r'(?i)(i apologize|sorry.{0,20}(try|attempt|fix))'),
    re.compile(r'(?i)(still (failing|broken|not working))'),
    re.compile(r'(?i)(same error|same issue|same problem)'),
    re.compile(r'(?i)(cannot|unable to|failed to).{0,30}(fix|resolve|solve)'),
    re.compile(r'(?i)(going in circles|stuck|deadlock|infinite loop)'),
]

# Files seen more than N times suggest circular edits
_MAX_FILE_VISITS = 5


class FrustrationDetector:
    """Monitors agent output for signs it's stuck in a loop.

    Tracks:
    - Repeated failure phrases across turns
    - Same file being read/edited more than N times
    - Consecutive tool errors
    """

    def __init__(self, threshold: int = 5):
        self.threshold = threshold
        self.frustration_score = 0
        self.file_visits: dict[str, int] = {}
        self.consecutive_errors = 0
        self.turn_count = 0

    def observe_text(self, text: str):
        """Check agent text output for stuck patterns."""
        self.turn_count += 1
        for pattern in _STUCK_PATTERNS:
            if pattern.search(text):
                self.frustration_score += 1
                break

    def observe_tool(self, tool_name: str, target: str, success: bool = True):
        """Track tool usage for circular behavior."""
        if target:
            self.file_visits[target] = self.file_visits.get(target, 0) + 1
            if self.file_visits[target] > _MAX_FILE_VISITS:
                self.frustration_score += 1

        if not success:
            self.consecutive_errors += 1
            if self.consecutive_errors >= 3:
                self.frustration_score += 2
        else:
            self.consecutive_errors = 0

    def is_stuck(self) -> bool:
        """Return True if the agent appears to be in a stuck loop."""
        return self.frustration_score >= self.threshold

    def summary(self) -> dict:
        """Return frustration metrics."""
        most_visited = sorted(self.file_visits.items(), key=lambda x: -x[1])[:3]
        return {
            "score": self.frustration_score,
            "threshold": self.threshold,
            "stuck": self.is_stuck(),
            "turns": self.turn_count,
            "consecutive_errors": self.consecutive_errors,
            "hot_files": most_visited,
        }


# ── ULTRAPLAN Mode ───────────────────────────────────────────────────────────

def build_ultraplan_prompt(task: str, project_name: str, context: str = "") -> str:
    """Build a deep planning prompt that runs BEFORE the work session.

    ULTRAPLAN creates a step-by-step implementation plan with:
    - File inventory (what exists, what needs creating)
    - Dependency order (what must be done first)
    - Risk assessment (what could go wrong)
    - Test strategy (how to verify each step)
    - Estimated complexity (simple/medium/complex per step)

    The plan is saved to current_task.md and the work session follows it.
    """
    return f"""You are a senior software architect planning a task for project '{project_name}'.

## Task
{task}

{f"## Context{chr(10)}{context}" if context else ""}

## Your job
Create a DETAILED implementation plan. Do NOT write code — only plan.

Output EXACTLY this format:

### PLAN: [task name]

**Complexity:** [SIMPLE | MEDIUM | COMPLEX]
**Estimated steps:** [N]
**Risk level:** [LOW | MEDIUM | HIGH]

#### Files to read first
1. [file path] — [why]

#### Implementation steps
1. [Step description] — Files: [paths] — Test: [how to verify] — Risk: [what could break]
2. ...

#### Dependencies
- Step N must complete before step M because [reason]

#### Failure modes
1. [What could go wrong] — Mitigation: [how to prevent]

#### Definition of done
- [ ] [Checklist item 1]
- [ ] [Checklist item 2]

Be specific. Name exact files, functions, and test commands. No hand-waving."""


def maybe_ultraplan(ctx, session_type: str):
    """Check if ULTRAPLAN should run and execute it if so."""
    if not get_flag(ctx, "ultraplan") or session_type != "work":
        return
    ct = ctx.memory_dir / "current_task.md"
    task_text = ct.read_text(encoding="utf-8") if ct.exists() else ""
    if "ULTRAPLAN" not in task_text and len(task_text) > 100:
        print(f"  [ULTRAPLAN] Generating implementation plan...")
        run_ultraplan(ctx, task_text[:500])


def run_ultraplan(ctx, task: str) -> Optional[str]:
    """Run ULTRAPLAN: generate a detailed plan before starting work.

    Returns the plan text, or None if planning fails.
    Saves plan to current_task.md for the work session to follow.
    """
    import shutil
    import subprocess

    claude = shutil.which("claude") or "claude"
    context = ""

    # Load north star for context
    ns = ctx.project_home / "NORTH_STAR.md"
    if ns.exists():
        context += ns.read_text(encoding="utf-8")[:500]

    # Load recent knowledge
    kf = ctx.memory_dir / "knowledge.md"
    if kf.exists():
        context += "\n\nRecent learnings:\n" + kf.read_text(encoding="utf-8")[-500:]

    prompt = build_ultraplan_prompt(task, ctx.name, context)

    try:
        result = subprocess.run(
            [claude, "-p", prompt, "--max-turns", "1", "--output-format", "text"],
            cwd=str(ctx.project_root),
            capture_output=True, text=True, timeout=120,
            encoding="utf-8", errors="replace",
        )
        plan = result.stdout.strip()
        if not plan or len(plan) < 50:
            return None

        # Save plan to current_task.md
        ct = ctx.memory_dir / "current_task.md"
        ct.write_text(f"# ULTRAPLAN\n\n{plan}\n", encoding="utf-8")
        logger.info("ULTRAPLAN generated for '%s' (%d chars)", task[:50], len(plan))
        return plan
    except Exception as e:
        logger.warning("ULTRAPLAN failed: %s", e)
        return None
