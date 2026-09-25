#!/usr/bin/env python3
"""Tenant provisioning + teardown — the assembly layer (Phase 6).

Ties the isolation primitives into one tenant lifecycle:
  provision   = register the tenant + create its volume (data_root) + seed its
                vault with the BYOK key.
  deprovision = the reverse, with hard guards so teardown can NEVER delete a path
                it doesn't own or a tenant it didn't provision.

The tenant registry is a control-plane JSON file (`AGENCY_HOME/tenants.json`) for
now — control-plane metadata managed by the operator/host. It moves into Postgres
with the control-plane API (Phase 5), which defines the privileged role that can
manage the registry without tripping tenant RLS. Volumes are host directories
under a single managed base; the container runner (sandbox.py) mounts one as the
tenant's workspace.

Teardown is the dangerous path (it removes data), so it is defensive by default:
soft-delete (mark status) unless ``delete_data=True``, refuses tenants not in the
registry, and refuses any data_root that doesn't resolve *inside* the managed
base — a generalization of the concierge cascade-delete guard.
"""
import json
import os
import shutil
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from tenant import require_valid_tenant_id

try:
    import fcntl  # POSIX advisory locking for registry mutations
except ImportError:  # pragma: no cover - non-POSIX
    fcntl = None


def _base() -> Path:
    """AGENCY_HOME via the registry SSoT (honours AUTOAGENT_HOME / test isolation)."""
    import registry
    return registry.AGENCY_HOME


def tenants_base() -> Path:
    """Managed root that ALL tenant volumes live under. Teardown never escapes it."""
    return _base() / "tenants"


def _registry_path() -> Path:
    return _base() / "tenants.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class TenantRecord:
    tenant_id: str
    data_root: str
    plan: str = "concierge"
    status: str = "active"
    created_at: str = ""
    token_hash: Optional[str] = None    # sha256 of the tenant's API token (Phase 5)

    @property
    def data_root_path(self) -> Path:
        return Path(self.data_root)


# ── registry I/O (control-plane JSON; -> Postgres in Phase 5) ────────────────

def _load_registry() -> dict:
    """Load the tenant registry. A MISSING file is an empty registry; a present
    but UNPARSEABLE file is a hard error — treating corruption as {} would let the
    next _save_registry atomically erase every other tenant (fail-fast, not silent).
    """
    path = _registry_path()
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"tenant registry {path} is corrupt ({e}); refusing to proceed — a "
            "write would erase all tenants. Fix or remove the file, then retry."
        ) from e


def _save_registry(data: dict) -> None:
    path = _registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp, path)                    # atomic


