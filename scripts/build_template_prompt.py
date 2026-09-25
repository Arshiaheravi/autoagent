#!/usr/bin/env python3
"""Compile the shipped tenant WORK prompt from the hardened root satellites.

The engine ships `templates/PROMPT.md` to every tenant, but that file is a
hand-maintained monolith that has drifted WEAKER than the five hardened
`PROMPT-*.md` satellites the agency runs for itself (it lost the concurrency /
recovery machinery, the failure ladder, context discipline, etc. — the top
multi-tenant launch risk). This script makes the satellites the single source of
truth and compiles the shipped template FROM them, so the two can't diverge.

Canonical order (from PROMPT.md): RECOVERY → WORK → CONTEXT → FAILURE → VERIFICATION.

Tenant-safe filter:
  - Strips the ADVISOR + COUNCIL sections by default (they depend on
    `.autoagent/scripts/{advisor,council}.sh` infra that BYOK tenants don't
    have). Pass --include-advisor-council to keep them.
  - Genericizes agency-internal specifics: `src/cultivos/` paths → `src/app/`,
    `cultivOS` → `myapp`, the operator's name → "the operator".

By default writes a PREVIEW to `templates/PROMPT.compiled.md` and does NOT touch
the live `templates/PROMPT.md` — diff the preview (and the deployed
`~/.autoagent/templates/PROMPT.md`) before adopting. Pass --write to overwrite
the live shipped template once you've reviewed the preview.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Satellite files in canonical read order.
SATELLITES = [
    ("PROMPT-RECOVERY.md", "RECOVERY"),
    ("PROMPT-WORK.md", "WORK"),
    ("PROMPT-CONTEXT.md", "CONTEXT"),
    ("PROMPT-FAILURE.md", "FAILURE"),
    ("PROMPT-VERIFICATION.md", "VERIFICATION"),
]

# Genericization substitutions (order matters: path forms before bare name).
_SUBS = [
    (re.compile(r"src/cultivos/"), "src/app/"),
    (re.compile(r"src\.cultivos"), "app"),
    (re.compile(r"cultivOS", re.IGNORECASE), "myapp"),
    (re.compile(r"\bSeb\b"), "the operator"),
]


def strip_advisor_council(text: str) -> str:
    """Remove the ADVISOR and COUNCIL sections. Skips from an
    `## ADVISOR`/`## COUNCIL` header until the next header of the same-or-higher
    level, so both contiguous blocks drop and the following section resumes."""
    out: list[str] = []
    skipping = False
    for line in text.splitlines():
        h = re.match(r"^(#{1,2})\s+(.*)", line)
        if h:
            title = h.group(2).strip().upper()
            if title.startswith("ADVISOR") or title.startswith("COUNCIL"):
                skipping = True
                continue
            skipping = False
        if not skipping:
            out.append(line)
    return "\n".join(out)


def genericize(text: str) -> str:
    """Strip agency-internal specifics that must not ship to tenants."""
    for pat, repl in _SUBS:
        text = pat.sub(repl, text)
    return text


def compile_template(root: Path, include_advisor_council: bool = False) -> str:
    """Compile the shipped WORK prompt from the satellites under `root`.

    Pure function (reads files, returns text) so it is unit-testable.
    """
    parts = [
        "# AutoAgent — WORK session instructions",
        "",
        "<!-- COMPILED by scripts/build_template_prompt.py from the hardened",
        "     PROMPT-*.md satellites. Do NOT edit by hand — edit the satellites",
        "     and recompile, or the two will drift again. -->",
        "",
    ]
    for filename, label in SATELLITES:
        raw = (root / filename).read_text(encoding="utf-8")
        if not include_advisor_council:
            raw = strip_advisor_council(raw)
        raw = genericize(raw)
        parts.append(f"\n<!-- ==== {label} ==== -->\n")
        parts.append(raw.strip())
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent,
                    help="repo root containing the PROMPT-*.md satellites")
    ap.add_argument("--include-advisor-council", action="store_true",
                    help="keep the ADVISOR/COUNCIL sections (needs tenant advisor/council infra)")
    ap.add_argument("--write", action="store_true",
                    help="overwrite the live templates/PROMPT.md (default: write a .compiled.md preview)")
    args = ap.parse_args(argv)

    text = compile_template(args.root, include_advisor_council=args.include_advisor_council)
    target = args.root / "templates" / ("PROMPT.md" if args.write else "PROMPT.compiled.md")
    target.write_text(text, encoding="utf-8")

    live = args.root / "templates" / "PROMPT.md"
    live_lines = len(live.read_text(encoding="utf-8").splitlines()) if live.exists() else 0
    print(f"Wrote {target.relative_to(args.root)} — {len(text.splitlines())} lines "
          f"(current live templates/PROMPT.md: {live_lines} lines).")
    if not args.write:
        print("Preview only. Diff against templates/PROMPT.md and the deployed "
              "~/.autoagent/templates/PROMPT.md, then rerun with --write to adopt.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
