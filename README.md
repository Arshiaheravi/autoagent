# AutoAgent Agency

Autonomous AI development teams. Bring an idea, get working software.

AutoAgent takes project ideas — even half-baked — and builds them with specialized AI agent teams that run autonomously, improve their own prompts, and show progress through a live dashboard.

## What it does

```bash
autoagent intake "organic seed marketplace"   # Describe your idea
# → Claude interviews you (8 questions)
# → Generates PROJECT.md, NORTH_STAR.md, agent team, TDD backlog

autoagent run my-project --tasks 10           # Let it rip
# → Picks tasks, writes tests FIRST, implements, verifies, commits
# → META sessions improve prompts from failures
# → BRAIN sessions research new techniques

autoagent dashboard                           # Watch it build
# → Live dashboard at localhost:8080
# → Test counts climbing, endpoints going green, sparklines
```

## Install

```bash
git clone https://github.com/Arshiaheravi/autoagent.git
cd autoagent
pip install -e .          # installs the `autoagent` command
autoagent init            # first-time setup — scaffolds ~/.autoagent
```

That's it — `autoagent` is now on your PATH. (Prefer no pip install? Run
`python3 engine/init_agency.py` and add `export PATH="$HOME/.autoagent:$PATH"`
to your shell profile instead.)

Requires: Python 3.11+ and the [Claude Code CLI](https://claude.ai/code) with a
Claude subscription (the engine drives Claude Code to do the actual work).

### Optional features

Some capabilities are packaged as extras so the core install stays lean —
install one only if you use it:

```bash
pip install -e '.[vault]'      # encrypted per-tenant secret vault (cryptography)
pip install -e '.[postgres]'   # Postgres + pgvector council-memory backend
pip install -e '.[replicate]'  # read .docx design briefs in `autoagent replicate`
pip install -e '.[dev]'        # everything above + pytest (for contributors)
```

## Commands

| Command | What it does |
|---|---|
| `autoagent init` | First-time setup (~/.autoagent) |
| `autoagent intake "idea"` | New project from description |
| `autoagent run <project> --once` | Single session |
| `autoagent run <project> --tasks N` | N sessions |
| `autoagent run <project>` | Run forever (1min cooldown) |
| `autoagent run <project> --type meta` | Force session type |
| `autoagent run <project> --test` | Dry run |
| `autoagent list` | All projects + session counts |
| `autoagent status <project>` | Spend + recent activity |
| `autoagent cleanup <project>` | Engineering cleanup crew scan |
| `autoagent agent list <project>` | List agent team |
| `autoagent agent create <project> <name> "desc"` | Create agent from description |
| `autoagent dashboard` | Live dashboard (localhost:8080) |
| `autoagent org [--strict]` | Show departments, agents, skills, and loops |
| `autoagent db sync [project]` | Backfill sessions.json into agency.db for routing |
| `autoagent db audit` | Check DB hygiene and routing-confidence issues |
| `autoagent db dedupe-sessions [--apply]` | Collapse duplicate DB session rows |
| `autoagent register <name> <path>` | Register existing repo |
| `autoagent migrate <v1-dir>` | Import V1 project |

## How it works

**Session types** rotate automatically:
- **WORK** (default) — pick task, write tests first, implement, verify, commit
- **META** (every 5th) — read failure logs, improve prompts and skills
- **BRAIN** (every 10th) — research web for new techniques
- **DEEP** (every 20th) — combined META + BRAIN
- **AUDIT** (every 25th) — security review and risk backlog generation
- **KNOWLEDGE** (every 50th) — compile durable project knowledge

**Agent teams** per project:
- 14 universal agent templates ship by department: Engineering, Product and Design, Growth and Communications, Research and Intelligence
- Domain agents are generated during intake or created with `autoagent agent create`
- Backlog tasks tagged with `[agent: name]` route to the right specialist
- Project-domain skills are hidden from normal prompts unless they are project-local or explicitly enabled in project config
- `autoagent org --strict` audits the department roster and fails on missing templates, duplicate templates, or bad manifest references

**Self-improvement loop:**
1. Work sessions build features with TDD
2. Meta sessions read failures → improve prompts
3. Brain sessions research techniques from the web
4. Skills get sharper → sessions get better → code quality compounds

## Architecture

```
~/.autoagent/
├── engine/              # Core Python (cli, run, registry, intake, orchestrator, dashboard)
├── templates/           # Shared prompts, department manifest, universal agent templates
├── skills/              # Shared skill library with manifest-based scoping
└── projects/            # Per-project isolated state
    └── <project>/
        ├── PROJECT.md, NORTH_STAR.md
        ├── agents/      # Domain-specific agent definitions
        ├── skills/      # Domain-specific skills
        ├── memory/      # Backlog, activity log, knowledge
        └── sessions.json
```

## Tests

```bash
pip install -e '.[dev]'          # test deps
python3 -m pytest engine -q      # ~1,200 unit tests (what CI runs)
python3 -m pytest engine tests -q  # + Postgres council-memory integration suite
```

- The `engine/` suite (≈1,200 tests) runs with no external services.
- The `tests/` suite covers the optional Postgres + pgvector council-memory
  backend. It **auto-skips** when no `COUNCIL_MEMORY_DSN` database is reachable,
  so `pytest` is green anywhere. CI provisions a pgvector service and runs it in
  full. To run it locally, stand up Postgres + pgvector and set
  `COUNCIL_MEMORY_DSN` (see `scripts/bootstrap_council_memory.sh`).

Every push to `master` runs the suite on Python 3.11 and 3.12 via GitHub Actions.

## Built by

- **[Arshia Heravi](https://github.com/Arshiaheravi)** — developer, created AutoAgent V1
- **[Seb San](https://github.com/SebSanGar)** — V2 Agency architecture

## License

MIT © Arshia Heravi
