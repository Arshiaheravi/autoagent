"""Tests for engine/judge.py — Agent-as-Judge MVP."""
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


@pytest.fixture
def tmp_project(tmp_path):
    """Minimal project structure for judge tests."""
    memory = tmp_path / "memory"
    memory.mkdir()
    return tmp_path


@pytest.fixture(autouse=True)
def _no_judge_key(monkeypatch):
    """Default every test to the CLI judge path by clearing any ambient key.

    Without this, a developer with ANTHROPIC_API_KEY exported would route the
    CLI-parsing tests through the SDK path and their subprocess mock would go
    unused. SDK/dispatch tests opt back in explicitly.
    """
    for k in ("JUDGE_ANTHROPIC_API_KEY", "COUNCIL_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(k, raising=False)


def _make_session_entry(session_id="s42", success=True, cost=0.12):
    return {
        "session": session_id,
        "type": "work",
        "success": success,
        "cost_usd": cost,
        "tests": {"before": 10, "after": 12, "status": "pass"},
    }


class TestDeterministicChecks:
    """Deterministic channel — no LLM needed."""

    def test_tests_fail_returns_reject(self, tmp_project):
        from judge import deterministic_check
        result = deterministic_check(
            tests_passed=False,
            exit_code=1,
            diff_text="some changes",
            claimed_success=True,
        )
        assert result["tests_pass"] is False
        assert result["verdict"] == "REJECT"

    def test_empty_diff_when_work_claimed_returns_reject(self, tmp_project):
        from judge import deterministic_check
        result = deterministic_check(
            tests_passed=True,
            exit_code=0,
            diff_text="",
            claimed_success=True,
        )
        assert result["diff_nonempty"] is False
        assert result["verdict"] == "REJECT"

    def test_nonzero_exit_returns_reject(self, tmp_project):
        from judge import deterministic_check
        result = deterministic_check(
            tests_passed=True,
            exit_code=1,
            diff_text="some changes",
            claimed_success=True,
        )
        assert result["exit_code"] == 1
        assert result["verdict"] == "REJECT"

    def test_all_pass_returns_pass(self, tmp_project):
        from judge import deterministic_check
        result = deterministic_check(
            tests_passed=True,
            exit_code=0,
            diff_text="some changes",
            claimed_success=True,
        )
        assert result["tests_pass"] is True
        assert result["diff_nonempty"] is True
        assert result["exit_code"] == 0
        assert result["verdict"] == "PASS"

    def test_no_tests_ran_is_not_a_reject(self, tmp_project):
        # META/BRAIN/infra sessions run no pytest suite -> tests_passed is None.
        # "No tests ran" must not be treated as "tests failed" (the false-REJECT bug).
        from judge import deterministic_check
        result = deterministic_check(
            tests_passed=None,
            exit_code=0,
            diff_text="edited PROMPT.md and a skill file",
            claimed_success=True,
        )
        assert result["tests_pass"] is None
        assert result["verdict"] == "PASS"

    def test_no_tests_but_empty_diff_still_rejects(self, tmp_project):
        # Guard the other side: no tests AND no diff while claiming success
        # is still a REJECT (nothing actually changed).
        from judge import deterministic_check
        result = deterministic_check(
            tests_passed=None,
            exit_code=0,
            diff_text="",
            claimed_success=True,
        )
        assert result["verdict"] == "REJECT"


class TestInferSessionSignals:
    """Derive judge inputs from schema-varying session.json entries."""

    def test_success_true_and_tests_pass(self):
        from judge import infer_session_signals
        sig = infer_session_signals({"success": True, "tests": {"status": "pass"}})
        assert sig == {"tests_passed": True, "exit_code": 0, "claimed_success": True}

    def test_missing_success_but_tests_pass_is_not_failure(self):
        # The real bug: some session entries omit `success` entirely. A missing
        # field must NOT be read as failure (was forcing exit_code=1 -> REJECT).
        from judge import infer_session_signals
        sig = infer_session_signals({"tests": {"status": "pass"}, "summary": "did B3"})
        assert sig["exit_code"] == 0
        assert sig["tests_passed"] is True
        assert sig["claimed_success"] is True

    def test_explicit_success_false_is_failure(self):
        from judge import infer_session_signals
        sig = infer_session_signals({"success": False, "tests": {"status": "pass"}})
        assert sig["exit_code"] == 1

    def test_failed_tests_is_failure(self):
        from judge import infer_session_signals
        sig = infer_session_signals({"tests": {"status": "fail"}})
        assert sig["exit_code"] == 1
        assert sig["tests_passed"] is False

    def test_no_tests_and_no_success_is_not_failure(self):
        # brain/infra session: no suite, no success field -> not a failure
        from judge import infer_session_signals
        sig = infer_session_signals({"type": "brain", "tests": {"status": "skip"}})
        assert sig["exit_code"] == 0
        assert sig["tests_passed"] is None


class TestCallJudgeLLM:
    """Parse the `--output-format json` envelope from the Claude CLI.

    subprocess.run is mocked, so these run WITHOUT a live CLI call — they lock
    in the parsing logic (the live CLI hop is confirmed separately from a real
    terminal; it cannot run nested inside another Claude process).
    """

    def _run(self, returncode=0, stdout="", stderr=""):
        return MagicMock(returncode=returncode, stdout=stdout, stderr=stderr)

    def test_json_envelope_success(self):
        from judge import _call_judge_llm
        envelope = json.dumps({"type": "result", "subtype": "success",
                               "is_error": False,
                               "result": '{"score": 8, "reason": "solid feature, tests included"}'})
        with patch("judge.subprocess.run", return_value=self._run(stdout=envelope)):
            r = _call_judge_llm("real diff", "built feature X")
        assert r == {"score": 8, "reason": "solid feature, tests included"}

    def test_json_envelope_with_markdown_fences_in_result(self):
        from judge import _call_judge_llm
        envelope = json.dumps({"type": "result", "subtype": "success", "is_error": False,
                               "result": '```json\n{"score": 3, "reason": "trivial"}\n```'})
        with patch("judge.subprocess.run", return_value=self._run(stdout=envelope)):
            r = _call_judge_llm("d", "s")
        assert r["score"] == 3 and r["reason"] == "trivial"

    def test_error_result_is_surfaced_not_swallowed(self):
        from judge import _call_judge_llm
        envelope = json.dumps({"type": "result", "subtype": "error_max_turns",
                               "is_error": True, "result": "hit max turns"})
        with patch("judge.subprocess.run", return_value=self._run(stdout=envelope)):
            r = _call_judge_llm("d", "s")
        assert r["score"] == 5
        assert "error result" in r["reason"] and "hit max turns" in r["reason"]

    def test_nonzero_exit_reports_stderr(self):
        from judge import _call_judge_llm
        with patch("judge.subprocess.run", return_value=self._run(returncode=1, stderr="auth failed")):
            r = _call_judge_llm("d", "s")
        assert r["score"] == 5
        assert "exit 1" in r["reason"] and "auth failed" in r["reason"]

    def test_empty_output_reported(self):
        from judge import _call_judge_llm
        with patch("judge.subprocess.run", return_value=self._run(stdout="   ")):
            r = _call_judge_llm("d", "s")
        assert r["reason"] == "judge LLM returned empty output"

    def test_plain_text_reply_fallback(self):
        # If the CLI ever returns the reply unwrapped, still parse it.
        from judge import _call_judge_llm
        with patch("judge.subprocess.run",
                   return_value=self._run(stdout='{"score": 7, "reason": "ok"}')):
            r = _call_judge_llm("d", "s")
        assert r["score"] == 7 and r["reason"] == "ok"

    def test_reply_without_json_reported(self):
        from judge import _call_judge_llm
        envelope = json.dumps({"type": "result", "subtype": "success", "is_error": False,
                               "result": "I cannot score this."})
        with patch("judge.subprocess.run", return_value=self._run(stdout=envelope)):
            r = _call_judge_llm("d", "s")
        assert r["score"] == 5 and "no JSON" in r["reason"]

    def test_timeout_reported(self):
        import subprocess
        from judge import _call_judge_llm
        with patch("judge.subprocess.run", side_effect=subprocess.TimeoutExpired("claude", 240)):
            r = _call_judge_llm("d", "s")
        assert r["reason"] == "judge LLM timed out after 240s"


class TestJudgeApiKey:
    """Key precedence: JUDGE > COUNCIL > ANTHROPIC > None."""

    def test_none_when_unset(self):
        from judge import _judge_api_key
        assert _judge_api_key() is None  # autouse fixture clears all three

    def test_judge_key_wins(self, monkeypatch):
        from judge import _judge_api_key
        monkeypatch.setenv("JUDGE_ANTHROPIC_API_KEY", "j")
        monkeypatch.setenv("COUNCIL_ANTHROPIC_API_KEY", "c")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "a")
        assert _judge_api_key() == "j"

    def test_falls_through_to_anthropic(self, monkeypatch):
        from judge import _judge_api_key
        monkeypatch.setenv("ANTHROPIC_API_KEY", "a")
        assert _judge_api_key() == "a"


