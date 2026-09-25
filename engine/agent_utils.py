#!/usr/bin/env python3
"""Agent utilities — listing, loading, and generating agent .md files."""
from pathlib import Path
from typing import Optional

from registry import ProjectContext


def list_agents(ctx: ProjectContext) -> list[dict]:
    """List all agents with name + first-line description."""
    agents = []
    if not ctx.agents_dir.exists():
        return agents
    for f in sorted(ctx.agents_dir.glob("*.md")):
        if f.name == "orchestrator.md":
            continue
        name = f.stem
        lines = f.read_text(encoding="utf-8").splitlines()
        # Description is first non-empty, non-heading line
        desc = name
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                desc = stripped
                break
            elif stripped.startswith("# "):
                desc = stripped.lstrip("# ").strip()
        agents.append({"name": name, "description": desc})
    return agents


def load_agent_prompt(ctx: ProjectContext, agent_name: str) -> str:
    """Load an agent's .md file content. Returns empty string if not found."""
    agent_file = ctx.agents_dir / f"{agent_name}.md"
    if agent_file.exists():
        return agent_file.read_text(encoding="utf-8")
    return ""


def condense_agent_prompt(agent_md_text: str, max_chars: int = 3000) -> str:
    """Extract the most important parts of an agent .md for inline injection.

    Priority: role description > expertise > principles > first skill.
    Truncates to max_chars while keeping complete sections.
    """
    if not agent_md_text:
        return ""

    lines = agent_md_text.splitlines()
    sections: list[tuple[str, str]] = []  # (heading, content)
    current_heading = "intro"
    current_lines: list[str] = []

    for line in lines:
        if line.strip().startswith("## ") or line.strip().startswith("# "):
            if current_lines:
                sections.append((current_heading, "\n".join(current_lines).strip()))
            current_heading = line.strip().lstrip("# ").strip()
            current_lines = []
        else:
            current_lines.append(line)
    if current_lines:
        sections.append((current_heading, "\n".join(current_lines).strip()))

    # Priority order for inclusion
    priority_patterns = [
        r"intro",
        r"expertise|responsibility|your role",
        r"architecture|principles|rules",
        r"skill",
    ]

    result = ""
    used = set()
    for pattern in priority_patterns:
        for heading, content in sections:
            if heading in used:
                continue
            import re
            if re.search(pattern, heading, re.IGNORECASE):
                section_text = f"\n## {heading}\n{content}\n"
                if len(result) + len(section_text) > max_chars:
                    # Truncate this section to fit
                    remaining = max_chars - len(result) - len(f"\n## {heading}\n") - 20
                    if remaining > 100:
                        result += f"\n## {heading}\n{content[:remaining]}...\n"
                    break
                result += section_text
                used.add(heading)
        if len(result) >= max_chars:
            break

    return result.strip()


def filter_skills_for_agent(all_skills: list[Path], agent_keywords: dict) -> list[Path]:
    """Return only skills relevant to this agent + universal skills.

    Matches skill filename against agent keywords and universal set.
    """
    UNIVERSAL = {
        "coding", "testing", "debugging", "git", "security", "audit",
        "performance", "research", "clean-architecture",
        "quality-standards", "agent-patterns",
    }

    agent_kw_set = set(agent_keywords.get("keywords", []))
    agent_text_lower = " ".join(agent_keywords.get("keywords", []))

    filtered = []
    for skill_path in all_skills:
        stem = skill_path.stem.lower()
        # Always include universal skills
        if stem in UNIVERSAL:
            filtered.append(skill_path)
            continue
        # Include if skill name appears in agent keywords
        if stem in agent_kw_set or stem.replace("-", " ") in agent_text_lower:
            filtered.append(skill_path)
            continue
        # Include if any agent keyword appears in skill name
        for kw in agent_kw_set:
            if kw in stem:
                filtered.append(skill_path)
                break

    return filtered


def generate_agent_md(name: str, description: str, project_name: str) -> str:
    """Generate an agent .md file from a user-provided description.

    This is for when users say "I need a soil scientist agent" —
    we generate the skeleton they can refine.
    """
    # Clean up name for display
    display_name = name.replace("-", " ").replace("_", " ").title()

    return f"""# {display_name}

You are the {display_name.lower()} for {project_name}. {description}

## Your responsibility

You own all tasks related to: {description.lower().rstrip('.')}

## Expertise

- {description}

## Protocols

### Core Workflow
**Trigger**: When a task matches your domain.

1. Read the relevant source files before making changes
2. Follow TDD — write failing tests first, then implement
3. Keep functions pure where possible (data in, results out)
4. Verify all tests pass before committing
5. Log what you learned to knowledge.md
"""
