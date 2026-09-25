#!/usr/bin/env python3
"""Cleanup crew checks for generated junk and source ambiguity."""
import json
import re
import shutil
import subprocess
from pathlib import Path


GENERATED_DIRS = {"__pycache__", ".pytest_cache"}
GENERATED_SUFFIXES = {".pyc", ".pyo"}
DUPLICATE_RE = re.compile(r"^(.+) \d+(\.[^.]+)$")


def scan(root: Path) -> dict:
    """Return cleanup findings for a project/repo root."""
    root = Path(root).resolve()
    findings = {
        "root": str(root),
        "generated": [],
        "duplicates": [],
        "module_package_conflicts": [],
        "agent_worktrees": _agent_worktrees(root),
    }
    if not root.exists():
        findings["error"] = f"path does not exist: {root}"
        return findings

    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if path.is_dir() and path.name in GENERATED_DIRS:
            findings["generated"].append(str(rel))
            continue
        if path.is_file() and path.suffix in GENERATED_SUFFIXES:
            findings["generated"].append(str(rel))
        if path.is_file() and DUPLICATE_RE.match(path.name):
            findings["duplicates"].append(str(rel))

    for py_file in sorted(root.rglob("*.py")):
        if "__pycache__" in py_file.parts:
            continue
        package_init = py_file.with_suffix("") / "__init__.py"
        if package_init.exists():
            findings["module_package_conflicts"].append(str(py_file.relative_to(root)))

    return findings


def apply_generated_cleanup(root: Path) -> list[str]:
    """Remove generated cleanup targets only. Leaves source-like files alone."""
    root = Path(root).resolve()
    removed = []
    for rel in scan(root).get("generated", []):
        path = root / rel
        try:
            if path.is_dir():
                shutil.rmtree(path)
            elif path.exists():
                path.unlink()
            removed.append(rel)
        except OSError:
            continue
    return removed


def format_report(findings: dict, removed: list[str] | None = None) -> str:
    """Format cleanup findings for CLI output."""
    removed = removed or []
    lines = [f"\n  Engineering Cleanup Crew - {findings.get('root', '')}"]
    if findings.get("error"):
        lines.append(f"  Error: {findings['error']}")
        return "\n".join(lines)

    generated = findings.get("generated", [])
    duplicates = findings.get("duplicates", [])
    conflicts = findings.get("module_package_conflicts", [])
    worktrees = findings.get("agent_worktrees", [])

    lines.append(f"  Generated artifacts: {len(generated)}")
    lines.append(f"  Duplicate-looking files: {len(duplicates)}")
    lines.append(f"  Module/package conflicts: {len(conflicts)}")
    lines.append(f"  Agent worktrees: {len(worktrees)}")
    if removed:
        lines.append(f"  Removed generated artifacts: {len(removed)}")

    for label, values in (
        ("generated", generated[:8]),
        ("duplicates", duplicates[:8]),
        ("module/package", conflicts[:8]),
        ("worktree", [w.get("path", "") for w in worktrees[:8]]),
    ):
        for value in values:
            lines.append(f"    - {label}: {value}")

    if generated and not removed:
        lines.append("  Run with --apply to remove generated artifacts only.")
    if duplicates or conflicts or worktrees:
        lines.append("  Review non-generated findings manually; cleanup crew will not delete source-like files.")
    return "\n".join(lines)


def run_cleanup_cli(args: list[str], default_root: Path | None = None) -> int:
    """CLI implementation for autoagent cleanup."""
    default_root = default_root or Path.cwd()
    apply = "--apply" in args
    as_json = "--json" in args
    root = _root_from_args(args, default_root)

    findings = scan(root)
    removed = apply_generated_cleanup(root) if apply and not findings.get("error") else []
    if removed:
        findings = scan(root)

    if as_json:
        print(json.dumps({"findings": findings, "removed": removed}, indent=2))
    else:
        print(format_report(findings, removed=removed))
    return 1 if findings.get("error") else 0


def _root_from_args(args: list[str], default_root: Path) -> Path:
    if "--path" in args:
        idx = args.index("--path")
        if idx + 1 < len(args):
            return Path(args[idx + 1])
    positional = [a for a in args if not a.startswith("--")]
    if positional:
        try:
            from registry import get
            return get(positional[0]).project_root
        except Exception:
            return Path(positional[0])
    return default_root


def _agent_worktrees(root: Path) -> list[dict]:
    try:
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception:
        return []
    worktrees = []
    current = {}
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            if current and "agent/" in current.get("branch", ""):
                worktrees.append(current)
            current = {"path": line.split(" ", 1)[1]}
        elif line.startswith("branch "):
            current["branch"] = line.split(" ", 1)[1]
        elif not line:
            if current and "agent/" in current.get("branch", ""):
                worktrees.append(current)
            current = {}
    if current and "agent/" in current.get("branch", ""):
        worktrees.append(current)
    return worktrees
