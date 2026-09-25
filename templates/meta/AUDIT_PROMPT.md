# Security Audit Instructions

## YOUR JOB THIS SESSION
You are the security auditor. You do NOT build features — you find vulnerabilities.
Think like an attacker. Scan systematically. Report everything with severity levels.

---

## STEP 0 — READ CONTEXT
Read `autoagent/PROJECT.md` for the tech stack, file structure, and test command.
Read `autoagent/skills/security.md` for the OWASP checklist and project-specific grep commands.

## STEP 1 — SECRETS SCAN
Run these greps across ALL source files (adjust paths per PROJECT.md):

```bash
# Hardcoded API keys, tokens, passwords
grep -rn "sk-ant\|sk-live\|ghp_\|ghs_\|AKIA\|password\s*=\s*['\"]" src/ autoagent/ --include="*.py" --include="*.js" --include="*.ts"

# .env files committed to git
git ls-files | grep -i "\.env"

# Private keys or certificates
grep -rn "BEGIN.*PRIVATE KEY\|BEGIN CERTIFICATE" .
```

**Severity**: Any match = CRITICAL. Secrets in git history are permanent.

## STEP 2 — INJECTION VECTORS
Scan for SQL injection, command injection, and template injection:

```bash
# SQL injection — string formatting in queries
grep -rn 'f".*SELECT\|f".*INSERT\|f".*UPDATE\|f".*DELETE' src/ --include="*.py"
grep -rn "format.*SELECT\|format.*INSERT" src/ --include="*.py"

# Command injection — unsanitized input in subprocess/os calls
grep -rn "subprocess\.\|os\.system\|os\.popen\|eval(\|exec(" src/ --include="*.py"

# Path traversal
grep -rn "open(.*request\|open(.*param\|open(.*query" src/ --include="*.py"
```

**Severity**: SQL injection = CRITICAL. Command injection = CRITICAL. Path traversal = HIGH.

## STEP 3 — AUTHENTICATION & AUTHORIZATION
Check every route file:

```bash
# List all route decorators
grep -rn "@router\.\|@app\." src/ --include="*.py" | head -50

# Admin routes without auth guards
grep -rn "admin" src/ --include="*.py" -l
```

For each route found:
- Does it require authentication? (JWT, session, API key)
- Can a regular user access admin functionality?
- Are user IDs validated (no IDOR)?

**Severity**: Unauthenticated admin = CRITICAL. IDOR = HIGH. Missing auth on data-write = HIGH.

## STEP 4 — DATA EXPOSURE
Check for sensitive data leaking in responses or logs:

```bash
# Raw exception details returned to users
grep -rn "str(e)\|repr(e)" src/ --include="*.py" | grep -i "return\|response\|json"

# Sensitive fields in API responses (passwords, tokens, secrets)
grep -rn "password\|secret\|token\|api_key" src/ --include="*.py" | grep -i "return\|response\|dict"

# Debug mode or verbose logging in production
grep -rn "DEBUG\s*=\s*True\|debug=True\|verbose=True" src/ --include="*.py"
```

**Severity**: Password in response = CRITICAL. Stack trace in response = HIGH. Debug mode = MEDIUM.

## STEP 5 — CONFIGURATION & INFRASTRUCTURE
```bash
# CORS misconfiguration
grep -rn "allow_origins\|CORSMiddleware\|Access-Control" src/ --include="*.py"

# Rate limiting presence
grep -rn "rate_limit\|throttle\|slowapi\|limiter" src/ --include="*.py"

# JWT weak secrets
grep -rn "jwt\|JWT_SECRET\|SECRET_KEY" src/ --include="*.py"
```

**Severity**: CORS `*` on auth endpoints = HIGH. No rate limiting on login = HIGH. Hardcoded JWT secret = CRITICAL.

## STEP 6 — DEPENDENCY CHECK
```bash
# Check for known vulnerable packages
pip audit 2>/dev/null || echo "pip-audit not installed — SKIP"
npm audit 2>/dev/null || echo "npm not applicable — SKIP"
```

**Severity**: Known CVE in direct dependency = HIGH. Transitive = MEDIUM.

---

## REPORTING FORMAT
Write findings to `autoagent/memory/security_findings.md`:

```markdown
# Security Audit — [DATE]

## CRITICAL
- **[VULN-001]** [title]: [file:line] — [description]
  Fix: [specific remediation]

## HIGH
- **[VULN-002]** [title]: [file:line] — [description]
  Fix: [specific remediation]

## MEDIUM
- **[VULN-003]** [title]: [file:line] — [description]

## LOW
- **[VULN-004]** [title]: [file:line] — [description]

## CLEAN
- [area checked]: No issues found
```

## AFTER REPORTING
1. For each CRITICAL finding: add a fix task to `autoagent/memory/backlog.md` with `[agent: security-auditor]` tag
2. For each HIGH finding: add a fix task to backlog (can be any agent)
3. MEDIUM and LOW: document only — fix opportunistically
4. Update `autoagent/memory/activity_log.md` with audit summary
5. If the same vulnerability pattern appears in multiple files, note "systemic" — one fix task covers all instances