class TestJudgeSDKPath:
    """In-process SDK judge — client injected, no network hop."""

    def _client(self, text):
        block = MagicMock()
        block.type = "text"
        block.text = text
        c = MagicMock()
        c.messages.create.return_value = MagicMock(content=[block])
        return c

    def test_sdk_parses_verdict_and_sends_model(self):
        from judge import _call_judge_llm_sdk
        client = self._client('{"score": 8, "reason": "solid feature, tests included"}')
        r = _call_judge_llm_sdk("real diff", "built X", "k", client=client)
        assert r == {"score": 8, "reason": "solid feature, tests included"}
        assert client.messages.create.call_args.kwargs["model"] == "claude-sonnet-5"

    def test_sdk_concatenates_multiple_text_blocks(self):
        from judge import _call_judge_llm_sdk
        b1, b2 = MagicMock(), MagicMock()
        b1.type, b1.text = "text", '{"score": 7,'
        b2.type, b2.text = "text", ' "reason": "ok"}'
        client = MagicMock()
        client.messages.create.return_value = MagicMock(content=[b1, b2])
        r = _call_judge_llm_sdk("d", "s", "k", client=client)
        assert r["score"] == 7 and r["reason"] == "ok"

    def test_sdk_api_error_returns_none_for_fallback(self):
        from judge import _call_judge_llm_sdk
        client = MagicMock()
        client.messages.create.side_effect = RuntimeError("overloaded")
        assert _call_judge_llm_sdk("d", "s", "k", client=client) is None

    def test_sdk_empty_output_returns_none_for_fallback(self):
        from judge import _call_judge_llm_sdk
        assert _call_judge_llm_sdk("d", "s", "k", client=self._client("   ")) is None

    def test_sdk_reply_without_json_is_a_verdict_not_fallback(self):
        # A reply that arrives but lacks JSON is a genuine bad verdict (score 5),
        # not an infra failure — mirror the CLI path, no fallback.
        from judge import _call_judge_llm_sdk
        r = _call_judge_llm_sdk("d", "s", "k", client=self._client("I cannot score this."))
        assert r is not None and r["score"] == 5 and "no JSON" in r["reason"]


