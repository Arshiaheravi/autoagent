# Skill: UI Stack (Default Frontend Toolkit)

**When to use**: Any new UI work, landing page, marketing site, app frontend, or web artifact where animation, layout, or visual polish matters. These are the default tools — pick them unless the task explicitly forbids one.

> **This is the design ENGINE.** This stack (ui-ux-pro-max + frontend-design +
> Framer Motion + 21st.dev) leads the build on produced-product quality.
> `claude-design.md` is a SUPPORTING tool used alongside it for design-system
> enforcement, deck exports, and fast mockups — not a gate the build passes
> through.

## Stack

1. **Framer Motion** — default animation library. Use for page transitions, hover states, scroll-triggered reveals, layout animations.
2. **ui-ux-pro-max** (Claude Code plugin skill, installed at user scope) — design-system generator. 50+ styles, 161 palettes, 57 font pairs, 99 UX guidelines, 25 chart types, 10 framework stacks (React, Next, Astro, Vue, Nuxt, Svelte, SwiftUI, RN, Flutter, Tailwind, shadcn, Jetpack). Invoke BEFORE committing to a design direction.
3. **frontend-design** (Claude Code plugin skill, Anthropic official, installed at user scope) — bold aesthetic execution + production-grade code, anti-AI-slop. Invoke for distinctive visual direction + implementation.
4. **21st.dev** — default source for layouts. Pull block patterns (hero, pricing, features, testimonials, footers) from https://21st.dev instead of hand-rolling generic sections.

## Workflow (two-skill pipeline)

1. **ui-ux-pro-max FIRST** — generate design system (style, palette, typography, effects, anti-patterns) from the database. Especially for multi-framework work or when no design direction is set.
2. **frontend-design SECOND** — commit to a bold aesthetic direction and ship production code matching the generated system.
3. **Framer Motion + 21st.dev** — tools inside the code layer.

## Install

```bash
# Framer Motion (per-project)
npm i framer-motion

# 21st.dev — browse + copy blocks at https://21st.dev (no install)

# Claude Code plugin skills (user scope, install once)
claude plugin install frontend-design@claude-plugins-official
claude plugin marketplace add nextlevelbuilder/ui-ux-pro-max-skill
claude plugin install ui-ux-pro-max@ui-ux-pro-max-skill
```

## Usage rules

- **Animations**: prefer `motion` components (`motion.div`, `motion.button`) over CSS keyframes for anything stateful (hover, tap, layout, presence).
- **Layouts**: start from a 21st.dev block, then customize — don't design from scratch unless the project demands unique visual language.
- **Design system**: invoke `ui-ux-pro-max` for non-trivial screens (spacing, contrast, palette, typography). Don't guess.
- **Aesthetic execution**: invoke `frontend-design` to pick a bold direction and ship cohesive production code. No Inter/Roboto defaults.
- **Tailwind + shadcn/ui** (from `web-artifacts.md`) remain styling + component primitives. This stack layers animation, system, and layout on top.

## Cross-references

- `claude-design.md` — design↔code standard (load first for UI); Claude Design import + manifest workflow
- `web-artifacts.md` — single-file HTML artifacts (React + Tailwind + shadcn base)
- `design.md` — project-specific visual rules (dark theme, card aesthetic, color system)
- `canvas-design.md` — static visual art and posters (not app UI)

## Anti-patterns

- Hand-rolling keyframe CSS when Framer Motion is 3 lines shorter and more composable.
- Building a hero/pricing/footer section from scratch when 21st.dev has a vetted block.
- Making design-system calls (spacing scale, type ramp, color tokens) without invoking `ui-ux-pro-max` on non-trivial screens.
- Using generic AI aesthetics (Inter + purple gradient + centered layout) when `frontend-design` exists to push distinctive direction.
- Letting both plugin skills auto-fight on the same task — explicit invocation order: system (Pro Max) → execution (frontend-design).
