#!/usr/bin/env python3
"""Council API usage tracking — per-model token consumption and cost estimation.

Tracks every council call across OpenAI, Gemini, DeepSeek, and Anthropic API.
Separate from usage.py which tracks Claude CLI (Max plan) sessions.

Storage: ~/.autoagent/council_usage.json
Format: {
    "2026-04-10": {
        "gpt-4o":            {"input_tokens": 1200, "output_tokens": 400, "calls": 3, "cost_usd": 0.007},
        "gemini-2.5-flash":  {"input_tokens": 800,  "output_tokens": 300, "calls": 2, "cost_usd": 0.0003},
        "deepseek-chat":     {"input_tokens": 600,  "output_tokens": 200, "calls": 1, "cost_usd": 0.0004},
        "claude-sonnet-5":   {"input_tokens": 900,  "output_tokens": 350, "calls": 2, "cost_usd": 0.008},
    }
}

Monthly budget defaults (USD) — override via ~/.autoagent/spending_config.json:
    openai: 50, gemini: 20, deepseek: 10, anthropic: 30
"""
import json
import logging
from datetime import date, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

# Per-model pricing in USD per 1M tokens. Keep keys matching exactly what
# `_record_usage(model=...)` writes — any backend call that uses a model
# name missing from this table will silently log $0 cost.
#
# Pricing refreshed 2026-07-07 to the current Claude family (Fable 5 /
# Opus 4.8 / Sonnet 5 / Haiku 4.5) plus the other providers the operator
# routes through the council. Older `claude-opus-4-6/4-7` / `claude-sonnet-4-6`
# entries retained for backwards compat with historical council_usage.json rows.
# NOTE: Opus-tier is $5/$25 (not $15/$75 — that was an Opus-3-era error that
# inflated estimated spend ~3x and tripped the budget gate early).
MODEL_PRICING: dict[str, dict[str, float]] = {
    # ── OpenAI ──
    "gpt-4o":             {"input": 2.50,  "output": 10.00},
    "gpt-5.5":            {"input": 5.00,  "output": 15.00},

    # ── Anthropic ──
    "claude-haiku-4-5":   {"input": 1.00,  "output": 5.00},
    "claude-sonnet-5":    {"input": 3.00,  "output": 15.00},
    "claude-sonnet-4-6":  {"input": 3.00,  "output": 15.00},
    "claude-opus-4-8":    {"input": 5.00,  "output": 25.00},
    "claude-opus-4-7":    {"input": 5.00,  "output": 25.00},
    "claude-opus-4-6":    {"input": 5.00,  "output": 25.00},
    "claude-fable-5":     {"input": 10.00, "output": 50.00},
    # API responses sometimes echo a long model id — alias for back-compat.
    "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},

    # ── Google Gemini ──
    "gemini-flash-lite":  {"input": 0.075, "output": 0.30},
    "gemini-2.5-flash":   {"input": 0.15,  "output": 0.60},
    "gemini-2.5-pro":     {"input": 1.25,  "output": 10.00},

    # ── DeepSeek ──
    "deepseek-chat":      {"input": 0.27,  "output": 1.10},
    "deepseek-reasoner":  {"input": 0.55,  "output": 2.19},

    # ── xAI Grok ──
    "grok-3":             {"input": 3.00,  "output": 15.00},
    "grok-4":             {"input": 5.00,  "output": 15.00},
}

# Default monthly budgets per provider (USD).
DEFAULT_BUDGETS: dict[str, float] = {
    "openai":    50.0,
    "gemini":    20.0,
    "deepseek":  10.0,
    "anthropic": 30.0,
    "xai":       20.0,
}

# Comped-council spend cap per TENANT per calendar month (USD). Signed product
# decision for Agentric: every tenant gets council access on the house up to
# this ceiling, then the gate blocks further council calls for that tenant until
# the month rolls over. Override via spending_config.json "tenant_council_cap".
# The provider budgets above protect the operator's *total* API spend; this cap
# protects per-tenant margin — the two gates stack.
DEFAULT_TENANT_COUNCIL_CAP: float = 40.0

