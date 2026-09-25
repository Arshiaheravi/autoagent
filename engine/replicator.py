#!/usr/bin/env python3
"""Replicator — URL or image → design brief → build-ready handoff.

Terminal-native port of Anthropic's Claude Design (Opus 4.7 Labs).
Three phases: capture → spec → handoff.

Usage:
    from replicator import replicate
    result = replicate("https://example.com", project="myapp")
    # result: {"slug": "...", "brief_path": "...", "status": "ready|failed"}

Or via CLI:
    autoagent replicate <url-or-image> [--project NAME] [--no-wait]
"""
import json
import logging
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

AUTOAGENT_ROOT = Path(__file__).parent.parent
REPLICATE_DIR = AUTOAGENT_ROOT / "brain" / "replicate"
REPLICATE_DIR.mkdir(parents=True, exist_ok=True)

SUPPORTED_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
SUPPORTED_DOC_EXTS = {".pdf", ".docx"}


# ── Slugs ─────────────────────────────────────────────────────────────

def _slug(src: str) -> str:
    """Derive a filesystem-safe slug from URL or image path."""
    if _is_url(src):
        host = urlparse(src).netloc.replace("www.", "")
        path = urlparse(src).path.strip("/").replace("/", "-")
        base = f"{host}-{path}" if path else host
    else:
        base = Path(src).stem
    slug = re.sub(r"[^a-zA-Z0-9\-]+", "-", base).strip("-").lower()[:60]
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    return f"{slug}-{stamp}"


def _is_url(src: str) -> bool:
    return src.startswith(("http://", "https://"))


# ── Phase 1: Capture ──────────────────────────────────────────────────

def capture_url(url: str, out_dir: Path) -> dict:
    """Screenshot URL at desktop + mobile, dump DOM. Uses Playwright."""
    out_dir.mkdir(parents=True, exist_ok=True)

    script = r'''
import json, sys
from playwright.sync_api import sync_playwright

url = sys.argv[1]
out_dir = sys.argv[2]
results = {"viewports": [], "dom": "", "meta": {}}

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    for name, w, h in [("desktop", 1440, 900), ("mobile", 390, 844)]:
        ctx = browser.new_context(viewport={"width": w, "height": h})
        page = ctx.new_page()
        try:
            page.goto(url, timeout=30000, wait_until="networkidle")
        except Exception:
            page.goto(url, timeout=30000)
        page.wait_for_timeout(2000)
        shot = f"{out_dir}/{name}.png"
        page.screenshot(path=shot, full_page=True)
        results["viewports"].append({"name": name, "file": shot, "w": w, "h": h})
        if name == "desktop":
            results["dom"] = page.content()[:200000]
            results["meta"] = {
                "title": page.title(),
                "description": page.locator("meta[name=description]").first.get_attribute("content") or "",
            }
        ctx.close()
    browser.close()

print(json.dumps(results))
'''
    try:
        r = subprocess.run(
            ["python3", "-c", script, url, str(out_dir)],
            capture_output=True, text=True, timeout=120
        )
        if r.returncode != 0:
            logger.error("Playwright failed: %s", r.stderr[:300])
            return {"error": r.stderr[:300]}
        data = json.loads(r.stdout.strip())
    except subprocess.TimeoutExpired:
        return {"error": "Playwright timeout after 120s"}
    except Exception as e:
        return {"error": f"capture_url failed: {e}"}

    (out_dir / "dom.html").write_text(data.get("dom", ""), encoding="utf-8")
    (out_dir / "source.txt").write_text(url, encoding="utf-8")
    (out_dir / "meta.json").write_text(json.dumps(data.get("meta", {}), indent=2), encoding="utf-8")
    return {
        "kind": "url",
        "source": url,
        "screenshots": [v["file"] for v in data["viewports"]],
        "dom_path": str(out_dir / "dom.html"),
        "meta": data.get("meta", {}),
    }


