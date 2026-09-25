#!/usr/bin/env python3
"""Control-plane API (Phase 5) — the surface self-serve tenants hit.

Admin endpoints (bearer = AUTOAGENT_ADMIN_TOKEN) provision/list/delete tenants.
Tenant endpoints (bearer = the per-tenant token issued at provision) enqueue and
inspect that tenant's own session jobs — never another tenant's.

This is the orchestration layer over the isolation primitives: POST /tenants calls
provisioning (registry + volume + vault), POST /sessions enqueues a job for a
worker to run in the tenant's sandbox. It does not run sessions inline.

Run: uvicorn control_api:app  (set AUTOAGENT_ADMIN_TOKEN first).
"""
import hashlib
import os
import secrets
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

import job_queue
import provisioning

app = FastAPI(title="AutoAgent Control Plane")


# ── token auth ──────────────────────────────────────────────────────────────

def _bearer(authorization: Optional[str]) -> Optional[str]:
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    return authorization.split(" ", 1)[1].strip()


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def issue_tenant_token(tenant_id: str) -> str:
    """Mint a tenant API token, store only its hash in the registry, return the
    plaintext ONCE (the caller shows it to the tenant; we never persist it)."""
    token = secrets.token_urlsafe(32)
    with provisioning._registry_lock():
        reg = provisioning._load_registry()
        if tenant_id not in reg:
            raise KeyError(tenant_id)
        reg[tenant_id]["token_hash"] = _hash(token)
        provisioning._save_registry(reg)
    return token


def resolve_tenant_by_token(token: str) -> Optional[str]:
    h = _hash(token)
    for tid, rec in provisioning._load_registry().items():
        stored = rec.get("token_hash")
        if stored and secrets.compare_digest(stored, h) and rec.get("status") == "active":
            return tid
    return None


def require_admin(authorization: Optional[str] = Header(None)) -> None:
    admin = os.environ.get("AUTOAGENT_ADMIN_TOKEN")
    if not admin:
        raise HTTPException(503, "control plane admin token not configured")
    token = _bearer(authorization)
    if not token or not secrets.compare_digest(token, admin):
        raise HTTPException(401, "invalid admin token")


def require_tenant(authorization: Optional[str] = Header(None)) -> str:
    token = _bearer(authorization)
    tid = resolve_tenant_by_token(token) if token else None
    if not tid:
        raise HTTPException(401, "invalid tenant token")
    return tid


# ── models ──────────────────────────────────────────────────────────────────

class ProvisionBody(BaseModel):
    tenant_id: str
    plan: str = "concierge"
    byok_key: Optional[str] = None


class SessionBody(BaseModel):
    project: Optional[str] = None
    session_type: str = "work"


# ── health ──────────────────────────────────────────────────────────────────

@app.get("/healthz")
def healthz():
    return {"ok": True}


# ── admin: tenant lifecycle ─────────────────────────────────────────────────

@app.post("/tenants", status_code=201, dependencies=[Depends(require_admin)])
def create_tenant(body: ProvisionBody):
    try:
        rec = provisioning.provision_tenant(
            body.tenant_id, byok_key=body.byok_key, plan=body.plan)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(400, str(e))
    token = issue_tenant_token(rec.tenant_id)
    # Return the token ONCE — it is never retrievable again.
    return {"tenant": _public(rec), "api_token": token}


@app.get("/tenants", dependencies=[Depends(require_admin)])
def list_tenants():
    return {"tenants": [_public(t) for t in provisioning.list_tenants()]}


@app.get("/tenants/{tenant_id}", dependencies=[Depends(require_admin)])
def get_tenant(tenant_id: str):
    rec = provisioning.get_tenant(tenant_id)
    if not rec:
        raise HTTPException(404, "no such tenant")
    return {"tenant": _public(rec)}


@app.delete("/tenants/{tenant_id}", dependencies=[Depends(require_admin)])
def delete_tenant(tenant_id: str, delete_data: bool = False):
    ok = provisioning.deprovision_tenant(tenant_id, delete_data=delete_data)
    if not ok:
        raise HTTPException(404, "no such tenant")
    return {"deprovisioned": tenant_id, "delete_data": delete_data}


# ── tenant: sessions ────────────────────────────────────────────────────────

@app.post("/sessions", status_code=202)
def enqueue_session(body: SessionBody, tenant_id: str = Depends(require_tenant)):
    job_id = job_queue.enqueue(tenant_id, project=body.project,
                               session_type=body.session_type)
    return {"job_id": job_id, "status": job_queue.STATUS_QUEUED}


@app.get("/sessions")
def my_sessions(tenant_id: str = Depends(require_tenant)):
    return {"jobs": job_queue.list_jobs(tenant_id)}


@app.get("/sessions/{job_id}")
def session_status(job_id: str, tenant_id: str = Depends(require_tenant)):
    job = job_queue.get_job(job_id)
    # Scope: a tenant may only see its own jobs. A foreign/absent job is 404 either
    # way, so existence of another tenant's job isn't even leaked.
    if not job or job.get("tenant_id") != tenant_id:
        raise HTTPException(404, "no such job")
    return job


def _public(rec) -> dict:
    """Registry record minus internals (never expose data_root or token_hash)."""
    return {"tenant_id": rec.tenant_id, "plan": rec.plan,
            "status": rec.status, "created_at": rec.created_at}
