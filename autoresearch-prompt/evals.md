# Autoresearch Evals — PROMPT.md

## Target
~/.autoagent/templates/PROMPT.md — the master rules every work session reads.

## Evals

EVAL 1: TDD ordering
Question: Does the prompt explicitly require writing tests BEFORE implementation code?
Pass: A clear, unambiguous instruction says tests must be written first and must fail before implementation begins
Fail: TDD is mentioned but the ordering is ambiguous, or implementation could reasonably happen before tests

EVAL 2: Single-task enforcement
Question: Does the prompt have a mechanism to prevent scope creep (working on multiple tasks in one session)?
Pass: There is an explicit instruction to pick ONE task and a rule against starting additional tasks
Fail: The prompt allows or doesn't prevent the agent from drifting into multiple tasks

EVAL 3: Verification gate
Question: Does the prompt require an explicit VERIFICATION REPORT with pass/fail status before committing?
Pass: A structured verification block with specific fields (tests, frontend, audit) must be emitted and all must pass before commit
Fail: Verification is mentioned but not structured, or commit can happen without explicit gate

EVAL 4: Current task tracking
Question: Does the prompt require writing a step checklist to current_task.md before starting work?
Pass: A specific format is defined (task name, steps, checkboxes) and must be written BEFORE coding begins
Fail: current_task.md is mentioned but writing to it is optional or the format is undefined

EVAL 5: Memory update completeness
Question: Does the prompt define ALL required memory updates after task completion?
Pass: Explicit instructions to update: current_task.md (clear), activity_log.md (append), knowledge.md (reflexion), backlog.md (remove task), done.md (append), sessions.json (append)
Fail: Any of these 6 memory files is not mentioned in the post-task sequence

EVAL 6: Failure recovery
Question: Does the prompt have a structured approach for when tools fail or tests break?
Pass: A multi-step recovery process with hypothesis ranking, knowledge search, and a max-retry limit before logging as blocked
Fail: Failure handling is vague ("try again") or missing entirely
