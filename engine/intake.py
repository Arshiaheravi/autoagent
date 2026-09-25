#!/usr/bin/env python3
"""Project intake — set up a new project with agent team and backlog."""
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Optional

from registry import register, get, ProjectContext, AGENCY_HOME
from models import DEFAULT_MODEL, DEFAULT_DAILY_LIMIT_USD


def setup_project(
    name: str,
    project_root: Path | str,
    project_md: str,
    north_star_md: str,
    backlog_md: str,
    domain_agents: Optional[dict[str, str]] = None,
    tech_stack: Optional[str] = None,
    test_command: Optional[str] = None,
) -> ProjectContext:
    """Create a fully configured project — the non-Claude part of intake.

    Args:
        name: Project name
        project_root: Path to the project repo
        project_md: Content for PROJECT.md
        north_star_md: Content for NORTH_STAR.md
        backlog_md: Content for memory/backlog.md
        domain_agents: Dict of {agent-name: markdown-content} for domain-specific agents
        tech_stack: e.g. "Python/FastAPI"
        test_command: e.g. "pytest tests/ -q"
    """
    project_root = Path(project_root).resolve()

    # Register the project
    ctx = register(name, project_root)
    ctx.ensure_dirs()

    # Write project files
    (ctx.project_home / "PROJECT.md").write_text(project_md, encoding="utf-8")
    (ctx.project_home / "NORTH_STAR.md").write_text(north_star_md, encoding="utf-8")

    # Write project.json
    project_json = {
        "model": DEFAULT_MODEL,
        "daily_limit_usd": DEFAULT_DAILY_LIMIT_USD,
        "session_max_turns": 50,
    }
    if tech_stack:
        project_json["tech_stack"] = tech_stack
    if test_command:
        project_json["test_command"] = test_command
    (ctx.project_home / "project.json").write_text(
        json.dumps(project_json, indent=2), encoding="utf-8"
    )

    # Initialize memory files
    (ctx.memory_dir / "backlog.md").write_text(backlog_md, encoding="utf-8")
    (ctx.memory_dir / "current_task.md").write_text("# Current Task: (none)\n", encoding="utf-8")
    (ctx.memory_dir / "activity_log.md").write_text("# Activity Log\n", encoding="utf-8")
    (ctx.memory_dir / "knowledge.md").write_text("# Knowledge\n", encoding="utf-8")
    (ctx.memory_dir / "done.md").write_text("# Done\n", encoding="utf-8")

    # Copy universal agent templates, replacing {{project_name}}.
    # The department manifest is the source of truth when present; otherwise
    # fall back to scanning templates/agents while ignoring Finder duplicates.
    try:
        from org_model import universal_agent_template_paths
        universal_templates = universal_agent_template_paths(AGENCY_HOME)
    except Exception:
        templates_agents = AGENCY_HOME / "templates" / "agents"
        universal_templates = [
            f for f in sorted(templates_agents.glob("*.md"))
            if not re.search(r"\s+\d+\.md$", f.name)
        ] if templates_agents.exists() else []
    for f in universal_templates:
        content = f.read_text(encoding="utf-8")
        content = content.replace("{{project_name}}", name)
        (ctx.agents_dir / f.name).write_text(content, encoding="utf-8")

    # Add domain-specific agents
    if domain_agents:
        for agent_name, agent_content in domain_agents.items():
            fname = f"{agent_name}.md" if not agent_name.endswith(".md") else agent_name
            (ctx.agents_dir / fname).write_text(agent_content, encoding="utf-8")

    # Generate orchestrator from agent roster
    _generate_orchestrator(ctx, domain_agents)

    # Create symlink
    ctx.ensure_symlink()

    return ctx


def _generate_orchestrator(ctx: ProjectContext, domain_agents: Optional[dict[str, str]] = None):
    """Generate an orchestrator.md from the full agent roster."""
    agents = []
    for f in sorted(ctx.agents_dir.glob("*.md")):
        if f.name == "orchestrator.md":
            continue
        agent_name = f.stem
        # Extract first line as description
        first_line = f.read_text(encoding="utf-8").split("\n")[0].strip("# ").strip()
        agents.append((agent_name, first_line))

    roster_table = "| Agent | Role |\n|---|---|\n"
    for name, desc in agents:
        roster_table += f"| **{name}** | {desc} |\n"

    orchestrator = f"""# Orchestrator

You are the project orchestrator for {ctx.name}. You route tasks to the right specialist agent.

## Your role

You don't do the work — you direct it. When a task arrives, you:
1. Identify which agent should handle it
2. Break complex tasks into subtasks assigned to specific agents
3. Define the order of operations when agents depend on each other

## Agent roster

{roster_table}

## Routing rules

- **New feature** → Architect (design) + relevant specialist (build) + Test Writer (tests)
- **Bug fix** → Architect (diagnose) → specialist (fix)
- **Accuracy/calibration** → relevant domain specialist
- **Deployment** → Infra + Architect (foresight check)
"""
    (ctx.agents_dir / "orchestrator.md").write_text(orchestrator, encoding="utf-8")