class TestJudgeDispatch:
    """_call_judge_llm routing: SDK when key present, CLI fallback otherwise."""

    def test_no_key_uses_cli(self, monkeypatch):
        import judge
        sdk_spy = MagicMock()
        monkeypatch.setattr(judge, "_call_judge_llm_sdk", sdk_spy)
        envelope = json.dumps({"type": "result", "subtype": "success", "is_error": False,
                               "result": '{"score": 6, "reason": "cli path"}'})
        with patch("judge.subprocess.run",
                   return_value=MagicMock(returncode=0, stdout=envelope, stderr="")):
            r = judge._call_judge_llm("d", "s")  # autouse fixture => no key
        assert r == {"score": 6, "reason": "cli path"}
        sdk_spy.assert_not_called()

    def test_key_present_uses_sdk_and_skips_cli(self, monkeypatch):
        import judge
        monkeypatch.setattr(judge, "_judge_api_key", lambda: "k")
        monkeypatch.setattr(judge, "_call_judge_llm_sdk",
                            lambda *a, **k: {"score": 9, "reason": "sdk path"})
        cli_spy = MagicMock()
        monkeypatch.setattr(judge, "_call_judge_llm_cli", cli_spy)
        r = judge._call_judge_llm("d", "s")
        assert r == {"score": 9, "reason": "sdk path"}
        cli_spy.assert_not_called()

    def test_sdk_failure_falls_back_to_cli(self, monkeypatch):
        import judge
        monkeypatch.setattr(judge, "_judge_api_key", lambda: "k")
        monkeypatch.setattr(judge, "_call_judge_llm_sdk", lambda *a, **k: None)
        monkeypatch.setattr(judge, "_call_judge_llm_cli",
                            lambda *a, **k: {"score": 4, "reason": "cli fallback"})
        assert judge._call_judge_llm("d", "s") == {"score": 4, "reason": "cli fallback"}


