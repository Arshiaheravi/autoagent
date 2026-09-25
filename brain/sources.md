# Brain Sources — Evaluated Resources

Track everything read so BRAIN sessions don't re-read old material.

---

## Repos Checked

- https://github.com/anthropics/skills — Anthropic official skills — checked 2026-03-26 — skipped (mostly creative/design skills, no agriculture-specific ones)
- https://github.com/affaan-m/everything-claude-code — community harness — checked 2026-03-26 — implemented (verification-loop security scan, continuous-learning pattern review). Re-checked 2026-03-26 — noted new skills: python-patterns, python-testing, api-design, database-migrations, security-scan, e2e-testing, deployment-patterns. Extracted python-patterns + api-design patterns.
- https://github.com/VoltAgent/awesome-agent-skills — 1,234+ agent skills collection — checked 2026-03-26 — skipped (general dev tools, no agriculture-specific skills)
- https://github.com/alirezarezvani/claude-skills — 192+ claude skills — checked 2026-03-26 — noted for future reference
- https://github.com/anthropics/anthropic-cookbook — Anthropic recipes — checked 2026-03-26 — noted (agent patterns notebooks, automatic-context-compaction notebook, memory cookbook — useful for future reference)
- https://github.com/anthropics/courses — Anthropic courses — checked 2026-03-26 — skipped (tool_use course covers basics, nothing novel beyond docs)

## Papers / Articles

- https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents — Anthropic official harness guide — read 2026-03-26 — implemented (progress docs, single-feature iterations, startup verification already in PROMPT.md; JSON over markdown for config already via sessions.json)
- https://arxiv.org/html/2508.11126v1 — "AI Agentic Programming: Survey of Techniques" — read 2026-03-26 — implemented (diff-level provenance, failure-conditioned retrieval already in PROMPT.md; hierarchical memory pattern noted)
- https://fortune.com/2026/03/24/ai-agents-are-getting-more-capable-but-reliability-is-lagging-narayanan-kapoor/ — Fortune AI reliability article — read 2026-03-26 — skipped (general industry commentary, no actionable patterns)
- https://www.langchain.com/state-of-agent-engineering — LangChain State of Agents — read 2026-03-26 — noted (57% agents in production, quality top barrier at 32%)
- https://www.weforum.org/stories/2025/01/delivering-regenerative-agriculture-through-digitalization-and-ai/ — WEF regenerative ag + AI — read 2026-03-26 — backlogged (crop rotation, cover cropping as key regenerative practices in Mexico)
- https://www.agmatix.com/blog/top-5-agtech-trends-for-2025-whats-next-for-regenerative-agriculture/ — Agmatix AgTech Trends 2025 — read 2026-03-26 — backlogged (unified multi-season analysis, carbon credit tracking)
- https://farmonaut.com/remote-sensing/ndvi-drone-ndvi-mapping-7-powerful-advances-for-2026 — Farmonaut NDVI advances — read 2026-03-26 — competitor reference (satellite + drone NDVI, 350M hectares mapped annually)
- https://fastlaunchapi.dev/blog/fastapi-best-practices-production-2026 — FastAPI production guide 2026 — read 2026-03-26 — backlogged (global error middleware task added to backlog)
- https://arxiv.org/abs/2510.04618 — ACE: Agentic Context Engineering (ICLR 2026) — read 2026-03-26 — implemented (curation cycle, delta updates, brevity bias guard added to PROMPT.md and agent-patterns.md)
- https://blog.jetbrains.com/research/2025/12/efficient-context-management/ — JetBrains context management research — read 2026-03-26 — implemented (observation masking, multi-agent context isolation added to agent-patterns.md)
- https://arxiv.org/abs/2603.17973 — TDAD: Test-Driven Agentic Development — read 2026-03-26 — implemented (test impact awareness note added to PROMPT.md STEP 1)
- https://arxiv.org/html/2506.11442v1 — ReVeal: Self-Evolving Code Agents via Iterative Generation-Verification — read 2026-03-26 — noted (RL-based self-verification, interesting but not actionable for current harness)
- https://arxiv.org/html/2603.13724 — Testing with AI Agents: Empirical Study — read 2026-03-26 — noted (AI tests have more assertions + lower cyclomatic complexity — confirms our testing patterns are good)
- https://softmaxdata.com/blog/the-biggest-lesson-from-ace-iclr-2026-the-power-of-agentic-engineering/ — ACE practical lessons blog — read 2026-03-26 — implemented (grow-and-refine strategy, context collapse warning)
- https://www.nature.com/articles/s43016-024-01001-1 — Root-soil-microbiome management for regenerative agriculture (Nature Food 2024) — read 2026-03-26 — backlogged (soil microbiome indicators task #8)
- https://www.omdena.com/blog/ai-agriculture-regenerative-practices-us — AI for Regenerative Agriculture (Omdena) — read 2026-03-26 — noted (AI soil monitoring replacing physical sampling, Biome Makers microbiome analysis)
- https://resources.anthropic.com/hubfs/2026%20Agentic%20Coding%20Trends%20Report.pdf — Anthropic 2026 Agentic Coding Trends Report — read 2026-03-26 — skipped (PDF rendering failed, could not extract content)
- https://arxiv.org/abs/2602.16666v1 — "Towards a Science of AI Agent Reliability" — read 2026-03-27 — implemented (4-dimension reliability framework: consistency, robustness, predictability, safety → added to agent-patterns.md)
- https://arxiv.org/abs/2602.01869 — "ProcMEM: Learning Reusable Procedural Memory from Experience" — read 2026-03-27 — implemented (Skill-MDP format with activation/termination conditions → enhanced SKILL_LIBRARY in PROMPT.md)
- https://github.com/affaan-m/everything-claude-code — re-checked 2026-03-27 — implemented (autonomous-loops exit patterns, search-first quick check, plankton write-time enforcement noted)
- https://github.com/VoltAgent/awesome-ai-agent-papers — checked 2026-03-27 — noted (ProcMEM, CTHA, MonoScale papers — ProcMEM implemented)
- https://www.getmaxim.ai/articles/context-window-management-strategies-for-long-context-ai-agents-and-chatbots/ — read 2026-03-27 — implemented (context budget allocation priority rules → enhanced CONTEXT_SUMMARY gate in PROMPT.md)
- https://borgenproject.org/ai-in-latin-americas-agriculture/ — read 2026-03-27 — implemented (Kilimo, Agrosmart, Madre Tierra competitor data → knowledge.md + backlog SMS alerts task)
- https://www.worldagritechmexico.com/articles/grupo-bimbo-transitioning-regenerative-agriculture-practices-smallholder-mexican-farmers — read 2026-03-27 — noted (Grupo Bimbo regenerative programs in Mexico, reference for future partnerships)
- https://dev.to/thesius_code_7a136ae718b7/production-ready-fastapi-project-structure-2026-guide-b1g — read 2026-03-27 — skipped (standard factory pattern, already implemented in cultivOS)
- https://dasroot.net/posts/2026/02/rate-limiting-ai-apis-async-middleware-fastapi-redis/ — read 2026-03-27 — noted (Redis rate limiting pattern, useful when we add multi-tenant API access)
- https://arxiv.org/abs/2509.23864v1 — "AgentGuard: Runtime Verification of AI Agents" — read 2026-03-27 — noted (3-layer verification: I/O observation, dynamic MDP, probabilistic checking — interesting but too complex for current harness)

