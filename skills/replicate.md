# Skill: Replicate (URL or Image → Build Plan)

**When to use**: The operator drops a website URL, social post, or design screenshot and says
"clone this / replicate this / build this." Terminal-native port of Anthropic's
Claude Design (Opus Labs product) — capture reference, extract spec, human
annotates, executor builds.

**When NOT to use**: original design from text prompt (use `canvas-design.md` or
`ui-stack.md`). Reviewing an OWN page for regressions (use `visual_check.py`).

## Three-phase workflow

### Phase 1 — Capture

Input is one of:
- URL (public web page)
- Image (.png / .jpg / .jpeg / .webp / .gif)
- PDF (claude-native read via `@path`)
- DOCX (text extracted via `python-docx`, passed as context)

`engine/replicator.py::capture(src)` dispatches by extension:
- URL → Playwright launches Chromium, screenshots at 1440×900 and 390×844,
  dumps full-page HTML + meta
- Image → copy into workspace, vision call reads via `@path`
- PDF → copy in; vision call reads PDF natively via `@path`
- DOCX → `python-docx` extracts paragraphs into `extracted.txt`, passed as
  text-only context (no vision call — acts as design brief / spec doc)

Artifacts written to `brain/replicate/<slug>/`:
- `desktop.png`, `mobile.png` (URL)
- `reference.{png,jpg,pdf,docx}` (local file)
- `extracted.txt` (DOCX only)
- `dom.html`, `meta.json` (URL only)
- `source.txt` (original URL or path)

### Phase 2 — Spec

`engine/replicator.py::extract_spec(capture)` calls Claude Opus with the
screenshot(s). Returns structured brief JSON:

```json
{
  "movement": "one-or-two-word philosophy",
  "layout": {"structure": "grid|flex|stacked", "sections": [...]},
  "palette": {"bg": "#xxx", "surface": "#xxx", "accents": ["#xxx"], "text": "#xxx"},
  "typography": {"display": "...", "body": "...", "mono": "..."},
  "components": [{"name": "Hero", "notes": "..."}, ...],
  "motion": ["fade-up on scroll", "..."],
  "copy": {"headline": "...", "subhead": "...", "cta": "..."},
  "assets_needed": ["logo", "hero-image", "..."],
  "tech_stack_hint": "React+Tailwind | vanilla HTML | ..."
}
```

Written as `brief.md` (human-readable) + `brief.json` (machine-readable).

### Phase 3 — Handoff

`engine/replicator.py::handoff(brief_path, ctx)`:
1. Notify the operator — "Replica brief ready. Annotate or approve."
2. Wait for `brief.md` edits (operator adds constraints, changes palette, vetoes sections)
3. `council.convene_council()` reviews brief — 3-stage multi-model check
4. Write approved brief to project backlog as a new task:
   `Replicate: <url-or-image-slug> per brief brain/replicate/<slug>/brief.md`
5. Executor picks it up on next WORK session — builds per brief + agency UI stack
   (`ui-stack.md`: Framer Motion + shadcn + 21st.dev layouts)

## Design-system merge (optional, `--project` flag)

If target project has a `frontend/styles.css` or `tailwind.config.{ts,js}`,
`replicator.merge_design_system(brief, ctx)` overrides `palette` + `typography` with
project's existing tokens. Also scans `public/`, `assets/`, `brand/`, `static/`,
`src/assets/`, `frontend/assets/` for:
- **Logos**: SVG/PNG/JPG with names matching `logo|brand|mark|wordmark|icon`
- **Fonts**: `.woff`, `.woff2`, `.ttf`, `.otf`
- **Other images**: remaining SVG/PNG/JPG (up to 30)

Results surfaced in `brief.md` under **Brand assets** — executor uses these paths
when building. Mirrors Claude Design's onboarding scan.

## Accessibility review (automatic)

Before the brief is written, `a11y_review(spec)` runs a separate `claude -p` pass
against WCAG 2.2 AA. Output injected into `brief.md` under **Accessibility review**:
- Contrast pairs likely failing 4.5:1 / 3:1
- Motion that needs `prefers-reduced-motion` fallback
- Components missing visible focus state
- Semantic-structure risk
- Top-3 required fixes

Non-blocking — if the a11y call fails or times out, brief still ships without it.

## Critical rules

- Screenshot + DOM beats screenshot alone — always grab both for URLs
- Human-in-loop mandatory before build — spec is a draft, not a contract
- Cap single capture at 2 viewports — no full-device-matrix bloat
- Never build production code in Phase 2 — spec only. Building is executor's job.
- Attribution: replica briefs must name the source URL in `brief.md` header.
  Agency does NOT ship clones as original work.

## CLI usage

```bash
autoagent replicate https://example.com
autoagent replicate ~/Downloads/landing-screenshot.png
autoagent replicate ~/Downloads/brand-brief.pdf
autoagent replicate ~/Downloads/design-spec.docx
autoagent replicate https://example.com --project myapp  # merge with project design system + brand assets + a11y
autoagent replicate https://example.com --no-wait           # skip human annotation, straight to council
autoagent replicate --resume <slug> --project myapp      # after annotating brief.md
```

## Output location

- Artifacts: `brain/replicate/<slug>/`
- Backlog task: `~/.autoagent/projects/<project>/memory/backlog.md` (prepended)
- Logs: `logs/replicate-<slug>.log`
