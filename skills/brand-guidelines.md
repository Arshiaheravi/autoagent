# Skill: Brand Guidelines

**When to use**: Creating branded documents, presentations, or artifacts that should follow
a consistent visual identity. This is a **project-domain example** — each project defines its
own palette and fonts here (or in its `PROJECT.md`) and this skill applies them consistently.

## Your project brand (fill these in per project)

Define the brand once, then reference it everywhere. Example structure:

| Element | Value (example) |
|---------|-----------------|
| Background | `#0a0a0a` |
| Surface | `#141414` |
| Accent (primary) | `#00c896` |
| Accent (warning) | `#f0b429` |
| Accent (info) | `#4da6ff` |
| Muted | `#666666` |
| Text primary | `#ffffff` |
| Text secondary | `#999999` |
| Font (numbers/data) | Monospace |
| Font (headings) | System sans-serif or a font set in CSS variables |

**Never add a new raw hex value** — always add it to `:root` CSS variables first, then
reference the variable.

## Rules

- Apply the brand system that matches the context (the app vs. an external document).
- Never mix two brand systems in one artifact.
- Maintain a contrast ratio ≥ 4.5:1 for body text.
- Use CSS variables for colors — never hardcode hex values in component code.