- https://arxiv.org/abs/2509.25370 — "Where LLM Agents Fail" — AgentDebug 5-category failure taxonomy (memory/reflection/planning/action/system) — read 2026-03-27 — implemented (error cascade pattern #8 in agent-patterns.md)
- https://arxiv.org/html/2603.21357 — AgentHER: Hindsight Experience Replay for LLM Agent Trajectories — read 2026-03-27 — noted (relabel failed runs as training data for narrower goals — interesting but not actionable for file-based harness)
- https://arxiv.org/abs/2602.00276 — L-ICL: Localizing and Correcting LLM Planner Errors — read 2026-03-27 — noted (localize first constraint violation + inject minimal correction — already covered by our step-by-step verification pattern)
- https://arxiv.org/abs/2502.12110 — A-Mem: Agentic Memory with Zettelkasten-style linking — read 2026-03-27 — noted (structured notes with relationship mapping — our knowledge.md SKILL tags serve similar purpose)
- https://arxiv.org/abs/2512.13564 — "Memory in the Age of AI Agents" survey — noted 2026-03-27 — reference for future memory architecture improvements
- https://arxiv.org/abs/2603.03293 — SE-Search: Self-Evolving Search Agent — noted 2026-03-27 — Think-Search-Memorize strategy, useful if we add search capabilities
- https://arxiv.org/html/2603.07670 — Memory for Autonomous LLM Agents: Mechanisms survey — noted 2026-03-27 — comprehensive evaluation framework for agent memory
- https://l.coecytjal.org.mx/convocatorias — COECyTJAL FODECIJAL 2026 — read 2026-03-27 — noted (TRL 4→5/6 maturity required, needs IP/copyright registration, fiscal address in Jalisco)
- https://www.frontiersin.org/journals/plant-science/articles/10.3389/fpls.2024.1435016/full — UAV deep learning for crop disease/pest detection — read 2026-03-27 — backlogged (95%+ accuracy with CNN + thermal, added disease detection task #9)
- https://www.nature.com/articles/s41598-025-32384-1 — AI-driven drone for early crop disease detection (Nature Scientific Reports 2025) — noted 2026-03-27 — AgroVisionNet CNN-Transformer hybrid for sub-millimeter lesion detection
- https://github.com/affaan-m/everything-claude-code — re-checked 2026-03-27 — v1.9.0 adds pytorch-patterns, documentation-lookup, bun-runtime, nextjs-turbopack, mcp-server-patterns. None agriculture-specific.
- https://code.claude.com/docs/en/best-practices — Claude Code official best practices — read 2026-03-27 — noted (CLAUDE.md pruning: "if Claude does it correctly without the instruction, delete it")
- https://arize.com/blog/claude-md-best-practices-learned-from-optimizing-claude-code-with-prompt-learning/ — CLAUDE.md optimization via Prompt Learning — read 2026-03-27 — noted (emphasis tuning with "IMPORTANT"/"MUST", lessons.md for mistake prevention, prune regularly)
- https://www.faros.ai/blog/best-ai-coding-agents-2026 — AI coding agent reviews 2026 — read 2026-03-27 — skipped (product comparison, no actionable patterns)
- https://arxiv.org/abs/2603.05344 — OPENDEV: Building Effective AI Coding Agents for the Terminal — read 2026-03-27 — implemented (doom-loop detection, stale-read detection, instruction fade-out reminders already covered)
- https://arxiv.org/abs/2603.15401 — SWE-Skills-Bench: Do Agent Skills Actually Help? — read 2026-03-27 — implemented (skill design principles: abstract > templates, 80% of skills = zero improvement, context bloat warning)
- https://arxiv.org/abs/2603.21489 — Effective Strategies for Asynchronous Software Engineering Agents — read 2026-03-27 — noted (git worktree isolation, compressed execution history, multi-agent coordination gains 14-27%, diminishing returns after 100 iterations)
- https://arxiv.org/abs/2602.03485 — Self-Verification Dilemma: Experience-Driven Suppression of Overused Checking — read 2026-03-27 — implemented (verification scaling rule: full/light/skip based on change scope, 85-95% of self-checks are confirmatory)
- https://github.com/affaan-m/everything-claude-code — re-checked 2026-03-27 — v1.9.0 selective install, 6 new agents, plankton-code-quality, cost-aware-llm-pipeline. No new agriculture-relevant skills.
- https://github.com/anthropics/skills — re-checked 2026-03-27 — 17 skills total, last updated Mar 22. NCBI-database-skill added Mar 14. No agriculture-specific skills.
- https://www.regrow.ag/ — Regrow: MRV for soil carbon at scale, 17 countries — noted 2026-03-27 — competitor reference for MRV/carbon features
- https://boomitra.com/ — Boomitra: satellite + AI carbon removal credits — noted 2026-03-27 — competitor reference for carbon tracking
- https://insoil.com/mrv-technology/ — InSoil: AI satellite MRV for regenerative practices — noted 2026-03-27 — competitor reference for practice verification
- https://arxiv.org/abs/2512.24103 — Enhancing LLM Planning through Intrinsic Self-Critique — noted 2026-03-27 — significant gains without external verifiers, but Blocksworld domain (not directly actionable)
- https://medium.com/@dave-patten/the-state-of-ai-coding-agents-2026 — State of AI Coding Agents 2026 — skipped 2026-03-27 (general industry overview, no actionable patterns)

## Search Terms Used

- "autonomous AI coding agent reliability patterns best practices 2025 2026" — searched 2026-03-26
- "Claude Code agent skills SKILL.md github 2026" — searched 2026-03-26
- "precision agriculture WhatsApp chatbot small farms NDVI drone platform 2025 2026" — searched 2026-03-26
- "FastAPI production patterns middleware error handling 2025 2026" — searched 2026-03-26
- "regenerative agriculture AI recommendation engine organic farming Mexico 2025 2026" — searched 2026-03-26
- "autonomous AI coding agent best practices reliability 2026" — searched 2026-03-26
- "LLM agent self-improvement context management techniques 2026" — searched 2026-03-26
- "precision agriculture AI platform small farms NDVI soil health 2026" — searched 2026-03-26
- "FastAPI production patterns async SQLAlchemy 2026" — searched 2026-03-26
- "regenerative agriculture soil microbiome AI recommendations ancestral farming methods Mexico Latin America 2026" — searched 2026-03-26
- "arXiv autonomous coding agent test generation verification 2026" — searched 2026-03-26
- "autonomous AI coding agent best practices reliability 2026 arxiv" — searched 2026-03-27
- "Claude Code agent skills SKILL.md github new 2026" — searched 2026-03-27
- "precision agriculture AI small farms drone NDVI soil health platform 2026" — searched 2026-03-27
- "FastAPI production patterns async middleware 2026" — searched 2026-03-27
- "LLM agent context window management memory techniques 2026" — searched 2026-03-27
- "regenerative agriculture AI platform Mexico Latin America small farms 2026" — searched 2026-03-27
- "arXiv agent self-correction tool use verification loop 2026" — searched 2026-03-27
- "autonomous AI coding agent best practices reliability 2026 arxiv new papers" — searched 2026-03-27
- "Claude Code agent skills SKILL.md github new 2026 march" — searched 2026-03-27
- "precision agriculture AI drone NDVI WhatsApp small farms Mexico 2026" — searched 2026-03-27
- "LLM agent planning self-correction error recovery techniques 2026 arxiv" — searched 2026-03-27
- "FastAPI SQLAlchemy production patterns async 2026 best practices" — searched 2026-03-27
- "FODECIJAL COECYTJAL 2026 convocatoria requisitos innovacion tecnologica" — searched 2026-03-27
- "arXiv agent memory retrieval augmented generation coding 2026 new" — searched 2026-03-27
- "disease detection pest identification AI drone crop image classification deep learning 2026" — searched 2026-03-27
- "claude code CLAUDE.md best practices project instructions optimization 2026" — searched 2026-03-27
- "autonomous AI coding agent best practices reliability 2026 arxiv new papers march" — searched 2026-03-27
- "Claude Code agent skills SKILL.md github new 2026 march april" — searched 2026-03-27
- "precision agriculture AI drone soil health WhatsApp small farms Mexico Latin America 2026" — searched 2026-03-27
- "FastAPI production patterns async background tasks 2026 best practices" — searched 2026-03-27
- "arXiv LLM agent planning self-correction verification 2026 new papers" — searched 2026-03-27
- "arxiv 2602.03485 self-verification dilemma LLM overused checking suppression" — searched 2026-03-27
- "site:github.com anthropics/skills new commits 2026 march" — searched 2026-03-27
- "arXiv OPENDEV multi-agent software development 2603.05344 2026" — searched 2026-03-27
- "regenerative agriculture soil carbon measurement MRV AI platform Mexico 2026" — searched 2026-03-27

## Session #43 Sources — 2026-03-27

