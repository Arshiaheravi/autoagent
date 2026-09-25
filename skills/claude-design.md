# Skill: Claude Design (Design↔Code Standard)

**When to use**: As a SUPPORTING tool during UI work — design-system manifest +
drift enforcement, stakeholder exports (PDF/PPTX), and fast throwaway mockups.
NOT as the design engine.

**Who leads:** the build stack leads design. The code stack (`ui-stack.md` —
ui-ux-pro-max + frontend-design + 21st.dev) produces the final product; it tends
to beat a hosted design tool on built-product quality. Do NOT route a real build
through Claude Design's canvas as a mandatory gate. Use Claude Design where it
adds value the code stack doesn't: importing/enforcing a design system, exporting
decks, and quick non-designer mockups.

**What Claude Design is**: Anthropic's hosted design tool (beta, paid plans, web
+ desktop). It imports a design system (from a repo, design files, or codebase),
builds with the project's *real* components/tokens, and **self-checks its output
against the design system before you see it**. It pairs bidirectionally with
Claude Code: hand a design off to build, or start in Code and sync design
projects from the terminal. Exports to PDF/PPTX and other tools.

It is external SaaS — you do not "install" it into a repo. You adopt the
*workflow* below and keep each project's design system clean so the import is
high-quality.

---

## Collaboration model — originate → produce

Treat the two tools as sequential, not competing:

- **Claude Design = the sketcher.** Wins brand fidelity, drift prevention,
  speed-to-artifact, stakeholder decks. Use it to ORIGINATE: workshops,
  rapid prototypes, brand-safe mockups, pitch collateral — at the cheapest stage,
  where its self-check enforces brand consistency before engineering starts.
- **Code stack = the builder.** Wins built-product design quality + code
  maintainability. Takes the sketch as a high-fidelity **spec** (not final code)
  and ships the production frontend. Human taste is the final gate.
- **Handoff is ONE-WAY: sketch → build.** Do not trust the tool's code in
  production or rely on bidirectional sync. It hands a spec/visual; you write the
  real code.
- **Earn trust before scaling it:** pilot Claude Design on 2-3 small surfaces and
  DIFF its code output against hand-written code (measure quality + rework)
  before giving it a larger role.

## What to fold back into the build stack

Claude Design does two things worth mirroring in the code stack so the gap keeps
closing:
1. **Self-check-against-system before output.** It verifies its work against the
   design system before showing it. Mirror this: the `extract_design_system.py`
   re-extract + drift diff is your version — run it as a build gate so the build
   self-checks too (no new `*-` drift family, new tokens reuse existing).
2. **Brand fidelity via real-component import.** It builds from the project's
   actual tokens/components. Keep the build doing the same — design against the
   extracted manifest, never freehand off-token. When the tool surfaces a cleaner
   token/component structure during ideation, capture it back into the manifest.

---

## The unison principle

**Unified workflow, per-brand systems.** Every project follows the same design
workflow + manifest convention (with Claude Design as an optional supporting tool
inside it). Each project keeps its OWN brand tokens — distinct projects are
intentionally distinct and must NOT be flattened into one look. "In unison" =
identical process + tooling + manifest convention, not identical visuals.

What is shared:
1. The **manifest convention** — every project's design system lives at
   `<project>/design/` (`design-system.json` + `DESIGN_SYSTEM.md`).
2. The **extractor** — `scripts/extract_design_system.py` produces that manifest
   from a project's CSS.
3. The **workflow** below.
4. The **toolkit** — `ui-stack.md` (Framer Motion, ui-ux-pro-max, frontend-design,
   21st.dev) is the code-layer execution.

What is NOT shared: colors, type, voice, component personality — those are
per-brand. See `brand-guidelines.md` for per-brand tokens.

---

## Workflow (every UI task)

1. **Extract the design system FIRST** (always — tool-agnostic, valuable on its
   own). Run the extractor:

   ```bash
   python3 scripts/extract_design_system.py <project-dir|css-file> --name <Brand>
   ```

   Writes `<project>/design/design-system.json` + `DESIGN_SYSTEM.md`. Reports a
   **drift signal** (class-prefix families with many variants) and **redefined
   tokens** (same `--var` defined more than once) — the consolidation backlog.

2. **Consolidate before treating as canon.** Loud drift (a class-prefix family
   with dozens of one-off variants) is the real problem. Fix worst offenders or
   note them.

3. **Build with the code stack** (`ui-stack.md`: ui-ux-pro-max → frontend-design
   → Framer Motion / 21st.dev) against the brand manifest. This is the design
   engine — it leads on built-product quality. This step is where the wow comes from.

4. **Use Claude Design only where it adds value** the code stack doesn't (all
   OPTIONAL):
   - **Drift enforcement** — import the manifest so it flags off-token colors /
     duplicate component variants. Useful as a *check*, not as the builder.
   - **Fast mockups** — quick canvas throwaways for non-designers / early
     alignment, before the real thing is built.
   - **Decks** — export to PDF/PPTX for pitches and stakeholder reviews.
   Skip Claude Design entirely when the code-stack output is already better (usual
   case). Do NOT route the real build through its canvas as a mandatory gate.

5. **Verify against the system.** Re-run the extractor and diff: new tokens reuse
   existing ones; no new `*-` drift family. Playwright check per `playwright.md`.

---

## Stack-fit caveat (and the migration lever)

Claude Design's "real components" superpower needs a component layer
(React/Vue/etc). Vanilla HTML/CSS projects (many hand-rolled pages, one
`styles.css`) get the **token/style-system enforcement + mockups** value now, but
not component reuse — there are no components to reuse.

→ This is a concrete argument to migrate vanilla frontends to a component layer.
Once a project has components, the canvas↔Code loop pays off fully. Don't hedge
new projects into vanilla "to keep it simple" — start them component-based so
they're Claude-Design-native from day one.

Beta caution: use Claude Design for design / mockups / new screens. Don't bet a
large production rollout on it until out of beta.

---

## Default for new projects

New frontends start component-based (Next.js/React + Tailwind + shadcn per
`web-artifacts.md`) with a `<project>/design/` manifest from day one, so they
stay in unison with the workflow (and are trivially importable into Claude Design
for enforcement/exports when useful).

## Cross-references

- `ui-stack.md` — the code-layer toolkit (Framer Motion, ui-ux-pro-max, frontend-design, 21st.dev)
- `brand-guidelines.md` — per-brand tokens (the per-brand half of the unison principle)
- `design.md` — project-specific visual rules / anti-AI-slop
- `canvas-design.md` — static visual art (not app UI)
- `playwright.md` — verify rendered output
- `scripts/extract_design_system.py` — the manifest extractor

## Anti-patterns

- Importing a raw, drifted stylesheet into Claude Design → it learns the drift.
  Always extract + review the drift signal first.
- Building one design system across distinct brands → flattens brand identity.
  Per-brand tokens, shared workflow.
- Routing a real build through Claude Design's canvas as a mandatory gate, or
  subordinating the proven code stack to a beta tool. The code stack leads on
  built-product design quality; Claude Design supports (enforcement, exports,
  mockups).
- Starting a new frontend in vanilla HTML "for speed," then wishing it were
  component-based. Start component-based.
