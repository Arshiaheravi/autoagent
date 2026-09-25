# Skill: Testing

## RULES
- Write tests ALONGSIDE the feature — not after
- One test per branch (if/elif/else) minimum
- Run `PYTHONPATH="$PWD/src" pytest tests/ --collect-only -q` first — catches import errors before full run
- Test command: use the project's test command from PROJECT.md, run from the project root, with per-session basetemp isolation (e.g. `pytest -q --basetemp=/tmp/pytest-$$`)
- **Per-session basetemp isolation** (MANDATORY when concurrent sessions may be running): append `--basetemp=/tmp/pytest-$$` (or `/tmp/pytest-<session-num>`) so concurrent pytest runs don't thrash a shared tmpdir. Session #340 skipped the full suite because two other pytests were competing for `.pytest_cache` / default tmp, and session #342 fixed it with per-session basetemp. Without this, concurrent sessions cascade into flaky fixtures and sessions skip the non-regression gate citing "pytest thrashing" — which silently disables one of the two mandatory commit checks. (Source: sessions #340 + #341 META + #342 follow-up)

## TEST-FIRST SPECIFICATION (evals-as-specs pattern)
Before writing any feature code, write out in plain English what the tests will verify:
```
# Tests for [feature]:
# 1. returns X when input is Y (happy path)
# 2. returns Z when edge case W occurs
# 3. does NOT return P when guard condition Q is false
```
This takes 60 seconds and catches scope drift before you write a line of production code.
The test list becomes the acceptance criteria — if all 3 pass, the feature is done.

## PATCHING — MOST COMMON SOURCE OF FAILURES
- ALWAYS patch at the namespace where the name is looked up
- If route does `from myapp.services.X import func` → patch `myapp.api.routefile.func`
- NOT `myapp.services.X.func` — that's the wrong binding
- Patch the guard function, not the third-party symbol
- (Use the current project's actual module paths — the `myapp.*` names are illustrative.)

### Intra-function imports
When ANY function uses `from module import func` INSIDE the function body:
- The import runs at call time, looking up `func` from `module` directly
- The calling module NEVER holds a reference to `func`
- CORRECT: patch `myapp.services.weather_client.fetch_weather`
- WRONG: patch `myapp.api.weather.fetch_weather` (if the import is inside the function)
- Rule: trace the import statement to its origin module, patch there

### Float formatting in test assertions
- `:.0f` uses banker's rounding in Python: 112.51 → "113", not "112"
- Safer: assert a substring that doesn't depend on rounding

## TEST FIXTURES
- Follow the project's existing conftest.py / fixture conventions — read them before adding fixtures.
- For nested resources (child under parent under grandparent), create parent entities first in test setup, in the order the existing tests use.

### MANDATORY: verify ORM columns BEFORE writing fixtures
Before writing ANY model constructor call in a test, grep the project's ORM models file for the actual column names. Do not trust memory — guessed column names have burned past sessions. Common traps:
- Columns are often named differently than you'd guess (e.g. `status`/`total_amount` vs `state`/`amount`) — verify against the model.
- `nullable=False` columns must be populated in the fixture.
Fast check: `grep -n "= Column" <project models file>` scoped to the table, or read the class directly. One grep saves a full debug cycle.

## TEST STRUCTURE — FROM ECC TDD SKILL
- **One assert per test**: Each test verifies exactly one behavior. Multiple asserts hide which one failed.
- **Arrange-Act-Assert (AAA)**: Set up → call the function → assert output. One blank line between sections.
- **Independent tests**: No test shares mutable state with another. Each test creates its own fixtures.
- **Test user-visible behavior, not implementation details**: Assert what a function returns, not which internal method it calls.

## FAIL-BEFORE VERIFICATION (mandatory in TDD)
After writing tests and BEFORE writing any implementation, run the test file to confirm tests FAIL:
```bash
PYTHONPATH="$PWD/src" pytest tests/test_X.py -v
```
Expected result: all new tests show FAILED or ERROR. If any new test unexpectedly PASSES before implementation:
- Either the feature already exists (run `git status` + `grep` to confirm)
- Or the test has a logic error (assert always-true condition)
Never assume tests fail — verify it. A test that passes against no implementation is testing nothing. Fail-before / pass-after is what makes the test trustworthy: it proves the test can actually detect the absence of the feature.

## VERIFICATION CONTRACT — state before coding
Before writing ANY feature code, state the full verification criteria:
```
# Verifying [feature]:
# 1. <project test command> tests/test_X.py::test_new_feature → passes
# 2. import the changed module and confirm it loads → OK
# 3. hit the actual endpoint (curl the project's dev URL) → includes new_field in response
```
Feature is done when ALL criteria pass — not when the code looks correct.

## WORD-BOUNDARY MATCHING FOR TERM SEARCHES
When testing for presence or absence of specific terms in generated content (e.g. jargon detection, keyword validation), always use word-boundary regex (`re.search(rf"\b{term}\b", text)`) — substring matching produces false positives on embedded substrings (e.g. "orm" matching "format").

## END-TO-END VERIFICATION (not just unit tests)
After unit tests pass, verify as a real user would:
```bash
# Start backend, hit the actual endpoint (use the project's dev URL + a real route)
curl -s "$PROJECT_URL/api/<resource>" | python3 -m json.tool
```
Unit tests passing ≠ feature working. Always verify the full flow at least once.

## TEST RESILIENCE UNDER CODE EVOLUTION
When MODIFYING existing code (not new features), run existing tests BEFORE writing new ones to verify you haven't broken them. Agent-generated tests are especially brittle under code change because they tend to pattern-match syntax rather than behavior — a rename can break a test that never exercised the renamed thing.
- **Prefer behavioral assertions**: Assert what a function RETURNS or what side effect occurs, not how internal code is structured. `assert response.status_code == 200` survives refactors; `assert mock_internal_fn.called_with(...)` breaks on rename.
- **Stable baseline tests**: When updating a feature, keep existing tests intact and add new ones for new behavior — don't regenerate the entire test file.
- **Regression awareness**: After modifying code, verify tests fail appropriately when the feature is broken (not just that they pass when it works). If a test passes regardless of the code change, it's testing nothing.

## WHAT "TESTS PASS" MEANS
- Zero failures in `tests/`
- No collection errors
- Same or higher test count than before your change
- Never commit if count drops — investigate why

## IMPORT CHECK BEFORE TESTS
Import the app/module you changed (using the project's package path) and confirm it loads.
If this fails, fix imports first — pytest will fail on collection.
