#!/usr/bin/env python3
"""File integrity verification — SHA256 hashes for critical instruction files.

Detects unauthorized modifications to PROMPT.md, PROJECT.md, NORTH_STAR.md,
and skills/*.md during agent work sessions.
"""
import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Dict, List

# Files to protect (relative to .autoagent/ root)
CRITICAL_PATTERNS = ["PROMPT.md", "PROJECT.md", "NORTH_STAR.md"]
CRITICAL_GLOBS = ["skills/*.md"]


def compute_hashes(root: Path) -> Dict[str, str]:
    """Compute SHA256 hashes for all critical files under root.

    Returns dict mapping relative path -> hex digest.
    """
    hashes = {}
    for name in CRITICAL_PATTERNS:
        f = root / name
        if f.exists():
            hashes[name] = _sha256(f)
    for glob in CRITICAL_GLOBS:
        for f in sorted(root.glob(glob)):
            rel = str(f.relative_to(root))
            hashes[rel] = _sha256(f)
    return hashes


def save_baseline(hashes: Dict[str, str], store: Path) -> None:
    """Write baseline hashes to JSON file."""
    store.write_text(json.dumps(hashes, indent=2), encoding="utf-8")


def load_baseline(store: Path) -> Dict[str, str]:
    """Load baseline hashes from JSON file. Returns empty dict if missing."""
    if not store.exists():
        return {}
    try:
        return json.loads(store.read_text(encoding="utf-8"))
    except Exception:
        return {}


def hash_files(files: list) -> Dict[str, str]:
    """Compute SHA256 hashes for a list of Path objects.

    Returns dict mapping str(path) -> hex digest.
    """
    return {str(f): _sha256(f) for f in files if f.exists()}


def verify_hashes(baseline: Dict[str, str], root_or_current) -> List[str]:
    """Compare current file hashes against baseline.

    Args:
        baseline: {path: expected_hash} from a previous compute/hash call.
        root_or_current: Either a Path (root dir for relative paths) or a
            dict of {path: current_hash} for direct comparison.

    Returns list of violation descriptions (empty = all good).
    """
    violations = []
    if isinstance(root_or_current, dict):
        current = root_or_current
        for path, expected in baseline.items():
            if path not in current:
                violations.append(f"DELETED: {Path(path).name}")
            elif current[path] != expected:
                violations.append(f"MODIFIED: {Path(path).name}")
    else:
        root = root_or_current
        for rel_path, expected_hash in baseline.items():
            f = root / rel_path
            if not f.exists():
                violations.append(f"DELETED: {rel_path}")
            else:
                actual = _sha256(f)
                if actual != expected_hash:
                    violations.append(f"MODIFIED: {rel_path}")
    return violations


def snapshot_critical(ctx) -> Dict[str, str]:
    """Snapshot all critical instruction files for a project context.

    Returns baseline hash dict and saves it to .integrity.json.
    """
    critical = [ctx.prompt_file, ctx.project_file, ctx.north_star_file]
    for sd in ctx.skills_dirs():
        if sd.exists():
            critical.extend(sorted(sd.glob("*.md")))
    baseline = hash_files([f for f in critical if f.exists()])
    store = ctx.memory_dir / ".integrity.json"
    save_baseline(baseline, store)
    return baseline


def check_integrity(baseline: Dict[str, str]) -> List[str]:
    """Re-hash the files in baseline and return any violations."""
    current = {p: _sha256(Path(p)) for p in baseline if Path(p).exists()}
    missing = [p for p in baseline if not Path(p).exists()]
    violations = [f"DELETED: {Path(p).name}" for p in missing]
    for p, expected in baseline.items():
        if p in current and current[p] != expected:
            violations.append(f"MODIFIED: {Path(p).name}")
    return violations


def _get_critical_files(root: Path) -> List[Path]:
    """Collect all critical instruction files under root."""
    files = []
    for name in CRITICAL_PATTERNS:
        f = root / name
        if f.exists():
            files.append(f)
    for glob in CRITICAL_GLOBS:
        files.extend(sorted(root.glob(glob)))
    return files


def lock_instruction_files(root: Path) -> None:
    """Remove write permission from critical instruction files."""
    for f in _get_critical_files(root):
        mode = f.stat().st_mode
        f.chmod(mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))


def unlock_instruction_files(root: Path) -> None:
    """Restore owner write permission on critical instruction files."""
    for f in _get_critical_files(root):
        mode = f.stat().st_mode
        f.chmod(mode | stat.S_IWUSR)


def lock_ctx_instruction_files(ctx) -> None:
    """Remove write permission from all critical instruction files for a project."""
    files = [ctx.prompt_file, ctx.project_file, ctx.north_star_file]
    for sd in ctx.skills_dirs():
        if sd.exists():
            files.extend(sorted(sd.glob("*.md")))
    for f in files:
        if f.exists():
            mode = f.stat().st_mode
            f.chmod(mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))


def unlock_ctx_instruction_files(ctx) -> None:
    """Restore owner write permission on all critical instruction files for a project."""
    files = [ctx.prompt_file, ctx.project_file, ctx.north_star_file]
    for sd in ctx.skills_dirs():
        if sd.exists():
            files.extend(sorted(sd.glob("*.md")))
    for f in files:
        if f.exists():
            mode = f.stat().st_mode
            f.chmod(mode | stat.S_IWUSR)


def _sha256(path: Path) -> str:
    """Compute SHA256 hex digest of a file."""
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()
