# Agnostic Council — Agency stack (A) vs Claude Design (B)

**Date:** 2026-06-18  ·  **Confidence:** HIGH  ·  **Winner voice:** Codex

**Panel:** Codex/gpt-5.5, Gemini, DeepSeek, Grok (no ANTHROPIC_API_KEY → Claude slot routed to Gemini; Claude own-view absent).

**Ranking:** Codex > Gemini > Claude > DeepSeek > Grok

## Synthesis

**Chairman's Recommendation**

The council's consensus is clear and correct: these are sequential, not competing, approaches. Approach A must lead all production builds, establishing the source of truth for code. Approach B should be adopted immediately as a powerful tool for rapid, brand-safe ideation and stakeholder alignment.

**Rationale & Criterion Winners:**

Approach A is the production engine. It wins on **(1) Design Quality** and **(5) Code Maintainability** due to its human-led, anti-slop process and committed component code. This signals premium craftsmanship to clients.

Approach B is the commercial accelerator. It wins on **(2) Brand Fidelity**, **(3) Drift Prevention**, **(4) Speed**, and **(6) Stakeholder Deliverables**. Its ability to import real brand components and self-check its output on a visual canvas is invaluable for quickly generating on-brand mockups and pitch decks, preventing costly rework before engineering begins. **(7) Cost** and **(8) Maturity** are split: B is cheaper for initial artifacts but carries beta risk; A is more expensive upfront but avoids the long-term cost of technical debt.

**Coexistence & Conditions:**

The two must coexist in a strict workflow: B is for origination, A is for production.

1.  **B Leads Ideation:** Use Claude Design (B) for initial client workshops, rapid prototyping, and generating sales collateral (PDF/PPTX). Its self-check mechanism enforces brand consistency at the cheapest stage.
2.  **A Leads Production:** The output from B is a high-fidelity spec, not final code. The code-first stack (A) takes this spec and executes the production-grade, maintainable frontend. The human designer's taste and council review remain the final gate for quality.
3.  **Mitigate Beta Risk:** The "bidirectional sync" is a critical risk. Treat it as a one-way handoff from B to A. Pilot B on 2-3 small projects, manually diffing its code output to measure quality and rework hours before trusting it further.

Confidence: HIGH

## Stage-1 perspectives

### Claude (claude)

**Bull Case:**
Leveraging both approaches creates a powerful pipeline. Approach A delivers unparalleled premium, bespoke code and design quality, essential for high-value clients and complex interactions. Approach B offers incredible speed for initial concepts, stakeholder alignment, and robust design system consistency, reducing early-stage costs and preventing brand drift across many clients.

**Bear Case:**
Approach A's bespoke nature can be slower and more expensive for early iterations. Approach B, being beta, carries significant execution risk regarding its "production code" quality via Claude Code sync and its ability to truly achieve "bold aesthetic execution" without human design compromise. Over-reliance on B could lead to homogenized "AI-slop" if not carefully managed.

**Design / Trust:**
Approach A signals premium, bespoke craftsmanship ("anti-AI-slop," "human designer's taste"), building high trust with discerning buyers. Approach B, while efficient, risks being perceived as generic or template-driven due to its visual tool nature and beta status, potentially eroding the premium brand signal if not carefully positioned.

**Pragmatic Read:**
Approach B is a potent tool for rapid ideation, visual prototyping, and ensuring initial design system adherence and brand fidelity. It excels at client presentations. Approach A is the ultimate production engine, delivering the final, high-fidelity, custom-coded frontend with complex interactions and a unique aesthetic.

**Decision:**
CLOSE BUT FIX THESE FIRST.
1.  **Validate B's Code Output:** Rigorously test Claude Design's bidirectional sync with Claude Code to ensure the generated code is production-grade, maintainable, and truly "anti-AI-slop" for the agency's specific frameworks.
2.  **Define Human Oversight:** Establish clear guidelines for human designers to inject "bold aesthetic execution" and taste into B's output, preventing generic visuals.
3.  **Pilot Project:** Implement B on a non-critical internal project or a low-risk client to fully understand its limitations and integration challenges before full client deployment.

**Coexistence:** Human designers lead with Claude Design (B) for rapid wireframing, concept validation, and client presentations, leveraging its speed and consistency checks. Once visual direction is locked, the project transitions to the Claude Code-driven stack (A) for final, high-fidelity, custom-coded production and complex interactions, ensuring premium quality and maintainability.

### Codex (openai)

Bull Case:
A wins produced-product design quality and code integration/maintainability: it creates committed component code, can use Framer Motion/21st.dev selectively, and has human taste plus council review to suppress AI-slop. It is the stronger lead for the mature FastAPI/~87-page rebuild.

B wins speed to first usable artifact, stakeholder deliverables, design-system consistency/drift prevention, and often brand fidelity when each client’s real tokens/components are imported. Canvas editing + self-check + PDF/PPTX export is commercially useful for pitches, reviews, and alignment before engineering spend.