@contextmanager
def _registry_lock():
    """Serialize registry read-modify-write so concurrent provision/deprovision
    can't lose rows. Advisory flock on a lockfile; a no-op where fcntl is absent."""
    _base().mkdir(parents=True, exist_ok=True)
    lock_path = _base() / "tenants.lock"
    if fcntl is None:
        yield
        return
    with open(lock_path, "w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def get_tenant(tenant_id: str) -> Optional[TenantRecord]:
    rec = _load_registry().get(tenant_id)
    return TenantRecord(**rec) if rec else None


def list_tenants() -> list:
    return [TenantRecord(**r) for r in _load_registry().values()]


def _default_data_root(tenant_id: str) -> Path:
    return tenants_base() / tenant_id


# ── provision ───────────────────────────────────────────────────────────────

def provision_tenant(tenant_id: str, *, byok_key: Optional[str] = None,
                     plan: str = "concierge") -> TenantRecord:
    """Create (or re-activate) a tenant: registry row + volume dir + vault seed.

    Idempotent: provisioning an existing tenant updates plan/status and re-seeds
    the key if given, but never clobbers its data_root or wipes its volume. The
    volume is ALWAYS the canonical tenants_base()/tenant_id — no caller-supplied
    path, so provision and teardown stay symmetric and a stray path can't be
    created or later deleted.
    """
    require_valid_tenant_id(tenant_id)
    # Fail fast BEFORE writing any state: validate the vault is usable (key present
    # AND a valid Fernet key), else we'd register a tenant and then blow up storing
    # the key, stranding a half-provisioned tenant. vault._fernet() raises on both.
    if byok_key:
        import vault
        vault._fernet()
    with _registry_lock():
        reg = _load_registry()
        existing = reg.get(tenant_id)
        root = _default_data_root(tenant_id)   # canonical; ignores any prior path

        # Volume: the tenant's isolated filesystem root (the container mounts this).
        root.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(root, 0o700)
        except OSError:
            pass
        (root / "projects").mkdir(exist_ok=True)

        rec = TenantRecord(
            tenant_id=tenant_id,
            data_root=str(root),
            plan=plan,
            status="active",
            created_at=existing["created_at"] if existing else _now(),
        )
        reg[tenant_id] = asdict(rec)
        _save_registry(reg)

    if byok_key:
        import vault
        vault.put_secret(tenant_id, "ANTHROPIC_API_KEY", byok_key)

    return rec


# ── deprovision (the dangerous path) ────────────────────────────────────────

def _assert_safe_to_delete(tenant_id: str, root: Path) -> None:
    """Refuse to delete anything other than THIS tenant's own canonical volume.

    Containment-in-the-base is not enough: tenant B's volume is also inside the
    base, so a mere containment check would let a teardown aimed at a tampered or
    wrong data_root delete a sibling. Require exact identity with
    tenants_base()/tenant_id.
    """
    canonical = _default_data_root(tenant_id).resolve()
    resolved = root.resolve()
    if resolved != canonical:
        raise RuntimeError(
            f"refusing to delete {resolved}: not this tenant's canonical volume "
            f"({canonical}). Registry may be tampered or the path was overridden."
        )


def deprovision_tenant(tenant_id: str, *, delete_data: bool = False) -> bool:
    """Tear a tenant down. Soft by default (status=deleted); delete_data=True also
    removes its volume, vault blob, and Postgres rows.

    Hard teardown is ALL-OR-NOTHING: if any of the vault/Postgres removals fail,
    the registry row is kept as status='delete_failed' and a RuntimeError is
    raised, so the operator retries rather than being told a stranger's secret
    ciphertext + control-DB rows are gone when they aren't. Returns False if the
    tenant was never provisioned (no-op) — teardown never touches an unknown
    tenant, so it can't be aimed at an arbitrary path.
    """
    require_valid_tenant_id(tenant_id)
    with _registry_lock():
        reg = _load_registry()
        rec = reg.get(tenant_id)
        if not rec:
            return False

        if not delete_data:
            rec["status"] = "deleted"
            reg[tenant_id] = rec
            _save_registry(reg)
            return True

        root = Path(rec["data_root"])
        _assert_safe_to_delete(tenant_id, root)     # guard BEFORE any removal
        if root.exists():
            shutil.rmtree(root)                     # loud on failure (never swallowed)

        errors = []
        try:
            import vault
            vp = vault._vault_path(tenant_id)
            if vp.exists():
                vp.unlink()
        except Exception as e:
            errors.append(f"vault blob: {e}")
        try:
            import control_pg
            if control_pg.is_enabled():
                _purge_pg_rows(tenant_id)
        except Exception as e:
            errors.append(f"postgres rows: {e}")

        if errors:
            rec["status"] = "delete_failed"
            reg[tenant_id] = rec
            _save_registry(reg)
            raise RuntimeError(
                f"teardown of '{tenant_id}' incomplete — registry kept for retry: "
                + "; ".join(errors)
            )

        reg.pop(tenant_id, None)
        _save_registry(reg)
        return True


def _purge_pg_rows(tenant_id: str) -> None:
    """Delete a tenant's rows from every control table.

    Defense-in-depth: an explicit ``WHERE tenant_id = %s`` scopes the delete even
    if RLS is absent (a misconfigured DB, a BYPASSRLS/superuser role, policies not
    applied) — a WHERE-less DELETE trusting RLS alone would wipe EVERY tenant in
    exactly that failure mode. RLS remains the primary boundary; this is the belt.
    Table names come from the fixed TENANT_TABLES constant, never user input.
    """
    import control_pg
    with control_pg.tenant_conn(tenant_id) as conn:
        for table in control_pg.TENANT_TABLES:
            conn.execute(f"DELETE FROM {table} WHERE tenant_id = %s", (tenant_id,))