def capture_image(image_path: str, out_dir: Path) -> dict:
    """Copy local image into the replicate workspace."""
    src = Path(image_path).expanduser().resolve()
    if not src.exists():
        return {"error": f"Image not found: {image_path}"}
    if src.suffix.lower() not in SUPPORTED_IMAGE_EXTS:
        return {"error": f"Unsupported extension: {src.suffix}"}

    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / f"reference{src.suffix.lower()}"
    dest.write_bytes(src.read_bytes())
    (out_dir / "source.txt").write_text(str(src), encoding="utf-8")
    return {
        "kind": "image",
        "source": str(src),
        "screenshots": [str(dest)],
        "dom_path": None,
        "meta": {},
    }


def capture_pdf(pdf_path: str, out_dir: Path) -> dict:
    """Copy PDF into workspace. Claude Code reads PDFs natively via @path."""
    src = Path(pdf_path).expanduser().resolve()
    if not src.exists():
        return {"error": f"PDF not found: {pdf_path}"}

    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / "reference.pdf"
    dest.write_bytes(src.read_bytes())
    (out_dir / "source.txt").write_text(str(src), encoding="utf-8")
    return {
        "kind": "pdf",
        "source": str(src),
        "screenshots": [str(dest)],  # vision call passes @path, claude reads natively
        "dom_path": None,
        "meta": {"format": "pdf"},
    }


def capture_docx(docx_path: str, out_dir: Path) -> dict:
    """Extract text from DOCX via python-docx; store alongside as context."""
    src = Path(docx_path).expanduser().resolve()
    if not src.exists():
        return {"error": f"DOCX not found: {docx_path}"}

    try:
        import docx as _docx
    except ImportError:
        return {"error": "python-docx not installed; run: pip install python-docx"}

    try:
        doc = _docx.Document(str(src))
    except Exception as e:
        return {"error": f"Failed to parse DOCX: {e}"}

    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    text = "\n\n".join(paragraphs)[:20000]

    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / "reference.docx"
    dest.write_bytes(src.read_bytes())
    (out_dir / "extracted.txt").write_text(text, encoding="utf-8")
    (out_dir / "source.txt").write_text(str(src), encoding="utf-8")
    return {
        "kind": "docx",
        "source": str(src),
        "screenshots": [],  # no vision — text-only
        "dom_path": str(out_dir / "extracted.txt"),
        "meta": {"format": "docx", "paragraphs": len(paragraphs)},
    }


def capture(src: str, out_dir: Path) -> dict:
    """Dispatch URL / image / PDF / DOCX."""
    if _is_url(src):
        return capture_url(src, out_dir)
    ext = Path(src).suffix.lower()
    if ext == ".pdf":
        return capture_pdf(src, out_dir)
    if ext == ".docx":
        return capture_docx(src, out_dir)
    return capture_image(src, out_dir)


# ── Phase 2: Spec extraction ──────────────────────────────────────────

_SPEC_SYSTEM = """You are a senior product designer and frontend architect.
You are looking at a reference design (website screenshot, social post, or image).
Your job is to produce a complete structured brief so another engineer can replicate it.

Be specific. No hedging. No "typically." Name exact colors, spacing, components.
Respond ONLY with valid JSON — no prose, no markdown fences."""

_SPEC_USER = """Extract a replication brief from the reference. Return JSON with:

- "movement": 1-2 word design philosophy (e.g. "Brutalist Joy", "Chromatic Silence")
- "layout": {"structure": "grid|flex|stacked|split", "sections": [ordered list of section names]}
- "palette": {"bg": "#hex", "surface": "#hex", "accents": ["#hex", ...], "text": "#hex", "muted": "#hex"}
- "typography": {"display": "font-family stack", "body": "...", "mono": "...", "scale_rule": "e.g. 4xl/2xl/base"}
- "components": list of {"name": str, "notes": str} — hero, nav, card, footer, etc.
- "motion": list of strings — specific animations (fade-up on scroll, hover-scale, etc.)
- "copy": {"headline": str, "subhead": str, "cta": str} — extract verbatim if visible
- "assets_needed": list of strings — logo, hero-image, icons, etc.
- "tech_stack_hint": "React+Tailwind" | "vanilla HTML+CSS" | "Next.js" | "framer-motion" etc.
- "notes": 2-3 sentence summary of what makes this design distinctive

CRITICAL OUTPUT RULES:
- Your ENTIRE response must be a single JSON object, starting with `{` and ending with `}`.
- Do NOT wrap in markdown code fences.
- Do NOT include any prose before or after the JSON.
- Do NOT say "Here is the JSON:" or "I analyzed the image".
- If unsure about a color, give your best hex estimate — do not omit fields."""


