"""Council memory — persistent verdicts + vector recall.

Stores every convene_council() outcome in Postgres+pgvector and surfaces
prior-similar verdicts ahead of the next stage-1 collect, so the council
stops thinking cold about questions it has already answered.

Storage: `council_episodic` on the `autoagency_memory` Postgres database
(set COUNCIL_MEMORY_DSN to point at it). Schema in
`migrations/001_council_memory.sql`. Bootstrap via
`scripts/bootstrap_council_memory.sh`.

Env knobs:
    COUNCIL_MEMORY_ENABLED       gate (default false — opt-in)
    COUNCIL_MEMORY_DSN           postgres://...autoagency_memory
    COUNCIL_MEMORY_EMBED_MODEL   default text-embedding-3-small
    COUNCIL_MEMORY_EMBED_DIM     default 1536
    COUNCIL_MEMORY_RECALL_K      default 3
    COUNCIL_MEMORY_MIN_SIM       default 0.70 (cosine, 0=orthogonal, 1=identical)
    COUNCIL_MEMORY_INJECT_BYTES  default 2048 — hard cap on recall context size
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
from contextlib import contextmanager
from typing import Any

logger = logging.getLogger(__name__)

DSN          = os.environ.get(
    "COUNCIL_MEMORY_DSN",
    # Neutral local default — set COUNCIL_MEMORY_DSN for a real deployment.
    # (No credential is shipped; the memory layer is opt-in via
    # COUNCIL_MEMORY_ENABLED and connects lazily, so this only matters when
    # enabled without a DSN, which then fails loudly at connect.)
    "postgresql://autoagency:autoagency@127.0.0.1:5432/autoagency_memory",
)
EMBED_MODEL  = os.environ.get("COUNCIL_MEMORY_EMBED_MODEL", "text-embedding-3-small")
EMBED_DIM    = int(os.environ.get("COUNCIL_MEMORY_EMBED_DIM", "1536"))
RECALL_K     = int(os.environ.get("COUNCIL_MEMORY_RECALL_K", "3"))
MIN_SIM      = float(os.environ.get("COUNCIL_MEMORY_MIN_SIM", "0.70"))
INJECT_BYTES = int(os.environ.get("COUNCIL_MEMORY_INJECT_BYTES", "2048"))

# R4 analogical defaults — see recall_analogical().
R4_Q_MAX_SIM  = float(os.environ.get("COUNCIL_MEMORY_R4_Q_MAX_SIM", "0.70"))
R4_CTX_MIN_SIM = float(os.environ.get("COUNCIL_MEMORY_R4_CTX_MIN_SIM", "0.75"))


def is_enabled() -> bool:
    """Single source of truth for the on/off gate.

    Re-read every call so tests can toggle without re-importing the module.
    """
    return os.environ.get("COUNCIL_MEMORY_ENABLED", "false").lower() in ("1", "true", "yes", "on")


def is_r4_enabled() -> bool:
    """R4 analogical traversal has its own opt-in gate independent of the
    main memory gate. Re-read every call so tests can toggle freely."""
    return os.environ.get("COUNCIL_MEMORY_R4_ENABLED", "false").lower() in ("1", "true", "yes", "on")


# ── connection pool ─────────────────────────────────────────────────────

_pool = None
_pool_lock = threading.Lock()
_openai_client = None


def _get_pool():
    global _pool
    if _pool is not None:
        return _pool
    with _pool_lock:
        if _pool is not None:
            return _pool
        try:
            from psycopg_pool import ConnectionPool
        except ImportError as e:
            raise RuntimeError(
                "psycopg + psycopg_pool required: pip install 'psycopg[binary]' psycopg_pool"
            ) from e
        _pool = ConnectionPool(
            DSN,
            min_size=1,
            max_size=4,
            kwargs={"autocommit": False},
            open=True,
        )
    return _pool


@contextmanager
def with_conn():
    pool = _get_pool()
    with pool.connection() as c:
        yield c


def _reset_pool_for_tests():
    """Test-only: drop the cached pool so a new DSN env var takes effect."""
    global _pool
    with _pool_lock:
        if _pool is not None:
            try: _pool.close()
            except Exception: pass
            _pool = None


# ── embeddings ──────────────────────────────────────────────────────────

def _get_openai():
    global _openai_client
    if _openai_client is not None:
        return _openai_client
    try:
        from openai import OpenAI
    except ImportError as e:
        raise RuntimeError("openai SDK required: pip install openai") from e
    _openai_client = OpenAI()
    return _openai_client


def embed(text: str) -> list[float]:
    """Single-text embedding. Truncates to ~32K chars (~8K tokens)."""
    text = (text or "")[:32000]
    if not text.strip():
        return [0.0] * EMBED_DIM
    resp = _get_openai().embeddings.create(model=EMBED_MODEL, input=text)
    vec = list(resp.data[0].embedding)
    if len(vec) != EMBED_DIM:
        raise RuntimeError(
            f"embedding dim mismatch: model={EMBED_MODEL} returned {len(vec)}, "
            f"schema expects {EMBED_DIM}. Re-check COUNCIL_MEMORY_EMBED_MODEL / _DIM."
        )
    return vec


def _hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8", errors="ignore")).hexdigest()


def _vec_literal(vec: list[float]) -> str:
    """Render a pgvector literal — `[0.1,0.2,...]`. Bypasses the need for a
    psycopg pgvector adapter just for two columns."""
    return "[" + ",".join(f"{v:.7f}" for v in vec) + "]"


# ── persistence ─────────────────────────────────────────────────────────

def persist(
    *,
    question: str,
    context: str,
    result: dict[str, Any],
    project: str | None = None,
    decision_id_legacy: int | None = None,
    had_recall_block: bool = False,
    recalled_count: int = 0,
    recalled_ids: list[int] | None = None,
) -> int | None:
    """Write a verdict to council_episodic. Returns the new row id, or None
    on failure (logged, never raised — persistence is best-effort).

    Telemetry columns (`had_recall_block`, `recalled_count`, `recalled_ids`)
    are wire-fed from executive.py so memory_metrics.weekly_rollup() can
    measure whether recall is actually helping convenes."""
    if not is_enabled():
        return None
    try:
        q_vec = embed(question)
        c_vec = embed(context) if context else [0.0] * EMBED_DIM
        stage1 = result.get("stage1") or []
        stage2_aggregate = ((result.get("stage2") or {}).get("aggregate")) or []
        with with_conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO council_episodic (
                    question, question_hash, context, context_hash, mode,
                    stage1, stage2_aggregate, synthesis, winner, confidence,
                    decision_id_legacy, project,
                    question_embedding, context_embedding,
                    had_recall_block, recalled_count, recalled_ids
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s::jsonb, %s::jsonb, %s, %s, %s,
                    %s, %s,
                    %s::vector, %s::vector,
                    %s, %s, %s::bigint[]
                ) RETURNING id
                """,
                (
                    question, _hash(question), context, _hash(context),
                    result.get("mode", "executive"),
                    json.dumps(stage1, default=str),
                    json.dumps(stage2_aggregate, default=str),
                    result.get("synthesis", ""),
                    result.get("winner", ""),
                    result.get("confidence", ""),
                    decision_id_legacy, project,
                    _vec_literal(q_vec), _vec_literal(c_vec),
                    had_recall_block, recalled_count, recalled_ids or [],
                ),
            )
            row_id = cur.fetchone()[0]
            conn.commit()
            return int(row_id)
    except Exception as e:
        logger.warning("council_memory.persist failed: %s: %s",
                       type(e).__name__, str(e)[:200])
        return None