- https://arxiv.org/abs/2603.04549 — Adaptive Memory Admission Control for LLM Agents — read 2026-03-27 — implemented (5-factor admission gate added to PROMPT.md reflexion rules)
- https://arxiv.org/abs/2603.12740 — ToolTree: MCTS-based tool planning with dual-feedback — read 2026-03-27 — skipped (training-time technique, not actionable for file-based harness)
- https://arxiv.org/abs/2603.20432 — Coding Agents are Effective Long-Context Processors — read 2026-03-27 — noted (confirms file-system-as-memory approach; 17.3% over SOTA by using tools over attention)
- https://arxiv.org/abs/2603.17831 — RPMS: Rule-Augmented Memory Synergy for embodied planning — read 2026-03-27 — noted (conflict resolution between rules and memory, not directly actionable)
- https://arxiv.org/html/2409.08916v2 — Farmer.Chat: Scaling AI-Powered Agricultural Services for Smallholder Farmers — read 2026-03-27 — implemented (architecture patterns added to knowledge.md, WhatsApp backlog enriched)
- https://qaltivate.com/blog/agtech-trends-2026/ — Top 6 AgTech Trends 2026 — read 2026-03-27 — noted (AI agents in farming, carbon farming MRV becoming profitable, validates soil carbon task #13)
- https://github.com/affaan-m/everything-claude-code — re-checked 2026-03-27 — no new agriculture-relevant skills since last check. 5 new business skills (article-writing, market-research, investor-materials). 6 new language agents.
- https://github.com/VoltAgent/awesome-ai-agent-papers — re-checked 2026-03-27 — no March 2026 papers added yet (last update was Feb 2026)
- https://arxiv.org/html/2601.17581 — How AI Coding Agents Modify Code: Large-Scale GitHub PR Study — noted 2026-03-27 — Copilot-style agents produce more stable code (death rate 20-30pp lower than human baseline)
- https://www.help.gooey.ai/farmerchat — Farmer.Chat by Digital Green + Gooey.AI — read 2026-03-27 — reference for WhatsApp agricultural chatbot implementation
- https://github.com/mandarwagh9/KisanAI — KisanAI: Flask WhatsApp chatbot for farmers — noted 2026-03-27 — open-source reference for WhatsApp agricultural bot (Flask + Twilio)

## Session #54 Sources — 2026-03-27

- https://arxiv.org/html/2601.07190 — Active Context Compression: Autonomous Memory Management in LLM Agents (Focus architecture) — read 2026-03-27 — implemented (sawtooth compression pattern with ~15 tool-call checkpoints added to PROMPT.md, 22.7% token reduction measured)
- https://zylos.ai/research/2026-02-28-ai-agent-context-compression-strategies — Zylos Research: AI Agent Context Compression Strategies — read 2026-03-27 — implemented (compression ratios: tool outputs 10:1-20:1, old turns 3:1-5:1, 70% threshold trigger added to PROMPT.md)
- https://arxiv.org/html/2601.16746v1 — SWE-Pruner: Self-Adaptive Context Pruning for Coding Agents — read 2026-03-27 — implemented (goal-hint file reading rule added to agent-patterns.md, 23-38% token reduction measured)
- https://arxiv.org/html/2601.20404v1 — On the Impact of AGENTS.md Files on AI Coding Agent Efficiency — read 2026-03-27 — noted (validates CLAUDE.md approach: 28.64% faster execution, 16.58% fewer output tokens. Focus on conventions, architecture, project structure)
- https://arxiv.org/html/2603.11445 — Plan-Execute-Verify-Replan Framework — read 2026-03-27 — implemented (verification completeness scoring with complete/partial/incomplete + stop conditions added to agent-patterns.md)
- https://arxiv.org/abs/2602.19633 — TAPE: Tool-Guided Adaptive Planning and Constrained Execution — read 2026-03-27 — noted (multi-path graph planning + constrained decoding, too abstract for file-based harness)
- https://arxiv.org/html/2503.09572v3 — Plan-and-Act: Dynamic Replanning for Long-Horizon Tasks — read 2026-03-27 — noted (dynamic replanning after each step, already covered by PROMPT.md global consistency check)
- https://arxiv.org/abs/2512.08769 — Practical Guide for Production-Grade Agentic AI Workflows — read 2026-03-27 — noted (pure-function invocation, single-responsibility agents, externalized prompt management — already implemented in cultivOS)
- https://github.com/affaan-m/everything-claude-code — re-checked 2026-03-27 — no new agriculture-relevant skills. v1.9.0 stable with language-specific agents.
- https://skillsmp.com/ — SkillsMP: Agent Skills Marketplace — noted 2026-03-27 — new resource for finding Claude/Codex skills
- https://openteam.community/ — OpenTEAM: Open Technology Ecosystem for Agricultural Management — noted 2026-03-27 — farmer-driven interoperable platform, potential integration partner
- https://www.soilassociation.org/farmers-growers/our-farming-projects/ai-4-soil-health/ — AI 4 Soil Health — noted 2026-03-27 — soil health measurement app launching 2026, potential competitor/partner

## Search Terms — Session #54

- "arxiv autonomous AI coding agent best practices reliability 2026 new papers march april" — searched 2026-03-27
- "Claude Code agent skills SKILL.md github new 2026 march april" — searched 2026-03-27
- "precision agriculture AI drone NDVI WhatsApp small farms Mexico regenerative 2026" — searched 2026-03-27
- "arxiv LLM agent context exhaustion recovery checkpoint techniques 2026" — searched 2026-03-27
- "arxiv PARC adaptive replanning coding agent plan revision 2026" — searched 2026-03-27
- "FastAPI background tasks scheduling cron production patterns 2026" — searched 2026-03-27
- "FODECIJAL COECYTJAL 2026 resultados convocatoria innovacion tecnologica Jalisco" — searched 2026-03-27
- "arxiv SWE-agent tool use efficiency reduce context usage coding agent 2026" — searched 2026-03-27
- "regenerative agriculture soil health monitoring API open source platform 2026" — searched 2026-03-27

## Session #64 Sources — 2026-03-28

- https://arxiv.org/html/2603.13404 — Schema First Tool APIs for LLM Agents: tool misuse, recovery, budgeted performance — read 2026-03-28 — implemented (enhanced failure taxonomy with interface/semantic misuse categories in PROMPT.md)
- https://arxiv.org/html/2603.19896 — Utility-Guided Agent Orchestration: reducing excessive tool calls — read 2026-03-28 — implemented (redundancy check rule added to PROMPT.md loop exit conditions, 12% token reduction)
- https://arxiv.org/html/2603.14248 — Why Do LLM Web Agents Fail: hierarchical planning perspective — read 2026-03-28 — implemented (plan granularity guard in PROMPT.md + over-specification failure mode #11 in agent-patterns.md)
- https://code.claude.com/docs/en/changelog — Claude Code March 2026 changelog — read 2026-03-28 — noted (effort frontmatter for skills, --channels MCP push, maxTurns/disallowedTools agent config, worktree isolation improvements)
- https://github.com/affaan-m/everything-claude-code — re-checked 2026-03-28 — no new agriculture-relevant skills. v1.9.0 stable with 6 language agents + selective install.
- https://soilcarbonfutures.earth/mrv/ — Soil Carbon Futures: open MRV models/tools for soil carbon — noted 2026-03-28 — reference for carbon tracking validation (adaptable components, remote sensing + AI models)

## Search Terms — Session #64

- "arxiv 2603 2604 LLM agent tool use planning error recovery coding 2026" — searched 2026-03-28
- "Claude Code 7.x new features changelog 2026 march" — searched 2026-03-28
- "regenerative agriculture digital MRV soil carbon API open source platform Mexico 2026" — searched 2026-03-28
- "arxiv 2604 LLM agent autonomous coding software engineering new papers 2026" — searched 2026-03-28
- "precision agriculture AI drone NDVI WhatsApp small farms Mexico regenerative 2026 new" — searched 2026-03-28
- "FastAPI production patterns async background tasks celery 2026 best practices new" — searched 2026-03-28

## Session #73 Sources — 2026-03-28 (DEEP BRAIN)

