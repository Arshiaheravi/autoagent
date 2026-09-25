"""Session entropy checker — detects stale state that wastes sessions."""
import os
import re
import time
import glob as globmod


def check_entropy(project_root: str) -> list:
    """Scan project memory for staleness signals. Returns list of issue dicts."""
    issues = []
    memory = os.path.join(project_root, "memory")

    _check_stale_task(memory, issues)
    _check_stale_backlog(memory, issues)
    _check_undated_rules(memory, issues)
    _check_orphaned_tests(project_root, issues)

    return issues


def _check_stale_task(memory: str, issues: list):
    path = os.path.join(memory, "current_task.md")
    if not os.path.exists(path):
        return
    content = open(path).read()
    if "- [ ]" not in content:
        return
    mtime = os.path.getmtime(path)
    age_hours = (time.time() - mtime) / 3600
    if age_hours > 24:
        issues.append({
            "type": "stale_task",
            "message": f"current_task.md has unchecked steps and is >{int(age_hours)}h old (>24h threshold)",
        })


def _check_stale_backlog(memory: str, issues: list):
    path = os.path.join(memory, "backlog.md")
    if not os.path.exists(path):
        return
    mtime = os.path.getmtime(path)
    age_days = (time.time() - mtime) / 86400
    if age_days > 14:
        issues.append({
            "type": "stale_backlog",
            "message": f"backlog.md not modified in {int(age_days)} days (>14 day threshold)",
        })


def _check_undated_rules(memory: str, issues: list):
    path = os.path.join(memory, "knowledge.md")
    if not os.path.exists(path):
        return
    for line in open(path):
        if line.strip().startswith("- RULE:"):
            if not re.search(r"\[\d{4}-\d{2}-\d{2}\]", line):
                issues.append({
                    "type": "undated_rule",
                    "message": f"Rule missing date prefix: {line.strip()[:60]}",
                })


def _check_orphaned_tests(project_root: str, issues: list):
    project_md = os.path.join(project_root, "PROJECT.md")
    if not os.path.exists(project_md):
        return
    content = open(project_md).read()
    test_files_on_disk = [
        os.path.basename(f)
        for f in globmod.glob(os.path.join(project_root, "test_*.py"))
    ]
    for tf in test_files_on_disk:
        if tf not in content:
            issues.append({
                "type": "orphaned_test",
                "message": f"Test file {tf} not in PROJECT.md test command",
            })
