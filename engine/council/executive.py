"""LLM Council — 3-stage executive pipeline.

Stage 1: multiple model-level reviewers answer independently
Stage 2: each reviewer ranks the anonymized responses
Stage 3: chairman synthesizes with full context
"""
import logging
import os
import re
from pathlib import Path
from typing import Optional

from .backends import (
    _call_claude, _call_codex, _call_gemini, _call_deepseek, _call_grok,
    _call_with_fallback, set_council_tenant, reset_council_tenant,
)

try:
    from council_usage import check_tenant_budget
except Exception:  # council_usage optional at import time
    def check_tenant_budget(tenant):  # type: ignore[misc]
        return True, "council_usage unavailable — allowed"
from .personas import EXECUTIVE_REVIEWERS, CHAIRMAN_PROMPT, PERSONAS
from context import truncate_response

try:
    from . import memory as council_memory
except Exception as _mem_exc:  # pragma: no cover
    council_memory = None
    _COUNCIL_MEMORY_IMPORT_ERROR = _mem_exc
else:
    _COUNCIL_MEMORY_IMPORT_ERROR = None

logger = logging.getLogger(__name__)


# ── Stage 1: Collect perspectives ────────────────────────────────────

def _build_executive_review_prompt(question: str, context: str, reviewer_brief: str) -> str:
    ctx = f"\n\nContext:\n{context}" if context else ""
    return (
        f"You are {reviewer_brief}. Think like a CEO-level operator who has to weigh "
        f"strategy, design, credibility, execution risk, and commercial consequences at once.\n\n"
        f"Question: {question}{ctx}\n\n"
        "Return one compact executive review with exactly these sections:\n"
        "Bull Case:\n"
        "Bear Case:\n"
        "Design / Trust:\n"
        "Pragmatic Read:\n"
        "Decision:\n\n"
        "Rules:\n"
        "- Be blunt and specific.\n"
        "- Make bull and bear arguments, then choose.\n"
        "- Judge the design and trust signal like a premium buyer would.\n"
        "- If something is weak, name the exact fix, not generic advice.\n"
        "- In Decision, end with one of: READY, CLOSE BUT FIX THESE FIRST, or NOT READY.\n"
        "- Keep the full answer under 250 words."
    )


def _collect_from_specs(question: str, context: str, specs: dict[str, dict], mode: str) -> list[dict]:
    results = []
    backend_dispatch = {
        "claude": _call_claude,
        "openai": _call_codex,
        "gemini": _call_gemini,
        "deepseek": _call_deepseek,
        "grok": _call_grok,
    }

    for key, spec in specs.items():
        if mode == "personas":
            ctx = f"\n\nContext:\n{context}" if context else ""
            prompt = f"{spec['prompt']}\n\nQuestion: {question}{ctx}\n\nRespond concisely (under 200 words)."
        else:
            prompt = _build_executive_review_prompt(question, context, spec["brief"])

        backend = spec.get("backend", "claude")
        call_fn = backend_dispatch.get(backend, _call_claude)
        response = call_fn(prompt)
        if response:
            results.append({
                "persona": key,
                "name": spec["name"],
                "response": response,
                "backend": backend,
            })
            logger.info("Council Stage 1 (%s): %s [%s] responded (%d chars)", mode, spec["name"], backend, len(response))
        else:
            logger.warning("Council Stage 1 (%s): %s [%s] returned no response — persona dropped", mode, spec["name"], backend)

    return results


def _stage1_collect(question: str, context: str = "", mode: str = "executive") -> list[dict]:
    """Collect first-pass council reviews.

    Modes:
        executive: one integrated executive review per backend/model
        personas: legacy persona fan-out
    """
    if mode == "personas":
        return _collect_from_specs(question, context, PERSONAS, mode="personas")
    return _collect_from_specs(question, context, EXECUTIVE_REVIEWERS, mode="executive")


# ── Stage 2: Anonymous peer ranking ──────────────────────────────────

