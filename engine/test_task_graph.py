#!/usr/bin/env python3
"""Tests for task_graph.py — DAG-style dependency-aware task selection."""
import pytest
from task_graph import TaskNode, TaskGraph, CyclicDependencyError


# ── Parsing ──

class TestParseBacklog:
    def test_flat_backlog_no_deps(self):
        """Plain backlog lines become independent nodes."""
        lines = [
            "- [ ] [T1] Build login page",
            "- [ ] [T2] Add search endpoint",
        ]
        g = TaskGraph.from_backlog("\n".join(lines))
        assert len(g.nodes) == 2
        assert g.nodes["T1"].name == "Build login page"
        assert g.nodes["T2"].depends_on == []

    def test_parse_with_dependencies(self):
        """(depends: T1) syntax creates edges."""
        lines = [
            "- [ ] [T1] Create database schema",
            "- [ ] [T2] Build API routes (depends: T1)",
            "- [ ] [T3] Wire frontend (depends: T1, T2)",
        ]
        g = TaskGraph.from_backlog("\n".join(lines))
        assert g.nodes["T2"].depends_on == ["T1"]
        assert g.nodes["T3"].depends_on == ["T1", "T2"]

    def test_duplicate_dependency_deduped_no_false_cycle(self):
        """A dep listed twice must not inflate in_degree into a phantom cycle."""
        lines = [
            "- [ ] [T1] setup",
            "- [ ] [T2] build (depends: T1, T1)",
        ]
        g = TaskGraph.from_backlog("\n".join(lines))
        assert g.nodes["T2"].depends_on == ["T1"]   # deduped, order preserved
        assert g.has_cycle() is False               # was True before the fix
        order = [n.id for n in g.topological_order()]
        assert set(order) == {"T1", "T2"}           # all nodes ordered, T1 first
        assert order.index("T1") < order.index("T2")

    def test_done_tasks_marked(self):
        """[x] lines are parsed as done."""
        lines = [
            "- [x] [T1] Setup project",
            "- [ ] [T2] Build feature (depends: T1)",
        ]
        g = TaskGraph.from_backlog("\n".join(lines))
        assert g.nodes["T1"].done is True
        assert g.nodes["T2"].done is False

    def test_lines_without_id_get_auto_id(self):
        """Lines without [Tn] prefix get an auto-generated ID."""
        lines = [
            "- [ ] Build login page",
            "- [ ] Add search endpoint",
        ]
        g = TaskGraph.from_backlog("\n".join(lines))
        assert len(g.nodes) == 2
        # Auto IDs should be stable and unique
        ids = list(g.nodes.keys())
        assert ids[0] != ids[1]

    def test_non_task_lines_skipped(self):
        """Headers, blank lines, and prose are ignored."""
        text = """# Backlog

## TDD Rules
- Write failing tests FIRST

---

- [ ] [T1] Real task here
"""
        g = TaskGraph.from_backlog(text)
        assert len(g.nodes) == 1

    def test_agent_hint_preserved(self):
        """[agent: name] hints survive parsing."""
        lines = ["- [ ] [T1] Fix auth bug [agent: backend]"]
        g = TaskGraph.from_backlog("\n".join(lines))
        assert g.nodes["T1"].agent_hint == "backend"

    def test_empty_backlog(self):
        g = TaskGraph.from_backlog("")
        assert len(g.nodes) == 0


# ── Ready tasks ──

class TestFindReady:
    def test_all_independent_are_ready(self):
        lines = [
            "- [ ] [T1] Task A",
            "- [ ] [T2] Task B",
        ]
        g = TaskGraph.from_backlog("\n".join(lines))
        ready = g.find_ready()
        assert {n.id for n in ready} == {"T1", "T2"}

    def test_blocked_task_not_ready(self):
        lines = [
            "- [ ] [T1] Task A",
            "- [ ] [T2] Task B (depends: T1)",
        ]
        g = TaskGraph.from_backlog("\n".join(lines))
        ready = g.find_ready()
        assert [n.id for n in ready] == ["T1"]

    def test_dep_done_unblocks(self):
        lines = [
            "- [x] [T1] Task A",
            "- [ ] [T2] Task B (depends: T1)",
        ]
        g = TaskGraph.from_backlog("\n".join(lines))
        ready = g.find_ready()
        assert [n.id for n in ready] == ["T2"]

    def test_partial_deps_still_blocked(self):
        """T3 depends on T1 (done) and T2 (not done) — still blocked."""
        lines = [
            "- [x] [T1] Task A",
            "- [ ] [T2] Task B",
            "- [ ] [T3] Task C (depends: T1, T2)",
        ]
        g = TaskGraph.from_backlog("\n".join(lines))
        ready = g.find_ready()
        ready_ids = {n.id for n in ready}
        assert "T3" not in ready_ids
        assert "T2" in ready_ids

    def test_done_tasks_excluded_from_ready(self):
        lines = [
            "- [x] [T1] Task A",
            "- [ ] [T2] Task B",
        ]
        g = TaskGraph.from_backlog("\n".join(lines))
        ready = g.find_ready()
        assert all(n.id != "T1" for n in ready)


