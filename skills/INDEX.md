# Skill Library — Quick Reference

Read this first to find the right skill file before starting any task.

## Skill scopes

- **Universal**: safe for every project (`coding`, `testing`, `debugging`, `git`, `security`, `performance`, `clean-architecture`, `quality-standards`, `agent-patterns`, `research`, `audit`).
- **Department**: generally reusable, but tied to a department workflow such as design, communications, documents, research, replication, or MCP building.
- **Project-domain**: hidden from a project's prompt unless that project enables `project_domain` in its config (enforced at runtime by the skill gate). The project-domain table below is injected only when the scope is enabled. Generic design/brand work routes to `ui-stack.md`.

## When to use each skill

| Task type | Skill file | Key workflow it provides |
|---|---|---|
| Any copy with numbers, stats, regulatory refs, claims | `claim-source-discipline.md` | Forces every stat to have a defensible source or get cut |
| Every session — agent meta-rules | `agent-patterns.md` | Failure modes, planning, verification contract, self-critique |
| Every session — code quality | `clean-architecture.md` | Import style, models, health probes, rate limiting, config, logging, tier enforcement |
| Every session — accuracy | `quality-standards.md` | Two-commit TDD proof, behavioral test assertions, META validation, scope declaration |
| End-to-end product features, UX + architecture decisions, council debate | `elite-product-council.md` | Shared quality bar, implementation sequence, debate protocol, polish checklist |
| Writing backend code | `coding.md` | Evidence-first, minimal change, route/service/model patterns |
| Debugging a bug or test failure | `debugging.md` (+ `agent-patterns.md` FM-8 Error Cascade) | 5-step systematic process: read → reproduce → isolate → fix → verify |
| Security review / input validation | `security.md` | OWASP checklist, SQL injection, secrets, admin auth, user input |
| Slow route / performance issue | `performance.md` | N+1 queries, async blocking, caching, parallel fetches |
| Writing tests or fixing test failures | `testing.md` (+ `quality-standards.md` for two-commit proof) | Test-first spec, patching rules, what "tests pass" means |
| Git commits and pushes | `git.md` | Project-repo flow, commit message format, pre-commit checks |
| New UI / landing / app frontend — design ENGINE (agency leads) | `ui-stack.md` | Framer Motion + UI/UX Pro Max + frontend-design + 21st.dev. Agency leads the build |
| Design-system manifest, drift enforcement, deck exports, fast mockups | `claude-design.md` | SUPPORTING tool only. Extractor (drift signal) + enforcement / PDF-PPT / mockups |
| Playwright UI checks | `playwright.md` | How to run checks, pass/fail criteria, recon-then-action pattern |
| Research and web search tasks | `research.md` | Search strategy, evaluation criteria |
| Building Claude API features | `claude_api.md` | Model selection, streaming, tool use, common pitfalls |
| Pre-commit quality audit | `audit.md` | Virtual senior dev team review — security, UX, performance, compliance |
| Excel / spreadsheet output | `xlsx.md` | openpyxl formulas, pandas export, financial color coding, zero error rules |
| PDF generation or reading | `pdf.md` | pypdf merge/split, pdfplumber extract, reportlab create, FileResponse return |
| Word document (.docx) | `docx.md` | docx-js creation, unpack/edit XML, critical page size + table rules |
| PowerPoint presentation (.pptx) | `pptx.md` | PptxgenJS creation, unpack/repack XML, design principles |
| MCP server development | `mcp-builder.md` | 4-phase workflow, TypeScript SDK, tool naming, evaluation |
| Self-contained HTML artifact | `web-artifacts.md` | React+Tailwind+shadcn bundle into single HTML file |
| Visual themes for docs/slides | `theme-factory.md` | 10 preset themes, apply consistently, custom theme generation |
| Generative / algorithmic art | `algorithmic-art.md` | p5.js, seeded randomness, parameter controls, single HTML output |
| Long-form document writing | `doc-coauthoring.md` | 3-stage co-authoring, section-by-section, reader testing |
| Internal team updates | `internal-comms.md` | 3P updates, incident reports, status reports, formatted templates |
| Animated GIFs for Slack | `slack-gif.md` | PIL + imageio, emoji/message sizes, animation techniques |
| Creating new skill files | `skill-creator.md` | Skill file format, quality checklist, when to create vs reuse |
| Visual art / posters / design images | `canvas-design.md` | 2-phase: philosophy (.md) then canvas (.png/.pdf), 90% visual 10% text |
| Replicate/clone website, post, or screenshot reference | `replicate.md` | capture → spec (Claude Opus vision) → human annotate → council → executor. CLI: `autoagent replicate <url\|image>` |

<!-- PROJECT-DOMAIN-START: injected per-project when a project enables `project_domain` -->
## Project-domain skills (only when enabled for this project)

Domain skills live in your project's own directory (`projects/<name>/skills/`) and
are loaded only when the project sets `project_domain` in its config. The reusable
framework ships none by default — each project adds skills specific to what it's
building. Examples of domain skills a project might add:

| Task type | Example skill file | What it would provide |
|---|---|---|
| Data ingest / processing pipeline | `data-pipeline.md` | Pipeline stages, data formats, quality validation |
| Project design system | `design.md` | The project's own theme / component aesthetic rules |
| Brand color + font system | `brand-guidelines.md` | Project palette, CSS variable rules |

Create one with `autoagent agent create` or drop a Markdown file into the project's
`skills/` directory and reference it from the project config.
<!-- PROJECT-DOMAIN-END -->