# ── recall ──────────────────────────────────────────────────────────────

def recall_similar(
    question: str,
    context: str = "",
    *,
    k: int | None = None,
    min_sim: float | None = None,
    project: str | None = None,
) -> list[dict[str, Any]]:
    """Return up to k prior verdicts ranked by question cosine similarity.

    Filters out anything below `min_sim`. Same-question (exact hash) match is
    excluded so a re-run doesn't recall itself.

    `project` scopes recall to one tenant's verdicts — REQUIRED for multi-tenant
    isolation. When None, recall is unscoped (single-tenant back-compat); passing
    it None in a shared multi-tenant store leaks other tenants' verdicts.

    Empty list = no recall (cold start, no similar history, or memory disabled).
    """
    if not is_enabled():
        return []
    k = k if k is not None else RECALL_K
    min_sim = min_sim if min_sim is not None else MIN_SIM
    try:
        q_vec = embed(question)
        q_hash = _hash(question)
        with with_conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, ts, question, winner, confidence, synthesis,
                       1 - (question_embedding <=> %s::vector) AS sim
                FROM council_episodic
                WHERE question_hash <> %s
                  AND question_embedding IS NOT NULL
                  AND (%s::text IS NULL OR project = %s)
                ORDER BY question_embedding <=> %s::vector
                LIMIT %s
                """,
                (_vec_literal(q_vec), q_hash, project, project,
                 _vec_literal(q_vec), k * 2),
            )
            rows = cur.fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            sim = float(r[6])
            if sim < min_sim:
                continue
            out.append({
                "id": int(r[0]),
                "ts": r[1].isoformat() if r[1] else None,
                "question": r[2],
                "winner": r[3],
                "confidence": r[4],
                "synthesis": r[5],
                "similarity": round(sim, 4),
            })
            if len(out) >= k:
                break
        return out
    except Exception as e:
        logger.warning("council_memory.recall_similar failed: %s: %s",
                       type(e).__name__, str(e)[:200])
        return []


def recall_analogical(
    question: str,
    context: str = "",
    *,
    k: int | None = None,
    q_max_sim: float | None = None,
    c_min_sim: float | None = None,
    exclude_ids: list[int] | None = None,
    project: str | None = None,
) -> list[dict[str, Any]]:
    """R4 traversal — surface prior verdicts whose CONTEXT matches even
    when the QUESTION embedding doesn't clear the primary recall floor.

    `project` scopes recall to one tenant (see recall_similar); None = unscoped.

    From Orus interview lift #2: "skill learned days ago surfaces on an
    obliquely-related question because the situation matches." Primary
    recall_similar() can't catch this because its ORDER BY question_emb
    rejects everything below MIN_SIM.

    Gated by both COUNCIL_MEMORY_ENABLED and COUNCIL_MEMORY_R4_ENABLED so
    the primary path can ship enabled while R4 stays in observation.

    Args:
        question: the current question (embedded, used to compute
            question_similarity for filtering and reporting).
        context: the current context — REQUIRED, non-empty. Empty context
            short-circuits to [] (R4 has nothing to anchor on).
        k: result cap. Default RECALL_K.
        q_max_sim: question similarity ceiling. Rows whose question is
            MORE similar than this are excluded — they belong to primary
            recall. Default R4_Q_MAX_SIM (0.70).
        c_min_sim: context similarity floor. Default R4_CTX_MIN_SIM (0.75).
        exclude_ids: row ids to skip (typically those already returned by
            recall_similar() so the caller can present a deduped list).

    Returns:
        Rows with both `question_similarity` and `context_similarity`
        keys so the caller can distinguish R4 hits from primary recall.
    """
    if not is_enabled() or not is_r4_enabled():
        return []
    if not context or not context.strip():
        return []

    k = k if k is not None else RECALL_K
    q_max = q_max_sim if q_max_sim is not None else R4_Q_MAX_SIM
    # Re-read env on every call so monkeypatched tests see the new value.
    c_min = (c_min_sim if c_min_sim is not None
             else float(os.environ.get("COUNCIL_MEMORY_R4_CTX_MIN_SIM",
                                       str(R4_CTX_MIN_SIM))))
    exclude_ids = exclude_ids or []

    try:
        q_vec = embed(question)
        c_vec = embed(context)
        q_hash = _hash(question)
        with with_conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, ts, question, winner, confidence, synthesis,
                       1 - (question_embedding <=> %s::vector) AS q_sim,
                       1 - (context_embedding  <=> %s::vector) AS c_sim
                FROM council_episodic
                WHERE question_hash <> %s
                  AND question_embedding IS NOT NULL
                  AND context_embedding  IS NOT NULL
                  AND (NOT (%s::bigint[] && ARRAY[id]))
                  AND (%s::text IS NULL OR project = %s)
                ORDER BY context_embedding <=> %s::vector
                LIMIT %s
                """,
                (_vec_literal(q_vec), _vec_literal(c_vec), q_hash,
                 exclude_ids, project, project, _vec_literal(c_vec), k * 4),
            )
            rows = cur.fetchall()
    except Exception as e:
        logger.warning("council_memory.recall_analogical failed: %s: %s",
                       type(e).__name__, str(e)[:200])
        return []

    import math
    out: list[dict[str, Any]] = []
    for r in rows:
        q_sim, c_sim = float(r[6]), float(r[7])
        # Skip degenerate rows: zero-vector embeddings (e.g. persisted with
        # empty context) produce NaN cosine and would never pass c_min.
        if math.isnan(q_sim) or math.isnan(c_sim):
            continue
        if q_sim > q_max:
            continue  # belongs to primary recall, skip
        if c_sim < c_min:
            continue  # context not similar enough
        out.append({
            "id": int(r[0]),
            "ts": r[1].isoformat() if r[1] else None,
            "question": r[2],
            "winner": r[3],
            "confidence": r[4],
            "synthesis": r[5],
            "question_similarity": round(q_sim, 4),
            "context_similarity": round(c_sim, 4),
        })
        if len(out) >= k:
            break
    return out


