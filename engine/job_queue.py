#!/usr/bin/env python3
"""Session job queue for the control plane (Phase 5).

`POST /sessions` doesn't run a session inline (they take minutes) — it enqueues a
job that a worker claims and runs. File-based FIFO for now (one JSON per job under
AGENCY_HOME/jobs), which is enough for a single control-plane host; it moves to
Postgres/Redis when the control DB does. Every job is tenant-scoped so a worker
and the API can only ever see/act on the right tenant's work.
"""
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from tenant import require_valid_tenant_id

STATUS_QUEUED = "queued"
STATUS_RUNNING = "running"
STATUS_DONE = "done"
STATUS_FAILED = "failed"


def _jobs_dir() -> Path:
    import registry
    return registry.AGENCY_HOME / "jobs"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _job_path(job_id: str) -> Path:
    if not job_id or "/" in job_id or job_id in (".", ".."):
        raise ValueError(f"invalid job_id: {job_id!r}")
    return _jobs_dir() / f"{job_id}.json"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, job: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(job, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def enqueue(tenant_id: str, *, project: Optional[str] = None,
            session_type: str = "work") -> str:
    require_valid_tenant_id(tenant_id)
    job_id = uuid.uuid4().hex
    _write(_job_path(job_id), {
        "job_id": job_id,
        "tenant_id": tenant_id,
        "project": project,
        "session_type": session_type,
        "status": STATUS_QUEUED,
        "created_at": _now(),
        "updated_at": _now(),
    })
    return job_id


def get_job(job_id: str) -> Optional[dict]:
    path = _job_path(job_id)
    return _read(path) if path.exists() else None


def list_jobs(tenant_id: Optional[str] = None) -> list:
    d = _jobs_dir()
    if not d.exists():
        return []
    jobs = [_read(p) for p in d.glob("*.json")]
    if tenant_id is not None:
        jobs = [j for j in jobs if j.get("tenant_id") == tenant_id]
    return sorted(jobs, key=lambda j: j.get("created_at", ""))


def mark(job_id: str, status: str) -> None:
    path = _job_path(job_id)
    job = _read(path)
    job["status"] = status
    job["updated_at"] = _now()
    _write(path, job)


def claim_next() -> Optional[dict]:
    """Oldest queued job → running. For a worker; simple, not multi-worker-safe
    (a lock lands with the Postgres move)."""
    for job in list_jobs():
        if job.get("status") == STATUS_QUEUED:
            mark(job["job_id"], STATUS_RUNNING)
            return get_job(job["job_id"])
    return None
