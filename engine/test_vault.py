"""BYOK vault — ciphertext-only-on-disk, master-key-in-env-only (Phase 3)."""
import importlib.util
import os
import stat
from pathlib import Path

import pytest

pytest.importorskip("cryptography")
import vault

# Load engine/run.py explicitly — the V1 root-level run.py shadows a bare `import run`.
_run_spec = importlib.util.spec_from_file_location("engine_run", Path(__file__).parent / "run.py")
run_module = importlib.util.module_from_spec(_run_spec)
_run_spec.loader.exec_module(run_module)


@pytest.fixture()
def master_key(monkeypatch, tmp_path):
    key = vault.generate_key()
    monkeypatch.setenv(vault.ENV_MASTER_KEY, key)
    monkeypatch.setenv(vault.ENV_VAULT_DIR, str(tmp_path / "vault"))
    return key


def test_generate_key_is_valid_fernet():
    from cryptography.fernet import Fernet
    Fernet(vault.generate_key().encode())   # no raise


def test_put_get_roundtrip(master_key):
    vault.put_secret("acme", "ANTHROPIC_API_KEY", "sk-secret-123")
    assert vault.get_secret("acme", "ANTHROPIC_API_KEY") == "sk-secret-123"


def test_ciphertext_on_disk_has_no_plaintext(master_key):
    secret = "sk-super-secret-value-xyz"
    vault.put_secret("acme", "ANTHROPIC_API_KEY", secret)
    raw = vault._vault_path("acme").read_bytes()
    assert secret.encode() not in raw
    assert b"ANTHROPIC_API_KEY" not in raw   # even the key name is encrypted


def test_file_permissions_are_0600(master_key):
    vault.put_secret("acme", "k", "v")
    mode = stat.S_IMODE(os.stat(vault._vault_path("acme")).st_mode)
    assert mode == 0o600


def test_wrong_master_key_fails_loudly(master_key, monkeypatch):
    vault.put_secret("acme", "k", "v")
    monkeypatch.setenv(vault.ENV_MASTER_KEY, vault.generate_key())  # rotate to a different key
    from cryptography.fernet import InvalidToken
    with pytest.raises(InvalidToken):
        vault.get_secret("acme", "k")


def test_missing_master_key_raises(master_key, monkeypatch):
    vault.put_secret("acme", "k", "v")
    monkeypatch.delenv(vault.ENV_MASTER_KEY, raising=False)
    with pytest.raises(RuntimeError):
        vault.get_secret("acme", "k")


def test_tenants_are_isolated(master_key):
    vault.put_secret("acme", "ANTHROPIC_API_KEY", "acme-key")
    vault.put_secret("globex", "ANTHROPIC_API_KEY", "globex-key")
    assert vault.get_secret("acme", "ANTHROPIC_API_KEY") == "acme-key"
    assert vault.get_secret("globex", "ANTHROPIC_API_KEY") == "globex-key"
    # separate files
    assert vault._vault_path("acme") != vault._vault_path("globex")


def test_inject_env_returns_all_and_empty_without_vault(master_key):
    assert vault.inject_env("nobody") == {}          # no vault => safe empty
    vault.put_secret("acme", "ANTHROPIC_API_KEY", "k1")
    vault.put_secret("acme", "OTHER", "k2")
    assert vault.inject_env("acme") == {"ANTHROPIC_API_KEY": "k1", "OTHER": "k2"}


def test_delete_secret(master_key):
    vault.put_secret("acme", "a", "1")
    vault.put_secret("acme", "b", "2")
    vault.delete_secret("acme", "a")
    assert vault.get_secret("acme", "a") is None
    assert vault.get_secret("acme", "b") == "2"


def test_bad_tenant_id_rejected(master_key):
    for bad in ("", "../etc", "a/b", "."):
        with pytest.raises(ValueError):
            vault._vault_path(bad)


def test_has_vault(master_key):
    assert vault.has_vault("acme") is False
    vault.put_secret("acme", "k", "v")
    assert vault.has_vault("acme") is True


def test_vault_key_wins_in_build_child_env(master_key, monkeypatch):
    """The BYOK precedence is vault > config > env, and vault reaches run.py."""
    import types
    monkeypatch.delenv("AUTOAGENT_TENANT_ID", raising=False)   # => 'default' tenant
    vault.put_secret("default", "ANTHROPIC_API_KEY", "vault-key")
    ctx = types.SimpleNamespace(config={"anthropic_api_key": "config-key"})
    env = run_module._build_child_env(ctx)
    assert env["ANTHROPIC_API_KEY"] == "vault-key"


def test_no_vault_key_falls_back_to_config(master_key, monkeypatch):
    import types
    monkeypatch.delenv("AUTOAGENT_VAULT_KEY", raising=False)    # vault disabled
    ctx = types.SimpleNamespace(config={"anthropic_api_key": "config-key"})
    env = run_module._build_child_env(ctx)
    assert env["ANTHROPIC_API_KEY"] == "config-key"