- https://arxiv.org/html/2603.24639 — Experiential Reflective Learning for Self-Improving LLM Agents — read 2026-03-28 — implemented (heuristic-driven rule retrieval before task start added to PROMPT.md)
- https://arxiv.org/html/2603.10600 — Trajectory-Informed Memory Generation for Self-Improving Agent Systems — read 2026-03-28 — implemented (OPTIMIZATION tip category added to reflexion format in PROMPT.md)
- https://arxiv.org/html/2603.18718 — MemMA: Coordinating Memory Cycle through Multi-Agent Reasoning — read 2026-03-28 — noted (probe-based verification interesting but too complex for file-based system; focus-point guidance partially covered by memory admission gate)
- https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md — Claude Code v2.1.83-2.1.86 changelog — read 2026-03-28 — noted (effort frontmatter for skills, initialPrompt for agents, Read tool deduplicates re-reads, conditional hooks, PowerShell tool, transcript search)
- https://insideclimatenews.org/news/28022026/precision-agriculture-and-ai/ — Inside Climate News: precision ag criticism — read 2026-03-28 — implemented (competitive positioning added to knowledge.md — cultivOS is regenerative-first counter to Big Ag precision ag criticism)
- https://arxiv.org/html/2512.07921v1 — DeepCode: Open Agentic Coding — noted 2026-03-28 — blueprint distillation + stateful code memory interesting but training-time technique
- https://arxiv.org/html/2510.03463v1 — ALMAS: Autonomous LLM Multi-Agent SE Framework — noted 2026-03-28 — agile team roles for coding agents, LLM-as-retriever for codebase
- https://arxiv.org/html/2602.07359 — W&D: Scaling Parallel Tool Calling — noted 2026-03-28 — confirms parallel tool calls improve speed, diminishing returns after depth >5
- https://planetarysolutions.yale.edu/posts/2025-06-05-ai-powered-low-cost-soil-carbon-verification-scalable-and-continuous-monitoring — Yale AI soil carbon verification — noted 2026-03-28 — open-access soil carbon database in development
- https://www.perennial.earth/ — Perennial: VT0014 Verra-approved digital soil mapping — noted 2026-03-28 — competitor reference for carbon MRV
- https://eos.com/blog/how-eosda-monitors-sequestrated-carbon-with-ai-and-ml/ — EOSDA satellite ML for SOC — noted 2026-03-28 — competitor reference

## Search Terms — Session #73

- "arxiv LLM autonomous coding agent new techniques 2026 march april" — searched 2026-03-28
- "Claude Code new features changelog march 2026" — searched 2026-03-28
- "precision agriculture AI WhatsApp voice small farms Mexico regenerative 2026 new" — searched 2026-03-28
- "FastAPI production patterns 2026 new best practices async" — searched 2026-03-28
- "arxiv 2604 2603 LLM agent self-improvement memory retrieval coding 2026 new papers" — searched 2026-03-28
- "site:arxiv.org LLM coding agent error recovery test generation 2026" — searched 2026-03-28
- "arxiv 2604 LLM agent structured output tool use function calling improvements 2026" — searched 2026-03-28
- "regenerative agriculture soil carbon measurement API open source Mexico LATAM 2026" — searched 2026-03-28

## Session #82 Sources — 2026-03-28

- https://arxiv.org/abs/2511.09030 — MAKER: Solving a Million-Step LLM Task with Zero Errors — read 2026-03-28 — implemented (red-flag output pattern added to agent-patterns.md #12; maximal decomposition validates atomic action criteria)
- https://arxiv.org/abs/2601.22290 — Six Sigma Agent: Enterprise-Grade Reliability through Consensus-Driven Decomposed Execution — read 2026-03-28 — implemented (atomic action criteria: minimality/verifiability/determinism added to PROMPT.md step quality bar)
- https://arxiv.org/html/2603.00897 — Detect-Repair-Verify for Securing LLM-Generated Code — read 2026-03-28 — implemented (function-level security focus rule added to audit.md Marcus checklist)
- https://arxiv.org/abs/2603.19935 — Memori: Persistent Memory Layer for LLM Agents — read 2026-03-28 — noted (67% token reduction via semantic triples, 1,294 tokens/query — validates our structured knowledge.md approach)
- https://arxiv.org/abs/2601.01885 — AgeMem: Agentic Memory with Unified LTM/STM Management — read 2026-03-28 — noted (6 memory operations as tools, RL-learned storage decisions — too complex for file-based harness, but filter threshold θ=0.6 is interesting)
- https://arxiv.org/abs/2504.19678 — From LLM Reasoning to Autonomous AI Agents: Comprehensive Review — read 2026-03-28 — noted (60 benchmarks, ACP/MCP/A2A protocols survey, general review)
- https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md — re-checked 2026-03-28 — no new releases after v2.1.86 (March 27)
- https://github.com/affaan-m/everything-claude-code/releases — re-checked 2026-03-28 — no releases after v1.9.0 (March 21)
- https://github.com/sickn33/antigravity-awesome-skills — 1,329+ agentic skills collection — checked 2026-03-28 — noted (no agriculture-specific skills, runtime hardening interesting but already covered by audit.md)
- https://github.com/astronova001/Krushak-Agri-Chat-Bot — Krushak AgriChat: Django + Gemini WhatsApp agricultural chatbot — read 2026-03-28 — backlogged (added as WhatsApp reference in backlog; key insight: multi-language via LLM prompting, no separate NLP pipeline)
- https://arxiv.org/html/2510.14453 — Natural Language Tools: NL approach to tool calling — noted 2026-03-28 — 18.4pp accuracy improvement + 70% variance reduction, but not applicable to our harness (we don't control tool calling format)

## Search Terms — Session #82

- "arxiv LLM autonomous coding agent new techniques papers 2026 april march" — searched 2026-03-28
- "Claude Code new features changelog april 2026" — searched 2026-03-28
- "precision agriculture AI drone NDVI WhatsApp small farms Mexico regenerative 2026 new" — searched 2026-03-28
- "arxiv LLM agent memory context management new papers 2026" — searched 2026-03-28
- "arxiv 2604 LLM agent test generation verification self-repair coding 2026 new papers" — searched 2026-03-28
- "FastAPI production patterns async middleware rate limiting 2026 best practices new" — searched 2026-03-28

## Session #100 Sources — 2026-03-28

- https://arxiv.org/abs/2603.13417 — Bridging Protocol and Production: MCP Design Patterns (CABP, ATBA, SERF) — read 2026-03-28 — implemented (SERF retryable vs terminal error classification added to PROMPT.md Step 1.5)
- https://arxiv.org/abs/2603.12634 — Budget-Aware Value Tree Search (BAVT): budget-conditioned exploration→exploitation — read 2026-03-28 — implemented (budget-aware exploration strategy added to PROMPT.md after doom-loop detection)
- https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices — Anthropic official skill authoring best practices — read 2026-03-28 — implemented (500-line limit, degrees of freedom matching, progressive disclosure updated in PROMPT.md skill design section)
- https://arxiv.org/abs/2602.14878 — MCP Tool Descriptions Are Smelly: 97.1% have defects, selective augmentation > blanket — read 2026-03-28 — noted (principle applicable to skill files: more detail != better)
- https://arxiv.org/abs/2511.17006 — Budget-Aware Tool-Use Scaling (BATS): Budget Tracker plug-in for continuous budget awareness — noted 2026-03-28 — pattern captured in BAVT implementation
- https://arxiv.org/abs/2603.13110 — AgentRM: OS-Inspired Resource Manager (MLFQ scheduler, context lifecycle manager) — noted 2026-03-28 — too complex for file-based harness, zombie reaping concept interesting
- https://arxiv.org/abs/2601.12560 — Agentic AI Architectures, Taxonomies, and Evaluation survey — noted 2026-03-28 — controllable orchestration trend (state machines + checkpointing) validates our current_task.md approach
- https://arxiv.org/abs/2602.06841 — From Features to Actions: Explainability in Agentic AI — noted 2026-03-28 — trace-grounded rubric analysis for failure diagnosis; already covered by diff-level provenance pattern

## Session #109 Sources — 2026-03-28 (DEEP BRAIN+META)

