# Skill: Virtual Senior Dev Team Audit

**When to use**: After every WORK session, before committing. Read this file and run each team member's checklist against the files changed this session. Fix all issues found. Issues too large to fix now → append one line to `.autoagent/memory/tech_debt.md`.

**How to use**:
1. Get changed files: read `.autoagent/memory/project_root.md` for the project path, then `git -C "[PROJECT_ROOT]" diff --name-only HEAD` (or use staged diff if pre-commit)
2. For each team member below: re-read the changed files through that lens and ask "Would this person approve this PR?"
3. Fix every issue immediately unless it's too large (>30 min)
4. Never commit with a known Marcus (security) failure — those are always blocking
5. Log deferred issues to `.autoagent/memory/tech_debt.md`: `[DATE] [FILE] [TEAM MEMBER] — [issue description]`

**Project-domain reviewers**: A project may add its own expert reviewers (e.g. an agronomist for an ag product, a compliance reviewer for fintech) as a project-local audit extension in its own skills. Load those alongside this universal team when they exist. Do NOT apply another domain's reviewer to an unrelated project.

---

## TEAM MEMBER 1 — Alex, Staff Backend Engineer (10 years Python/FastAPI)

Mandate: the backend must be bulletproof, consistent, and scalable.

**Checklist**:
- [ ] Every new route follows one-way dependency: routes/ import services/, services/ import nothing from routes/
- [ ] No logic in routes — routes call service functions, services do the work
- [ ] Every external network call (third-party APIs, webhooks, scrapers) is wrapped in try/except with a logged warning and graceful fallback — never crashes the endpoint
- [ ] No N+1 DB queries — batch queries where multiple rows are needed
- [ ] No blocking I/O on the async event loop — use `run_in_executor` for all sync calls
- [ ] All new Pydantic models have `model_config` set correctly
- [ ] Schema/migration handled the way the project already does it — never require an undocumented manual step
- [ ] Config variables go in the project's typed settings with a default — never raw `os.getenv()` scattered in routes
- [ ] API responses follow the project's existing case convention consistently
- [ ] New endpoints registered the way existing ones are (e.g. `app.include_router()`)

---

## TEAM MEMBER 2 — Sarah, Senior Frontend Engineer (8 years JS/CSS)

Mandate: the UI must be polished, consistent, and never leave the user confused.

**Checklist**:
- [ ] Frontend files follow the project structure from `.autoagent/PROJECT.md` — no new separate files unless the project pattern allows it
- [ ] Every API call has: loading state (spinner or skeleton), success state, error state with a user-friendly message
- [ ] New UI elements use existing CSS variables and design patterns — no one-off inline styles
- [ ] Theme/dark mode consistent with the color variables defined in the project
- [ ] Mobile-first: every new element visible and functional at 375px, 768px, 1280px
- [ ] No `console.error` left in production code
- [ ] New interactive elements have hover states and `cursor:pointer`
- [ ] Loading skeletons shown immediately — never a blank white flash

---

## TEAM MEMBER 3 — Marcus, Application Security Engineer (OWASP certified)

Mandate: zero security regressions. One vuln ships = company trust destroyed.

**BLOCKING — never commit with a Marcus failure.**

**Checklist**:
- [ ] No hardcoded secrets, API keys, passwords, or tokens anywhere in source files
- [ ] All user-supplied input rendered via `textContent` or escaped — never `innerHTML` with user data (XSS)
- [ ] All DB queries use SQLAlchemy ORM or parameterized statements — never f-string SQL (injection)
- [ ] No IDOR: every DB query that returns user data filters by `current_user.id` — users cannot access other users' data
- [ ] Admin routes check password/JWT — never accessible unauthenticated
- [ ] JWT secret is from settings — never hardcoded
- [ ] Sensitive data (passwords, API keys, card numbers) never appear in log output
- [ ] CORS settings not widened beyond what's in config
- [ ] HTTP error responses use generic messages — no stack traces, DB error strings, or file paths in 4xx/5xx JSON. `{"detail": "Internal server error"}` not `{"detail": "sqlalchemy.exc.NoResultFound: ..."}`

