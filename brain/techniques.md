# Brain Techniques — Implemented Improvements

Track what was implemented and where, so it's never re-done.

---

## Skill file decontamination — implemented 2026-03-26
What: Replaced all stockcards/fintech references in coding.md, testing.md, agent-patterns.md, audit.md with cultivOS-specific patterns
Where: autoagent/skills/coding.md, testing.md, agent-patterns.md, audit.md
Source: Internal audit — found stale project references from previous project
Expected impact: Agent follows correct import paths, test commands, and domain-specific review criteria

## Agriculture-adapted audit team — implemented 2026-03-26
What: Replaced fintech audit personas (Jordan growth marketer, Chen compliance officer) with agriculture personas (Diego agronomist, Elena rural UX specialist)
Where: autoagent/skills/audit.md
Source: Internal audit — audit team was reviewing for SaaS conversion funnels instead of regenerative agriculture accuracy
Expected impact: Code reviews catch agronomic accuracy issues (wrong thresholds, synthetic recommendations) and rural UX problems (language complexity, phone-first design)

## Security scan in verification pipeline — implemented 2026-03-26
What: Added STEP 1.5 security scan (grep for hardcoded secrets + innerHTML) to the pre-commit verification pipeline, and added security scan line to verification report template
Where: autoagent/PROMPT.md (STEP 1.5 + STEP 2.5 verification report)
Source: everything-claude-code verification-loop/SKILL.md — Phase 5 security scan pattern
Expected impact: Catches hardcoded API keys and XSS vectors before commit, prevents Marcus (security) audit failures

## Backlog enrichment from agriculture research — implemented 2026-03-26
What: Added 3 new tasks to backlog: crop rotation planner (regenerative), irrigation optimization (drought-critical), global error middleware (production readiness). Removed duplicate Dashboard API entry. Renumbered all tasks.
Where: autoagent/memory/backlog.md
Source: WEF regenerative agriculture report, Agmatix AgTech trends 2025, FastAPI production patterns 2026
Expected impact: Next 3 sessions after dashboard work have clear, research-backed tasks that advance both regenerative intelligence and production readiness

## Strategic compaction decision table — implemented 2026-03-26
What: Added compaction decision table to PROMPT.md showing when to compact (research→planning, planning→implementation, implementation→testing, failed approach→new approach) and when NOT to (debugging→fix). Also documented what survives vs what is lost during compaction.
Where: autoagent/PROMPT.md (under CONTEXT_SUMMARY gate section)
Source: everything-claude-code strategic-compact/SKILL.md
Expected impact: Agents compact at the right phase boundaries instead of arbitrary points, preserving critical debugging context while freeing space after completed phases

## ACE curation cycle + brevity bias guard — implemented 2026-03-26
What: Added knowledge.md curation rule (every 10 sessions: merge duplicates, mark superseded, group by topic) with explicit brevity bias guard that preserves domain-specific thresholds/formulas during curation. Added delta update rule for reflexion writing.
Where: autoagent/PROMPT.md (STEP 4 section 8, STEP 0 section)
Source: ACE (Agentic Context Engineering) ICLR 2026 — arxiv 2510.04618
Expected impact: knowledge.md stays lean and organized without losing calibration data (thermal thresholds, drainage multipliers, etc.). Prevents context collapse from iterative rewrites.

## Test impact awareness — implemented 2026-03-26
What: Added note to PROMPT.md STEP 1 about identifying impacted test files before running full suite. Currently informational (cultivOS suite runs <10s) but prepares for future scaling.
Where: autoagent/PROMPT.md (STEP 1)
Source: TDAD (Test-Driven Agentic Development) arxiv 2603.17973
Expected impact: When test suite grows beyond 30s, agents will already know to run targeted tests first for faster feedback.

## Observation masking + context isolation — implemented 2026-03-26
What: Added two context management rules to agent-patterns.md: (1) observation masking — keep last 10 turns intact, old tool outputs are first compaction candidates; (2) multi-agent context isolation — narrow focused prompts for subagents, don't dump full context.
Where: autoagent/skills/agent-patterns.md (CONTEXT MANAGEMENT section)
Source: JetBrains Research blog "Cutting Through the Noise" (Dec 2025)
Expected impact: Sessions maintain reasoning clarity longer by prioritizing recent actions over verbose old tool outputs.

