# Skill: Web Artifacts Builder

**When to use**: Building self-contained interactive HTML artifacts — dashboards, data visualizers,
calculators, tools that run entirely in the browser with no backend.

## Stack

A single self-contained HTML file. Use vanilla JS/CSS, or React via inlined UMD
builds — whatever the artifact needs — with every dependency embedded in the file.

## Workflow

Write ONE `.html` file directly and iterate on it. There is no scaffold/bundle
step and no build toolchain — the deliverable is the file itself.

1. Write the artifact as a single `.html` with all markup, CSS in a `<style>`
   block, and JS in a `<script>` block. If you need React, paste the minified
   UMD `react`/`react-dom` source inline (or a small hand-rolled component
   layer) — never a CDN `<script src>`.
2. Open the file in a browser (or the project's Playwright check) to verify it
   renders and the console is clean.
3. Ship the file. If the project has a preferred artifacts directory in
   `.autoagent/PROJECT.md`, write there; otherwise alongside the feature.

## Design rules (from Anthropic)

- Avoid centered layouts, purple gradients, uniform rounded corners, Inter font — these scream AI-generated
- Give it a distinctive, context-appropriate visual identity — unique type, cohesive palette, micro-interactions
- Dark theme preferred for trading/data tools
- Every element must work without a network connection

## Example use cases

- Data visualizer (interactive chart in a single HTML file)
- What-if calculator (run scenarios in the browser)
- Interactive tutorial (animated concept explanation)
- Exportable dashboard (send a standalone HTML to stakeholders)

## Key principle

The output is ONE `.html` file. No CDN links, no external fonts, no API calls — everything embedded.
Share it as a file attachment; it runs in any browser.
