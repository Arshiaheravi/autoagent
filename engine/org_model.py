#!/usr/bin/env python3
"""Department and agent organization model for the agency."""
import json
import os
import re
from pathlib import Path
from typing import Any

from registry import AGENCY_HOME


_DUPLICATE_TEMPLATE_RE = re.compile(r".+\s+\d+\.md$")


def _home(agency_home: Path | str | None = None) -> Path:
    if agency_home is not None:
        return Path(agency_home)
    return Path(os.environ.get("AUTOAGENT_HOME", AGENCY_HOME))


def manifest_path(agency_home: Path | str | None = None) -> Path:
    """Return the department manifest path for an agency home."""
    return _home(agency_home) / "templates" / "departments.json"


def load_department_manifest(agency_home: Path | str | None = None) -> dict[str, Any]:
    """Load templates/departments.json, returning {} when absent or invalid."""
    path = manifest_path(agency_home)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def is_duplicate_template(path: Path) -> bool:
    """Return True for Finder-style duplicate templates such as 'architect 2.md'."""
    return bool(_DUPLICATE_TEMPLATE_RE.fullmatch(path.name))


def _agent_name(agent: Any) -> str:
    if isinstance(agent, str):
        return agent
    if isinstance(agent, dict):
        return str(agent.get("name", ""))
    return ""


def _agent_scope(agent: Any) -> str:
    if isinstance(agent, dict):
        return str(agent.get("scope", "universal"))
    return "universal"


def _agent_has_template(agent: Any) -> bool:
    if isinstance(agent, dict):
        return bool(agent.get("template", _agent_scope(agent) == "universal"))
    return True


def universal_agent_names(agency_home: Path | str | None = None) -> list[str]:
    """Return universal agent template names from the manifest or template scan."""
    data = load_department_manifest(agency_home)
    if data:
        names: list[str] = []
        for department in data.get("departments", []):
            for agent in department.get("agents", []):
                name = _agent_name(agent)
                if name and _agent_scope(agent) == "universal" and _agent_has_template(agent):
                    names.append(name)
        return list(dict.fromkeys(names))

    templates_dir = _home(agency_home) / "templates" / "agents"
    if not templates_dir.exists():
        return []
    return [
        f.stem for f in sorted(templates_dir.glob("*.md"))
        if f.name != "orchestrator.md" and not is_duplicate_template(f)
    ]


def universal_agent_template_paths(agency_home: Path | str | None = None) -> list[Path]:
    """Return existing universal agent template paths in manifest order."""
    home = _home(agency_home)
    templates_dir = home / "templates" / "agents"
    if not templates_dir.exists():
        return []

    names = universal_agent_names(home)
    if names:
        paths = []
        for name in names:
            path = templates_dir / f"{name}.md"
            if path.exists():
                paths.append(path)
        return paths

    return [
        f for f in sorted(templates_dir.glob("*.md"))
        if f.name != "orchestrator.md" and not is_duplicate_template(f)
    ]


def _manifest_skills(data: dict[str, Any]) -> set[str]:
    skills: set[str] = set()
    for department in data.get("departments", []):
        for skill in department.get("skills", []):
            if isinstance(skill, str):
                skills.add(skill)
    scopes = data.get("skill_scopes", {})
    if isinstance(scopes, dict):
        for value in scopes.values():
            if isinstance(value, list):
                skills.update(str(v) for v in value)
            elif isinstance(value, dict):
                for items in value.values():
                    if isinstance(items, list):
                        skills.update(str(v) for v in items)
    return skills


def project_domain_skill_names(agency_home: Path | str | None = None) -> set[str]:
    """Return shared skill names that are project-domain scoped by manifest."""
    data = load_department_manifest(agency_home)
    scopes = data.get("skill_scopes", {}) if data else {}
    if not isinstance(scopes, dict):
        return set()
    return {str(v) for v in scopes.get("project_domain", [])}


def _project_domain_enabled(ctx: Any) -> bool:
    config = getattr(ctx, "config", {}) or {}
    if config.get("include_project_domain_skills") is True:
        return True
    scopes = config.get("skill_scopes") or config.get("enabled_skill_scopes") or []
    if isinstance(scopes, str):
        scopes = [scopes]
    return "project_domain" in scopes


def _project_domain_allowlist(ctx: Any) -> set[str]:
    config = getattr(ctx, "config", {}) or {}
    values = config.get("project_domain_skills") or config.get("domain_skills") or []
    if isinstance(values, str):
        values = [values]
    return {str(v).removesuffix(".md") for v in values}


def visible_skill_paths(ctx: Any) -> list[Path]:
    """Return skill files visible to a project after manifest scoping.

    Shared project-domain skills are hidden by default. Project-local skills
    always remain visible and override shared skills with the same filename.
    """
    shared_dir = Path(ctx.agency_home) / "skills"
    project_skills = Path(ctx.project_home) / "skills"
    project_domain = project_domain_skill_names(ctx.agency_home)
    include_project_domain = _project_domain_enabled(ctx)
    allowlist = _project_domain_allowlist(ctx)

    seen: dict[str, Path] = {}
    if shared_dir.exists():
        for path in shared_dir.glob("*.md"):
            stem = path.stem
            if stem in project_domain and not include_project_domain and stem not in allowlist:
                continue
            seen[path.name] = path

    if project_skills.exists():
        for path in project_skills.glob("*.md"):
            seen[path.name] = path

    return sorted(seen.values(), key=lambda p: p.name)


