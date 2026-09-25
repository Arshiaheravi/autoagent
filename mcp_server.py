#!/usr/bin/env python3
"""AutoAgent MCP server — Tier 1 (bounded, synchronous) surface.

Exposes the agency's reusable bounded operations as MCP tools so any
MCP client (Claude Code, desktop, cron agents, other repos) can call the
council reviews, the advisor pattern, and usage/cost queries directly —
no shelling out to the CLI, no parsing stdout.

Scope (Tier 1 ONLY):
    - advisor_consult   advise()                  advisor.py
    - codex_review      codex_review()            council/reviews.py
    - ux_review         ux_review()               council/reviews.py
    - design_review     design_council()          council/reviews.py
    - usage_summary     get_*_usage()             usage.py
    - predict_cost      predict_session_cost()    cost_predictor.py
    - council_spend     get_provider_spending()   council_usage.py

NOT in scope (deliberately):
    - convene_council / debate  → Tier 2, needs async job-id + polling
      (single call is 5-40 min; known 12-min hang risk). Add in phase 2.
    - run_session / run_continuous / supervisors → Tier 3, stay on
      LaunchAgents (continuous push loops, must outlive any client).

Run:
    python3 mcp_server.py            # stdio transport (default for Claude Code)

Wire into Claude Code (.mcp.json or `claude mcp add`):
    {
      "mcpServers": {
        "autoagent": {
          "command": "python3",
          "args": ["/path/to/autoagent/mcp_server.py"]
        }
      }
    }
"""
from __future__ import annotations

import json
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

# Engine modules use bare imports (`import registry`, `from council.reviews ...`),
# so engine/ must be on sys.path before importing them.
_ENGINE = Path(__file__).resolve().parent / "engine"
sys.path.insert(0, str(_ENGINE))

import registry            # noqa: E402
import usage               # noqa: E402
import advisor             # noqa: E402
import council_usage       # noqa: E402
import cost_predictor      # noqa: E402
from council.reviews import codex_review as _codex_review        # noqa: E402
from council.reviews import ux_review as _ux_review              # noqa: E402
from council.reviews import design_council as _design_council    # noqa: E402
from council.executive import convene_council as _convene_council            # noqa: E402
from council.executive import convene_council_with_debate as _convene_debate  # noqa: E402

from mcp.server.fastmcp import FastMCP  # noqa: E402

mcp = FastMCP("autoagent")

# ── T2: async council job layer ────────────────────────────────────
# convene_council / debate run 5-40 min and have a known 12-min hang risk,
# so they must NOT block an MCP request. Pattern: submit → return job_id →
# the call runs on a bounded worker pool → result persists to disk → client
# polls council_result(job_id). The per-provider spend gate (council_usage)
# still fires inside every backend; this layer adds a pre-submit refusal
# when EVERY council provider is already over budget.

# max_workers bounds concurrent council fan-outs — burn control, not perf.
_COUNCIL_POOL = ThreadPoolExecutor(max_workers=2, thread_name_prefix="council")
_JOBS_DIR = registry.AGENCY_HOME / "mcp_jobs"

# Providers the executive council fans out to (stage1). If all are over
# their monthly budget, spawning a job would only produce empty personas.
_COUNCIL_PROVIDERS = ("anthropic", "openai", "gemini", "deepseek", "xai")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _job_path(job_id: str) -> Path:
    return _JOBS_DIR / f"{job_id}.json"


def _write_job(job_id: str, payload: dict) -> None:
    """Atomically persist job state (tmp + rename) so a polling reader never
    sees a half-written file."""
    _JOBS_DIR.mkdir(parents=True, exist_ok=True)
    tmp = _job_path(job_id).with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    tmp.replace(_job_path(job_id))


def _run_council_job(job_id: str, base: dict, fn, kwargs: dict) -> None:
    """Worker body: run the (blocking) council call, persist the outcome."""
    try:
        result = fn(**kwargs)
        base.update(status="done", finished_at=_now(), result=result)
    except Exception as e:
        base.update(status="error", finished_at=_now(),
                    error=f"{type(e).__name__}: {str(e)[:500]}")
    _write_job(job_id, base)


def _submit(kind: str, fn, kwargs: dict, question: str) -> dict:
    """Pre-check budget, register a job, dispatch to the pool, return job_id."""
    allowed = [p for p in _COUNCIL_PROVIDERS
               if council_usage.check_provider_budget(p)[0]]
    if not allowed:
        return {"status": "refused",
                "error": "all council providers over monthly budget",
                "providers": list(_COUNCIL_PROVIDERS)}
    job_id = uuid.uuid4().hex[:12]
    base = {"job_id": job_id, "kind": kind, "question": question[:500],
            "status": "running", "created_at": _now(),
            "providers_in_budget": allowed}
    _write_job(job_id, base)
    _COUNCIL_POOL.submit(_run_council_job, job_id, base, fn, kwargs)
    return {"job_id": job_id, "status": "running",
            "providers_in_budget": allowed,
            "poll": "call council_result with this job_id"}


