#!/usr/bin/env python3
"""Postgres control-plane backend with Row-Level Security (Fork B).

The self-serve control DB is one shared Postgres where every row carries a
``tenant_id`` and **RLS is the enforced isolation boundary** — a query without a
tenant set returns nothing (default-deny), and no connection can read, update, or
delete another tenant's rows. This is the security guarantee the whole self-serve
model rests on, so it is proven with an adversarial test against a real Postgres
(see test_control_pg.py), not just asserted.

Opt-in: set ``AUTOAGENT_DB_URL`` to a Postgres DSN. Unset => the engine stays on
per-tenant SQLite (agency_db), which is the single-tenant default.

Two hard requirements for RLS to actually hold:
  1. The app connects as a **non-superuser** role that does **not own** the tables.
     Superusers and table owners bypass RLS unless forced; we ``FORCE`` it so even
     the owner is subject to policy, but the app should still use a plain role.
  2. Every tenant-scoped statement runs with ``app.tenant`` set for the
     transaction (``set_config('app.tenant', <id>, true)``). ``tenant_conn`` does
     this on checkout; forget it and you see zero rows, never someone else's.
"""
import os
import threading
from contextlib import contextmanager

ENV_DB_URL = "AUTOAGENT_DB_URL"

# Control-plane tables. Kept in lockstep with agency_db's SQLite schema; the
# policy loop below guarantees EVERY one gets an RLS policy — a table missing
# from this list would be a silent isolation hole, so adding a table here is
# mandatory, not optional.
TENANT_TABLES = (
    "projects", "sessions", "agents", "knowledge",
    "tasks", "messages", "metrics", "council_decisions",
)

# Faithful Postgres port of the SQLite control schema. tenant_id is first on
# every table and is the RLS key. Natural keys are scoped by tenant so two
# tenants can each own a project named "shop".
_TABLES_DDL = """
CREATE TABLE IF NOT EXISTS projects (
    tenant_id   TEXT NOT NULL,
    name        TEXT NOT NULL,
    path        TEXT NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT now(),
    config      JSONB DEFAULT '{}'::jsonb,
    PRIMARY KEY (tenant_id, name)
);
CREATE TABLE IF NOT EXISTS sessions (
    id            BIGSERIAL PRIMARY KEY,
    tenant_id     TEXT NOT NULL,
    project       TEXT NOT NULL,
    session_num   INTEGER NOT NULL,
    session_type  TEXT NOT NULL,
    agent         TEXT,
    success       INTEGER NOT NULL DEFAULT 0,
    started_at    TIMESTAMPTZ DEFAULT now(),
    finished_at   TIMESTAMPTZ,
    tests_before  INTEGER DEFAULT 0,
    tests_after   INTEGER DEFAULT 0,
    files_changed JSONB DEFAULT '[]'::jsonb,
    summary       TEXT DEFAULT '',
    cost_usd      DOUBLE PRECISION DEFAULT 0.0,
    quality_score INTEGER DEFAULT 0,
    success_source TEXT DEFAULT 'explicit'
);
CREATE TABLE IF NOT EXISTS agents (
    id             BIGSERIAL PRIMARY KEY,
    tenant_id      TEXT NOT NULL,
    project        TEXT NOT NULL,
    name           TEXT NOT NULL,
    display_name   TEXT,
    total_sessions INTEGER DEFAULT 0,
    successful     INTEGER DEFAULT 0,
    failed         INTEGER DEFAULT 0,
    avg_quality    DOUBLE PRECISION DEFAULT 0.0,
    last_session_at TIMESTAMPTZ,
    keywords       JSONB DEFAULT '[]'::jsonb,
    owned_files    JSONB DEFAULT '[]'::jsonb,
    UNIQUE (tenant_id, project, name)
);
CREATE TABLE IF NOT EXISTS knowledge (
    id           BIGSERIAL PRIMARY KEY,
    tenant_id    TEXT NOT NULL,
    project      TEXT NOT NULL,
    rule         TEXT NOT NULL,
    source       TEXT DEFAULT '',
    created_at   TIMESTAMPTZ DEFAULT now(),
    last_used_at TIMESTAMPTZ,
    use_count    INTEGER DEFAULT 0,
    score        DOUBLE PRECISION DEFAULT 1.0,
    is_universal INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS tasks (
    id           BIGSERIAL PRIMARY KEY,
    tenant_id    TEXT NOT NULL,
    project      TEXT NOT NULL,
    title        TEXT NOT NULL,
    description  TEXT DEFAULT '',
    agent_hint   TEXT,
    status       TEXT DEFAULT 'pending',
    priority     INTEGER DEFAULT 0,
    depends_on   JSONB DEFAULT '[]'::jsonb,
    created_at   TIMESTAMPTZ DEFAULT now(),
    completed_at TIMESTAMPTZ,
    session_id   BIGINT
);
CREATE TABLE IF NOT EXISTS messages (
    id            BIGSERIAL PRIMARY KEY,
    tenant_id     TEXT NOT NULL,
    direction     TEXT NOT NULL,
    message_type  TEXT DEFAULT 'notify',
    project       TEXT,
    agent         TEXT,
    content       TEXT NOT NULL,
    reply_to      BIGINT,
    telegram_msg_id BIGINT,
    created_at    TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE IF NOT EXISTS metrics (
    id          BIGSERIAL PRIMARY KEY,
    tenant_id   TEXT NOT NULL,
    project     TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    value       DOUBLE PRECISION NOT NULL,
    recorded_at TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE IF NOT EXISTS council_decisions (
    id             BIGSERIAL PRIMARY KEY,
    tenant_id      TEXT NOT NULL,
    project        TEXT NOT NULL,
    session_num    INTEGER NOT NULL,
    question       TEXT NOT NULL,
    winner         TEXT DEFAULT '',
    confidence     TEXT DEFAULT 'MEDIUM',
    synthesis      TEXT DEFAULT '',
    session_outcome INTEGER,
    created_at     TIMESTAMPTZ DEFAULT now()
);
"""


