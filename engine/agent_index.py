#!/usr/bin/env python3
"""Agent Index — keyword extraction, caching, and smart auto-routing.

Parses agent .md files to extract structured metadata (keywords, owned files,
skill triggers), caches as .index.json, and provides task→agent scoring.
"""
import json
import re
import time
from pathlib import Path
from typing import Optional

from registry import ProjectContext

# Words too common to be useful for routing
_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "must", "shall", "can", "that", "this",
    "these", "those", "it", "its", "you", "your", "we", "our", "they",
    "their", "all", "each", "every", "any", "not", "no", "if", "when",
    "how", "what", "which", "who", "where", "use", "using", "read",
    "write", "file", "files", "data", "based", "new", "add", "update",
}

# Skills every agent should see regardless of specialization
UNIVERSAL_SKILLS = {
    "coding", "testing", "debugging", "git", "security",
    "clean-architecture", "quality-standards", "agent-patterns",
}


def _extract_section(text: str, heading_pattern: str) -> str:
    """Extract content under a ## heading matching pattern until next ## heading."""
    lines = text.splitlines()
    capturing = False
    result = []
    for line in lines:
        if line.strip().startswith("## ") or line.strip().startswith("# "):
            if capturing:
                break
            if re.search(heading_pattern, line, re.IGNORECASE):
                capturing = True
                continue
        elif capturing:
            result.append(line)
    return "\n".join(result).strip()


def _tokenize(text: str) -> set[str]:
    """Extract meaningful lowercase tokens from text."""
    words = re.findall(r'[a-zA-Z][a-zA-Z0-9_.-]{2,}', text.lower())
    return {w for w in words if w not in _STOPWORDS and len(w) > 2}


def _extract_file_paths(text: str) -> list[str]:
    """Extract file/directory paths from text."""
    patterns = re.findall(r'[\w/.-]+\.(?:py|js|html|css|md|json|ts|yaml|yml)', text)
    dirs = re.findall(r'(?:src|services|routes|models|frontend|engine|tests)/[\w/.-]+', text)
    return list(set(patterns + dirs))


def extract_agent_keywords(agent_md_text: str) -> dict:
    """Parse an agent .md file and extract structured metadata.

    Returns dict with: name, display_name, keywords, owned_files, skill_triggers.
    """
    lines = agent_md_text.splitlines()

    # Extract name from first # heading
    name = ""
    display_name = ""
    for line in lines:
        if line.strip().startswith("# "):
            display_name = line.strip().lstrip("# ").strip()
            name = display_name.lower().replace(" ", "-")
            break

    # Extract keywords from expertise/responsibility sections
    expertise_text = (
        _extract_section(agent_md_text, r'expertise|responsibility|your role|what you own')
        or _extract_section(agent_md_text, r'architecture|protocols|principles')
    )
    keywords = _tokenize(expertise_text) if expertise_text else _tokenize(agent_md_text)

    # Also add words from the first paragraph (role description)
    first_para = ""
    capturing = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("# "):
            capturing = True
            continue
        if capturing:
            if stripped.startswith("## ") or stripped.startswith("---"):
                break
            if stripped:
                first_para += " " + stripped
    keywords |= _tokenize(first_para)

    # Extract owned files/directories
    owned_files = _extract_file_paths(agent_md_text)

    # Extract skill triggers
    skill_triggers = []
    for m in re.finditer(r'\*\*Trigger\*\*:\s*(.+)', agent_md_text):
        skill_triggers.append(m.group(1).strip().lower())

    # Extract skill names
    skill_names = [m.group(1).strip() for m in re.finditer(r'##\s*Skill:\s*(.+)', agent_md_text)]

    return {
        "name": name,
        "display_name": display_name,
        "keywords": sorted(keywords),
        "owned_files": owned_files,
        "skill_triggers": skill_triggers,
        "skill_names": skill_names,
    }


def build_agent_index(ctx: ProjectContext) -> list[dict]:
    """Scan agents_dir, extract keywords from each agent .md."""
    if not ctx.agents_dir.exists():
        return []
    index = []
    for f in sorted(ctx.agents_dir.glob("*.md")):
        if f.name.startswith("."):
            continue
        try:
            text = f.read_text(encoding="utf-8")
            entry = extract_agent_keywords(text)
            entry["file"] = str(f)
            entry["name"] = f.stem  # use filename as canonical name
            index.append(entry)
        except Exception:
            continue
    return index


def load_or_build_index(ctx: ProjectContext, max_age_seconds: int = 3600) -> list[dict]:
    """Load cached index from .index.json if fresh, otherwise rebuild."""
    cache_file = ctx.agents_dir / ".index.json"
    if cache_file.exists():
        try:
            cache = json.loads(cache_file.read_text(encoding="utf-8"))
            if time.time() - cache.get("built_at", 0) < max_age_seconds:
                return cache.get("agents", [])
        except Exception:
            pass

    index = build_agent_index(ctx)
    try:
        cache_file.write_text(json.dumps({
            "built_at": time.time(),
            "agents": index,
        }, indent=2), encoding="utf-8")
    except Exception:
        pass
    return index


# ── Smart Auto-Routing ───────────────────────────────────────────


def score_agent_match(task_text: str, agent_entry: dict,
                      changed_files: Optional[list[str]] = None) -> float:
    """Score how well an agent matches a task (0.0 - 1.0).

    Scoring weights:
      - keyword_coverage: fraction of task words found in agent keywords (weight: 0.5)
      - file_overlap: fraction of changed files in agent's owned paths (weight: 0.3)
      - trigger_match: any skill trigger phrase found in task (weight: 0.2)
    """
    task_tokens = _tokenize(task_text)
    agent_keywords = set(agent_entry.get("keywords", []))

    # Keyword coverage: what fraction of the task's words does this agent know about?
    if task_tokens and agent_keywords:
        hits = sum(1 for t in task_tokens if t in agent_keywords)
        keyword_score = hits / len(task_tokens)
    else:
        keyword_score = 0

    # File overlap
    file_score = 0
    if changed_files and agent_entry.get("owned_files"):
        owned = agent_entry["owned_files"]
        matches = sum(1 for cf in changed_files if any(o in cf for o in owned))
        file_score = matches / len(changed_files) if changed_files else 0

    # Trigger match
    trigger_score = 0
    triggers = agent_entry.get("skill_triggers", [])
    task_lower = task_text.lower()
    if triggers:
        matches = sum(1 for t in triggers if t in task_lower)
        trigger_score = min(1.0, matches / max(1, len(triggers)))

    return 0.5 * keyword_score + 0.3 * file_score + 0.2 * trigger_score


def auto_route(ctx: ProjectContext, task_text: str,
               changed_files: Optional[list[str]] = None,
               threshold: float = 0.08) -> Optional[str]:
    """Find the best agent for a task using keyword/file/trigger matching.

    Returns agent name or None if no match above threshold.
    """
    index = load_or_build_index(ctx)
    if not index:
        return None

    scored = []
    for entry in index:
        score = score_agent_match(task_text, entry, changed_files)
        if score >= threshold:
            scored.append((entry["name"], score))

    if not scored:
        return None

    # Sort by score descending
    scored.sort(key=lambda x: x[1], reverse=True)

    # Verify agent file exists
    best_name = scored[0][0]
    agent_file = ctx.agents_dir / f"{best_name}.md"
    if agent_file.exists():
        return best_name

    return None
