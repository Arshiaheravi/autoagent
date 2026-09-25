# Skill: Document Co-Authoring

**When to use**: Writing long-form documents collaboratively — specs, proposals, decision docs,
PRDs, architecture docs, investor memos.

## 3-stage workflow

### Stage 1 — Context gathering (before writing anything)

Collect:
- Document type (spec, proposal, decision doc, memo?)
- Audience (engineers, investors, users?)
- Desired outcome (approval, alignment, reference?)
- Any templates or existing examples
- Background info dump (paste whatever is relevant — discussions, notes, constraints)

Ask clarifying questions to close gaps. Do NOT start drafting until context is clear.

### Stage 2 — Section-by-section drafting

Work through sections in this order: **start with the hardest/most unknown section first**.

For each section:
1. Clarifying questions (if needed)
2. Brainstorm 5-10 options for how to frame it
3. Draft the section
4. Refine iteratively (use `str_replace` for edits — never reprint the whole doc)

### Stage 3 — Reader testing

Before finalizing, simulate a fresh reader:
- What questions would they have after reading?
- Does the document work without the author's context?
- Are there any blind spots?

## Key principles

- Use `str_replace` for edits (never reprint entire document)
- Request specific feedback, not "does this look good?"
- Build section-by-section, not all at once
- Final quality check: read the whole thing as if you've never seen it

## Project usage

- Investor / stakeholder one-pager
- Methodology documentation
- API documentation
- Feature spec before building
