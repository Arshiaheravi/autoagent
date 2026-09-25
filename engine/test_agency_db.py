"""Tests for agency_db.py — SQLite-backed agency state."""
import pytest
import agency_db


@pytest.fixture(autouse=True)
def _fresh_db(tmp_path, monkeypatch):
    """Each test gets a fresh SQLite database in tmp_path."""
    monkeypatch.setattr(agency_db, "_DB_PATH", tmp_path / "test.db")
    # Reset thread-local connection so _get_conn creates a new one
    agency_db._local.conn = None
    yield
    agency_db._local.conn = None


# ── Projects ──────────────────────────────────────────────────────

def test_upsert_and_get_projects():
    agency_db.upsert_project("alpha", "/tmp/alpha")
    projects = agency_db.get_projects()
    assert len(projects) == 1
    assert projects[0]["name"] == "alpha"
    assert projects[0]["path"] == "/tmp/alpha"


def test_upsert_project_updates_existing():
    agency_db.upsert_project("alpha", "/old")
    agency_db.upsert_project("alpha", "/new", config={"k": "v"})
    projects = agency_db.get_projects()
    assert len(projects) == 1
    assert projects[0]["path"] == "/new"


def test_get_projects_empty():
    assert agency_db.get_projects() == []


# ── Sessions ──────────────────────────────────────────────────────

def test_log_session_returns_id():
    agency_db.upsert_project("p", "/p")
    sid = agency_db.log_session("p", 1, "work", summary="did stuff")
    assert isinstance(sid, int) and sid > 0


def test_upsert_session_updates_existing_session_num():
    agency_db.upsert_project("p", "/p")
    sid1 = agency_db.upsert_session("p", 1, "work", agent="architect", success=False,
                                    summary="first")
    sid2 = agency_db.upsert_session("p", 1, "work", agent="architect", success=True,
                                    tests_after=12, summary="updated")
    sessions = agency_db.get_recent_sessions("p", limit=10)
    assert sid1 == sid2
    assert len(sessions) == 1
    assert sessions[0]["success"] == 1
    assert sessions[0]["tests_after"] == 12
    assert sessions[0]["summary"] == "updated"
    assert sessions[0]["success_source"] == "explicit"


def test_upsert_session_collapses_duplicate_rows():
    agency_db.upsert_project("p", "/p")
    old_id = agency_db.log_session("p", 1, "work", agent="old", success=False)
    newer_id = agency_db.log_session("p", 1, "work", agent="newer", success=False)
    task_id = agency_db.add_task("p", "Task")
    agency_db.update_task(task_id, "done", session_id=old_id)

    sid = agency_db.upsert_session("p", 1, "work", agent="coder", success=True)

    assert sid == newer_id
    sessions = agency_db.get_recent_sessions("p", limit=10)
    assert len(sessions) == 1
    assert sessions[0]["id"] == newer_id
    assert sessions[0]["agent"] == "coder"
    task = agency_db.get_tasks("p", status="done")[0]
    assert task["session_id"] == newer_id


def test_get_recent_sessions_by_project():
    agency_db.upsert_project("a", "/a")
    agency_db.upsert_project("b", "/b")
    agency_db.log_session("a", 1, "work")
    agency_db.log_session("b", 1, "meta")
    agency_db.log_session("a", 2, "work")
    assert len(agency_db.get_recent_sessions("a")) == 2
    assert len(agency_db.get_recent_sessions("b")) == 1


def test_get_recent_sessions_all():
    agency_db.upsert_project("a", "/a")
    agency_db.log_session("a", 1, "work")
    agency_db.log_session("a", 2, "meta")
    all_sessions = agency_db.get_recent_sessions(limit=10)
    assert len(all_sessions) == 2


def test_get_recent_sessions_respects_limit():
    agency_db.upsert_project("p", "/p")
    for i in range(5):
        agency_db.log_session("p", i, "work")
    assert len(agency_db.get_recent_sessions("p", limit=3)) == 3