- https://arxiv.org/abs/2601.22352 — ERR: Recoverability Has a Law for Tool-Augmented Agents — read 2026-03-28 — implemented (early-step recovery dominance rule added to PROMPT.md doom-loop section; 80%+ recovery at step 2 = 60% at step 6, 30% = collapse by step 4)
- https://arxiv.org/html/2509.25238 — PALADIN: Self-Correcting Language Model Agents (ToolScan taxonomy) — read 2026-03-28 — implemented (partial execution + re-entrant failure categories added to PROMPT.md failure taxonomy; 89.68% recovery rate vs 32.76% baseline)
- https://arxiv.org/html/2508.00031v1 — Git Context Controller (GCC): COMMIT/BRANCH/MERGE for LLM agents — read 2026-03-28 — implemented (milestone-triggered checkpointing rule added to PROMPT.md sawtooth section)
- https://arxiv.org/html/2603.20625v1 — ACRFence: Preventing Semantic Rollback Attacks in Agent Checkpoint-Restore — read 2026-03-28 — noted (semantic rollback risks in checkpoint-restore; not actionable for file-based harness — we don't have external tool calls with side effects)
- https://arxiv.org/abs/2504.19678 — From LLM Reasoning to Autonomous AI Agents: Comprehensive Review (updated Mar 2026) — noted 2026-03-28 — survey of 60 benchmarks and ACP/MCP/A2A protocols; general reference
- https://greyb.com/blog/ai-agriculture-startups/ — 10 AI Agriculture Startups 2026 — read 2026-03-28 — implemented (RegenCrops competitor intel added to knowledge.md: 33% soil carbon increase, 95% water savings, India-focused)
- https://github.com/anthropics/skills — re-checked 2026-03-28 — 105k stars, 25 commits. No new agriculture-specific skills since last check.
- https://github.com/affaan-m/everything-claude-code — re-checked 2026-03-28 — v1.9.0 stable (selective install, 12 languages, 6 new agents). No new agriculture-relevant skills.
- https://code.claude.com/docs/en/changelog — Claude Code changelog re-checked 2026-03-28 — v2.1.86 (March 27): session ID header, VCS exclusions, resume fixes. No major new features.

## Search Terms — Session #109

- "arxiv LLM autonomous coding agent new techniques 2026 march april papers" — searched 2026-03-28
- "arxiv agent tool use error recovery self-improvement 2604 2603 2026" — searched 2026-03-28
- "Claude Code new features changelog april 2026" — searched 2026-03-28
- "precision agriculture AI FODECIJAL COECYTJAL grant Mexico drone regenerative 2026" — searched 2026-03-28
- "arxiv LLM agent context window checkpoint resume long session 2026 new" — searched 2026-03-28
- "regenerative agriculture AI platform Mexico small farms WhatsApp voice 2026 startup" — searched 2026-03-28
- https://www.icl-group.com/blog/agriculture-in-2026-moving-from-ai-hype-to-roi-resilience/ — ICL: Agriculture 2026 moving from AI hype to ROI — noted 2026-03-28 — 65% farms adopting precision ag, standardization + survivability as 2026 themes
- https://github.com/anthropics/skills — re-checked 2026-03-28 — no new skills since last check (25 total commits, 105k stars)
- https://github.com/affaan-m/everything-claude-code — re-checked 2026-03-28 — v1.9.0 still latest, no new agriculture-relevant additions
- https://medium.com/@unicodeveloper/10-must-have-skills-for-claude-and-any-coding-agent-in-2026-b5451b013051 — 10 Must-Have Skills for Claude 2026 — noted 2026-03-28 — general skills overview, no novel patterns
- https://github.com/shanraisshan/claude-code-best-practice — Claude Code best practice CLAUDE.md examples — noted 2026-03-28 — community reference
- https://www.openaitoolshub.org/en/blog/best-claude-code-skills-2026 — 349 Agent Skills Ranked by GitHub Stars — noted 2026-03-28 — find-skills (418K), vercel-react (176K), web-design (137K) top 3

## Session #133 Sources — 2026-03-29

- https://arxiv.org/abs/2603.09023 — The Missing Memory Hierarchy: Demand Paging for LLM Context Windows (Pichay) — read 2026-03-29 — implemented (21.8% structural waste metric, evict-by-staleness rule, graduated degradation added to PROMPT.md sawtooth section)
- https://arxiv.org/abs/2603.21278 — Conversation Tree Architecture: Context-Aware Multi-Branch Conversations — read 2026-03-29 — implemented (logical context poisoning failure mode #13 added to agent-patterns.md)
- https://arxiv.org/abs/2603.04814 — Beyond the Context Window: Fact-Based Memory vs Long-Context LLMs — read 2026-03-29 — noted (break-even at ~10 turns for memory system; validates knowledge.md approach for long sessions)
- https://arxiv.org/abs/2603.23443 — Evaluating LLM-Based Test Generation Under Software Evolution — read 2026-03-29 — implemented (test resilience rules added to testing.md: 66% pass rate drop on code changes, prefer behavioral assertions)
- https://arxiv.org/abs/2603.23448 — c-CRAB: Code Review Agent Benchmark — read 2026-03-29 — noted (agents solve ~40% of review tasks; complementary to human review rather than replacement)
- https://arxiv.org/abs/2603.21362 — AdaRubric: Task-Adaptive Rubrics for LLM Agent Evaluation — read 2026-03-29 — implemented (dimension-isolated scoring rule added to PROMPT.md Step 0; DimensionAwareFilter prevents masking failures)
- https://code.claude.com/docs/en/changelog — Claude Code v2.1.83-2.1.86 changelog — re-checked 2026-03-29 — noted (conditional hooks with `if` field, `initialPrompt` for agents, Read tool deduplicates re-reads, CwdChanged/FileChanged hooks, PowerShell tool, transcript search)
- https://github.com/anthropics/skills — re-checked 2026-03-29 — no new skills since March 22 check (25 commits, 105k stars)
- https://sustainableatlas.org/post/trend-analysis-soil-carbon-mrv-incentives-where-the-value-pools-are-and-who-captures-them-644 — Soil Carbon MRV Trend Analysis — noted 2026-03-29 — $2.3B investment in digital MRV, satellite verification costs down 40%
- https://www.seqana.com/ — Seqana: SOC sequestration for agrifood corporations — noted 2026-03-29 — competitor reference for MRV insetting
- https://farmonaut.com/precision-farming/precision-agriculture-with-drones-2026-game-changer — Precision Ag Drones 2026 — noted 2026-03-29 — drone costs expected down 20-30% in 2026, $7B global market

## Search Terms — Session #133

- "arxiv LLM autonomous coding agent new papers 2026 march april techniques" — searched 2026-03-29
- "Claude Code new features changelog march april 2026" — searched 2026-03-29
- "precision agriculture AI regenerative small farms Mexico drone 2026 new" — searched 2026-03-29
- "arxiv agent tool use self-correction structured output 2026 new papers april" — searched 2026-03-29
- "arxiv 2604 2603 LLM coding agent test generation debugging self-repair 2026" — searched 2026-03-29
- "FODECIJAL COECYTJAL 2026 convocatoria resultados innovacion tecnologica Jalisco abril" — searched 2026-03-29
- "FastAPI production patterns 2026 best practices async middleware new" — searched 2026-03-29
- "arxiv 2603 2604 LLM agent context window exhaustion recovery long session checkpoint 2026" — searched 2026-03-29
- "regenerative agriculture soil carbon digital MRV Mexico LATAM 2026 new startup platform" — searched 2026-03-29
- "arxiv 2603 2604 LLM agent task decomposition step verification autonomous coding 2026 new" — searched 2026-03-29

## Session #117 Sources — 2026-03-28

