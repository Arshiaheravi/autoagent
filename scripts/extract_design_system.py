#!/usr/bin/env python3
"""Extract a clean design-system manifest from a project's CSS.

Agency tooling for the Claude Design workflow (see skills/claude-design.md).
Claude Design imports a design system and then builds + self-checks against it.
Importing a drifted stylesheet imports the drift; this extractor produces a
consolidated, categorized manifest (tokens + component inventory) so the import
is high-quality and the drift is visible instead of inherited.

Pure stdlib (regex) — no CSS parser dependency. Heuristic categorization is good
enough for design-token review; it is not a spec-compliant CSS parser.

Usage:
    python3 extract_design_system.py <css-file|project-dir> [--name BRAND] [--out DIR]

Outputs (into --out, default <project>/design/):
    design-system.json   machine-readable manifest
    DESIGN_SYSTEM.md      human/Claude-readable manifest for Claude Design import
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

# --- token regexes ---------------------------------------------------------
_DECL = re.compile(r"(--[A-Za-z0-9_-]+)\s*:\s*([^;}]+)\s*[;}]")
_HEX = re.compile(r"#[0-9A-Fa-f]{3,8}\b")
_COLOR_FN = re.compile(r"\b(rgb|rgba|hsl|hsla|oklch|color)\s*\(")
_LENGTH = re.compile(r"-?\d*\.?\d+(px|rem|em|%|vh|vw|vmin|vmax|ch|pt)\b")
# class selectors at the start of a rule (rough — strips pseudo/combinators)
_CLASS = re.compile(r"\.([A-Za-z_][A-Za-z0-9_-]*)")


def _is_color(value: str) -> bool:
    return bool(_HEX.search(value) or _COLOR_FN.search(value)) or value.strip() in {
        "transparent", "currentColor", "white", "black",
    }


def _is_length(value: str) -> bool:
    return bool(_LENGTH.search(value))


def _categorize(name: str, value: str) -> str:
    n = name.lower()
    v = value.strip()
    if "shadow" in n or (v.count("px") >= 2 and "rgb" in v):
        return "shadow"
    if "radius" in n or "round" in n:
        return "radius"
    if any(k in n for k in ("font", "leading", "line-height", "tracking", "weight")) and not _is_color(v):
        return "typography"
    if re.search(r"\btext(-|$)", n) and _is_length(v):
        return "typography"  # text-size scale (--text-sm: 0.875rem)
    if _is_color(v) or any(k in n for k in (
        "color", "bg", "surface", "border", "brand", "accent", "muted",
        "danger", "warning", "success", "info", "green", "ink", "fg", "text",
    )):
        return "color"
    if _is_length(v) and any(k in n for k in ("space", "gap", "size", "width", "height", "pad", "margin")):
        return "spacing"
    if "z" in n.split("-") or "index" in n:
        return "z-index"
    if _is_length(v):
        return "spacing"
    if "ease" in n or "duration" in n or "transition" in n or "anim" in n:
        return "motion"
    return "other"


def _read_css(target: str) -> tuple[str, str]:
    """Return (css_text, project_dir) for a css file or a project directory."""
    if os.path.isfile(target):
        with open(target, encoding="utf-8") as f:
            return f.read(), os.path.dirname(os.path.abspath(target))
    if os.path.isdir(target):
        # prefer a top-level styles.css, else concatenate all *.css (shallow first)
        candidates = []
        for root, _dirs, files in os.walk(target):
            if "node_modules" in root or "/." in root:
                continue
            for fn in files:
                if fn.endswith(".css"):
                    candidates.append(os.path.join(root, fn))
        if not candidates:
            sys.exit(f"no .css files found under {target}")
        candidates.sort(key=lambda p: (p.count(os.sep), p))
        text = "\n".join(open(c, encoding="utf-8").read() for c in candidates)
        return text, os.path.abspath(target)
    sys.exit(f"not a file or directory: {target}")


def _strip_comments(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def extract(css: str) -> dict:
    css = _strip_comments(css)

    # tokens — last declaration wins (cascade), but record duplicate count
    tokens: dict[str, dict[str, str]] = {}
    seen: dict[str, int] = {}
    for m in _DECL.finditer(css):
        name, value = m.group(1), " ".join(m.group(2).split())
        seen[name] = seen.get(name, 0) + 1
        cat = _categorize(name, value)
        tokens.setdefault(cat, {})[name] = value

    # component inventory — class selector frequency (drift signal)
    counts: dict[str, int] = {}
    for m in _CLASS.finditer(css):
        cls = m.group(1)
        counts[cls] = counts.get(cls, 0) + 1
    components = sorted(
        ({"selector": "." + c, "rules": n} for c, n in counts.items()),
        key=lambda x: (-x["rules"], x["selector"]),
    )

    # drift hint — classes grouped by leading prefix (e.g. nav-, card-, kpi-)
    prefixes: dict[str, int] = {}
    for c in counts:
        pre = c.split("-")[0]
        prefixes[pre] = prefixes.get(pre, 0) + 1
    drift = sorted(
        ({"prefix": p + "-*", "variants": n} for p, n in prefixes.items() if n >= 4),
        key=lambda x: -x["variants"],
    )

    redefined = sorted(n for n, c in seen.items() if c > 1)

    return {
        "tokens": tokens,
        "components": components,
        "drift_hints": drift,
        "redefined_tokens": redefined,
        "stats": {
            "token_count": sum(len(v) for v in tokens.values()),
            "component_count": len(components),
        },
    }


def render_markdown(manifest: dict, brand: str, source: str) -> str:
    t = manifest["tokens"]
    out = [
        f"# {brand} — Design System",
        "",
        "> Auto-extracted by `autoagent/scripts/extract_design_system.py` for the",
        "> Claude Design workflow (see `skills/claude-design.md`). Import this file",
        "> (or `design-system.json`) into Claude Design so it builds + self-checks",
        "> against the real system. Review + consolidate before treating as canon.",
        "",
        f"- **Source:** `{source}`",
        f"- **Tokens:** {manifest['stats']['token_count']}  ·  **Components:** {manifest['stats']['component_count']}",
        "",
    ]
    order = ["color", "typography", "spacing", "radius", "shadow", "motion", "z-index", "other"]
    for cat in order:
        if not t.get(cat):
            continue
        out.append(f"## {cat.capitalize()} tokens")
        out.append("")
        out.append("| Token | Value |")
        out.append("|---|---|")
        for name, val in sorted(t[cat].items()):
            out.append(f"| `{name}` | `{val}` |")
        out.append("")

    if manifest["drift_hints"]:
        out.append("## Drift signal — class-prefix families (review for consolidation)")
        out.append("")
        out.append("| Prefix | Variants |")
        out.append("|---|---|")
        for d in manifest["drift_hints"]:
            out.append(f"| `{d['prefix']}` | {d['variants']} |")
        out.append("")

    if manifest["redefined_tokens"]:
        out.append("## Redefined tokens (defined more than once — possible drift)")
        out.append("")
        out.append(", ".join(f"`{n}`" for n in manifest["redefined_tokens"]))
        out.append("")

    out.append("## Top components (by rule frequency)")
    out.append("")
    out.append("| Selector | Rules |")
    out.append("|---|---|")
    for c in manifest["components"][:40]:
        out.append(f"| `{c['selector']}` | {c['rules']} |")
    out.append("")
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("target", help="CSS file or project directory")
    ap.add_argument("--name", help="brand name (default: project dir name)")
    ap.add_argument("--out", help="output dir (default: <project>/design)")
    args = ap.parse_args()

    css, project_dir = _read_css(args.target)
    brand = args.name or os.path.basename(project_dir.rstrip(os.sep)) or "Project"
    out_dir = args.out or os.path.join(project_dir, "design")
    os.makedirs(out_dir, exist_ok=True)

    manifest = extract(css)
    manifest["brand"] = brand
    manifest["source"] = args.target

    json_path = os.path.join(out_dir, "design-system.json")
    md_path = os.path.join(out_dir, "DESIGN_SYSTEM.md")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(render_markdown(manifest, brand, args.target))

    s = manifest["stats"]
    print(f"[design-system] {brand}: {s['token_count']} tokens, "
          f"{s['component_count']} components")
    if manifest["drift_hints"]:
        print("[design-system] drift families: " +
              ", ".join(f"{d['prefix']}({d['variants']})" for d in manifest["drift_hints"][:6]))
    print(f"[design-system] wrote {json_path}")
    print(f"[design-system] wrote {md_path}")


if __name__ == "__main__":
    main()
