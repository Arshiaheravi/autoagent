#!/usr/bin/env python3
"""DAG-style task graph — dependency-aware task selection for orchestration.

Parses backlog.md lines into a directed acyclic graph where tasks can declare
dependencies on other tasks. The orchestrator uses this to pick the next task
whose prerequisites are all done.

Supports parallel batch detection: find_parallel_batches() returns groups
of independent tasks that can run simultaneously in separate worktrees.

Backlog format:
  - [ ] [T1] Task description
  - [ ] [T2] Another task (depends: T1)
  - [x] [T3] Done task (depends: T1, T2)
  - [ ] Plain task without ID (gets auto-ID)
  - [ ] [T4] Urgent task (priority: high)
"""
import re
from collections import deque
from dataclasses import dataclass, field
from typing import Optional


class CyclicDependencyError(Exception):
    """Raised when the task graph contains a cycle."""


_PRIORITY_VALUES = {"critical": 0, "high": 1, "medium": 2, "low": 3}


@dataclass
class TaskNode:
    id: str
    name: str
    depends_on: list[str] = field(default_factory=list)
    done: bool = False
    agent_hint: Optional[str] = None
    priority: str = "medium"
    _order: int = 0  # insertion order for stable sorting

    @property
    def priority_value(self) -> int:
        return _PRIORITY_VALUES.get(self.priority, 2)


# Regex patterns
_TASK_RE = re.compile(
    r'^- \[([ xX])\]\s*'           # checkbox
    r'(?:\[([A-Za-z0-9_-]+)\]\s*)?'  # optional [ID]
    r'(.+)$'                        # rest of line
)
_DEPENDS_RE = re.compile(r'\(depends:\s*([^)]+)\)')
_AGENT_RE = re.compile(r'\[agent:\s*([a-zA-Z0-9_-]+)\]')
_PRIORITY_RE = re.compile(r'\(priority:\s*(critical|high|medium|low)\)', re.IGNORECASE)


def _parse_line(line: str, order: int) -> Optional[TaskNode]:
    """Parse a single backlog line into a TaskNode, or None if not a task."""
    m = _TASK_RE.match(line.strip())
    if not m:
        return None

    check, task_id, rest = m.group(1), m.group(2), m.group(3)
    done = check.lower() == 'x'

    # Extract dependencies
    depends_on = []
    dep_m = _DEPENDS_RE.search(rest)
    if dep_m:
        # Dedupe (order-preserving): a dep listed twice would inflate in_degree
        # past what the single decrement per dependent can undo, producing a
        # phantom cycle that disables parallel execution.
        depends_on = list(dict.fromkeys(d.strip() for d in dep_m.group(1).split(",")))
        rest = _DEPENDS_RE.sub("", rest)

    # Extract agent hint
    agent_hint = None
    agent_m = _AGENT_RE.search(rest)
    if agent_m:
        agent_hint = agent_m.group(1)
        rest = _AGENT_RE.sub("", rest)

    # Extract priority
    priority = "medium"
    pri_m = _PRIORITY_RE.search(rest)
    if pri_m:
        priority = pri_m.group(1).lower()
        rest = _PRIORITY_RE.sub("", rest)

    name = rest.strip().rstrip(" —-")

    # Auto-generate ID if not provided
    if not task_id:
        task_id = f"auto_{order}"

    return TaskNode(
        id=task_id,
        name=name,
        depends_on=depends_on,
        done=done,
        agent_hint=agent_hint,
        priority=priority,
        _order=order,
    )


