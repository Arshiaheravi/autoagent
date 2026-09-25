#!/usr/bin/env python3
"""Session Trace Capture — full reasoning traces for meta-agent analysis.

Inspired by kevinrgu/autoagent ATIF format. Captures every step of a
Claude CLI session: text reasoning, tool calls, tool results, errors.

The meta-agent reads traces to understand WHY sessions failed, not just
THAT they failed. This enables targeted harness improvements.

Trace format (JSONL):
  .autoagent/traces/session_{num}.jsonl
  Each line: {"step": N, "type": "text|tool_call|tool_result|error", ...}

Usage:
    tracer = SessionTracer(ctx, session_num)
    tracer.record_text("I'll start by reading the backlog...")
    tracer.record_tool_call("Read", {"file_path": "backlog.md"})
    tracer.record_tool_result("Read", "backlog contents...")
    tracer.save()
"""
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from registry import ProjectContext


def _session_id(p: Path) -> int:
    """Numeric session id from a `session_{n}.jsonl` filename. Lexicographic
    sorting is wrong once ids reach two digits (session_10 < session_2); sort
    on this instead. Non-numeric names sort first (-1)."""
    m = re.search(r"session_(\d+)", p.stem)
    return int(m.group(1)) if m else -1

logger = logging.getLogger(__name__)


class SessionTracer:
    """Captures full reasoning trace for a session."""

    def __init__(self, ctx: ProjectContext, session_num: int, agent: str = ""):
        self.ctx = ctx
        self.session_num = session_num
        self.agent = agent
        self.steps: list[dict] = []
        self.step_counter = 0
        self.start_time = datetime.now().isoformat()
        self.traces_dir = ctx.memory_dir / "traces"
        self.traces_dir.mkdir(parents=True, exist_ok=True)

    def _add(self, entry: dict):
        self.step_counter += 1
        entry["step"] = self.step_counter
        entry["timestamp"] = datetime.now().isoformat()
        self.steps.append(entry)

    def record_text(self, text: str):
        """Record agent text output (reasoning)."""
        self._add({"type": "text", "content": text[:500]})

    def record_tool_call(self, tool_name: str, tool_input: dict):
        """Record a tool call before execution."""
        self._add({
            "type": "tool_call",
            "tool": tool_name,
            "input": _truncate_input(tool_input),
        })

    def record_tool_result(self, tool_name: str, result: str, success: bool = True):
        """Record a tool result after execution."""
        self._add({
            "type": "tool_result",
            "tool": tool_name,
            "success": success,
            "output": result[:300],
        })

    def record_error(self, error: str):
        """Record an error or failure."""
        self._add({"type": "error", "message": error[:500]})

    def save(self, success: bool = True, summary: str = ""):
        """Save the trace to disk as JSONL."""
        trace_file = self.traces_dir / f"session_{self.session_num}.jsonl"

        # Write header
        header = {
            "schema": "autoagent-trace-v1",
            "session_num": self.session_num,
            "project": self.ctx.name,
            "agent": self.agent,
            "started_at": self.start_time,
            "finished_at": datetime.now().isoformat(),
            "total_steps": self.step_counter,
            "success": success,
            "summary": summary[:200],
        }

        with open(trace_file, "w", encoding="utf-8") as f:
            f.write(json.dumps(header) + "\n")
            for step in self.steps:
                f.write(json.dumps(step, ensure_ascii=False) + "\n")

        logger.info("Trace saved: %s (%d steps)", trace_file.name, self.step_counter)
        # Keep only last 20 traces to avoid disk bloat
        _prune_traces(self.traces_dir, keep=20)

    def get_failure_summary(self) -> str:
        """Extract a failure diagnosis from the trace.

        Returns a concise summary of where things went wrong,
        suitable for the meta-agent to read.
        """
        errors = [s for s in self.steps if s["type"] == "error"]
        failed_tools = [s for s in self.steps if s["type"] == "tool_result" and not s.get("success", True)]
        last_text = [s for s in self.steps if s["type"] == "text"][-3:] if self.steps else []

        lines = []
        if errors:
            lines.append("ERRORS:")
            for e in errors[-3:]:
                lines.append(f"  Step {e['step']}: {e['message']}")
        if failed_tools:
            lines.append("FAILED TOOLS:")
            for t in failed_tools[-3:]:
                lines.append(f"  Step {t['step']}: {t['tool']} — {t.get('output', '')[:100]}")
        if last_text:
            lines.append("LAST REASONING:")
            for t in last_text:
                lines.append(f"  Step {t['step']}: {t['content'][:100]}")

        return "\n".join(lines) if lines else "No failure details captured."


def load_trace(ctx: ProjectContext, session_num: int) -> Optional[list[dict]]:
    """Load a trace file and return list of steps."""
    trace_file = ctx.memory_dir / "traces" / f"session_{session_num}.jsonl"
    if not trace_file.exists():
        return None
    steps = []
    for line in trace_file.read_text(encoding="utf-8").splitlines():
        if line.strip():
            steps.append(json.loads(line))
    return steps


def load_last_failed_trace(ctx: ProjectContext) -> Optional[list[dict]]:
    """Find and load the most recent failed session trace."""
    traces_dir = ctx.memory_dir / "traces"
    if not traces_dir.exists():
        return None
    for trace_file in sorted(traces_dir.glob("session_*.jsonl"), key=_session_id, reverse=True):
        try:
            first_line = trace_file.read_text(encoding="utf-8").split("\n", 1)[0]
            header = json.loads(first_line)
            if not header.get("success", True):
                return load_trace(ctx, header["session_num"])
        except Exception:
            continue
    return None


def format_trace_for_meta(trace: list[dict], max_chars: int = 2000) -> str:
    """Format a trace into a readable summary for the meta-agent.

    Focuses on tool calls and errors — skips verbose text.
    """
    if not trace:
        return "No trace data."

    header = trace[0] if trace else {}
    lines = [
        f"Session #{header.get('session_num', '?')} [{header.get('agent', 'generic')}] "
        f"— {'SUCCESS' if header.get('success') else 'FAILED'}",
        f"Steps: {header.get('total_steps', 0)} | {header.get('started_at', '')[:16]}",
        "",
    ]

    for step in trace[1:]:  # skip header
        st = step.get("type", "")
        sn = step.get("step", "?")
        if st == "tool_call":
            inp = step.get("input", {})
            target = inp.get("file_path", inp.get("command", ""))
            lines.append(f"  [{sn}] {step['tool']}({str(target)[:60]})")
        elif st == "error":
            lines.append(f"  [{sn}] ERROR: {step['message'][:80]}")
        elif st == "tool_result" and not step.get("success", True):
            lines.append(f"  [{sn}] FAIL: {step['tool']} — {step.get('output', '')[:60]}")

        if len("\n".join(lines)) > max_chars:
            lines.append("  ... (truncated)")
            break

    return "\n".join(lines)


def _truncate_input(inp: dict) -> dict:
    """Truncate tool input values to keep traces manageable."""
    truncated = {}
    for k, v in inp.items():
        if isinstance(v, str) and len(v) > 200:
            truncated[k] = v[:200] + "..."
        else:
            truncated[k] = v
    return truncated


def _prune_traces(traces_dir: Path, keep: int = 20):
    """Keep only the N most recent trace files."""
    traces = sorted(traces_dir.glob("session_*.jsonl"), key=_session_id)
    for old in traces[:-keep]:
        old.unlink(missing_ok=True)
