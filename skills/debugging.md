# Skill: Debugging

**When to use**: Any time a test fails, a bug is reported, an API returns wrong data,
or code behaves unexpectedly. Always follow this systematic process — never guess.

## The 5-step process (never skip steps)

### Step 1 — Read the error literally
```
AttributeError: 'NoneType' object has no attribute 'score'
  File "routes/dashboard.py", line 47, in get_dashboard
    signal.score
```
- What type is wrong? (`NoneType`)
- What line? (`dashboard.py:47`)
- What was expected? (`signal` with a `.score` attribute)

Do NOT jump to solutions. Read every line of the traceback.

### Step 2 — Reproduce it
```bash
pytest tests/test_routes.py::test_get_route -xvs   # use the project's test command
```
If you can't reproduce it, you can't fix it. Add a failing test FIRST that proves the bug exists.

### Step 3 — Isolate the cause
Binary search the call chain:
```python
# Add temporary print at each layer to find where None enters
print(f"DEBUG fetch result: {result}")   # is it None here?
print(f"DEBUG item object: {item}")       # or here?
print(f"DEBUG item.value: {item.value}")  # or here?
```
Find the EXACT line where the value becomes wrong. Remove debug prints after.

### Step 4 — Fix the root cause (not the symptom)
Bad fix (symptom):
```python
if signal is not None:  # hiding the problem
    return signal.score
```
Good fix (root cause):
```python
# Find WHY the value is None and fix THAT
# e.g. the upstream call returned an empty list → need a fallback
```

### Step 5 — Verify and prevent recurrence
```bash
# use the project's test command from PROJECT.md
pytest tests/ -q --ignore=tests/test_e2e.py
```
- Test count must not drop
- Add a test specifically for this bug so it never silently returns
- If it was a data-type mismatch, add a type check at the boundary

## Common bug patterns

| Symptom | Common cause | Where to look |
|---------|-------------|---------------|
| `KeyError` in response | Missing field in the response model | the model that shapes that response |
| `AttributeError: NoneType` | An upstream/API call returned empty data | the service that makes that call |
| Test passes locally, fails in CI | env var not set | config defaults |
| Frontend shows wrong data | snake_case vs camelCase mismatch | the client's key names |
| Value unexpectedly 0 | New param not wired through the layers | trace the param from route → service |
| Import error on startup | Circular import or missing route registration | the app/router entry point |

## When stuck after 15 minutes

1. Read the file from the top — the bug is usually above where the error shows
2. Check git diff — did a recent change break this?
3. Simplify — can you reproduce the bug with 5 lines instead of 50?
4. Search for similar patterns: `grep -r "same_function_name" src/`
5. Add logging at every step in the call chain and run again

## Self-critique before fixing (from research 2025)

After writing the fix but BEFORE running tests, re-read what you changed and ask:
1. Does this fix the root cause or just suppress the symptom?
2. Could this fix break something else? (check callers with `grep -r "function_name" src/`)
3. Is there an edge case (None, empty list, zero) this fix doesn't handle?

This 90-second check catches ~20% of fixes that would fail on the next test run.

## Never do

- Never comment out a failing test to make the suite pass
- Never catch `Exception` broadly without logging what you caught
- Never fix a symptom when the root cause is unknown
- Never assume — verify every assumption with a print or test
- Never stop after "tests pass" — also verify the endpoint works end-to-end
