"""LLM Council — code review, UX review, and design council functions."""
import concurrent.futures
import logging
import os
import re
import subprocess
from pathlib import Path

from .backends import (
    _call_claude, _call_codex, _call_gemini_vision, _call_openai_vision,
)
from .personas import PERSONAS, DESIGN_REVIEW_PROMPT, _FRONTEND_EXTENSIONS

logger = logging.getLogger(__name__)


def codex_review(ctx, session_num: int, log_fn=None) -> dict:
    """Run a Codex code review on the latest commit's diff.

    Returns:
        {"status": "lgtm"|"issues"|"skipped", "review": str}
    """
    diff_result = subprocess.run(
        ["git", "diff", "HEAD~1"],
        cwd=str(ctx.project_root),
        capture_output=True, text=True, timeout=15,
    )
    diff_text = diff_result.stdout[:3000]

    if not diff_text.strip():
        return {"status": "skipped", "review": ""}

    review_prompt = (
        "You are a senior code reviewer. Review this git diff for:\n"
        "1. Bugs or logic errors\n"
        "2. Security vulnerabilities\n"
        "3. Missing edge cases\n"
        "4. Code style issues (one-liners, silent exceptions, unclear names)\n\n"
        "If the code is solid, respond with: LGTM\n"
        "If there are issues, respond with: ISSUES FOUND\n"
        "Then list each issue on its own line with the file and concern.\n"
        "Be concise — under 200 words.\n\n"
        f"```diff\n{diff_text}\n```"
    )

    review = _call_codex(review_prompt, timeout=60)
    if not review:
        return {"status": "skipped", "review": ""}

    if "ISSUES FOUND" in review.upper():
        print(f"  [Codex Review] Issues flagged:")
        for line in review.splitlines():
            if line.strip():
                print(f"    {line.strip()}")
        if log_fn:
            log_fn(
                ctx,
                f"\nRULE: [CODEX REVIEW] Session #{session_num} — "
                f"issues flagged: {review[:300]}\n",
            )
        return {"status": "issues", "review": review}

    print(f"  [Codex Review] LGTM")
    return {"status": "lgtm", "review": review}


def _has_frontend_changes(diff_text: str) -> bool:
    """Check if a git diff contains frontend file changes."""
    for line in diff_text.splitlines():
        if line.startswith("diff --git"):
            for ext in _FRONTEND_EXTENSIONS:
                if ext in line:
                    return True
    return False


def ux_review(ctx, session_num: int, log_fn=None) -> dict:
    """Run a UX-focused council review on frontend changes.

    Returns:
        {"status": "pass"|"issues"|"skipped", "review": str}
    """
    diff_result = subprocess.run(
        ["git", "diff", "HEAD~1"],
        cwd=str(ctx.project_root),
        capture_output=True, text=True, timeout=15,
    )
    diff_text = diff_result.stdout[:4000]

    if not diff_text.strip() or not _has_frontend_changes(diff_text):
        return {"status": "skipped", "review": ""}

    ux_persona = PERSONAS.get("ux", {})
    prompt = (
        f"{ux_persona.get('prompt', '')}\n\n"
        f"Review this frontend change for project '{ctx.name}'.\n"
        f"Focus on UX quality, not just code correctness.\n\n"
        f"If the UX is solid, respond with: UX PASS\n"
        f"If there are UX concerns, respond with: UX ISSUES\n"
        f"Then list each concern with a specific fix.\n"
        f"Be concise — under 200 words.\n\n"
        f"```diff\n{diff_text}\n```"
    )

    review = _call_claude(prompt, timeout=120)
    if not review:
        return {"status": "skipped", "review": ""}

    if "UX ISSUES" in review.upper():
        print(f"  [UX Review] Issues flagged:")
        for line in review.splitlines():
            if line.strip():
                print(f"    {line.strip()}")
        if log_fn:
            log_fn(
                ctx,
                f"\nRULE: [UX REVIEW] Session #{session_num} — "
                f"issues: {review[:300]}\n",
            )
        return {"status": "issues", "review": review}

    print(f"  [UX Review] PASS")
    return {"status": "pass", "review": review}


def design_council(ctx, session_num: int, screenshot_path: str = None, log_fn=None) -> dict:
    """Convene a multi-model design review on a screenshot.

    Returns:
        {"status": "pass"|"issues"|"skipped", "score": float, "reviews": list, "synthesis": str}
    """
    if not screenshot_path:
        try:
            from session_helpers import capture_screenshot
            screenshot_path = capture_screenshot(ctx, session_num)
        except Exception:
            pass

    if not screenshot_path:
        return {"status": "skipped", "score": 0, "reviews": [], "synthesis": "No screenshot available"}

    full_path = str(Path(ctx.project_home) / screenshot_path) if not os.path.isabs(screenshot_path) else screenshot_path
    if not os.path.exists(full_path):
        return {"status": "skipped", "score": 0, "reviews": [], "synthesis": f"Screenshot not found: {full_path}"}

    print(f"  [Design Council] Reviewing screenshot: {screenshot_path}", flush=True)

    reviews = []

    def review_with_model(name, call_fn):
        try:
            result = call_fn(DESIGN_REVIEW_PROMPT, full_path, timeout=120)
            return {"model": name, "review": result} if result else None
        except Exception as e:
            logger.warning("Design review %s failed: %s", name, e)
            return None

    with concurrent.futures.ThreadPoolExecutor() as pool:
        futures = []
        futures.append(pool.submit(review_with_model, "GPT-5.4", _call_openai_vision))
        futures.append(pool.submit(review_with_model, "Gemini", _call_gemini_vision))

        for f in concurrent.futures.as_completed(futures):
            result = f.result()
            if result:
                reviews.append(result)
                print(f"  [Design Council] {result['model']}:", flush=True)
                for line in result["review"].splitlines()[:5]:
                    if line.strip():
                        print(f"    {line.strip()}", flush=True)

    if not reviews:
        return {"status": "skipped", "score": 0, "reviews": [], "synthesis": "No vision models available"}

    scores = []
    for r in reviews:
        score_match = re.search(r'(\d+(?:\.\d+)?)\s*/?\s*10', r["review"])
        if score_match:
            scores.append(float(score_match.group(1)))

    avg_score = sum(scores) / len(scores) if scores else 0

    synthesis_prompt = (
        f"You are synthesizing design feedback from multiple AI reviewers.\n\n"
        f"Reviews:\n"
    )
    for r in reviews:
        synthesis_prompt += f"\n--- {r['model']} ---\n{r['review']}\n"
    synthesis_prompt += (
        f"\nCombine the reviews into a prioritized list of the top 3 actionable improvements. "
        f"Be specific — say exactly what CSS/layout/content changes to make. Under 150 words."
    )

    try:
        synthesis = _call_claude(synthesis_prompt, timeout=90)
    except Exception:
        synthesis = "Could not synthesize reviews."

    print(f"  [Design Council] Average score: {avg_score:.1f}/10", flush=True)
    if synthesis:
        print(f"  [Design Council] Synthesis:", flush=True)
        for line in synthesis.splitlines()[:5]:
            if line.strip():
                print(f"    {line.strip()}", flush=True)

    status = "pass" if avg_score >= 7.5 else "issues"

    if status == "issues" and log_fn:
        log_fn(
            ctx,
            f"\nRULE: [DESIGN COUNCIL] Session #{session_num} — "
            f"score {avg_score:.1f}/10. Top fix: {synthesis[:200]}\n",
        )

    return {
        "status": status,
        "score": avg_score,
        "reviews": reviews,
        "synthesis": synthesis,
    }
