"""Control-plane API — admin/tenant auth, provisioning, session enqueue, scoping."""
import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

import control_api

ADMIN = "admin-secret-token"


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("AUTOAGENT_ADMIN_TOKEN", ADMIN)
    return TestClient(control_api.app)


def _admin_h():
    return {"Authorization": f"Bearer {ADMIN}"}


def _provision(client, tid="acme", **body):
    return client.post("/tenants", json={"tenant_id": tid, **body}, headers=_admin_h())


# ── health + admin auth ─────────────────────────────────────────────────────

def test_healthz(client):
    assert client.get("/healthz").json() == {"ok": True}


def test_tenants_requires_admin(client):
    r = client.post("/tenants", json={"tenant_id": "acme"})
    assert r.status_code == 401
    r = client.post("/tenants", json={"tenant_id": "acme"},
                    headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 401


def test_admin_token_must_be_configured(monkeypatch):
    monkeypatch.delenv("AUTOAGENT_ADMIN_TOKEN", raising=False)
    c = TestClient(control_api.app)
    assert c.post("/tenants", json={"tenant_id": "acme"},
                  headers=_admin_h()).status_code == 503


# ── provisioning + token issuance ───────────────────────────────────────────

def test_provision_returns_token_once_and_lists(client):
    r = _provision(client)
    assert r.status_code == 201
    body = r.json()
    assert body["tenant"]["tenant_id"] == "acme"
    assert "data_root" not in body["tenant"]        # internals never exposed
    assert body["api_token"]                        # token returned once
    lst = client.get("/tenants", headers=_admin_h()).json()["tenants"]
    assert any(t["tenant_id"] == "acme" for t in lst)


def test_invalid_tenant_id_is_400(client):
    assert _provision(client, tid="../evil").status_code == 400


# ── tenant session endpoints + scoping ──────────────────────────────────────

def test_tenant_token_enqueues_session(client):
    token = _provision(client).json()["api_token"]
    r = client.post("/sessions", json={"project": "shop"},
                    headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 202
    assert r.json()["job_id"]


def test_session_requires_valid_tenant_token(client):
    _provision(client)
    assert client.post("/sessions", json={}).status_code == 401
    assert client.post("/sessions", json={},
                       headers={"Authorization": "Bearer bogus"}).status_code == 401


def test_tenant_cannot_see_another_tenants_job(client):
    ta = _provision(client, tid="acme").json()["api_token"]
    tb = _provision(client, tid="globex").json()["api_token"]
    jid = client.post("/sessions", json={},
                      headers={"Authorization": f"Bearer {ta}"}).json()["job_id"]
    # globex asking for acme's job → 404 (existence not even leaked)
    r = client.get(f"/sessions/{jid}", headers={"Authorization": f"Bearer {tb}"})
    assert r.status_code == 404
    # acme can see its own
    assert client.get(f"/sessions/{jid}",
                      headers={"Authorization": f"Bearer {ta}"}).status_code == 200


def test_delete_tenant(client):
    _provision(client, tid="acme")
    # soft delete keeps an audit record, now inactive
    assert client.delete("/tenants/acme", headers=_admin_h()).status_code == 200
    assert client.get("/tenants/acme", headers=_admin_h()).json()["tenant"]["status"] == "deleted"
    # hard delete removes it entirely
    assert client.delete("/tenants/acme?delete_data=true", headers=_admin_h()).status_code == 200
    assert client.get("/tenants/acme", headers=_admin_h()).status_code == 404


def test_revoked_tenant_token_stops_working(client):
    """After deprovision, the tenant token no longer authenticates."""
    token = _provision(client, tid="acme").json()["api_token"]
    client.delete("/tenants/acme", headers=_admin_h())   # soft delete => status != active
    assert client.post("/sessions", json={},
                       headers={"Authorization": f"Bearer {token}"}).status_code == 401