# Map model names to provider buckets. Any unknown model lands in "other"
# (see `get_provider_spending` — explicit so a typo in a backend doesn't
# silently disappear from rollups).
MODEL_PROVIDER: dict[str, str] = {
    # ── OpenAI ──
    "gpt-4o":             "openai",
    "gpt-5.5":            "openai",
    # ── Anthropic ──
    "claude-haiku-4-5":   "anthropic",
    "claude-sonnet-5":    "anthropic",
    "claude-sonnet-4-6":  "anthropic",
    "claude-opus-4-8":    "anthropic",
    "claude-opus-4-7":    "anthropic",
    "claude-opus-4-6":    "anthropic",
    "claude-fable-5":     "anthropic",
    "claude-sonnet-4-20250514": "anthropic",
    # ── Google Gemini ──
    "gemini-flash-lite":  "gemini",
    "gemini-2.5-flash":   "gemini",
    "gemini-2.5-pro":     "gemini",
    # Some Gemini API responses prefix with the API namespace.
    "gemini:gemini-2.5-pro":   "gemini",
    "gemini:gemini-2.5-flash": "gemini",
    # ── DeepSeek ──
    "deepseek-chat":      "deepseek",
    "deepseek-reasoner":  "deepseek",
    # ── xAI Grok ──
    "grok-3":             "xai",
    "grok-4":             "xai",
}


def _normalize_model_key(model: str) -> str:
    """Strip provider namespace prefixes some APIs add (e.g.
    'gemini:gemini-2.5-pro' → 'gemini-2.5-pro'). Keeps the pricing /
    provider lookups robust against minor format drift."""
    if not model:
        return model
    if ":" in model:
        # 'gemini:gemini-2.5-pro' → 'gemini-2.5-pro'
        head, tail = model.split(":", 1)
        if tail.startswith(head + "-") or tail == head:
            return tail
        return tail
    return model

_COUNCIL_USAGE_FILE = Path.home() / ".autoagent" / "council_usage.json"
_SPENDING_CONFIG_FILE = Path.home() / ".autoagent" / "spending_config.json"
# Tenant-scoped comped-council ledger. Kept separate from the global
# council_usage.json so the existing global rollups stay untouched (single
# source of truth for each surface): global = operator's total API spend,
# tenant = per-tenant comped-council spend for the $40/mo cap.
# Shape: {tenant: {"YYYY-MM": {"cost_usd": float, "calls": int}}}
_TENANT_USAGE_FILE = Path.home() / ".autoagent" / "council_tenant_usage.json"