def test_get_session_stats():
    agency_db.upsert_project("p", "/p")
    agency_db.log_session("p", 1, "work", success=True, quality_score=80)
    agency_db.log_session("p", 2, "work", success=False, quality_score=40)
    stats = agency_db.get_session_stats("p")
    assert stats["total"] == 2
    assert stats["successes"] == 1
    assert stats["avg_quality"] == 60.0


def test_get_session_stats_all_projects():
    agency_db.upsert_project("a", "/a")
    agency_db.upsert_project("b", "/b")
    agency_db.log_session("a", 1, "work", success=True)
    agency_db.log_session("b", 1, "work", success=True)
    stats = agency_db.get_session_stats()
    assert stats["total"] == 2


# ── Agents ────────────────────────────────────────────────────────

def test_upsert_and_get_agents():
    agency_db.upsert_project("p", "/p")
    agency_db.upsert_agent("p", "coder", display_name="The Coder", keywords=["python"])
    agents = agency_db.get_agents("p")
    assert len(agents) == 1
    assert agents[0]["name"] == "coder"
    assert agents[0]["display_name"] == "The Coder"


def test_upsert_agent_updates_existing():
    agency_db.upsert_project("p", "/p")
    agency_db.upsert_agent("p", "coder", display_name="Old")
    agency_db.upsert_agent("p", "coder", display_name="New")
    agents = agency_db.get_agents("p")
    assert len(agents) == 1
    assert agents[0]["display_name"] == "New"


def test_update_agent_stats_success():
    agency_db.upsert_project("p", "/p")
    agency_db.upsert_agent("p", "coder")
    agency_db.update_agent_stats("p", "coder", success=True, quality=90)
    agent = agency_db.get_agents("p")[0]
    assert agent["total_sessions"] == 1
    assert agent["successful"] == 1
    assert agent["failed"] == 0


def test_update_agent_stats_failure():
    agency_db.upsert_project("p", "/p")
    agency_db.upsert_agent("p", "coder")
    agency_db.update_agent_stats("p", "coder", success=False)
    agent = agency_db.get_agents("p")[0]
    assert agent["total_sessions"] == 1
    assert agent["successful"] == 0
    assert agent["failed"] == 1


def test_get_top_agents():
    agency_db.upsert_project("p", "/p")
    agency_db.upsert_agent("p", "good")
    agency_db.upsert_agent("p", "bad")
    agency_db.update_agent_stats("p", "good", success=True)
    agency_db.update_agent_stats("p", "good", success=True)
    agency_db.update_agent_stats("p", "bad", success=False)
    top = agency_db.get_top_agents(limit=10)
    assert len(top) == 2
    assert top[0]["name"] == "good"  # higher success rate comes first
    assert top[0]["success_rate"] == 1.0


# ── Knowledge ─────────────────────────────────────────────────────

def test_add_and_get_knowledge():
    agency_db.upsert_project("p", "/p")
    kid = agency_db.add_knowledge("p", "Always test first", source="session 1")
    assert isinstance(kid, int) and kid > 0
    rules = agency_db.get_knowledge("p")
    assert len(rules) == 1
    assert rules[0]["rule"] == "Always test first"


def test_add_knowledge_deduplicates():
    agency_db.upsert_project("p", "/p")
    id1 = agency_db.add_knowledge("p", "Same rule")
    id2 = agency_db.add_knowledge("p", "Same rule")
    assert id1 == id2
    rules = agency_db.get_knowledge("p")
    assert len(rules) == 1
    assert rules[0]["use_count"] == 1  # incremented on duplicate


def test_get_knowledge_respects_min_score():
    agency_db.upsert_project("p", "/p")
    agency_db.add_knowledge("p", "Low score rule")
    # Default score is 1.0, so min_score=2.0 should filter it out
    assert len(agency_db.get_knowledge("p", min_score=2.0)) == 0
    assert len(agency_db.get_knowledge("p", min_score=0.5)) == 1


