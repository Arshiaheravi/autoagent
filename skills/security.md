# Skill: Security

**When to use**: Before committing ANY code that handles user input, authentication,
database queries, file uploads, API keys, or external data. Also run during the audit step.

## The non-negotiables (always check these)

### 1. Never hardcode secrets
```python
# WRONG — will end up in git history forever
ANTHROPIC_API_KEY = "sk-ant-..."
ADMIN_PASSWORD = "supersecret"

# CORRECT — always from environment
from myapp.config import settings  # the project's typed settings object
api_key = settings.anthropic_api_key
```
Check: `grep -rn "sk-ant\|ghp_\|password.*=.*['\"]" <source dir>` — should return nothing.

### 2. Parameterize all database queries
```python
# WRONG — SQL injection vulnerability
query = f"SELECT * FROM users WHERE email = '{email}'"

# CORRECT — SQLAlchemy ORM or parameterized
user = db.query(User).filter(User.email == email).first()
```

### 3. Validate all user input at the boundary
```python
# WRONG — trusting user-supplied data
raw = request.query_params.get("path")
data = read_resource(raw)  # could be "../../../etc/passwd"

# CORRECT — validate before use
ticker = request.query_params.get("ticker", "").upper().strip()
if not ticker.isalnum() or len(ticker) > 10:
    raise HTTPException(400, "Invalid ticker")
```

### 4. Never expose internal errors to users
```python
# WRONG — leaks stack traces and internal paths
except Exception as e:
    return {"error": str(e)}  # exposes internals

# CORRECT — log internally, return generic message
except Exception as e:
    logger.error(f"Dashboard error for {ticker}: {e}")
    raise HTTPException(500, "Service temporarily unavailable")
```

### 5. Rate limiting on all public endpoints
```python
# Auth endpoints especially — prevent brute force
# Reference the project's existing limiter/rate-limit pattern (grep for it first)
from myapp.routes.auth import limiter
```

### 6. Admin endpoints always require authentication
```python
# Every admin route must depend on the project's admin-auth guard
# (find it: grep for the existing admin routes and reuse their dependency)
from myapp.routes.admin import require_admin

@router.post("/admin/something")
async def admin_action(admin=Depends(require_admin)):
    ...
```

## OWASP Top 10 checklist for every PR

- [ ] **Injection**: All DB queries parameterized? No `f"... {user_input} ..."` in SQL
- [ ] **Broken Auth**: Admin routes require `_require_admin`? JWT validated properly?
- [ ] **Sensitive Data**: No secrets in code? Passwords hashed (bcrypt, not MD5)?
- [ ] **XSS**: User data HTML-escaped before rendering? (FastAPI + Pydantic handles most of this)
- [ ] **Insecure Direct Object Reference**: Users can only access their own data?
- [ ] **Security Misconfiguration**: Debug mode off in production? No open CORS `*`?
- [ ] **Outdated Dependencies**: No known CVEs in requirements.txt?

## Repo security checks

```bash
# Check for hardcoded secrets (scope to the project's source dir)
grep -rn "sk-ant\|ghp_\|password\s*=\s*['\"]" <source dir>

# Check for SQL injection risk
grep -rn "f\".*SELECT\|f\".*INSERT\|f\".*UPDATE" <source dir>

# Check admin routes have auth (point at the project's admin routes file)
grep -rn "@router\." <admin routes file> | head -20
```

## If you find a security issue

1. Fix it immediately — security issues are always blocking
2. Check if the same pattern exists elsewhere: `grep -rn "same_pattern" src/`
3. Fix all instances, not just the one you noticed
4. Add a test that proves the vulnerability is closed
