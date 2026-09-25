#!/usr/bin/env python3
"""Registry utilities — validation, skill promotion, knowledge extraction."""
import shutil
from pathlib import Path

from registry import ProjectContext, get, list_projects


def promote_skill(project_name: str, skill_name: str):
    """Copy a project-specific skill to the shared skills directory."""
    ctx = get(project_name)
    skill_file = ctx.project_home / "skills" / f"{skill_name}.md"
    if not skill_file.exists():
        raise FileNotFoundError(
            f"Skill '{skill_name}' not found in project '{project_name}' at {skill_file}"
        )
    shared_dir = ctx.agency_home / "skills"
    shared_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(skill_file, shared_dir / f"{skill_name}.md")


def extract_universal_rules(ctx: ProjectContext) -> list[str]:
    """Extract rules from knowledge.md that don't reference project-specific names."""
    knowledge_file = ctx.memory_dir / "knowledge.md"
    if not knowledge_file.exists():
        return []

    project_names = {p["name"] for p in list_projects()}

    rules = []
    for line in knowledge_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped.startswith("RULE:"):
            continue
        if any(name in stripped for name in project_names):
            continue
        rules.append(stripped)
    return rules


def validate_project(ctx: ProjectContext) -> list[str]:
    """Check project health and return a list of warning strings. Empty = healthy."""
    warnings = []

    if not ctx.project_file.exists():
        warnings.append("Missing PROJECT.md — project has no configuration file")

    if not ctx.north_star_file.exists():
        warnings.append("Missing NORTH_STAR.md — no mission or success metrics defined")

    if not ctx.agents_dir.exists() or not list(ctx.agents_dir.glob("*.md")):
        warnings.append("No agents defined — create agents with: autoagent agent create")

    backlog = ctx.memory_dir / "backlog.md"
    if not backlog.exists():
        warnings.append("Missing backlog.md — no tasks queued for the agent")
    else:
        content = backlog.read_text(encoding="utf-8")
        if "- [ ]" not in content:
            warnings.append("Backlog has no unchecked tasks — agent has nothing to work on")

    if not ctx.memory_dir.exists():
        warnings.append("Missing memory directory — run ensure_dirs() first")

    return warnings
