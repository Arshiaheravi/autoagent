"""Agent-as-Judge — external session verifier.

Two-channel verdict: deterministic checks (tests, exit code, diff) +
rubric-scored LLM review. Runs as independent evaluator with no shared
context from the session being graded.
"""
import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Rubric model — same tier the CLI path uses, kept in one place for both paths.
JUDGE_MODEL = "claude-sonnet-5"

RUBRIC_PROMPT = """You are a code review judge. Score this session diff 0-10.

Criteria:
- 0-3: No meaningful work, trivial/broken changes, or reverted commits
- 4-6: Partial work, unclear value, possible regressions
- 7-10: Clear feature/fix, tests included, production-ready

Session summary: {summary}

Diff:
```
{diff}
```

Respond with ONLY valid JSON: {{"score": N, "reason": "one sentence"}}"""


def deterministic_check(
    tests_passed: bool | None,
    exit_code: int,
    diff_text: str,
    claimed_success: bool,
) -> dict[str, Any]:
    # tests_passed is tri-state: True = ran + passed, False = ran + failed,
    # None = no test suite ran (META/BRAIN/infra sessions). Only a genuine
    # FAILURE rejects; "no tests" must not be conflated with "tests failed",
    # or every non-code session gets a false REJECT.
    diff_nonempty = bool(diff_text and diff_text.strip())
    tests_failed = tests_passed is False
    checks = {
        "tests_pass": tests_passed,
        "exit_code": exit_code,
        "diff_nonempty": diff_nonempty,
    }
    if tests_failed or exit_code != 0 or (claimed_success and not diff_nonempty):
        checks["verdict"] = "REJECT"
    else:
        checks["verdict"] = "PASS"
    return checks


def _judge_api_key() -> str | None:
    """API key for the fast in-process SDK judge, or None to use the CLI path.

    Opt-in by design. The loop's session claude is billed via the Max plan
    through the `claude` CLI (OAuth in ~/.claude, no env key), and the CLI judge
    rides that same free auth. An SDK call instead bills API rates, so it only
    activates when a key is explicitly set. Precedence lets the judge reuse the
    council key without introducing a new secret.
    """
    return (os.environ.get("JUDGE_ANTHROPIC_API_KEY")
            or os.environ.get("COUNCIL_ANTHROPIC_API_KEY")
            or os.environ.get("ANTHROPIC_API_KEY")
            or None)


def _parse_rubric_reply(reply: str) -> dict[str, Any]:
    """Extract {"score", "reason"} from a model reply. Shared by both judge paths.

    Fail-loud: a reply with no JSON or unparseable JSON returns the borderline
    score 5 with the real reason, never a swallowed exception.
    """
    start = reply.find("{")
    end = reply.rfind("}") + 1
    if start < 0 or end <= start:
        return {"score": 5, "reason": f"judge LLM reply had no JSON: {reply[:120]}"}
    try:
        parsed = json.loads(reply[start:end])
    except json.JSONDecodeError as e:
        return {"score": 5, "reason": f"judge LLM JSON parse error: {e}"}
    try:
        score = int(parsed.get("score", 5))
    except (TypeError, ValueError):
        score = 5
    reason = str(parsed.get("reason", "")).strip() or "no reason given"
    return {"score": score, "reason": reason}


