## 2026-07-10 — Self-serve isolation Phase 1: Tenant SSoT + tenant_id scoping

**Why:** self-serve SaaS (strangers sign up, run their own agents) needs a real
per-tenant boundary — each session runs `claude -p` = arbitrary code execution.
Forks locked with Seb: **A1 container-per-tenant**, **B1 Postgres + tenant_id +
RLS** (`docs/SELF_SERVE_ISOLATION_ARCHITECTURE.md`). Phase 1 is the
decision-independent foundation both forks build on.

**Phase 1a — Tenant SSoT (`7b61b37`):**
- New `engine/tenant.py`: frozen `Tenant(tenant_id, data_root)`, `current_tenant()`
  / `default()` resolved from `AUTOAGENT_TENANT_ID` + `AUTOAGENT_HOME`.
- `registry.AGENCY_HOME` and `agency_db._DB_PATH` now derive from it.
- Fixed latent bug: `agency_db._DB_PATH` hardcoded `~/.autoagent`, silently
  ignoring `AUTOAGENT_HOME` — a relocated tenant left its DB at the shared path.
- Back-compat: unset env => single `default` tenant at `~/.autoagent`.
- `engine/test_tenant.py`.

**Phase 1b — tenant_id column (`5bc8652`):**
- `tenant_id TEXT NOT NULL DEFAULT 'default'` on all 8 control tables, stamped on
  every INSERT via `_tenant_id()`; legacy DBs backfill via `_ensure_column`.
- Committed by Fork B — makes the Postgres+RLS cutover a connection-layer change.
- INVARIANT (documented): a SQLite file is never shared across tenants; the file
  (now) / RLS (later) is the read boundary, so reads don't filter on tenant_id.

**Files:** `engine/tenant.py` (new), `engine/registry.py`, `engine/agency_db.py`,
`engine/test_tenant.py` (new), `docs/SELF_SERVE_ISOLATION_ARCHITECTURE.md`.
**Tests:** 1134 pass.

**Phase 2a — Postgres control plane + RLS, boundary PROVEN (`2fa61ff`):**
- New `engine/control_pg.py`: PG port of the 8 control tables (tenant_id first,
  tenant-scoped keys) + `ENABLE`+`FORCE ROW LEVEL SECURITY` + a default-deny
  `tenant_isolation` policy templated over every table. `tenant_conn(id)` sets
  `app.tenant` transaction-locally (`set_config(...,true)`) so RLS scopes every
  statement and never leaks across pooled checkouts. Opt-in via `AUTOAGENT_DB_URL`.
- New `engine/test_control_pg.py`: adversarial proof against a real local Postgres.
  Provisions a throwaway DB + a NON-superuser role (superusers bypass RLS), then
  proves scoped reads see only own rows, no-tenant => 0 rows (default-deny), WITH
  CHECK blocks cross-tenant writes, cross-tenant UPDATE/DELETE = 0 rows, isolation
  generalizes across tables, every table policied. 6/6 green; suite 1140.
- This validates Fork B's core security claim end-to-end — RLS is a real boundary,
  not an assumption.

**Phase 4a — execution sandbox runner, boundary PROVEN (`ad64a18`):**
- New `engine/sandbox.py`: the seam at run.py's one spawn site. `get_runner(ctx)`
  → `LocalRunner` (host, byte-identical default) or `ContainerRunner` (Fork A) when
  `config.sandbox == container`. `ContainerRunner` wraps the command in `docker
  run` with the tenant volume mounted, ONLY whitelisted env crossing (BYOK key +
  tenant vars), non-root user, `--read-only` + `--cap-drop ALL` +
  `no-new-privileges`, memory/cpu/pid caps. Misconfig fails closed.
- run.py now calls `runner.wrap(...)` instead of hardcoding cwd/env — default
  unchanged.
- New `engine/test_sandbox.py`: unit contract + a REAL-container proof (launched
  kali) — uid 10001 (non-root), injected key present, a host env var did NOT
  cross, own volume readable, host-only file invisible by abspath. Suite 1148.

**Phase 3 — BYOK vault, encrypted at rest (`ef2e43d`):**
- New `engine/vault.py`: per-tenant Fernet-encrypted secrets; ciphertext-only on
  disk (0600, atomic); master key solely in `AUTOAGENT_VAULT_KEY`. Control plane
  decrypts only that tenant's secrets and injects into its sandbox; container
  never sees the master key or another tenant's blob. Wrong key => InvalidToken.
- run.py `_vault_byok_key()`: vault > config.json > $BYOK_ANTHROPIC_API_KEY.
  Back-compat: None unless the vault key is set AND the tenant has a vault.
- New `engine/test_vault.py`: round-trip; disk has neither secret value nor key
  name; 0600; wrong/missing key; per-tenant isolation; path-traversal rejected;
  vault-wins proven through run._build_child_env. Suite 1161.

