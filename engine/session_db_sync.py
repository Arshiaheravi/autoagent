#!/usr/bin/env python3
"""Sync file-based session logs into the agency SQLite database."""
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_bool(value: Any, default: bool = False) -> bool:
    """Parse bool-ish session fields without treating every string as True."""
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "ok", "pass", "passed", "success"}:
            return True
        if normalized in {"0", "false", "no", "n", "fail", "failed", "failure", "none", ""}:
            return False
    return default


def _quality_score(entry: dict[str, Any]) -> int:
    quality = entry.get("quality", {})
    if isinstance(quality, dict):
        return _as_int(quality.get("score", quality.get("overall", 0)))
    return _as_int(quality)


def _test_counts(entry: dict[str, Any]) -> tuple[int, int]:
    tests = entry.get("tests", {})
    if not isinstance(tests, dict):
        return 0, 0
    return _as_int(tests.get("before", 0)), _as_int(tests.get("after", 0))


def _files_changed(entry: dict[str, Any]) -> list[str]:
    files = entry.get("files", [])
    if not isinstance(files, list):
        return []
    return [str(f) for f in files if f]


def infer_success(entry: dict[str, Any]) -> tuple[bool, str]:
    """Return (success, source) from a sessions.json entry.

    Older session logs often lack an explicit success field. The inference is
    intentionally conservative about known failure markers, then accepts
    positive test/quality/impact signals.
    """
    if "success" in entry:
        return _as_bool(entry.get("success")), "explicit"

    notes = str(entry.get("notes", "")).lower()
    summary = str(entry.get("summary", "")).lower()
    tests = entry.get("tests", {}) if isinstance(entry.get("tests", {}), dict) else {}
    test_status = str(tests.get("status", "")).lower()
    quality = _quality_score(entry)
    impact = _as_float(entry.get("impact_score", 0.0))
    files = _files_changed(entry)

    failure_terms = ("ghost", "failed", "failure", "blocked", "regression", "crash")
    if "ghost" in notes or test_status == "fail" or any(term in summary for term in failure_terms):
        return False, "inferred"
    if test_status == "pass" or quality >= 60 or impact >= 4:
        return True, "inferred"
    if files and test_status != "fail":
        return True, "inferred"
    return False, "inferred"


def sync_session_entry_to_agency_db(ctx: Any, entry: dict[str, Any],
                                    success: bool | None = None,
                                    raise_errors: bool = False) -> int | None:
    """Upsert one sessions.json entry into agency.db."""
    session_num = _as_int(entry.get("session"))
    if session_num <= 0:
        return None
    tests_before, tests_after = _test_counts(entry)
    if success is None:
        final_success, success_source = infer_success(entry)
    else:
        final_success, success_source = _as_bool(success), "explicit"
    try:
        from agency_db import upsert_project, upsert_session
        upsert_project(ctx.name, str(ctx.project_root), config=getattr(ctx, "config", {}))
        return upsert_session(
            ctx.name,
            session_num,
            str(entry.get("type") or "work"),
            agent=str(entry.get("agent") or ""),
            success=final_success,
            tests_before=tests_before,
            tests_after=tests_after,
            files_changed=_files_changed(entry),
            summary=str(entry.get("summary") or ""),
            cost_usd=_as_float(entry.get("cost_usd", 0.0)),
            quality_score=_quality_score(entry),
            success_source=success_source,
        )
    except Exception as exc:
        if raise_errors:
            raise
        logger.debug("session DB sync skipped for %s #%s: %s",
                     getattr(ctx, "name", "?"), session_num, exc)
        return None


def sync_sessions_file_to_agency_db(ctx: Any, rebuild_agent_stats: bool = True,
                                    raise_errors: bool = False) -> int:
    """Sync all entries in a project's sessions.json into agency.db."""
    sessions_file = Path(ctx.sessions_file)
    if not sessions_file.exists():
        return 0
    try:
        sessions = json.loads(sessions_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        if raise_errors:
            raise
        return 0
    if not isinstance(sessions, list):
        if raise_errors:
            raise ValueError(f"{sessions_file} must contain a JSON list")
        return 0

    count = 0
    for entry in sessions:
        if isinstance(entry, dict) and sync_session_entry_to_agency_db(
            ctx, entry, raise_errors=raise_errors,
        ) is not None:
            count += 1

    if rebuild_agent_stats and count:
        try:
            from agency_db import rebuild_agent_stats_from_sessions
            rebuild_agent_stats_from_sessions(ctx.name)
        except Exception as exc:
            logger.debug("agent stat rebuild skipped for %s: %s", getattr(ctx, "name", "?"), exc)
    return count