def format_recall_block(rows: list[dict[str, Any]], byte_cap: int | None = None) -> str:
    """Render recall rows as a context-prepend block. Hard byte cap so we
    don't balloon stage-1 prompt cost on long syntheses.

    Accepts BOTH row shapes:
      - primary recall: `{similarity: float, ...}`
      - R4 analogical:  `{question_similarity, context_similarity, ...}`

    R4 rows get an extra `ctx=0.XX` marker so the council can weight an
    analogical hit differently from a direct question match."""
    if not rows:
        return ""
    byte_cap = byte_cap if byte_cap is not None else INJECT_BYTES
    lines: list[str] = ["## Prior similar council verdicts"]
    for r in rows:
        synth = (r.get("synthesis") or "").strip().replace("\n", " ")
        if len(synth) > 400:
            synth = synth[:400] + "…"
        # Sim marker: primary rows use `similarity`; R4 rows use the pair.
        if "similarity" in r:
            sim_marker = f"sim={r['similarity']:.2f}"
        else:
            sim_marker = (
                f"q={r.get('question_similarity', 0.0):.2f} "
                f"ctx={r.get('context_similarity', 0.0):.2f}"
            )
        lines.append(
            f"- [{sim_marker}] Q: {r['question'][:200]} "
            f"| winner: {r.get('winner') or '?'} "
            f"| confidence: {r.get('confidence') or '?'} "
            f"| synthesis: {synth}"
        )
    block = "\n".join(lines)
    if len(block.encode("utf-8")) > byte_cap:
        # Truncate by line so the cap is respected without mid-line cuts.
        kept: list[str] = [lines[0]]
        size = len(lines[0].encode("utf-8"))
        for line in lines[1:]:
            ln = len(line.encode("utf-8")) + 1
            if size + ln > byte_cap:
                kept.append("- [...truncated]")
                break
            kept.append(line)
            size += ln
        block = "\n".join(kept)
    return block


