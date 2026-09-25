# Self-serve multi-tenant isolation — architecture

Status: **BUILDING — forks locked, Phase 1 shipped.**

**Locked decisions (2026-07-10):**
- **Fork A = A1 container-per-tenant** — one long-lived container + volume per
  tenant; design so per-session (A2) is a later runner swap.
- **Fork B = B1 Postgres + tenant_id + RLS** — one control DB, every row
  tenant-scoped, Row-Level Security (default-deny) is the enforced boundary.

**Progress:**
- ✅ **Phase 1a** (`7b61b37`) — `engine/tenant.py` Tenant SSoT; `registry.AGENCY_HOME`
  + `agency_db._DB_PATH` derive from it; fixed the AUTOAGENT_HOME-ignored bug.
- ✅ **Phase 1b** (`5bc8652`) — `tenant_id` column on all 8 control tables, stamped
  on every write; legacy-DB backfill. Reads still boundary-enforced.
- ✅ **Phase 2a** (`2fa61ff`) — `engine/control_pg.py`: Postgres control schema +
  **RLS default-deny, FORCED**, `tenant_conn()` sets `app.tenant` per transaction.
  **Isolation boundary PROVEN** by adversarial test against real Postgres (scoped
  reads, default-deny, WITH-CHECK, cross-tenant UPDATE/DELETE = 0 rows, every
  table policied). This validates Fork B's core security claim end-to-end.
- ✅ **Phase 3** (`ef2e43d`) — `engine/vault.py`: BYOK secrets encrypted at rest
  (Fernet), master key in env only, ciphertext-only on disk. Wired as the top BYOK
  source in run.py; composes with the sandbox env whitelist. Proven by tests.
- ✅ **Phase 4a** (`ad64a18`) — `engine/sandbox.py`: `ContainerRunner` confines a
  session in the tenant's container (non-root, read-only FS, cap-drop, env
  whitelist, resource caps). **Execution boundary PROVEN** against a real
  container. `LocalRunner` is the untouched single-tenant default.
- ✅ **Phase 6** (`a2f2344`, hardened `77d949b`) — `engine/provisioning.py` tenant
  lifecycle (provision/teardown, all-or-nothing, canonical-path guard) + agent
  Docker image (`deploy/Dockerfile.agent`), **built + smoke-tested** (`41c98e8`):
  claude runs non-root, engine importable + read-only, volume writable.
- ✅ **Egress gate** (`3ffb815`) — `--internal` network + allowlist proxy; the
  off-host-isolation half PROVEN vs real Docker. (Deploy of the proxy remains.)
- ✅ **Phase 5** (`543cff3` + `6accfbf`) — `engine/control_api.py` (FastAPI: admin
  provisioning + per-tenant token auth + session enqueue, tenant-scoped),
  `engine/job_queue.py` (FIFO), `engine/session_worker.py` (claims jobs → runs each
  in its tenant sandbox, hard loop cap). **Self-serve loop is code-complete.**
- ⏭ **Phase 2b** — route `agency_db` through `control_pg` when `AUTOAGENT_DB_URL`
  is set (Railway Postgres; SQLite stays the default). See "Phase 2b seam" below.

**Where we stand:** the three isolation *primitives* — data (RLS), execution
(container), secrets (vault) — are built and each PROVEN against real infra
(Postgres / Docker / crypto). What remains is assembly (provision a tenant =
row + volume + vault + container, and a control-plane API in front) plus the one
operational decision below. Every primitive ships behind the single-tenant
default, so nothing changes for the current setup until the control plane turns
it on.

## Why

Today "multi-tenant" = project folders under one `~/.autoagent` on one machine,
all sharing one OS process, one SQLite `agency.db`, one council pgvector, one
filesystem. The concierge fixes make that *safe at small scale when the operator
runs it*. Self-serve (strangers sign up, provision themselves, run their own
agents) needs a real per-tenant boundary, because each session runs
`claude -p …` which executes bash + writes files + runs git in the tenant's
workspace — arbitrary code execution on shared infra is the thing to isolate.

## Current seams (what we build on)

