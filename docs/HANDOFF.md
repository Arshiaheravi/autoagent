# HANDOFF — Agentric self-serve isolation build

_Last updated 2026-07-14. Read this first when resuming._

## TL;DR

Self-serve multi-tenant is **code-complete and tested** (1217 tests green); every
isolation boundary is proven against real infra. **Nothing is deployed.** Concierge
(operator-run, vetted tenants) is **launch-ready today**. My recommendation: ship
concierge first, validate demand, then deploy self-serve — don't build more.

- Branch: **`agentric-launch-polish`** (pushed to `origin` = Arshiaheravi/autoagent).
- Repo: `/Users/SebSan/Documents/autoagent`. Engine: `engine/*.py`.
- Full design + status: `docs/SELF_SERVE_ISOLATION_ARCHITECTURE.md`.
- Audit trail: `docs/work-log.md`. Memory: `project_agentric_isolation.md`.

## The loop (all built)

```
signup ─▶ POST /tenants ─▶ provision(registry + volume + vault seed) ─▶ tenant token
tenant ─▶ POST /sessions ─▶ job_queue ─▶ session_worker claims ─▶ run in tenant sandbox
          (sandbox = --internal net + allowlist proxy + RLS + injected BYOK key)
```

## What each file does

| File | Role | Proven by |
|---|---|---|
| `engine/tenant.py` | Tenant SSoT (tenant_id + data_root); id validator | test_tenant.py |
| `engine/control_pg.py` | Postgres control schema + **RLS default-deny** | test_control_pg.py (real PG) |
| `engine/vault.py` | BYOK secrets, Fernet, ciphertext-only on disk | test_vault.py |
| `engine/sandbox.py` | `ContainerRunner` — confine `claude -p` (non-root, read-only, caps, proxy) | test_sandbox.py (real container) |
| `engine/egress.py` | `--internal` net + allowlist proxy plumbing | test_egress.py (real Docker) |
| `deploy/Dockerfile.agent` | per-tenant sandbox image | test_agent_image.py (built+run) |
| `deploy/egress-proxy/` | tinyproxy default-deny, `api.anthropic.com` only | test_egress.py |
| `engine/provisioning.py` | tenant lifecycle (provision/teardown, guarded) | test_provisioning.py |
| `engine/control_api.py` | FastAPI: admin + tenant token auth, provision, enqueue | test_control_api.py |
| `engine/job_queue.py` | FIFO session queue (file-based) | test_job_queue.py |
| `engine/session_worker.py` | claims jobs → runs in tenant sandbox (hard cap) | test_session_worker.py |

Everything is **behind the single-tenant default** — the current setup is unchanged
until env vars turn multi-tenant on.

## Commits (this build, in order)

`7b61b37` tenant SSoT · `5bc8652` tenant_id column · `2fa61ff` Postgres+RLS ·
`ef2e43d` vault · `ad64a18` sandbox · `a2f2344` provisioning+Dockerfile ·
`77d949b` **14-finding adversarial-review hardening** · `41c98e8` image built+smoke ·
`3ffb815` egress gate · `543cff3` control API+queue · `6accfbf` session worker.

## How to run / verify

```bash
cd engine && python3 -X utf8 -m pytest . -q          # 1217 tests

# build + smoke-test the agent image
docker build -f deploy/Dockerfile.agent -t autoagent-agent:smoke .
python3 -X utf8 -m pytest engine/test_agent_image.py -q

# run the control API locally
AUTOAGENT_ADMIN_TOKEN=xxx uvicorn control_api:app   # (from engine/)
```

## Env vars that turn things on (all default OFF)

| Var | Effect |
|---|---|
| `AUTOAGENT_TENANT_ID` / `AUTOAGENT_HOME` | select the tenant + its data root |
| `AUTOAGENT_DB_URL` | use Postgres control DB (Phase 2b, not wired live yet) |
| `AUTOAGENT_VAULT_KEY` | master key for the BYOK vault (`vault.generate_key()`) |
| `AUTOAGENT_ADMIN_TOKEN` | control-API admin bearer |
| `AUTOAGENT_SANDBOX_IMAGE` + config `sandbox: container` | run sessions in a container |
| config `sandbox_proxy_url` + `--internal` `sandbox_network` | force egress via the proxy |

## Locked decisions

- Fork A = **container-per-tenant**. Fork B = **Postgres + tenant_id + RLS**.
- Prod control-Postgres = **Railway** (for Phase 2b).

## What's LEFT (all deploy/ops — no core code) — recommended order

1. **Ship concierge first** (revenue, ready now): rotate creds (below), onboard the
   2 `$399` clients via `provisioning.provision_tenant(id, byok_key=...)`.
2. **Only when self-serve demand shows** → **Phase 2b**: wire `agency_db` +
   `job_queue` + registry through `control_pg` on Railway PG (flag flip; the "Phase
   2b seam" section of the design doc has the plan). Do this before any deploy —
   file-based single-host → PG migration otherwise is rework.
3. **Before opening signups** → adversarial red-team of the DEPLOYED stack
   (`/code-review ultra`-class). Unit-proven ≠ safe against strangers running code.
4. Deploy manifests (API + worker + egress proxy + PG). Build+publish the proxy image.
5. Billing/metering (Stripe + usage). Not built.

## SECURITY — must do (Seb's action)

- **Rotate the leaked GitHub PAT + Telegram token.** They're in git HISTORY
  (unrotated); working tree redacted. Runbook: `docs/SECURITY_PURGE_2026-07-08.md`.
  `git-filter-repo` is installed. This is your action — I can't rotate your creds.
- **Egress launch gate:** untrusted signups are NOT safe until the allowlist proxy
  is deployed + live-verified. Concierge on bridge is fine. See sandbox.py
  `DEFAULT_NETWORK` + the design doc's launch-gate section.
- Never bypass the pre-commit secret-scan hook with `--no-verify`.

## Gotchas

- **Two `run.py`** (engine + legacy root). A bare `import run` under pytest hits the
  ROOT one — load engine's via `spec_from_file_location` (see test_run.py/test_vault.py).
- **Registry + job queue are file-based** (single control-plane host). Fine small;
  they move to Postgres with 2b. Multi-host needs 2b first.
- **Line-count guards** in tests: run.py ≤600, orchestrator.py <300, session_helpers.py <350.
- macOS: no `timeout` (use gtimeout); Full Disk Access occasionally re-locks
  `~/Documents/autoagent` (re-grant if Bash/Read EPERM).

## My recommendation (verbatim)

Stop building self-serve — the stack is complete. Ship concierge, validate demand
with real money, then deploy (2b first, then red-team, then signups). Building
billing/manifests now is premature. Optional cheap demand test: a static in-tab
waitlist LP before investing in deploy.
