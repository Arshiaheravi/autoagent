#!/usr/bin/env python3
"""Memory eviction — keep agent context relevant by archiving stale entries."""
import datetime
import re
from pathlib import Path

# Matches RULE: [YYYY-MM-DD] or ### Session #N Reflexion — YYYY-MM-DD
_DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")

# Section headers in knowledge.md: RULE: lines or ### Session blocks
_SECTION_RE = re.compile(r"^(RULE: \[|### Session #)", re.MULTILINE)

# Activity log entry header: ## YYYY-MM-DD HH:MM — TYPE
_ACTIVITY_RE = re.compile(r"^## \d{4}-\d{2}-\d{2}", re.MULTILINE)


def _parse_knowledge_sections(text: str) -> list[tuple[str, datetime.date | None]]:
    """Split knowledge.md into sections, each with its most recent date."""
    sections = []
    # Find all section start positions
    starts = [m.start() for m in _SECTION_RE.finditer(text)]
    if not starts:
        return [(text, None)]

    # Header before first section
    header = text[:starts[0]]

    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(text)
        chunk = text[start:end]
        dates = _DATE_RE.findall(chunk)
        section_date = None
        for d in dates:
            try:
                parsed = datetime.date.fromisoformat(d)
                if section_date is None or parsed > section_date:
                    section_date = parsed
            except ValueError:
                continue
        sections.append((chunk, section_date))

    return [(header, None)] + sections


def evict_old_entries(knowledge_path: Path, archive_path: Path, max_age_days: int = 30):
    """Archive knowledge.md entries older than max_age_days."""
    if not knowledge_path.exists():
        return 0

    text = knowledge_path.read_text(encoding="utf-8")
    cutoff = datetime.date.today() - datetime.timedelta(days=max_age_days)
    sections = _parse_knowledge_sections(text)

    keep = []
    archive = []
    for chunk, section_date in sections:
        if section_date is not None and section_date < cutoff:
            archive.append(chunk)
        else:
            keep.append(chunk)

    # Write kept content back
    knowledge_path.write_text("".join(keep), encoding="utf-8")

    # Append archived content
    if archive:
        existing = archive_path.read_text(encoding="utf-8") if archive_path.exists() else ""
        separator = "\n" if existing and not existing.endswith("\n") else ""
        archive_path.write_text(
            existing + separator + "".join(archive),
            encoding="utf-8",
        )

    return len(archive)


def _parse_activity_entries(text: str) -> tuple[str, list[str]]:
    """Split activity_log.md into header + list of entry blocks."""
    starts = [m.start() for m in _ACTIVITY_RE.finditer(text)]
    if not starts:
        return text, []

    header = text[:starts[0]]
    entries = []
    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(text)
        entries.append(text[start:end])

    return header, entries


def sliding_window_activity_log(activity_path: Path, archive_path: Path, max_entries: int = 30):
    """Keep last max_entries in activity_log.md, archive the rest."""
    if not activity_path.exists():
        return 0

    text = activity_path.read_text(encoding="utf-8")
    header, entries = _parse_activity_entries(text)

    if len(entries) <= max_entries:
        return 0

    # Entries are newest-first in the file, so keep the first max_entries
    keep = entries[:max_entries]
    evicted = entries[max_entries:]

    # Write kept
    activity_path.write_text(header + "".join(keep), encoding="utf-8")

    # Append evicted to archive
    if evicted:
        existing = archive_path.read_text(encoding="utf-8") if archive_path.exists() else ""
        separator = "\n" if existing and not existing.endswith("\n") else ""
        archive_path.write_text(
            existing + separator + "".join(evicted),
            encoding="utf-8",
        )

    return len(evicted)


def run_eviction(memory_dir: Path, knowledge_max_age: int = 30, activity_max_entries: int = 30) -> dict:
    """Orchestrate all evictions for a project's memory directory."""
    knowledge = memory_dir / "knowledge.md"
    knowledge_archive = memory_dir / "knowledge_archive.md"
    k_count = evict_old_entries(knowledge, knowledge_archive, max_age_days=knowledge_max_age)

    activity = memory_dir / "activity_log.md"
    activity_archive = memory_dir / "activity_log_archive.md"
    a_count = sliding_window_activity_log(activity, activity_archive, max_entries=activity_max_entries)

    return {
        "knowledge_archived": k_count,
        "activity_archived": a_count,
    }
