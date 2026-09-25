"""Opportunity scanner — spot what's missing in projects.

Analyzes project memory files (backlog, done, north star) and generates
EARS-formatted backlog tasks for gaps the agency should address.
"""
import re
from datetime import date, timedelta
from pathlib import Path


def _parse_date(text: str) -> date | None:
    """Extract a YYYY-MM-DD date from text, or None."""
    m = re.search(r"(\d{4}-\d{2}-\d{2})", text)
    if m:
        try:
            return date.fromisoformat(m.group(1))
        except ValueError:
            pass
    return None


def _read_safe(path: Path) -> str:
    """Read file text, returning empty string if missing."""
    if path.exists():
        try:
            return path.read_text(encoding="utf-8")
        except Exception:
            return ""
    return ""


def _detect_stale_backlog(
    backlog_path: Path, *, today: str = "", threshold_days: int = 7
) -> list[dict]:
    """Find backlog items that have been sitting longer than threshold_days.

    Looks for date headers (## YYYY-MM-DD) and task headers (### N. Title).
    Items under a date older than threshold are flagged.
    """
    text = _read_safe(backlog_path)
    if not text.strip() or text.strip() == "# Backlog":
        return []

    today_date = date.fromisoformat(today) if today else date.today()
    cutoff = today_date - timedelta(days=threshold_days)

    opportunities = []
    current_date = None

    for line in text.splitlines():
        # Task headers: ### N. Task title. Checked FIRST so a date embedded in a
        # task title (e.g. "### 5. Fix the 2026-03-15 outage") is not mistaken
        # for a date section header and doesn't corrupt current_date.
        task_match = re.match(r"###\s+\d+\.\s+(.+)", line)
        if task_match:
            if current_date and current_date < cutoff:
                task_name = task_match.group(1).strip()
                days_old = (today_date - current_date).days
                opportunities.append({
                    "trigger": f"When backlog item is stale for {days_old} days",
                    "action": f"Prioritize or remove stale task: {task_name}",
                    "acceptance": "test_stale_items_resolved",
                    "scope": "memory/backlog.md",
                    "category": "stale-backlog",
                })
            continue

        # Date section headers: a whole-line `## YYYY-MM-DD` only (anchored so
        # `### N.` task lines and dates inside titles never match here).
        if re.match(r"##\s+\d{4}-\d{2}-\d{2}\s*$", line.strip()):
            current_date = _parse_date(line)

    return opportunities


def _parse_metrics_table(text: str) -> list[dict]:
    """Parse a markdown metrics table into list of {metric, current, target, trend}."""
    metrics = []
    in_table = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("| Metric"):
            in_table = True
            continue
        if in_table and stripped.startswith("|---"):
            continue
        if in_table and stripped.startswith("|"):
            cols = [c.strip() for c in stripped.split("|")]
            # cols[0] is empty (before first |), cols[-1] may be empty too
            cols = [c for c in cols if c]
            if len(cols) >= 4:
                metrics.append({
                    "metric": cols[0],
                    "current": cols[1],
                    "target": cols[2],
                    "trend": cols[3],
                })
        elif in_table and not stripped.startswith("|"):
            in_table = False
    return metrics


def _detect_north_star_gaps(ns_path: Path, done_path: Path) -> list[dict]:
    """Find North Star metrics that haven't been met yet."""
    ns_text = _read_safe(ns_path)
    if not ns_text.strip():
        return []

    metrics = _parse_metrics_table(ns_text)
    opportunities = []

    for m in metrics:
        trend = m["trend"].upper()
        # Skip metrics already met
        if "TARGET MET" in trend:
            continue
        # This metric still has room — generate an opportunity
        opportunities.append({
            "trigger": f"When {m['metric']} is at {m['current']} vs target {m['target']}",
            "action": f"Advance {m['metric']} toward target ({m['target']})",
            "acceptance": f"test_{_slugify(m['metric'])}_improved",
            "scope": "NORTH_STAR.md",
            "category": "north-star-gap",
        })

    return opportunities


def _slugify(text: str) -> str:
    """Convert text to a test-name-safe slug."""
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def scan_opportunities(
    project_dir: Path, *, today: str = ""
) -> list[dict]:
    """Scan a project for opportunities and return EARS-formatted tasks.

    Args:
        project_dir: Root directory containing .autoagent/
        today: ISO date string for testing (defaults to today)

    Returns:
        List of opportunity dicts with keys: trigger, action, acceptance,
        scope, category
    """
    aa = project_dir / ".autoagent"
    mem = aa / "memory"

    all_opps = []

    # 1. Stale backlog items
    backlog_path = mem / "backlog.md"
    all_opps.extend(_detect_stale_backlog(backlog_path, today=today))

    # 2. North Star gaps
    ns_path = aa / "NORTH_STAR.md"
    done_path = mem / "done.md"
    all_opps.extend(_detect_north_star_gaps(ns_path, done_path))

    return all_opps


def format_opportunity_as_backlog(opp: dict) -> str:
    """Render an opportunity dict into EARS-formatted markdown for backlog.

    Returns a string like:
        ### N. [category] Action text
        - Trigger: When X
        - Acceptance: test_name
        - Scope: files
    """
    title = opp.get("action", "Unnamed opportunity")
    cat = opp.get("category", "opportunity")
    trigger = opp.get("trigger", "")
    acceptance = opp.get("acceptance", "")
    scope = opp.get("scope", "")

    lines = [
        f"### [{cat}] {title}",
        f"- Trigger: {trigger}",
        f"- Acceptance: {acceptance}",
        f"- Scope: {scope}",
    ]
    return "\n".join(lines)