## Knowledge drift failure mode — implemented 2026-03-26
What: Added failure mode #8 "Knowledge Drift" to agent-patterns.md — warns agents to verify knowledge.md rules against current codebase before applying them, since the code may have changed since the rule was written.
Where: autoagent/skills/agent-patterns.md (FAILURE MODES section)
Source: ACE ICLR 2026 (context collapse pattern) + observed risk from 17-session knowledge accumulation
Expected impact: Prevents agents from following stale rules that reference renamed/removed functions or deprecated patterns.

## Backlog enrichment — soil microbiome + ancestral methods + API standardization — implemented 2026-03-26
What: Added 3 new tasks: #7 API response standardization (absorbs old #6), #8 soil microbiome indicators (Nature Food research), #9 ancestral farming methods knowledge base (WEF + traditional Mexican agriculture). Renumbered WhatsApp/voice tasks to #10/#11.
Where: autoagent/memory/backlog.md
Source: Nature Food 2024 (soil microbiome), WEF 2025 (regenerative agriculture), API Design best practices (everything-claude-code api-design skill)
Expected impact: Next sessions have clear, research-backed tasks advancing both regenerative intelligence (North Star pillars 3-4) and API quality.

## Error cascade prevention pattern — implemented 2026-03-27
What: Added failure mode #8 "Error Cascade" to agent-patterns.md with 4-category root cause classification (memory/planning/action/system) and "stop fixing forward, trace back to first divergence" rule.
Where: autoagent/skills/agent-patterns.md (FAILURE MODES section, new #8)
Source: AgentDebug framework (arxiv 2509.25370) — 26% improvement in task success with structured error classification
Expected impact: Prevents wasted cycles patching downstream symptoms when the root cause is an earlier step. Agents now have a concrete taxonomy for classifying errors before attempting fixes.

## Disease detection + anomaly detection backlog tasks — implemented 2026-03-27
What: Added 2 new backlog tasks: #9 disease/pest risk identification from NDVI anomalies, #10 automated field health anomaly alerts. Both with TDD test cases.
Where: autoagent/memory/backlog.md
Source: Frontiers in Plant Science 2024 (UAV disease detection), Nature Scientific Reports 2025 (AgroVisionNet), AgentDebug failure patterns (proactive monitoring)
Expected impact: Strengthens FODECIJAL Cerebro application by demonstrating AI anomaly detection capabilities. Backlog now has 8 autonomous tasks.

## Skill design principles from SWE-Skills-Bench — implemented 2026-03-27
What: Added evidence-based skill design rules to PROMPT.md: abstract guidance over templates, target genuine capability gaps, minimize context bloat (<150 lines), dynamic single-skill selection. Based on finding that 80% of skills provide zero improvement and 3 skills actually degraded performance by -9 to -10%.
Where: autoagent/PROMPT.md (under IF NO RELEVANT SKILL EXISTS)
Source: SWE-Skills-Bench (arxiv 2603.15401) — 49 skills evaluated, only 7 helped
Expected impact: Future skill files will be leaner and more abstract, avoiding the template-anchoring anti-pattern that caused performance degradation in the benchmark.

## Verification scaling rule — implemented 2026-03-27
What: Added tiered self-critique intensity to PROMPT.md Step 0: full (multi-file), light (single-file <20 lines, checks 1+3 only), skip (config/docs). Based on finding that 85-95% of self-verification is confirmatory (not corrective), wasting tokens.
Where: autoagent/PROMPT.md (STEP 0)
Source: Self-Verification Dilemma (arxiv 2602.03485) — EDS framework reduces tokens 9-20.3%
Expected impact: Trivial changes skip unnecessary re-reading, saving 2-5 tool calls per session on simple tasks. Complex changes still get full review.

## Doom-loop detection + stale-read prevention — implemented 2026-03-27
What: (1) Added doom-loop detection to PROMPT.md loop exit conditions: 3-iteration cap per test, 80-tool-call session checkpoint, thrashing detection (undo within 5 calls). (2) Added stale-read failure mode #10 to agent-patterns.md: re-read files if >10 tool calls since last read.
Where: autoagent/PROMPT.md (LOOP EXIT CONDITIONS), autoagent/skills/agent-patterns.md (FAILURE MODES #10)
Source: OPENDEV (arxiv 2603.05344) — stale-read detection + doom-loop cap patterns
Expected impact: Prevents the two most context-wasteful failure modes: infinite fix-retry loops and edits based on stale file state.

## Soil carbon MRV backlog task — implemented 2026-03-27
What: Added backlog task #13: soil carbon tracking with SOC estimation from soil organic matter %, carbon trend computation, Spanish-language report. Lightweight MRV-lite approach using existing soil data.
Where: autoagent/memory/backlog.md
Source: Regrow, Boomitra, InSoil MRV platforms (competitors charging $10-50k). cultivOS can estimate SOC from existing soil analyses at zero marginal cost.
Expected impact: Adds regenerative impact measurement to FODECIJAL application — proves interventions measurably improve soil carbon.

## Memory admission gate — implemented 2026-03-27
What: Added 5-factor admission criteria (future utility, semantic novelty, factual confidence, content type, temporal stability) as a gate before writing RULE entries to knowledge.md. Rules failing criteria 1 (no future utility) or 2 (duplicate) are rejected.
Where: autoagent/PROMPT.md (step 8, reflexion section)
Source: Adaptive Memory Admission Control (arxiv 2603.04549) — 5 complementary factors with content type prior as most influential
Expected impact: Reduces knowledge.md bloat by filtering out one-off observations and duplicate rules. knowledge.md currently has 355 lines — without admission control, it will hit context limits within ~20 more sessions.

## Farmer.Chat WhatsApp reference architecture — implemented 2026-03-27
What: Added Farmer.Chat architecture patterns (RAG + LLM + Whisper voice pipeline + progressive onboarding) to knowledge.md competitor intelligence section. Enriched WhatsApp MVP backlog task (#11) with specific implementation guidance.
Where: autoagent/memory/knowledge.md (WhatsApp Reference Architecture section), autoagent/memory/backlog.md (task #11)
Source: Farmer.Chat paper (arxiv 2409.08916v2) — 830K users, $0.35/farmer, 75% answer rate, 9s response time
Expected impact: When WhatsApp API token becomes available, the build session has a proven architecture to follow instead of designing from scratch. Key insight: translate-process-translate-back outperforms direct multilingual generation.

## Sawtooth context compression — implemented 2026-03-27
What: Replaced linear context growth pattern with explore→consolidate→compress cycle. Every ~15 tool calls, checkpoint findings to current_task.md instead of relying on raw tool outputs in context. Added concrete compression ratios (tool outputs 10:1-20:1, old turns 3:1-5:1, 70% threshold trigger).
Where: autoagent/PROMPT.md (CONTEXT_SUMMARY gate section)
Source: Focus architecture (arxiv 2601.07190) — 22.7% token reduction; Zylos Research 2026 — 26-54% reduction via ACON; SWE-Pruner (arxiv 2601.16746) — 23-38% reduction
Expected impact: Directly addresses context exhaustion before logging — the only recurring failure mode across 54 sessions. Agents now have concrete guidance on when to compress (70% budget, ~15 tool calls) and what to keep vs discard.

## Goal-hint file reading — implemented 2026-03-27
What: Added rule to state reading purpose in one sentence before reading any file, plus use offset+limit to target relevant sections.
Where: autoagent/skills/agent-patterns.md (CONTEXT MANAGEMENT section)
Source: SWE-Pruner (arxiv 2601.16746) — goal hints guide task-specific pruning, 23-38% token reduction
Expected impact: Reduces unnecessary context absorption from large files. Agents read 20 lines instead of 500 when they know what they're looking for.

## Plan granularity guard + over-specification prevention — implemented 2026-03-28
What: Added plan granularity guard to PROMPT.md (5-8 abstract steps, not 15+ micro-steps) and failure mode #11 to agent-patterns.md. Based on finding that agents over-specify 7× more than they omit.
Where: autoagent/PROMPT.md (TASK ROUTING section), autoagent/skills/agent-patterns.md (FAILURE MODES #11)
Source: arxiv 2603.14248 — Why Do LLM Web Agents Fail (hierarchical planning perspective)
Expected impact: Prevents over-detailed plans that anchor implementation and make replanning worse. Plans stay abstract enough to adapt when reality diverges.

## Redundancy check for tool calls — implemented 2026-03-28
What: Added redundancy detection rule to PROMPT.md loop exit conditions: before making a tool call, check if it's semantically similar to one in the last 3 turns. Common patterns: re-reading files, re-running passed tests, re-grepping known results.
Where: autoagent/PROMPT.md (LOOP EXIT CONDITIONS section)
Source: arxiv 2603.19896 — Utility-Guided Agent Orchestration (12% token reduction from redundancy elimination)
Expected impact: Reduces wasted tool calls in exploration and debugging phases. 12% token savings means more context budget for actual implementation.

## Enhanced failure taxonomy — implemented 2026-03-28
What: Added interface misuse and semantic misuse categories to the failure classification in PROMPT.md. Interface misuse = schema violations (malformed JSON, missing fields). Semantic misuse = valid but unproductive calls.
Where: autoagent/PROMPT.md (WHEN A TOOL CALL FAILS section)
Source: arxiv 2603.13404 — Schema First Tool APIs for LLM Agents
Expected impact: More precise failure classification leads to faster recovery. Semantic misuse category catches the common failure mode of making valid but pointless tool calls.

## Verification completeness scoring — implemented 2026-03-27
What: Added 3-level verification assessment (complete/partial/incomplete) with stop conditions (80% completeness, <5% improvement, max 3 cycles) to the verification contract.
Where: autoagent/skills/agent-patterns.md (VERIFICATION CONTRACT section)
Source: Plan-Execute-Verify-Replan (arxiv 2603.11445) — verification gates prevent premature conclusion
Expected impact: Prevents both over-verification (retrying when already done) and under-verification (committing when gaps remain). Stop conditions prevent infinite verify-fix loops.

## Optimization tip category in reflexion — implemented 2026-03-28
What: Added OPTIMIZATION line to reflexion format capturing suboptimal successes — things that worked but could be faster/cleaner. Three tip types (strategy from successes, recovery from failures, optimization from inefficient successes) give complete trajectory coverage.
Where: autoagent/PROMPT.md (step 8, reflexion format)
Source: Trajectory-Informed Memory Generation (arxiv 2603.10600)
Expected impact: Captures a class of lessons currently lost — sessions that succeed but waste time on suboptimal approaches. Rules from optimization tips prevent repeating slow patterns.

## Heuristic-driven rule retrieval — implemented 2026-03-28
What: Added proactive rule scanning before task start — search knowledge.md RULE entries for trigger conditions matching current task type. Selective retrieval by relevance outperforms loading all rules.
Where: autoagent/PROMPT.md (WHEN BUILDING A FEATURE section)
Source: Experiential Reflective Learning (arxiv 2603.24639) — LLM-based heuristic scoring > embedding for retrieval, k=20 optimal
Expected impact: Proactively applies past lessons instead of rediscovering them after a failure. Reduces retry cycles by front-loading relevant knowledge.

## Precision ag competitive positioning — implemented 2026-03-28
What: Added InsideClimateNews criticism analysis to knowledge.md — conventional precision ag hasn't proven environmental benefits, cultivOS's regenerative-first approach is the counter-narrative for FODECIJAL.
Where: autoagent/memory/knowledge.md (competitive intelligence section)
Source: InsideClimateNews (Feb 2026) + Nature portfolio study
Expected impact: Strengthens FODECIJAL grant narrative — cultivOS positions as the antidote to corporate precision ag criticism.

## Atomic action criteria for step quality — implemented 2026-03-28
What: Enhanced step quality bar with 3 formal criteria from Six Sigma Agent: minimality (can't decompose further), verifiability (correctness objectively determinable), determinism (unique correct output). Plus REASONING vs TOOL classification.
Where: autoagent/PROMPT.md (step quality bar section)
Source: Six Sigma Agent (arxiv 2601.22290) — enterprise-grade reliability through decomposed execution
Expected impact: Steps that meet all 3 criteria are more reliably executable. Classification helps set expectations (TOOL steps may fail due to external factors; REASONING steps should be deterministic).

## Red-flag output detection — implemented 2026-03-28
What: Added failure mode #12 to agent-patterns.md: when a step produces unexpectedly long output (>700 tokens) or format violations, discard and re-attempt rather than repair. Long outputs correlate with confusion.
Where: autoagent/skills/agent-patterns.md (FAILURE MODES #12)
Source: MAKER (arxiv 2511.09030) — million-step zero-error framework with red-flagging
Expected impact: Catches confused agent state early. Instead of building on a confused output, forces a clean restart of the step — preventing error cascades from propagating.

## Session invariants for behavioral drift prevention — implemented 2026-03-28
What: Added SESSION INVARIANTS section to PROMPT.md with 3 invariant checks (task scope, file scope, import direction) that must hold before every file-modifying tool call. Based on ABC framework's P,I,G,R structure where invariants (I) bound behavioral drift D* = α/γ.
Where: autoagent/PROMPT.md (new section before LOOP EXIT CONDITIONS)
Source: Agent Behavioral Contracts (arxiv 2602.22302) — formal specification and runtime enforcement for reliable AI agents
Expected impact: Prevents the gradual scope creep and task drift that accumulates in long sessions. The 3 invariants catch the most common drift patterns: starting side tasks, modifying unrelated files, and violating dependency direction.

## Mexico water efficiency data for FODECIJAL — implemented 2026-03-28
What: Added CARLOTA platform data (700 devices, 25,820 ha, 18.7M m³ water saved), CONAGUA precision ag messaging, and Mexico aquifer overexploitation stats (115/653) to knowledge.md competitive intelligence section.
Where: autoagent/memory/knowledge.md (FODECIJAL positioning section)
Source: Yucatan Times (World Water Day 2026), Mexico News Daily (water crisis article)
Expected impact: Strengthens FODECIJAL grant narrative with concrete Mexican water efficiency data. cultivOS positioned as accessible alternative to hardware-heavy corporate solutions like CARLOTA/Bayer.

## DRV function-level security focus — implemented 2026-03-28
What: Added rule to audit.md Marcus checklist: security checks should analyze at function-level scope (individual route handlers, service functions), not broad project-level sweeps. Function-level prompts produce more actionable findings.
Where: autoagent/skills/audit.md (Marcus checklist)
Source: Detect-Repair-Verify (arxiv 2603.00897) — function-level prompts outperform project-level for security detection
Expected impact: Reduces false positives in security audits and produces more targeted, actionable findings. Prevents the "spurious findings prompt unnecessary edits" anti-pattern.

## SERF retryable vs terminal error classification — implemented 2026-03-28
What: Added Step 1.5 to PROMPT.md error handling: classify failures as RETRYABLE (timeout, rate limit, transient) or TERMINAL (auth, missing resource, schema mismatch) before attempting recovery. Only retry retryable failures.
Where: autoagent/PROMPT.md (WHEN A TOOL CALL FAILS section, new Step 1.5)
Source: SERF — Structured Error Recovery Framework (arxiv 2603.13417) — machine-readable error semantics for deterministic self-correction
Expected impact: Prevents wasting 2+ tool calls retrying terminal failures. Agents now have a binary gate before deciding to retry vs fix root cause.

## Budget-aware exploration strategy — implemented 2026-03-28
What: Added budget-aware tool call strategy to PROMPT.md: >70% remaining = explore freely, 30-70% = focus on building, <30% = exploit only (finish current step, checkpoint, stop exploring). Transition from exploration to exploitation as budget depletes.
Where: autoagent/PROMPT.md (after doom-loop detection section)
Source: BAVT — Budget-Aware Value Tree Search (arxiv 2603.12634) — remaining resource ratio as scaling exponent over node values
Expected impact: Prevents context exhaustion by making budget awareness explicit. Agents shift from gathering information to completing tasks as context fills up — the #1 failure mode in long sessions.

## ERR early-step recovery dominance — implemented 2026-03-28
What: Added quantitative rule to doom-loop detection: recovery efficiency at step 2 determines downstream cascade severity (80%+ ES = 60% at step 6, 30% = collapse by step 4). If first 2 fix attempts miss, mental model is wrong — re-read from scratch.
Where: autoagent/PROMPT.md (doom-loop detection section)
Source: ERR measure (arxiv 2601.22352) — Expected Recovery Regret follows a measurable law
Expected impact: Stronger justification for the "stop after 2 failed fixes" rule. Agents now have a quantitative reason (geometric cascade) not just a heuristic.

## PALADIN failure taxonomy expansion — implemented 2026-03-28
What: Added 2 missing failure categories to PROMPT.md: "partial execution" (incomplete outputs needing continuation) and "re-entrant failures" (cascading across turns, references Error Cascade pattern #8). PALADIN achieves 89.68% recovery rate vs 32.76% baseline with 7-category taxonomy.
Where: autoagent/PROMPT.md (failure classification Step 1)
Source: PALADIN (arxiv 2509.25238) — ToolScan 7-category taxonomy
Expected impact: More precise failure classification catches two common patterns that were unnamed: truncated tool outputs and cascading fix failures.

## GCC milestone-triggered checkpointing — implemented 2026-03-28
What: Added milestone-triggered checkpoint rule alongside time-based (every 15 calls) sawtooth compression. Milestone checkpoints capture architectural state (what files exist, what interfaces connect) that time-based checkpoints miss. Agents who checkpoint at milestones develop more disciplined workflows.
Where: autoagent/PROMPT.md (sawtooth compression section)
Source: Git Context Controller (arxiv 2508.00031) — COMMIT/BRANCH/MERGE for LLM agent context
Expected impact: Better session resumption — milestone checkpoints carry more semantic meaning than "here's what happened in the last 15 tool calls."

## Anthropic skill quality standard — implemented 2026-03-28
What: Updated PROMPT.md skill design section with Anthropic's official 500-line SKILL.md limit (up from 150 lines), progressive disclosure for complex skills, and degrees-of-freedom matching (high/medium/low specificity matched to task fragility).
Where: autoagent/PROMPT.md (IF NO RELEVANT SKILL EXISTS section)
Source: Anthropic official skill authoring best practices (platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)
Expected impact: Skill files now follow Anthropic's validated guidelines. Progressive disclosure pattern enables complex skills without context bloat. Degrees-of-freedom matching prevents over-specification of flexible tasks and under-specification of fragile ones.

## File-pattern trigger table for automatic skill routing — implemented 2026-03-28
What: Added file-pattern-to-skill mapping table in INDEX.md that routes editing of specific file patterns (e.g. `src/cultivos/api/*.py` → `coding.md` + `security.md`) to the correct skill files automatically, eliminating manual skill selection.
Where: autoagent/skills/INDEX.md (new "File-pattern triggers" section)
Source: Codified Context (arxiv 2602.20478) — trigger tables for automatic agent routing, three-tier knowledge architecture
Expected impact: Agents automatically know which skill to load based on which files they're editing, reducing wrong-skill-selection errors and saving 1-2 tool calls per session on skill lookup.

## Agriculture AI reference architectures — implemented 2026-03-28
What: Added AgriRegion (region-aware RAG) and AgriGPT (Tri-RAG ecosystem) as reference architectures to knowledge.md competitive intelligence section. Added backlog task #27 for region-aware recommendations.
Where: autoagent/memory/knowledge.md (Agriculture AI Reference Architectures section), autoagent/memory/backlog.md (task #27)
Source: AgriRegion (arxiv 2512.10114), AgriGPT (arxiv 2508.08632)
Expected impact: When building multi-region recommendation engine or WhatsApp RAG pipeline, sessions have proven architecture patterns to follow. Region-aware recommendations strengthen FODECIJAL application by showing regional intelligence.

## Observation masking empirical validation — implemented 2026-03-28
What: Added empirical backing to observation masking rule in agent-patterns.md: M=10 observation masking achieves 54.8% solve rate at 52.7% cost reduction vs raw baseline. Added explicit warning against LLM summarization — causes "trajectory elongation" where agents explore unproductive paths longer.
Where: autoagent/skills/agent-patterns.md (CONTEXT MANAGEMENT section)
Source: The Complexity Trap (arxiv 2508.21433) — Qwen3-Coder 480B on SWE-bench Verified
Expected impact: Stronger justification for simple masking over complex summarization. Prevents future sessions from implementing expensive LLM-based context compression that doesn't actually help.

## Single-round reflection rule — implemented 2026-03-28
What: Added rule that one self-critique cycle captures ~90% of repair value. Multi-round reflection has diminishing returns. Do critique once (PROMPT.md Step 0), fix, then move to tests.
Where: autoagent/skills/agent-patterns.md (VERIFICATION CONTRACT section)
Source: Reflection-Driven Control (arxiv 2512.21354) — 9.3% security improvement with single-round reflection
Expected impact: Prevents wasting 2-3 tool calls on redundant re-critique cycles. Agents do one focused critique pass, then trust the tests to catch anything else.

## Backlog enrichment — field-level carbon, rotation, irrigation, comparison widgets — implemented 2026-03-28
What: Added 5 new backlog tasks (#32-#36): soil carbon widget, crop rotation widget, irrigation schedule widget, multi-field comparison view, farm-level carbon summary. All surface existing backend APIs in the frontend.
Where: autoagent/memory/backlog.md
Source: Internal audit — field.js fetches carbon/rotation/irrigation but doesn't render dedicated widgets; farm dashboard lacks field comparison view
Expected impact: Next 5+ sessions have clear frontend integration tasks that demonstrate deeper Cerebro intelligence on the field detail page for FODECIJAL reviewers.

## Dimension-isolated self-critique — implemented 2026-03-29
What: Added DimensionAwareFilter rule to PROMPT.md Step 0: each self-critique check is pass/fail independently — a pass on one does NOT compensate for a fail on another. Prevents high-performing aspects from masking failures.
Where: autoagent/PROMPT.md (STEP 0 self-critique section)
Source: AdaRubric (arxiv 2603.21362) — DimensionAwareFilter achieves r=0.79 human correlation by treating dimensions independently
Expected impact: Self-critique catches failures that would otherwise be hidden by passing dimensions. Prevents the "code works but edge cases are broken" pattern.

## Structural waste awareness + graduated degradation — implemented 2026-03-29
What: Added evict-by-staleness rule to context management: tool results >15 turns old are first eviction candidates. If re-requested content was removed, pin it by writing to current_task.md. Prefer graduated degradation over hard failure. 21.8% structural waste measured in production sessions.
Where: autoagent/PROMPT.md (sawtooth compression section)
Source: Pichay/Missing Memory Hierarchy (arxiv 2603.09023) — demand paging system, 93% context reduction, 0.0254% fault rate
Expected impact: More precise eviction decisions during compaction. "Graduated degradation" mindset prevents sessions from crashing when context is tight.

## Test resilience under code evolution — implemented 2026-03-29
What: Added test resilience rules to testing.md: run existing tests before writing new ones when modifying code, prefer behavioral assertions over syntactic, keep stable baseline tests, verify regression awareness. Based on finding that LLM-generated tests drop to 66% pass rate when code changes.
Where: autoagent/skills/testing.md (new TEST RESILIENCE section)
Source: arxiv 2603.23443 — Evaluating LLM-Based Test Generation Under Software Evolution (66% pass rate, >99% of failures are pattern-matching, not semantic)
Expected impact: Tests survive refactors better. Agents check existing tests first before writing new ones, catching regressions earlier.

## Logical context poisoning failure mode — implemented 2026-03-29
What: Added failure mode #13 to agent-patterns.md: "Logical Context Poisoning" — when topically distinct steps bleed into current reasoning. Fix: when switching subtasks, re-read current_task.md and relevant files for the NEW subtask instead of carrying assumptions.
Where: autoagent/skills/agent-patterns.md (FAILURE MODES section, new #13)
Source: Conversation Tree Architecture (arxiv 2603.21278) — context accumulation degrades response quality progressively
Expected impact: Prevents the subtle bug where debugging context from Step 3 contaminates implementation of Step 4. Agents reset context explicitly when switching subtask types.

## Reasoning-execution gap prevention — implemented 2026-04-08
What: Added session invariant #4 to PROMPT.md: verify current action matches current_task.md plan before executing. Agents that write correct plans but ignore them during execution fail 47% more often.
Where: autoagent/PROMPT.md (SESSION INVARIANTS section, new invariant #4)
Source: YC-Bench (arxiv 2604.01212) — benchmarking AI agents for long-term planning and consistent execution
Expected impact: Catches plan-execution divergence before it compounds. Top performers in YC-Bench maintained strict plan-action alignment.

## Tool necessity gate — implemented 2026-04-08
What: Added "Is this call necessary to advance the current step?" micro-check before every tool call. "More tool use is always beneficial" is empirically false — unnecessary calls waste context.
Where: autoagent/PROMPT.md (LOOP EXIT CONDITIONS section, before redundancy check)
Source: Agentic Tool Use in Large Language Models (arxiv 2604.00835) — comprehensive survey of tool use patterns
Expected impact: Reduces wasted tool calls by prompting necessity assessment before invocation. Complements existing redundancy check (which catches duplicates but not unnecessary-but-novel calls).

## Checkpoint density target — implemented 2026-04-08
What: Added quantified checkpoint density target (5-11 entries per 100 tool calls) to PROMPT.md milestone checkpointing rule. Agents at this density significantly outperform minimal-note agents.
Where: autoagent/PROMPT.md (checkpoint at milestones section)
Source: YC-Bench (arxiv 2604.01212) — scratchpad dominance correlates with task success
Expected impact: Provides a concrete measurable target for checkpointing frequency. Previous rule ("every ~15 tool calls") was approximate; this gives a validated density range.

## Emergency commit rule — implemented 2026-04-08
What: Added "EMERGENCY COMMIT" rule to PROMPT.md: when budget <30% and tests pass, commit immediately without waiting for full verification gate, frontend check, or logging. Ghost detection (step 1.5) backfills missing logs next session.
Where: autoagent/PROMPT.md (budget-aware exploration section)
Source: Internal analysis of sessions #219-#243 (persistent ghost session pattern) + COLLAPSE.md specification (85% threshold)
Expected impact: Directly prevents the #1 reliability problem: sessions completing work but crashing before commit+log. Code committed late > code never committed.

## Failure trajectory elongation detection — implemented 2026-04-08
What: Added failure mode #14 to agent-patterns.md: at 60 tool calls, assess forward progress; failing attempts use 4× resources and produce 12-82% longer trajectories. Emergency-commit if last 10 calls produced no green tests.
Where: autoagent/skills/agent-patterns.md (FAILURE MODES section, new #14)
Source: Inside the Scaffold (arxiv 2604.03515) — source-code taxonomy of 13 coding agent architectures
Expected impact: Earlier detection of failure trajectories. Combined with emergency commit rule, agents exit bad trajectories by committing what works rather than continuing to struggle.

## Test-gating per step — implemented 2026-04-08
What: Added rule to test after each function/route handler, not after all code. Scaffold-level test gating is the primary reliability lever — prompt interventions alone change outcomes by at most 2.6pp.
Where: autoagent/PROMPT.md (WHEN BUILDING A FEATURE section)
Source: Inside the Scaffold (arxiv 2604.03515) — scaffold architecture determines behavior more than prompt engineering
Expected impact: Earlier test feedback catches bugs before they compound. Moves testing from "gate at the end" to "feedback after each step."

## Pre-task backlog duplicate grep gate — implemented 2026-04-10
What: Added mandatory 30-second grep check to PROMPT.md step 3 before committing to any backlog task — grep endpoint path AND 2-3 keywords; if found mark as duplicate and pick next task
Where: autoagent/PROMPT.md (step 3, after "never start a session on a task you can't finish")
Source: Sessions #258 failure pattern (3 duplicate backlog tasks found mid-session) — rule was only in knowledge.md reflexion, not canonical step
Expected impact: Prevents wasted sessions on already-implemented features. 30-second grep at task selection prevents a full context window of re-implementation.

## Spec formula alignment test — implemented 2026-04-10
What: Added rule to PROMPT.md WHEN BUILDING A FEATURE: when spec lists explicit numeric values (point thresholds, weights, formulas), write a test assertion using those EXACT literal numbers BEFORE any implementation
Where: autoagent/PROMPT.md (WHEN BUILDING A FEATURE, after quick existence check)
Source: Session #259 failure (weighted fraction vs direct-point spec mismatch) + arxiv 2604.04226 (100% failure rate from API/type signature mismatch)
Expected impact: Catches formula mismatches at TDD stage, before implementation is written. The literal-value test fails immediately if the formula doesn't match the spec.

## Fail-before verification (TDD mandatory step) — implemented 2026-04-10
What: Added explicit rule to testing.md: after writing tests and BEFORE writing implementation, run pytest to confirm tests FAIL. Unexpected passes before implementation = feature exists or test logic error.
Where: autoagent/skills/testing.md (new section before VERIFICATION CONTRACT)
Source: arxiv 2604.05100 (Edit, But Verify — fail-before/pass-after validation essential for reliable TDD)
Expected impact: Catches tests that pass vacuously (always-true assertions, or feature already implemented). One test run at the right moment prevents submitting useless tests.

## Claude Managed Agents tier + Compaction — implemented 2026-04-10
What: Added Managed Agents (Beta) surface to claude_api.md with code pattern, tutorial notebook links, anthropic>=0.91.0 requirement. Added Server-Side Compaction section. Fixed stale StockCards project reference.
Where: autoagent/skills/claude_api.md (SURFACE SELECTION + new sections)
Source: Anthropic Cookbook managed_agents/ (April 8, 2026) + anthropics/skills claude-api SKILL.md update
Expected impact: When building WhatsApp chatbot or stateful agents, agent has correct architecture tier guidance and code pattern. Prevents using deprecated `budget_tokens` on new models.

## Collapse prevention thresholds — implemented 2026-04-08
What: Added concrete collapse thresholds to agent-patterns.md context management: 85% = imminent collapse (stop, checkpoint, emergency commit), 70% = build-only mode, >20% output repetition = early collapse signal.
Where: autoagent/skills/agent-patterns.md (CONTEXT MANAGEMENT section)
Source: COLLAPSE.md specification — AI Agent Context Collapse Prevention
Expected impact: Converts vague "context is getting low" to measurable triggers with prescribed actions. Prevents the slow degradation that precedes ghost sessions.