**Session outcome:** the three isolation primitives — data (RLS, 2a), execution
(container, 4a), secrets (vault, 3) — are built and each PROVEN against real infra.
~40 new tests, 1161 total, all green. Everything behind the single-tenant default.

**Remaining:** Phase 2b (data cutover) surfaces the one Seb deploy decision —
where prod control-Postgres runs (Railway / Supabase / self-hosted) + migrating
`~/.autoagent/agency.db`. Phases 5–6 (control-plane API + provisioning that wires
row+volume+vault+container) + the agent Docker image are assembly, partly gated on
2b. Building continues behind the flag; Seb flips it when prod PG exists.

## 2026-07-12 — Self-serve isolation Phase 6 + adversarial hardening

**Phase 6 — provisioning/teardown + agent image (`a2f2344`):**
- `engine/provisioning.py`: tenant lifecycle — provision (registry row + volume +
  vault seed) / deprovision (soft default; hard delete behind guards). Registry is
  a control-plane JSON file (→ Postgres in Phase 5).
- `deploy/Dockerfile.agent` + `.dockerignore`: per-tenant sandbox image, non-root
  uid 10001, no baked secret, engine on PYTHONPATH.
- `engine/tenant.py`: `is_valid_tenant_id`/`require_valid_tenant_id` SSoT; vault uses it.

**Adversarial review + hardening (`77d949b`):** ran a 24-agent Workflow (find →
verify) over the destructive/secret paths + image. 14 confirmed defects, all fixed:
- teardown swallowed vault/PG cleanup failures then reported success (stranger's
  ciphertext + control rows survive a "deleted" tenant) → now all-or-nothing,
  status='delete_failed' + raise on any cleanup error.
- data_root override + containment-only guard → cross-tenant volume deletion. Guard
  now requires the exact canonical per-tenant path; override param dropped.
- corrupt tenants.json → next save erased all tenants → now fails loud; + flock.
- BYOK key in `docker -e KEY=VALUE` argv (host process table) → forwarded name-only
  via the docker CLI env; value never in argv.
- `_vault_byok_key` swallowed decrypt errors → silent fallback to operator key →
  InvalidToken now propagates.
- Dockerfile chowned /opt/autoagent to tenant (engine writable) + no writable HOME
  under --read-only → engine stays root-owned, HOME under /workspace.
- MED (documented, not code-fixable): bare bridge networking reaches cloud
  metadata / control plane / siblings. Recorded as a LAUNCH GATE (egress proxy
  required before untrusted signups) in sandbox.py + the architecture doc.

**Files:** engine/provisioning.py, engine/sandbox.py, engine/vault.py,
engine/tenant.py, engine/run.py, deploy/Dockerfile.agent, .dockerignore, +
test_provisioning/test_sandbox/test_dockerfile/test_vault. Suite 1182 pass.

## 2026-07-14 — Egress gate (untrusted-signup launch blocker)

**Decision:** prod control-Postgres = **Railway** (for Phase 2b).

**Egress gate (`3ffb815`):** closed the bare-bridge exposure.
- `engine/egress.py`: tenant containers on a Docker `--internal` network (no
  off-host route) + a dual-homed allowlist proxy as the only way out. Pure argv
  builders + docker-gated ensure_egress().
- `engine/sandbox.py`: SandboxSpec.proxy_url injects HTTPS_PROXY/NO_PROXY (non-
  secret); get_runner reads config.sandbox_proxy_url. Off by default.
- `deploy/egress-proxy/`: tinyproxy image, FilterDefaultDeny, CONNECT 443 to
  api.anthropic.com only. Non-root. Blocks metadata / control plane / siblings.
- PROVEN vs real Docker: TCP probe to 1.1.1.1:443 succeeds on bridge, fails on
  --internal. Suite 1192 pass.

**Remaining for self-serve:** build+publish proxy image + stand up on Railway;
Phase 2b (agency_db → Railway Postgres, decision locked); Phase 5 control-plane
API (auth + signup + POST tenants/sessions); build+verify agent image runs a real
session; billing. Concierge remains launch-ready today.

## 2026-07-14 (cont.) — Agent image verified + Phase 5 loop code-complete

- **Agent image (`41c98e8`):** built `deploy/Dockerfile.agent`, smoke-tested through
  the real `ContainerRunner` — uid 10001, claude CLI runs, engine importable +
  read-only, /workspace writable. `engine/test_agent_image.py` (gated).
- **Phase 5 API (`543cff3`):** `engine/control_api.py` (FastAPI) — admin token
  provisioning + per-tenant token auth (sha256 in registry) + `POST /sessions`
  enqueue, tenant-scoped (cross-tenant job = 404). `engine/job_queue.py` FIFO.
