# Skill: Canvas Design (Visual Art / Posters / Design Artifacts)

**When to use**: Creating visual art, posters, abstract designs, branded visuals, or any
output that is primarily a designed image (.png or .pdf) rather than a document with text.

## Two-phase workflow

### Phase 1 — Design Philosophy (.md file first)

Before touching any canvas code, write a visual philosophy (4-6 paragraphs):

- **Name the movement** (1-2 words): "Brutalist Joy" / "Chromatic Silence" / "Metabolist Dreams"
- Express how the philosophy manifests through: space/form, color/material, scale/rhythm, composition/balance
- Emphasize: visual expression over text, spatial communication, minimal words
- Stress craftsmanship: "meticulously crafted," "painstaking attention," "master-level execution"

**Examples of movement philosophies:**
- "Concrete Poetry" — monumental form, bold geometry, Brutalist spatial divisions, text as rare gesture
- "Chromatic Language" — color as primary information system, geometric precision, Josef Albers meets data viz
- "Analog Meditation" — paper grain, vast negative space, Japanese photobook aesthetic, whispered typography

Save as a `.md` file alongside the output.

### Phase 2 — Canvas Expression (.png or .pdf)

Express the philosophy visually using Python (reportlab, PIL) or JavaScript (canvas/SVG):

```python
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

c = canvas.Canvas("output.pdf", pagesize=letter)
w, h = letter

# 90% visual, 10% text
# Use repeating patterns, geometric forms, layered elements
# Sparse clinical typography — short phrases, never paragraphs

c.setFillColorRGB(0.04, 0.04, 0.06)
c.rect(0, 0, w, h, fill=1)  # background

# ... build the composition ...

c.save()
```

## Critical design rules

- **90% visual, 10% text** — ideas through form/color/space, not paragraphs
- **No overlapping elements** — every element has breathing room and clear separation
- **Nothing falls off the canvas** — proper margins throughout
- **Design-forward typography** — pick expressive, characterful fonts over default system fonts (use a project fonts dir if one exists, else a well-chosen installed face)
- **Subtle conceptual reference** — embed the topic's "soul" invisibly into the composition
  (only those who know will catch it — like a jazz musician quoting another song)
- **Refine, don't add** — second pass = make existing elements more cohesive, not more elements

## Final pass checklist

Before saving the final output ask: *"How can I make what's already here more of a piece of art?"*
- Composition more cohesive?
- Spacing more intentional?
- Color palette more unified?
- Typography more integrated into the design?

## Project usage

- Marketing poster for a launch
- Visual explanation of a concept or pattern
- Investor one-page visual (abstract representation of the product/strategy)
- Social media image assets