| Concern | Today | Seam we exploit |
|---|---|---|
| FS root | `AGENCY_HOME = ~/.autoagent`, per-project `projects/<name>/` | already `AUTOAGENT_HOME` env-overridable |
| Control DB | single global `~/.autoagent/agency.db` (SQLite, thread-local conn) | `agency_db._DB_PATH` is the one chokepoint |
| Council memory | shared pgvector, now `project`-scoped in SQL | project filter already threaded |
| Session exec | `subprocess.Popen(["claude", …], cwd=project_root)` | one spawn site in `run.py` |
| BYOK keys | per-project `config.json` (gitignored) + env | no vault yet |
| Identity | project = a name in a **global** namespace | needs `(tenant_id, project)` |

## Target architecture (recommended)

```
                       ┌─────────────────────────────┐
   signup / API  ───▶  │  CONTROL PLANE (FastAPI)     │
                       │  auth · tenants · billing    │
                       │  provisioning · job queue    │
                       └───────────┬─────────────────┘
                                   │  enqueues a session job
                    ┌──────────────┼───────────────┐
                    ▼              ▼               ▼
             ┌───────────┐  ┌───────────┐   ┌───────────┐
             │ tenant A  │  │ tenant B  │   │ tenant C  │   ← isolated SANDBOX
             │ engine +  │  │ engine +  │   │ engine +  │     (own volume, own
             │ repos vol │  │ repos vol │   │ repos vol │      AUTOAGENT_HOME,
             └─────┬─────┘  └─────┬─────┘   └─────┬─────┘      BYOK key injected)
                   └──────────────┼───────────────┘
                                  ▼
                     ┌──────────────────────────┐
                     │ Postgres (control plane)  │  every row tenant_id-scoped,
                     │  + pgvector (council mem) │  Row-Level Security enforced
                     └──────────────────────────┘
```

- **Isolation boundary** = the sandbox (Fork A) + RLS on the data plane (Fork B).
- The engine barely changes: it already reads `AUTOAGENT_HOME` and spawns one
  subprocess. The new work is the control plane + the sandbox runtime + moving
  the control DB to Postgres-with-RLS + a BYOK vault.

## Decisions locked (kept for the rationale; both chosen — see status)

### Fork A — the execution sandbox
| Option | Isolation | Ops cost | Notes |
|---|---|---|---|
| **A1 container-per-tenant** (recommended start) | strong (own kernel cgroup, own volume) | medium | one long-lived container per tenant; docker-compose → Fly Machines later |
| A2 container-per-session (ephemeral) | strongest (fresh env each run, like Anthropic Managed Agents) | high | more orchestration; best end-state |
| A3 shared host, per-OS-user + AUTOAGENT_HOME | weak (shared kernel, FS perms only) | low | NOT safe for untrusted signups |

Recommendation: **A1 now, design so A2 is a later swap** (both key off tenant_id
+ AUTOAGENT_HOME + injected key; only the runner differs).

### Fork B — the control-plane data store
| Option | Isolation | Enables | Cost |
|---|---|---|---|
| **B1 Postgres + tenant_id + RLS** (recommended) | strong (DB-enforced row scoping) | billing/usage rollups, one ops surface | migrate agency_db SQLite→Postgres |
| B2 per-tenant SQLite (own agency.db per home) | physical | matches today's file model | no cross-tenant control view; ops sprawl |
| B3 Postgres schema-per-tenant | strong | hard isolation | migration + schema management overhead |

Recommendation: **B1** — RLS is the enforced boundary, and it's the only option
that gives an operator/billing view without cross-tenant queries.

## Build phases (once A + B are locked)

1. ✅ **Tenant model + tenant_id everywhere** (done — 1a/1b above): `Tenant`
   (tenant_id + data_root), `AGENCY_HOME`/`_DB_PATH` derive from it, `tenant_id` a
   first-class column stamped on every write. Additive, back-compat, tested.
