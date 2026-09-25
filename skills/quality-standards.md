# Quality Standards — Scoring 2/2 on Every Criterion

When to read: every session. These standards are enforced. META sessions audit compliance.

Source: Agency accuracy audit (March 28, 2026). Overall grade B (7.9/10). These rules bring every criterion to 2/2.

---

## 1. TDD — Two-Commit Proof (target: 2/2)

Every feature task produces TWO commits, not one. Both use the project's
configured commit prefix from PROJECT.md (`<prefix>`, e.g. `agent`) — see
git.md for the message format; this section only sets the two-commit policy.

**Commit 1 — Tests only:**
```
<prefix>(test): add failing tests for [task name]
```
Contains ONLY test files. Tests MUST fail when run — verify with the
fail-before check in testing.md. If they pass, the tests are wrong.

**Commit 2 — Implementation:**
```
<prefix>(feat): implement [task name] — all tests passing
```
Contains ONLY source files. Tests now pass.

**Verification:** In the VERIFICATION REPORT, include:
```
TDD: YES
  Commit 1 (tests): [hash] — X tests failed
  Commit 2 (impl):  [hash] — X tests passed
```

META sessions verify by checking git log for the two-commit pattern.

**Why two commits?** One commit bundles tests with code and makes TDD unfalsifiable. Two commits create an audit trail. The test commit proves the tests existed before the implementation.

---

## 2. Clean Architecture — Incremental Cleanup (target: 2/2)

New code MUST follow clean-architecture.md patterns. Old code gets fixed when touched.

**META task (once per 5 sessions):** Pick ONE file that violates clean-architecture.md. Fix it. Run tests. Commit. One file at a time, never a big-bang refactor.

**Priority violations to fix:**
- Import walls (from X import Y as Z_router × 20)
- Bare array returns (should be `{"data": [...], "meta": {...}}`)
- `os.getenv()` scattered in route files (should use get_settings())

---

## 3. Test Quality — Behavioral Assertions (target: 2/2)

### Backend tests
Every test MUST assert on response BODY, not just status code:

**Bad:**
```python
def test_list_items(client):
    res = client.get("/api/items")
    assert res.status_code == 200  # proves nothing about correctness
```

**Good:**
```python
def test_list_items(client, seed_item):
    res = client.get("/api/items")
    assert res.status_code == 200
    data = res.json()
    assert len(data["data"]) == 1
    assert data["data"][0]["name"] == "Widget One"
```

### Frontend tests
NEVER grep JS source code for keywords. That tests existence, not behavior.

**Bad:**
```python
def test_pdf_button(client):
    res = client.get("/")
    assert "POST" in res.text  # proves nothing — dead code also contains "POST"
```

**Good:**
```python
def test_pdf_report_downloads(client, seed_item):
    res = client.post(f"/api/items/{item_id}/report")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert res.content[:4] == b"%PDF"
```

If a frontend feature calls an API, test the API. If it renders HTML, test that the HTML contains the expected elements with correct data.

---

## 4. Single Responsibility — Scope Declaration (target: 2/2)

Already strong (1.8/2). One rule to close the gap:

If a commit MUST touch files beyond the primary feature (e.g., nav links in other pages), list them in the commit message:

```
feat: Add notification history page

Primary: notifications.html, notifications.js, api/notifications.py
Related: index.html, intel.html, field.html (nav link added)
```

This makes scope visible and auditable.

---

## 5. Working Code — META Validation (target: 2/2)

META sessions must validate their own output:

```python
# After updating sessions.json:
import json
json.loads(open("sessions.json").read())  # must parse

# After updating backlog.md:
assert "### " in content  # has task headers
assert "- Test:" in content  # has test cases

# After updating knowledge.md:
assert "RULE:" in content  # has rules
assert "2026-" in content  # has dates
```

If META produces output that fails validation, log it as a failure — don't silently corrupt memory files.
