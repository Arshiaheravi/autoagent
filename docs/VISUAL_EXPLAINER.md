# AutoAgent Agency — Visual Explainer

Five diagrams that explain how AutoAgent works. All rendered via Mermaid — they display natively on GitHub, in Gamma, and in Notion. To export any diagram as PNG/SVG: copy the code block into [mermaid.live](https://mermaid.live) and click **Actions → PNG** or **SVG**.

---

## 1. The 4-Brain Council

When a decision matters, AutoAgent doesn't trust a single model. It asks four different AI systems from different labs, each with a different perspective, then a Chairman synthesizes the best answer.

```mermaid
flowchart TB
    Q["❓ Question<br/><i>'Should we deploy this migration?'</i>"]

    Q --> C1
    Q --> C2
    Q --> C3
    Q --> C4

    subgraph Brains["🧠 4-Brain Council"]
        direction LR
        C1["🟣 Claude<br/><b>The Bull</b><br/>Optimist · upside case"]
        C2["🟢 GPT-4o<br/><b>Codex</b><br/>Independent reviewer"]
        C3["🔵 Gemini<br/><b>The Architect</b><br/>Scalability · systems"]
        C4["🟠 DeepSeek<br/><b>The Debugger</b><br/>Edge cases · correctness"]
    end

    C1 --> R["🗳️ Peer Ranking<br/><i>Each brain ranks the others<br/>anonymously (A/B/C)</i>"]
    C2 --> R
    C3 --> R
    C4 --> R

    R --> CH["⚖️ <b>Chairman</b><br/>Claude synthesizes the<br/>best consensus answer"]

    CH --> A["✅ Decision<br/>+ confidence score<br/>+ dissent notes"]

    classDef brain fill:#f3e8ff,stroke:#7c3aed,stroke-width:2px,color:#1f2937
    classDef chairman fill:#fef3c7,stroke:#d97706,stroke-width:3px,color:#1f2937
    classDef io fill:#ecfdf5,stroke:#059669,stroke-width:2px,color:#1f2937
    class C1,C2,C3,C4 brain
    class CH chairman
    class Q,A,R io
```

**Why four, not one?** Different training data, different architectures, different blind spots. A bug Claude misses, DeepSeek often catches. A scalability concern Gemini flags, Codex validates. The Chairman sees all four answers *and* the peer rankings — then synthesizes.

---

## 2. The Orchestrator

The Orchestrator is the conductor. It picks what to work on next, routes it to the right specialist, and enforces the rules (tests first, commit atomically, no scope creep).

```mermaid
flowchart TB
    START([🚀 Session Start]) --> READ[📖 Read Project State]

    READ --> R1[PROJECT.md<br/>NORTH_STAR.md]
    READ --> R2[backlog.md<br/>activity_log.md]
    READ --> R3[knowledge.md<br/>current_task.md]

    R1 & R2 & R3 --> TYPE{Session<br/>Type?}

    TYPE -->|every run| WORK[🔨 WORK<br/>build features]
    TYPE -->|every 5th| META[🔁 META<br/>improve prompts]
    TYPE -->|every 10th| BRAIN[🌐 BRAIN<br/>research techniques]
    TYPE -->|every 20th| DEEP[⚡ DEEP<br/>meta + brain combined]

    WORK --> PICK[🎯 Pick Task by<br/>North Star Impact]
    PICK --> ROUTE{Which Agent?}

    ROUTE --> A1[👷 Backend]
    ROUTE --> A2[🎨 Frontend]
    ROUTE --> A3[🧪 Test Writer]
    ROUTE --> A4[🏗️ Architect]
    ROUTE --> A5[🔬 UX Researcher]
    ROUTE --> A6[📚 Domain Specialist]

    A1 & A2 & A3 & A4 & A5 & A6 --> GATES[🚪 Verification Gates]

    GATES --> G1{Tests<br/>Pass?}
    G1 -->|no| FIX[🔧 Fix]
    FIX --> G1
    G1 -->|yes| G2{Self-Critique<br/>OK?}
    G2 -->|no| FIX
    G2 -->|yes| G3{Constraints<br/>Met?}
    G3 -->|no| FIX
    G3 -->|yes| COMMIT[✅ Atomic Commit]

    COMMIT --> LOG[📝 Update Logs]
    LOG --> END([Session End])

    classDef work fill:#dbeafe,stroke:#2563eb,stroke-width:2px,color:#1f2937
    classDef meta fill:#fef3c7,stroke:#d97706,stroke-width:2px,color:#1f2937
    classDef gate fill:#fee2e2,stroke:#dc2626,stroke-width:2px,color:#1f2937
    classDef agent fill:#f3e8ff,stroke:#7c3aed,stroke-width:2px,color:#1f2937
    class WORK,PICK work
    class META,BRAIN,DEEP meta
    class GATES,G1,G2,G3,FIX gate
    class A1,A2,A3,A4,A5,A6 agent
```

**Core principle:** the Orchestrator never writes code itself. It reads state, chooses work, routes to specialists, and enforces gates. Separation of decision from execution.

---

## 3. The Agent Teams

Every project starts with 6 universal agents. Domain specialists are created during intake or on-demand. Each agent has its own system prompt, skills, and responsibilities.

```mermaid
flowchart LR
    O([🎼 Orchestrator])

    subgraph Universal["🌐 6 Universal Agents<br/><i>(ships with every project)</i>"]
        U1[🏗️ <b>Architect</b><br/>design decisions<br/>system layout]
        U2[🧪 <b>Test Writer</b><br/>TDD · coverage<br/>regression suites]
        U3[🎨 <b>Frontend</b><br/>UI · UX · visual<br/>accessibility]
        U4[⚙️ <b>Infra</b><br/>deploys · DBs<br/>CI/CD · env]
        U5[🔬 <b>UX Researcher</b><br/>user journeys<br/>error patterns]
        U6[📚 <b>Educator</b><br/>docs · READMEs<br/>onboarding]
    end

    subgraph Domain["🎯 Domain Specialists<br/><i>(generated per project)</i>"]
        D1[🌽 <b>Agronomist</b><br/><i>cultivOS</i>]
        D2[💰 <b>Fintech Analyst</b><br/><i>StockCards</i>]
        D3[🍽️ <b>Food Ops</b><br/><i>KitchenIntelligence</i>]
        D4[🧬 <b>…created on demand</b>]
    end

    O --> Universal
    O --> Domain

    Universal -.->|shared skill library| SK[📖 30+ Universal Skills<br/>testing · debugging · security<br/>playwright · PDF · canvas · API design]
    Domain -.->|domain skills| SK

    classDef orch fill:#fef3c7,stroke:#d97706,stroke-width:3px,color:#1f2937
    classDef universal fill:#dbeafe,stroke:#2563eb,stroke-width:2px,color:#1f2937
    classDef domain fill:#dcfce7,stroke:#16a34a,stroke-width:2px,color:#1f2937
    classDef skills fill:#f3e8ff,stroke:#7c3aed,stroke-width:2px,color:#1f2937
    class O orch
    class U1,U2,U3,U4,U5,U6 universal
    class D1,D2,D3,D4 domain
    class SK skills
```

**Backlog routing:** tasks tagged `[agent: test-writer]` route to the Test Writer; `[agent: agronomist]` routes to a domain specialist. The Orchestrator decides which agent sees the task based on tag, skill match, and history of success with similar work.

---

## 4. Self-Improving Loops

AutoAgent gets better at building software the longer it runs. Three loops operate at different timescales.

```mermaid
flowchart TB
    subgraph Fast["⚡ Fast Loop · every session"]
        direction LR
        F1[Pick Task] --> F2[Write Tests]
        F2 --> F3[Implement]
        F3 --> F4[Verify]
        F4 --> F5[Commit]
        F5 --> F6[Log Knowledge]
        F6 -.->|failures become rules| F1
    end

    subgraph Mid["🔁 Medium Loop · every 5th session (META)"]
        direction LR
        M1[Read last 5<br/>session failures] --> M2[Diagnose<br/>pattern]
        M2 --> M3[Edit PROMPT.md<br/>+ skill files]
        M3 --> M4[Commit<br/>prompt changes]
        M4 -.->|sharper agents| M1
    end

    subgraph Slow["🌐 Slow Loop · every 10th session (BRAIN)"]
        direction LR
        B1[Scan web for<br/>new techniques] --> B2[Select top<br/>3 findings]
        B2 --> B3[Download +<br/>implement]
        B3 --> B4[Add to<br/>skill library]
        B4 -.->|expanded capabilities| B1
    end

    Fast ==>|feeds failures into| Mid
    Mid ==>|informs research direction| Slow
    Slow ==>|new techniques ship to| Fast

    DEEP[["⭐ DEEP Session<br/>(every 20th)<br/>runs META + BRAIN together<br/>for compounding improvement"]]

    Mid -.-> DEEP
    Slow -.-> DEEP

    classDef fast fill:#dbeafe,stroke:#2563eb,stroke-width:2px,color:#1f2937
    classDef mid fill:#fef3c7,stroke:#d97706,stroke-width:2px,color:#1f2937
    classDef slow fill:#dcfce7,stroke:#16a34a,stroke-width:2px,color:#1f2937
    classDef deep fill:#f3e8ff,stroke:#7c3aed,stroke-width:3px,color:#1f2937
    class F1,F2,F3,F4,F5,F6 fast
    class M1,M2,M3,M4 mid
    class B1,B2,B3,B4 slow
    class DEEP deep
```

**Why it compounds:** the Fast Loop writes code and logs failures. The Medium Loop reads those failures and rewrites the prompts that caused them. The Slow Loop researches techniques humans are publishing *right now* and adds them to the skill library. Every loop feeds the next.

---

## 5. The Whole System

Everything together: idea in → working software out, autonomously, with compounding quality.

```mermaid
flowchart TB
    IDEA["💡 Idea<br/><i>'organic seed marketplace'</i>"]

    IDEA --> INTAKE["📋 Intake Interview<br/>Claude asks 8 questions<br/>→ PROJECT.md<br/>→ NORTH_STAR.md<br/>→ initial backlog"]

    INTAKE --> SETUP["⚙️ Setup<br/>Generate agent team<br/>Initialize memory<br/>Pick tech stack"]

    SETUP --> LOOP{{"🔁 Session Loop"}}

    LOOP --> ORCH["🎼 <b>Orchestrator</b><br/>reads state · picks task"]

    ORCH --> COUNCIL{"High-stakes<br/>decision?"}
    COUNCIL -->|yes| BRAINS["🧠 4-Brain Council<br/>Claude · GPT-4o · Gemini · DeepSeek<br/>→ synthesized answer"]
    COUNCIL -->|no| DIRECT[direct route]

    BRAINS --> AGENTS
    DIRECT --> AGENTS

    AGENTS["👥 <b>Agent Team</b><br/>Architect · Test Writer · Frontend<br/>Infra · UX · Domain Specialists"]

    AGENTS --> TDD["🧪 TDD Build<br/>Tests first → implement → verify"]

    TDD --> GATES{"🚪 Verification<br/>Gates"}
    GATES -->|fail| FIX[🔧 Fix]
    FIX --> GATES
    GATES -->|pass| SHIP["✅ Commit + Push<br/>Update dashboard"]

    SHIP --> IMPROVE{"Session<br/>multiple of 5?"}
    IMPROVE -->|yes| META["🔄 Self-improve<br/>META · BRAIN · DEEP"]
    IMPROVE -->|no| LOOP
    META --> LOOP

    SHIP -.-> DASH["📊 Live Dashboard<br/>tests · sparklines · spend"]
    SHIP -.-> SW["🚀 Working Software"]

    classDef input fill:#ecfdf5,stroke:#059669,stroke-width:2px,color:#1f2937
    classDef orchestrator fill:#fef3c7,stroke:#d97706,stroke-width:3px,color:#1f2937
    classDef brain fill:#f3e8ff,stroke:#7c3aed,stroke-width:2px,color:#1f2937
    classDef agents fill:#dbeafe,stroke:#2563eb,stroke-width:2px,color:#1f2937
    classDef gate fill:#fee2e2,stroke:#dc2626,stroke-width:2px,color:#1f2937
    classDef output fill:#dcfce7,stroke:#16a34a,stroke-width:3px,color:#1f2937
    class IDEA,INTAKE,SETUP input
    class ORCH,LOOP orchestrator
    class BRAINS,COUNCIL brain
    class AGENTS,TDD agents
    class GATES,FIX gate
    class SHIP,SW,DASH,META output
```

---

## How to Export as Images

**Option 1 — mermaid.live (fastest, no install)**
1. Go to https://mermaid.live
2. Paste any code block above into the editor (left panel)
3. Click **Actions → PNG** or **SVG** to download
4. The export is transparent-background, high-res, ready for slides

**Option 2 — Gamma (build the deck directly)**
1. Create a new Gamma deck
2. Paste the relevant sections of this markdown into the "import from text" flow
3. Gamma renders the mermaid code blocks as embedded diagrams
4. You can restyle with the AI designer

**Option 3 — mermaid-cli (local batch export)**
```bash
npm install -g @mermaid-js/mermaid-cli
mmdc -i docs/VISUAL_EXPLAINER.md -o docs/diagrams.png
```

**Option 4 — NotebookLM**
Upload this markdown file as a source. Generate an Audio Overview — the AI hosts will walk through all 5 concepts in podcast format.

---

## Narrative Summary (for voice-over / NotebookLM)

AutoAgent is a multi-agent AI development framework that takes an idea and autonomously builds working software. It has three distinct advantages over single-agent coding assistants.

First, **the Council**. High-stakes decisions route through four different AI models from four different labs — Claude, GPT-4o, Gemini, and DeepSeek. Each has a different training and different blind spots. They answer independently, peer-rank each other's answers anonymously, then a Chairman synthesizes the best response. This catches bugs a single model would miss.

Second, **specialized agents**. Every project ships with six universal agents — Architect, Test Writer, Frontend, Infra, UX Researcher, Educator — plus domain specialists generated during intake. An Orchestrator reads the project state, picks the highest-impact task, routes it to the right specialist, and enforces verification gates before any commit lands.

Third, **self-improvement**. Work sessions build features and log failures. Every fifth session, a Meta loop reads those failures and rewrites the prompts that caused them. Every tenth session, a Brain loop scans the web for new techniques and adds them to the skill library. The longer the system runs, the better it gets.

One human describes the goal, walks away, and comes back to working software with tests, commits, and a live dashboard showing what shipped.