- **Session worker (`6accfbf`):** `engine/session_worker.py` — claims jobs → runs
  each in its tenant sandbox (tenant env injected) → marks done/failed; hard loop
  cap. **Self-serve loop code-complete:** signup → provision → enqueue → worker →
  confined sandbox run → status.
- Suite 1217 pass.

**Left for PRODUCTION launch (not code):** deploy control API + worker + egress
proxy + Railway Postgres; wire Phase 2b (agency_db → PG, flag flip); egress-proxy
allowlist live-verify; billing/metering; a full staging run of a real tenant
session end-to-end; rotate the leaked PAT/Telegram (Seb). Concierge: launch-ready.

## 2026-07-05 — Opt-in SDK judge: skip the 117s nested-claude CLI

**Why:** the Agent-as-Judge rubric call (`engine/judge.py:_call_judge_llm`) shells
out to a nested `claude -p`. Measured 117.7s on a trivial diff — standalone, with
no concurrent session claude — so the cost is CLI cold-start + inference, NOT the
OAuth contention the old comment blamed. In the live loop the judge runs in
`post_session_improve` after the session claude has already exited, so contention
never applied. An in-process Anthropic SDK call is the only real fix.

**Changed (`engine/judge.py`):**
- `_call_judge_llm` is now a dispatcher: fast SDK path when a judge key is set,
  else the unchanged CLI path (renamed `_call_judge_llm_cli`).
- `_call_judge_llm_sdk` — `client.messages.create` on `JUDGE_MODEL`, returns the
  parsed rubric, or `None` on any infra failure (import/init/API/empty) so the
  caller falls back to CLI instead of pinning every verdict at 5.
- `_judge_api_key` — `JUDGE_ANTHROPIC_API_KEY` > `COUNCIL_ANTHROPIC_API_KEY` >
  `ANTHROPIC_API_KEY` > None. Opt-in because the SDK bills API rates while the
  session/CLI judge rides the Max plan (no env key by design).
- `_parse_rubric_reply` — single JSON-extraction path shared by SDK + CLI.

**Behavior:** zero change unless a judge key is set — the loop stays on the free
117s CLI path by default. Set `JUDGE_ANTHROPIC_API_KEY` (in `.env` or the
LaunchAgent plist) to switch the judge to a ~5-15s SDK call (trivial per-call
cost; fires only on deterministic-pass sessions).

**Verified:** `test_judge.py` 38 pass (0.47s, hermetic — +12 SDK/dispatch/key
tests, autouse fixture pins existing tests to CLI path); judge+self_improve+
post_session 68 pass. Real-SDK smoke: bad key fails fast (0.7s) → clean CLI
fallback, fail-loud logged. Valid-key SDK latency not measured — no key in env.

## 2026-06-13 — Fix hooks writepath bug: inline `--settings` delivery

**Why:** `engine/run.py` installed Claude Code quality-gate hooks by writing
`project_root/.claude/settings.local.json`. From sandboxed main-thread Claude
Code this write fails; the 2026-06-03 try/except merely swallowed it, so the
gates (gitignore/inspector/syntax/auto_test) silently vanished. Root-cause fix:
deliver hooks inline on the CLI argv, never touch the project tree.

**Changed:**
- `session_hooks.py`: + `generate_hooks_settings_json(ctx)` (= json.dumps of
  generate_hooks_config). `write_hooks_config` retained as a utility but no
  longer called in the session spawn path.
- `engine/run.py`: removed `write_hooks_config(ctx)`; added
  `--settings generate_hooks_settings_json(ctx)` to `claude_args`.
- `session_analytics.py`, `session_helpers.py`: re-export the new helper.
- `test_session_hooks.py`: +2 tests (valid JSON w/ hooks block; matches config dict).

**Verified:** 21 session_hooks + 189 changed-module tests green; CLI v2.1.177
accepts the inline 2KB hooks JSON (`claude --settings <json> mcp list` exit 0);
both engine trees compile + import. Pre-existing unrelated red:
`test_run_py_under_400_lines` (502 lines).

**Scope note:** fix covers the agency path (`autoagent run` → engine/run.py)
only. The top-level `run.py` (legacy `py launcher.py`, used by cultivOS sprints)
never wrote hooks and still runs gate-less — giving it real gates needs the hook
commands rewritten for an absolute engine path + project `PYTHONPATH`; deferred.


## 2026-07-07 — Agentric launch readiness review
Ran a 12-agent review of skills/, templates/agents/, PROMPT-*.md, meta/, docs/, and engine/ architecture against the Agentric multi-tenant launch lens. Verdict: **NOT-READY**, fixable in a focused 1–2 week strip-and-scope sprint. Full prioritized plan (8 P0 blockers incl. a security emergency, 10 P1, 7 P2, 14 quick wins) in `docs/AGENTRIC_LAUNCH_REVIEW.md`. Review only — no source changed.
Reasoning: the engine's tenancy guardrail, prompt hardening, and failure-catalog IP are sound; the blockers are almost all strip-and-scope of past-client (CultivOS/StockCards) content baked into "universal" assets, plus stale model ids and 4 runtime bypasses of the skill gate.