def _rls_ddl() -> str:
    """Enable + FORCE RLS and install a default-deny tenant policy on every table.

    ``current_setting('app.tenant', true)`` returns NULL when unset (the ``true``
    = missing_ok), so ``tenant_id = NULL`` is NULL, never true — a connection that
    forgot to set the tenant sees zero rows. WITH CHECK blocks writing a row under
    the wrong tenant, so a scoped connection can't smuggle rows into another tenant.
    """
    out = []
    for t in TENANT_TABLES:
        out.append(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY;")
        out.append(f"ALTER TABLE {t} FORCE ROW LEVEL SECURITY;")
        out.append(f"DROP POLICY IF EXISTS tenant_isolation ON {t};")
        out.append(
            f"CREATE POLICY tenant_isolation ON {t} "
            f"USING (tenant_id = current_setting('app.tenant', true)) "
            f"WITH CHECK (tenant_id = current_setting('app.tenant', true));"
        )
    return "\n".join(out)


def init_schema(conn) -> None:
    """Create the control-plane tables + RLS policies. Idempotent."""
    conn.execute(_TABLES_DDL)
    conn.execute(_rls_ddl())
    conn.commit()


def grant_app_role(conn, role: str) -> None:
    """Grant a non-superuser app role DML on every control table (run as owner)."""
    conn.execute(f"GRANT USAGE ON SCHEMA public TO {role};")
    conn.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {role};")
    conn.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {role};")
    conn.commit()


# ── connection pool (mirrors council.memory) ────────────────────────────────
_pool = None
_pool_lock = threading.Lock()


def _dsn() -> str:
    dsn = os.environ.get(ENV_DB_URL)
    if not dsn:
        raise RuntimeError(
            f"{ENV_DB_URL} not set — Postgres control plane is opt-in. "
            "Unset means the engine uses per-tenant SQLite (agency_db)."
        )
    return dsn


def is_enabled() -> bool:
    """True when a Postgres control DB is configured. Re-read every call."""
    return bool(os.environ.get(ENV_DB_URL))


def _get_pool():
    global _pool
    if _pool is not None:
        return _pool
    with _pool_lock:
        if _pool is not None:
            return _pool
        try:
            from psycopg_pool import ConnectionPool
        except ImportError as e:
            raise RuntimeError(
                "psycopg + psycopg_pool required: pip install 'psycopg[binary]' psycopg_pool"
            ) from e
        _pool = ConnectionPool(_dsn(), min_size=1, max_size=4,
                               kwargs={"autocommit": False}, open=True)
    return _pool


def _reset_pool_for_tests():
    global _pool
    with _pool_lock:
        if _pool is not None:
            try:
                _pool.close()
            except Exception:
                pass
            _pool = None


@contextmanager
def tenant_conn(tenant_id: str):
    """A control-DB connection scoped to one tenant for the transaction.

    Sets ``app.tenant`` transaction-locally so RLS filters every statement to
    this tenant; the setting resets when the transaction ends, so a pooled
    connection never leaks scope to the next checkout.
    """
    if not tenant_id:
        raise ValueError("tenant_conn requires a non-empty tenant_id (RLS is default-deny)")
    pool = _get_pool()
    with pool.connection() as conn:
        conn.execute("SELECT set_config('app.tenant', %s, true)", (tenant_id,))
        yield conn