def project_domain_enabled(ctx: Any) -> bool:
    """True if this project has opted into project-domain skills."""
    return _project_domain_enabled(ctx)


def hidden_project_domain_skills(ctx: Any) -> set[str]:
    """Skill stems this project must NOT see (project-domain, not enabled here).

    Single source of truth for which shared skills stay hidden from a project, so
    template sync and the registry fallback scope identically and one client's
    domain skills never leak into another's project-local skills dir.
    """
    if _project_domain_enabled(ctx):
        return set()
    agency_home = getattr(ctx, "agency_home", None)
    return project_domain_skill_names(agency_home) - _project_domain_allowlist(ctx)


def build_org_report(agency_home: Path | str | None = None) -> dict[str, Any]:
    """Build a read-only organization report for CLI and tests."""
    home = _home(agency_home)
    data = load_department_manifest(home)
    templates_dir = home / "templates" / "agents"
    skills_dir = home / "skills"

    template_files = sorted(templates_dir.glob("*.md")) if templates_dir.exists() else []
    template_names = {
        f.stem for f in template_files
        if f.name != "orchestrator.md" and not is_duplicate_template(f)
    }
    duplicate_templates = [f.name for f in template_files if is_duplicate_template(f)]
    universal_names = universal_agent_names(home)
    missing_agents = [name for name in universal_names if name not in template_names]
    unmanaged_templates = sorted(template_names - set(universal_names))

    skill_files = {f.stem for f in skills_dir.glob("*.md")} if skills_dir.exists() else set()
    missing_skills = sorted(_manifest_skills(data) - skill_files) if data else []
    project_domain_skills = []
    scopes = data.get("skill_scopes", {}) if data else {}
    if isinstance(scopes, dict):
        for skill in scopes.get("project_domain", []):
            if skill in skill_files:
                project_domain_skills.append(skill)
    visible_shared_skills = sorted(skill_files - set(project_domain_skills))

    departments = []
    for department in data.get("departments", []):
        agents = []
        for agent in department.get("agents", []):
            name = _agent_name(agent)
            scope = _agent_scope(agent)
            has_template = name in template_names
            agents.append({
                "name": name,
                "scope": scope,
                "template": _agent_has_template(agent),
                "present": has_template or scope in ("generated", "runtime"),
            })
        departments.append({
            "id": department.get("id", ""),
            "name": department.get("name", department.get("id", "")),
            "purpose": department.get("purpose", ""),
            "agents": agents,
            "skills": department.get("skills", []),
            "loops": department.get("loops", []),
        })

    errors = []
    notes = []
    for name in missing_agents:
        errors.append(f"Missing universal agent template: {name}.md")
    for name in duplicate_templates:
        errors.append(f"Duplicate-looking agent template should not ship: {name}")
    for name in unmanaged_templates:
        errors.append(f"Agent template is not assigned to a department: {name}.md")
    for name in missing_skills:
        errors.append(f"Manifest references missing skill: {name}.md")
    for name in project_domain_skills:
        notes.append(f"Project-domain shared skill hidden by default: {name}.md")

    return {
        "manifest": str(manifest_path(home)),
        "manifest_found": bool(data),
        "departments": departments,
        "universal_agents": universal_names,
        "missing_agent_templates": missing_agents,
        "duplicate_agent_templates": duplicate_templates,
        "unmanaged_agent_templates": unmanaged_templates,
        "missing_skills": missing_skills,
        "project_domain_skills_in_shared": project_domain_skills,
        "visible_shared_skills": visible_shared_skills,
        "candidate_agents": data.get("candidate_agents", []) if data else [],
        "errors": errors,
        "notes": notes,
        "warnings": errors,
        "strict_ok": not errors,
    }


def format_org_report(report: dict[str, Any]) -> str:
    """Format an org report for terminal output."""
    lines = [
        "",
        "  Agency Organization",
        "  " + "-" * 58,
    ]
    if not report.get("manifest_found"):
        lines.append("  No departments.json manifest found; using template scan fallback.")
    lines.append(f"  Universal agent templates: {len(report.get('universal_agents', []))}")
    lines.append("")

    for department in report.get("departments", []):
        lines.append(f"  {department['name']}")
        if department.get("purpose"):
            lines.append(f"    {department['purpose']}")
        agent_bits = []
        for agent in department.get("agents", []):
            marker = "ok" if agent.get("present") else "missing"
            label = agent["name"]
            if agent.get("scope") != "universal":
                label = f"{label} ({agent['scope']})"
            agent_bits.append(f"{label}:{marker}")
        if agent_bits:
            lines.append(f"    Agents: {', '.join(agent_bits)}")
        if department.get("loops"):
            lines.append(f"    Loops: {', '.join(department['loops'])}")
        lines.append("")

    errors = report.get("errors", report.get("warnings", []))
    if errors:
        lines.append("  Errors")
        for error in errors:
            lines.append(f"    - {error}")
        lines.append("")

    notes = report.get("notes", [])
    if notes:
        lines.append("  Notes")
        for note in notes:
            lines.append(f"    - {note}")
        lines.append("")

    candidates = report.get("candidate_agents", [])
    if candidates:
        lines.append("  Candidate Universal Agents")
        for candidate in candidates:
            name = candidate.get("name", "")
            department = candidate.get("department", "")
            reason = candidate.get("reason", "")
            lines.append(f"    - {name} ({department}): {reason}")
        lines.append("")

    return "\n".join(lines)