def _call_judge_llm_sdk(diff_text: str, session_summary: str, api_key: str,
                        client: Any = None) -> dict[str, Any] | None:
    """Grade a session diff via an in-process Anthropic SDK call.

    ~10s versus the CLI path's ~120s (a nested `claude -p` cold-start, measured
    117.7s on 2026-07-05 with no concurrent session claude — the cost is CLI
    spawn + inference, not OAuth contention). Returns the parsed rubric on
    success, or None on any INFRASTRUCTURE failure (SDK import/init, API error,
    empty output) so the caller falls back to the CLI path instead of pinning
    every verdict at 5. A reply that arrives but lacks JSON is a genuine (bad)
    verdict, not an infra failure, so it is parsed and returned like the CLI path.
    """
    prompt = RUBRIC_PROMPT.format(summary=session_summary, diff=diff_text[:8000])
    if client is None:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
        except Exception as e:  # import or client init
            logger.warning("judge SDK init failed, falling back to CLI: %s", e)
            return None
    try:
        resp = client.messages.create(
            model=JUDGE_MODEL,
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        reply = "".join(
            getattr(b, "text", "") for b in resp.content
            if getattr(b, "type", None) == "text"
        ).strip()
    except Exception as e:  # API error / malformed response
        logger.warning("judge SDK call failed, falling back to CLI: %s", e)
        return None
    if not reply:
        logger.warning("judge SDK returned empty output, falling back to CLI")
        return None
    return _parse_rubric_reply(reply)


def _call_judge_llm_cli(diff_text: str, session_summary: str) -> dict[str, Any]:
    """Grade a session diff via a fresh, headless Claude CLI call.

    Mirrors the proven-working session invocation in run.py: headless `-p`
    with `--dangerously-skip-permissions`, `--output-format json`, and stdin
    closed. The `json` format is the one run.py exercises successfully in the
    real loop; the CLI *default* format was what hung until the 60s timeout, so
    every verdict fell back to borderline. `json` wraps the reply as
    `{"type":"result","result":"<text>", "is_error":bool, ...}` — we pull
    `.result` out (and tolerate a plain-text reply as a fallback).

    Free path: rides the `claude` CLI's Max-plan OAuth (no API key). Slow —
    ~120s cold-start — so it is the fallback when no judge API key is set.

    Fails LOUD: on any failure the REAL reason (timeout / non-zero exit +
    stderr / error-result / empty output / no-JSON / parse error) is returned
    in `reason`, so a persistent failure is diagnosable from
    judge_verdicts.jsonl instead of a single opaque string. Never swallows it.
    """
    prompt = RUBRIC_PROMPT.format(summary=session_summary, diff=diff_text[:8000])
    # timeout is generous: the nested `claude -p` cold-start alone runs ~120s
    # (measured 117.7s). A short timeout was the original silent failure; 240s
    # lets the real call complete. The SDK path (_call_judge_llm_sdk) avoids
    # this entirely when a judge key is configured.
    try:
        result = subprocess.run(
            ["claude", "-p", prompt,
             "--model", JUDGE_MODEL,
             "--max-turns", "1",
             "--dangerously-skip-permissions",
             "--output-format", "json"],
            capture_output=True, text=True, timeout=240,
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired:
        return {"score": 5, "reason": "judge LLM timed out after 240s"}
    except Exception as e:  # surface, do not swallow
        return {"score": 5, "reason": f"judge LLM errored: {type(e).__name__}: {e}"}

    if result.returncode != 0:
        err = (result.stderr or result.stdout or "").strip().replace("\n", " ")
        return {"score": 5, "reason": f"judge LLM exit {result.returncode}: {err[:160] or 'no output'}"}

    raw = (result.stdout or "").strip()
    if not raw:
        return {"score": 5, "reason": "judge LLM returned empty output"}

    # Unwrap the --output-format json envelope; fall back to raw stdout if the
    # CLI ever emits the reply as plain text instead.
    reply = raw
    try:
        wrapper = json.loads(raw)
    except json.JSONDecodeError:
        wrapper = None
    if isinstance(wrapper, dict) and ("result" in wrapper or "is_error" in wrapper or "subtype" in wrapper):
        if wrapper.get("is_error") or wrapper.get("subtype") not in (None, "success"):
            detail = str(wrapper.get("result") or wrapper.get("subtype") or "error")
            return {"score": 5, "reason": f"judge LLM error result: {detail[:160]}"}
        reply = str(wrapper.get("result", raw))

    return _parse_rubric_reply(reply)


def _call_judge_llm(diff_text: str, session_summary: str) -> dict[str, Any]:
    """Grade a session diff. Fast SDK path when a judge key is set, else CLI.

    See _judge_api_key for why the SDK path is opt-in. On any SDK infrastructure
    failure the CLI path runs, so a misconfigured key degrades latency, never
    correctness.
    """
    key = _judge_api_key()
    if key:
        sdk = _call_judge_llm_sdk(diff_text, session_summary, key)
        if sdk is not None:
            return sdk
    return _call_judge_llm_cli(diff_text, session_summary)


def apply_rubric(diff_text: str, session_summary: str) -> dict[str, Any]:
    llm_result = _call_judge_llm(diff_text, session_summary)
    score = llm_result.get("score", 5)
    reason = llm_result.get("reason", "")
    if score < 4:
        verdict = "REJECT"
    elif score <= 6:
        verdict = "ESCALATE"
    else:
        verdict = "ACCEPT"
    return {"score": score, "reason": reason, "verdict": verdict}


def infer_session_signals(session_entry: dict[str, Any]) -> dict[str, Any]:
    """Derive judge inputs from a sessions.json entry whose schema VARIES.

    Some entries omit `success` entirely (brain/infra runs) and some run no
    test suite (`status` = "skip"/absent). The absence of a field is NEVER a
    failure signal — only an explicit `success is False` or a failed suite
    (`status == "fail"`) counts as failure. Reading a missing `success` as
    failure was making the judge REJECT legit sessions at the deterministic
    stage, short-circuiting the rubric so the LLM channel never ran.

    Returns the tri-state tests_passed (True/False/None), an exit_code that is
    1 only on a real failure signal, and a claimed_success flag.
    """
    tests_status = (session_entry.get("tests") or {}).get("status")
    tests_passed = (
        True if tests_status == "pass"
        else False if tests_status == "fail"
        else None
    )
    success = session_entry.get("success")
    failed = (success is False) or (tests_status == "fail")
    claimed = bool(success) if success is not None else (tests_passed is True)
    return {
        "tests_passed": tests_passed,
        "exit_code": 1 if failed else 0,
        "claimed_success": claimed,
    }


def judge_session(
    session_id: str,
    diff_text: str,
    tests_passed: bool,
    exit_code: int,
    claimed_success: bool,
    session_summary: str,
) -> dict[str, Any]:
    det = deterministic_check(tests_passed, exit_code, diff_text, claimed_success)

    if det["verdict"] == "REJECT":
        final_verdict = "REJECT"
        rubric = {"score": 0, "reason": "deterministic check failed", "verdict": "REJECT"}
    else:
        rubric = apply_rubric(diff_text, session_summary)
        final_verdict = rubric["verdict"]

    disagreement = (claimed_success and final_verdict == "REJECT") or \
                   (not claimed_success and final_verdict == "ACCEPT")

    return {
        "session_id": session_id,
        "deterministic": {k: v for k, v in det.items() if k != "verdict"},
        "rubric": {k: v for k, v in rubric.items() if k != "verdict"},
        "verdict": final_verdict,
        "agent_self_claim": claimed_success,
        "disagreement": disagreement,
    }


def write_verdict(verdict: dict[str, Any], outfile: Path) -> None:
    outfile.parent.mkdir(parents=True, exist_ok=True)
    with outfile.open("a", encoding="utf-8") as f:
        f.write(json.dumps(verdict) + "\n")