## 2026-07-07 (cont.) — Autonomous de-leak sprint continued
P0-4 tail + P1-2 + P0-3 + P0-2 shipped (commits 286a3fd, 17eb4f9, dbe5bb0, 9655a5c). All universal engineering skills de-branded; format-skill examples genericized; project_context/design/brand-guidelines/bilingual quarantined behind the runtime skill gate; INDEX injection now scoped so a generic tenant's system prompt carries no project-domain routing. 1066 engine tests pass. See docs/AGENTRIC_LAUNCH_REVIEW.md for the remaining Seb-gated items.

## 2026-07-07 (cont.) — P0-7 model-ID refresh + P1-1 audit rewrite
Client-facing half of P0-7 (stale model ids purged from every runtime call site and the shipped client template). Files: `skills/claude_api.md` fully refreshed to the current family (Fable 5 / Opus 4.8 / Sonnet 5 / Haiku 4.5) — corrected thinking/effort/prefill semantics, added a Fable-5 refusal-fallback section, fixed the Managed-Agents example (Agent-once → Session-per-run, correct event-stream shape), de-branded the cultivOS coupling on line 5. Call sites bumped to current tiers: `advisor.py` executor `sonnet-4-6`→`sonnet-5` / advisor `opus-4-7`→`opus-4-8` (valid advisor≥executor pair), `judge.py` `sonnet-5`, `digest.py` / `article_distiller.py` / `director_intelligence.py` `sonnet-5`. `config.example.json` (client template) `opus-4-6`→`opus-4-8`; `config.json` (agency runtime, gitignored) tiers preserved, ids current; `templates/PROMPT.md` placeholder `sonnet-5`.
`council_usage.py` cost table: **fixed a real bug** — Opus-tier was priced `$15/$75` (Opus-3-era; ~3× too high) which tripped the provider budget gate and would trip the $40/tenant council cap at ~$13 real spend. Corrected to `$5/$25`, Haiku to `$1/$5`, added `claude-fable-5` / `claude-sonnet-5` entries; old ids retained for historical-row / pinning back-compat. Two coupled test assertions updated (`test_judge.py`, `test_advisor.py`). Earlier same session: `audit.md` rewritten to 6 real universal reviewers (removed ghost reviewers Priya/Jordan/Chen + cultivOS-specific reviewers), commit 114d1eb. 1066 engine tests pass. Model-TIER default (opus-4-8 kept, sonnet-5 candidate) and engine/models.py SSoT remain Seb-gated.

