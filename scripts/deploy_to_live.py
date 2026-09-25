#!/usr/bin/env python3
"""Deploy the repo's engine + templates to the live agency home (~/.autoagent).

The engine actually RUNS from ~/.autoagent, not the repo. Fixes committed to the
repo do nothing until synced here — and the per-tenant PROMPT.md copies under
~/.autoagent/projects/<name>/ are frozen (copy-if-absent), so a template fix
never reaches an already-onboarded tenant without an explicit refresh.

This script closes that gap safely:
  1. Timestamped backup of the live engine/ and templates/ (never deletes).
  2. Sync repo engine/ and templates/ into the live home.
  3. Force-refresh each tenant's projects/<name>/PROMPT.md from the new template
     (backing up the old one first).
  4. Print a summary.

DRY-RUN by default — prints what WOULD change and touches nothing. Re-run with
--apply once the plan looks right. Review `templates/PROMPT.md` (freshly adopted
from the hardened satellites) before applying, since --apply overwrites the
shipped prompt for every tenant.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

_IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache")


def _log(msg: str) -> None:
    print(msg)


def _copy_tree(src: Path, dst: Path, apply: bool) -> None:
    if not apply:
        _log(f"  would sync {src} → {dst}")
        return
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=_IGNORE)
    _log(f"  synced {src.name}/ → {dst}")


def deploy(repo: Path, live_home: Path, apply: bool, refresh_projects: bool,
           stamp: str) -> dict:
    """Perform (or dry-run) the deployment. `stamp` names the backups."""
    summary: dict = {"backups": [], "synced": [], "prompts_refreshed": [], "apply": apply}

    live_engine = live_home / "engine"
    live_templates = live_home / "templates"
    repo_engine = repo / "engine"
    repo_templates = repo / "templates"

    if not repo_engine.is_dir() or not repo_templates.is_dir():
        raise FileNotFoundError(f"repo engine/ or templates/ missing under {repo}")

    _log(f"Deploy {'(APPLY)' if apply else '(dry-run)'}: {repo} → {live_home}")

    # 1. Backups
    for live_dir in (live_engine, live_templates):
        if live_dir.exists():
            backup = live_dir.with_name(f"{live_dir.name}.backup-{stamp}")
            summary["backups"].append(str(backup))
            if apply:
                shutil.copytree(live_dir, backup, ignore=_IGNORE)
                _log(f"  backed up {live_dir.name}/ → {backup.name}")
            else:
                _log(f"  would back up {live_dir.name}/ → {backup.name}")

    # 2. Sync engine + templates
    _copy_tree(repo_engine, live_engine, apply)
    summary["synced"].append("engine")
    _copy_tree(repo_templates, live_templates, apply)
    summary["synced"].append("templates")

    # 3. Force-refresh frozen tenant prompts from the new template
    new_prompt = repo_templates / "PROMPT.md"
    projects_dir = live_home / "projects"
    if refresh_projects and new_prompt.exists() and projects_dir.is_dir():
        for proj in sorted(p for p in projects_dir.iterdir() if p.is_dir()):
            tenant_prompt = proj / "PROMPT.md"
            if not tenant_prompt.exists():
                continue  # created on next session from the template; nothing frozen
            summary["prompts_refreshed"].append(proj.name)
            if apply:
                shutil.copy2(tenant_prompt, tenant_prompt.with_name(f"PROMPT.md.backup-{stamp}"))
                shutil.copy2(new_prompt, tenant_prompt)
                _log(f"  refreshed prompt for tenant '{proj.name}' (old → PROMPT.md.backup-{stamp})")
            else:
                _log(f"  would refresh prompt for tenant '{proj.name}'")

    return summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", type=Path, default=Path(__file__).resolve().parent.parent)
    ap.add_argument("--live-home", type=Path, default=Path.home() / ".autoagent")
    ap.add_argument("--apply", action="store_true", help="perform the deploy (default: dry-run)")
    ap.add_argument("--skip-projects", action="store_true",
                    help="do not refresh the per-tenant PROMPT.md copies")
    args = ap.parse_args(argv)

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    summary = deploy(args.repo, args.live_home, apply=args.apply,
                     refresh_projects=not args.skip_projects, stamp=stamp)

    _log("")
    _log(f"Summary: synced {summary['synced']}, "
         f"{len(summary['prompts_refreshed'])} tenant prompt(s) "
         f"{'refreshed' if args.apply else 'to refresh'}, "
         f"{len(summary['backups'])} backup(s).")
    if not args.apply:
        _log("Dry-run only. Re-run with --apply to deploy.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
