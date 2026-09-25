"""Regression tests for council memory tenant-scoping (cross-tenant leak fix).

recall_similar / recall_analogical / recall_combined must scope every query by
`project` so tenant A never recalls tenant B's verdicts from a shared pgvector.
A missing project filter was a cross-tenant data leak.

These are hermetic — no live Postgres. `embed` and `with_conn` are stubbed;
a fake cursor records the SQL + params so we can assert the project filter and
its bound value are present.
"""
from contextlib import contextmanager
from unittest.mock import patch

from council import memory


class _FakeCursor:
    """Records execute() calls; returns no rows."""
    def __init__(self, sink):
        self._sink = sink

    def execute(self, sql, params=None):
        self._sink.append((sql, params))

    def fetchall(self):
        return []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _FakeConn:
    def __init__(self, sink):
        self._sink = sink

    def cursor(self):
        return _FakeCursor(self._sink)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _stub_db(sink):
    @contextmanager
    def _with_conn():
        yield _FakeConn(sink)
    return _with_conn


def test_recall_similar_binds_project_into_filter():
    sink = []
    with patch.object(memory, "is_enabled", return_value=True), \
         patch.object(memory, "embed", return_value=[0.0] * memory.EMBED_DIM), \
         patch.object(memory, "with_conn", _stub_db(sink)):
        memory.recall_similar("ship it?", project="tenant-A")
    assert sink, "execute was never called"
    sql, params = sink[0]
    assert "project = %s" in sql, "project filter clause missing from SQL"
    assert "tenant-A" in params, "project value not bound into query params"


def test_recall_similar_unscoped_passes_none():
    sink = []
    with patch.object(memory, "is_enabled", return_value=True), \
         patch.object(memory, "embed", return_value=[0.0] * memory.EMBED_DIM), \
         patch.object(memory, "with_conn", _stub_db(sink)):
        memory.recall_similar("ship it?", project=None)
    sql, params = sink[0]
    assert "%s::text IS NULL OR project = %s" in sql, "unscoped guard missing"
    assert None in params, "None (unscoped) not bound — would over-filter"


def test_recall_analogical_binds_project_into_filter():
    sink = []
    with patch.object(memory, "is_enabled", return_value=True), \
         patch.object(memory, "is_r4_enabled", return_value=True), \
         patch.object(memory, "embed", return_value=[0.0] * memory.EMBED_DIM), \
         patch.object(memory, "with_conn", _stub_db(sink)):
        memory.recall_analogical("ship it?", "some context", project="tenant-B")
    sql, params = sink[0]
    assert "project = %s" in sql
    assert "tenant-B" in params


def test_recall_combined_threads_project_to_both_recalls():
    calls = {}

    def _fake_similar(question, context="", *, k=None, project=None):
        calls["similar"] = project
        return []

    def _fake_analogical(question, context="", *, k=None, exclude_ids=None, project=None):
        calls["analogical"] = project
        return []

    with patch.object(memory, "is_enabled", return_value=True), \
         patch.object(memory, "is_r4_enabled", return_value=True), \
         patch.object(memory, "recall_similar", _fake_similar), \
         patch.object(memory, "recall_analogical", _fake_analogical):
        memory.recall_combined("q", "ctx", project="tenant-C")

    assert calls.get("similar") == "tenant-C"
    assert calls.get("analogical") == "tenant-C"
