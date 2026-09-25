"""Unit tests for council.reviews — codex_review, ux_review, design_council."""

import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import council.reviews as cr


# ── _has_frontend_changes ──────────────────────────────────────────

def test_has_frontend_changes_detects_html():
    diff = "diff --git a/templates/index.html b/templates/index.html\n+<div>new</div>"
    assert cr._has_frontend_changes(diff) is True


def test_has_frontend_changes_detects_css():
    diff = "diff --git a/static/style.css b/static/style.css\n+body{color:red}"
    assert cr._has_frontend_changes(diff) is True


def test_has_frontend_changes_detects_js():
    diff = "diff --git a/app.js b/app.js\n+console.log('hi')"
    assert cr._has_frontend_changes(diff) is True


def test_has_frontend_changes_detects_tsx():
    diff = "diff --git a/Component.tsx b/Component.tsx\n+export default"
    assert cr._has_frontend_changes(diff) is True


def test_has_frontend_changes_false_for_python():
    diff = "diff --git a/main.py b/main.py\n+print('hi')"
    assert cr._has_frontend_changes(diff) is False


def test_has_frontend_changes_false_for_empty():
    assert cr._has_frontend_changes("") is False


# ── codex_review ───────────────────────────────────────────────────

def _mock_ctx(project_root="/tmp/proj"):
    ctx = MagicMock()
    ctx.project_root = project_root
    ctx.name = "test-project"
    ctx.project_home = project_root
    return ctx


def test_codex_review_skipped_on_empty_diff():
    ctx = _mock_ctx()
    fake_result = MagicMock(stdout="")
    with patch("council.reviews.subprocess.run", return_value=fake_result):
        result = cr.codex_review(ctx, 1)
    assert result["status"] == "skipped"


def test_codex_review_lgtm():
    ctx = _mock_ctx()
    fake_diff = MagicMock(stdout="+def foo(): pass\n-def bar(): pass")
    with patch("council.reviews.subprocess.run", return_value=fake_diff), \
         patch.object(cr, "_call_codex", return_value="LGTM — code looks good."):
        result = cr.codex_review(ctx, 1)
    assert result["status"] == "lgtm"


def test_codex_review_issues_found():
    ctx = _mock_ctx()
    fake_diff = MagicMock(stdout="+unsafe_eval(input)")
    log_calls = []
    with patch("council.reviews.subprocess.run", return_value=fake_diff), \
         patch.object(cr, "_call_codex",
                      return_value="ISSUES FOUND\nLine 5: unsafe eval"):
        result = cr.codex_review(ctx, 1, log_fn=lambda c, t: log_calls.append(t))
    assert result["status"] == "issues"
    assert "ISSUES FOUND" in result["review"].upper()
    assert len(log_calls) == 1


def test_codex_review_skipped_when_codex_returns_empty():
    ctx = _mock_ctx()
    fake_diff = MagicMock(stdout="+some code")
    with patch("council.reviews.subprocess.run", return_value=fake_diff), \
         patch.object(cr, "_call_codex", return_value=""):
        result = cr.codex_review(ctx, 1)
    assert result["status"] == "skipped"


# ── ux_review ──────────────────────────────────────────────────────

def test_ux_review_skipped_no_frontend():
    ctx = _mock_ctx()
    fake_diff = MagicMock(stdout="diff --git a/main.py b/main.py\n+code")
    with patch("council.reviews.subprocess.run", return_value=fake_diff):
        result = cr.ux_review(ctx, 1)
    assert result["status"] == "skipped"


def test_ux_review_skipped_empty_diff():
    ctx = _mock_ctx()
    fake_diff = MagicMock(stdout="")
    with patch("council.reviews.subprocess.run", return_value=fake_diff):
        result = cr.ux_review(ctx, 1)
    assert result["status"] == "skipped"


def test_ux_review_pass():
    ctx = _mock_ctx()
    fake_diff = MagicMock(stdout="diff --git a/index.html b/index.html\n+<div>")
    with patch("council.reviews.subprocess.run", return_value=fake_diff), \
         patch.object(cr, "_call_claude", return_value="UX PASS — looks good"):
        result = cr.ux_review(ctx, 1)
    assert result["status"] == "pass"