- https://arxiv.org/html/2602.20478v1 — Codified Context: Infrastructure for AI Agents in Complex Codebases — read 2026-03-28 — implemented (file-pattern trigger table concept added to INDEX.md for automatic skill routing; validated three-tier knowledge architecture already in place)
- https://arxiv.org/html/2510.21413v1 — Context Engineering for AI Agents in Open-Source Software — read 2026-03-28 — noted (15 info categories for AGENTS.md files, 5 writing styles; validates our CLAUDE.md/PROJECT.md approach; only 5% of repos adopt AI config files)
- https://arxiv.org/html/2505.18135v2 — Tool Preferences in Agentic LLMs are Unreliable — read 2026-03-28 — noted (assertive cues yield 7x tool usage bias, combined manipulations 11x; tool selection driven by surface text not reasoning; not actionable for our harness)
- https://arxiv.org/html/2603.21520 — MemAPO: Generalizable Self-Evolving Memory for Automatic Prompt Optimization — read 2026-03-28 — noted (dual-memory: correct-template + error-pattern; error patterns retrieved globally, strategies by similarity; validates our knowledge.md RULE + SKILL approach)
- https://arxiv.org/html/2510.07841v1 — Self-Improving LLM Agents at Test-Time — read 2026-03-28 — noted (LoRA fine-tuning at inference, +5.48% accuracy, 68x fewer samples; requires model access, not applicable to file-based harness)
- https://arxiv.org/abs/2510.24358 — PRDBench: Automatically Benchmarking LLM Code Agents — read 2026-03-28 — noted (PRD-based evaluation, specialized judges outperform general LLMs, 90%+ human alignment; interesting but not actionable)
- https://arxiv.org/html/2512.10114 — AgriRegion: Region-Aware Retrieval for High-Fidelity Agricultural Advice — read 2026-03-28 — backlogged (geospatial metadata injection + region-prioritized re-ranking; added task #27 for multi-region recommendations + reference in knowledge.md)
- https://arxiv.org/html/2508.08632v1 — AgriGPT: A Large Language Model Ecosystem for Agriculture — read 2026-03-28 — noted (Tri-RAG: dense + sparse + knowledge graph reasoning; reference for future WhatsApp RAG pipeline; added to knowledge.md)
- https://arxiv.org/html/2503.04788 — AgroLLM: Connecting Farmers through LLMs — noted 2026-03-28 — FAISS vector DB for agricultural RAG, open-source reference
- https://www.weforum.org/stories/2026/01/ai-in-global-agriculture/ — WEF 3 Strategic Pillars for AI in Agriculture — read 2026-03-28 — 403 error, could not fetch content
- https://www.weforum.org/stories/2026/01/ai-agricultural-intelligence-revolutionize-farming/ — WEF Agricultural Intelligence 2026 — noted 2026-03-28 — AI ag projected $4.7B by 2028, digital ag +$450B GDP in LMICs, 21% yield increase + 9% pesticide reduction in Telangana India trial
- https://github.com/anthropics/claude-code/releases — re-checked 2026-03-28 — no new releases after v2.1.86 (March 27, 2026)

## Search Terms — Session #117

- "arxiv LLM autonomous coding agent new techniques 2026 april papers" — searched 2026-03-28
- "Claude Code new features changelog april 2026" — searched 2026-03-28
- "precision agriculture AI regenerative farming FODECIJAL Mexico grant 2026 new" — searched 2026-03-28
- "arxiv LLM agent structured reasoning tool use reliability 2604 2026 new papers" — searched 2026-03-28

## Session #125 Sources — 2026-03-28 (DEEP BRAIN+META)

- https://arxiv.org/html/2508.21433v1 — The Complexity Trap: Simple Observation Masking ≈ LLM Summarization for Agent Context — read 2026-03-28 — implemented (empirical validation of M=10 observation masking added to agent-patterns.md; trajectory elongation warning for LLM summarization; 54.8% solve rate at 52.7% cost reduction)
- https://arxiv.org/html/2603.04257v1 — Memex(RL): Indexed Experience Memory for Long-Horizon Agents — read 2026-03-28 — noted (dual-storage: compact working context + external archive with index pointers; 24.2→85.6% on long tasks, 43% context reduction; validates current_task.md checkpoint approach)
- https://arxiv.org/html/2512.21354 — Reflection-Driven Control for Trustworthy Code Agents — read 2026-03-28 — implemented (single-round reflection rule added to agent-patterns.md; 90% of repair value captured in first cycle; lightweight binary check before deep reflection)
- https://arxiv.org/abs/2504.19678 — From LLM Reasoning to Autonomous AI Agents: Comprehensive Review (updated Mar 2026) — noted 2026-03-28 — general survey, 60 benchmarks covered, no new actionable techniques beyond what's already implemented
- https://arxiv.org/abs/2512.10398 — Confucius Code Agent: 59% SWE-Bench-Pro via persistent note-taking + modular tools — noted 2026-03-28 — AX/UX/DX separation interesting but abstract from summary; persistent note-taking validates our current_task.md approach
- https://l.coecytjal.org.mx/convocatorias — COECyTJAL FODECIJAL + PROPIN 2026 convocatorias — read 2026-03-28 — implemented (PROPIN IP fund discovery added to knowledge.md for Seb's IP registration)
- https://farmonaut.com/precision-farming/mexicos-precision-agriculture-revolution-inspired-by-farmonauts-success — Mexico AEM + UAEMEX satellite precision ag pilot — noted 2026-03-28 — competitor reference (satellite-based, not drone)

- https://github.com/anthropics/skills — re-checked 2026-03-28 — new: prompt-caching.md reference guide (Mar 25), updated claude-api skill across all languages + Agent SDK docs. Useful for future Claude API integration.
- https://github.com/affaan-m/everything-claude-code — re-checked 2026-03-28 — v1.9.0 still latest (Mar 21). New skills: codebase-onboarding, architecture-decision-records, agent-eval. SQLite state store + MCP health-check hook added. No agriculture-specific skills.
- https://github.com/anthropics/anthropic-cookbook — re-checked 2026-03-28 — NEW: knowledge graph construction cookbook (Mar 27) using structured outputs (SDK >= 0.77.0). Entity/relation extraction for building knowledge graphs with Claude. Highly relevant for Cerebro crop-disease-treatment knowledge graph.
- https://github.com/anthropics/courses — re-checked 2026-03-28 — dormant since Nov 2025, no new content.

## Search Terms — Session #125

- "arxiv LLM autonomous agent best practices reliability 2026 new papers" — searched 2026-03-28
- "arxiv AI coding agent context management tool use optimization 2026" — searched 2026-03-28
- "precision agriculture AI platform small farms Mexico regenerative 2026" — searched 2026-03-28
- "Claude Code new features changelog march 2026" — searched 2026-03-28
- "arxiv LLM agent tool result summarization compression reduce context 2026" — searched 2026-03-28
- "arxiv agent self-correction reflection memory retrieval coding 2026 new" — searched 2026-03-28
- "FODECIJAL COECYTJAL 2026 convocatoria resultados innovacion Jalisco mayo" — searched 2026-03-28
- "arxiv 2604 LLM coding agent test generation self-repair context management 2026 new" — searched 2026-03-28
- "site:github.com anthropics/claude-code releases 2026 april" — searched 2026-03-28
- "WEF agricultural intelligence AI 2026 regenerative farming small farms developing countries" — searched 2026-03-28
- "arxiv LLM agent prompt self-optimization automated prompt improvement 2026 new papers" — searched 2026-03-28
- "arxiv LLM agent knowledge base retrieval augmented generation agriculture soil crop recommendation 2026" — searched 2026-03-28

## Search Terms — Session #100

- "arxiv autonomous AI coding agent reliability techniques 2026 march new papers" — searched 2026-03-28
- "arxiv LLM agent tool use planning error recovery 2026 new papers march" — searched 2026-03-28
- "Claude Code best practices agent skills 2026 march april new" — searched 2026-03-28
- "precision agriculture AI regenerative farming small farms Mexico FODECIJAL 2026" — searched 2026-03-28
- "arxiv agent structured error semantics tool budgeting MCP production deployment 2026" — searched 2026-03-28
- "arxiv LLM agent adaptive tool budget allocation timeout management 2026" — searched 2026-03-28
- "ICL Group agriculture 2026 AI ROI resilience regenerative farming data" — searched 2026-03-28
- "site:github.com affaan-m everything-claude-code new skills april 2026" — searched 2026-03-28
- "arxiv 2604 LLM agent structured output reliability tool calling improvements 2026 april" — searched 2026-03-28
- "WhatsApp Business API agriculture chatbot voice message farmer small farms 2026 new implementation" — searched 2026-03-28
- "arxiv agentic AI coding agent prompt engineering self-improvement 2026 april new papers" — searched 2026-03-28
- "arxiv LLM agent task decomposition error recovery new techniques 2026 march april papers" — searched 2026-03-28

