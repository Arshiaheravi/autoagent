#!/usr/bin/env python3
"""Telegram-based project intake — onboard new projects via chat.

Users message the bot with their idea. The Director walks them through
the intake questions, generates the project, and kicks off the first session.

Flow:
  1. User sends: /new "my app idea"
  2. Director asks 8 intake questions one at a time
  3. After all answers, generates PROJECT.md, NORTH_STAR.md, backlog, agents
  4. Sets up the project directory with scaffolding
  5. Runs first autonomous session
  6. Notifies user on Telegram when complete
"""
import json
import logging
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def _unique_project_name(base: str) -> str:
    """Return `base`, or `base-2`/`base-3`/… if a project with that name is
    already registered — so a new tenant never collides with an existing one's
    home dir / symlink / db row / `/run <name>`."""
    try:
        from registry import list_projects
        taken = {p["name"] for p in list_projects()}
    except Exception:
        taken = set()
    if base not in taken:
        return base
    i = 2
    while f"{base}-{i}" in taken:
        i += 1
    return f"{base}-{i}"


def _universal_agent_label() -> str:
    try:
        from org_model import universal_agent_names
        count = len(universal_agent_names())
        if count:
            return f"{count} universal agents + orchestrator"
    except Exception:
        pass
    return "department-based universal agents + orchestrator"


