#!/usr/bin/env python3
"""Project registry — CRUD for managing multiple projects."""
import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from models import DEFAULT_MODEL
from tenant import current_tenant

# Tenant SSoT: root, control DB, and scoping stay aligned. Honours AUTOAGENT_HOME.
AGENCY_HOME = current_tenant().data_root


@dataclass
class ProjectContext:
    """All paths and config for one project. No globals, no module-level state."""
    name: str
    project_root: Path          # e.g., /path/to/myapp
    agency_home: Path           # ~/.autoagent
    config: dict = field(default_factory=dict)

    @property
    def project_home(self) -> Path:
        return self.agency_home / "projects" / self.name

    # ── Templates (shared) ──
    @property
    def prompt_file(self) -> Path:
        return self.agency_home / "templates" / "PROMPT.md"

    @property
    def meta_dir(self) -> Path:
        return self.agency_home / "templates" / "meta"

    # ── Project-specific ──
    @property
    def project_file(self) -> Path:
        return self.project_home / "PROJECT.md"

    @property
    def north_star_file(self) -> Path:
        return self.project_home / "NORTH_STAR.md"

    @property
    def memory_dir(self) -> Path:
        return self.project_home / "memory"

    @property
    def sessions_file(self) -> Path:
        return self.project_home / "sessions.json"

    @property
    def budget_file(self) -> Path:
        return self.project_home / "daily_budget.json"

    @property
    def weekly_sessions_file(self) -> Path:
        return self.project_home / "weekly_sessions.json"

    @property
    def counter_file(self) -> Path:
        return self.project_home / "session_counter.json"

    @property
    def agents_dir(self) -> Path:
        return self.project_home / "agents"

    @property
    def events_file(self) -> Path:
        return self.project_home / "live_events.jsonl"

    @property
    def dashboard_file(self) -> Path:
        return self.project_home / "dashboard.html"

    def skills_dirs(self) -> list[Path]:
        """Shared skills first, project-specific skills overlay."""
        dirs = [self.agency_home / "skills"]
        project_skills = self.project_home / "skills"
        if project_skills.exists():
            dirs.append(project_skills)
        return dirs

    def all_skills(self) -> list[Path]:
        """Merged skill files — project-specific overrides shared if same name."""
        try:
            from org_model import visible_skill_paths
            return visible_skill_paths(self)
        except Exception:
            pass
        # Fail CLOSED: if scoping can't be computed, still hide shared
        # project-domain skills rather than exposing every client's skills.
        try:
            from org_model import hidden_project_domain_skills
            hidden = hidden_project_domain_skills(self)
        except Exception:
            hidden = set()
        shared_dir = self.agency_home / "skills"
        seen = {}
        for d in self.skills_dirs():
            if d.exists():
                for p in d.glob("*.md"):
                    if d == shared_dir and p.stem in hidden:
                        continue
                    seen[p.name] = p
        return sorted(seen.values(), key=lambda p: p.name)

    def symlink_path(self) -> Path:
        """Where the symlink lives inside the project repo."""
        return self.project_root / ".autoagent"

    def ensure_dirs(self):
        """Create all required directories."""
        self.project_home.mkdir(parents=True, exist_ok=True)
        self.memory_dir.mkdir(exist_ok=True)
        (self.project_home / "skills").mkdir(exist_ok=True)
        self.agents_dir.mkdir(exist_ok=True)

    def ensure_symlink(self):
        """Create symlink from project_root/.autoagent → project_home."""
        link = self.symlink_path()
        if link.is_symlink():
            if link.is_symlink() and link.resolve() == self.project_home.resolve():
                return  # already correct
            link.unlink()
        elif link.exists():
            raise FileExistsError(
                f"Refusing to replace existing non-symlink .autoagent at {link}. "
                "Move it aside before registering this project."
            )
        link.symlink_to(self.project_home)
        # Add to .gitignore if not already there
        gitignore = self.project_root / ".gitignore"
        marker = ".autoagent"
        if gitignore.exists():
            content = gitignore.read_text()
            if marker not in {line.strip() for line in content.splitlines()}:
                with open(gitignore, "a") as f:
                    f.write(f"\n{marker}\n")
        else:
            gitignore.write_text(f"{marker}\n")


def _agency_file() -> Path:
    return AGENCY_HOME / "agency.json"


def _load_agency() -> dict:
    f = _agency_file()
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    return {"projects": {}, "defaults": {"model": DEFAULT_MODEL, "session_max_turns": 50}}


def _save_agency(data: dict):
    _agency_file().parent.mkdir(parents=True, exist_ok=True)
    _agency_file().write_text(json.dumps(data, indent=2), encoding="utf-8")


