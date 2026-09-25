"""Tenant SSoT — the isolation-unit foundation for multi-tenant deployments."""
import importlib
from pathlib import Path

import tenant as tenant_mod
from tenant import DEFAULT_TENANT_ID, Tenant, current_tenant


def test_default_tenant_is_single_tenant_home(monkeypatch):
    monkeypatch.delenv("AUTOAGENT_HOME", raising=False)
    monkeypatch.delenv("AUTOAGENT_TENANT_ID", raising=False)
    t = Tenant.default()
    assert t.tenant_id == DEFAULT_TENANT_ID
    assert t.data_root == Path.home() / ".autoagent"
    assert t.db_path == Path.home() / ".autoagent" / "agency.db"


def test_current_tenant_defaults_when_env_unset(monkeypatch):
    monkeypatch.delenv("AUTOAGENT_HOME", raising=False)
    monkeypatch.delenv("AUTOAGENT_TENANT_ID", raising=False)
    t = current_tenant()
    assert t.tenant_id == DEFAULT_TENANT_ID
    assert t.data_root == Path.home() / ".autoagent"


def test_env_overrides_id_and_root_together(monkeypatch, tmp_path):
    root = tmp_path / "acme_vol"
    monkeypatch.setenv("AUTOAGENT_TENANT_ID", "acme")
    monkeypatch.setenv("AUTOAGENT_HOME", str(root))
    t = current_tenant()
    assert t.tenant_id == "acme"
    assert t.data_root == root
    # db lives under the tenant's own root — never the shared ~/.autoagent
    assert t.db_path == root / "agency.db"
    assert t.projects_dir == root / "projects"


def test_tenant_is_immutable():
    t = Tenant("x", Path("/tmp/x"))
    try:
        t.tenant_id = "y"  # type: ignore[misc]
    except Exception as e:
        assert "frozen" in str(e).lower() or "cannot assign" in str(e).lower()
    else:
        raise AssertionError("Tenant should be frozen/immutable")


def _fresh_db(monkeypatch, tmp_path, name="t.db"):
    import agency_db
    monkeypatch.setattr(agency_db, "_DB_PATH", tmp_path / name)
    agency_db._local.conn = None
    return agency_db


def test_writes_stamp_ambient_tenant(monkeypatch, tmp_path):
    monkeypatch.setenv("AUTOAGENT_TENANT_ID", "acme")
    db = _fresh_db(monkeypatch, tmp_path)
    db.upsert_project("shop", "/tmp/shop")
    db.log_session("shop", 1, "work", agent="eng", success=True)
    db.add_task("shop", "do a thing")
    conn = db._get_conn()
    assert conn.execute("SELECT tenant_id FROM projects WHERE name='shop'").fetchone()[0] == "acme"
    assert conn.execute("SELECT tenant_id FROM sessions WHERE project='shop'").fetchone()[0] == "acme"
    assert conn.execute("SELECT tenant_id FROM tasks WHERE project='shop'").fetchone()[0] == "acme"
    db._local.conn = None


def test_stamp_follows_current_tenant(monkeypatch, tmp_path):
    """Same DB, two tenants writing => each row carries its own owner."""
    db = _fresh_db(monkeypatch, tmp_path)
    monkeypatch.setenv("AUTOAGENT_TENANT_ID", "acme")
    db.upsert_project("a", "/tmp/a")
    monkeypatch.setenv("AUTOAGENT_TENANT_ID", "globex")
    db.upsert_project("b", "/tmp/b")
    conn = db._get_conn()
    assert conn.execute("SELECT tenant_id FROM projects WHERE name='a'").fetchone()[0] == "acme"
    assert conn.execute("SELECT tenant_id FROM projects WHERE name='b'").fetchone()[0] == "globex"
    db._local.conn = None


def test_default_tenant_stamp_when_env_unset(monkeypatch, tmp_path):
    monkeypatch.delenv("AUTOAGENT_TENANT_ID", raising=False)
    db = _fresh_db(monkeypatch, tmp_path)
    db.upsert_project("p", "/tmp/p")
    conn = db._get_conn()
    assert conn.execute("SELECT tenant_id FROM projects WHERE name='p'").fetchone()[0] == "default"
    db._local.conn = None


def test_legacy_db_backfills_tenant_column(monkeypatch, tmp_path):
    """A DB predating tenant scoping gets the column added, defaulting to 'default'."""
    import sqlite3
    dbfile = tmp_path / "legacy.db"
    conn = sqlite3.connect(str(dbfile))
    conn.executescript(
        "CREATE TABLE projects (name TEXT PRIMARY KEY, path TEXT NOT NULL, "
        "created_at TEXT, config TEXT DEFAULT '{}');"
        "INSERT INTO projects (name, path) VALUES ('old', '/tmp/old');"
    )
    conn.commit()
    conn.close()
    db = _fresh_db(monkeypatch, tmp_path, name="legacy.db")
    conn = db._get_conn()  # triggers _init_schema => _ensure_column backfill
    row = conn.execute("SELECT tenant_id FROM projects WHERE name='old'").fetchone()
    assert row[0] == "default"
    db._local.conn = None


def test_registry_home_derives_from_tenant(monkeypatch, tmp_path):
    """registry.AGENCY_HOME and agency_db._DB_PATH resolve to the same tenant root."""
    root = tmp_path / "tenant_root"
    monkeypatch.setenv("AUTOAGENT_HOME", str(root))
    import registry
    import agency_db
    importlib.reload(registry)
    importlib.reload(agency_db)
    try:
        assert registry.AGENCY_HOME == root
        # The historical bug: agency_db ignored AUTOAGENT_HOME. Now they agree.
        assert agency_db._DB_PATH == root / "agency.db"
        assert agency_db._DB_PATH.parent == registry.AGENCY_HOME
    finally:
        # Restore module state for the rest of the suite (conftest re-patches too).
        monkeypatch.delenv("AUTOAGENT_HOME", raising=False)
        importlib.reload(registry)
        importlib.reload(agency_db)