def _stage2_rank(question: str, stage1_results: list[dict]) -> dict:
    """Each persona ranks the others' responses (anonymized)."""
    labels = [chr(65 + i) for i in range(len(stage1_results))]  # A, B, C
    label_map = {labels[i]: stage1_results[i]["name"] for i in range(len(stage1_results))}

    anon_block = "\n\n".join(
        f"--- Response {labels[i]} ---\n{truncate_response(r['response'], max_chars=1500)}"
        for i, r in enumerate(stage1_results)
    )

    rankings = []
    for i, result in enumerate(stage1_results):
        other_labels = [l for j, l in enumerate(labels) if j != i]
        prompt = (
            f"You are evaluating anonymous responses to this question:\n\n"
            f"Question: {question}\n\n"
            f"Here are the responses:\n{anon_block}\n\n"
            f"Evaluate each response's quality (accuracy, reasoning, actionability). "
            f"Then output your ranking in EXACTLY this format:\n\n"
            f"FINAL RANKING:\n1. Response X\n2. Response Y\n3. Response Z\n\n"
            f"Where X, Y, Z are the letters A through {labels[-1]}. Best first."
        )
        ranking_text = _call_with_fallback(
            prompt,
            backends=("claude", "openai", "gemini", "deepseek", "grok"),
            timeout=300,
        )
        parsed = _parse_ranking(ranking_text, labels)
        rankings.append({
            "evaluator": result["name"],
            "ranking_text": ranking_text,
            "parsed_ranking": parsed,
        })
        logger.info("Council Stage 2: %s ranked → %s", result["name"], parsed)

    aggregate = _aggregate_rankings(rankings, labels, label_map)

    return {
        "rankings": rankings,
        "label_map": label_map,
        "aggregate": aggregate,
    }


def _parse_ranking(text: str, labels: list[str]) -> list[str]:
    """Extract ordered labels from ranking text."""
    if "FINAL RANKING:" in text.upper():
        section = text.upper().split("FINAL RANKING:")[-1]
        found = re.findall(r'RESPONSE\s+([A-Z])', section)
        valid = [f for f in found if f in labels]
        if len(valid) >= 2:
            return valid

    found = re.findall(r'Response\s+([A-Z])', text, re.IGNORECASE)
    valid = []
    for f in found:
        f = f.upper()
        if f in labels and f not in valid:
            valid.append(f)
    return valid if len(valid) >= 2 else labels


def _aggregate_rankings(rankings: list[dict], labels: list[str],
                        label_map: dict) -> list[dict]:
    """Compute average rank position per response. Lower = better."""
    scores: dict[str, list[int]] = {l: [] for l in labels}

    for r in rankings:
        for position, label in enumerate(r["parsed_ranking"]):
            if label in scores:
                scores[label].append(position + 1)

    results = []
    for label in labels:
        positions = scores[label]
        avg = sum(positions) / len(positions) if positions else 99
        results.append({
            "label": label,
            "name": label_map.get(label, "Unknown"),
            "avg_position": round(avg, 2),
            "positions": positions,
        })

    results.sort(key=lambda x: x["avg_position"])
    return results


# ── Stage 3: Chairman synthesis ──────────────────────────────────────

def _stage3_synthesize(question: str, stage1_results: list[dict],
                       stage2: dict, chairman_prompt: str | None = None) -> str:
    """Chairman synthesizes the final answer."""
    responses_block = "\n\n".join(
        f"--- {r['name']} ---\n{truncate_response(r['response'], max_chars=1500)}"
        for r in stage1_results
    )

    agg = stage2["aggregate"]
    ranking_summary = ", ".join(
        f"{i+1}. {a['name']} (avg rank {a['avg_position']})"
        for i, a in enumerate(agg)
    )

    prompt = (
        f"{chairman_prompt or CHAIRMAN_PROMPT}\n\n"
        f"Question: {question}\n\n"
        f"Council responses:\n{responses_block}\n\n"
        f"Peer ranking (best to worst): {ranking_summary}\n\n"
        f"Synthesize the council's best thinking into a decisive recommendation."
    )

    if os.environ.get("COUNCIL_ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_API_KEY"):
        try:
            from advisor import advise
            text = advise(
                system_prompt=chairman_prompt or CHAIRMAN_PROMPT,
                task=prompt,
            )
            if text:
                return text
        except Exception as e:
            logger.warning("advisor synthesis failed, falling back: %s", e)

    return _call_with_fallback(
        prompt,
        backends=("claude", "openai", "gemini", "deepseek", "grok"),
        timeout=180,
    )


# ── Public API ───────────────────────────────────────────────────────