2. **Control-plane DB → Postgres + RLS** (next): add a Postgres backend behind
   the `agency_db` write/query API (SQLite stays the single-tenant default; a
   `AUTOAGENT_DB_URL` opt-in selects Postgres). Create the same schema with
   `tenant_id` on every table, an RLS policy per table (`USING (tenant_id =
   current_setting('app.tenant'))`, default-deny), and `SET app.tenant = <id>`
   on every connection checkout from the tenant SSoT. Reads then drop the file
   boundary and rely on RLS. Needs a Postgres instance + a migration path for the
   existing SQLite `agency.db`.
3. **BYOK vault**: encrypted-at-rest secrets, decrypted + injected as env into
   the sandbox at session start; never on disk in plaintext.
4. **Sandbox runtime** (per Fork A): a runner that launches a tenant's session in
   its container with its volume + injected key; the engine's one spawn site
   calls the runner instead of `subprocess.Popen` directly.
5. **Control-plane API**: auth, `POST /tenants` (provision), `POST /sessions`
   (enqueue), status stream. (Billing/UI can be a separate track.)
6. **Provisioning + teardown**: create/destroy a tenant's volume + DB scope +
   container; safe teardown (the concierge cascade-delete guard generalizes here).

Each phase ships tested, behind the single-tenant default so nothing breaks until
the control plane turns it on.

### Phase 2b seam (next build)

`control_pg` (2a) proves the boundary but isn't wired into the live data path yet.
2b routes the existing `agency_db` API through it without a big-bang rewrite:

- Keep every `agency_db` / `agency_db_queries` function signature. Add a backend
  switch at the connection layer keyed on `control_pg.is_enabled()`
  (`AUTOAGENT_DB_URL` set). SQLite stays the untouched default.
- The dialect gap (SQLite `?`/`datetime('now')`/`lastrowid` vs PG
  `%s`/`now()`/`RETURNING id`) wants a thin adapter, **not** per-call string
  hacks — an elegant seam, done deliberately, not rushed.
- Reads drop the file boundary and rely on RLS; `tenant_conn` supplies the
  scoped connection.
- Gate the PG-backend tests on reachability (like `test_control_pg.py`).

**Operational decision this surfaces (Seb):** where the production control
Postgres runs (Railway / Supabase / self-hosted) and how the current
`~/.autoagent/agency.db` data migrates in. That's the real "store cutover" — a
deploy decision, not a code one — so 2b builds behind the flag and Seb flips it.

## Risks / non-negotiables
- The sandbox is the security boundary — a tenant's `claude -p` must never reach
  another tenant's volume, key, or DB rows. Phase 4 gets an adversarial test.
- BYOK keys are the crown jewels — vault or bust; never `config.json` for a
  self-serve tenant.
- RLS must be *default-deny* — a query without a tenant set returns nothing, not
  everything.
- Don't build billing/auth UI before the isolation boundary is proven.

## LAUNCH GATE — network egress (mechanism built + proven; deploy remains)

The bare-bridge exposure (a session reaching `169.254.169.254` metadata, the
control plane, siblings) is now closed at the mechanism level (`3ffb815`):
- Untrusted tenants run on a Docker **`--internal`** network — no route off-host.
  PROVEN against real Docker (a TCP probe reaches the internet on bridge, fails on
  `--internal`).
- A dual-homed **allowlist proxy** (`deploy/egress-proxy/`, tinyproxy,
  default-deny, `CONNECT 443` to `api.anthropic.com` only) is the single hole back
  out. `engine/sandbox.py` injects `HTTPS_PROXY` so the session egresses only
  through it; `engine/egress.py` provisions the networks + proxy.

Remaining before untrusted signups open: **build + publish the proxy image**,
stand it up in prod (Railway), and confirm a real session reaches the API only via
the proxy. Concierge (vetted tenants) stays fine on bridge. Off by default —
`config.sandbox_proxy_url` + an `--internal` `sandbox_network` turn it on.

## Review provenance

The Phase 6 assembly (provisioning/teardown + image) was run through a 24-agent
adversarial review (find → independently verify). 14 confirmed defects were fixed
in `77d949b` — teardown all-or-nothing + canonical-path guard, corrupt-registry
fail-loud + flock, secret-out-of-argv, fail-loud vault decrypt, image ownership —
and the egress gate above was recorded rather than papered over.
