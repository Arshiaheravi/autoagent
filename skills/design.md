# Skill: Design / Frontend

> For NEW UI work, also read `ui-stack.md` — agency defaults: Framer Motion + UI/UX Pro Max skill + 21st.dev layouts.

## RULES
- Dark theme always — no light mode
- No emojis except flag emojis (🇺🇸 🇨🇦) for market toggle
- All CSS in `frontend/styles.css` — no inline styles, no separate CSS files
- All JS in `frontend/app.js` — no separate JS files
- Trading card aesthetic — cards, badges, confidence bars
- Mobile-first: test at 375px width mentally before committing

## CARD ANATOMY (renderCard() in app.js)
Key differentiators should be VISIBLE on the card face — not hidden behind a modal.
Scan `renderCard()` first when doing any UX work — highest-leverage function in frontend.

## COLOR SYSTEM (from styles.css)
- Background: #0a0a0a (near-black)
- Card surface: #141414
- PLAY green: #00c896
- WATCH yellow: #f0b429
- DECK blue: #4da6ff
- PASS gray: #666
- Earnings warning: red chip

## SIGNAL DISPLAY RULES
- PLAY: show score, pattern type badge, earnings warning if within 21 days
- Score confidence bar fills proportionally (score/100)
- Pattern badge: green for bullish (Flag, Pennant, Asc. Triangle, Falling Wedge), orange for bearish warning (Desc. Triangle, Rising Wedge)

## AFTER FRONTEND CHANGES
- Open browser, check at 375px, 768px, 1280px widths mentally
- Check dark theme renders correctly
- Check no layout breaks when signal list is empty
- Run tests: `py -m pytest tests/ -q --ignore=tests/test_e2e.py`

## ANTHROPIC FRONTEND-DESIGN PRINCIPLES (extracted 2026-03-20)

**Before adding any new UI element:**
- Define the tonal direction: is this element utilitarian (data, precision) or atmospheric (trust, excitement)?
- Match the project's established direction — e.g. a data-heavy product might aim for a dark, precise "terminal" feel, while a consumer app aims for warmth and approachability

**Typography rules:**
- Use CSS variables for font stacks — never hardcode font-family inline
- Monospace for numbers/prices/scores (already used in card confidence) — keep this consistent

**Color discipline:**
- Stick to the existing CSS variable system — never add new raw hex values
- Accents (new badges, chips) must use existing palette: PLAY green, WATCH yellow, DECK blue, or explicit warning red
- Never add a new color without adding it as a CSS variable in the `:root` block

**Animation:**
- High-impact moments only: PLAY signal appearing, breakout alert, convergence badge
- Never animate anything that appears on every page load — only transitions triggered by user action or new data

**Avoid (AI slop patterns):**
- Generic purple/blue gradients on dark backgrounds
- Predictable 3-column card grids without visual hierarchy
- Loading spinners on every element — batch skeleton states instead
- Cookie-cutter empty states ("No data available") — write context-specific copy

**Match complexity to vision:**
- A simple data addition (new chip on card) = clean minimal CSS, no animation
- A new page (Auto-Trader, Smart Money) = full layout with header, stats strip, and table
