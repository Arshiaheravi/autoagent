---
name: claim-source-discipline
description: Use this skill ANY time you are writing or reviewing copy that contains numerical claims, percentages, market sizing, regulatory references, comparative claims, financial projections, savings statistics, performance improvements, exit multiples, or named government programs. Triggers on landing pages, pitch decks, grant applications, investor materials, partnership briefs, marketing copy, and anything where a stat will be on a public surface or in front of an evaluator. Enforces the rule that every numerical or factual claim either has a defensible primary source or gets cut. High-leverage because a single wrong number permanently costs credibility with sophisticated readers — use proactively even if not asked. Common repeat offenders: inflated savings percentages, regulatory-body confusion, exit multiples without comp anchors, stats without dates.
---

# Claim & Source Discipline

## The rule

Every numerical or factual claim in copy meets one of two standards before it ships:

1. **Has a defensible primary source** — citation present, source named, date stamped where the underlying figure changes over time
2. **Is qualitatively framed as estimation, not assertion** — "in the order of," "we are targeting," "preliminary modeling suggests"

A claim that meets neither standard gets cut. No exceptions for "it sounds about right" or "I've seen this number elsewhere."

This discipline exists because credibility loss from one wrong number is permanent with sophisticated readers (grant evaluators, academics, investors). One unsourced "84% of [population]" or one wrong regulatory body name is enough to lose the room.

## Source hierarchy

When sourcing a claim, prefer higher-tier sources. Use the lowest-tier source only when no higher-tier source exists, and acknowledge the limitation in the framing.

| Tier | Source type | Examples |
|---|---|---|
| 1 | Primary government / agency data | National statistics agencies, regulator bulletins, official registries |
| 2 | Peer-reviewed research | Journals with a DOI (Nature, Science, Springer, MDPI, domain journals) |
| 3 | Named industry reports | McKinsey, Gartner, BCG, or another named consultancy with a publication date |
| 4 | Direct company filings or press releases | SEC 10-K, earnings releases, official corporate press releases |
| 5 | Reputable trade press | Named trade publications, BusinessWire, PRNewswire |
| **Avoid** | Blog posts, undated stats, secondary aggregators, "studies show" without naming the study |

## The known-offender list

AI-drafted and hastily-drafted copy repeatedly produces these error shapes. Check explicitly for each when reviewing or drafting — the categories are domain-agnostic; fill them with your project's specifics.

### Exit multiples
- **Bad:** "8–12× SaaS multiple at exit," "$80M–$180M exit thesis"
- **Why bad:** No comp anchors. A stated multiple invites pushback unless it matches recent comparable transactions.
- **Fix:** Either name comparable transactions with their multiples and dates, or strip exit math from public surfaces and keep it for the data room.

### Regulatory body names
- **Bad:** naming an agency that was renamed, merged, or superseded
- **Why this matters:** Any domain evaluator spots an outdated regulator instantly — it dates the document and signals the team isn't current.
- **Fix:** Verify the current regulator name and cite its current rules.

### Volatile operational / compliance claims
- **Bad:** stating a throughput or operating window that exceeds what the governing rules permit
- **Why bad:** A non-compliant number is verifiable and collapses on first scrutiny.
- **Fix:** Use realistic figures within the current rules, and cite the rule.

### Time-sensitive statistics
- **Bad:** "84.8% of [population] in [state]" (undated)
- **Right:** the same stat with "as of [specific date], [named source]"
- **Why this matters:** Volatile stats change on every bulletin. An undated stat is wrong as soon as the next one lands.

### Named government programs
- **Bad:** asserting that a named national program "prioritizes X" without verification
- **Why bad:** A real program's priorities must be verified against its current published version before the claim ships.
- **Fix:** Verify against the current program document; quote the priority section with a page reference, or rewrite around a verified priority.

### Improvement / savings percentages
- **Bad:** "30% input savings" or "20% improvement" without source
- **Right:** "15–25% reduction ([named meta-analysis / study], with sample size and date)"
- **Why this matters:** Quantitative claims are domain-checked by anyone with a relevant background. A correctly cited modest claim beats an inflated uncited claim every time.

### Bundle / package pricing
- **Bad:** a headline bundle price that double-counts components
- **Why bad:** Any dealer or operator in the space spots double-counting immediately.
- **Fix:** Verify against current pricing and itemize what's in the bundle.

### "First in market" / "only" claims
- **Bad:** "The only [category] doing [thing]"
- **Better:** Frame as a market vacuum with sourced support — name the competitor that exited or pivoted (with source + date) — rather than asserting absolute uniqueness.

### Patent claims
- **Bad:** claiming a provisional patent on something not patentable subject matter (e.g. a layered software architecture)
- **Why bad:** Non-patentable subject matter collapses on first technical scrutiny.
- **Fix:** Either cite a specific algorithmic process a patent agent has confirmed is filable, or reframe defensibility around trade secrets and trademarks.

## Workflow when drafting

1. **Inventory.** Before writing, list every numerical or factual claim the section needs to support its argument.
2. **Source each.** For every item on the list, name the primary source. If you can't name it, the claim doesn't ship.
3. **Date-stamp.** For any claim where the underlying figure changes (prices, market size, regulatory state, volatile stats), include the date or "as of [period]" framing.
4. **Cite inline.** Use the format that fits the surface — parenthetical citation for landing pages, footnoted citation for grants, full reference list for academic surfaces.

## Workflow when reviewing existing copy

1. **Highlight every number.** Read through and flag every number, percentage, comparative claim, and named program/agency.
2. **Demand a source for each.** Ask where each number came from. Don't accept "I've seen this around."
3. **Check the known-offender list.** Run through the categories above and verify each explicitly.
4. **Propose cuts.** For any claim that can't be sourced or framed as estimation, propose either a source-supported replacement or a cut.

## Format conventions

### Inline citation (landing pages, marketing copy)
> 15–25% cost reduction ([named source], 2025)

### Parenthetical with source list (decks)
> The [category] slot is open following [Competitor A]'s asset sale ([source], [date]) and [Competitor B]'s pivot ([source], [date]).

### Formal citation (grants, academic)
Full author / title / journal / DOI / date in a sources block at end of document.

### Estimation framing (when source isn't available but claim is needed)
> *"[Named sources] suggest combined savings in the order of [range]. That's the range we're targeting in the Y1 pilot — to be measured, not asserted."*

The phrase "to be measured, not asserted" is a clean estimation frame. Reuse it.

## Cross-references

- For audience-appropriate framing of sourced claims, see `copy-tone-calibrator`.
- For EN/ES parallel sourcing, see `bilingual-parallel-positioning`.
- For a project's verified factual canon (the exact stats that have been checked), see that project's voice/brand guide.
