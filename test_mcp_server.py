"""Tests for the MCP server's T2 async council job layer.

No network / API cost — the council call is stubbed. Exercises the job
lifecycle (submit → run → persist → poll), the budget refusal pre-check,
and the unknown/error states.
"""
import time

import pytest

import mcp_server as srv


def _tool(name):
    """Resolve a registered MCP tool's underlying function."""
    return srv.mcp._tool_manager._tools[name].fn


@pytest.fixture(autouse=True)
def isolate_jobs(tmp_path, monkeypatch):
    """Redirect the job store to a temp dir and allow all providers by default."""
    monkeypatch.setattr(srv, "_JOBS_DIR", tmp_path / "mcp_jobs")
    monkeypatch.setattr(srv.council_usage, "check_provider_budget",
                        lambda p, period="month": (True, "ok"))


def _wait(job_id, timeout=5.0):
    result = _tool("council_result")
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = result(job_id=job_id)
        if r["status"] != "running":
            return r
        time.sleep(0.05)
    raise AssertionError("job did not finish in time")


def test_convene_lifecycle(monkeypatch):
    monkeypatch.setattr(srv, "_convene_council",
                        lambda question, context="", mode="executive": {
                            "question": question, "winner": "Stub", "confidence": "HIGH"})
    sub = _tool("council_convene")(question="ship it?")
    assert sub["status"] == "running" and "job_id" in sub
    final = _wait(sub["job_id"])
    assert final["status"] == "done"
    assert final["result"]["winner"] == "Stub"


def test_debate_lifecycle(monkeypatch):
    monkeypatch.setattr(srv, "_convene_debate",
                        lambda question, context="", max_rounds=3: {
                            "question": question, "status": "converged", "confidence": "HIGH"})
    sub = _tool("council_debate")(question="merge?", max_rounds=2)
    final = _wait(sub["job_id"])
    assert final["status"] == "done"
    assert final["result"]["status"] == "converged"


def test_error_is_captured(monkeypatch):
    def boom(question, context="", mode="executive"):
        raise RuntimeError("council exploded")
    monkeypatch.setattr(srv, "_convene_council", boom)
    sub = _tool("council_convene")(question="x")
    final = _wait(sub["job_id"])
    assert final["status"] == "error"
    assert "council exploded" in final["error"]


def test_refused_when_all_over_budget(monkeypatch):
    monkeypatch.setattr(srv.council_usage, "check_provider_budget",
                        lambda p, period="month": (False, "over"))
    out = _tool("council_convene")(question="x")
    assert out["status"] == "refused"
    assert "over" in out["error"]


def test_unknown_job():
    assert _tool("council_result")(job_id="nope")["status"] == "unknown"


def test_jobs_list(monkeypatch):
    monkeypatch.setattr(srv, "_convene_council",
                        lambda question, context="", mode="executive": {"winner": "S"})
    sub = _tool("council_convene")(question="list me")
    _wait(sub["job_id"])
    jobs = _tool("council_jobs")(limit=10)
    assert any(j["job_id"] == sub["job_id"] and j["kind"] == "convene" for j in jobs)
