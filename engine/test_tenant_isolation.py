"""Multi-tenant isolation integration test — the "safe to onboard client N+1" proof.

Provisions two real registered projects (tenants) and asserts NO bleed across the
subsystems that share infrastructure: on-disk state, the council spend ledger,
cross-project knowledge sharing, and the destructive DB-prune path. Hermetic — no
live Postgres (council pgvector recall scoping is covered in
test_council_memory_scope).
"""
import json
from pathlib import Path

import pytest

import registry
import council_usage as cu
import db_maintenance
from self_improve_analyzers import share_knowledge_across_projects


@pytest.fixture
def two_tenants(tmp_path, monkeypatch):
    """Register two isolated tenants under a throwaway agency home."""
    home = tmp_path / "agency"
    (home / "templates" / "agents").mkdir(parents=True)
    (home / "agency.json").write_text(json.dumps({"projects": {}, "defaults": {}}))
    monkeypatch.setattr(registry, "AGENCY_HOME", home)

    ctxs = []
    for name in ("acme", "globex"):
        root = tmp_path / name
        root.mkdir()
        ctx = registry.register(name, str(root))
        ctx.memory_dir.mkdir(parents=True, exist_ok=True)
        ctxs.append(ctx)
    return ctxs


def test_on_disk_state_is_disjoint(two_tenants):
    a, b = two_tenants
    # Every per-tenant path lives under its own project_home and never overlaps.
    for pa, pb in [(a.project_home, b.project_home),
                   (a.memory_dir, b.memory_dir),
                   (a.sessions_file, b.sessions_file),
                   (a.budget_file, b.budget_file),
                   (a.agents_dir, b.agents_dir)]:
        assert pa != pb
        assert not str(pa).startswith(str(pb))
        assert not str(pb).startswith(str(pa))


def test_council_spend_ledger_is_per_tenant(tmp_path, monkeypatch, two_tenants):
    monkeypatch.setattr(cu, "_TENANT_USAGE_FILE", tmp_path / "tenant_usage.json")
    monkeypatch.setattr(cu, "_SPENDING_CONFIG_FILE", tmp_path / "spending.json")
    # acme burns to its cap; globex must be unaffected.
    cu.record_tenant_council_call("acme", 40.0)
    assert cu.get_tenant_monthly_spend("acme") == 40.0
    assert cu.get_tenant_monthly_spend("globex") == 0.0
    assert cu.check_tenant_budget("acme")[0] is False   # over cap
    assert cu.check_tenant_budget("globex")[0] is True  # untouched


def test_knowledge_does_not_bleed_between_tenants_by_default(two_tenants, monkeypatch):
    monkeypatch.delenv("AUTOAGENT_CROSS_PROJECT_SHARING", raising=False)
    a, b = two_tenants
    (a.memory_dir / "knowledge.md").write_text(
        "RULE: always run tests pass before commit\n", encoding="utf-8")
    (b.memory_dir / "knowledge.md").write_text("# Knowledge\n", encoding="utf-8")

    assert share_knowledge_across_projects() == 0        # gated off
    # globex's knowledge is untouched — acme's rule did not leak in.
    assert "tests pass" not in (b.memory_dir / "knowledge.md").read_text(encoding="utf-8").lower()


def test_db_prune_never_touches_a_registered_tenant(monkeypatch, two_tenants):
    import agency_db
    import threading
    monkeypatch.setattr(agency_db, "_DB_PATH", two_tenants[0].project_home.parent.parent / "agency.db")
    monkeypatch.setattr(agency_db, "_local", threading.local())
    # Register a tenant whose NAME looks disposable, plus a real throwaway.
    agency_db.upsert_project("acme", "/clients/acme")
    agency_db.upsert_project("demo-corp", "/clients/demo-corp")   # registered → protected
    agency_db.upsert_project("testproject", "/tmp/scratch")        # unregistered → disposable
    monkeypatch.setattr(db_maintenance, "_registered_project_names",
                        lambda: {"acme", "demo-corp"})

    result = db_maintenance.prune_test_data(apply=True)
    assert result["projects"] == ["testproject"]
    survivors = {p["name"] for p in agency_db.get_projects()}
    assert "acme" in survivors and "demo-corp" in survivors
