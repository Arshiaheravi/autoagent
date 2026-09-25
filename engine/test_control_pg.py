"""Adversarial proof that RLS is a real isolation boundary (Fork B).

Provisions a throwaway Postgres database + a NON-superuser app role (superusers
bypass RLS, so testing as one would be a false pass), installs the control schema
+ RLS policies, then proves a tenant-scoped connection cannot read, write, update,
or delete another tenant's rows — and that a connection with no tenant set sees
nothing at all (default-deny).

Skips cleanly when no Postgres admin is reachable.
"""
import os

import pytest

psycopg = pytest.importorskip("psycopg")
import control_pg  # noqa: E402

ADMIN_DSN = os.environ.get(
    "AUTOAGENT_TEST_ADMIN_DSN",
    "postgresql://postgres:postgres@127.0.0.1:5432/postgres",
)
TEST_DB = "aa_rls_test"
APP_ROLE = "aa_app_rls"
APP_PW = "aa_app_rls"
APP_DSN = f"postgresql://{APP_ROLE}:{APP_PW}@127.0.0.1:5432/{TEST_DB}"


def _admin_reachable() -> bool:
    try:
        with psycopg.connect(ADMIN_DSN, connect_timeout=3):
            return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _admin_reachable(),
    reason="no reachable Postgres admin (set AUTOAGENT_TEST_ADMIN_DSN)",
)


@pytest.fixture()
def rls_db(monkeypatch):
    """Fresh DB + non-superuser role with the RLS control schema installed."""
    with psycopg.connect(ADMIN_DSN, autocommit=True) as admin:
        admin.execute(f"DROP DATABASE IF EXISTS {TEST_DB} WITH (FORCE)")
        try:
            admin.execute(f"DROP ROLE IF EXISTS {APP_ROLE}")
        except Exception:
            pass
        admin.execute(f"CREATE ROLE {APP_ROLE} LOGIN PASSWORD '{APP_PW}' NOSUPERUSER")
        admin.execute(f"CREATE DATABASE {TEST_DB}")

    # As owner in the new DB: build schema + RLS, grant the app role DML.
    with psycopg.connect(ADMIN_DSN.rsplit("/", 1)[0] + f"/{TEST_DB}", autocommit=False) as owner:
        control_pg.init_schema(owner)
        control_pg.grant_app_role(owner, APP_ROLE)

    monkeypatch.setenv(control_pg.ENV_DB_URL, APP_DSN)
    control_pg._reset_pool_for_tests()
    yield
    control_pg._reset_pool_for_tests()
    with psycopg.connect(ADMIN_DSN, autocommit=True) as admin:
        admin.execute(f"DROP DATABASE IF EXISTS {TEST_DB} WITH (FORCE)")
        try:
            admin.execute(f"DROP ROLE IF EXISTS {APP_ROLE}")
        except Exception:
            pass


def _insert_project(tenant, name, path="/tmp/x"):
    with control_pg.tenant_conn(tenant) as c:
        c.execute("INSERT INTO projects (tenant_id, name, path) VALUES (%s, %s, %s)",
                  (tenant, name, path))


def test_scoped_reads_see_only_own_rows(rls_db):
    _insert_project("acme", "shop")
    _insert_project("globex", "store")
    with control_pg.tenant_conn("acme") as c:
        names = [r[0] for r in c.execute("SELECT name FROM projects").fetchall()]
    assert names == ["shop"]
    with control_pg.tenant_conn("globex") as c:
        names = [r[0] for r in c.execute("SELECT name FROM projects").fetchall()]
    assert names == ["store"]


def test_default_deny_when_no_tenant_set(rls_db):
    _insert_project("acme", "shop")
    # Raw app-role connection that never sets app.tenant → RLS denies everything.
    with psycopg.connect(APP_DSN) as raw:
        rows = raw.execute("SELECT * FROM projects").fetchall()
    assert rows == []


def test_with_check_blocks_writing_another_tenants_row(rls_db):
    with pytest.raises(Exception):
        with control_pg.tenant_conn("acme") as c:
            # Scoped to acme but trying to stamp the row globex → WITH CHECK rejects.
            c.execute("INSERT INTO projects (tenant_id, name, path) VALUES (%s, %s, %s)",
                      ("globex", "smuggled", "/tmp/x"))


def test_cross_tenant_update_and_delete_affect_zero_rows(rls_db):
    _insert_project("acme", "shop")
    _insert_project("globex", "store")
    with control_pg.tenant_conn("acme") as c:
        upd = c.execute("UPDATE projects SET path='hacked' WHERE name='store'").rowcount
        deleted = c.execute("DELETE FROM projects WHERE name='store'").rowcount
    assert upd == 0
    assert deleted == 0
    # globex's row is untouched.
    with control_pg.tenant_conn("globex") as c:
        row = c.execute("SELECT path FROM projects WHERE name='store'").fetchone()
    assert row[0] == "/tmp/x"


def test_isolation_generalizes_to_another_table(rls_db):
    with control_pg.tenant_conn("acme") as c:
        c.execute("INSERT INTO sessions (tenant_id, project, session_num, session_type) "
                  "VALUES (%s, %s, %s, %s)", ("acme", "shop", 1, "work"))
    with control_pg.tenant_conn("globex") as c:
        rows = c.execute("SELECT * FROM sessions").fetchall()
    assert rows == []


def test_teardown_row_purge_is_tenant_scoped(rls_db):
    """provisioning._purge_pg_rows deletes only the target tenant's rows."""
    import provisioning
    _insert_project("acme", "shop")
    _insert_project("globex", "store")
    provisioning._purge_pg_rows("acme")
    with control_pg.tenant_conn("acme") as c:
        assert c.execute("SELECT count(*) FROM projects").fetchone()[0] == 0
    with control_pg.tenant_conn("globex") as c:
        assert c.execute("SELECT name FROM projects").fetchone()[0] == "store"


def test_every_tenant_table_has_a_policy(rls_db):
    """No control table may silently ship without an RLS policy."""
    with psycopg.connect(ADMIN_DSN.rsplit("/", 1)[0] + f"/{TEST_DB}") as owner:
        rows = owner.execute(
            "SELECT tablename FROM pg_policies WHERE policyname='tenant_isolation'"
        ).fetchall()
    covered = {r[0] for r in rows}
    assert covered == set(control_pg.TENANT_TABLES)