## 2026-07-07 (cont.) — P1-4 phantom asset scripts purged from media skills
Four media skills instructed a tenant agent to run bundled helper scripts that don't exist in this repo (a 404 the moment the agent copied the command). Verified each against the filesystem, then rewrote to self-contained equivalents that use tools the agent already has:
- `web-artifacts.md`: `scripts/init-artifact.sh` + `scripts/bundle-artifact.sh` (missing) → write ONE self-contained `.html` directly (matches the skill's own "one file, everything embedded" principle); dropped the stale "40+ pre-installed shadcn" claim.
- `pptx.md`: `scripts/thumbnail.py` (missing) → LibreOffice headless `soffice --convert-to pdf` + `pdftoppm`.
- `docx.md`: `scripts/office/{validate,unpack,pack}.py` (missing) → validate by opening with python-docx; unpack/repack via `unzip`/`zip` (a .docx is a zip), matching pptx.md's existing pattern.
- `canvas-design.md`: mandated fonts from `./canvas-fonts/` (missing dir) → reworded to "design-forward typography, project fonts dir if present, else a well-chosen installed face".
`scripts/extract_design_system.py` referenced by `claude-design.md` was verified to EXIST — left as-is. No engine code references the phantom scripts; skill-doc only, no test impact.

## 2026-07-07 (cont.) — P1-3 convention consolidation + fabricated-citation purge + residual de-leak
Three fixes across 9 universal skill docs (skill-doc only; org/registry/run/session tests 110/110 pass, departments.json net-unchanged):
1. **Commit-convention contradiction (P1-3 core):** `quality-standards.md` §1 mandated `test:`/`feat:` conventional-commit prefixes while `git.md` (and PROJECT.md `commit_prefix`) use the project's configured prefix (`agent:`). Aligned §1 to `<prefix>(test):` / `<prefix>(feat):` and cross-linked git.md (message format) + testing.md (fail-before) so each convention has one home.
2. **Fabricated citations:** purged unverifiable `arxiv NNNN.NNNNN` and named-framework citations from `git.md` (1), `testing.md` (2), and `agent-patterns.md` (~14 — the always-loaded failure catalog). Kept every failure-mode + fix and the concept names; removed only the invented authority/statistics. A shipped product cannot carry citations a customer can 404. Per the project's own claim-source-discipline: an uncited-but-correct claim beats a fabricated-citation one.
3. **Residual past-client/operator de-leak** (missed by the earlier P0-4 sweep): `quality-standards.md` (Rancho Don Manuel / `/api/farms` → generic items), `clean-architecture.md` (farm models → order/item), `agent-patterns.md` (`src.cultivos` paths + thermal/health ag examples → myapp/generic), `git.md` (cooperative/outbreak ag commit example → order-total), `testing.md` (hectares columns → generic), `replicate.md` (`--project cultivOS` + hardcoded "Seb" operator → myapp / "the operator"), `ui-stack.md` (agency/Seb/RedHunter framing → generic build stack), `claude-design.md` (full rewrite: agency/council/Seb/ITESO/JPL/cultivOS doctrine → generic design↔code standard), `claim-source-discipline.md` (full rewrite: cultivOS-pitch known-offender list — Sebastián/AFAC/DGAC/Agras T100/Deveron/Farmers Edge/Ontario-specialty-crop — → domain-agnostic offender categories, keeping the universal rule/hierarchy/workflow).
Considered gating `claude-design`/`ui-stack` behind project_domain but reverted — INDEX routes generic UI work to them, and whether the agency design doctrine should be the tenant default is a Seb scope call; de-branding keeps them universal + tenant-safe. INDEX project-domain rows confirmed inside the `<!-- PROJECT-DOMAIN -->` fence (gated, not leaks).

## 2026-07-10 — Concierge-launch hardening (Phases 1–4; Phase 5 = operator)
Operator chose the concierge launch (run the engine for hand-onboarded clients, like the current 2 @ $399 BYOK). Honest gap: everything hardened is the ENGINE — there is NO product layer (no hosting/Dockerfile, auth, billing, signup, provisioning, BYOK vault; "multi-tenant" = project folders on one machine sharing a process + agency.db + council pgvector). Concierge is close; self-serve SaaS is weeks-to-months of net-new build. Shipped the concierge blockers:
- **Phase 1 — severe safety (commit 3d04780):** db_maintenance.prune_test_data matched real tenant names by substring → could cascade-delete a client named "acme-test"/"demo-co"; now requires name-match AND unregistered (registration = tenant-safety boundary). session_hooks security inspector signalled block with exit(1) but Claude Code only blocks on exit(2) → dangerous/secret/exfil commands ran anyway; now exit(2) (gitignore check stays exit 1 by design — hard-blocking gitignored writes would brick memory/config). self_improve_analyzers cross-project rule/security sharing (client A's rules → client B) gated behind AUTOAGENT_CROSS_PROJECT_SHARING (default OFF). +5 tests.
- **Phase 2 — isolation proof (commit bfc1c4c):** engine/test_tenant_isolation.py provisions 2 tenants, asserts disjoint on-disk state + per-tenant council ledger + sharing-off + prune-never-touches-registered. The "safe to onboard client N+1" artifact.
- **Phase 3 — fixes reach prod (commit d0d0b3c):** adopted templates/PROMPT.md = the 642-line compiled superset from the hardened satellites (was the weak 233-line monolith; closes the top multi-tenant risk); dropped stale py/master/model-id bits; removed .compiled.md preview. scripts/deploy_to_live.py closes repo≠live: backs up, syncs engine+templates → ~/.autoagent, force-refreshes frozen per-tenant PROMPT.md copies; DRY-RUN default, --apply to deploy. +4 tests.
- **Phase 4 — client-adding bugs (commit 700bac7):** telegram_intake project-name uniqueness (_unique_project_name, suffix -2/-3 vs registry — no tenant home/db/symlink collision); pre-push test gate revived (reads project.json test_command fallback + expanded runner allowlist + logs-instead-of-silent-pass for unrunnable commands; real failures now block). +9 tests.
1125 engine tests pass. **PHASE 5 (operator-only, the actual gate):** (1) rotate the leaked PAT+Telegram token + purge history (runbook docs/SECURITY_PURGE_2026-07-08.md); (2) run `python3 scripts/deploy_to_live.py --apply` after diffing the new templates/PROMPT.md vs the deployed ~/.autoagent copy. After those two, the concierge model is launch-ready.

## 2026-07-08 (cont.) — 3 post-queue workstreams (operator-chosen): bug-hardening + de-brand + prompt-stack
After the 6-item queue, operator picked 3 more workstreams. All shipped:
- **Bug-hardening (commit 5a05c00 + deferred doc 59f6e4c):** ran a second exhaustive bug-sweep (8 concern-clustered finders → 33 candidates → adversarial verify → 27 confirmed / 3 refuted). Fixed the 13 clearly-correct: task_graph duplicate-dep phantom-cycle (was disabling parallel exec), tool_inspector exfil-warning-before-secret-block SECURITY downgrade, trace_capture lexicographic sort deleting newest traces (x2), session_helpers unsatisfiable auto-route guard (dead code), opportunity_scanner date-in-title corrupting staleness, self_improve_analyzers + knowledge_compiler wrong session/tests keys (metric stuck at 0, "#None" fed to wiki prompt), orchestrator test-count regex, agent_router orchestrator-as-specialist, article_distiller KeyError-on-missing-field, telegram_intake "pick" substring beating explicit stack, agency_db_queries logging a function object. +8 regression tests. The 14 decision-gated findings → `docs/BUGSWEEP_DEFERRED_2026-07-08.md` (2 severe: db_maintenance substring project-match = cascade-delete risk; session_hooks exit-1 = security hooks never actually block; + a cross-tenant knowledge-sharing leak in self_improve_analyzers).
- **Director-layer de-brand (commit 6cccbef):** removed the hardcoded `["cultivOS","StockCards","KitchenIntelligence","autoagent"]` roster (4 sites → registry.list_projects() via _project_names), the "Hey Seb"/"Seb (agency owner)" operator-name leaks across director_ai/helpers/commands/intelligence/brain + comms/post_session/replicator/digest, the stockcards.ca /deploy health hardcode (→ per-project config health_url), and council/memory.py's `redhunter:redhunter_local_dev` DSN default (→ neutral). cli.py/registry/self_improve example strings cultivOS→myapp. Non-test engine now leak-clean except the fully-scoped-out red_*/bounty/empathy_sim/visual_check cockpit (P1-10 fate = operator). 
- **Prompt-stack consolidation (commit d54d2ce, P0-6):** built `scripts/build_template_prompt.py` — compiles the shipped tenant `templates/PROMPT.md` FROM the 5 hardened satellites (RECOVERY→WORK→CONTEXT→FAILURE→VERIFICATION), tenant-safe filter strips ADVISOR/COUNCIL (BYOK infra) + genericizes agency specifics. Generated `templates/PROMPT.compiled.md` PREVIEW (642 lines vs live 233 — leak-clean superset; closes the "shipped template weaker" top multi-tenant risk). Preview only — does NOT touch the live template; operator diffs + adopts via `--write`. +4 tests. 1105 engine tests pass.
**Night total: 14 commits (b871dde → d54d2ce), 1105 tests green.** Remaining = operator-only: security rotation+force-push (runbook ready), adopt the compiled prompt (`--write` after diff), P1-10 director cockpit fate, the 14 deferred bug findings, F2/F3.

## 2026-07-08 — #5 README/CLAUDE fact-fix + de-leak (commit ed12ff8); overnight queue COMPLETE
P1-9. Both top-level orientation docs described the legacy launcher loop with wrong counts and, worse, README published a live client roster (cultivOS/StockCards/KitchenIntelligence names + metrics) in a repo meant to ship. CLAUDE.md rewritten around the `autoagent` CLI + engine/cli.py→run.py path (586 lines), correct 6-type session routing (keyed on session_num, not `%20`), 46 skills (was 27), models.py SSoT + org-scoping notes, operator-machine plugin internals trimmed. README: removed the "Currently managing" client table, fixed tests to 1093/70 files. Kept AutoAgent framing — introducing the "Agentric" product name is a positioning call left to Seb. Verified both docs clean of client/operator names + stale facts.

**OVERNIGHT QUEUE COMPLETE** (6 commits pushed to agentric-launch-polish): b871dde (#2 cross-tenant recall leak), 68f7b10 (#1/P0-8 tenant council cap), a90e42a (#3 bug-sweep F1/F4/F5), 6e7785d (#4 security-purge runbook + #6 prompt-stack map), ed12ff8 (#5 README/CLAUDE). 1093 tests pass throughout.

**REMAINING — all Seb-gated (NOT auto-doing; needs his decision/action):** (1) SECURITY: rotate leaked PAT+Telegram + run the force-push purge (runbook ready in docs/SECURITY_PURGE_2026-07-08.md). (2) P0-6 prompt-stack consolidation — compile templates/PROMPT.md from the 5 hardened satellites; open Qs: is legacy root run.py alive? ship ADVISOR/COUNCIL to BYOK tenants? was the Jul-7 condensation a regression vs the 24KB deployed copy? (3) P1-10 director-layer fate + de-brand — director_ai.py hardcodes `["cultivOS","StockCards","KitchenIntelligence","autoagent"]` (4 sites), director_helpers.py hits stockcards.ca/api/health, whole red_*/bounty_portfolio/cli_red RedHunter cockpit, council/memory.py DSN default embeds `redhunter:redhunter_local_dev` creds — whether the cockpit ships to Agentric at all is Seb's call, and the DSN change would alter his running infra. (4) F2 gemini pricing (needs price card), F3 model_fallback.py unmetered+ungated+drifted-taxonomy (design cluster). Stopped expanding scope into founder-decision territory per discipline.

## 2026-07-08 — Bug-sweep fixes F1/F4/F5 (commit a90e42a) + security-purge runbook + prompt-stack map
Engine bug-sweep (12-finding subagent → 5 prioritized → adversarial verify workflow: 3 CONFIRMED, 2 errored/deferred). Fixed the 3 confirmed:
- **F1 run.py:489 — dead council gate.** Gated on `session_type=="work" and session_num % 5 == 0`, but get_session_type routes every multiple of 5 to a NON-work type, so the intersection is empty — the council never convened on a ship under auto-routing (only via forced `--type work` / `autoagent parallel`). This made the prior two commits' tenant-scoping + budget threading inert in prod. Fixed to `% 5 == 1` (always a work session under the routing cadence; the work-type guard degrades safely if cadence changes). Verified empirically: old gate fires on ∅ in 1..200; new fires on 1,6,11,16,21,26,… all work.
- **F4 council/backends.py — $0 usage default.** `_call_claude_api` logged usage with fallback model `"claude-sonnet"` (absent from MODEL_PRICING/MODEL_PROVIDER → $0 under provider "other") when the API response omitted "model". Hoisted the requested `model_id` (`$COUNCIL_ANTHROPIC_MODEL` or `claude-opus-4-8`) and reuse it as the fallback — a real priced anthropic key.
- **F5 models.py + 4 sites — daily-limit SSoT.** `daily_limit_usd` default split 50.0 (intake, writer) vs 15.0 (run.py budget_ok / cost_predictor / runner readers) → unconfigured project metered at 15/day in API mode instead of 50. Centralized `models.DEFAULT_DAILY_LIMIT_USD = 50.0`, wired all 4 sites.
Deferred to Seb (NOT fixed): F2 gemini-flash pricing (`gemini-2.5-flash` $0.15/$0.60 possibly stale; can't verify fictional-world prices without a card — don't change blindly), F3 `model_fallback.py` (rate-limit path is UNMETERED + UNGATED and carries a drifted model taxonomy gpt-5.4/gemini-3.1-pro-preview/deepseek-v3/claude-sonnet — a design cluster, not a cosmetic id bump). +4 regression tests. 1093 engine tests pass.

**#4 SECURITY-PURGE-PREP** (`docs/SECURITY_PURGE_2026-07-08.md`, committed). Pinned the leak: GitHub PAT (first in `eed520d`) + Telegram token (first in `55bc7d0`) across 5 historical file paths (config.json, launcher.py, engine/comms.py, engine/director.py, docs/AUDIT_2026-04-16.md); HEAD is clean. Confirmed `git-filter-repo` installed + pre-commit hook (`scripts/check_secrets.sh`) covers all patterns + is armed. Wrote a full runbook (rotate→backup→filter-repo regex replace→force-push→re-clone→verify) + a regex rules file at `scratchpad/replace-rules.txt` (no token values anywhere). Verified the `ghp_[A-Za-z0-9]{36,}` rule does NOT touch the short detection-literal `ghp_` in check_secrets.sh/security.md/config.example.json/AUDIT_PROMPT.md (purge is scope-safe). STILL SEB ACTION: rotate creds + run the destructive force-push (Claude cannot rotate creds or rewrite shared history).

**#6 PROMPT-STACK MAP** (subagent report, captured to memory — Seb decision, no files touched). Critical finding: TWO parallel hand-maintained prompt trees + THREE physical copies of the shipped template. The live/Agentric engine (`registry.py:29` → `~/.autoagent/templates/PROMPT.md`) NEVER reads the hardened root `PROMPT-*.md` (5 satellites); only the legacy root `run.py` path does. The shipped `templates/PROMPT.md` (233-line monolith) is a condensed re-implementation that's materially WEAKER than the hardened stack — missing the entire `PROMPT-RECOVERY.md` concurrency/multi-writer safety (highest multi-tenant launch risk), ADVISOR/COUNCIL, SESSION INVARIANTS, the full failure ladder, and context-discipline depth. Worse: the DEPLOYED `~/.autoagent/templates/PROMPT.md` (24KB, May 27) is older+larger than the repo's already-weaker copy (15KB, Jul 7), and `_sync_templates` is copy-if-absent so 18 onboarded tenants have frozen stale copies. Proposal: make the 5 satellites the SSoT and COMPILE `templates/PROMPT.md` from them via a `scripts/build_template_prompt.py` (tenant-safe filter), retire the twin. Open Seb calls: (a) is the legacy root run.py path still alive? (b) ship ADVISOR/COUNCIL to BYOK tenants? (c) was the Jul-7 repo condensation itself a regression vs the 24KB deployed? — diff before compiling.

## 2026-07-07 (cont.5) — P0-8 per-tenant comped-council budget cap (commit 68f7b10)
The council spend gate (`check_provider_budget`) was global + fail-open — no tenant dimension — so a single Agentric tenant could burn the operator's comped council spend without limit. Implemented the signed $40/tenant/month cap as a second gate that stacks on the provider gate.
- `council_usage.py`: separate tenant ledger `~/.autoagent/council_tenant_usage.json` (`{tenant: {"YYYY-MM": {cost_usd, calls}}}`) so the existing global rollups stay the SSoT for total-API spend. New `record_tenant_council_call`, `get_tenant_monthly_spend`, `get_tenant_council_cap` (default `DEFAULT_TENANT_COUNCIL_CAP = 40.0`, `spending_config.json "tenant_council_cap"` overrides), `check_tenant_budget` — contract mirrors `check_provider_budget` exactly (None tenant → allowed; fail-OPEN on any error so a gate bug never bricks a paying tenant; blocks only when `spend >= cap` is proven). `record_council_call` gained optional `tenant=` that attributes the same computed cost to the tenant ledger.
- `council/backends.py`: a `contextvars.ContextVar` (`_current_tenant`) carries the in-flight tenant so every provider call attributes + is gated per tenant WITHOUT threading a param through all eight `_call_*` callers (council is sequential — no thread fan-out, so a ContextVar suffices). `set_council_tenant`/`reset_council_tenant` exposed. `_budget_gate` checks the tenant cap first, then the provider budget; `_record_usage` injects the bound tenant.
- `council/executive.py`: `convene_council` gates the whole run up front when the tenant is over cap (returns `{budget_exceeded: True, confidence: LOW}` instead of half-running the council), binds the ContextVar for the pipeline, resets in `finally` so the binding never leaks across calls. Only an explicit `project=` gates — the context-first-line fallback is not a real tenant boundary.
- +18 tests across `test_council_usage.py` (ledger accumulation/isolation, cap + config override, fail-open, record attribution) and `test_council_backends.py` (backend blocks when tenant over cap, unbound no-op passes None, reset-no-leak). 1089 engine tests pass. P0-8 COMPLETE.

## 2026-07-07 (cont.4) — Cross-tenant council-memory recall leak closed (commit b871dde)
`council/memory.py` stored every convene_council verdict in a shared `council_episodic` pgvector with a `project` column (written by `persist()`), but the three recall paths (`recall_similar`, `recall_analogical`, `recall_combined`) queried `WHERE question_hash <> %s AND embedding IS NOT NULL` with **no project filter** — so tenant A's recall surfaced tenant B's verdicts. A client-data leak the moment two Agentric tenants share the store.
Fix: added an optional `project` filter `AND (%s::text IS NULL OR project = %s)` (NULL = unscoped, preserves single-tenant back-compat) threaded through all three recall fns; `convene_council` / `convene_council_with_debate` gained a `project` param and derive `project_key = project or context-first-line` (explicit project is the isolation boundary, context-line only a back-compat fallback); `persist()` and `log_council_decision` now key off `project_key`; the task-selection council keys off `project_name`. **run.py:495** ship-gate now passes `project=ctx.name` — the multi-tenant hot path. Files: `engine/council/memory.py`, `engine/council/executive.py`, `engine/run.py`, new `engine/test_council_memory_scope.py` (+4 hermetic tests: project binds into SQL params, None stays unscoped, recall_combined threads project to both recalls). 1077 engine tests pass. Closes the critic-HIGH "council/memory.py recalls cross-tenant" item without needing a live pgvector.

## 2026-07-07 (cont.) — P0-7 ENGINE half: engine/models.py model SSoT
Built `engine/models.py` as the single source of truth for Claude model ids + per-session-type tier defaults, killing the scattered-literal drift that let stale ids accumulate. Tier decision (Seb): **work sessions → `claude-sonnet-5`; meta/brain/deep/audit → `claude-opus-4-8`**; `DEFAULT_MODEL = claude-opus-4-8` for fresh configs. Exposes `resolve_model(config, session_type)` with precedence config `models.{type}` → config `model` → SSoT tier default (always returns a real id, so callers never guard a missing model). Rewired the four drift sources to it: `run.py` session routing (`resolve_model`), `intake.py` / `init_agency.py` / `registry.py` fresh-config `DEFAULT_MODEL`. Per-feature deliberate call-sites (judge/advisor/digest — already refreshed to current ids this session) left as explicit choices; models.py exports the ID constants for them to adopt over time. No import cycle (models.py is a leaf — imports only typing). +7 tests in `engine/test_models.py` (resolve precedence, session defaults, silent-config fallback). 1066 full suite pass. P0-7 now COMPLETE (client + engine halves).
