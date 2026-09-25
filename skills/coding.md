# Skill: Coding

## BEFORE WRITING ANY CODE — EVIDENCE FIRST
- Run `git diff` — check if there's in-progress work to finish first
- Check `autoagent/memory/knowledge.md` for existing patterns
- **Read the file you're about to change before touching it** — never modify code you haven't read
- Find the existing pattern for what you're building and follow it exactly
- If current_task.md has unchecked steps, continue those — don't restart

## MINIMAL CHANGE PRINCIPLE
Make the smallest change that solves the problem. Before every edit ask:
- "Does this file actually need to change, or just the one I'm already editing?"
- "Is this logic already somewhere else I can call instead of duplicate?"
- "Am I adding an abstraction for ONE use case?" → don't, just write the code
Over-engineering is the #1 agent failure mode. 3 lines that work > 30 that are "cleaner".

## BACKEND PATTERNS
- Follow the project's EXISTING layout — read the repo first, mirror where routes, services, and models already live. Never assume a path; find the pattern and match it.
- New route → new service → new model: place each in the directory the project already uses for that layer, and register it the same way existing ones are registered.
- Pure functions only in service/processing files — no HTTP, no object-storage, no side effects inside processing functions.
- All settings through a single typed config object (e.g. Pydantic Settings) — never raw `os.getenv()` scattered in routes.
- Use the project's configured Python/run command (from PROJECT.md); default `python3` on the Linux/macOS runner.
- Dependency direction flows one way (routes → services → utils) — never import backwards.

## FRONTEND
- For any UI / landing / app frontend, use the `ui-stack.md` skill — modern stack and design engine, agency-led. Do not hard-code a stack or language here.
- Follow the current project's existing frontend conventions (read PROJECT.md and the repo before adding files).

## DICT KEY CONTRACT — CHECK ALL 3 LAYERS
When a function returns a dict with new keys:
1. Route passes ALL keys to model constructor
2. Model has fields for all keys
3. Frontend uses same key names
Missing any layer = silent bug

## FEATURE WIRING CHAIN (new service endpoint)
When adding a new endpoint backed by a new service:
1. Pure function in `services/` (arrays/dicts in, dict out — no I/O)
2. Pydantic response model in `models/`
3. Route handler in `api/` — thin, HTTP only, calls service
4. Register router in `api/__init__.py`
5. Mount router in `app.py`
6. Test: service unit test + route integration test
7. Frontend: JS fetch + render

## SQLALCHEMY + FASTAPI PATTERNS
- **Never use `expire_on_commit=True` in async sessions** — accessing expired attributes after commit raises an error in async contexts. Set `expire_on_commit=False` in `AsyncSession`.
- **asyncpg URL scheme**: Use `postgresql+asyncpg://` not `postgresql://` — wrong scheme won't error immediately but blocks the event loop under load.
- **Connection pool tuning**: Default `pool_size=5` is too small. Use `pool_size=20, max_overflow=10` for production. Each Uvicorn worker has its own pool: total connections = workers × pool_size.
- **Bulk inserts**: Use `session.add_all([...])` not individual `session.add()` calls in loops.
- **Session lifecycle**: Use FastAPI `Depends(get_db)` for session injection — never create sessions manually in routes.

## EXTERNAL API ERROR HANDLING PATTERNS
- Retry on 503/504: `time.sleep(2**attempt)` up to 3 attempts with exponential backoff
- Re-raise immediately on 401/403: auth errors are not retryable
- OpenWeather API: wrap in try/except with graceful `None` fallback — weather data is supplemental, never crash the endpoint for missing weather
- Anthropic API: always check for empty response content before extracting text

## FASTAPI STARTUP/SHUTDOWN — USE LIFESPAN, NOT @app.on_event
`@app.on_event("startup")` / `@app.on_event("shutdown")` are deprecated since FastAPI 0.103+. Use `lifespan`:
```python
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup: init DB tables, warm cache
    Base.metadata.create_all(bind=engine)
    yield
    # shutdown: close connections

app = FastAPI(lifespan=lifespan)
```
Wire this into the app the way the project already constructs it (e.g. an app factory) — pass `lifespan=lifespan` to the FastAPI constructor.

## AFTER WRITING CODE
- Import check: import the module you changed and confirm it loads (use the project's package path, not a hardcoded one).
- Run tests: use the project's test command from PROJECT.md, run from the project root.
- Fix ALL failures — never commit red
