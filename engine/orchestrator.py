#!/usr/bin/env python3
"""Orchestrator — agent routing, task parsing, prompt building."""
import re
from pathlib import Path
from typing import Optional

from registry import ProjectContext, AGENCY_HOME
from task_graph import TaskGraph
from agent_utils import list_agents, load_agent_prompt, generate_agent_md  # noqa: F401


def parse_agent_hint(line: str) -> Optional[str]:
    """Extract [agent: name] hint from a backlog line."""
    m = re.search(r'\[agent:\s*([a-zA-Z0-9_-]+)\]', line)
    return m.group(1) if m else None


def build_agent_boot_prompt(ctx: ProjectContext, agent_name: Optional[str], session_type: str) -> str:
    """Build the boot prompt for Claude, optionally scoped to a specific agent.

    When an agent is assigned:
      1. Injects condensed agent .md inline (expertise, principles, first skill)
      2. Filters skills list to only agent-relevant ones
      3. Injects agent memory context if available
    """
    from agent_utils import condense_agent_prompt, filter_skills_for_agent, load_agent_prompt

    boot = f"You are working on the project '{ctx.name}'. "

    if agent_name:
        # Inject condensed agent expertise directly into boot prompt
        agent_md = load_agent_prompt(ctx, agent_name)
        condensed = condense_agent_prompt(agent_md, max_chars=2500)
        if condensed:
            boot += f"\n\n--- AGENT ROLE: {agent_name} ---\n{condensed}\n--- END AGENT ROLE ---\n\n"
        else:
            boot += f"You are the {agent_name} agent. Read .autoagent/agents/{agent_name}.md for your role. "

        # Filter skills to agent-relevant subset
        try:
            from agent_index import extract_agent_keywords
            agent_kw = extract_agent_keywords(agent_md)
            relevant_skills = filter_skills_for_agent(ctx.all_skills(), agent_kw)
            skills_names = ", ".join(p.name for p in relevant_skills)
        except Exception:
            skills_names = ", ".join(p.name for p in ctx.all_skills())

        # Inject agent memory if available
        try:
            from agent_memory import inject_agent_memory_context
            mem_ctx = inject_agent_memory_context(ctx, agent_name, max_chars=400)
            if mem_ctx:
                boot += f"\n{mem_ctx}\n"
        except Exception:
            pass
    else:
        skills_names = ", ".join(p.name for p in ctx.all_skills())

    boot += (
        f"Read .autoagent/PROMPT.md for session rules. "
        f"Read .autoagent/PROJECT.md for project-specific rules. "
        f"Read .autoagent/NORTH_STAR.md for the mission and success metrics. "
        f"Read .autoagent/memory/activity_log.md, .autoagent/memory/backlog.md, "
        f".autoagent/memory/knowledge.md, .autoagent/memory/current_task.md for context. "
        f"Available skills in .autoagent/skills/: {skills_names}. "
        f"Session type: {session_type.upper()}. "
    )

    if session_type == "meta":
        boot += "Read .autoagent/meta/PROMPT.md for this session's instructions. "
    if session_type in ("brain", "deep"):
        boot += "Read .autoagent/meta/BRAIN_PROMPT.md for this session's instructions. "
    if session_type == "audit":
        boot += (
            "This is a SECURITY AUDIT session. Read .autoagent/skills/security.md and .autoagent/skills/audit.md for the audit checklist. "
            "Scan ALL source files for: hardcoded secrets, auth bypasses, injection vectors, "
            "exposed sensitive data, missing rate limiting, weak JWT secrets, CORS misconfig. "
            "Write findings to .autoagent/memory/security_findings.md with severity levels. "
            "For CRITICAL findings, add fix tasks to .autoagent/memory/backlog.md immediately. "
            "You are the security-auditor agent. Think like an attacker. "
        )

    boot += "Follow the instructions exactly."
    return boot


def parse_orchestrator_output(output: str) -> dict:
    """Parse TASK/AGENT/REASON from orchestrator output."""
    result = {"task": None, "agent": None}

    task_m = re.search(r'TASK:\s*(.+)', output)
    if task_m:
        result["task"] = task_m.group(1).strip()

    agent_m = re.search(r'AGENT:\s*(\S+)', output)
    if agent_m:
        agent = agent_m.group(1).strip()
        if agent.lower() in ("none", "n/a", "generic", "-"):
            agent = None
        result["agent"] = agent

    return result


def get_ready_tasks(ctx: ProjectContext) -> list[dict]:
    """Load backlog, build task graph, return ready (unblocked) tasks."""
    backlog_file = ctx.memory_dir / "backlog.md"
    if not backlog_file.exists():
        return []
    text = backlog_file.read_text(encoding="utf-8")
    graph = TaskGraph.from_backlog(text)
    ready = graph.find_ready()
    return [
        {"id": n.id, "name": n.name, "agent_hint": n.agent_hint,
         "depends_on": n.depends_on, "priority": n.priority}
        for n in ready
    ]