def _consume_staging() -> Optional[ProjectContext]:
    """Read the intake staging directory and call setup_project().

    Returns ProjectContext on success, None if staging is missing or invalid.
    Cleans up the staging directory after successful consumption.
    """
    staging = AGENCY_HOME / "projects" / "_intake_staging"
    if not staging.exists():
        return None

    manifest_file = staging / "manifest.json"
    if not manifest_file.exists():
        print("  Warning: staging directory exists but no manifest.json found")
        return None

    try:
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"  Error reading manifest.json: {e}")
        return None

    name = manifest.get("name")
    project_path = manifest.get("project_path")
    if not name or not project_path:
        print("  Error: manifest.json missing 'name' or 'project_path'")
        return None

    project_root = Path(project_path)
    if not project_root.exists():
        print(f"  Error: project path does not exist: {project_root}")
        return None

    # Read generated files from staging
    project_md = ""
    north_star_md = ""
    backlog_md = ""

    pm = staging / "PROJECT.md"
    if pm.exists():
        project_md = pm.read_text(encoding="utf-8")

    ns = staging / "NORTH_STAR.md"
    if ns.exists():
        north_star_md = ns.read_text(encoding="utf-8")

    bl = staging / "memory" / "backlog.md"
    if bl.exists():
        backlog_md = bl.read_text(encoding="utf-8")

    # Read domain agents
    domain_agents = {}
    agents_dir = staging / "agents"
    if agents_dir.exists():
        for f in agents_dir.glob("*.md"):
            domain_agents[f.stem] = f.read_text(encoding="utf-8")

    ctx = setup_project(
        name=name,
        project_root=project_root,
        project_md=project_md,
        north_star_md=north_star_md,
        backlog_md=backlog_md,
        domain_agents=domain_agents or None,
        tech_stack=manifest.get("tech_stack"),
        test_command=manifest.get("test_command"),
    )

    # Clean up staging directory
    shutil.rmtree(staging)

    print(f"  [Intake] Project '{name}' created successfully!")
    print(f"    → {ctx.project_home}")
    return ctx


def run_intake(description: str = "", project_path: Optional[str] = None):
    """Run the full interactive intake — spawns Claude to interview the user.

    This is the CLI-facing function. For non-interactive use, call setup_project() directly.
    """
    claude = shutil.which("claude")
    if not claude:
        print("  Error: Claude CLI not found. Install: npm install -g @anthropic-ai/claude-code")
        return None

    intake_prompt_file = AGENCY_HOME / "templates" / "INTAKE_PROMPT.md"
    if not intake_prompt_file.exists():
        print(f"  Error: {intake_prompt_file} not found")
        return None

    intake_prompt = intake_prompt_file.read_text(encoding="utf-8")

    # Build the boot prompt
    boot = intake_prompt
    if description:
        boot += f"\n\nThe user's initial idea: \"{description}\"\n"
    if project_path:
        boot += f"\nExisting project repo: {project_path}\n"

    staging_dir = AGENCY_HOME / "projects" / "_intake_staging"
    boot += f"\nWrite all output files to: {staging_dir}/\n"

    print(f"\n  [AutoAgent Agency] Starting project intake...")
    print(f"  Claude will ask you questions about your project.\n")

    # Run interactively — user answers questions in terminal
    try:
        result = subprocess.run(
            [claude, "-p", boot,
             "--dangerously-skip-permissions",
             "--max-turns", "30"],
            cwd=str(AGENCY_HOME),
        )
        if result.returncode != 0:
            print("  [Intake] Claude session failed.")
            return None
    except KeyboardInterrupt:
        print("\n  [Intake] Cancelled.")
        return None

    # Consume staging output and auto-setup the project
    ctx = _consume_staging()
    if ctx is None:
        print("  [Intake] Warning: Could not auto-setup project from staging output.")
        print("  You can set it up manually with: autoagent register <name> <path>")
        return None

    return ctx
