#!/usr/bin/env python3
"""Red Intel — Build agents provide Red agents with target knowledge.

Scans a project's codebase to identify attack surface, then generates
a structured hunt brief that the Hunter agent can use for targeting.

Usage:
    from red_intel import get_project_attack_surface, generate_hunt_brief, save_hunt_brief
    surface = get_project_attack_surface(ctx)
    brief = generate_hunt_brief(ctx)
    save_hunt_brief(ctx, Path("hunt_brief.md"))
"""
import logging
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Regex patterns for Python route decorators
_ROUTE_DECORATOR = re.compile(
    r'@(?:app|router|api)\.(get|post|put|patch|delete|options|head)\(\s*["\']([^"\']+)["\']',
    re.IGNORECASE,
)

# Detect auth dependencies
_AUTH_DEPENDS = re.compile(
    r'Depends\(\s*(get_current_user|require_auth|verify_token|auth|get_user)',
    re.IGNORECASE,
)

# Detect user input parameters
_QUERY_PARAM = re.compile(r'(\w+)\s*[:=]\s*(Query|Path|Body|Header|Cookie)\s*\(', re.IGNORECASE)
_BODY_MODEL = re.compile(r'(\w+)\s*:\s*(\w+)\s*', re.IGNORECASE)

# SQLAlchemy / Tortoise model detection
_DB_MODEL = re.compile(r'class\s+(\w+)\s*\(.*(?:Base|Model|DeclarativeBase|SQLModel).*\):')
_SENSITIVE_FIELD = re.compile(
    r'(?:password|secret|token|api_key|ssn|credit_card|hash|salt|private_key)',
    re.IGNORECASE,
)


def _scan_python_files(root: Path) -> list[Path]:
    """Collect all Python files under root, excluding venv/node_modules."""
    skip = {'.venv', 'venv', 'node_modules', '__pycache__', '.git', '.autoagent'}
    results = []
    for p in root.rglob('*.py'):
        if any(part in skip for part in p.parts):
            continue
        results.append(p)
    return results


def _parse_routes(files: list[Path]) -> list[dict]:
    """Extract route definitions from Python files."""
    routes = []
    for fp in files:
        try:
            content = fp.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            continue

        lines = content.split('\n')
        for i, line in enumerate(lines):
            match = _ROUTE_DECORATOR.search(line)
            if not match:
                continue

            method = match.group(1).upper()
            path = match.group(2)

            # Look ahead in the function signature for auth and params
            func_block = '\n'.join(lines[i:min(i + 15, len(lines))])
            has_auth = bool(_AUTH_DEPENDS.search(func_block))

            params = []
            for pm in _QUERY_PARAM.finditer(func_block):
                params.append({'name': pm.group(1), 'type': pm.group(2)})

            routes.append({
                'method': method,
                'path': path,
                'has_auth': has_auth,
                'params': params,
                'file': str(fp),
                'line': i + 1,
            })

    return routes


def _parse_db_models(files: list[Path]) -> list[dict]:
    """Extract database models and flag sensitive fields."""
    models = []
    for fp in files:
        try:
            content = fp.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            continue

        for match in _DB_MODEL.finditer(content):
            model_name = match.group(1)
            # Grab the class body (next ~40 lines)
            start = match.start()
            block = content[start:start + 2000]
            block_lines = block.split('\n')

            sensitive = []
            all_fields = []
            for bline in block_lines[1:]:
                if bline.strip() and not bline[0].isspace() and not bline.strip().startswith('#'):
                    break  # End of class body
                field_match = re.match(r'\s+(\w+)\s*[=:]', bline)
                if field_match:
                    fname = field_match.group(1)
                    if not fname.startswith('_'):
                        all_fields.append(fname)
                        if _SENSITIVE_FIELD.search(fname):
                            sensitive.append(fname)

            models.append({
                'name': model_name,
                'file': str(fp),
                'fields': all_fields,
                'sensitive_fields': sensitive,
            })

    return models


def _load_known_weaknesses(project_root: Path) -> list[str]:
    """Load known weaknesses from security_findings.md if it exists."""
    candidates = [
        project_root / 'security_findings.md',
        project_root / '.autoagent' / 'security_findings.md',
        project_root / 'docs' / 'security_findings.md',
    ]
    weaknesses = []
    for fp in candidates:
        if fp.exists():
            try:
                content = fp.read_text(encoding='utf-8', errors='ignore')
                for line in content.split('\n'):
                    line = line.strip()
                    if line.startswith('- ') or line.startswith('* '):
                        weaknesses.append(line[2:].strip())
            except Exception:
                pass
    return weaknesses