def _call_claude_vision(image_paths: list[str], extra_context: str = "") -> dict:
    """Call Claude CLI (Max plan) with image paths via @-reference. Return parsed JSON.

    Uses `claude -p` subprocess so billing goes to the Max plan, NOT the API key.
    Claude Code auto-reads files referenced with @absolute/path in the prompt.
    """
    claude = shutil.which("claude") or "claude"

    valid_paths = [str(Path(p).resolve()) for p in image_paths[:3] if Path(p).exists()]

    user_text = _SPEC_USER
    if extra_context:
        user_text = f"Additional context:\n{extra_context[:4000]}\n\n{user_text}"

    if valid_paths:
        refs = "\n".join(f"@{p}" for p in valid_paths)
        ref_header = f"Reference files to analyze:\n{refs}\n\n"
    else:
        ref_header = ""  # text-only brief (e.g. docx input)

    full_prompt = f"{_SPEC_SYSTEM}\n\n{ref_header}{user_text}"

    try:
        result = subprocess.run(
            [claude, "-p", full_prompt, "--model", "opus", "--max-turns", "6",
             "--output-format", "text"],
            capture_output=True, text=True, timeout=180,
            encoding="utf-8", errors="replace",
            cwd=str(Path.home()),
        )
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"claude -p timeout after 180s") from e

    raw = (result.stdout or "").strip()
    if not raw:
        raise RuntimeError(
            f"claude -p produced no output (exit {result.returncode}): "
            f"{(result.stderr or '')[:300]}"
        )
    if result.returncode != 0:
        logger.warning(
            "claude -p exit %s (non-fatal — likely hook noise): %s",
            result.returncode, (result.stderr or "")[:200]
        )

    # Always archive the raw response next to the screenshots for debugging
    debug_path = None
    try:
        parent = Path(valid_paths[0]).parent if valid_paths else REPLICATE_DIR
        debug_path = parent / "vision_raw.txt"
        debug_path.write_text(raw, encoding="utf-8")
    except Exception:
        pass

    # Strip markdown fences, then extract first {...} JSON object even if wrapped in prose
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    first = cleaned.find("{")
    last = cleaned.rfind("}")
    if first != -1 and last > first:
        candidate = cleaned[first:last + 1]
        return json.loads(candidate)
    raise json.JSONDecodeError(
        f"No JSON object in claude response (saved to {debug_path})",
        cleaned, 0
    )


def extract_spec(capture_data: dict) -> dict:
    """Run vision call to produce the structured brief."""
    if capture_data.get("error"):
        return {"error": capture_data["error"]}

    extra = ""
    kind = capture_data.get("kind", "")
    if capture_data.get("dom_path"):
        try:
            text = Path(capture_data["dom_path"]).read_text(encoding="utf-8")
            meta = capture_data.get("meta", {})
            if kind == "docx":
                extra = f"DOCX content (design brief / spec):\n{text[:6000]}"
            else:
                extra = (
                    f"Page title: {meta.get('title', '')}\n"
                    f"Meta description: {meta.get('description', '')}\n"
                    f"DOM excerpt (first 2000 chars):\n{text[:2000]}"
                )
        except Exception:
            pass

    try:
        spec = _call_claude_vision(capture_data["screenshots"], extra_context=extra)
    except json.JSONDecodeError as e:
        return {"error": f"Spec JSON parse failed: {e}"}
    except Exception as e:
        return {"error": f"Vision call failed: {e}"}

    spec["_source"] = capture_data["source"]
    spec["_kind"] = capture_data["kind"]
    return spec


# ── Design-system merge ───────────────────────────────────────────────