def _load() -> dict:
    if not _COUNCIL_USAGE_FILE.exists():
        return {}
    try:
        return json.loads(_COUNCIL_USAGE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(data: dict):
    _COUNCIL_USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _COUNCIL_USAGE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate cost in USD given token counts and model pricing.

    Logs a warning the first time a model has no pricing entry so silent
    $0 rows don't become permanent dark matter in the budget surface.
    """
    key = _normalize_model_key(model)
    pricing = MODEL_PRICING.get(key)
    if not pricing:
        if key not in _missing_pricing_warned:
            _missing_pricing_warned.add(key)
            logger.warning(
                "[CouncilUsage] no pricing entry for model %r — "
                "cost will be logged as $0. Add an entry in MODEL_PRICING.",
                key,
            )
        return 0.0
    cost = (input_tokens / 1_000_000) * pricing["input"]
    cost += (output_tokens / 1_000_000) * pricing["output"]
    return round(cost, 6)


# One-shot warning suppression: don't spam the log on every call for a
# missing model — only the first time per process.
_missing_pricing_warned: set[str] = set()


def record_council_call(model: str, input_tokens: int, output_tokens: int,
                        cost_usd: float = 0.0, tenant: str | None = None):
    """Record token usage from a single council API call.

    Args:
        model: Model name (e.g. 'gpt-5.5', 'deepseek-reasoner').
        input_tokens: Prompt/input token count.
        output_tokens: Completion/output token count.
        cost_usd: Actual cost if provided by the API; else estimated from
            the pricing table.
        tenant: When set, the same cost is also attributed to this tenant's
            monthly comped-council ledger for the $40/mo cap. None (agency
            /single-tenant) touches only the global ledger.
    """
    if input_tokens == 0 and output_tokens == 0:
        return

    # Normalize early so all subsequent rollups key consistently.
    model = _normalize_model_key(model)

    if cost_usd == 0.0:
        cost_usd = _estimate_cost(model, input_tokens, output_tokens)

    # Attribute to the tenant ledger too (best-effort — a tenant-ledger write
    # failure must not lose the global-ledger record below).
    if tenant:
        try:
            record_tenant_council_call(tenant, cost_usd)
        except Exception as e:
            logger.warning("[CouncilUsage] tenant ledger write failed for %s: %s", tenant, e)

    today = str(date.today())
    data = _load()

    if today not in data:
        data[today] = {}

    day = data[today]
    if model not in day:
        day[model] = {"input_tokens": 0, "output_tokens": 0,
                      "calls": 0, "cost_usd": 0.0}

    entry = day[model]
    entry["input_tokens"] += input_tokens
    entry["output_tokens"] += output_tokens
    entry["calls"] += 1
    entry["cost_usd"] = round(entry["cost_usd"] + cost_usd, 6)

    _save(data)
    logger.debug(
        "[CouncilUsage] %s: %d in + %d out = est $%.5f",
        model, input_tokens, output_tokens, cost_usd,
    )


def get_budgets() -> dict[str, float]:
    """Load monthly budgets from spending_config.json, falling back to defaults."""
    if _SPENDING_CONFIG_FILE.exists():
        try:
            cfg = json.loads(_SPENDING_CONFIG_FILE.read_text(encoding="utf-8"))
            return {k: cfg.get(k, DEFAULT_BUDGETS[k]) for k in DEFAULT_BUDGETS}
        except Exception:
            pass
    return dict(DEFAULT_BUDGETS)


def check_provider_budget(provider: str, period: str = "month") -> tuple[bool, str]:
    """Hard pre-call budget gate for a provider.

    Compares this period's spend against the monthly budget. Intended to be
    called BEFORE a provider API call so council usage can be exposed to any
    caller (MCP clients, supervisors, CLI) without unbounded burn.

    Fail-OPEN by design: unknown provider, missing budget, or any internal
    error returns allowed=True. A bug in the gate must never brick the
    council — it only ever blocks when it can prove spend >= budget.

    Args:
        provider: bucket name (openai/gemini/deepseek/anthropic/xai).
        period: comparison window; must match the budget window (monthly).

    Returns:
        (allowed, reason). reason is human-readable for logging.
    """
    try:
        budgets = get_budgets()
        limit = budgets.get(provider)
        if limit is None:
            return True, f"no budget defined for {provider!r} — allowed"
        spent = get_provider_spending(period).get(provider, {}).get("cost_usd", 0.0)
        if spent >= limit:
            return False, f"{provider} over budget: ${spent:.2f} >= ${limit:.2f} ({period})"
        return True, f"{provider} ok: ${spent:.2f} / ${limit:.2f} ({period})"
    except Exception as e:  # never brick the council on a gate bug
        logger.warning("[CouncilUsage] budget gate error for %s, failing open: %s", provider, e)
        return True, f"gate error ({type(e).__name__}) — allowed"


# ── tenant-scoped comped-council ledger ($40/tenant/month cap) ──────────────

def _month_key(d: date | None = None) -> str:
    """Calendar-month bucket key, e.g. '2026-07'."""
    d = d or date.today()
    return f"{d.year:04d}-{d.month:02d}"


def _load_tenant() -> dict:
    if not _TENANT_USAGE_FILE.exists():
        return {}
    try:
        return json.loads(_TENANT_USAGE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_tenant(data: dict):
    _TENANT_USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _TENANT_USAGE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def get_tenant_council_cap() -> float:
    """Monthly per-tenant comped-council cap (USD). spending_config.json
    'tenant_council_cap' overrides the signed $40 default."""
    if _SPENDING_CONFIG_FILE.exists():
        try:
            cfg = json.loads(_SPENDING_CONFIG_FILE.read_text(encoding="utf-8"))
            val = cfg.get("tenant_council_cap")
            if isinstance(val, (int, float)) and val > 0:
                return float(val)
        except Exception:
            pass
    return DEFAULT_TENANT_COUNCIL_CAP


def record_tenant_council_call(tenant: str, cost_usd: float, calls: int = 1):
    """Attribute comped-council spend to one tenant's current-month bucket.

    No-op when tenant is falsy (single-tenant / agency-internal council) or the
    cost is non-positive, so the agency's own council never accretes a phantom
    tenant ledger.
    """
    if not tenant or cost_usd <= 0:
        return
    month = _month_key()
    data = _load_tenant()
    trow = data.setdefault(tenant, {})
    mrow = trow.setdefault(month, {"cost_usd": 0.0, "calls": 0})
    mrow["cost_usd"] = round(mrow["cost_usd"] + cost_usd, 6)
    mrow["calls"] += calls
    _save_tenant(data)


def get_tenant_monthly_spend(tenant: str, month: str | None = None) -> float:
    """This tenant's comped-council spend for the given month (default: now)."""
    if not tenant:
        return 0.0
    month = month or _month_key()
    return float(_load_tenant().get(tenant, {}).get(month, {}).get("cost_usd", 0.0))


def check_tenant_budget(tenant: str | None) -> tuple[bool, str]:
    """Hard pre-call gate for one tenant's monthly comped-council cap.

    Mirrors check_provider_budget's contract exactly:
      - tenant None/empty → allowed (single-tenant / agency-internal council).
      - Fail-OPEN on any internal error: a gate bug must never brick a paying
        tenant's product — it only blocks when it can PROVE spend >= cap.
      - Blocks only when this month's spend is already at/over the cap.

    Returns (allowed, human-readable reason).
    """
    if not tenant:
        return True, "no tenant — allowed (single-tenant)"
    try:
        cap = get_tenant_council_cap()
        spent = get_tenant_monthly_spend(tenant)
        if spent >= cap:
            return False, f"tenant {tenant!r} over council cap: ${spent:.2f} >= ${cap:.2f} (month)"
        return True, f"tenant {tenant!r} ok: ${spent:.2f} / ${cap:.2f} (month)"
    except Exception as e:  # never brick a tenant on a gate bug
        logger.warning("[CouncilUsage] tenant gate error for %s, failing open: %s", tenant, e)
        return True, f"tenant gate error ({type(e).__name__}) — allowed"


def get_spending(period: str = "week") -> dict:
    """Aggregate council spending by model for the given period.

    Args:
        period: 'today', 'week', or 'month' (last 30 days)

    Returns dict keyed by model name with: input_tokens, output_tokens, calls, cost_usd
    """
    data = _load()
    today = date.today()

    if period == "today":
        days = 1
    elif period == "week":
        days = 7
    else:  # month
        days = 30

    totals: dict[str, dict] = {}

    for i in range(days):
        day_str = str(today - timedelta(days=i))
        if day_str not in data:
            continue
        for model, entry in data[day_str].items():
            if model not in totals:
                totals[model] = {"input_tokens": 0, "output_tokens": 0, "calls": 0, "cost_usd": 0.0}
            t = totals[model]
            t["input_tokens"] += entry.get("input_tokens", 0)
            t["output_tokens"] += entry.get("output_tokens", 0)
            t["calls"] += entry.get("calls", 0)
            t["cost_usd"] = round(t["cost_usd"] + entry.get("cost_usd", 0.0), 6)

    return totals


def get_provider_spending(period: str = "month") -> dict[str, dict]:
    """Aggregate spending by provider bucket (openai/gemini/deepseek/anthropic).

    Returns dict: {provider: {cost_usd, calls, models: [...]}}
    """
    model_totals = get_spending(period)
    providers: dict[str, dict] = {}

    for model, totals in model_totals.items():
        provider = MODEL_PROVIDER.get(_normalize_model_key(model), "other")
        if provider not in providers:
            providers[provider] = {"cost_usd": 0.0, "calls": 0, "models": []}
        p = providers[provider]
        p["cost_usd"] = round(p["cost_usd"] + totals["cost_usd"], 6)
        p["calls"] += totals["calls"]
        p["models"].append({"model": model, **totals})

    return providers


def get_memory_layer_metrics(period: str = "week") -> dict:
    """Surface the council memory layer rollup alongside cost/usage.

    Returns the same shape as council.memory_metrics.weekly_rollup() so
    a dashboard can display recall_rate + verdict_stability_pct next to
    spend. Failure (memory layer not installed / DB down) returns an
    empty placeholder rather than raising — the cost tracker must keep
    working even if memory is offline.
    """
    if period == "today":
        days = 1
    elif period == "month":
        days = 30
    else:
        days = 7
    try:
        from council.memory_metrics import weekly_rollup
        return weekly_rollup(days=days)
    except Exception as e:
        logger.warning("[CouncilUsage] memory_layer metrics unavailable: %s: %s",
                       type(e).__name__, str(e)[:200])
        return {
            "days": days, "convenes_total": 0, "convenes_with_recall": 0,
            "recall_rate": 0.0, "verdict_stability_pct": 0.0,
            "repeat_questions": 0, "avg_recalled_count": 0.0,
            "error": f"{type(e).__name__}: {str(e)[:100]}",
        }
