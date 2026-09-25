"""Integration-suite guard for the optional Postgres council-memory backend.

The ``tests/`` suite exercises ``engine/council/memory.py``, which stores council
verdicts in Postgres + pgvector. When no database is reachable — the normal case
for a fresh checkout or the core unit run — the DB-backed tests are *skipped*
rather than *failed*, so ``pytest`` is green anywhere. CI provisions a pgvector
service and exports ``COUNCIL_MEMORY_DSN``, so the full suite runs there.

To run these locally, stand up Postgres + pgvector and export
``COUNCIL_MEMORY_DSN`` (see ``scripts/bootstrap_council_memory.sh``).

Author: Arshia Heravi
"""
import os

import pytest

# DB-backed tests all request the ``memory_on`` fixture, except the handful
# listed here that reach the database directly. Every other test in ``tests/``
# is a pure unit test (parsers, formatters, dimension guards) and always runs.
_DB_TESTS_WITHOUT_MEMORY_ON = {"test_health_check_reports_schema_dim"}

_db_reachable = None  # lazily resolved once, only if a DB test is collected


def _check_db() -> bool:
    """Return True iff a council-memory Postgres is reachable (2s timeout)."""
    dsn = os.environ.get(
        "COUNCIL_MEMORY_DSN",
        "postgresql://autoagency:autoagency@127.0.0.1:5432/autoagency_memory",
    )
    try:
        import psycopg
    except Exception:
        return False
    try:
        with psycopg.connect(dsn, connect_timeout=2):
            return True
    except Exception:
        return False


def _needs_db(item) -> bool:
    if "memory_on" in getattr(item, "fixturenames", ()):
        return True
    return getattr(item, "originalname", item.name) in _DB_TESTS_WITHOUT_MEMORY_ON


def pytest_collection_modifyitems(config, items):
    global _db_reachable
    skip = pytest.mark.skip(
        reason="Postgres council-memory DB not reachable — set COUNCIL_MEMORY_DSN "
        "(see scripts/bootstrap_council_memory.sh)"
    )
    for item in items:
        if not _needs_db(item):
            continue
        if _db_reachable is None:
            _db_reachable = _check_db()
        if not _db_reachable:
            item.add_marker(skip)