def get_project_attack_surface(ctx) -> dict:
    """Scan a project's codebase and return its attack surface.

    Args:
        ctx: ProjectContext with .project_root

    Returns:
        dict with keys: routes, unauth_routes, auth_routes,
        input_routes, db_models, known_weaknesses
    """
    root = Path(ctx.project_root)
    files = _scan_python_files(root)

    routes = _parse_routes(files)
    db_models = _parse_db_models(files)
    known_weaknesses = _load_known_weaknesses(root)

    unauth = [r for r in routes if not r['has_auth']]
    auth = [r for r in routes if r['has_auth']]
    with_input = [r for r in routes if r['params']]

    logger.info(
        "Attack surface for %s: %d routes (%d unauth, %d auth), %d models, %d known weaknesses",
        getattr(ctx, 'name', 'unknown'), len(routes), len(unauth), len(auth),
        len(db_models), len(known_weaknesses),
    )

    return {
        'project': getattr(ctx, 'name', 'unknown'),
        'routes': routes,
        'unauth_routes': unauth,
        'auth_routes': auth,
        'input_routes': with_input,
        'db_models': db_models,
        'known_weaknesses': known_weaknesses,
    }


def generate_hunt_brief(ctx) -> str:
    """Generate a markdown hunt brief for the Hunter agent.

    Args:
        ctx: ProjectContext with .project_root and .name

    Returns:
        Markdown string with structured attack surface intel.
    """
    surface = get_project_attack_surface(ctx)
    lines = [f"# Hunt Brief: {surface['project']}", ""]

    # Unauthenticated endpoints
    lines.append("## Unauthenticated Endpoints")
    if surface['unauth_routes']:
        for r in surface['unauth_routes']:
            params_str = ""
            if r['params']:
                params_str = " (accepts " + ", ".join(p['name'] for p in r['params']) + ")"
            lines.append(f"- {r['method']} {r['path']}{params_str}")
    else:
        lines.append("- (none found)")
    lines.append("")

    # Auth endpoints
    lines.append("## Auth Endpoints (test for bypass)")
    if surface['auth_routes']:
        for r in surface['auth_routes']:
            params_str = ""
            if r['params']:
                params_str = " (accepts " + ", ".join(p['name'] for p in r['params']) + ")"
            lines.append(f"- {r['method']} {r['path']} (requires auth){params_str}")
    else:
        lines.append("- (none found)")
    lines.append("")

    # Routes accepting user input
    lines.append("## Routes Accepting User Input")
    if surface['input_routes']:
        for r in surface['input_routes']:
            param_details = ", ".join(f"{p['name']}:{p['type']}" for p in r['params'])
            auth_tag = " [AUTH]" if r['has_auth'] else " [NO AUTH]"
            lines.append(f"- {r['method']} {r['path']} — {param_details}{auth_tag}")
    else:
        lines.append("- (none found)")
    lines.append("")

    # Database models with sensitive fields
    models_with_sensitive = [m for m in surface['db_models'] if m['sensitive_fields']]
    lines.append("## Database Models with Sensitive Fields")
    if models_with_sensitive:
        for m in models_with_sensitive:
            lines.append(f"- **{m['name']}**: {', '.join(m['sensitive_fields'])}")
    else:
        lines.append("- (none found)")
    lines.append("")

    # Known weak spots
    lines.append("## Known Weak Spots")
    if surface['known_weaknesses']:
        for w in surface['known_weaknesses']:
            lines.append(f"- {w}")
    else:
        lines.append("- (none from security_findings.md)")
    lines.append("")

    # Summary stats
    lines.append("## Summary")
    lines.append(f"- Total routes: {len(surface['routes'])}")
    lines.append(f"- Unauthenticated: {len(surface['unauth_routes'])}")
    lines.append(f"- Auth-protected: {len(surface['auth_routes'])}")
    lines.append(f"- Accepting input: {len(surface['input_routes'])}")
    lines.append(f"- DB models: {len(surface['db_models'])}")
    lines.append("")

    return '\n'.join(lines)


def save_hunt_brief(ctx, output_path: Optional[Path] = None):
    """Write the hunt brief to a file.

    Args:
        ctx: ProjectContext
        output_path: Where to write. Defaults to <project_home>/hunt_brief.md
    """
    if output_path is None:
        output_path = Path(ctx.project_root) / '.autoagent' / 'hunt_brief.md'

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    brief = generate_hunt_brief(ctx)
    output_path.write_text(brief, encoding='utf-8')
    logger.info("Hunt brief saved to %s", output_path)
    return output_path