## Session #91 Sources — 2026-03-28 (DEEP BRAIN)

- https://arxiv.org/abs/2603.03329 — AutoHarness: Improving LLM Agents by Synthesizing Code Harness (Google/Kevin Murphy, ICLR'26 ws) — read 2026-03-28 — noted (generate→test→feedback→refine loop for constraint enforcement harness, smaller model beats larger with guardrails. Pattern already covered by our TDD + audit.md approach)
- https://arxiv.org/abs/2602.22302 — Agent Behavioral Contracts: Formal Specification and Runtime Enforcement — read 2026-03-28 — implemented (P,I,G,R framework → session invariants pattern added to PROMPT.md. Key insight: behavioral drift D* = α/γ, invariant checks are the recovery mechanism γ)
- https://arxiv.org/abs/2503.18666 — AgentSpec: Customizable Runtime Enforcement for Safe LLM Agents (ICSE'26) — read 2026-03-28 — noted (trigger-predicate-enforcement DSL, 95.56% precision for risk identification, 90%+ unsafe execution prevention. Already covered by audit.md checklist)
- https://arxiv.org/abs/2601.12538 — Agentic Reasoning for Large Language Models: Survey — read 2026-03-28 — noted (3-layer framework: foundational/self-evolving/collective reasoning. General survey, no actionable rules beyond what we already have)
- https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md — re-checked 2026-03-28 — no new releases after v2.1.86 (March 27)
- https://github.com/affaan-m/everything-claude-code/releases — re-checked 2026-03-28 — no releases after v1.9.0 (March 21)
- https://theyucatantimes.com/2026/03/world-water-day-ai-and-precision-agriculture-can-improve-water-efficiency/ — read 2026-03-28 — implemented (CARLOTA 700 devices / 25,820 ha / 18.7M m³ saved, CONAGUA precision ag messaging → knowledge.md FODECIJAL narrative)
- https://www.cropway.com/the-future-of-farming-2025/ — read 2026-03-28 — noted (WhatsApp/SMS advisories for smallholders, carbon & regenerative tools, subscription models for affordability — validates cultivOS approach)
- https://mexiconewsdaily.com/business/is-mexicos-agricultural-sector-experiencing-a-water-crisis/ — read 2026-03-28 — implemented (115/653 Mexican aquifers overexploited → knowledge.md water crisis data)

## Search Terms — Session #91

- "arxiv LLM autonomous coding agent new techniques papers 2026 march april" — searched 2026-03-28
- "Claude Code new features changelog april 2026" — searched 2026-03-28
- "precision agriculture AI drone WhatsApp small farms Mexico regenerative 2026 new platforms" — searched 2026-03-28
- "arxiv LLM agent memory reasoning self-correction new papers 2026 april" — searched 2026-03-28
- "arxiv 2603 2604 AutoHarness LLM agent code harness synthesis feedback 2026" — searched 2026-03-28
- "arxiv agentic reasoning 2601.12538 LLM agent plan act learn 2026" — searched 2026-03-28
- "site:github.com anthropics/claude-code releases 2026 march" — searched 2026-03-28
- "FODECIJAL COECYTJAL 2026 convocatoria resultados innovacion tecnologica Jalisco agriculture" — searched 2026-03-28
- "arxiv 2604 LLM coding agent test-driven development error recovery verification 2026 new papers" — searched 2026-03-28
- "site:github.com affaan-m everything-claude-code new skills updates march april 2026" — searched 2026-03-28
- "regenerative agriculture AI platform Mexico LATAM CONAGUA drought water efficiency 2026" — searched 2026-03-28
- "arxiv 2604 LLM agent structured output tool use guardrails constraint enforcement 2026" — searched 2026-03-28
- "arxiv 2603 2604 LLM agent context window efficiency token reduction coding 2026 new" — searched 2026-03-28

## Session #244 Sources — 2026-04-08

- https://arxiv.org/abs/2604.01212 — YC-Bench: Benchmarking AI Agents for Long-Term Planning and Consistent Execution — read 2026-04-08 — implemented (reasoning-execution gap invariant #4 added to PROMPT.md; checkpoint density target 5-11 per 100 calls; 47% bankruptcy rate from plan-action misalignment)
- https://arxiv.org/abs/2604.00835 — Agentic Tool Use in Large Language Models (survey) — read 2026-04-08 — implemented (tool necessity gate added to PROMPT.md; "more tool use is always beneficial" is empirically false; hierarchical retrieval pattern noted)
- https://arxiv.org/abs/2604.02688 — MatClaw: Autonomous Code-First LLM Agent for Materials Exploration — read 2026-04-08 — noted (four-layer memory architecture, ~99% per-step API accuracy; abstract only — full paper needed for implementation details)
- https://arxiv.org/html/2603.09716 — AutoAgent: Evolving Cognition and Elastic Memory Orchestration — read 2026-04-08 — noted (dual representation raw+compressed, episode clustering, composite action synthesis; validates our sawtooth compression approach)
- https://arxiv.org/abs/2604.00824 — SWE-Lego: Yet Even Less Is Even Better for Agentic Coding LLMs — read 2026-04-08 — noted (step-level error masking excludes erroneous tokens from loss; curriculum learning; training-time technique not actionable for file-based harness)
- https://arxiv.org/abs/2604.05289 — FLARE: Coverage-Guided Fuzzing for LLM-Based Multi-Agent Systems — noted 2026-04-08 — (multi-agent infinite loop detection; not actionable for single-agent harness)
- https://code.claude.com/docs/en/changelog — Claude Code v2.1.89-97 (April 1-8, 2026) — read 2026-04-08 — noted (default effort now "high", MCP 500K limit, subagent worktree isolation fixes, 60% faster diffs, compaction fixes for duplicate transcripts, Focus view toggle Ctrl+O)
- https://github.com/anthropics/skills/commits/main/ — re-checked 2026-04-08 — one commit: updated claude-api skill with Managed Agents guidance (#891). No new agriculture-specific skills.
- https://agriculture.fjdynamics.com/blog/dealer-voice-26/ — FJDynamics/RH TECH Mexico smart farming partnership — noted 2026-04-08 — competitor reference (hardware-focused, corporate-scale)
- https://online.ucpress.edu/elementa/article/13/1/00121/209710/ — Yucatec Maya Indigenous knowledge approach to agroecology — noted 2026-04-08 — validates cultivOS ancestral knowledge approach (intercultural knowledge co-creation)
- https://foodtank.com/news/2026/01/indigenous-wisdom-offers-path-forward-for-global-food-systems-reform/ — Food Tank: Indigenous Wisdom for Food Systems Reform — noted 2026-04-08 — Heifer International "Milpa for Life" supporting Yucatán smallholders
- https://www.cimmyt.org/news/from-the-amazon-to-mesoamerica-women-science-and-policy-are-shaping-resilient-agri-food-systems-in-latin-america/ — CIMMYT: Women shaping resilient agri-food systems in LATAM — noted 2026-04-08 — reference for FODECIJAL gender equity narrative

## Search Terms — Session #244

- "arxiv LLM autonomous coding agent new techniques papers April 2026" — searched 2026-04-08
- "Claude Code new features changelog april 2026" — searched 2026-04-08
- "precision agriculture AI regenerative farming Mexico FODECIJAL 2026 new" — searched 2026-04-08
- "arxiv agent self-improvement memory context management 2026 april new papers" — searched 2026-04-08
- "arxiv 2604 LLM coding agent error recovery planning tool use April 2026 new papers" — searched 2026-04-08
- "site:github.com anthropics/skills commits 2026 april new" — searched 2026-04-08
- "regenerative agriculture AI indigenous knowledge TEK Mexico LATAM 2026 new research" — searched 2026-04-08

## Session #245 Sources — 2026-04-08