def convene_council(
    question: str,
    context: str = "",
    chairman_prompt: str | None = None,
    mode: str = "executive",
    project: str | None = None,
) -> dict:
    """Run a full 3-stage council on a question.

    Args:
        question: The question or decision to evaluate.
        context: Optional background context (code diff, project state, etc.)
        mode: `executive` for one integrated answer per model, `personas` for legacy fan-out.

    Returns:
        {
            "question": str,
            "stage1": [{"persona": str, "name": str, "response": str}],
            "stage2": {"rankings": [...], "aggregate": [...]},
            "synthesis": str,
            "winner": str,
            "confidence": str,  # HIGH/MEDIUM/LOW extracted from synthesis
        }
    """
    logger.info("Council convened for: %s [mode=%s]", question[:80], mode)

    # Tenant key for memory scoping + decision log. An explicit project is the
    # multi-tenant isolation boundary; fall back to the context's first line only
    # for single-tenant/back-compat callers that don't pass one.
    project_key = project or (context.split("\n")[0][:100] if context else None)

    # Hard per-tenant comped-council cap. Gate BEFORE any provider call so a
    # capped tenant burns nothing further this month. Only fires on an explicit
    # project (multi-tenant) — the context-first-line fallback is not a real
    # tenant boundary and must not gate the agency's own council.
    if project is not None:
        allowed, reason = check_tenant_budget(project)
        if not allowed:
            logger.warning("[Council] skipped — %s", reason)
            return {"question": question, "error": "tenant council budget exceeded",
                    "budget_exceeded": True, "reason": reason,
                    "confidence": "LOW", "synthesis": "", "winner": None}

    # Bind the tenant for every provider call in this run so spend is attributed
    # to (and gated per) the tenant. Reset in finally — never leak across calls.
    _tenant_token = set_council_tenant(project)
    try:
        # Pre-stage1: surface prior similar verdicts (off by default).
        # Uses recall_combined() which fuses primary (question-sim) + R4
        # analogical (context-sim) recall, deduped. R4 is gated separately so
        # the primary path can ship enabled while analogical stays off.
        # Failure here MUST NOT break the council — fall through silently.
        recall_block = ""
        recall_rows: list[dict] = []
        if council_memory is not None and council_memory.is_enabled():
            try:
                recall_rows = council_memory.recall_combined(question, context, project=project_key)
                recall_block = council_memory.format_recall_block(recall_rows)
                if recall_block:
                    logger.info("council_memory: recalled %d prior verdict(s)", len(recall_rows))
            except Exception as e:
                logger.warning("council_memory recall failed: %s: %s",
                               type(e).__name__, str(e)[:200])

        effective_context = (recall_block + "\n\n" + context) if recall_block else context

        stage1 = _stage1_collect(question, effective_context, mode=mode)
        if len(stage1) < 2:
            return {"question": question, "error": "Not enough council members responded"}

        stage2 = _stage2_rank(question, stage1)
        synthesis = _stage3_synthesize(question, stage1, stage2, chairman_prompt=chairman_prompt)

        confidence = "MEDIUM"
        for level in ("HIGH", "LOW", "MEDIUM"):
            if level in synthesis.upper()[-50:]:
                confidence = level
                break

        winner = stage2["aggregate"][0]["name"] if stage2["aggregate"] else "Unknown"

        decision_id = None
        try:
            from agency_db import log_council_decision
            decision_id = log_council_decision(
                project=project_key or "unknown",
                session_num=0, question=question[:500],
                winner=winner, confidence=confidence, synthesis=synthesis[:1000],
            )
        except Exception:
            pass

        result = {
            "question": question,
            "mode": mode,
            "stage1": stage1,
            "stage2": stage2,
            "synthesis": synthesis,
            "winner": winner,
            "confidence": confidence,
            "decision_id": decision_id,
        }

        # Post-stage3: persist verdict for future recall (off by default).
        # Best-effort — does not propagate failures.
        if council_memory is not None and council_memory.is_enabled():
            try:
                row_id = council_memory.persist(
                    question=question,
                    context=context,
                    result=result,
                    project=project_key,
                    decision_id_legacy=decision_id,
                    had_recall_block=bool(recall_block),
                    recalled_count=len(recall_rows),
                    recalled_ids=[r["id"] for r in recall_rows],
                )
                if row_id is not None:
                    result["council_memory_id"] = row_id
                    logger.info("council_memory: persisted verdict id=%s", row_id)
            except Exception as e:
                logger.warning("council_memory persist failed: %s: %s",
                               type(e).__name__, str(e)[:200])

        # Telemetry: how many prior verdicts were surfaced into stage1.
        if recall_rows:
            result["recalled_priors"] = len(recall_rows)

        return result
    finally:
        reset_council_tenant(_tenant_token)