def test_prune_knowledge():
    agency_db.upsert_project("p", "/p")
    for i in range(10):
        agency_db.add_knowledge("p", f"Rule {i}")
    deleted = agency_db.prune_knowledge("p", keep_top=5)
    assert deleted == 5
    remaining = agency_db.get_knowledge("p", limit=100)
    assert len(remaining) == 5


# ── Tasks ─────────────────────────────────────────────────────────

def test_add_and_get_tasks():
    agency_db.upsert_project("p", "/p")
    tid = agency_db.add_task("p", "Build feature X", priority=10)
    assert isinstance(tid, int) and tid > 0
    tasks = agency_db.get_tasks("p")
    assert len(tasks) == 1
    assert tasks[0]["title"] == "Build feature X"
    assert tasks[0]["status"] == "pending"


def test_update_task_to_done():
    agency_db.upsert_project("p", "/p")
    sid = agency_db.log_session("p", 1, "work")
    tid = agency_db.add_task("p", "Task A")
    agency_db.update_task(tid, "done", session_id=sid)
    # No longer in pending
    assert len(agency_db.get_tasks("p", status="pending")) == 0
    done = agency_db.get_tasks("p", status="done")
    assert len(done) == 1
    assert done[0]["completed_at"] is not None
    assert done[0]["session_id"] == sid


def test_update_task_to_in_progress():
    agency_db.upsert_project("p", "/p")
    tid = agency_db.add_task("p", "Task B")
    agency_db.update_task(tid, "in_progress")
    tasks = agency_db.get_tasks("p", status="in_progress")
    assert len(tasks) == 1


def test_tasks_ordered_by_priority():
    agency_db.upsert_project("p", "/p")
    agency_db.add_task("p", "Low", priority=1)
    agency_db.add_task("p", "High", priority=10)
    agency_db.add_task("p", "Med", priority=5)
    tasks = agency_db.get_tasks("p")
    assert [t["title"] for t in tasks] == ["High", "Med", "Low"]


# ── Messages ──────────────────────────────────────────────────────

def test_log_and_get_messages():
    mid = agency_db.log_message("outbound", "Hello user", message_type="notify", project="p")
    assert isinstance(mid, int) and mid > 0
    msgs = agency_db.get_messages(limit=10)
    assert len(msgs) == 1
    assert msgs[0]["content"] == "Hello user"
    assert msgs[0]["direction"] == "outbound"


def test_get_messages_filtered_by_project():
    agency_db.log_message("outbound", "For A", project="a")
    agency_db.log_message("outbound", "For B", project="b")
    assert len(agency_db.get_messages(project="a")) == 1
    assert len(agency_db.get_messages(project="b")) == 1


# ── Metrics ───────────────────────────────────────────────────────

def test_record_and_get_metrics():
    agency_db.upsert_project("p", "/p")
    agency_db.record_metric("p", "test_count", 100)
    agency_db.record_metric("p", "test_count", 110)
    metrics = agency_db.get_metrics("p", "test_count")
    assert len(metrics) == 2
    values = [m["value"] for m in metrics]
    assert 100.0 in values and 110.0 in values


def test_get_metrics_respects_limit():
    agency_db.upsert_project("p", "/p")
    for i in range(10):
        agency_db.record_metric("p", "cost", float(i))
    assert len(agency_db.get_metrics("p", "cost", limit=3)) == 3


# ── Council Decisions ────────────────────────────────────────────

def test_log_council_decision_returns_id():
    agency_db.upsert_project("p", "/p")
    did = agency_db.log_council_decision(
        project="p", session_num=5, question="Ship this?",
        winner="The Pragmatist", confidence="HIGH",
    )
    assert isinstance(did, int) and did > 0


