#!/usr/bin/env python3
"""Initialize the AutoAgent Agency home directory."""
import json
import shutil
from pathlib import Path

from models import DEFAULT_MODEL


# Source of truth for bundled assets — relative to this file's location in the repo
REPO_ROOT = Path(__file__).resolve().parent.parent


def init(agency_home: Path):
    """Create or update the agency home directory with templates and skills.

    Safe to run multiple times — preserves existing data (agency.json, projects/).
    """
    agency_home = Path(agency_home)

    # Create directory structure
    for d in ["engine", "templates/agents", "templates/meta", "templates/examples",
              "skills", "projects", "dashboard"]:
        (agency_home / d).mkdir(parents=True, exist_ok=True)

    # agency.json — create only if missing (preserves registered projects)
    agency_file = agency_home / "agency.json"
    if not agency_file.exists():
        agency_file.write_text(json.dumps({
            "projects": {},
            "defaults": {"model": DEFAULT_MODEL, "session_max_turns": 50}
        }, indent=2), encoding="utf-8")

    # Copy managed engine files
    engine_src = REPO_ROOT / "engine"
    _sync_engine(engine_src, agency_home / "engine")

    # Copy templates (don't overwrite user customizations)
    _sync_dir(REPO_ROOT / "templates", agency_home / "templates")

    # Copy skills (don't overwrite user customizations)
    _sync_dir(REPO_ROOT / "skills", agency_home / "skills")

    # Copy shell wrapper
    wrapper = agency_home / "autoagent"
    wrapper.write_text(
        f"#!/bin/bash\npython3 {agency_home}/engine/cli.py \"$@\"\n",
        encoding="utf-8"
    )
    wrapper.chmod(0o755)

    print(f"  [AutoAgent Agency] Initialized at {agency_home}")
    print(f"  Run: {agency_home}/autoagent --help")


def _sync_dir(src: Path, dst: Path):
    """Copy files from src to dst, creating subdirs. Don't overwrite existing files."""
    if not src.exists():
        return
    for f in src.rglob("*"):
        if f.is_file():
            rel = f.relative_to(src)
            target = dst / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                shutil.copy2(f, target)


def _sync_engine(src: Path, dst: Path):
    """Copy runtime engine Python files recursively, excluding tests/caches."""
    if not src.exists():
        return
    dst.mkdir(parents=True, exist_ok=True)

    # If a top-level module became a package, remove the stale module so the
    # installed runtime cannot accidentally import old code.
    package_module_conflicts = set()
    for init_file in src.rglob("__init__.py"):
        package_rel = init_file.parent.relative_to(src)
        if not package_rel.parts:
            continue
        conflict_rel = package_rel.parent / f"{package_rel.name}.py"
        package_module_conflicts.add(conflict_rel)
        conflict = dst / conflict_rel
        if conflict.is_file():
            conflict.unlink()

    for f in src.rglob("*.py"):
        rel = f.relative_to(src)
        if rel in package_module_conflicts or _skip_engine_file(rel):
            continue
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, target)


def _skip_engine_file(rel: Path) -> bool:
    """Return True for files that should not be deployed to agency home."""
    return (
        rel.name.startswith("test_")
        or rel.name == "conftest.py"
        or "__pycache__" in rel.parts
    )
