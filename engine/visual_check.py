#!/usr/bin/env python3
"""Visual verification — agents can see their UI work via Playwright screenshots.

Post-session hook: takes screenshots of frontend pages, detects visual regressions
by comparing dimensions, broken layouts, and error states.

Wired into post_session_improve() in self_improve.py.
"""
import json
import logging
import subprocess
from pathlib import Path
from typing import Optional

from registry import ProjectContext

logger = logging.getLogger(__name__)

# Screenshots stored per project
SCREENSHOTS_DIR = ".screenshots"


def _get_app_url(ctx: ProjectContext) -> Optional[str]:
    """Determine the app URL for a project."""
    # Check if project has a known URL
    project_json = ctx.project_home / "project.json"
    if project_json.exists():
        try:
            config = json.loads(project_json.read_text(encoding="utf-8"))
            url = config.get("app_url") or config.get("url")
            if url:
                return url
        except Exception:
            pass

    # Known projects
    urls = {
        "StockCards": "https://www.stockcards.ca",
        "cultivOS": "http://localhost:8000",
        "KitchenIntelligence": "http://localhost:8000",
    }
    return urls.get(ctx.name)


def take_screenshots(ctx: ProjectContext, pages: Optional[list[str]] = None) -> list[dict]:
    """Take screenshots of frontend pages using Playwright.

    Args:
        ctx: Project context
        pages: List of URL paths to screenshot (e.g., ["/", "/admin", "/intel"])
               If None, screenshots the root page only.

    Returns list of {path, file, width, height, errors}.
    """
    url = _get_app_url(ctx)
    if not url:
        return []

    if pages is None:
        pages = ["/"]

    screenshot_dir = ctx.project_home / SCREENSHOTS_DIR
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    results = []

    script = '''
import json, sys
from playwright.sync_api import sync_playwright

url = sys.argv[1]
pages = json.loads(sys.argv[2])
output_dir = sys.argv[3]

results = []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)

    for viewport_name, width, height in [("desktop", 1440, 900), ("mobile", 390, 844)]:
        context = browser.new_context(viewport={"width": width, "height": height})
        page = context.new_page()

        errors = []
        page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)

        for path in pages:
            try:
                full_url = url.rstrip("/") + path
                page.goto(full_url, timeout=15000)
                page.wait_for_timeout(3000)

                filename = f"{path.strip('/').replace('/', '_') or 'index'}_{viewport_name}.png"
                filepath = f"{output_dir}/{filename}"
                page.screenshot(path=filepath, full_page=False)

                # Check for visual issues
                body_width = page.evaluate("document.body.scrollWidth")
                overflow = body_width > width + 5

                results.append({
                    "path": path,
                    "viewport": viewport_name,
                    "file": filepath,
                    "width": width,
                    "height": height,
                    "body_width": body_width,
                    "overflow": overflow,
                    "console_errors": len(errors),
                    "error_messages": errors[:5],
                })
                errors.clear()
            except Exception as e:
                results.append({
                    "path": path,
                    "viewport": viewport_name,
                    "error": str(e),
                })

        context.close()
    browser.close()

print(json.dumps(results))
'''

    try:
        result = subprocess.run(
            ["python3", "-c", script, url, json.dumps(pages), str(screenshot_dir)],
            capture_output=True, text=True, timeout=60
        )
        if result.stdout.strip():
            results = json.loads(result.stdout.strip())
    except subprocess.TimeoutExpired:
        logger.warning("Playwright screenshot timed out for %s", ctx.name)
    except Exception as e:
        logger.warning("Playwright screenshot failed for %s: %s", ctx.name, e)

    return results


def check_visual_regressions(ctx: ProjectContext, pages: Optional[list[str]] = None) -> dict:
    """Take screenshots and check for visual issues.

    Returns:
        {
            "ok": bool,
            "pages_checked": int,
            "issues": ["overflow on /dashboard (mobile)", ...],
            "screenshots": [...]
        }
    """
    results = take_screenshots(ctx, pages)
    issues = []

    for r in results:
        if r.get("error"):
            issues.append(f"Page {r['path']} failed to load ({r.get('viewport', '')}): {r['error'][:60]}")
            continue
        if r.get("overflow"):
            issues.append(f"Horizontal overflow on {r['path']} ({r['viewport']}): body={r['body_width']}px > viewport={r['width']}px")
        if r.get("console_errors", 0) > 0:
            issues.append(f"JS errors on {r['path']} ({r['viewport']}): {r['console_errors']} errors")

    return {
        "ok": len(issues) == 0,
        "pages_checked": len(results),
        "issues": issues,
        "screenshots": results,
    }


def post_session_visual_check(ctx: ProjectContext) -> Optional[dict]:
    """Run visual check after a session that changed frontend files.

    Only runs if the session modified .html, .css, or .js files.
    """
    # Check if recent git changes include frontend files
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD~1"],
            capture_output=True, text=True, timeout=10,
            cwd=str(ctx.project_root)
        )
        changed = result.stdout.strip().splitlines()
        frontend_changed = any(
            f.endswith((".html", ".css", ".js", ".tsx", ".jsx"))
            for f in changed
        )
    except Exception:
        frontend_changed = False

    if not frontend_changed:
        return None

    logger.info("Frontend files changed in %s — running visual check", ctx.name)
    check = check_visual_regressions(ctx)

    if not check["ok"]:
        # Notify via Telegram
        try:
            from comms import notify
            issue_text = "\n".join(f"  - {i}" for i in check["issues"][:5])
            notify(
                f"Visual issues detected after session:\n{issue_text}",
                project=ctx.name,
                agent="visual-check"
            )
        except Exception:
            pass

        # Log to knowledge.md
        kf = ctx.memory_dir / "knowledge.md"
        if kf.exists():
            entry = f"\nRULE: [VISUAL CHECK] {len(check['issues'])} visual issues: {check['issues'][0][:80]}\n"
            kf.write_text(kf.read_text(encoding="utf-8") + entry, encoding="utf-8")

    return check