class TestRubricScore:
    """Rubric scoring — mocked LLM call."""

    def test_low_score_returns_reject(self):
        from judge import apply_rubric
        with patch("judge._call_judge_llm", return_value={"score": 2, "reason": "no real work"}):
            result = apply_rubric(diff_text="trivial change", session_summary="did stuff")
        assert result["score"] == 2
        assert result["verdict"] == "REJECT"

    def test_borderline_returns_escalate(self):
        from judge import apply_rubric
        with patch("judge._call_judge_llm", return_value={"score": 5, "reason": "unclear value"}):
            result = apply_rubric(diff_text="medium change", session_summary="some work")
        assert result["score"] == 5
        assert result["verdict"] == "ESCALATE"

    def test_high_score_returns_accept(self):
        from judge import apply_rubric
        with patch("judge._call_judge_llm", return_value={"score": 8, "reason": "solid feature"}):
            result = apply_rubric(diff_text="good changes", session_summary="built feature X")
        assert result["score"] == 8
        assert result["verdict"] == "ACCEPT"


class TestJudgeSession:
    """Full judge_session integration — both channels combined."""

    def test_deterministic_fail_overrides_rubric(self, tmp_project):
        from judge import judge_session
        with patch("judge._call_judge_llm", return_value={"score": 9, "reason": "great"}):
            verdict = judge_session(
                session_id="s1",
                diff_text="some code",
                tests_passed=False,
                exit_code=1,
                claimed_success=True,
                session_summary="did great work",
            )
        assert verdict["verdict"] == "REJECT"
        assert verdict["disagreement"] is True  # agent claimed success but judge rejected

    def test_full_accept(self, tmp_project):
        from judge import judge_session
        with patch("judge._call_judge_llm", return_value={"score": 8, "reason": "solid"}):
            verdict = judge_session(
                session_id="s2",
                diff_text="real changes here",
                tests_passed=True,
                exit_code=0,
                claimed_success=True,
                session_summary="built feature",
            )
        assert verdict["verdict"] == "ACCEPT"
        assert verdict["disagreement"] is False

    def test_escalate_on_borderline(self, tmp_project):
        from judge import judge_session
        with patch("judge._call_judge_llm", return_value={"score": 5, "reason": "meh"}):
            verdict = judge_session(
                session_id="s3",
                diff_text="some changes",
                tests_passed=True,
                exit_code=0,
                claimed_success=True,
                session_summary="did some stuff",
            )
        assert verdict["verdict"] == "ESCALATE"

    def test_disagreement_flagged_when_agent_claims_success_but_rejected(self, tmp_project):
        from judge import judge_session
        with patch("judge._call_judge_llm", return_value={"score": 2, "reason": "nothing useful"}):
            verdict = judge_session(
                session_id="s4",
                diff_text="tiny change",
                tests_passed=True,
                exit_code=0,
                claimed_success=True,
                session_summary="completed task",
            )
        assert verdict["verdict"] == "REJECT"
        assert verdict["disagreement"] is True
        assert verdict["agent_self_claim"] is True


class TestWriteVerdict:
    """Verdict persistence to JSONL."""

    def test_write_verdict_appends_jsonl(self, tmp_path):
        from judge import write_verdict
        verdict = {
            "session_id": "s99",
            "verdict": "ACCEPT",
            "deterministic": {"tests_pass": True, "exit_code": 0, "diff_nonempty": True},
            "rubric": {"score": 8, "reason": "good"},
            "agent_self_claim": True,
            "disagreement": False,
        }
        outfile = tmp_path / "judge_verdicts.jsonl"
        write_verdict(verdict, outfile)
        lines = outfile.read_text().strip().split("\n")
        assert len(lines) == 1
        parsed = json.loads(lines[0])
        assert parsed["session_id"] == "s99"
        assert parsed["verdict"] == "ACCEPT"

        # Second write appends
        write_verdict(verdict, outfile)
        lines = outfile.read_text().strip().split("\n")
        assert len(lines) == 2