def build_orchestrator_prompt(ctx: Optional[ProjectContext]) -> str:
    """Build the prompt for the orchestrator phase (task + agent selection).

    Loads from templates/ORCHESTRATOR_PROMPT.md and injects the agent roster.
    """
    agent_roster = ""
    ready_tasks_section = ""
    if ctx:
        agents = list_agents(ctx)
        if agents:
            agent_roster = "\n## Available agents\n\n"
            agent_roster += "| Agent | Description |\n|---|---|\n"
            for a in agents:
                agent_roster += f"| {a['name']} | {a['description']} |\n"

        ready = get_ready_tasks(ctx)
        if ready:
            ready_tasks_section = "\n## Ready tasks (dependencies satisfied)\n\n"
            ready_tasks_section += "| ID | Task | Agent hint | Blocked by |\n|---|---|---|---|\n"
            for t in ready:
                hint = t["agent_hint"] or "-"
                deps = ", ".join(t["depends_on"]) if t["depends_on"] else "-"
                ready_tasks_section += f"| {t['id']} | {t['name']} | {hint} | {deps} |\n"

    template_path = AGENCY_HOME / "templates" / "ORCHESTRATOR_PROMPT.md"
    if template_path.exists():
        template = template_path.read_text(encoding="utf-8")
        return template.replace("{agent_roster}", agent_roster).replace(
            "{ready_tasks}", ready_tasks_section
        )

    # Fallback: inline prompt if template not found
    return f"""You are the orchestrator. Your job is to pick the next task and assign the right agent.

## Instructions

1. Read .autoagent/memory/current_task.md — if there's an in-progress task, continue it
2. Read .autoagent/memory/backlog.md — pick the highest-impact unchecked task
3. Look for [agent: name] hints in the task — use them if they make sense
4. Match the task to the best agent from the roster below
5. Output EXACTLY this format (nothing else):

```
TASK: <task name from backlog>
AGENT: <agent-name from roster, or "none" if no specialist needed>
REASON: <one sentence why this agent>
```
{agent_roster}
{ready_tasks_section}
## Rules

- Pick ONE task only
- If ready tasks are listed above, pick from those first (their dependencies are satisfied)
- If the task has an [agent: X] hint, prefer that agent
- If no agent matches, output AGENT: none
- Never pick a task marked "blocked" or "needs-human"
- Do not start working on the task — just pick and assign
"""


def _count_unchecked_backlog(backlog_text: str) -> int:
    """Count unchecked items in backlog text.

    Counts both '- [ ]' checkbox items and '### N.' numbered headings
    (the two backlog formats used in practice).
    """
    count = 0
    for line in backlog_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("- [ ]") or stripped.startswith("### "):
            count += 1
    return count


def _find_test_gaps(project_root: Path) -> list[dict]:
    """Scan project_root for Python modules without corresponding test files.

    Returns list of {"module": "name.py", "has_tests": bool, "test_count": int}.
    """
    gaps = []
    # Find all .py files in project root (non-recursive first level + common dirs)
    py_files = []
    for p in project_root.glob("*.py"):
        if not p.name.startswith("test_") and not p.name.startswith("__"):
            py_files.append(p)
    # Also check src/ and engine/ subdirs
    for subdir in ["src", "engine", "lib", "app"]:
        sd = project_root / subdir
        if sd.exists():
            for p in sd.glob("*.py"):
                if not p.name.startswith("test_") and not p.name.startswith("__"):
                    py_files.append(p)

    # Find all test files
    test_files = set()
    for p in project_root.rglob("test_*.py"):
        test_files.add(p.stem)  # e.g., "test_app"

    for py_file in py_files:
        module_name = py_file.stem
        expected_test = f"test_{module_name}"
        has_tests = expected_test in test_files

        # Count test functions in the test file if it exists
        test_count = 0
        if has_tests:
            for tf in project_root.rglob(f"{expected_test}.py"):
                content = tf.read_text(encoding="utf-8", errors="ignore")
                test_count += len(re.findall(r"^\s*def test_", content, re.M))  # counts class-based tests too
                break

        gaps.append({
            "module": py_file.name,
            "has_tests": has_tests,
            "test_count": test_count,
        })

    return gaps


def auto_generate_backlog(ctx: "ProjectContext") -> list[str]:
    """Generate EARS-quality backlog items when backlog has <3 unchecked items.
    Scans for: test gaps (no test file / <5 tests), North Star gaps.

    Returns list of EARS-formatted strings (trigger + test name + file scope).
    """
    backlog_file = ctx.memory_dir / "backlog.md"
    backlog_text = ""
    if backlog_file.exists():
        backlog_text = backlog_file.read_text(encoding="utf-8")

    if _count_unchecked_backlog(backlog_text) >= 3:
        return []

    items = []

    # 1. Test gaps
    gaps = _find_test_gaps(ctx.project_root)
    for gap in gaps:
        mod = gap["module"]
        mod_stem = mod.replace(".py", "")
        if not gap["has_tests"]:
            items.append(
                f"When {mod} has zero test coverage, add unit tests. "
                f"Test: `test_{mod_stem}_basic`. "
                f"Files: {mod}, test_{mod_stem}.py (~3 tests)"
            )
        elif gap["test_count"] < 5:
            items.append(
                f"When {mod} has only {gap['test_count']} tests (<5), "
                f"add tests for uncovered branches. "
                f"Test: `test_{mod_stem}_edge_cases`. "
                f"Files: test_{mod_stem}.py (~{5 - gap['test_count']} tests)"
            )

    # 2. North Star gaps
    ns_file = ctx.project_home / "NORTH_STAR.md"
    if ns_file.exists():
        ns_text = ns_file.read_text(encoding="utf-8")
        for line in ns_text.splitlines():
            if "|" in line and "---" not in line and "Metric" not in line:
                parts = [p.strip() for p in line.split("|") if p.strip()]
                if len(parts) >= 3:
                    metric, current, target = parts[0], parts[1], parts[2]
                    try:
                        cur_val = int(current)
                        tgt_val = int(target)
                        if cur_val < tgt_val:
                            items.append(
                                f"When {metric.lower()} is {cur_val} (target: {tgt_val}), "
                                f"close the gap. "
                                f"Test: `test_{metric.lower().replace(' ', '_')}_improvement`. "
                                f"Files: relevant module (~2 tests)"
                            )
                    except ValueError:
                        pass
    return items

from context_utils import recite_todos, append_context  # noqa: E402, F401
