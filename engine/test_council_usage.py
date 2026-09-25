"""Unit tests for council_usage.check_provider_budget — the hard spend gate."""

import council_usage as cu


# ── check_provider_budget ──────────────────────────────────────────

def test_under_budget_allowed(monkeypatch):
    monkeypatch.setattr(cu, "get_budgets", lambda: {"openai": 50.0})
    monkeypatch.setattr(cu, "get_provider_spending",
                        lambda period="month": {"openai": {"cost_usd": 12.0}})
    ok, reason = cu.check_provider_budget("openai")
    assert ok is True
    assert "12.00" in reason and "50.00" in reason


def test_over_budget_blocked(monkeypatch):
    monkeypatch.setattr(cu, "get_budgets", lambda: {"openai": 50.0})
    monkeypatch.setattr(cu, "get_provider_spending",
                        lambda period="month": {"openai": {"cost_usd": 50.0}})
    ok, reason = cu.check_provider_budget("openai")
    assert ok is False
    assert "over budget" in reason


def test_no_spend_recorded_allowed(monkeypatch):
    monkeypatch.setattr(cu, "get_budgets", lambda: {"gemini": 20.0})
    monkeypatch.setattr(cu, "get_provider_spending", lambda period="month": {})
    ok, _ = cu.check_provider_budget("gemini")
    assert ok is True


def test_unknown_provider_fails_open(monkeypatch):
    monkeypatch.setattr(cu, "get_budgets", lambda: {"openai": 50.0})
    ok, reason = cu.check_provider_budget("bogus")
    assert ok is True
    assert "no budget defined" in reason


def test_gate_error_fails_open(monkeypatch):
    def boom():
        raise RuntimeError("config corrupt")
    monkeypatch.setattr(cu, "get_budgets", boom)
    ok, reason = cu.check_provider_budget("openai")
    assert ok is True
    assert "gate error" in reason


# ── check_tenant_budget — per-tenant comped-council cap ────────────────

def _isolate_tenant_file(monkeypatch, tmp_path):
    monkeypatch.setattr(cu, "_TENANT_USAGE_FILE", tmp_path / "tenant.json")
    monkeypatch.setattr(cu, "_SPENDING_CONFIG_FILE", tmp_path / "spending.json")


def test_tenant_none_allowed_and_no_ledger(monkeypatch, tmp_path):
    _isolate_tenant_file(monkeypatch, tmp_path)
    ok, reason = cu.check_tenant_budget(None)
    assert ok is True and "single-tenant" in reason
    cu.record_tenant_council_call(None, 5.0)  # no-op
    assert not (tmp_path / "tenant.json").exists()


def test_tenant_under_cap_allowed(monkeypatch, tmp_path):
    _isolate_tenant_file(monkeypatch, tmp_path)
    cu.record_tenant_council_call("acme", 12.0)
    ok, reason = cu.check_tenant_budget("acme")
    assert ok is True
    assert "12.00" in reason and "40.00" in reason


def test_tenant_over_cap_blocked(monkeypatch, tmp_path):
    _isolate_tenant_file(monkeypatch, tmp_path)
    cu.record_tenant_council_call("acme", 40.0)
    ok, reason = cu.check_tenant_budget("acme")
    assert ok is False
    assert "over council cap" in reason


def test_tenant_spend_accumulates_within_month(monkeypatch, tmp_path):
    _isolate_tenant_file(monkeypatch, tmp_path)
    cu.record_tenant_council_call("acme", 10.0)
    cu.record_tenant_council_call("acme", 15.5)
    assert cu.get_tenant_monthly_spend("acme") == 25.5


def test_tenant_ledger_isolated_per_tenant(monkeypatch, tmp_path):
    _isolate_tenant_file(monkeypatch, tmp_path)
    cu.record_tenant_council_call("acme", 40.0)
    cu.record_tenant_council_call("globex", 1.0)
    assert cu.check_tenant_budget("acme")[0] is False
    assert cu.check_tenant_budget("globex")[0] is True  # not leaked across tenants


def test_tenant_cap_override_from_config(monkeypatch, tmp_path):
    _isolate_tenant_file(monkeypatch, tmp_path)
    (tmp_path / "spending.json").write_text('{"tenant_council_cap": 10.0}', encoding="utf-8")
    cu.record_tenant_council_call("acme", 10.0)
    assert cu.check_tenant_budget("acme")[0] is False  # over the lowered cap


def test_tenant_gate_error_fails_open(monkeypatch, tmp_path):
    _isolate_tenant_file(monkeypatch, tmp_path)

    def boom(*a, **k):
        raise RuntimeError("ledger corrupt")
    monkeypatch.setattr(cu, "get_tenant_monthly_spend", boom)
    ok, reason = cu.check_tenant_budget("acme")
    assert ok is True
    assert "gate error" in reason


def test_record_council_call_attributes_to_tenant(monkeypatch, tmp_path):
    _isolate_tenant_file(monkeypatch, tmp_path)
    monkeypatch.setattr(cu, "_COUNCIL_USAGE_FILE", tmp_path / "global.json")
    # opus-4-8 = $5/$25 per 1M; 1M in + 1M out = $30
    cu.record_council_call("claude-opus-4-8", 1_000_000, 1_000_000, tenant="acme")
    assert cu.get_tenant_monthly_spend("acme") == 30.0


def test_record_council_call_without_tenant_leaves_ledger_empty(monkeypatch, tmp_path):
    _isolate_tenant_file(monkeypatch, tmp_path)
    monkeypatch.setattr(cu, "_COUNCIL_USAGE_FILE", tmp_path / "global.json")
    cu.record_council_call("claude-opus-4-8", 1_000_000, 1_000_000)
    assert not (tmp_path / "tenant.json").exists()