class TaskGraph:
    """Directed acyclic graph of tasks with dependency resolution."""

    def __init__(self, nodes: Optional[dict[str, TaskNode]] = None):
        self.nodes: dict[str, TaskNode] = nodes or {}

    @classmethod
    def from_backlog(cls, text: str) -> "TaskGraph":
        """Parse backlog markdown into a TaskGraph."""
        graph = cls()
        order = 0
        for line in text.splitlines():
            node = _parse_line(line, order)
            if node:
                graph.nodes[node.id] = node
                order += 1
        return graph

    def find_ready(self) -> list[TaskNode]:
        """Return undone tasks whose dependencies are all done."""
        ready = []
        for node in self.nodes.values():
            if node.done:
                continue
            all_deps_done = all(
                self.nodes.get(dep, TaskNode(id=dep, name="", done=True)).done
                for dep in node.depends_on
            )
            if all_deps_done:
                ready.append(node)
        return sorted(ready, key=lambda n: n._order)

    def pick_next(self) -> Optional[TaskNode]:
        """Pick the first ready task (by insertion order)."""
        ready = self.find_ready()
        return ready[0] if ready else None

    def has_cycle(self) -> bool:
        """Detect cycles using Kahn's algorithm."""
        in_degree = {nid: 0 for nid in self.nodes}
        for node in self.nodes.values():
            for dep in node.depends_on:
                if dep in self.nodes:
                    in_degree[node.id] += 1

        queue = deque(nid for nid, deg in in_degree.items() if deg == 0)
        visited = 0
        while queue:
            nid = queue.popleft()
            visited += 1
            # Find nodes that depend on nid
            for other in self.nodes.values():
                if nid in other.depends_on:
                    in_degree[other.id] -= 1
                    if in_degree[other.id] == 0:
                        queue.append(other.id)

        return visited < len(self.nodes)

    def validate(self):
        """Raise CyclicDependencyError if graph has cycles."""
        if self.has_cycle():
            raise CyclicDependencyError("Task graph contains a dependency cycle")

    def topological_order(self) -> list[TaskNode]:
        """Return all nodes in topological order (Kahn's algorithm).

        Independent nodes preserve insertion order.
        """
        in_degree = {nid: 0 for nid in self.nodes}
        for node in self.nodes.values():
            for dep in node.depends_on:
                if dep in self.nodes:
                    in_degree[node.id] += 1

        # Use a sorted queue for stable ordering of independent tasks
        queue = sorted(
            [nid for nid, deg in in_degree.items() if deg == 0],
            key=lambda nid: self.nodes[nid]._order,
        )
        result = []
        while queue:
            nid = queue.pop(0)
            result.append(self.nodes[nid])
            # Find dependents
            newly_ready = []
            for other in self.nodes.values():
                if nid in other.depends_on:
                    in_degree[other.id] -= 1
                    if in_degree[other.id] == 0:
                        newly_ready.append(other.id)
            # Sort newly ready by insertion order for stability
            newly_ready.sort(key=lambda nid: self.nodes[nid]._order)
            queue.extend(newly_ready)

        return result

    def find_parallel_batches(self, max_batch_size: int = 3) -> list[list[TaskNode]]:
        """Find groups of independent tasks that can run in parallel.

        Returns a list of batches. Each batch contains tasks that have
        no dependencies on each other and can execute simultaneously
        in separate worktrees. Tasks are sorted by priority within each batch.
        """
        batches = []
        # Simulate execution: repeatedly find ready tasks, "execute" a batch
        simulated_done = {n.id for n in self.nodes.values() if n.done}
        remaining = {n.id for n in self.nodes.values() if not n.done}

        while remaining:
            ready = []
            for nid in remaining:
                node = self.nodes[nid]
                all_deps_done = all(
                    dep in simulated_done or dep not in self.nodes
                    for dep in node.depends_on
                )
                if all_deps_done:
                    ready.append(node)

            if not ready:
                break  # deadlock / cycle

            # Sort by priority then insertion order
            ready.sort(key=lambda n: (n.priority_value, n._order))
            batch = ready[:max_batch_size]
            batches.append(batch)

            for node in batch:
                simulated_done.add(node.id)
                remaining.discard(node.id)

        return batches

    def critical_path(self) -> list[TaskNode]:
        """Find the longest dependency chain (critical path).

        The critical path determines the minimum number of sequential
        steps needed to complete all tasks, even with infinite parallelism.
        """
        if not self.nodes:
            return []

        # Compute longest path from each node (memoized)
        cache: dict[str, int] = {}

        def _longest(nid: str) -> int:
            if nid in cache:
                return cache[nid]
            node = self.nodes.get(nid)
            if not node:
                return 0
            # Find all nodes that depend on this one
            dependents = [
                n.id for n in self.nodes.values()
                if nid in n.depends_on and not n.done
            ]
            if not dependents:
                cache[nid] = 1
                return 1
            max_downstream = max(_longest(d) for d in dependents)
            cache[nid] = 1 + max_downstream
            return cache[nid]

        # Find the root(s) — nodes with no dependencies
        undone = [n for n in self.nodes.values() if not n.done]
        if not undone:
            return []

        for node in undone:
            _longest(node.id)

        # Reconstruct path from the node with longest chain
        start = max(undone, key=lambda n: cache.get(n.id, 0))
        path = [start]
        current = start
        while True:
            dependents = [
                self.nodes[n.id] for n in self.nodes.values()
                if current.id in n.depends_on and not n.done
            ]
            if not dependents:
                break
            nxt = max(dependents, key=lambda n: cache.get(n.id, 0))
            path.append(nxt)
            current = nxt
        return path

    def blocked_tasks(self) -> list[tuple[TaskNode, list[str]]]:
        """Find tasks that are blocked and what blocks them.

        Returns list of (task, [blocking_task_ids]).
        """
        blocked = []
        for node in self.nodes.values():
            if node.done:
                continue
            blocking = [
                dep for dep in node.depends_on
                if dep in self.nodes and not self.nodes[dep].done
            ]
            if blocking:
                blocked.append((node, blocking))
        return blocked

    def summary(self) -> dict:
        """Summary stats for the task graph."""
        undone = [n for n in self.nodes.values() if not n.done]
        ready = self.find_ready()
        blocked = self.blocked_tasks()
        batches = self.find_parallel_batches()
        crit = self.critical_path()
        return {
            "total": len(self.nodes),
            "done": len(self.nodes) - len(undone),
            "remaining": len(undone),
            "ready_now": len(ready),
            "blocked": len(blocked),
            "parallel_batches": len(batches),
            "critical_path_length": len(crit),
            "min_sequential_steps": len(batches),
        }

    def to_backlog(self) -> str:
        """Serialize graph back to backlog markdown format."""
        lines = []
        for node in sorted(self.nodes.values(), key=lambda n: n._order):
            check = "x" if node.done else " "
            parts = [f"- [{check}] [{node.id}] {node.name}"]
            if node.depends_on:
                parts.append(f"(depends: {', '.join(node.depends_on)})")
            if node.agent_hint:
                parts.append(f"[agent: {node.agent_hint}]")
            if node.priority != "medium":
                parts.append(f"(priority: {node.priority})")
            lines.append(" ".join(parts))
        return "\n".join(lines)
