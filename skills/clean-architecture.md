# Clean Architecture — Backend Standards

When to read: every session that touches backend code. Non-negotiable patterns, distilled from production FastAPI code review.

## 1. App entry point — no import walls

**Bad (import wall):**
```python
from myapp.api.alerts import router as alerts_router
from myapp.api.billing import router as billing_router
from myapp.api.auth import router as auth_router
# ... 26 more lines of this
```

**Good (one import line):**
```python
from app.routes import admin, alerts, auth, billing, users

app.include_router(auth.router)
app.include_router(users.router)
```

**Rule:** Import the module, not the router. Use `module.router` when registering. If you have more than 10 router imports, create a `routes/__init__.py` that exports them or use a loop.

## 2. Single models.py — all ORM in one file

**Bad:** Scattering models across `models/order.py`, `models/user.py`, `models/item.py` etc.
**Good:** One `models.py` with all ORM classes. Under 200 lines? One file. Over 200? Split by domain but keep it to 3-4 files max.

**Why:** A developer should be able to see ALL database tables by opening ONE file. Scattered models mean nobody knows the full schema.

## 3. Health + readiness probes

Every app needs both:
```python
@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/readiness")
def readiness():
    """Checks DB connectivity. 200 if reachable, 503 if not."""
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception:
        return JSONResponse(status_code=503, content={"status": "unavailable"})
    finally:
        db.close()
```

## 4. Rate limiting on auth endpoints

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("/register")
@limiter.limit("5/minute")
def register(request: Request, ...):
```

Minimum: rate limit `/register` and `/login`. Prevents brute force with zero effort.

## 5. Config — every external service in one place

```python
class Settings(BaseSettings):
    # DB
    database_url: str = "sqlite:///./app.db"
    # Auth
    jwt_secret_key: str = "change-me"
    jwt_expire_minutes: int = 10080
    # Stripe
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    # Telegram
    telegram_bot_token: str = ""
    # etc — ALL in ONE file with defaults

    class Config:
        env_file = ".env"
```

**Rule:** If a service needs a key, it goes in Settings with a default. No `os.getenv()` scattered in service files.

## 6. Structured logging at module level

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)
```

Do this ONCE in main.py. Every other module just does `logger = logging.getLogger(__name__)`.

## 7. Tier/role enforcement — centralized dict, not scattered ifs

```python
TIER_LIMITS = {
    "free": {"follows": 1, "notifications": False},
    "basic": {"follows": 5, "notifications": True},
    "vip": {"follows": float("inf"), "notifications": True, "priority": True},
}

def check_tier_limit(user, feature, value):
    limit = TIER_LIMITS[user.subscription_tier].get(feature)
    if limit is not None and value > limit:
        raise HTTPException(403, f"Upgrade to access this feature")
```

**Never:** `if user.tier == "free" and len(follows) >= 1` scattered across 5 route files.

## 8. API response format — always a dict, never bare arrays

**Bad:** `return [item1, item2, item3]`
**Good:** `return {"data": [item1, item2, item3], "meta": {"total": 3}}`

Bare arrays can't be extended. Dicts can always add metadata.

## 9. Cascade deletes — declare in relationships

```python
follows = relationship("BettorFollow", back_populates="user", cascade="all, delete-orphan")
```

Don't manually delete children in route handlers. Let SQLAlchemy handle it.

## 10. Test fixtures — minimal, focused

```python
@pytest.fixture
def registered_user(client):
    resp = client.post("/auth/register", json={"email": "test@test.com", "password": "pass123", "name": "Test"})
    return resp.json()
```

One fixture per concept. Don't build a 50-line fixture factory. Keep it readable.

## Apply to existing projects

When applying these to an existing project:
1. Don't refactor everything at once — fix patterns as you touch files
2. New code MUST follow these patterns
3. If you're adding a new route file, import it the clean way
4. If you're adding a new model, check if models.py is the right place first