Bear Case:
A can homogenize brands if ui-ux-pro-max becomes the “house look.” Exact fix: require per-brand token extraction, competitor/brand audit, typography lock, motion rules, and “forbidden patterns” before generation.  
B is beta and largely unproven here. Risk: impressive canvas, weak production edge cases, sync conflicts, or false confidence from “self-check.” Exact fix: pilot on 2–3 bounded flows, diff exported/synced code, measure token violations, accessibility, responsive behavior, and engineer rework hours.

Design / Trust:
Premium buyer signal: A currently has more trust for final shipped frontend craft. B has more trust for “show me the idea in my brand system now.”  
Criterion winners:  
1 Design quality: A.  
2 Brand fidelity across many brands: B, if systems are imported correctly.  
3 Drift prevention: B.  
4 Speed: B.  
5 Maintainability: A.  
6 Pitch decks: B.  
7 Cost: B for concept/decks; A for lifecycle production cost control.  
8 Maturity risk: A.

Pragmatic Read:
Do not replace A with B. Use B as the front-of-house visual ideation, stakeholder, and design-system validation layer. Use A as the production build lead, especially for complex apps, bespoke interactions, and long-term maintainability.

Decision:
Adopt coexistence: B leads discovery, pitches, layout exploration, and brand-system previews; A leads final implementation, refactors, motion, accessibility, and production hardening. For the mature app rebuild, A leads; B prototypes priority flows first. CLOSE BUT FIX THESE FIRST

### Gemini (gemini)

**Bull Case:**
Approach B is a commercial accelerator. It weaponizes our existing design systems, allowing faster, cheaper production of derivative pages and sales collateral (PDF/PPTX). It enforces brand fidelity via its self-check mechanism, de-risking work done by junior staff or in rapid-prototyping sprints. This lets us reserve the expensive, high-craft Approach A for establishing the core brand identity and hero components, while B handles scalable production.

**Bear Case:**
Approach B’s beta status is a major execution risk. "Bidirectional sync" is notoriously fragile; a single failed sync could corrupt a project, creating massive technical debt. It risks de-skilling our team into tool operators and creating vendor lock-in. If the self-check is too rigid, it stifles creative solutions; if it's too loose, it’s useless.

**Design / Trust:**
Approach A signals bespoke, code-native craftsmanship, which builds trust with sophisticated clients. Approach B signals speed, consistency, and safety—a different kind of trust. A premium buyer would trust A to *create* their brand's digital identity and B to *scale* it without breaking it. Using B for initial creative work would signal a lower-end, template-driven agency.

**Pragmatic Read:**
These are not competing workflows; they are sequential. A is for origination, B is for iteration. A’s code-first stack is the source of truth for creating and evolving a design system’s core DNA. B is a production tool for applying that DNA across dozens of pages or variants, with built-in guardrails. The FastAPI frontend rebuild is the perfect pilot for B.

**Decision:**
The two approaches must coexist. The code-first stack (A) leads, establishing the canonical design system and components. B is then used for rapid page assembly and stakeholder reviews. The primary risk is B’s sync reliability.

**CLOSE BUT FIX THESE FIRST:**
1.  Pilot Approach B on the internal FastAPI frontend rebuild to battle-test the bidirectional sync.
2.  Define a clear protocol for resolving sync conflicts before using B on any new client project.

### DeepSeek (deepseek)

**Bull Case:**  
A delivers superior design quality and brand fidelity—human taste beats AI slop for distinct identities. Mature, integrated code production.  
B wins on speed to artifact, stakeholder deliverables (PDF/PPTX), and cost (beta). Self-checking reduces drift.  

**Bear Case:**  
A is expensive, slower for prototypes, and drift-prone without automated enforcement.  
B is beta—unproven at scale, risks homogenizing brands, and its code sync is fragile.  

**Design / Trust:**  
A. Human-in-loop prevents “same-brand” feel. B’s AI could flatten uniqueness. For premium buyers, A’s output signals craft; B’s feels like a templated start.  

**Pragmatic Read:**  
Use B for rapid mockups, pitch decks, and design exploration—its speed and export are unmatched. Use A for production commits, maintaining brand soul, and integrating with existing codebases.  

**Decision:**  
**READY** if you treat B as a front-end sketch tool that feeds A. Lead with human designers on A; B supports pre-viz and stakeholder engagement. Do not let B generate final code for multiple brands until its drift-prevention is battle-tested.

### Grok (grok)

Bull Case: B wins (2)(3)(6) via self-checks against imported tokens and PDF/PPTX exports, preserving distinct brand palettes without homogenization. A wins (1)(5) with committed, reviewed components + Framer Motion that integrate directly into Next/React stacks. Bidirectional sync lets B hand off clean specs to A.

Bear Case: B's beta canvas risks token drift on complex 87-page rebuilds; A lacks native visual review, slowing non-technical stakeholders. B adds sync overhead; A incurs higher per-brand setup via ui-ux-pro-max.

Design / Trust: A delivers premium, anti-slop execution buyers notice; B's self-checks build internal trust on fidelity but feel less battle-tested.

Pragmatic Read: A leads builds; B reserved for brand-specific kickoffs and decks. Run token extractor into both.

Decision: CLOSE BUT FIX THESE FIRST (sync edge cases + beta guardrails).