def convene_council_with_debate(
    question: str,
    context: str = "",
    max_rounds: int = 3,
    bench_dir: Optional[Path] = None,
    task_id: Optional[str] = None,
    project: Optional[str] = None,
) -> dict:
    """Run convene_council with a debate loop. If confidence is not HIGH after
    the first synthesis, feed the draft back to personas so they can point out
    remaining disagreements, then re-rank and re-synthesize. Repeat up to
    max_rounds. If no HIGH-confidence convergence by the cap, bench the task
    for human-in-loop resolution.

    Returns the same dict as convene_council plus:
        - "status": "converged" | "benched"
        - "rounds": list of per-round {confidence, synthesis}
        - "bench_path": Path to bench file (only when status == "benched")
    """
    rounds: list[dict] = []
    final = convene_council(question, context, project=project)
    rounds.append({
        "round": 1,
        "confidence": final.get("confidence", "MEDIUM"),
        "synthesis": final.get("synthesis", ""),
    })

    for round_num in range(2, max_rounds + 1):
        if final.get("confidence") == "HIGH":
            break
        draft = final.get("synthesis", "")
        if not draft:
            break
        debate_ctx = (
            f"{context}\n\n"
            f"--- Draft consensus from round {round_num - 1} "
            f"(confidence: {final.get('confidence', 'MEDIUM')}) ---\n"
            f"{draft}\n\n"
            f"Identify the SPECIFIC points you still disagree with or that remain "
            f"underspecified. Do not restate agreement. If you agree fully, say 'CONVERGED'."
        )
        final = convene_council(question, debate_ctx, project=project)
        rounds.append({
            "round": round_num,
            "confidence": final.get("confidence", "MEDIUM"),
            "synthesis": final.get("synthesis", ""),
        })

    final["rounds"] = rounds
    if final.get("confidence") == "HIGH":
        final["status"] = "converged"
        return final

    final["status"] = "benched"
    bench_root = bench_dir or (Path(__file__).resolve().parent.parent.parent / "memory" / "benched")
    bench_root.mkdir(parents=True, exist_ok=True)
    tid = task_id or "unknown"
    _dt = __import__("datetime")
    ts = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    bench_path = bench_root / f"{ts}_{tid}.md"
    trace = "\n\n".join(
        f"### Round {r['round']} — confidence {r['confidence']}\n{r['synthesis']}"
        for r in rounds
    )
    stage1 = final.get("stage1", [])
    perspectives = "\n\n".join(
        f"**{r['name']}** ({r.get('backend', '?')}):\n{r['response'][:600]}"
        for r in stage1
    )
    bench_path.write_text(
        f"# BENCHED — council could not converge\n\n"
        f"**Task:** {tid}\n"
        f"**Question:** {question}\n"
        f"**Rounds attempted:** {len(rounds)} / {max_rounds}\n"
        f"**Final confidence:** {final.get('confidence', 'MEDIUM')}\n\n"
        f"## Debate trace\n\n{trace}\n\n"
        f"## Final perspectives\n\n{perspectives}\n\n"
        f"## Next step\n\nHuman-in-loop review + deep research required. "
        f"Once resolved, move this file to `memory/benched/resolved/` with "
        f"the decision appended.\n"
    )
    final["bench_path"] = str(bench_path)
    return final


def council_pick_task(project_name: str, ready_tasks: list[dict],
                      north_star: str = "") -> str | None:
    """Use the council to pick the highest-impact task from ready tasks.

    Only convened when 3+ tasks are ready. Returns task ID or None.
    """
    if len(ready_tasks) < 3:
        return None

    task_list = "\n".join(
        f"  [{t['id']}] {t['name']} (agent: {t.get('agent_hint') or 'auto'}, "
        f"priority: {t.get('priority', 'medium')})"
        for t in ready_tasks[:6]
    )

    result = convene_council(
        f"Which task should {project_name} work on next for maximum impact?",
        context=f"North Star:\n{north_star[:500]}\n\nReady tasks:\n{task_list}",
        project=project_name,
    )

    synthesis = result.get("synthesis", "")
    for t in ready_tasks:
        if t["id"] in synthesis or t["name"][:30] in synthesis:
            return t["id"]
    return None
