"""Tests for opportunity_scanner — spot what's missing in projects."""
import textwrap
from pathlib import Path

from opportunity_scanner import (
    scan_opportunities,
    format_opportunity_as_backlog,
    _detect_stale_backlog,
    _detect_north_star_gaps,
)


def _write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text), encoding="utf-8")


# -- scan_opportunities integration ------------------------------------------

def test_opportunity_scanner_generates_tasks(tmp_path):
    """With realistic project data, scanner produces at least 1 opportunity."""
    proj = tmp_path / ".autoagent"
    proj.mkdir()
    mem = proj / "memory"
    mem.mkdir()

    _write(proj / "NORTH_STAR.md", """\
        # North Star
        ## Success Metrics
        | Metric | Current | Target | Trend |
        |--------|---------|--------|-------|
        | API endpoints | 5 | 10+ | 50% |
        | WhatsApp integration | none | voice-first MVP | blocked |
    """)
    _write(mem / "backlog.md", """\
        # Backlog
        ## 2026-03-20
        ### 1. Build user onboarding flow
        - acceptance: test_onboarding_works
    """)
    _write(mem / "done.md", """\
        # done
        ## 2026-04-01
        - **[SESSION #50] Added NDVI endpoint** — 3 new tests
    """)
    _write(mem / "activity_log.md", """\
        # activity log
        ## 2026-04-01 — FEATURE
        DONE: Added NDVI endpoint
    """)

    results = scan_opportunities(tmp_path, today="2026-04-03")
    assert len(results) >= 1
    # Each result has EARS structure
    for r in results:
        assert "trigger" in r
        assert "action" in r
        assert "acceptance" in r
        assert "category" in r


# -- stale backlog detection --------------------------------------------------

def test_stale_backlog_detected(tmp_path):
    """Backlog items older than threshold produce a stale-backlog opportunity."""
    backlog_md = tmp_path / "backlog.md"
    _write(backlog_md, """\
        # Backlog
        ## 2026-03-15
        ### 1. Build reporting dashboard
        - acceptance: test_reporting_works
        ### 2. Add CSV export
        - acceptance: test_csv_export
    """)

    stale = _detect_stale_backlog(backlog_md, today="2026-04-03", threshold_days=7)
    assert len(stale) >= 1
    assert any("reporting" in s["action"].lower() or "csv" in s["action"].lower() for s in stale)


def test_date_in_task_title_does_not_corrupt_section_date(tmp_path):
    """A date inside a task title must NOT be read as a section date header.

    Before the fix, `### 2. ... 2026-04-02 ...` was parsed as a date header,
    overwriting current_date with a recent date so the older task under the
    real 2026-03-15 header stopped being flagged as stale."""
    backlog_md = tmp_path / "backlog.md"
    _write(backlog_md, """\
        # Backlog
        ## 2026-03-15
        ### 1. Investigate the 2026-04-02 outage regression
        - acceptance: test_outage
    """)
    stale = _detect_stale_backlog(backlog_md, today="2026-04-20", threshold_days=7)
    # The task sits under 2026-03-15 (36 days old) → must be flagged despite the
    # 2026-04-02 date embedded in its title.
    assert len(stale) == 1
    assert "outage" in stale[0]["action"].lower()


def test_stale_backlog_not_triggered_when_recent(tmp_path):
    """Backlog items within threshold don't get flagged."""
    backlog_md = tmp_path / "backlog.md"
    _write(backlog_md, """\
        # Backlog
        ## 2026-04-02
        ### 1. Fresh task added yesterday
        - acceptance: test_fresh
    """)

    stale = _detect_stale_backlog(backlog_md, today="2026-04-03", threshold_days=7)
    assert len(stale) == 0


# -- north star gap detection -------------------------------------------------

def test_north_star_gap_detected(tmp_path):
    """Unmet North Star metrics produce gap opportunities."""
    ns_md = tmp_path / "NORTH_STAR.md"
    _write(ns_md, """\
        # North Star
        ## Success Metrics
        | Metric | Current | Target | Trend |
        |--------|---------|--------|-------|
        | API endpoints | 12 | 10+ | TARGET MET |
        | WhatsApp integration | none | voice-first MVP | blocked |
        | Data pipelines | 2 | 5 | 40% |
    """)

    done_md = tmp_path / "done.md"
    _write(done_md, """\
        # done
        ## 2026-04-01
        - **[SESSION #50] Added API endpoint** — 2 tests
    """)

    gaps = _detect_north_star_gaps(ns_md, done_md)
    assert len(gaps) >= 1
    # Should flag unmet metrics, not met ones
    categories = [g["action"].lower() for g in gaps]
    assert not any("api endpoints" in c for c in categories)  # already met
    assert any("whatsapp" in c or "pipeline" in c for c in categories)


def test_north_star_all_met(tmp_path):
    """When all metrics are met, no gaps returned."""
    ns_md = tmp_path / "NORTH_STAR.md"
    _write(ns_md, """\
        # North Star
        ## Success Metrics
        | Metric | Current | Target | Trend |
        |--------|---------|--------|-------|
        | Tests | 500 | 50+ | TARGET MET |
        | Endpoints | 15 | 10+ | TARGET MET |
    """)

    done_md = tmp_path / "done.md"
    _write(done_md, "# done\n")

    gaps = _detect_north_star_gaps(ns_md, done_md)
    assert len(gaps) == 0


# -- empty inputs -------------------------------------------------------------

def test_no_false_positives_on_empty(tmp_path):
    """Empty/missing inputs produce empty output — no crashes."""
    proj = tmp_path / ".autoagent"
    proj.mkdir()
    mem = proj / "memory"
    mem.mkdir()
    # Write minimal files
    _write(proj / "NORTH_STAR.md", "# North Star\n")
    _write(mem / "backlog.md", "# Backlog\n")
    _write(mem / "done.md", "# done\n")
    _write(mem / "activity_log.md", "# activity log\n")

    results = scan_opportunities(tmp_path, today="2026-04-03")
    assert results == []


def test_no_crash_on_missing_files(tmp_path):
    """Scanner handles missing files gracefully."""
    proj = tmp_path / ".autoagent"
    proj.mkdir()
    (proj / "memory").mkdir()
    # No files written at all

    results = scan_opportunities(tmp_path, today="2026-04-03")
    assert results == []


# -- format helper ------------------------------------------------------------

def test_format_opportunity_as_backlog():
    """Renders an opportunity dict into valid EARS-formatted markdown."""
    opp = {
        "trigger": "When backlog has stale items older than 14 days",
        "action": "Prioritize or remove stale reporting dashboard task",
        "acceptance": "test_stale_items_resolved",
        "scope": "memory/backlog.md",
        "category": "stale-backlog",
    }
    result = format_opportunity_as_backlog(opp)
    assert "### " in result  # markdown heading
    assert opp["trigger"] in result
    assert opp["acceptance"] in result
    assert "stale" in result.lower()