def _scan_brand_assets(project_root: Path) -> dict:
    """Discover logos, fonts, and brand images under conventional asset dirs.

    Mirrors Claude Design's onboarding scan of brand + codebase folders.
    """
    asset_dirs = [
        project_root / "public",
        project_root / "assets",
        project_root / "brand",
        project_root / "static",
        project_root / "src" / "assets",
        project_root / "frontend" / "assets",
    ]

    logos: list[str] = []
    fonts: list[str] = []
    images: list[str] = []

    logo_hints = re.compile(r"(logo|brand|mark|wordmark|icon)", re.IGNORECASE)
    font_exts = {".woff", ".woff2", ".ttf", ".otf"}
    image_exts = {".svg", ".png", ".jpg", ".jpeg", ".webp"}

    for root in asset_dirs:
        if not root.exists() or not root.is_dir():
            continue
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            ext = p.suffix.lower()
            rel = str(p.relative_to(project_root))
            if ext in font_exts:
                if len(fonts) < 20:
                    fonts.append(rel)
            elif ext in image_exts:
                if logo_hints.search(p.name):
                    if len(logos) < 10:
                        logos.append(rel)
                elif len(images) < 30:
                    images.append(rel)

    return {"logos": logos, "fonts": fonts, "images": images}


def merge_design_system(spec: dict, project_root: Path) -> dict:
    """Override palette+typography with project's existing design tokens if present.

    Mirrors Claude Design's "reads codebase for design system" behavior:
    - CSS custom properties (--token: #hex)
    - Tailwind config reference
    - Brand-asset inventory (logos, fonts, images)
    """
    if not project_root or not project_root.exists():
        return spec

    css_candidates = [
        project_root / "frontend" / "styles.css",
        project_root / "src" / "styles.css",
        project_root / "src" / "app" / "globals.css",
    ]
    for css in css_candidates:
        if not css.exists():
            continue
        text = css.read_text(encoding="utf-8")
        tokens = dict(re.findall(r"--([a-z-]+):\s*(#[0-9a-fA-F]{3,8})", text))
        if tokens:
            spec.setdefault("_design_system_source", str(css))
            spec["_project_tokens"] = tokens
            break

    tw_config = project_root / "tailwind.config.ts"
    if not tw_config.exists():
        tw_config = project_root / "tailwind.config.js"
    if tw_config.exists():
        spec["_tailwind_config"] = str(tw_config)

    brand = _scan_brand_assets(project_root)
    if brand["logos"] or brand["fonts"] or brand["images"]:
        spec["_brand_assets"] = brand

    return spec


# ── Brief writer ──────────────────────────────────────────────────────