def register(name: str, project_root: str | Path, **overrides) -> ProjectContext:
    """Register a new project with the agency."""
    project_root = Path(project_root).resolve()
    if not project_root.exists():
        raise FileNotFoundError(f"Project root does not exist: {project_root}")

    agency = _load_agency()
    existing = agency["projects"].get(name)
    if existing and Path(existing["path"]).resolve() != project_root:
        raise ValueError(
            f"'{name}' already registered to {existing['path']}. "
            f"Re-registering it to {project_root} would repoint its home + symlink and "
            f"bleed memory/budget/sessions across repos. "
            f"Use a different name, or `autoagent remove {name}` first."
        )
    agency["projects"][name] = {
        "path": str(project_root),
        "created": __import__("datetime").date.today().isoformat(),
        **overrides,
    }
    _save_agency(agency)

    ctx = get(name)
    ctx.ensure_dirs()
    ctx.ensure_symlink()
    return ctx


def get(name: str) -> ProjectContext:
    """Load a project by name → ProjectContext."""
    agency = _load_agency()
    if name not in agency["projects"]:
        raise KeyError(f"Project '{name}' not registered. Run: autoagent list")

    proj = agency["projects"][name]
    # Merge defaults + project-specific config
    config = {**agency.get("defaults", {})}

    # Load project.json if it exists
    project_home = AGENCY_HOME / "projects" / name
    pj = project_home / "project.json"
    if pj.exists():
        try:
            config.update(json.loads(pj.read_text(encoding="utf-8")))
        except Exception:
            pass

    return ProjectContext(
        name=name,
        project_root=Path(proj["path"]),
        agency_home=AGENCY_HOME,
        config=config,
    )


def list_projects() -> list[dict]:
    """Return list of registered projects with basic info."""
    agency = _load_agency()
    result = []
    for name, info in agency.get("projects", {}).items():
        ctx = get(name)
        session_num = 0
        if ctx.counter_file.exists():
            try:
                session_num = json.loads(ctx.counter_file.read_text()).get("count", 0)
            except Exception:
                pass
        result.append({
            "name": name,
            "path": info["path"],
            "created": info.get("created", "unknown"),
            "sessions": session_num,
        })
    return result


def remove(name: str):
    """Unregister a project (does NOT delete files)."""
    agency = _load_agency()
    agency["projects"].pop(name, None)
    _save_agency(agency)


# ── Re-exports from registry_utils (backward compatibility) ──
from registry_utils import promote_skill, extract_universal_rules, validate_project  # noqa: F401


def migrate_v1(v1_dir: str | Path, name: Optional[str] = None, project_root: Optional[str | Path] = None) -> ProjectContext:
    """Import a V1 autoagent directory into the V2 agency structure."""
    v1 = Path(v1_dir).resolve()
    if not (v1 / "run.py").exists():
        raise FileNotFoundError(f"Not a V1 autoagent directory: {v1}")

    # V1 might be inside the project or standalone — use explicit project_root if given
    if project_root is not None:
        project_root = Path(project_root).resolve()
    else:
        project_root = v1.parent  # V1 autoagent/ lives inside the project
    if name is None:
        name = project_root.name

    ctx = register(name, project_root)

    # Copy project-specific files
    for fname in ["PROJECT.md", "NORTH_STAR.md", "sessions.json"]:
        src = v1 / fname
        if src.exists():
            shutil.copy2(src, ctx.project_home / fname)

    # Copy memory
    v1_memory = v1 / "memory"
    if v1_memory.exists():
        for f in v1_memory.glob("*"):
            shutil.copy2(f, ctx.memory_dir / f.name)

    # Separate universal vs domain skills
    universal_skills = {p.name for p in (AGENCY_HOME / "skills").glob("*.md")}
    v1_skills = v1 / "skills"
    if v1_skills.exists():
        project_skills = ctx.project_home / "skills"
        for f in v1_skills.glob("*.md"):
            if f.name not in universal_skills:
                shutil.copy2(f, project_skills / f.name)

    # Copy agent definitions if they exist in the project's .claude/agents/
    project_agents = project_root / ".claude" / "agents"
    if project_agents.exists():
        for f in project_agents.glob("*.md"):
            shutil.copy2(f, ctx.agents_dir / f.name)

    # Copy config
    v1_config = v1 / "config.json"
    if v1_config.exists():
        shutil.copy2(v1_config, ctx.project_home / "project.json")

    print(f"  Migrated '{name}' from {v1}")
    print(f"    → {ctx.project_home}")
    return ctx
