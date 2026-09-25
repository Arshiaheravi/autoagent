"""Tenant provisioning + teardown — lifecycle wiring and destructive-path guards."""
import json

import pytest

import provisioning
from provisioning import (deprovision_tenant, get_tenant, list_tenants,
                          provision_tenant, tenants_base)


@pytest.fixture()
def vault_env(monkeypatch, tmp_path):
    import vault
    monkeypatch.setenv(vault.ENV_MASTER_KEY, vault.generate_key())
    monkeypatch.setenv(vault.ENV_VAULT_DIR, str(tmp_path / "vaultdir"))


# ── provision ───────────────────────────────────────────────────────────────

def test_provision_creates_registry_and_volume():
    rec = provision_tenant("acme")
    assert rec.tenant_id == "acme"
    assert rec.status == "active"
    root = tenants_base() / "acme"
    assert root.is_dir()
    assert (root / "projects").is_dir()
    assert get_tenant("acme").data_root == str(root)


def test_provision_seeds_vault_when_key_given(vault_env):
    import vault
    provision_tenant("acme", byok_key="sk-tenant-key")
    assert vault.get_secret("acme", "ANTHROPIC_API_KEY") == "sk-tenant-key"


def test_provision_is_idempotent_and_preserves_created_at():
    a = provision_tenant("acme")
    marker = tenants_base() / "acme" / "projects" / "keep.txt"
    marker.write_text("data")
    b = provision_tenant("acme", plan="growth")
    assert b.created_at == a.created_at        # not reset
    assert b.plan == "growth"                  # updated
    assert marker.exists()                     # volume never wiped on re-provision


def test_byok_without_vault_key_fails_fast_and_writes_nothing(monkeypatch):
    monkeypatch.delenv("AUTOAGENT_VAULT_KEY", raising=False)
    with pytest.raises(RuntimeError):
        provision_tenant("acme", byok_key="sk-key")
    assert get_tenant("acme") is None            # no half-provisioned tenant
    assert not (tenants_base() / "acme").exists()


def test_invalid_tenant_id_rejected():
    for bad in ("../evil", "a/b", "", "."):
        with pytest.raises(ValueError):
            provision_tenant(bad)


def test_list_tenants():
    provision_tenant("acme")
    provision_tenant("globex")
    ids = {t.tenant_id for t in list_tenants()}
    assert ids == {"acme", "globex"}


# ── deprovision (destructive path) ──────────────────────────────────────────

def test_soft_deprovision_keeps_data():
    provision_tenant("acme")
    root = tenants_base() / "acme"
    assert deprovision_tenant("acme") is True
    assert get_tenant("acme").status == "deleted"
    assert root.is_dir()                        # soft delete leaves the volume


def test_hard_deprovision_removes_volume_vault_and_row(vault_env):
    import vault
    provision_tenant("acme", byok_key="sk-key")
    root = tenants_base() / "acme"
    assert deprovision_tenant("acme", delete_data=True) is True
    assert not root.exists()
    assert not vault.has_vault("acme")
    assert get_tenant("acme") is None


def test_deprovision_unknown_tenant_is_noop():
    assert deprovision_tenant("ghost", delete_data=True) is False


def test_teardown_refuses_path_outside_managed_base(tmp_path):
    """Even a tampered registry pointing outside the base cannot be deleted."""
    outside = tmp_path / "not_ours"
    outside.mkdir()
    (outside / "important.txt").write_text("do not delete")
    # Hand-write a malicious registry entry escaping the managed base.
    reg = {"evil": {"tenant_id": "evil", "data_root": str(outside),
                    "plan": "x", "status": "active", "created_at": "t"}}
    provisioning._save_registry(reg)
    with pytest.raises(RuntimeError):
        deprovision_tenant("evil", delete_data=True)
    assert (outside / "important.txt").exists()  # untouched


def test_hard_teardown_is_all_or_nothing_on_cleanup_failure(monkeypatch):
    """If PG purge fails, the tenant is kept as delete_failed and the error raised."""
    provision_tenant("acme")
    import control_pg
    monkeypatch.setattr(control_pg, "is_enabled", lambda: True)
    monkeypatch.setattr(provisioning, "_purge_pg_rows",
                        lambda tid: (_ for _ in ()).throw(RuntimeError("pg down")))
    with pytest.raises(RuntimeError):
        deprovision_tenant("acme", delete_data=True)
    rec = get_tenant("acme")
    assert rec is not None and rec.status == "delete_failed"   # kept for retry


def test_corrupt_registry_fails_loud(monkeypatch):
    provision_tenant("acme")
    provisioning._registry_path().write_text("{ this is not json ]", encoding="utf-8")
    with pytest.raises(RuntimeError):
        provision_tenant("beta")            # a save now would erase acme — refuse


def test_provision_rejects_invalid_vault_key(monkeypatch):
    import vault
    monkeypatch.setenv(vault.ENV_MASTER_KEY, "not-a-valid-fernet-key")
    with pytest.raises(Exception):
        provision_tenant("acme", byok_key="sk-key")
    assert get_tenant("acme") is None       # nothing written on a bad key


def test_teardown_refuses_base_itself(tmp_path):
    base = tenants_base()
    base.mkdir(parents=True, exist_ok=True)
    reg = {"root": {"tenant_id": "root", "data_root": str(base),
                    "plan": "x", "status": "active", "created_at": "t"}}
    provisioning._save_registry(reg)
    with pytest.raises(RuntimeError):
        deprovision_tenant("root", delete_data=True)
    assert base.exists()