def write_brief(spec: dict, out_dir: Path) -> Path:
    """Write human-readable brief.md + machine-readable brief.json."""
    brief_md = out_dir / "brief.md"
    brief_json = out_dir / "brief.json"

    brief_json.write_text(json.dumps(spec, indent=2), encoding="utf-8")

    if spec.get("error"):
        brief_md.write_text(f"# Replica brief — ERROR\n\n{spec['error']}\n", encoding="utf-8")
        return brief_md

    palette = spec.get("palette", {})
    typo = spec.get("typography", {})
    layout = spec.get("layout", {})
    copy = spec.get("copy", {})

    lines = [
        f"# Replica brief: {spec.get('_source', 'unknown')}",
        "",
        f"**Source kind:** {spec.get('_kind', '?')}",
        f"**Movement:** {spec.get('movement', '—')}",
        f"**Generated:** {datetime.now().isoformat(timespec='minutes')}",
        "",
        "## Notes",
        spec.get("notes", "—"),
        "",
        "## Layout",
        f"- Structure: `{layout.get('structure', '—')}`",
        f"- Sections: {', '.join(layout.get('sections', [])) or '—'}",
        "",
        "## Palette",
    ]
    for k, v in palette.items():
        if isinstance(v, list):
            lines.append(f"- {k}: {', '.join(v)}")
        else:
            lines.append(f"- {k}: `{v}`")
    lines += [
        "",
        "## Typography",
        f"- Display: {typo.get('display', '—')}",
        f"- Body: {typo.get('body', '—')}",
        f"- Mono: {typo.get('mono', '—')}",
        f"- Scale: {typo.get('scale_rule', '—')}",
        "",
        "## Components",
    ]
    for c in spec.get("components", []):
        lines.append(f"- **{c.get('name', '?')}**: {c.get('notes', '')}")
    lines += [
        "",
        "## Motion",
    ]
    for m in spec.get("motion", []):
        lines.append(f"- {m}")
    lines += [
        "",
        "## Copy",
        f"- Headline: {copy.get('headline', '—')}",
        f"- Subhead: {copy.get('subhead', '—')}",
        f"- CTA: {copy.get('cta', '—')}",
        "",
        "## Assets needed",
    ]
    for a in spec.get("assets_needed", []):
        lines.append(f"- {a}")
    lines += [
        "",
        f"**Tech stack hint:** {spec.get('tech_stack_hint', '—')}",
        "",
    ]
    if spec.get("_project_tokens"):
        lines += ["## Project design-system tokens (will override palette)", ""]
        for k, v in spec["_project_tokens"].items():
            lines.append(f"- --{k}: `{v}`")
        lines.append("")

    brand = spec.get("_brand_assets")
    if brand:
        lines += ["## Brand assets (from project scan)", ""]
        if brand.get("logos"):
            lines.append(f"**Logos ({len(brand['logos'])})**")
            for p in brand["logos"][:10]:
                lines.append(f"- `{p}`")
            lines.append("")
        if brand.get("fonts"):
            lines.append(f"**Fonts ({len(brand['fonts'])})**")
            for p in brand["fonts"][:10]:
                lines.append(f"- `{p}`")
            lines.append("")
        if brand.get("images"):
            lines.append(f"**Other images ({len(brand['images'])})** — first 10 shown")
            for p in brand["images"][:10]:
                lines.append(f"- `{p}`")
            lines.append("")

    a11y = spec.get("_a11y_review")
    if a11y:
        lines += ["## Accessibility review (WCAG AA)", "", a11y.strip(), ""]

    lines += [
        "---",
        "",
        "## Operator annotations",
        "",
        "_Edit anything above, then approve. Adjust palette, veto sections, reword copy."
        " When done, run:_ `autoagent replicate --resume <slug>`",
        "",
    ]

    brief_md.write_text("\n".join(lines), encoding="utf-8")
    return brief_md


# ── A11y review ───────────────────────────────────────────────────────

_A11Y_PROMPT = """You are an accessibility auditor reviewing a replication brief before build.
Check against WCAG 2.2 AA.

Evaluate ONLY what the brief specifies (palette, typography scale, components, motion).
Call out concrete issues — contrast ratios, touch target sizes, motion safety, focus
visibility, semantic structure. No generic advice.

Output format (markdown, under 250 words):
- **Contrast:** list any pairs likely failing 4.5:1 (body) or 3:1 (large text)
- **Motion:** flag animations that need prefers-reduced-motion fallback
- **Focus + keyboard:** components missing visible focus state
- **Semantic risk:** hero/nav/footer structure that could hurt screen-reader flow
- **Required fixes:** 3 max, each one actionable line"""


def a11y_review(spec: dict) -> str:
    """Run a separate claude -p pass for WCAG AA review. Returns markdown."""
    claude = shutil.which("claude") or "claude"

    spec_snippet = json.dumps(
        {k: v for k, v in spec.items() if not k.startswith("_")},
        indent=2,
    )[:6000]

    prompt = f"{_A11Y_PROMPT}\n\nBrief JSON:\n```json\n{spec_snippet}\n```"

    try:
        result = subprocess.run(
            [claude, "-p", prompt, "--model", "opus", "--max-turns", "2",
             "--output-format", "text"],
            capture_output=True, text=True, timeout=120,
            encoding="utf-8", errors="replace",
            cwd=str(Path.home()),
        )
    except subprocess.TimeoutExpired:
        logger.warning("a11y review timeout")
        return ""

    out = (result.stdout or "").strip()
    if not out:
        logger.info("a11y review produced no output (exit %s)", result.returncode)
    return out