# ── Pick next ──

class TestPickNext:
    def test_picks_first_ready(self):
        lines = [
            "- [ ] [T1] Task A",
            "- [ ] [T2] Task B (depends: T1)",
        ]
        g = TaskGraph.from_backlog("\n".join(lines))
        nxt = g.pick_next()
        assert nxt is not None
        assert nxt.id == "T1"

    def test_returns_none_when_all_done(self):
        lines = [
            "- [x] [T1] Task A",
        ]
        g = TaskGraph.from_backlog("\n".join(lines))
        assert g.pick_next() is None

    def test_returns_none_when_all_blocked(self):
        """All undone tasks depend on something undone — deadlock."""
        lines = [
            "- [ ] [T1] Task A (depends: T2)",
            "- [ ] [T2] Task B (depends: T1)",
        ]
        g = TaskGraph.from_backlog("\n".join(lines))
        assert g.pick_next() is None


# ── Cycle detection ──

class TestCycleDetection:
    def test_direct_cycle_detected(self):
        lines = [
            "- [ ] [T1] Task A (depends: T2)",
            "- [ ] [T2] Task B (depends: T1)",
        ]
        g = TaskGraph.from_backlog("\n".join(lines))
        assert g.has_cycle() is True

    def test_transitive_cycle_detected(self):
        lines = [
            "- [ ] [T1] A (depends: T3)",
            "- [ ] [T2] B (depends: T1)",
            "- [ ] [T3] C (depends: T2)",
        ]
        g = TaskGraph.from_backlog("\n".join(lines))
        assert g.has_cycle() is True

    def test_no_cycle_in_valid_dag(self):
        lines = [
            "- [ ] [T1] A",
            "- [ ] [T2] B (depends: T1)",
            "- [ ] [T3] C (depends: T1, T2)",
        ]
        g = TaskGraph.from_backlog("\n".join(lines))
        assert g.has_cycle() is False

    def test_validate_raises_on_cycle(self):
        lines = [
            "- [ ] [T1] A (depends: T2)",
            "- [ ] [T2] B (depends: T1)",
        ]
        g = TaskGraph.from_backlog("\n".join(lines))
        with pytest.raises(CyclicDependencyError):
            g.validate()


# ── Topological order ──

class TestTopologicalOrder:
    def test_topo_order_respects_deps(self):
        lines = [
            "- [ ] [T1] A",
            "- [ ] [T2] B (depends: T1)",
            "- [ ] [T3] C (depends: T2)",
        ]
        g = TaskGraph.from_backlog("\n".join(lines))
        order = g.topological_order()
        ids = [n.id for n in order]
        assert ids.index("T1") < ids.index("T2") < ids.index("T3")

    def test_topo_order_independent_tasks_preserved(self):
        """Independent tasks appear in insertion order."""
        lines = [
            "- [ ] [T1] A",
            "- [ ] [T2] B",
            "- [ ] [T3] C",
        ]
        g = TaskGraph.from_backlog("\n".join(lines))
        order = g.topological_order()
        ids = [n.id for n in order]
        assert ids == ["T1", "T2", "T3"]


# ── Serialization back to backlog ──

class TestSerialize:
    def test_roundtrip(self):
        """Parse → serialize → parse produces equivalent graph."""
        text = """- [ ] [T1] Create schema
- [ ] [T2] Build routes (depends: T1)
- [x] [T3] Setup CI"""
        g1 = TaskGraph.from_backlog(text)
        serialized = g1.to_backlog()
        g2 = TaskGraph.from_backlog(serialized)
        assert set(g2.nodes.keys()) == set(g1.nodes.keys())
        for tid in g1.nodes:
            assert g1.nodes[tid].depends_on == g2.nodes[tid].depends_on
            assert g1.nodes[tid].done == g2.nodes[tid].done