def recall_combined(
    question: str,
    context: str = "",
    *,
    k: int | None = None,
    project: str | None = None,
) -> list[dict[str, Any]]:
    """Convenience helper used by executive.py: primary recall first, then
    R4 analogical with the primary ids excluded, return one merged list.

    Order: primary rows first (direct question matches), R4 rows after
    (oblique context matches). Capped at `k` total.

    `project` scopes recall to one tenant (see recall_similar); None = unscoped.

    Empty list if the memory gate is off."""
    if not is_enabled():
        return []
    k = k if k is not None else RECALL_K
    primary = recall_similar(question, context, k=k, project=project)
    remaining = max(0, k - len(primary))
    analogical: list[dict[str, Any]] = []
    if remaining > 0 and is_r4_enabled() and context and context.strip():
        analogical = recall_analogical(
            question, context,
            k=remaining,
            exclude_ids=[r["id"] for r in primary],
            project=project,
        )
    return primary + analogical


# ── health ──────────────────────────────────────────────────────────────

def health_check() -> dict[str, Any]:
    """One-shot sanity probe — DSN reachable + schema present + vector dim
    matches. Used by the bootstrap and tests."""
    out: dict[str, Any] = {
        "enabled": is_enabled(),
        "dsn": DSN.split("@", 1)[-1],
        "embed_model": EMBED_MODEL,
        "embed_dim_expected": EMBED_DIM,
    }
    try:
        with with_conn() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM council_episodic"
            )
            out["row_count"] = int(cur.fetchone()[0])
            cur.execute(
                "SELECT atttypmod FROM pg_attribute "
                "WHERE attrelid='council_episodic'::regclass "
                "AND attname='question_embedding'"
            )
            row = cur.fetchone()
            out["embed_dim_schema"] = int(row[0]) if row else None
            if out["embed_dim_schema"] not in (None, EMBED_DIM):
                out["error"] = (
                    f"vector dim mismatch: schema={out['embed_dim_schema']} "
                    f"env={EMBED_DIM}"
                )
        out["ok"] = "error" not in out
    except Exception as e:
        out["ok"] = False
        out["error"] = f"{type(e).__name__}: {str(e)[:200]}"
    return out


__all__ = [
    "is_enabled", "is_r4_enabled",
    "embed", "persist",
    "recall_similar", "recall_analogical", "recall_combined",
    "format_recall_block", "health_check",
    "DSN", "EMBED_MODEL", "EMBED_DIM",
    "RECALL_K", "MIN_SIM",
    "R4_Q_MAX_SIM", "R4_CTX_MIN_SIM",
]