def _ctx(project: str):
    """Load a ProjectContext by registered name. Raises KeyError if unknown."""
    return registry.get(project)


def _session_num(ctx) -> int:
    """Best-effort current session counter for review logging. 0 if absent."""
    cf = ctx.counter_file
    if cf.exists():
        try:
            return json.loads(cf.read_text(encoding="utf-8")).get("count", 0)
        except Exception:
            return 0
    return 0


@mcp.tool()
def list_projects() -> list[dict]:
    """List registered agency projects (name, path, session count)."""
    return registry.list_projects()


@mcp.tool()
def advisor_consult(task: str, system_prompt: str = "You are a senior staff engineer advising on a decision.") -> str:
    """Run the Advisor pattern (Sonnet executor + Opus advisor) on a task.

    Single deliberation turn. Returns the executor's final text. Requires
    ANTHROPIC_API_KEY — bills API rates, not Max. Use for hard judgment
    calls, not routine work.
    """
    return advisor.advise(system_prompt=system_prompt, task=task)


@mcp.tool()
def codex_review(project: str) -> dict:
    """Codex code review of the project's latest commit diff (HEAD~1).

    Returns {"status": "lgtm"|"issues"|"skipped", "review": str}. 60s cap.
    """
    ctx = _ctx(project)
    return _codex_review(ctx, _session_num(ctx))


@mcp.tool()
def ux_review(project: str) -> dict:
    """UX-focused council review of frontend changes in the latest diff.

    Skips if no frontend files changed. 120s cap.
    Returns {"status": "pass"|"issues"|"skipped", "review": str}.
    """
    ctx = _ctx(project)
    return _ux_review(ctx, _session_num(ctx))


@mcp.tool()
def design_review(project: str, screenshot_path: str | None = None) -> dict:
    """Multi-model design council (GPT + Gemini vision) on a screenshot.

    Returns {"status", "score", "reviews", "synthesis"}. 120s per model.
    """
    ctx = _ctx(project)
    return _design_council(ctx, _session_num(ctx), screenshot_path=screenshot_path)


@mcp.tool()
def usage_summary(project: str, period: str = "today") -> dict:
    """Token + cost usage for a project. period = today | week | all."""
    ctx = _ctx(project)
    if period == "week":
        return usage.get_weekly_usage(ctx)
    if period == "all":
        return usage.get_all_time_usage(ctx)
    return usage.get_today_usage(ctx)


@mcp.tool()
def predict_cost(project: str, session_type: str = "work") -> dict:
    """Forecast the cost of the next session from this project's history."""
    ctx = _ctx(project)
    return cost_predictor.predict_session_cost(ctx, session_type)


@mcp.tool()
def council_spend(period: str = "month") -> dict:
    """Council API spend bucketed by provider. period = week | month | all."""
    return council_usage.get_provider_spending(period=period)


@mcp.tool()
def council_convene(question: str, context: str = "", mode: str = "executive") -> dict:
    """Start an async 3-stage council (fan-out → rank → synthesize) on a question.

    Returns a job_id immediately; the council runs ~5-15 min in the
    background. Poll council_result(job_id) for the verdict. Refused if every
    provider is over its monthly budget.
    """
    return _submit("convene", _convene_council,
                   {"question": question, "context": context, "mode": mode}, question)


@mcp.tool()
def council_debate(question: str, context: str = "", max_rounds: int = 3) -> dict:
    """Start an async council WITH a debate loop — re-converges until HIGH
    confidence or max_rounds (benches if it can't). ~15-40 min.

    Returns a job_id immediately. Poll council_result(job_id).
    """
    return _submit("debate", _convene_debate,
                   {"question": question, "context": context, "max_rounds": max_rounds}, question)


@mcp.tool()
def council_result(job_id: str) -> dict:
    """Fetch an async council job by id. status = running|done|error|unknown.

    When done, the full council dict is under "result".
    """
    p = _job_path(job_id)
    if not p.exists():
        return {"job_id": job_id, "status": "unknown"}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        return {"job_id": job_id, "status": "error", "error": f"read failed: {e}"}


@mcp.tool()
def council_jobs(limit: int = 20) -> list[dict]:
    """List recent async council jobs (newest first) — id, kind, status, question."""
    if not _JOBS_DIR.exists():
        return []
    files = sorted(_JOBS_DIR.glob("*.json"),
                   key=lambda f: f.stat().st_mtime, reverse=True)[:limit]
    out = []
    for f in files:
        try:
            j = json.loads(f.read_text(encoding="utf-8"))
            out.append({k: j.get(k) for k in
                        ("job_id", "kind", "status", "question",
                         "created_at", "finished_at")})
        except Exception:
            continue
    return out


if __name__ == "__main__":
    mcp.run()
