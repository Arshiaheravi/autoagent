#!/usr/bin/env python3
"""BYOK secret vault — encrypted at rest, master key never on disk (Phase 3).

Self-serve tenants bring their own Anthropic key. Storing it in a gitignored
config.json is fine for the operator's own machine but unacceptable for
strangers' keys on shared infra — a disk image, backup, or stray read exposes
every tenant. This vault keeps only ciphertext on disk; the master key lives in
the control-plane environment (``AUTOAGENT_VAULT_KEY``) and nowhere else.

Trust model: the control plane holds the master key and every tenant's
ciphertext. At session start it decrypts ONLY that tenant's secrets and injects
them as env into the tenant's sandbox (see sandbox.ContainerRunner). The tenant
container never sees the master key and never sees another tenant's blob.

Fernet (AES-128-CBC + HMAC-SHA256, authenticated) — a wrong/rotated key fails
loudly with InvalidToken rather than returning garbage.
"""
import json
import os
from pathlib import Path
from typing import Optional

ENV_MASTER_KEY = "AUTOAGENT_VAULT_KEY"
ENV_VAULT_DIR = "AUTOAGENT_VAULT_DIR"


def generate_key() -> str:
    """Mint a new master key (base64 str). Store it in the control-plane env as
    AUTOAGENT_VAULT_KEY — NOT on disk, NOT in git. Losing it loses every secret."""
    from cryptography.fernet import Fernet
    return Fernet.generate_key().decode()


def _fernet():
    from cryptography.fernet import Fernet
    key = os.environ.get(ENV_MASTER_KEY)
    if not key:
        raise RuntimeError(
            f"{ENV_MASTER_KEY} not set — the BYOK vault needs a master key in the "
            "control-plane environment. Mint one with vault.generate_key()."
        )
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception as e:
        raise RuntimeError(f"{ENV_MASTER_KEY} is not a valid Fernet key: {e}") from e


def _vault_dir() -> Path:
    override = os.environ.get(ENV_VAULT_DIR)
    if override:
        return Path(override)
    # Control-plane base: all tenants' blobs live here, never inside a tenant's
    # own mounted volume. Honours AUTOAGENT_HOME via the registry SSoT.
    import registry
    return registry.AGENCY_HOME / "vault"


def _vault_path(tenant_id: str) -> Path:
    from tenant import require_valid_tenant_id
    require_valid_tenant_id(tenant_id)      # SSoT: rejects traversal / metacharacters
    return _vault_dir() / f"{tenant_id}.enc"


def _load(tenant_id: str) -> dict:
    path = _vault_path(tenant_id)
    if not path.exists():
        return {}
    blob = path.read_bytes()
    if not blob:
        return {}
    data = _fernet().decrypt(blob)          # InvalidToken on wrong key / tamper
    return json.loads(data.decode("utf-8"))


def _save(tenant_id: str, secrets: dict) -> None:
    path = _vault_path(tenant_id)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    token = _fernet().encrypt(json.dumps(secrets).encode("utf-8"))
    tmp = path.with_suffix(".enc.tmp")
    tmp.write_bytes(token)
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)                    # atomic
    os.chmod(path, 0o600)


def put_secret(tenant_id: str, name: str, value: str) -> None:
    secrets = _load(tenant_id)
    secrets[name] = value
    _save(tenant_id, secrets)


def get_secret(tenant_id: str, name: str) -> Optional[str]:
    return _load(tenant_id).get(name)


def delete_secret(tenant_id: str, name: str) -> None:
    secrets = _load(tenant_id)
    if name in secrets:
        del secrets[name]
        _save(tenant_id, secrets)


def has_vault(tenant_id: str) -> bool:
    return _vault_path(tenant_id).exists()


def inject_env(tenant_id: str) -> dict:
    """Decrypt all of a tenant's secrets into an env dict for its sandbox.

    Returns {} when the tenant has no vault, so this is a safe additive lookup:
    callers merge it over the base env only when a vault exists.
    """
    if not has_vault(tenant_id):
        return {}
    return {str(k): str(v) for k, v in _load(tenant_id).items()}
