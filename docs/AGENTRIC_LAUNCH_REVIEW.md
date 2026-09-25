# Agentric Launch Review — AutoAgency (skills · prompts · agent templates · engine)

> Generated 2026-07-07 by a 12-agent review workflow (10 domain reviewers → synthesis → critic fact-check). 10 reviewers, 110 raw findings.

**LAUNCH READINESS: NOT-READY**

Three independent reviewers confirmed the multi-tenant skill gate is nullified at runtime, and client-specific brand, strategy, and personal content reaches every tenant through at least four distinct paths (session sync, INDEX injection, unscoped shared files, and universal agent templates). A launch today would visibly put a past client's brand voice, competitive moat, and founder's name into a new client's deliverables — the exact failure the product promises to prevent. Add stale model ids in shipped defaults and a product prompt path that never loads the hardened executor stack, and the current state fails both the G4 zero-jargon gate and basic tenancy isolation. However, the architecture underneath is sound and the fixes are small and localized: a focused 1–2 week de-leakage and consolidation sprint (the P0 list) gets this to launchable, not a rebuild.

---

## ⚠️ SECURITY EMERGENCY (do first — needs Seb)

`docs/AUDIT_2026-04-16.md` (git-tracked) prints a **live GitHub PAT and Telegram bot token verbatim**, documented as still unrotated. Actions, in order:
1. **Seb, now:** revoke the GitHub PAT (github.com/settings/tokens) and regenerate the Telegram token via @BotFather.
2. Redact the two values from the audit doc.
3. BFG/`git filter-repo` history purge + single coordinated force-push (destructive — needs Seb's go).
4. Add a `check_secrets.sh` pre-commit hook (ghp_ / sk-ant- / Telegram regex).

## Executive summary

The engine's bones are genuinely strong — the project-domain scoping mechanism in org_model.py, the hardened root prompt stack, the agent-patterns failure catalog, and the judge/budget hardening are real, differentiated IP. But the repo is not launch-ready as a multi-tenant product: the flagship skill-visibility guardrail is defeated in production by three independent bypasses (the per-session template sync copies every CultivOS skill into each client project, INDEX.md with CultivOS/StockCards routing is injected verbatim into every system prompt, and the gate fails open on any exception). Past-client DNA — cultivOS, StockCards, PolyEdge, and Seb personally — is baked into "universal" skills, the two growth agent templates copied into every client, core executor prompts, and even the meta-skill that creates future skills, making the leakage self-replicating. Model ids are two generations stale in exactly the defaults that ship (intake.py writes claude-opus-4-6 into every new project; claude_api.md tells the agent to bake stale ids into client code), spread across four disagreeing registries. The product path also ships the thin, unhardened templates/PROMPT.md while months of validated hardening sits in root PROMPT-*.md files clients never receive. The good news: the fix surface is well-localized — nearly every blocker is a strip-and-scope operation on a sound architecture, not a rebuild, and several of the worst leaks close with one-condition code changes. Do not let the polish pass "fix" the mechanisms themselves: the scoping gate, concern-split prompts, evidence-cited rule culture, and the CultivOS content (as a relocated project-local pack) are exactly right and should be preserved.

## Cross-cutting themes

### The multi-tenant guardrail is real but defeated at runtime
engine/org_model.py's project-domain scoping is well-designed and tested, but production nullifies it three ways: _sync_templates copies every shared skill into project-local dirs (unconditionally visible) at every session start, run.py injects the CultivOS-saturated INDEX.md verbatim into every system prompt, and registry.all_skills() fails OPEN to a full glob on any exception. CI stays green because tests never exercise the sync path. The fix is closing bypasses, not rebuilding the gate.

*Affected:* engine/session_helpers.py, engine/run.py, engine/registry.py, run.py, skills/INDEX.md, engine/test_registry.py

### Past-client DNA baked into 'universal' assets — and self-replicating
cultivOS, StockCards, PolyEdge, absolute /Users/SebSan paths, and Seb by name are hard-wired into skills INDEX labels 'safe for every project', into both growth agent templates copied into every client project, into the core executor prompts, the audit gate's reviewers, the META/BRAIN prompts, and the director layer. Worst: skill-creator.md MANDATES a StockCards section in every future skill, so the contamination reproduces itself.

*Affected:* skills/ (30+ files), templates/agents/, PROMPT-*.md, meta/, engine/director_*

### No single source of truth for model ids; shipped defaults are two generations stale
At least four independent model registries disagree: intake.py writes claude-opus-4-6 into every new project.json, claude_api.md recommends 4.6-era ids for client code, config.json/run.py pin opus-4-7, advisor/judge/digest pin sonnet-4-6, and INDEX/replicate cite 'Opus 4.7 vision'. Nothing references the current family (Fable 5 / Opus 4.8 / Sonnet 5 / Haiku 4.5) except one council default.

*Affected:* engine/intake.py, skills/claude_api.md, config.json, run.py, engine/advisor.py, engine/judge.py, engine/model_fallback.py, skills/INDEX.md, skills/replicate.md

### Two diverging stacks: the product path ships the weak copy
The hardened root PROMPT-*.md set (WAL markers, claim protocol, budget tiers, verification gate) is never synced to clients — they get the thinner templates/PROMPT.md. Same fork in meta/: live and template META/BRAIN prompts have each gained improvements the other lacks, push to branches that don't exist (V2/master), and mix path schemes. CLAUDE.md and README document the legacy system with wrong counts.

*Affected:* PROMPT-*.md vs templates/PROMPT.md, meta/ vs templates/meta/, CLAUDE.md, README.md, engine/session_helpers.py

### Phantom assets and dead references break skills as written
Multiple skills depend on files that don't exist: init/bundle-artifact.sh, scripts/office/*, scripts/thumbnail.py, canvas-fonts/, skills/themes/, research.md's autoagent/-prefixed memory paths, audit.md's three ghost reviewers, two orphaned templates/skills files, and four zero-caller engine modules. The executor hits file-not-found or silently skips mandatory steps (validation, memory-first, the Playwright gate).

*Affected:* skills/web-artifacts.md, skills/docx.md, skills/pptx.md, skills/canvas-design.md, skills/theme-factory.md, skills/research.md, skills/audit.md, templates/skills/, engine dead modules

### Internal contradictions in core conventions
Three incompatible commit/TDD conventions (git.md vs quality-standards.md vs testing.md); the TDD two-commit red proof directly contradicts 'never commit red tests' with no carve-out; orphan-adoption commit order contradicts the mandatory verification order; design skills contradict each other on model layout, CDN use, and brand defaults; Cerebro sender rule contradicts itself across two files.

*Affected:* skills/git.md, skills/quality-standards.md, skills/testing.md, PROMPT-WORK.md, PROMPT-VERIFICATION.md, PROMPT-RECOVERY.md, skills/design layer

### Single-operator assumptions vs multi-tenant cloud SaaS
'Seb action' markers and 'Hey Seb' greetings in prompts; the 9-file director cockpit hardwired to Seb's project portfolio and Telegram; council budgets global per-provider with no tenant key (and fail-open); model_fallback spend invisible to all budget gates; Windows batch and macOS 'open' commands in skills a Linux headless runner executes; an uncapped autonomous research loop on vendor-paid compute; RedHunter modules and dev credentials as engine defaults.

*Affected:* engine/director_*, engine/council_usage.py, engine/model_fallback.py, engine/council/memory.py, skills/playwright.md, skills/autoresearch.md, PROMPT-WORK.md

### The G4 zero-jargon North Star is unenforced anywhere in the loop
Client-visible surfaces carry internal vocabulary: 'Audit (Marcus)' in the mandatory verification report, meta:/PARTIAL/ghost-recovery language in client git history, council references in design skill instructions. And nothing in MISSION.md's quality score, META's rule gate, or BRAIN's evaluation gate measures client-facing clarity — the self-improvement loop optimizes internal metrics while blind to the one gate that defines the product.

*Affected:* PROMPT-VERIFICATION.md, PROMPT-FAILURE.md, skills/git.md, meta/MISSION.md, meta/PROMPT.md, templates/meta/, engine/orchestrator.py

## P0 — Launch blockers

### [P0-1] Close the three runtime bypasses of the project-domain skill gate  · _small_
**Files:** engine/session_helpers.py, engine/run.py, engine/registry.py, engine/org_model.py, run.py, engine/test_registry.py

**Action:** Make _sync_templates scope-aware (skip stems in project_domain_skill_names unless the project enables them) and purge already-leaked copies from existing project homes; change registry.all_skills() to fail CLOSED (exclude the project_domain set) instead of globbing everything on exception; route the legacy root run.py skill glob through visible_skill_paths() or retire it; add an integration test that runs _sync_templates on a fake project and asserts no manifest-scoped skill lands in project_home/skills/ (fails today).

**Why:** Three reviewers independently confirmed that after one session, every client project holds the full CultivOS pack locally and permanently visible — the flagship multi-tenant guardrail is currently fiction in production while CI stays green. Highest-leverage fix in the repo: roughly ten lines closes the biggest leak.

### [P0-2] Stop shipping the cultivOS-saturated INDEX.md into every session's system prompt  · _medium_
**Files:** skills/INDEX.md, engine/run.py, run.py

**Action:** Generate the injected routing index from visible_skill_paths() output (or split INDEX into a shared index plus a project-domain index injected only when the scope is enabled); move the CultivOS/Jaqemate/Cerebro rows and the entire 'Common task workflows (cultivOS)' section (lines 61-91) into the cultivOS project-local index; genericize remaining rows to describe capabilities, not past clients; fix the stale 'Claude Opus 4.7 vision' row, the '8-person' audit count, and the dead elite-product-council distillation row while in there.

**Why:** run.py appends INDEX.md verbatim to every tenant's system prompt, so even perfectly-hidden skills leak their client names, brand routing, and another company's codebase workflows into every session — the gate is porous at the injection path regardless of file visibility.

### [P0-3] Quarantine the five unscoped client dossier/brand skills and the research.md moat block  · _medium_
**Files:** skills/project_context.md, skills/design.md, skills/brand-guidelines.md, skills/claim-source-discipline.md, skills/bilingual-parallel-positioning.md, skills/research.md, templates/departments.json

**Action:** Move project_context.md (founder names, funding deadlines, un-contacted partners, legal address) out of the shared library into the cultivOS project-local skills overlay and remove it from the research-intelligence department list; split design.md and brand-guidelines.md into a generic 'read the project's design-system manifest' skill plus a scoped StockCards pack; split the two CultivOS copy skills into generic doctrine (source-or-cut, parallel-positioning) plus project-local content; delete research.md's Trade Ideas/TFSA 'our moat' competitive block outright.

**Why:** These files are visible to every tenant TODAY even with a perfect gate: a generic client inherits a trading app's dark theme as law, a rival product's competitive moat in research output, another founder's grant strategy, and a past client's founders and pilots in its working context.

### [P0-4] Strip cultivOS/StockCards hard-wiring from the 'Universal' engineering and design skill set  · _medium_
**Files:** skills/coding.md, skills/testing.md, skills/git.md, skills/debugging.md, skills/performance.md, skills/security.md, skills/playwright.md, skills/mcp-builder.md, skills/clean-architecture.md

**Action:** Split each into its generic core (evidence-first, patch-at-lookup-namespace, fail-before verification, compound stage+commit — all excellent) and move project flesh behind the project-domain gate; replace absolute /Users/SebSan paths, the `from cultivos.app import create_app` gate, branch-V2 pushes, src.stockcards imports, and StockCards selectors with placeholders resolved from PROJECT.md; delete coding.md's vanilla-JS/Spanish-first frontend lock and point INDEX's frontend row at ui-stack.md; retitle clean-architecture.md and neutralize its project names. Verify with a grep of the Universal set for cultivos|stockcards|polyedge|SebSan.

**Why:** An executor on a fresh client repo is literally instructed to cd into Seb's laptop, run another client's import checks, push to a nonexistent branch, refuse frameworks, and write Spanish UI — the single most likely source of a visibly wrong first client deliverable.

### [P0-5] Rewrite the two universal growth agent templates; delete their orphaned duplicates  · _medium_
**Files:** templates/agents/marketing-growth.md, templates/agents/pr-strategist.md, templates/skills/marketing-copywriting.md, templates/skills/pr-communications.md, templates/departments.json

**Action:** Convert both templates to the standard per-project {{project_name}} framing; replace the Voice-by-Project tables (StockCards/cultivOS/KitchenIntelligence) with a protocol step 'read the project's voice guide / NORTH_STAR.md and derive tone from it'; drop 'Seb's voice', the FODECIJAL/CONACYT/SAGARPA grant protocols, and the 'AutoAgent Agency' identity; add one owned-vs-earned channel routing line to disambiguate the two roles; delete (or genericize and actually wire) the two orphaned templates/skills files carrying the worst examples ('68% win rate on PLAY signals', StockCards email subjects). Keep the anti-fabrication rules.

**Why:** These two escaped the project_domain quarantine and are copied into EVERY client project by intake — a new client's marketing agent adopts a past client's brand voice, cites fabricated metrics from another product, pitches Mexican government grants, and attributes quotes to Seb.

### [P0-6] Consolidate to one canonical, genericized executor prompt stack  · _large_
**Files:** templates/PROMPT.md, PROMPT.md, PROMPT-WORK.md, PROMPT-RECOVERY.md, PROMPT-CONTEXT.md, PROMPT-FAILURE.md, PROMPT-VERIFICATION.md, engine/session_helpers.py, engine/registry.py

**Action:** Port the hardened root PROMPT-*.md content (WAL markers, TOCTOU-safe claim protocol, budget-tier failure ladder, full verification gate, plus templates' PINNED protocol) into templates/ as the concern-split set; while porting, strip the client hard-wiring: src/cultivos/* grep gates, the cultivos openapi_tags rule, StockCards log-format examples, and the 'branch is V2' commit reminder; extend _sync_templates to copy the full set; delete or clearly mark the root copies as legacy.

**Why:** Paying clients currently receive the thin unhardened monolith while months of META-validated hardening sits in root files the product path never loads — and the hardened stack can't ship as-is because its MANDATORY rules grep another client's directories. Both halves are launch-broken until merged.

### [P0-7] Create a model-id single source of truth and purge two-generations-stale defaults  · _medium_
**Files:** skills/claude_api.md, engine/intake.py, config.json, config.example.json, run.py, engine/advisor.py, engine/judge.py, engine/registry.py, engine/init_agency.py, engine/digest.py, engine/model_fallback.py, engine/council_usage.py, skills/replicate.md, skills/INDEX.md

**Action:** Add one engine/models.py (or config-level) registry of current ids — claude-fable-5, claude-opus-4-8, claude-sonnet-5, claude-haiku-4-5-20251001 — and import it everywhere; refresh claude_api.md's model table and every code example, re-verifying the thinking/prefill caveats and deleting the expired Haiku-3 note; fix intake.py's project.json default (claude-opus-4-6) and its 999-USD daily limit; replace 'Opus 4.7 vision' prose in INDEX/replicate; prefer CLI aliases ('opus', 'sonnet') where supported so ids can't rot again; resolve the Opus 4.8 pricing TODO.

**Why:** claude_api.md is the skill that tells the agent which ids to bake into client code, and intake writes a two-generations-stale id into every new project's config — clients would ship apps pinned to superseded, soon-retired models, with four internal registries disagreeing about what's current.

### [P0-8] Tenant-key the council budget and route the fallback path through spend gates  · _medium_
**Files:** engine/council_usage.py, engine/council/backends.py, engine/model_fallback.py, engine/run.py

**Action:** Add a tenant/project dimension to the usage schema and check_provider_budget(provider, tenant), with per-tenant entries in spending_config.json; thread ctx.name through convene_council → backends → _record_usage; make model_fallback's callers use the same budget-gate and usage-record helpers backends.py uses (its spend is currently invisible and fires precisely under rate-limit stress); fix its drifted docstrings.

**Why:** One global per-provider bucket plus a fail-open gate means a single heavy tenant can exhaust or un-cap council spend for every other client on day one of paid multi-tenancy — a cost incident and fairness break, and the only budget surface that isn't already per-project.


## P0+ — Additional blockers/high found by critic fact-check (missed by reviewers)

### [BLOCKER] Live leaked credentials printed verbatim in a tracked doc; no rotation/purge item anywhere in the plan
**Files:** docs/AUDIT_2026-04-16.md

**Evidence:** docs/AUDIT_2026-04-16.md:276-277 (git-tracked, confirmed via `git ls-files`) prints both secrets in full: 'ghp_***REDACTED*** (GitHub PAT, in autoagent/launcher.py history)' and '***REDACTED-TELEGRAM-TOKEN*** (Telegram bot token)'. Line 283: 'Status today: still unrotated, 13 days later' and 'remain in git history on master'. The synthesis plan contains zero mention of secret rotation, history purge (BFG), or removing these values from the audit doc — 10 reviewers and the synthesis all missed it.

### [HIGH] Council memory recall is cross-tenant: project column stored but never filtered on read
**Files:** engine/council/memory.py

**Evidence:** engine/council/memory.py stores `project` on insert (lines 180, 199) but recall_similar (line 239) and recall_analogical (line 330) query with only 'WHERE question_hash <> %s AND question_embedding IS NOT NULL ORDER BY question_embedding <=> ...' — no project/tenant predicate. One client's council questions, winners, and synthesis text are recalled verbatim into another client's council session. The plan's P0 #8 covers budget keying and P2 mentions convene_council's free-text project parsing, but nobody owns the unscoped recall query itself.

### [HIGH] No skill-update propagation to existing tenants — the P0 de-leakage fixes will never reach already-provisioned projects
**Files:** engine/session_helpers.py, engine/org_model.py

**Evidence:** engine/session_helpers.py:319-322: `for f in shared_skills.glob("*.md"): dst = project_skills / f.name; if not dst.exists(): _sh.copy2(f, dst)` — copies only when absent, never refreshes. Combined with org_model.py:171-173 (project-local skills always visible, always override shared), every existing project keeps frozen contaminated copies of all 45 skills forever. The plan's one-time 'purge already-leaked copies' does not create a distribution/versioning mechanism, so future shared-skill fixes also never ship to live tenants — a structural multi-tenant operations gap no reviewer owned.

### [MEDIUM] System-prompt assembly bug: agent-patterns.md is never injected and INDEX.md is injected twice after first sync
**Files:** engine/run.py, engine/registry.py

**Evidence:** engine/run.py:331-338: `for skills_dir in ctx.skills_dirs(): for name in ("INDEX.md", "agent-patterns.md"): ... stable_parts.append(...); break` — the break sits inside the inner loop after the first successful append, so whenever INDEX.md exists (always, in shared skills/), agent-patterns.md is skipped; and because skills_dirs() returns shared then project (registry.py:75-81) and _sync_templates copies INDEX.md into project skills, the outer loop appends INDEX.md a second time. Net: the failure-mode catalog the docs call mandatory every session is absent from the cached system prompt while the cultivOS-saturated INDEX is doubled.

### [LOW] Runtime state tracked in git despite .gitignore (ignore added after tracking)
**Files:** sessions.json, self_heal_log.md, memory/backlog.md, .gitignore

**Evidence:** `git ls-files` shows sessions.json and self_heal_log.md tracked even though .gitignore lists sessions.json; 57 tracked files under memory/ + brain/ including memory/backlog.md (which the audit doc says holds the open CRITICAL security items), memory/activity_log.md, memory/active_claims.md, and brain/notifications/2026-04-*.json runtime logs. Plan's P2 'committed runtime debris' item lists only brain/ paths — the root-level tracked runtime files and the gitignore-vs-tracked mismatch are unowned.

### [POLISH] INDEX drift is two skills, not one: project_context.md is also absent from INDEX.md
**Files:** skills/INDEX.md, skills/project_context.md, skills/autoresearch.md

**Evidence:** Diff of `ls skills/*.md` against backticked references in skills/INDEX.md: unlisted = autoresearch.md (plan caught it) AND project_context.md (plan did not — it quarantines the file in P0 #3 but never notes INDEX omits it, relevant because the INDEX-generated-from-visible_skill_paths fix in P0 #2 must account for currently-unindexed skills). skills/references/ directory also unmentioned in INDEX.


## P1 — High value

### [P1-1] Split audit.md into universal + CultivOS extension; fix the ghost-reviewer table  · _medium_
**Files:** skills/audit.md, skills/INDEX.md, templates/departments.json

**Action:** Keep the six genuinely universal reviewers (Alex, Sarah, Marcus, Ama minus API-name specifics, Leo, Nina minus farmer tooltips) as the shared skill; move Diego/Elena/Ana (agronomist, rural-UX, FODECIJAL grants) into a cultivOS project-local audit extension with a 'load project-local audit extensions' hook; rebuild the quick-reference table against the real roster (Priya, Jordan, Chen do not exist); fix the '8-person' count in INDEX.

**Why:** The orchestrator hard-injects audit.md at pre-commit — every generic client's quality gate currently flags missing Spanish empty states and grant-narrative alignment, and routes to reviewers that don't exist at the single highest-stakes moment in the pipeline.

### [P1-2] Kill the self-replicating leakage: fix skill-creator's template and sweep the 19 StockCards trailers  · _small_
**Files:** skills/skill-creator.md, skills/pdf.md, skills/docx.md, skills/pptx.md, skills/xlsx.md, skills/slack-gif.md, skills/internal-comms.md, skills/doc-coauthoring.md, skills/canvas-design.md, skills/theme-factory.md, skills/algorithmic-art.md, skills/web-artifacts.md

**Action:** Replace the mandated '## StockCards usage' section and checklist line in skill-creator.md with '## Project usage — ground in the CURRENT project (read PROJECT.md)'; then mechanically genericize the existing StockCards sections and examples across the library ('StockCards Signal Report' → 'Client Report', the false 'GET /api/export/signals already exists' claim, StockCards GIF ideas, 'Pro users' framing).

**Why:** The meta-skill guarantees every future skill created for any client embeds a past client's name — fixing the root cause plus one mechanical sweep permanently stops the dominant contamination pattern reviewers found across 19 files.

### [P1-3] Resolve the contradictory commit/TDD conventions across the prompt and skill layer  · _small_
**Files:** skills/git.md, skills/quality-standards.md, skills/testing.md, PROMPT-WORK.md, PROMPT-VERIFICATION.md, PROMPT-RECOVERY.md

**Action:** Pick two-commit TDD (test:/feat:) as the single convention stated once in git.md, with quality-standards.md and testing.md referencing it; add the explicit carve-out that 'never commit red tests' exempts a TDD Commit 1 of new intentionally-red tests resolved within the session; enumerate orphan adoption and EMERGENCY/PARTIAL tiers as the named exceptions to the mandatory tests→frontend→commit order, cross-referenced in both files; fix testing.md's 'alongside' phrasing.

**Why:** The executor currently holds three incompatible instructions for the same act and two pairs of MANDATORY rules in direct conflict — a proven driver of the ghost/hesitation failure modes these very prompts document, plus false META audit flags on compliant sessions.

### [P1-4] Fix the phantom assets that skills depend on  · _medium_
**Files:** skills/web-artifacts.md, skills/docx.md, skills/pptx.md, skills/canvas-design.md, skills/theme-factory.md, skills/research.md

**Action:** Vendor or inline the missing helpers: scripts/init-artifact.sh + bundle-artifact.sh (or replace with a Vite single-file recipe), scripts/office/* pack/unpack/validate and scripts/thumbnail.py (Anthropic's public skills include them), a real canvas-fonts/ directory or a rewritten font rule, and inline hex/font specs for the 10 named themes; correct research.md's four autoagent/-prefixed memory paths to the real memory/ and brain/ locations.

**Why:** Multiple skills fail at step 1 with file-not-found today: client Word/PowerPoint documents ship unvalidated, theme application is nondeterministic, and the check-memory-first discipline silently no-ops on every research task, defeating its token-saving purpose.

### [P1-5] Match execution-environment assumptions to the headless Linux cloud runner; cap the research loop  · _small_
**Files:** skills/playwright.md, skills/debugging.md, PROMPT-VERIFICATION.md, skills/autoresearch.md, skills/replicate.md, skills/docx.md, skills/pptx.md

**Action:** Convert Windows batch (`py -m`, `start /B`, `del`, netstat/taskkill) to POSIX or PROJECT.md-parameterized commands; delete the 'py on Windows' commit reminder; give autoresearch.md a default hard cap (~20 cycles) plus wall-clock/spend stops, make its dashboard write-only, and remove mid-run interactive gates; genericize replicate.md's Seb/Telegram/cultivOS wiring to roles and per-project channels; fix the npm -g/require() recipes and the missing PptxGenJS require line.

**Why:** As written, the Playwright frontend gate can never pass on the cloud runner and silently downgrades to 'skip' for every client — permanently disabling frontend verification — while an uncapped autonomous mutate-and-rerun loop on vendor-paid compute violates the repo's own hard-loop-cap law and is a cost incident by design.

### [P1-6] G4 jargon pass on agent-emitted client-visible strings; wire the North Star into the self-improve loop  · _small_
**Files:** PROMPT-VERIFICATION.md, PROMPT-FAILURE.md, skills/git.md, engine/orchestrator.py, engine/director_orchestrator.py, templates/PROMPT.md, PROMPT-WORK.md, skills/claude-design.md, skills/ui-stack.md, meta/MISSION.md, meta/PROMPT.md, templates/meta/BRAIN_PROMPT.md, skills/doc-coauthoring.md

**Action:** Rename 'Audit (Marcus)' → 'Audit'; find-replace 'Seb action' with a neutral needs-human marker in prompts and the _is_operator_only matcher; add a git.md rule that client-repo commits use the client's domain language only (session ids, ghost-recovery, TDD audit trails go to memory logs) and soften PARTIAL/EMERGENCY human text; strip 'Seb's taste', council references, and past-client war stories from design skill instructions (history moves to docs/); replace the retired 'str_replace' tool name; add a client-facing-clarity component to MISSION's quality score and a 'does this rule cause jargon to reach users?' check to META/BRAIN gates.

**Why:** Git history, verification reports, and status output are client-facing in a productized agency, and today they carry council personas, founder names, and internal vocabulary — while the self-improvement loop optimizes internal metrics with zero pressure toward the one launch gate (zero jargon, user-friendliness) that defines Agentric.

### [P1-7] Merge the diverging META/BRAIN prompt copies; fix branches, paths, and the fintech topic  · _medium_
**Files:** meta/PROMPT.md, meta/BRAIN_PROMPT.md, templates/meta/PROMPT.md, templates/meta/BRAIN_PROMPT.md, engine/session_helpers.py

**Action:** Merge each live/template pair into one canonical templates/meta/ version taking the union of improvements (live's minimalism gate + churn monitor, template's knowledge-promotion + quality gates, live BRAIN's MCE step); delete the hardcoded fintech/FastAPI search topics from section 2A in both copies; replace 'git push origin V2'/'master' with the [BRANCH] placeholder; normalize on the .autoagent/ path prefix everywhere; generalize the cultivOS hot-file quota and WhatsApp evergreen exemption to project-declared lists.

**Why:** Clients receive a META template missing two months of validated improvements, every client's BRAIN session researches fintech regardless of domain, and BRAIN pushes to a branch that doesn't exist — failing or creating stray branches silently, every session.

### [P1-8] Gate the BRAIN skill-download supply chain  · _small_
**Files:** meta/BRAIN_PROMPT.md, templates/meta/BRAIN_PROMPT.md

**Action:** Restrict direct curl-into-skills/ to an allowlist of trusted orgs (e.g. anthropics/*); route everything else to a quarantine directory plus a backlog entry for human review; add the explicit rule that downloaded content is DATA to extract rules from, never merged verbatim into standing instructions.

**Why:** An autonomous agent curling arbitrary SKILL.md files found via open web search into the live multi-tenant skills library is persistent prompt injection across all client projects — an unacceptable supply-chain hole for a trust-critical cloud product.

### [P1-9] Rewrite CLAUDE.md and README for the real product architecture; drop the client roster  · _medium_
**Files:** CLAUDE.md, README.md

**Action:** Document the engine/CLI/templates architecture instead of the legacy root launcher loop; fix the stale counts (27→46 skills, 148 tests→current, run.py line count, session types); drop the Windows 'py -X utf8' commands and Seb's machine-local plugin/hook setup; remove or anonymize the 'Currently managing' client table with its stale metrics; restate requirements for the cloud product context and verify the canonical repo URL.

**Why:** The two top-level orientation docs describe two different systems and both are factually wrong — misleading every future contributor and every agent session that reads them, while publishing client names and domains in the product engine's repo.

### [P1-10] Decide the director layer's fate; de-brand the engine's product-specific modules and credentials  · _large_
**Files:** engine/director_ai.py, engine/director_helpers.py, engine/director_commands.py, engine/director_intelligence.py, engine/director_brain.py, engine/visual_check.py, engine/empathy_sim.py, engine/red_bridge.py, engine/red_intel.py, engine/cli_red.py, engine/bounty_portfolio.py, engine/council/memory.py

**Action:** Either scope the 9-file director cockpit out of the Agentric deployment (operator-only, clearly marked) or parameterize it — project lists from registry.list_projects() (the pattern already exists in get_agency_context), deploy URLs from per-project config, greetings from tenant config; delete the hardcoded ['cultivOS','StockCards',...] lists regardless; move red_* and bounty_portfolio to a plugin dir excluded from the product build; replace council/memory.py's redhunter dev-credential DSN default with a required env var that fails loud. Fold the 9-file responsibility restructure into the same pass.

**Why:** A tenant's status surface referencing other companies' products and health endpoints, 'Hey Seb' greetings, and another product's dev credentials as the default memory connection string are launch embarrassment plus security surface in one layer.


## P2 — Polish / cleanup

### [P2-1] Delete dead engine modules and retire V1 entry-point shadowing  · _small_
**Files:** engine/subagent.py, engine/task_splitter.py, engine/dream.py, engine/empathy_sim.py, run.py, launcher.py, engine/runner.py

**Action:** Remove (or move to an explicit experimental/ area) the four zero-caller modules and their tests; after the P0 sync/INDEX fixes land, retire root run.py/launcher.py so engine/runner.py can drop its importlib spec_from_file_location workarounds and import normally.

**Why:** Dead modules inflate the audited surface and maintenance bill, and V1 shadowing forces the V2 engine to work around its own package layout — pure cruft under the senior-engineer bar.

### [P2-2] Standardize skill format, naming, and INDEX completeness; add in-file scope markers  · _small_
**Files:** skills/skill-creator.md, skills/claude_api.md, skills/autoresearch.md, skills/INDEX.md, templates/departments.json, skills/quant-strategy.md, skills/data-pipeline.md, skills/expansion.md, skills/field-intelligence.md

**Action:** Pick YAML frontmatter as the canonical skill format and update skill-creator's template/checklist; rename claude_api.md → claude-api.md (updating references); add an INDEX row for autoresearch.md (consider renaming it skill-optimizer.md to end the research.md collision) plus a note about references/; add 'scope: project-domain + owning project' frontmatter to gated skills with a lint in build_org_report that cross-checks against the manifest; first-line-mark the deceptively generic vertical files (data-pipeline, quant-strategy, expansion) so accidental reads self-identify as out of scope.

**Why:** Two competing file formats break description-based routing, the meta-skill teaches the oldest one, and scope protection that lives only in a remote manifest is silently stripped by any copy — defense in depth makes the P0 fixes durable.

### [P2-3] Repair agent-patterns numbering; dedup the duplicated normative blocks  · _small_
**Files:** skills/agent-patterns.md, skills/testing.md, skills/debugging.md, skills/INDEX.md

**Action:** Renumber the failure-mode catalog sequentially (two #8s, two #9s, two #13s, #11 after #14), move all failure modes under one section, and fix the ambiguous INDEX 'FM-8' reference; keep the VERIFICATION CONTRACT in agent-patterns.md and the self-critique checklist in debugging.md only, replacing duplicates with one-line cross-references. Content stays verbatim — it is the library's crown jewel.

**Why:** A file the executor reads every session has broken cross-references and independently drifting duplicate blocks — cheap structural repair that protects differentiated IP.

### [P2-4] Refresh or retire the stale governance docs and committed runtime debris  · _medium_
**Files:** meta/MISSION.md, docs/BIAS_MITIGATION.md, brain/sources.md, brain/techniques.md, brain/notifications/, brain/replicate/

**Action:** Rewrite MISSION.md against the actual engine/ layout (or fold its North Star into meta/PROMPT.md and delete it), resolving the 'can META touch code?' contradiction; mark each BIAS_MITIGATION countermeasure IMPLEMENTED/PARTIAL/NOT STARTED against the real codebase, fix the dead engine/council.py references and broken [BIAS] backlog pointer, re-date it; move brain/ runtime logs (cultivOS research corpus, notifications, scraped snapshots) to gitignored/archive locations and ship empty seed templates preserving the good log schema.

**Why:** A verifiably unexecuted bias-mitigation plan and a mission doc granting permissions against directories that don't exist read badly at any due-diligence pass of a product whose pitch is trustworthy autonomous agents.

### [P2-5] Bring the weak/old agent templates to the house protocol format; fill the customer-success gap  · _medium_
**Files:** templates/agents/architect.md, templates/agents/educator.md, templates/agents/frontend.md, templates/agents/infra.md, templates/agents/test-writer.md, templates/agents/ux-researcher.md, templates/departments.json

**Action:** Migrate the six Apr-10 templates to the Responsibilities + Protocols(Trigger) + [agent: X] format; make test-writer and architect stack-conditional ('in pytest this means X / in Vitest Y') instead of Python/FastAPI-only; replace frontend.md's field-app assumptions (mobile-first, offline, fixed four-view model) with 'derive from PROJECT.md/NORTH_STAR.md'; replace infra's arbitrary 500ms constraint with per-project targets; promote customer-success from candidate to a real template (or explicitly assign onboarding/help/feedback duties to technical-writer + educator).

**Why:** Template quality equals client output quality across every project — half the roster gives the executor markedly weaker or stack-mismatched instructions than its May-12 peers, degrading exactly the non-Python clients Agentric wants to win, and a user-friendliness-first product ships with nobody owning onboarding.

### [P2-6] Small correctness/consistency sweep across skills  · _small_
**Files:** skills/claim-source-discipline.md, skills/cultivos-voice-guide.md, skills/project_context.md, skills/field-intelligence.md, skills/expansion.md, skills/xlsx.md, skills/algorithmic-art.md, skills/ui-stack.md, skills/clean-architecture.md, skills/coding.md

**Action:** Align the Deveron exit date to the voice-guide canon; fix project_context.md line 27 so WhatsApp messages are 'from cultivOS', not the internal Cerebro codename; remove the expired April/May 2026 grant deadlines in favor of a live-tracker pointer; add color="FFFFFF" to xlsx.md's header font; resolve algorithmic-art's CDN self-contradiction and bump p5.js; move ui-stack to the 'motion' package and verify the runner image actually bakes in the design plugins; reconcile the single-models.py vs models-dir contradiction when coding.md is genericized.

**Why:** Individually trivial, but each is a wrong instruction an autonomous executor follows verbatim into a client deliverable — illegible spreadsheet headers, internal codenames signed to end-user messages, planning against dead deadlines.

### [P2-7] Align engine behavior with PRINCIPLES' fail-fast rule; fix the pollution root cause  · _medium_
**Files:** engine/session_helpers.py, engine/self_improve_analyzers.py, meta/PROMPT.md, engine/council/executive.py

**Action:** Log loudly and mark the session degraded when a session-type prompt file is missing instead of silently returning empty (a META session with no instructions currently counts as a session); replace bare except-pass blocks with logged exceptions; fix the analyzer's cross-project knowledge injection so META's manual scrub (STEP 1.5, '8+ cleanups recurring') can be deleted; give convene_council an explicit project parameter instead of parsing the first line of free-text context.

**Why:** The governance doc's most-emphasized rule (never swallow errors) is violated by the code that governs it, and paying LLM sessions for months to clean up after a known bug inverts the repo's own no-symptom-suppression law — plus the injection path is itself a cross-tenant leakage vector.


## Quick wins (trivial/small, outsized payoff)

1. Add the scope filter to _sync_templates in engine/session_helpers.py (one import + one condition) — closes the single biggest multi-tenant leak in the repo for ~10 lines.
2. Make engine/registry.py all_skills() fail closed instead of globbing every skill on exception.
3. Delete the COMPETITIVE RESEARCH block from skills/research.md — removes a rival product's moat statement from every client's research context.
4. Fix engine/intake.py defaults: model claude-opus-4-6 → claude-sonnet-5 and daily_limit_usd 999 → a sane cap.
5. Replace skill-creator.md's mandated 'StockCards usage' section with 'Project usage (read PROJECT.md)' — stops leakage from self-replicating into every future skill.
6. Find-replace 'Seb action' → 'needs-human' across PROMPT-WORK.md, templates/PROMPT.md, engine/orchestrator.py, engine/director_orchestrator.py.
7. Fix 'Claude Opus 4.7 vision' in skills/INDEX.md and skills/replicate.md to the current Opus alias.
8. Rename 'Audit (Marcus)' to 'Audit' in PROMPT-VERIFICATION.md's mandatory report block.
9. Delete the '## StockCards usage' trailers from skills/internal-comms.md and skills/doc-coauthoring.md.
10. Remove 'project_context' from the research-intelligence department skill list in templates/departments.json.
11. Delete coding.md's vanilla-JS/Spanish-first frontend section and repoint INDEX's frontend row at ui-stack.md.
12. Add color="FFFFFF" to the header Font in skills/xlsx.md's example so client spreadsheets don't ship black-on-black headers.
13. Cap skills/autoresearch.md's default loop at ~20 cycles instead of 'no cap, never stop'.
14. Delete the 'py on Windows' and 'branch is V2' lines from PROMPT-VERIFICATION.md's COMMIT REMINDERS.

## Critic verdict

The synthesis plan is accurate where it looked: every one of the eight P0 blockers spot-checked against the code is real, correctly scoped, and correctly prioritized (one minor factual slip — integration tests do call _sync_templates, they just assert nothing about scoping), and its not-ready verdict is right. But the plan is incomplete on the security/ops axis in ways that matter for a trust-critical cloud launch: a live GitHub PAT and Telegram bot token are printed verbatim in a tracked doc and documented as unrotated and still in git history with no rotation/purge item anywhere in the plan (blocker); council pgvector memory recalls other tenants' decisions because the stored project column is never filtered on read (high); and the sync mechanism has no update propagation, meaning the entire P0 de-leakage sprint fixes only future projects while existing tenants keep frozen contaminated skill copies forever (high) — plus a system-prompt assembly bug that silently drops agent-patterns.md and doubles the leaked INDEX. Add those four items (credential rotation + history purge, project-scoped recall, a skill-refresh/versioning mechanism folded into P0 #1, and the run.py injection-loop fix folded into P0 #2) and the plan is a complete, launch-blocking-first roadmap; the 1–2 week strip-and-scope estimate remains plausible since all additions are small, localized changes.

## Strengths to PRESERVE (do not let the polish pass break these)

- agent-patterns.md is the crown jewel: a 15-mode failure catalog with citations, concrete detection commands, and calibrated fixes (context-collapse thresholds, observation masking, over-specified-planning limits). Fix its numbering and project-path examples, but preserve the content verbatim — this is differentiated IP.
- testing.md's mechanics are genuinely senior-grade and generic underneath the cultivOS skin: patch-at-the-lookup-namespace rule with the intra-function-import trap, fail-before verification, behavioral-assertion guidance, word-boundary term matching, and per-session basetemp isolation for concurrent runs.
- debugging.md's 5-step process (read literally → reproduce → isolate → root cause → verify + prevent) and its 'never comment out a failing test / never catch broadly without logging' rules are exactly the right discipline and fully portable.
- quality-standards.md's two-commit TDD audit trail ('one commit makes TDD unfalsifiable') and the frontend-test rule 'never grep JS source for keywords — test the API or rendered output' are sharp, enforceable standards worth making the single canonical convention.
- clean-architecture.md's 10 patterns (health+readiness probes, rate-limit auth, centralized Settings, tier-limits dict, dict-wrapped API responses, cascade deletes) are solid generic FastAPI standards — only the framing needs de-branding.
- git.md's compound stage+commit race-window analysis and the expanded commit-message-as-persistent-context rationale are thoughtful, agent-specific insights; keep the structure, strip the project paths and lore.
- playwright.md's reconnaissance-then-action debug order (screenshot → DOM → selectors → act, wait for networkidle) and skip-never-blocks-commit semantics are the right shape for an automated frontend gate once the commands and selectors are parameterized.
- INDEX.md's three-tier scope taxonomy (Universal / Department / Project-domain) is the correct guardrail design — the problem is only that the Universal tier's contents don't yet honor the label.
- The project-domain hiding guardrail is REAL, not a comment: engine/org_model.py:124-167 hides manifest-scoped skills by default, templates/departments.json carries the skill_scopes list, and engine/test_registry.py:290-310 tests both hiding and project-local visibility. Preserve this mechanism; the fix for leakage is adding files to the list, not rebuilding the gate.
- The 'agency leads design, Claude Design supports' stance is coherent and consistent across claude-design.md, ui-stack.md, and INDEX.md rows 30-31 — dated decision, one-way B-to-A handoff, explicit anti-pattern list. Do not let synthesis re-litigate it.
- The unison principle in claude-design.md (shared workflow + extractor + manifest convention, per-brand tokens never flattened) is exactly the right multi-tenant architecture for Agentric — keep it as the backbone of a rewritten brand-guidelines.md.
- scripts/extract_design_system.py exists and is referenced consistently; the drift-signal-as-build-gate idea (re-extract and diff after building) is a strong self-check pattern worth keeping verbatim.
- Anti-AI-slop guidance (no Inter/purple gradients/centered layouts/cookie-cutter empty states) is consistent across design.md, ui-stack.md, and web-artifacts.md — high-value, client-agnostic content worth extracting into the generic design skill.
- Two-phase philosophy-then-execute workflow in canvas-design.md and algorithmic-art.md (write the aesthetic manifesto before code, refine-don't-add final pass) is a genuine quality lever independent of any project.
- The project-domain guardrail is real, not just a comment: engine/org_model.py visible_skill_paths() hides manifest-scoped skills by default with an explicit opt-in (include_project_domain_skills / allowlist), and registry.all_skills() routes through it. Preserve this mechanism.
- The project-local skills overlay (engine/registry.py skills_dirs(): shared first, project_home/skills overrides by name) already exists and is the architecturally correct home for client-specific voice guides — no new mechanism needed to fix the leakage findings.
- claim-source-discipline's core doctrine is best-in-class and generic: source-or-cut rule, 5-tier source hierarchy, date-stamping of volatile figures, estimation framing ('framed as estimation, not assertion'), and separate drafting vs reviewing workflows. This is exactly the discipline a multi-client copy agency needs.
- copy-tone-calibrator's method is excellent even though its content is project-specific: pick-exactly-one-register, the audience/channel/relationship decision flow, named failure-mode smells with fixes, and the 'recommend a register, then draft — don't make the user pick blind' interaction pattern.
- bilingual-parallel-positioning's 'parallel positioning, not translation' doctrine (diverge body content by market, keep thesis/voice parallel; rewrite institutional Spanish from scratch) is a genuinely differentiated multi-market capability worth productizing in generic form.
- cultivos-voice-guide is an exemplary per-client voice guide — canon phrasings, approved-terms table, do/don't list, dated factual canon with a re-verify horizon, and an external-copy review checklist. It should become the TEMPLATE every Agentric client gets a filled-in copy of, just relocated to project-local skills.
- internal-comms and doc-coauthoring are compact, immediately usable generic templates (3P/incident formats; 3-stage co-authoring with hardest-section-first and fresh-reader testing).
- The gating mechanism itself is well-designed: manifest-driven skill_scopes in templates/departments.json, a single filtering function (engine/org_model.py:visible_skill_paths), an org report that surfaces hidden skills as notes, and per-project allowlist/enable flags (include_project_domain_skills, project_domain_skills). Keep this architecture — fix the bypasses, don't rebuild.
- The CultivOS skill content is genuinely high quality and should be preserved as a project-local skill pack, not deleted: crop-analysis.md's graceful-degradation scoring rules, data-pipeline.md's never-lose-raw-data error recovery, drone-ops.md's go/no-go protocol.
- skills/field-intelligence.md is a model of Agentric's own North Star: the Don Manuel test, the 'Technical -> Farmer Spanish' jargon translation table, and voice/low-end-Android constraints are exactly the zero-jargon, user-friendliness discipline G4 demands. Worth generalizing into a template for future vertical packs.
- Consistent file structure across all vertical skills ('When to read', 'Owns', 'Protocols', 'Downstream') makes them trivially portable to a per-project directory.
- org_model.build_org_report emits 'Project-domain shared skill hidden by default' notes — good operational visibility that the scope list exists and is auditable via CLI.
- docx.md's critical-rules block is accurate, hard-won docx-js knowledge (A4-default trap, DXA-only widths, dual table widths, ShadingType.CLEAR, PageBreak-inside-Paragraph, no unicode bullets) — this is exactly the class of gotcha that makes agent-generated Word docs actually open correctly; preserve verbatim.
- pdf.md's tool-per-task table (pdfplumber extract / pypdf merge-split / reportlab create / qpdf CLI / pytesseract OCR) is correct and concise, and the ReportLab unicode sub/superscript warning is a real production failure mode worth keeping.
- xlsx.md's 'Excel formulas, not hardcoded Python values' rule and the industry-standard financial color-coding (blue inputs / black formulas / green links) plus zero-formula-errors gate are precisely the right quality bar for client deliverables.
- autoresearch.md's methodology is disciplined and worth preserving intact: binary evals only, baseline before any change, one mutation per experiment, keep/discard with revert, never modify the original SKILL.md, and the changelog-as-research-log artifact.
- replicate.md's product-safety properties — mandatory human approval before build, spec-only Phase 2 (no production code), 2-viewport capture cap, and the attribution rule that replicas must credit the source and never ship as original work — are genuinely good guardrails; generalize them, don't remove them.
- research.md's memory-first order of operations (knowledge file → sources log → codebase → web last, with mandatory save-back) is a strong token-discipline and no-re-read pattern once the paths are fixed.
- The project-domain scoping mechanism is real, not just a comment: engine/org_model.py (project_domain_skill_names, visible_skill_paths) reads templates/departments.json, whose 9-skill project_domain list matches skills/INDEX.md line 9 exactly, and it has dedicated tests (engine/test_registry.py::test_project_domain_shared_skill_hidden_by_default). The design is correct; only one code path bypasses it.
- skills/elite-product-council.md is fully generic, zero project leakage, zero jargon, and encodes a genuinely high product bar (debate protocol, polish checklist, anti-patterns). It is the model every universal skill should follow — do not 'fix' it.
- skills/references/eval-guide.md is excellent: generic, binary-eval discipline with concrete good/bad examples and a 3-question test. skills/autoresearch.md correctly links to it, forming a coherent self-improvement pair.
- INDEX.md's routing-table format (task type -> skill file -> workflow provided) is a strong, scannable pattern worth preserving through any content rewrite.
- audit.md's structural mechanism is sound: persona checklists, a hard-blocking security reviewer (Marcus), and deferred-debt logging to tech_debt.md. The structure should survive the de-CultivOS-ing of its content.
- skill-creator.md's core discipline (specific when-to-use trigger, at least one CRITICAL/NEVER rule, under-100-lines cap, INDEX registration step) is the right quality bar for a meta-skill.
- The May-12 template cohort (product-strategist, reliability-engineer, researcher, security-auditor, technical-writer, engineering-cleanup) shares a clean, consistent format — Responsibilities + trigger-based Protocols + the [agent: X] backlog-handoff convention. This is the house style to extend, not replace.
- The scope guardrail is real code, not a comment: departments.json is the source of truth and engine/org_model.py universal_agent_template_paths() filters by scope=universal + template=true before intake.py copies anything into a client project. The domain-ops department and skill_scopes.project_domain quarantine (cultivos-voice-guide, crop-analysis, quant-strategy, etc.) correctly keep those skills out of generic projects.
- test-writer.md's test-isolation section (monkeypatch over globals, tmp_path over mkdtemp, autouse conftest fixtures) is hard-won, concrete, and prevents real autonomous-agent flakiness — preserve the substance even if the pytest specifics get made stack-conditional.
- engineering-cleanup.md's safety rules are exactly right for an autonomous fleet: never delete source-like files without human approval, duplicates and package conflicts are review-only, worktree cleanup must preserve unmerged work.
- ux-researcher.md ('No jargon — translate technical terms into user-friendly language', 'can the least technical target user complete the core action without help?') directly reinforces the G4 zero-jargon gate — this template is an asset for the launch lens.
- Anti-fabrication and anti-buzzword rules in marketing-growth ('Reference real metrics from the platform — never invent numbers') and pr-strategist ('Never fabricate quotes, metrics, or partnerships') are the right instincts; keep them in any rewrite.
- The orchestrator is generated per-project from the actual agent roster (intake._generate_orchestrator) rather than shipped as a stale template, and Finder-duplicate ('name 2.md') filtering makes template scanning robust on macOS.
- Plain-English logging mandate in PROMPT-VERIFICATION.md (sessions.json summary must be 'plain English... NOT technical jargon, write it like you're telling a non-developer') — this is exactly the G4 zero-jargon gate, already enforced at the prompt level; preserve verbatim.
- Concern-split prompt architecture (PROMPT.md as routing index + 5 focused files, 'read only the file for your concern') — excellent context economy; the split itself should survive consolidation.
- Evidence-backed rule culture: nearly every rule cites a concrete session incident or paper (e.g. WAL marker from 6+ ghost-commit incidents, compound pre-claim scan closing a real TOCTOU race). The RULE ADMISSION gate and memory-pruning protocol in PROMPT-CONTEXT.md prevent knowledge bloat — rare discipline, keep it.
- Budget-tier failure ladder (PROMPT-FAILURE.md): retry caps scaled to remaining budget, PARTIAL/EMERGENCY commit tiers, doom-loop caps — coherent, internally consistent, and directly implements the 'hard loop caps' engineering law.
- Verification gate with explicit machine-checkable VERIFICATION REPORT block and READY TO COMMIT YES/NO — structural verification over vibes.
- Concurrent-session claim protocol in PROMPT-RECOVERY.md (optimistic write-verify, session-number collision handling, future-timestamp ban) — production-grade multi-writer safety that most agent frameworks lack.
- Evidence-gated self-improvement discipline in meta/PROMPT.md: the minimalism gate ('would a session DEFINITELY fail without this rule?'), quantitative signal extraction, and code-churn monitor are research-cited, concrete, and genuinely prevent prompt bloat — preserve these when merging copies.
- templates/meta/PROMPT.md's knowledge promotion lifecycle (STEP 2.5) and INSTRUCTION FILE QUALITY GATE are excellent additions the live copy lacks — the merge should take the union.
- brain/sources.md and techniques.md logging format (URL — verdict — where implemented — expected impact) is a real audit trail that prevents re-reading and re-implementing; keep the schema as the shipped template even after purging cultivOS content.
- BRAIN_PROMPT's 4-question implementation gate and concrete success criteria ('added rule X to skills/coding.md line 47, not improved general quality') set a high bar for actionability.
- docs/PRINCIPLES.md is timeless, model-agnostic (zero stale model IDs), and well-written — needs no content changes, only code alignment.
- docs/BIAS_MITIGATION.md's bias taxonomy (self-serving META loop, backend cheerleading, confirmation bias, TDD test-bias) with measurable success metrics is unusually honest and valuable IP for a trust-critical product — refresh it, don't delete it.
- No stale Claude model references (Opus 4.7 / Sonnet 4.7 / old IDs) anywhere in the seven reviewed files, and no G4 banned-jargon strings in user-facing positions — these docs are internal-facing.
- run.py session hardening is senior-grade: BYOK-aware child env (engine/run.py _build_child_env strips a dead shell ANTHROPIC_API_KEY), SIGINT checkpoint salvage to knowledge.md, instruction-file integrity locks, pre-push test gate, constraint gate, stuck-loop detection, and prompt-cache-friendly stable system prompt assembly.
- runner.py has real burn guards: MAX_CONTINUOUS_ITERATIONS, per-project session_cap (3x tasks_limit), weekly_session_budget to protect the tenant's Max quota, branch guard before running, and a non-TTY default that prevents the historical stdin hang.
- The project-domain skill scoping mechanism in engine/org_model.py (visible_skill_paths + departments.json skill_scopes) is a real guardrail, not a comment — it is wired through registry.all_skills() into every boot prompt, and build_org_report surfaces hidden skills for audit.
- judge.py is exemplary: tri-state test signal (pass/fail/none) so non-code sessions aren't falsely rejected, fail-loud reasons persisted to judge_verdicts.jsonl, and a documented SDK-fast/CLI-free fallback split.
- council/ package is cleanly factored (backends / executive 3-stage / personas / memory / reviews), with anonymized peer ranking, opt-in pgvector memory that can never break a convene, and a deliberately documented fail-open budget gate.
- registry.py ProjectContext is a clean no-globals design; register() refuses to silently repoint a name to a different repo, preventing cross-project memory/budget bleed.
- agent_router.py success-rate routing has sane thresholds (min 5 sessions before any swap decision) — evidence-based routing without premature judgment.