#!/usr/bin/env python3
"""Session worker — drains the job queue, runs each session in its tenant sandbox.

Closes the self-serve loop: the control API enqueues jobs (job_queue), this worker
claims them oldest-first and runs a session scoped to the owning tenant, then marks
the job done/failed. It runs on the control-plane host; each job executes with the
tenant's AUTOAGENT_TENANT_ID + AUTOAGENT_HOME so the engine (and the sandbox runner
it spawns) confines to that tenant — one job can never touch another tenant's state.

Every loop has a HARD iteration cap — an uncapped drain is exactly the runaway that
burns budget. run_forever stops at max_iterations or an empty queue and returns.
"""
import logging
import os
import subprocess
from typing import Callable, Optional

import job_queue
import provisioning

logger = logging.getLogger(__name__)


def execute_job(job: dict) -> bool:
    """Run one session for the job's tenant. Returns True on success.

    Shells the engine CLI with the tenant's env so the session — and any sandbox
    container it launches — is scoped to that tenant. Injectable so tests exercise
    the claim→mark lifecycle without spinning a real session.
    """
    rec = provisioning.get_tenant(job.get("tenant_id", ""))
    if not rec or rec.status != "active":
        logger.warning("job %s: tenant %s not active", job.get("job_id"), job.get("tenant_id"))
        return False
    project = job.get("project")
    if not project:
        logger.warning("job %s: no project", job.get("job_id"))
        return False
    env = {
        **os.environ,
        "AUTOAGENT_TENANT_ID": rec.tenant_id,
        "AUTOAGENT_HOME": rec.data_root,
    }
    argv = ["autoagent", "run", project, "--once"]
    if job.get("session_type"):
        argv += ["--type", job["session_type"]]
    try:
        return subprocess.run(argv, env=env, timeout=3600).returncode == 0
    except Exception as e:
        logger.error("job %s execution error: %s", job.get("job_id"), e)
        return False


def run_once(execute: Callable[[dict], bool] = execute_job) -> Optional[dict]:
    """Claim the oldest queued job, run it, mark done/failed. None if queue empty."""
    job = job_queue.claim_next()
    if not job:
        return None
    try:
        ok = bool(execute(job))
    except Exception as e:                       # never let one job kill the worker
        logger.error("job %s: unhandled %s", job.get("job_id"), e)
        ok = False
    job_queue.mark(job["job_id"],
                   job_queue.STATUS_DONE if ok else job_queue.STATUS_FAILED)
    return job_queue.get_job(job["job_id"])


def run_forever(max_iterations: int = 100,
                execute: Callable[[dict], bool] = execute_job) -> int:
    """Drain up to max_iterations jobs, then stop (HARD cap — no uncapped loop).
    Stops early on an empty queue. Returns how many jobs it processed."""
    if max_iterations <= 0:
        raise ValueError("max_iterations must be positive (hard loop cap)")
    processed = 0
    while processed < max_iterations:
        if run_once(execute) is None:
            break
        processed += 1
    return processed
