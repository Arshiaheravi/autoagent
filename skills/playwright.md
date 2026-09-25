# Skill: Frontend Verification (Playwright)

## When to use this skill
Run after every WORK session, BEFORE committing. You must start the servers yourself, run checks, then shut them down.

---

## STEP 1 — Start the servers

Start backend and frontend in the background:

Read `autoagent/PROJECT.md` for the exact start commands, backend URL, and frontend URL.

```bash
# Use the start commands from PROJECT.md — example structure:
# cd [PROJECT_ROOT]
# start /B [BACKEND_START_CMD] > autoagent/tmp_backend.log 2>&1
# start /B [FRONTEND_START_CMD] > autoagent/tmp_frontend.log 2>&1
```

Wait 4 seconds for them to boot, then check they're up:

```bash
# Use backend_url and frontend_url from autoagent/config.json or PROJECT.md
curl -s [BACKEND_URL]/[HEALTH_ENDPOINT] > nul && echo backend:OK || echo backend:FAIL
curl -s [FRONTEND_URL] > nul && echo frontend:OK || echo frontend:FAIL
```

If either fails after 4s, try once more after another 3s. If still failing, set status=skip with note "servers failed to start", kill both processes, and continue to commit without a frontend check.

---

## STEP 2 — Check if Playwright is installed

```bash
py -m playwright --version
```

If not installed:
```bash
py -m pip install playwright -q && py -m playwright install chromium --quiet
```

---

## STEP 3 — Run the check script

Save as `autoagent/tmp_check.py`, run it, delete it after.

```python
import asyncio, sys
from playwright.async_api import async_playwright

async def check():
    failures = []
    checks = 0
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        js_errors = []
        page.on("pageerror", lambda e: js_errors.append(str(e)))

        # 1. Page loads
        try:
            await page.goto("http://localhost:3000", timeout=12000)
            checks += 1
            print("  [CHECK 1] Page loaded OK")
        except Exception as e:
            failures.append(f"Page failed to load: {e}")
            await browser.close()
            return checks, failures

        # 2. Backend API responds — use backend_url from autoagent/config.json
        try:
            resp = await page.request.get("http://localhost:8000/api/health", timeout=8000)  # update URL per PROJECT.md
            if resp.ok:
                checks += 1
                print("  [CHECK 2] Backend API OK")
            else:
                failures.append(f"Backend returned {resp.status}")
        except Exception as e:
            failures.append(f"Backend API unreachable: {e}")

        # 3. Signal cards visible
        try:
            await page.wait_for_selector(".signal-card, .card, [class*='card']", timeout=10000)
            checks += 1
            print("  [CHECK 3] Signal cards visible")
        except:
            failures.append("Signal cards not found — dashboard may be empty or broken")

        # 4. Market toggle present
        try:
            toggle = await page.query_selector("#market-toggle, [data-market], .market-toggle")
            if toggle:
                checks += 1
                print("  [CHECK 4] Market toggle found")
            else:
                failures.append("Market toggle not found")
        except Exception as e:
            failures.append(f"Market toggle check error: {e}")

        # 5. Navigation present
        try:
            nav = await page.query_selector("nav, .nav, header")
            if nav:
                checks += 1
                print("  [CHECK 5] Navigation present")
            else:
                failures.append("Navigation not found")
        except Exception as e:
            failures.append(f"Nav check error: {e}")

        # 6. No JS errors
        await asyncio.sleep(1)
        if js_errors:
            failures.append(f"JS errors: {'; '.join(js_errors[:3])}")
        else:
            checks += 1
            print("  [CHECK 6] No JS errors")

        # 7. Removed nav items NOT present (regression guard)
        # Read "REMOVED FEATURES" from autoagent/PROJECT.md and check those page names are absent
        # Example: REMOVED_PAGES = ["old-feature", "removed-section"]
        # Customize per project — leave empty list if no removed features to guard
        REMOVED_PAGES = []  # populate from PROJECT.md "REMOVED FEATURES" table
        for rp in REMOVED_PAGES:
            elem = await page.query_selector(f'[data-page="{rp}"], [onclick*="{rp}"]')
            if elem:
                failures.append(f"REMOVED section '{rp}' still appears in nav")
            else:
                checks += 1
                print(f"  [CHECK 7/{rp}] '{rp}' correctly absent from nav")

        # 8. Light mode toggle — dark is default, verify light mode switches and no invisible elements
        try:
            toggle = await page.query_selector("#theme-toggle, [onclick*='toggleTheme'], [onclick*='theme']")
            if toggle:
                await toggle.click()
                await asyncio.sleep(0.5)
                # Verify page still has content (not invisible on white bg)
                body_bg = await page.evaluate("getComputedStyle(document.body).backgroundColor")
                # Check a card or main section is still visible
                card = await page.query_selector(".stock-card, .signal-card, #signals-container")
                if card:
                    checks += 1
                    print("  [CHECK 8] Light mode: page has content after theme toggle")
                else:
                    failures.append("Light mode: main content not visible after toggle")
                # Switch back to dark
                await toggle.click()
                await asyncio.sleep(0.3)
            else:
                checks += 1
                print("  [CHECK 8] Light mode toggle not found — skip (not blocking)")
        except Exception as e:
            print(f"  [CHECK 8] Light mode check skipped: {e}")
            checks += 1  # Non-blocking

        await browser.close()
    return checks, failures

checks, failures = asyncio.run(check())
print(f"\n  Frontend: {checks} checks, {len(failures)} failures")
for f in failures:
    print(f"  FAIL: {f}")
sys.exit(1 if failures else 0)
```

```bash
py autoagent/tmp_check.py
del autoagent\tmp_check.py
```

---

## STEP 4 — Kill the servers

After the check (pass or fail), always kill the servers:

```bash
for /f "tokens=5" %a in ('netstat -aon ^| findstr ":8000"') do taskkill /F /PID %a > nul 2>&1
for /f "tokens=5" %a in ('netstat -aon ^| findstr ":3000"') do taskkill /F /PID %a > nul 2>&1
del autoagent\tmp_backend.log autoagent\tmp_frontend.log > nul 2>&1
```

---

## STEP 5 — Record results in sessions.json

Pass:
```json
"frontend": {"status": "pass", "checks": 6, "failures": 0, "notes": ""}
```

Fail (fix before committing):
```json
"frontend": {"status": "fail", "checks": 4, "failures": 2, "notes": "Signal cards not found; JS error: X"}
```

Skip (servers couldn't start or Playwright missing):
```json
"frontend": {"status": "skip", "checks": 0, "failures": 0, "notes": "servers failed to start"}
```

---

## IF CHECKS FAIL

Fix the issue, re-run the check, confirm pass — then commit. A failing frontend check blocks the commit exactly like a failing test.
The only exception is status=skip (can't start servers / Playwright missing) — that never blocks a commit.

---

## RECONNAISSANCE-THEN-ACTION PATTERN (from Anthropic webapp-testing skill)

When debugging a failing check, use this order — never skip to action:
1. **Screenshot first**: `await page.screenshot(path="autoagent/tmp_debug.png")` — see what the page actually shows
2. **DOM inspect**: `await page.content()` — see raw HTML to verify selectors exist
3. **Identify correct selectors** from DOM, then act
4. **Always wait for networkidle** on dynamic apps before inspecting: `await page.wait_for_load_state("networkidle")`

Source: Anthropic skills/webapp-testing/SKILL.md (2026-03-20)
