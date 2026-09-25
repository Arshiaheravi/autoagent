# Skill: Theme Factory

**When to use**: Applying a consistent visual theme to any artifact — slides, docs, HTML pages, dashboards.

## Available themes (10 presets)

| # | Name | Identity |
|---|------|----------|
| 1 | Ocean Depths | Professional, calming, maritime |
| 2 | Sunset Boulevard | Warm, vibrant |
| 3 | Forest Canopy | Natural, earth tones |
| 4 | Modern Minimalist | Clean, grayscale |
| 5 | Golden Hour | Rich, autumnal |
| 6 | Arctic Frost | Cool, crisp |
| 7 | Desert Rose | Soft, sophisticated |
| 8 | Tech Innovation | Bold, modern tech |
| 9 | Botanical Garden | Fresh, organic |
| 10 | Midnight Galaxy | Dramatic, cosmic |

## How to apply a theme

1. Show theme options to the user (or pick based on context)
2. Read the theme spec from `autoagent/skills/themes/[theme-name].md` (if it exists)
3. Apply colors and fonts consistently across ALL elements — headings, body, backgrounds, accents
4. Ensure contrast ratio is readable (4.5:1 minimum for body text)

## Respect the project's own theme

If the project already defines its own theme / design system, do NOT apply
theme-factory presets to the main app. Use theme-factory only for:
- Exported PDFs / reports
- Investor presentations
- One-off standalone HTML artifacts

## Custom theme (when no preset fits)

Generate a theme with: primary color, secondary color, accent color, heading font, body font.
Name it descriptively (e.g. "Midnight Trading"). Apply consistently.