# ── Phase 3: Handoff ──────────────────────────────────────────────────

def _notify_seb(message: str) -> None:
    """Best-effort Telegram notify."""
    try:
        from comms import notify
        notify(message, project="replicator", agent="replicator")
    except Exception as e:
        logger.info("Telegram notify skipped: %s", e)


def handoff(brief_path: Path, project: Optional[str] = None,
            wait_for_review: bool = True) -> dict:
    """Wire brief into agency pipeline.

    If wait_for_review: Telegram ping the operator, return pending status.
    Else: immediate council review + backlog write.
    """
    if wait_for_review:
        _notify_seb(
            f"Replica brief ready: {brief_path}\n"
            f"Edit the brief, then run: autoagent replicate --resume {brief_path.parent.name}"
        )
        return {"status": "pending_review", "brief_path": str(brief_path)}

    # Run council review
    try:
        from council import convene_council
        brief_text = brief_path.read_text(encoding="utf-8")
        result = convene_council(
            question="Review this replica brief before the agency builds it. "
                    "Flag missing details, impractical choices, or brand conflicts.",
            context=brief_text[:8000],
        )
        synthesis = result.get("synthesis", "")
    except Exception as e:
        logger.warning("Council review skipped: %s", e)
        synthesis = ""

    # Write to project backlog if project specified
    if project:
        try:
            from registry import get
            ctx = get(project)
            backlog = ctx.memory_dir / "backlog.md"
            task_line = (
                f"\n## Replicate: {brief_path.parent.name}\n"
                f"- Follow brief at {brief_path}\n"
                f"- Use `skills/replicate.md` + `skills/ui-stack.md`\n"
                f"- Council notes: {synthesis[:200]}\n"
            )
            existing = backlog.read_text(encoding="utf-8") if backlog.exists() else ""
            backlog.write_text(task_line + existing, encoding="utf-8")
        except Exception as e:
            logger.warning("Backlog write failed: %s", e)

    return {
        "status": "ready",
        "brief_path": str(brief_path),
        "council_synthesis": synthesis,
    }


# ── Top-level entry ───────────────────────────────────────────────────

def replicate(src: str, project: Optional[str] = None,
              wait_for_review: bool = True) -> dict:
    """Run the full capture → spec → handoff pipeline.

    Returns:
        {"status": "ready"|"pending_review"|"failed",
         "slug": str, "brief_path": str, "error"?: str}
    """
    slug = _slug(src)
    out_dir = REPLICATE_DIR / slug
    out_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Replicate phase 1 (capture): %s", src)
    captured = capture(src, out_dir)
    if captured.get("error"):
        return {"status": "failed", "slug": slug, "error": captured["error"]}

    logger.info("Replicate phase 2 (spec): %s", slug)
    spec = extract_spec(captured)
    if spec.get("error"):
        return {"status": "failed", "slug": slug, "error": spec["error"]}

    if project:
        try:
            from registry import get
            ctx = get(project)
            spec = merge_design_system(spec, Path(ctx.project_root))
        except Exception as e:
            logger.info("Design-system merge skipped: %s", e)

    logger.info("Replicate a11y review: %s", slug)
    try:
        a11y = a11y_review(spec)
        if a11y:
            spec["_a11y_review"] = a11y
    except Exception as e:
        logger.info("A11y review skipped: %s", e)

    brief_path = write_brief(spec, out_dir)

    logger.info("Replicate phase 3 (handoff): %s", slug)
    result = handoff(brief_path, project=project, wait_for_review=wait_for_review)
    result["slug"] = slug
    return result


def resume(slug: str, project: Optional[str] = None) -> dict:
    """Resume a replication after the operator has annotated the brief."""
    out_dir = REPLICATE_DIR / slug
    brief_path = out_dir / "brief.md"
    if not brief_path.exists():
        return {"status": "failed", "error": f"Brief not found: {brief_path}"}
    return handoff(brief_path, project=project, wait_for_review=False)