- https://collapse.md/ — COLLAPSE.md: AI Agent Context Collapse Prevention specification — read 2026-04-08 — implemented (85% collapse threshold + 20% repetition signal added to agent-patterns.md context management)
- https://arxiv.org/html/2604.03515v1 — Inside the Scaffold: Source-Code Taxonomy of Coding Agent Architectures — read 2026-04-08 — implemented (failure trajectory elongation pattern #14 in agent-patterns.md, test-gating-per-step rule in PROMPT.md; key findings: failing attempts 4× resources, 12-82% longer trajectories, prompt interventions max 2.6pp impact vs scaffold control)
- https://arxiv.org/html/2604.03253 — Self-Execution Simulation Improves Coding Models — read 2026-04-08 — skipped (training-time technique, 43% output prediction improvement, not actionable at inference time)
- https://arxiv.org/html/2604.00835 — Agentic Tool Use in Large Language Models survey — read 2026-04-08 — noted (skills as practical abstraction over end-to-end autonomy, validates our skill library approach)
- https://arxiv.org/html/2604.01212 — YCBench: Long-Term Planning and Consistent Execution — noted 2026-04-08 — already implemented in session #244 (reasoning-execution gap)
- https://arxiv.org/html/2604.00594 — Agent Psychometrics: Task-Level Performance Prediction — noted 2026-04-08 — benchmark for predicting agent success, not directly actionable
- https://arxiv.org/abs/2604.02688 — MatClaw: Autonomous Code-First Agent with four-layer memory — noted 2026-04-08 — interesting HPC workflow agent, validates retrieval-augmented generation for API accuracy
- https://code.claude.com/docs/en/changelog — Claude Code v2.1.90-2.1.97 April 2026 — read 2026-04-08 — noted (autocompact circuit breaker, nested CLAUDE.md dedup, Edit tool shorter anchors, 429 exponential backoff, MCP 500K results, defer hook permission, session stability fixes)
- https://releasebot.io/updates/anthropic/claude-code — Claude Code April 2026 release notes — read 2026-04-08 — noted (same as changelog above)
- https://github.com/VoltAgent/awesome-ai-agent-papers — re-checked 2026-04-08 — no April 2026 papers visible in truncated view

## Search Terms — Session #245

- "arxiv LLM autonomous coding agent new papers 2026 april reliability self-correction" — searched 2026-04-08
- "Claude Code new features changelog april 2026" — searched 2026-04-08
- "regenerative agriculture AI platform Mexico small farms 2026 new" — searched 2026-04-08
- "arxiv agent context exhaustion crash recovery checkpoint 2026 new papers" — searched 2026-04-08
- "arxiv 2604 LLM coding agent tool use planning verification 2026 april new" — searched 2026-04-08
- "FODECIJAL COECYTJAL 2026 convocatoria resultados innovacion tecnologica abril mayo" — searched 2026-04-08

## Session #260 Sources — 2026-04-10 (DEEP BRAIN)

- https://arxiv.org/abs/2604.07236 — How Much LLM Does a Self-Revising Agent Actually Need? — read 2026-04-10 — noted (sparse LLM revision ~4.3% of steps, explicit world-model planning +24.1pp win rate. Key insight: most agent capability comes from structured planning, not continuous LLM processing. Not directly actionable for file-based harness)
- https://arxiv.org/html/2604.07487 — CLEAR: Context Augmentation from Contrastive Learning of Experience — read 2026-04-10 — skipped (81% vs 73% task completion by training CAM model on successful/failed trajectory pairs; requires executable reward environment, not applicable to file-based harness)
- https://arxiv.org/abs/2604.05100 — Edit, But Verify: Empirical Audit of Instructed Code-Editing Benchmarks — read 2026-04-10 — implemented (fail-before/pass-after validation rule added to testing.md; fail-before explicitly verifies tests FAIL before implementation)
- https://arxiv.org/html/2604.04226 — Agentization of Digital Assets: Hallucinated APIs and Signature Mismatch — read 2026-04-10 — implemented (100% failure rate from type/signature mismatch validates spec formula alignment rule added to PROMPT.md WHEN BUILDING A FEATURE)
- https://code.claude.com/docs/en/changelog — Claude Code v2.1.98-101 (April 9-10, 2026) — read 2026-04-10 — noted (Monitor tool for streaming background events, Vertex AI setup wizard, subprocess sandboxing, `--exclude-dynamic-system-prompt-sections` for prompt caching, fixed `--resume` losing context on large sessions, fixed stalled streaming responses)
- https://github.com/anthropics/skills/commits/main/ — re-checked 2026-04-10 — noted (Apr 9: added proper front-matter to claude-api SKILL.md. No new skill files added in April 2026)
- https://github.com/anthropics/anthropic-cookbook/commits/main/ — re-checked 2026-04-10 — noted (Apr 8: Claude Managed Agents Cookbooks — 9 notebooks: data_analyst_agent, slack_data_bot, sre_incident_responder, CMA_iterate_fix_failing_tests, CMA_orchestrate_issue_to_pr, CMA_explore_unfamiliar_codebase, CMA_gate_human_in_the_loop, CMA_prompt_versioning_and_rollback, CMA_operate_in_production. anthropic>=0.91.0 required)
- https://raw.githubusercontent.com/anthropics/skills/main/skills/claude-api/SKILL.md — fetched 2026-04-10 — implemented (Managed Agents Beta tier + Compaction section added to autoagent/skills/claude_api.md; adaptive thinking + effort parameter already present; fixed stale StockCards project reference)
- https://github.com/affaan-m/everything-claude-code/commits — re-checked 2026-04-10 — noted (ECC2 new features: decision log audit trail, agent profiles, conflict resolution protocol, hunk-level git patch actions, webhook notifications, layered TOML config. All ECC2 — not yet released in installable form)
- https://www.gsma.com/solutions-and-impact/connectivity-for-good/mobile-for-development/mobile-for-development-2/agronomic-advisory-enhanced-by-ai-insights-from-farmerline/ — Farmerline Darli AI UX patterns — noted 2026-04-10 — confirms IVR + local language translate-process-translate-back pattern, 110K farmers, 27 languages. Already captured in knowledge.md Farmer.Chat section.

## Search Terms — Session #260

- "arxiv LLM autonomous coding agent new papers April 9 10 2026 reliability self-correction" — searched 2026-04-10
- "Claude Code changelog new features April 2026 v2.1.98 v2.1.99" — searched 2026-04-10
- "arxiv 2604 LLM agent planning verification tool use April 2026 new papers" — searched 2026-04-10
- "regenerative agriculture AI voice WhatsApp low-literacy farmer interface UX 2026" — searched 2026-04-10
- "FastAPI production best practices async SQLAlchemy 2026 new patterns" — searched 2026-04-10
- "arxiv 2604 LLM coding agent spec-following implementation accuracy scoring April 9 10 2026" — searched 2026-04-10
- "site:github.com anthropics/skills commits April 2026 new skill" — searched 2026-04-10
- "Darli AI OR Farmerline regenerative agriculture voice chatbot UX low-literacy 2026 implementation" — searched 2026-04-10
- "site:github.com affaan-m everything-claude-code commits April 2026 new skills" — searched 2026-04-10
- "arxiv 2604 agentic coding agent spec compliance formula verification implementation mismatch 2026" — searched 2026-04-10

## Search Terms — Session #43

- "autonomous AI coding agent best practices reliability 2026 arxiv new papers march april" — searched 2026-03-27
- "precision agriculture AI soil carbon MRV WhatsApp small farms Mexico 2026" — searched 2026-03-27
- "Claude Code agent skills SKILL.md github new 2026 march april" — searched 2026-03-27
- "FastAPI production patterns background tasks websocket 2026 best practices" — searched 2026-03-27
- "arxiv 2603 LLM agent coding software engineering tool planning memory 2026" — searched 2026-03-27
- "WhatsApp Business API agriculture chatbot farmer voice message small farms 2026" — searched 2026-03-27
- "agtech trends 2026 AI agents carbon farming soil health digital MRV" — searched 2026-03-27
- "everything-claude-code github new skills updates march 2026" — searched 2026-03-27