def test_log_council_decision_stores_fields():
    agency_db.upsert_project("p", "/p")
    agency_db.log_council_decision(
        project="p", session_num=10, question="Deploy on Friday?",
        winner="The Bear", confidence="LOW", synthesis="Don't do it.",
    )
    decisions = agency_db.get_council_decisions("p")
    assert len(decisions) == 1
    d = decisions[0]
    assert d["question"] == "Deploy on Friday?"
    assert d["winner"] == "The Bear"
    assert d["confidence"] == "LOW"
    assert d["synthesis"] == "Don't do it."
    assert d["session_outcome"] is None  # not yet known


def test_update_council_outcome():
    agency_db.upsert_project("p", "/p")
    did = agency_db.log_council_decision(
        project="p", session_num=5, question="Ship?",
        winner="The Bull", confidence="HIGH",
    )
    agency_db.update_council_outcome(did, session_success=True)
    decisions = agency_db.get_council_decisions("p")
    assert decisions[0]["session_outcome"] == 1


def test_get_council_stats_correlation():
    """HIGH confidence decisions should correlate with session outcomes."""
    agency_db.upsert_project("p", "/p")
    # 3 HIGH confidence decisions: 2 success, 1 fail
    for i, success in enumerate([True, True, False]):
        did = agency_db.log_council_decision(
            project="p", session_num=i, question=f"Q{i}",
            winner="Bull", confidence="HIGH",
        )
        agency_db.update_council_outcome(did, session_success=success)
    # 2 LOW confidence decisions: 0 success, 2 fail
    for i, success in enumerate([False, False]):
        did = agency_db.log_council_decision(
            project="p", session_num=10 + i, question=f"Q{10+i}",
            winner="Bear", confidence="LOW",
        )
        agency_db.update_council_outcome(did, session_success=success)

    stats = agency_db.get_council_stats("p")
    assert stats["HIGH"]["total"] == 3
    assert stats["HIGH"]["successful"] == 2
    assert abs(stats["HIGH"]["success_rate"] - 0.67) < 0.01
    assert stats["LOW"]["total"] == 2
    assert stats["LOW"]["successful"] == 0
    assert stats["LOW"]["success_rate"] == 0.0


def test_get_council_stats_empty():
    agency_db.upsert_project("p", "/p")
    stats = agency_db.get_council_stats("p")
    assert stats == {}


def test_get_council_decisions_respects_limit():
    agency_db.upsert_project("p", "/p")
    for i in range(10):
        agency_db.log_council_decision(
            project="p", session_num=i, question=f"Q{i}",
            winner="Bull", confidence="HIGH",
        )
    assert len(agency_db.get_council_decisions("p", limit=3)) == 3


# ── Agency Summary ────────────────────────────────────────────────

def test_agency_summary_empty():
    s = agency_db.agency_summary()
    assert s["projects"] == 0
    assert s["total_sessions"] == 0
    assert s["success_rate_pct"] == 0


def test_agency_summary_with_data():
    agency_db.upsert_project("p", "/p")
    agency_db.log_session("p", 1, "work", success=True)
    agency_db.log_session("p", 2, "work", success=False)
    agency_db.upsert_agent("p", "coder")
    agency_db.add_knowledge("p", "A rule")
    agency_db.add_task("p", "Do X")
    agency_db.log_message("outbound", "hi")
    s = agency_db.agency_summary()
    assert s["projects"] == 1
    assert s["total_sessions"] == 2
    assert s["agents"] == 1
    assert s["knowledge_rules"] == 1
    assert s["tasks_pending"] == 1
    assert s["tasks_done"] == 0
    assert s["messages"] == 1
    assert s["success_rate_pct"] == 50


# ── Split verification ───────────────────────────────────────────