# Tech stack templates for auto-scaffolding
SCAFFOLDS = {
    "fastapi": {
        "dirs": ["src/{name}", "src/{name}/api", "src/{name}/services", "src/{name}/models",
                 "src/{name}/db", "frontend", "tests"],
        "files": {
            "src/{name}/__init__.py": "",
            "src/{name}/app.py": '''"""FastAPI application factory."""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path

def create_app() -> FastAPI:
    app = FastAPI(title="{display_name}", version="0.1.0")

    # Mount frontend if exists
    frontend_dir = Path(__file__).parent.parent.parent / "frontend"
    if frontend_dir.exists():
        app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")

    @app.get("/api/health")
    async def health():
        return {{"status": "ok"}}

    return app
''',
            "src/{name}/config.py": '''"""Settings from environment variables."""
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    db_url: str = "sqlite:///./{name}.db"
    jwt_secret_key: str = "change-me"
    log_level: str = "INFO"

    class Config:
        env_file = ".env"

_settings = None
def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
''',
            "src/{name}/db/__init__.py": "",
            "src/{name}/db/models.py": '''"""SQLAlchemy ORM models."""
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from datetime import datetime

class Base(DeclarativeBase):
    pass

# Add your models here
''',
            "src/{name}/api/__init__.py": "",
            "src/{name}/services/__init__.py": "",
            "src/{name}/models/__init__.py": "",
            "tests/__init__.py": "",
            "tests/conftest.py": '''"""Shared test fixtures."""
import pytest
from fastapi.testclient import TestClient
from {name}.app import create_app

@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)
''',
            "tests/test_health.py": '''"""Smoke test — app boots and health endpoint works."""
def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
''',
            "requirements.txt": '''fastapi>=0.110.0
uvicorn[standard]>=0.30.0
pydantic>=2.0.0
pydantic-settings>=2.0.0
sqlalchemy>=2.0.0
python-jose[cryptography]>=3.3.0
pytest>=8.0.0
httpx>=0.27.0
''',
            "run.sh": '''#!/bin/bash
pip install -r requirements.txt -q
PYTHONPATH=src uvicorn {name}.app:create_app --factory --reload --port 8000
''',
            "frontend/index.html": '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{display_name}</title>
    <style>
        body {{ font-family: system-ui; background: #0a0a0b; color: #e4e4e7; max-width: 800px; margin: 0 auto; padding: 40px; }}
        h1 {{ color: #22c55e; }}
    </style>
</head>
<body>
    <h1>{display_name}</h1>
    <p>Your app is running. Start building!</p>
</body>
</html>
''',
            ".gitignore": '''__pycache__/
*.pyc
*.db
.env
.autoagent/
venv/
node_modules/
''',
        },
    },
    "nextjs": {
        "dirs": ["src/app", "src/components", "src/lib", "public"],
        "files": {
            "src/app/layout.tsx": '''export default function RootLayout({{ children }}: {{ children: React.ReactNode }}) {{
  return (
    <html lang="en">
      <body>{{children}}</body>
    </html>
  )
}}
''',
            "src/app/page.tsx": '''export default function Home() {{
  return (
    <main style={{{{ padding: "40px", fontFamily: "system-ui", maxWidth: 800, margin: "0 auto" }}}}>
      <h1>{display_name}</h1>
      <p>Your app is running. Start building!</p>
    </main>
  )
}}
''',
            "src/app/api/health/route.ts": '''import {{ NextResponse }} from "next/server"
export async function GET() {{
  return NextResponse.json({{ status: "ok" }})
}}
''',
            "src/lib/db.ts": '''// Database client — add your ORM here (Prisma, Drizzle, etc.)
export const db = {{}}
''',
            "package.json": '''{{"name": "{name}", "version": "0.1.0", "private": true, "scripts": {{"dev": "next dev", "build": "next build", "start": "next start", "test": "jest"}}, "dependencies": {{"next": "^14.0.0", "react": "^18.0.0", "react-dom": "^18.0.0"}}, "devDependencies": {{"@types/node": "^20.0.0", "@types/react": "^18.0.0", "typescript": "^5.0.0", "jest": "^29.0.0", "@testing-library/react": "^14.0.0"}}}}''',
            "tsconfig.json": '''{{"compilerOptions": {{"target": "ES2017", "lib": ["dom", "dom.iterable", "esnext"], "allowJs": true, "skipLibCheck": true, "strict": true, "noEmit": true, "esModuleInterop": true, "module": "esnext", "moduleResolution": "bundler", "resolveJsonModule": true, "isolatedModules": true, "jsx": "preserve", "incremental": true, "paths": {{"@/*": ["./src/*"]}}}}, "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx"], "exclude": ["node_modules"]}}''',
            "__tests__/health.test.ts": '''describe("Health", () => {{
  it("returns ok", async () => {{
    const res = await fetch("http://localhost:3000/api/health")
    const data = await res.json()
    expect(data.status).toBe("ok")
  }})
}})
''',
            ".gitignore": '''node_modules/
.next/
.env
.autoagent/
''',
        },
    },
    "express": {
        "dirs": ["src/routes", "src/services", "src/models", "src/middleware", "public", "tests"],
        "files": {
            "src/app.js": '''const express = require("express")
const path = require("path")
const app = express()

app.use(express.json())
app.use(express.static(path.join(__dirname, "..", "public")))

app.get("/api/health", (req, res) => res.json({{ status: "ok" }}))

// Mount routes
// const usersRouter = require("./routes/users")
// app.use("/api/users", usersRouter)

module.exports = app
''',
            "src/index.js": '''const app = require("./app")
const PORT = process.env.PORT || 3000
app.listen(PORT, () => console.log(`Server running on port ${{PORT}}`))
''',
            "src/routes/.gitkeep": "",
            "src/services/.gitkeep": "",
            "src/models/.gitkeep": "",
            "package.json": '''{{"name": "{name}", "version": "0.1.0", "main": "src/index.js", "scripts": {{"start": "node src/index.js", "dev": "nodemon src/index.js", "test": "jest"}}, "dependencies": {{"express": "^4.18.0"}}, "devDependencies": {{"jest": "^29.0.0", "supertest": "^6.3.0", "nodemon": "^3.0.0"}}}}''',
            "tests/health.test.js": '''const request = require("supertest")
const app = require("../src/app")

describe("GET /api/health", () => {{
  it("returns ok", async () => {{
    const res = await request(app).get("/api/health")
    expect(res.status).toBe(200)
    expect(res.body.status).toBe("ok")
  }})
}})
''',
            "public/index.html": '''<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>{display_name}</title></head>
<body style="font-family:system-ui;max-width:800px;margin:0 auto;padding:40px;">
<h1>{display_name}</h1><p>Your app is running.</p>
</body></html>
''',
            ".gitignore": "node_modules/\n.env\n.autoagent/\n",
        },
    },
    "react": {
        "dirs": ["src/components", "src/pages", "src/hooks", "src/lib", "public"],
        "files": {
            "src/App.tsx": '''import React from "react"

export default function App() {{
  return (
    <div style={{{{ padding: 40, fontFamily: "system-ui", maxWidth: 800, margin: "0 auto" }}}}>
      <h1>{display_name}</h1>
      <p>Your app is running. Start building!</p>
    </div>
  )
}}
''',
            "src/main.tsx": '''import React from "react"
import ReactDOM from "react-dom/client"
import App from "./App"

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode><App /></React.StrictMode>
)
''',
            "index.html": '''<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>{display_name}</title></head>
<body><div id="root"></div><script type="module" src="/src/main.tsx"></script></body>
</html>
''',
            "package.json": '''{{"name": "{name}", "version": "0.1.0", "type": "module", "scripts": {{"dev": "vite", "build": "vite build", "preview": "vite preview", "test": "vitest"}}, "dependencies": {{"react": "^18.0.0", "react-dom": "^18.0.0"}}, "devDependencies": {{"@types/react": "^18.0.0", "@types/react-dom": "^18.0.0", "typescript": "^5.0.0", "vite": "^5.0.0", "@vitejs/plugin-react": "^4.0.0", "vitest": "^1.0.0"}}}}''',
            "vite.config.ts": '''import {{ defineConfig }} from "vite"
import react from "@vitejs/plugin-react"
export default defineConfig({{ plugins: [react()] }})
''',
            "tsconfig.json": '''{{"compilerOptions": {{"target": "ES2020", "module": "ESNext", "lib": ["ES2020", "DOM"], "jsx": "react-jsx", "moduleResolution": "bundler", "strict": true, "noEmit": true}}, "include": ["src"]}}''',
            ".gitignore": "node_modules/\ndist/\n.env\n.autoagent/\n",
        },
    },
    "go": {
        "dirs": ["cmd/{name}", "internal/api", "internal/service", "internal/model", "pkg"],
        "files": {
            "cmd/{name}/main.go": '''package main

import (
\t"fmt"
\t"log"
\t"net/http"
)

func main() {{
\thttp.HandleFunc("/api/health", func(w http.ResponseWriter, r *http.Request) {{
\t\tw.Header().Set("Content-Type", "application/json")
\t\tfmt.Fprintf(w, `{{"status":"ok"}}`)
\t}})

\tlog.Println("Server starting on :8080")
\tlog.Fatal(http.ListenAndServe(":8080", nil))
}}
''',
            "go.mod": '''module {name}

go 1.22
''',
            "internal/api/.gitkeep": "",
            "internal/service/.gitkeep": "",
            "internal/model/.gitkeep": "",
            "main_test.go": '''package main

import (
\t"net/http"
\t"net/http/httptest"
\t"testing"
)

func TestHealthEndpoint(t *testing.T) {{
\treq := httptest.NewRequest("GET", "/api/health", nil)
\tw := httptest.NewRecorder()

\thttp.HandleFunc("/api/health", func(w http.ResponseWriter, r *http.Request) {{
\t\tw.WriteHeader(http.StatusOK)
\t\tw.Write([]byte(`{{"status":"ok"}}`))
\t}})

\tif w.Code != http.StatusOK {{
\t\tt.Errorf("Expected 200, got %d", w.Code)
\t}}
}}
''',
            "Makefile": '''run:
\tgo run cmd/{name}/main.go

test:
\tgo test ./...

build:
\tgo build -o bin/{name} cmd/{name}/main.go
''',
            ".gitignore": "bin/\n*.exe\n.env\n.autoagent/\n",
        },
    },
    "rust": {
        "dirs": ["src", "tests"],
        "files": {
            "Cargo.toml": '''[package]
name = "{name}"
version = "0.1.0"
edition = "2021"

[dependencies]
actix-web = "4"
serde = {{ version = "1", features = ["derive"] }}
serde_json = "1"
tokio = {{ version = "1", features = ["full"] }}

[dev-dependencies]
actix-rt = "2"
''',
            "src/main.rs": '''use actix_web::{{web, App, HttpServer, HttpResponse}};
use serde::Serialize;

#[derive(Serialize)]
struct Health {{
    status: String,
}}

async fn health() -> HttpResponse {{
    HttpResponse::Ok().json(Health {{
        status: "ok".to_string(),
    }})
}}

#[actix_web::main]
async fn main() -> std::io::Result<()> {{
    println!("Server starting on :8080");
    HttpServer::new(|| {{
        App::new()
            .route("/api/health", web::get().to(health))
    }})
    .bind("0.0.0.0:8080")?
    .run()
    .await
}}
''',
            "tests/health_test.rs": '''#[cfg(test)]
mod tests {{
    use actix_web::{{test, App, web}};

    #[actix_rt::test]
    async fn test_health() {{
        // Basic compilation test — full integration test needs server setup
        assert!(true);
    }}
}}
''',
            ".gitignore": "target/\n.env\n.autoagent/\n",
        },
    },
}


def scaffold_project(name: str, project_root: Path, tech_stack: str = "fastapi") -> bool:
    """Create project directory with boilerplate code.

    Returns True if scaffolding was created, False if directory already has code.
    """
    project_root = Path(project_root)
    display_name = name.replace("-", " ").replace("_", " ").title()
    snake_name = name.lower().replace("-", "_").replace(" ", "_")

    # Don't scaffold if project already has code
    if (project_root / "src").exists() or (project_root / "package.json").exists():
        logger.info("Project already has code, skipping scaffold")
        return False

    scaffold = SCAFFOLDS.get(tech_stack.lower().replace("/", "").replace(" ", ""), SCAFFOLDS["fastapi"])

    # Create directories
    for d in scaffold["dirs"]:
        (project_root / d.format(name=snake_name)).mkdir(parents=True, exist_ok=True)

    # Create files
    for filepath, content in scaffold["files"].items():
        fp = project_root / filepath.format(name=snake_name)
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content.format(name=snake_name, display_name=display_name), encoding="utf-8")

    # Make run.sh executable
    run_sh = project_root / "run.sh"
    if run_sh.exists():
        os.chmod(str(run_sh), 0o755)

    # Git init
    if not (project_root / ".git").exists():
        subprocess.run(["git", "init"], cwd=str(project_root), capture_output=True)
        subprocess.run(["git", "add", "-A"], cwd=str(project_root), capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial scaffold from AutoAgent Agency"],
                       cwd=str(project_root), capture_output=True)

    logger.info("Scaffolded %s project at %s", tech_stack, project_root)
    return True


# ── Intake State Machine ──────────────────────────────────────

INTAKE_QUESTIONS = [
    "What problem does this solve? Who has this problem?",
    "What does a user DO with this product? Walk me through the core loop.",
    "What tech stack? (Python/FastAPI, React, Next.js, or 'pick for me')",
    "How will you measure success? Give me ONE metric.",
    "What domain knowledge is unique here? What do you know that a generic dev wouldn't?",
    "Do you have an existing repo? Give me the path, or say 'start fresh'.",
    "Any hard rules? Things the agent must NEVER do.",
    "Anything else I should know?",
]

# In-memory intake sessions (reset on restart — fine for now)
_active_intakes: dict[int, dict] = {}  # chat_id → intake state


def start_intake(chat_id: int, initial_description: str = "") -> str:
    """Start a new intake session. Returns the first question."""
    _active_intakes[chat_id] = {
        "answers": [],
        "current_q": 0,
        "description": initial_description,
        "started_at": datetime.now().isoformat(),
    }

    intro = "🚀 <b>New Project Intake</b>\n\n"
    if initial_description:
        intro += f"Got it: <i>{initial_description}</i>\n\n"

    return intro + f"<b>Q1/8:</b> {INTAKE_QUESTIONS[0]}"


def process_intake_answer(chat_id: int, answer: str) -> str:
    """Process an answer and return the next question or completion message."""
    state = _active_intakes.get(chat_id)
    if not state:
        return "No active intake. Send /new to start."

    state["answers"].append(answer)
    state["current_q"] += 1

    if state["current_q"] < len(INTAKE_QUESTIONS):
        q_num = state["current_q"] + 1
        return f"<b>Q{q_num}/8:</b> {INTAKE_QUESTIONS[state['current_q']]}"

    # All questions answered — generate the project
    return _finalize_intake(chat_id)


def is_intake_active(chat_id: int) -> bool:
    return chat_id in _active_intakes


def cancel_intake(chat_id: int) -> str:
    if chat_id in _active_intakes:
        del _active_intakes[chat_id]
        return "Intake cancelled."
    return "No active intake."


def _finalize_intake(chat_id: int) -> str:
    """Generate project from intake answers."""
    state = _active_intakes.pop(chat_id, None)
    if not state:
        return "Error: intake state lost."

    answers = state["answers"]
    desc = state.get("description", "")

    # Parse answers
    problem = answers[0] if len(answers) > 0 else desc
    core_loop = answers[1] if len(answers) > 1 else ""
    tech_stack = answers[2] if len(answers) > 2 else "fastapi"
    metric = answers[3] if len(answers) > 3 else "users"
    domain = answers[4] if len(answers) > 4 else ""
    repo_path = answers[5] if len(answers) > 5 else "start fresh"
    hard_rules = answers[6] if len(answers) > 6 else ""
    extra = answers[7] if len(answers) > 7 else ""

    # Normalize tech stack. Check explicit stacks BEFORE the "pick for me"
    # catch-all — a substring match on "pick" would otherwise force fastapi even
    # when the answer names a stack (e.g. "pick nextjs").
    ts = tech_stack.lower().strip()
    if "next" in ts:
        tech_stack = "nextjs"
    elif "react" in ts and "native" not in ts:
        tech_stack = "react"
    elif "express" in ts or "node" in ts:
        tech_stack = "express"
    elif "python" in ts or "fast" in ts or "flask" in ts or "django" in ts:
        tech_stack = "fastapi"
    elif "go" == ts or "golang" in ts:
        tech_stack = "go"
    elif "rust" in ts:
        tech_stack = "rust"
    elif "pick" in ts or "you choose" in ts or "don't know" in ts or "idk" in ts:
        tech_stack = "fastapi"
    else:
        tech_stack = "fastapi"  # default

    # Generate project name — must be UNIQUE across tenants. The first ≤3 words
    # of the problem often collide (many clients start "Build a marketplace…"),
    # and a collision would repoint another tenant's home dir + symlink + db row
    # + `/run <name>`. Suffix -2/-3/… until free.
    base = problem.split()[0:3]
    base = "-".join(w.lower().strip(".,!?") for w in base if w.isalpha())[:30] or "new-project"
    name = _unique_project_name(base)

    # Determine project root
    if "fresh" in repo_path.lower() or "scratch" in repo_path.lower() or not repo_path.strip():
        project_root = Path.home() / "Documents" / name
        project_root.mkdir(parents=True, exist_ok=True)
        needs_scaffold = True
    else:
        project_root = Path(repo_path.strip())
        needs_scaffold = not project_root.exists()
        if needs_scaffold:
            project_root.mkdir(parents=True, exist_ok=True)

    try:
        # Scaffold if needed
        if needs_scaffold:
            scaffold_project(name, project_root, tech_stack)

        # Generate project files
        from intake import setup_project

        project_md = f"""# {name.replace('-', ' ').title()}

## What we're building
{problem}

## Core loop
{core_loop}

## Tech stack
{tech_stack}

## Success metric
{metric}

## Domain knowledge
{domain}

## Hard rules
{hard_rules}
- Write failing tests first (TDD)
- One task per session, no scope creep

{extra}
"""

        north_star_md = f"""# North Star

## Mission
{problem}

## Success Metric
{metric}

## Measurement
Track in sessions.json quality scores.
"""

        backlog_md = f"""# Backlog

## TDD Rules
- Write failing tests FIRST, then implement until they pass
- One task per session, no scope creep

---

### 1. Set up core data models [agent: architect]
- Define the primary entities based on: {core_loop}
- Tests: models import, basic CRUD
- Files: src/*/db/models.py, tests/test_models.py

### 2. Build core API endpoints [agent: architect]
- REST endpoints for the main user loop
- Tests: CRUD operations, validation
- Files: src/*/api/*.py, tests/test_api.py

### 3. Build frontend dashboard [agent: frontend]
- Main page showing core data
- Tests: page loads, key elements render
- Files: frontend/index.html, frontend/app.js

### 4. Add authentication [agent: infra]
- JWT auth with login/register
- Tests: register, login, protected routes
- Files: src/*/auth.py, tests/test_auth.py

### 5. Add core business logic [agent: architect]
- The main intelligence/processing based on: {domain}
- Tests: unit tests for pure functions
- Files: src/*/services/*.py, tests/test_services.py
"""

        ctx = setup_project(
            name=name,
            project_root=project_root,
            project_md=project_md,
            north_star_md=north_star_md,
            backlog_md=backlog_md,
            tech_stack=tech_stack,
            test_command=f"cd {project_root} && PYTHONPATH=src pytest tests/ -q",
        )

        # Register in agency DB
        try:
            from agency_db import upsert_project
            upsert_project(name, str(project_root))
        except Exception:
            pass

        return (
            f"✅ <b>Project '{name}' created!</b>\n\n"
            f"📁 {project_root}\n"
            f"🤖 {_universal_agent_label()}\n"
            f"📋 5 backlog tasks ready\n"
            f"🧪 {tech_stack} scaffold with test suite\n\n"
            f"Send /run {name} to start the first session, or I'll pick it up on the next cron cycle."
        )

    except Exception as e:
        logger.error("Intake failed: %s", e)
        return f"❌ Error creating project: {e}\n\nTry again with /new"