def test_ux_review_issues():
    ctx = _mock_ctx()
    fake_diff = MagicMock(stdout="diff --git a/style.css b/style.css\n+tiny font")
    log_calls = []
    with patch("council.reviews.subprocess.run", return_value=fake_diff), \
         patch.object(cr, "_call_claude",
                      return_value="UX ISSUES\nFont too small for mobile"):
        result = cr.ux_review(ctx, 1, log_fn=lambda c, t: log_calls.append(t))
    assert result["status"] == "issues"
    assert len(log_calls) == 1


def test_ux_review_skipped_when_claude_returns_empty():
    ctx = _mock_ctx()
    fake_diff = MagicMock(stdout="diff --git a/app.js b/app.js\n+code")
    with patch("council.reviews.subprocess.run", return_value=fake_diff), \
         patch.object(cr, "_call_claude", return_value=""):
        result = cr.ux_review(ctx, 1)
    assert result["status"] == "skipped"


# ── design_council ─────────────────────────────────────────────────

def test_design_council_skipped_no_screenshot():
    ctx = _mock_ctx()
    with patch("council.reviews.capture_screenshot", side_effect=ImportError, create=True):
        result = cr.design_council(ctx, 1)
    assert result["status"] == "skipped"
    assert "No screenshot" in result["synthesis"]


def test_design_council_skipped_file_not_found(tmp_path):
    ctx = _mock_ctx(project_root=str(tmp_path))
    result = cr.design_council(ctx, 1, screenshot_path="/nonexistent/shot.png")
    assert result["status"] == "skipped"
    assert "not found" in result["synthesis"]


def test_design_council_pass_high_score(tmp_path):
    ctx = _mock_ctx(project_root=str(tmp_path))
    img = tmp_path / "shot.png"
    img.write_bytes(b"\x89PNG fake")

    with patch.object(cr, "_call_openai_vision",
                      return_value="Great design. 8.5/10. Minor spacing fix."), \
         patch.object(cr, "_call_gemini_vision",
                      return_value="Clean layout. 9/10. Nice work."), \
         patch.object(cr, "_call_claude", return_value="Top fixes: spacing"):
        result = cr.design_council(ctx, 1, screenshot_path=str(img))
    assert result["status"] == "pass"
    assert result["score"] >= 7.5
    assert len(result["reviews"]) == 2


def test_design_council_issues_low_score(tmp_path):
    ctx = _mock_ctx(project_root=str(tmp_path))
    img = tmp_path / "shot.png"
    img.write_bytes(b"\x89PNG fake")
    log_calls = []

    with patch.object(cr, "_call_openai_vision",
                      return_value="Poor contrast. 4/10."), \
         patch.object(cr, "_call_gemini_vision",
                      return_value="Misaligned. 5/10."), \
         patch.object(cr, "_call_claude", return_value="Fix contrast"):
        result = cr.design_council(ctx, 1, screenshot_path=str(img),
                                    log_fn=lambda c, t: log_calls.append(t))
    assert result["status"] == "issues"
    assert result["score"] < 7.5
    assert len(log_calls) == 1


def test_design_council_no_vision_models(tmp_path):
    ctx = _mock_ctx(project_root=str(tmp_path))
    img = tmp_path / "shot.png"
    img.write_bytes(b"\x89PNG fake")

    with patch.object(cr, "_call_openai_vision", return_value=""), \
         patch.object(cr, "_call_gemini_vision", return_value=""):
        result = cr.design_council(ctx, 1, screenshot_path=str(img))
    assert result["status"] == "skipped"
    assert "No vision models" in result["synthesis"]


def test_design_council_no_score_in_review(tmp_path):
    ctx = _mock_ctx(project_root=str(tmp_path))
    img = tmp_path / "shot.png"
    img.write_bytes(b"\x89PNG fake")

    with patch.object(cr, "_call_openai_vision",
                      return_value="Looks decent, no major issues"), \
         patch.object(cr, "_call_gemini_vision", return_value=""), \
         patch.object(cr, "_call_claude", return_value="ok"):
        result = cr.design_council(ctx, 1, screenshot_path=str(img))
    assert result["score"] == 0