---

## TEAM MEMBER 4 — Ama, Staff DevOps + Reliability Engineer

Mandate: the system must stay up, stay fast, and never silently fail.

**Checklist**:
- [ ] No new endpoint exceeds 2s response time on warm cache — check with `curl -o /dev/null -s -w "%{time_total}" [BACKEND_URL]/api/...` (read backend_url from `.autoagent/PROJECT.md`)
- [ ] New background jobs use the project's existing scheduler — never raw threads or bare asyncio tasks
- [ ] All background jobs have error logging — silent failures are invisible failures
- [ ] New DB queries hit indexed columns — no full table scans on large tables
- [ ] Cache TTL set to match data volatility — volatile data short, static data long
- [ ] No infinite loops or unbounded retries in background jobs
- [ ] External API calls respect rate limits — use batch endpoints where available, never call in tight loops

---

## TEAM MEMBER 5 — Leo, Senior Technical Writer + Code Consistency Enforcer

Mandate: the codebase must be readable and consistent — a new developer should understand any file in 5 minutes.

**Checklist**:
- [ ] No dead code left behind — removed features fully deleted, not commented out
- [ ] No duplicate logic — if the same calculation appears twice, it's in a shared service function
- [ ] Function names are verbs: `compute_total()`, `get_user()`, `send_alert()` — not `total()` or `user()`
- [ ] New files follow the existing naming convention in the project (match the pattern already there)
- [ ] No TODO comments left in committed code — either fix it or add to tech_debt.md
- [ ] Project docs updated if any new architectural pattern, convention, or file structure was introduced this session

---

## TEAM MEMBER 6 — Nina, QA Engineer + Accessibility Specialist

Mandate: every change must be regression-tested against what already works. No feature should silently break something else. No removed feature should reappear.

**Checklist**:
- [ ] **Removed features stay removed**: Check `.autoagent/PROJECT.md` "REMOVED FEATURES" list — none of those sections, nav links, or JS functions reappear in any changed file
- [ ] **Navigation consistency**: Nav links must be consistent across pages — if a page exists, it has a nav link; removed pages have nav links removed everywhere
- [ ] **Logic accuracy gate**: If any core calculation or scoring function was changed, run the project's test suite (see `.autoagent/PROJECT.md` for the test command) and verify all critical tests pass
- [ ] **No partial implementations**: Every frontend UI element that calls an API must have a corresponding working endpoint. No buttons that 404, no tabs that show empty state because the route wasn't wired
- [ ] **Agent code churn check**: Agent-generated code has 41% higher churn than human code (GitClear 2024). Review multi-file changes for coherence — one consistent feature, not disjointed blocks pasted together
- [ ] **Console clean**: After any frontend change, the Playwright check (playwright.md) must report zero JS errors. Warnings are okay, errors are not
- [ ] **Feature explanations**: Any complex feature (a score, a threshold, a recommendation) must have a tooltip, info icon, or explanatory text visible to the user. If you add a chip or metric, add its explanation too

---

## Quick reference — which checklist for which change type

| Change type | Must check |
|-------------|-----------|
| New backend route | Alex (architecture), Marcus (security) |
| New DB model | Alex (migration), Ama (indexes + background jobs) |
| New frontend component | Sarah (UI consistency), Nina (regression + accessibility) |
| New scoring function | Alex (data flow), Leo (naming), Nina (test gate), test coverage in testing.md |
| New external API call | Alex (try/except), Ama (rate limits + caching) |
| New paywall / gated feature | Marcus (IDOR), Nina (pricing accuracy + gated UI works) |
| New config variable | Alex (settings), Leo (naming) |
| Any change involving user data | Marcus (security) — always blocking |
| Removing a feature | Leo (dead code fully deleted), Nina (removed-features list updated in PROJECT.md) |
| Changing tier logic | Nina (pricing accuracy), Marcus (access control) |