def test_agency_db_split_preserves_imports():
    """All public functions remain importable from agency_db after split."""
    import agency_db_queries
    # Verify agency_db_queries exports the query/reporting functions
    for name in ("get_projects", "get_recent_sessions", "get_session_stats",
                 "get_agents", "get_top_agents", "get_knowledge", "prune_knowledge",
                 "get_tasks", "get_messages", "get_metrics",
                 "agency_summary", "migrate_from_files"):
        assert hasattr(agency_db_queries, name), f"agency_db_queries missing {name}"
    # Verify agency_db still re-exports them for backward compatibility
    for name in ("get_projects", "get_recent_sessions", "get_session_stats",
                 "get_agents", "get_top_agents", "get_knowledge", "prune_knowledge",
                 "get_tasks", "get_messages", "get_metrics",
                 "agency_summary"):
        assert hasattr(agency_db, name), f"agency_db missing re-export {name}"
    # Verify agency_db retains the write functions natively
    for name in ("upsert_project", "log_session", "upsert_agent",
                 "upsert_session", "rebuild_agent_stats_from_sessions",
                 "update_agent_stats", "add_knowledge", "add_task",
                 "update_task", "log_message", "record_metric"):
        assert hasattr(agency_db, name), f"agency_db missing {name}"


# ── Agent Metrics: avg_quality tracking ──────────────────────────

def test_agent_metrics_updated_after_session():
    """update_agent_stats properly tracks avg_quality as a running average."""
    agency_db.upsert_project("p", "/p")
    agency_db.upsert_agent("p", "coder")
    # Session 1: quality 80
    agency_db.update_agent_stats("p", "coder", success=True, quality=80)
    agent = agency_db.get_agents("p")[0]
    assert agent["avg_quality"] == 80.0
    assert agent["total_sessions"] == 1
    # Session 2: quality 60 → avg should be (80+60)/2 = 70
    agency_db.update_agent_stats("p", "coder", success=True, quality=60)
    agent = agency_db.get_agents("p")[0]
    assert agent["avg_quality"] == 70.0
    assert agent["total_sessions"] == 2
    # Session 3: quality 90 → avg should be (70*2 + 90)/3 = 76.7
    agency_db.update_agent_stats("p", "coder", success=False, quality=90)
    agent = agency_db.get_agents("p")[0]
    assert abs(agent["avg_quality"] - 76.7) < 0.1
    assert agent["total_sessions"] == 3
    assert agent["successful"] == 2
    assert agent["failed"] == 1


def test_agent_metrics_zero_quality():
    """Quality of 0 is a valid score and should pull average down."""
    agency_db.upsert_project("p", "/p")
    agency_db.upsert_agent("p", "tester")
    agency_db.update_agent_stats("p", "tester", success=True, quality=100)
    agency_db.update_agent_stats("p", "tester", success=False, quality=0)
    agent = agency_db.get_agents("p")[0]
    assert agent["avg_quality"] == 50.0


def test_rebuild_agent_stats_from_sessions_is_idempotent():
    agency_db.upsert_project("p", "/p")
    agency_db.upsert_session("p", 1, "work", agent="coder", success=True, quality_score=80)
    agency_db.upsert_session("p", 2, "work", agent="coder", success=False, quality_score=40)
    assert agency_db.rebuild_agent_stats_from_sessions("p") == 1
    assert agency_db.rebuild_agent_stats_from_sessions("p") == 1
    agent = agency_db.get_agents("p")[0]
    assert agent["total_sessions"] == 2
    assert agent["successful"] == 1
    assert agent["failed"] == 1
    assert agent["avg_quality"] == 60.0


def test_agents_stats_cli_output(capsys):
    """autoagent agents stats subcommand renders ranked table."""
    agency_db.upsert_project("p1", "/p1")
    agency_db.upsert_agent("p1", "coder")
    agency_db.upsert_agent("p1", "tester")
    agency_db.update_agent_stats("p1", "coder", success=True, quality=85)
    agency_db.update_agent_stats("p1", "coder", success=True, quality=75)
    agency_db.update_agent_stats("p1", "tester", success=False, quality=40)
    from cli_commands import cmd_agent
    cmd_agent(["stats"])
    out = capsys.readouterr().out
    assert "coder" in out
    assert "tester" in out
    assert "100%" in out or "100" in out  # coder has 100% success rate
