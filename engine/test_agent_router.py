"""Tests for agent_router — success-rate-based agent routing."""
import pytest
from pathlib import Path

import agency_db as db


@pytest.fixture(autouse=True)
def setup_agency(tmp_path, monkeypatch):
    """Use an isolated temp DB for every test."""
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(db, "_local", __import__("threading").local())
    db.upsert_project("proj", str(tmp_path))
    yield


def _seed_sessions(project, agent, session_type, successes, failures):
    """Helper: seed N successful + N failed sessions for an agent."""
    for _ in range(successes):
        db.log_session(project, 1, session_type, agent=agent, success=True)
    for _ in range(failures):
        db.log_session(project, 1, session_type, agent=agent, success=False)


# ─── Core tests from backlog ─────────────────────────────────

def test_agent_routing_picks_best():
    """When multiple agents have history, pick the one with highest success rate."""
    from agent_router import pick_best_agent

    db.upsert_agent("proj", "alice")
    db.upsert_agent("proj", "bob")
    db.upsert_agent("proj", "carol")

    _seed_sessions("proj", "alice", "work", successes=3, failures=7)   # 30%
    _seed_sessions("proj", "bob", "work", successes=8, failures=2)     # 80%
    _seed_sessions("proj", "carol", "work", successes=5, failures=5)   # 50%

    result = pick_best_agent("proj", "work", ["alice", "bob", "carol"])
    assert result == "bob"


def test_fallback_when_no_history():
    """When no agent has session history, return None (caller uses default)."""
    from agent_router import pick_best_agent

    db.upsert_agent("proj", "alice")
    db.upsert_agent("proj", "bob")

    result = pick_best_agent("proj", "work", ["alice", "bob"])
    assert result is None


def test_fallback_when_history_is_too_small():
    """Routing waits for enough session history before choosing."""
    from agent_router import pick_best_agent

    db.upsert_agent("proj", "alice")
    _seed_sessions("proj", "alice", "work", successes=4, failures=0)

    result = pick_best_agent("proj", "work", ["alice"])
    assert result is None


def test_routing_with_tied_rates():
    """When agents are tied on success rate, prefer the one with more sessions."""
    from agent_router import pick_best_agent

    db.upsert_agent("proj", "alice")
    db.upsert_agent("proj", "bob")

    _seed_sessions("proj", "alice", "work", successes=2, failures=0)   # 100%, 2 sessions
    _seed_sessions("proj", "bob", "work", successes=5, failures=0)     # 100%, 5 sessions

    result = pick_best_agent("proj", "work", ["alice", "bob"])
    assert result == "bob"  # more sessions = more confident


# ─── get_agent_success_rate tests ─────────────────────────────

def test_success_rate_basic():
    """Compute success rate from session history."""
    from agent_router import get_agent_success_rate

    _seed_sessions("proj", "alice", "work", successes=7, failures=3)
    rate = get_agent_success_rate("proj", "alice", "work")
    assert abs(rate - 0.7) < 0.01


def test_success_rate_no_sessions():
    """No sessions → rate is 0.0."""
    from agent_router import get_agent_success_rate

    rate = get_agent_success_rate("proj", "nobody", "work")
    assert rate == 0.0


def test_success_rate_filters_by_type():
    """Success rate only counts sessions of the requested type."""
    from agent_router import get_agent_success_rate

    _seed_sessions("proj", "alice", "work", successes=9, failures=1)   # 90% work
    _seed_sessions("proj", "alice", "meta", successes=1, failures=9)   # 10% meta

    work_rate = get_agent_success_rate("proj", "alice", "work")
    meta_rate = get_agent_success_rate("proj", "alice", "meta")
    assert abs(work_rate - 0.9) < 0.01
    assert abs(meta_rate - 0.1) < 0.01


# ─── Swap threshold test ─────────────────────────────────────

def test_swap_below_threshold():
    """pick_best_agent skips agents below 40% success rate."""
    from agent_router import pick_best_agent

    db.upsert_agent("proj", "bad")
    db.upsert_agent("proj", "ok")

    _seed_sessions("proj", "bad", "work", successes=2, failures=8)   # 20%
    _seed_sessions("proj", "ok", "work", successes=6, failures=4)    # 60%

    # Even if "bad" is listed first, "ok" should be picked
    result = pick_best_agent("proj", "work", ["bad", "ok"])
    assert result == "ok"


def test_maybe_swap_keeps_agent_with_small_sample(tmp_path):
    """Do not swap an agent based on one noisy failed session."""
    from agent_router import maybe_swap_agent

    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    (agents_dir / "bad.md").write_text("# Bad", encoding="utf-8")
    (agents_dir / "ok.md").write_text("# OK", encoding="utf-8")
    _seed_sessions("proj", "bad", "work", successes=0, failures=1)
    _seed_sessions("proj", "ok", "work", successes=6, failures=0)

    assert maybe_swap_agent("proj", "bad", "work", agents_dir) == "bad"
