#!/usr/bin/env python3
"""DREAM mode — nightly creative synthesis across projects.

Reviews session activity across ALL projects from the last 24h and generates
cross-project "What if..." ideas by finding complementary capabilities.
"""
import json
from datetime import date, timedelta
from pathlib import Path

# Keyword clusters that represent capabilities. When two projects have
# keywords from different clusters, a connection idea is generated.
_CLUSTERS = {
    "data": {"data", "pipeline", "weather", "sensor", "ndvi", "thermal", "csv", "import", "ingest"},
    "analysis": {"analysis", "scoring", "detection", "prediction", "forecast", "regression", "model", "pattern"},
    "market": {"market", "price", "stock", "trade", "signal", "volatility", "regime", "portfolio"},
    "agriculture": {"farm", "crop", "soil", "field", "harvest", "yield", "irrigation", "weather", "microclimate"},
    "user": {"dashboard", "page", "ui", "ux", "login", "notification", "alert", "whatsapp"},
    "automation": {"automate", "pipeline", "schedule", "cron", "bot", "agent", "session"},
}

# Templates for cross-cluster idea generation
_IDEA_TEMPLATES = [
    ("data", "market", "What if we correlated {a_topic} data with {b_topic} signals to find predictive patterns?"),
    ("data", "analysis", "What if we fed {a_topic} raw data into {b_topic} analysis for deeper insights?"),
    ("agriculture", "market", "What if we connected {a_topic} agricultural data with {b_topic} commodity signals?"),
    ("agriculture", "analysis", "What if we applied {b_topic} techniques to {a_topic} data?"),
    ("data", "agriculture", "What if {a_topic} pipelines could enrich {b_topic} decision-making?"),
    ("user", "analysis", "What if {b_topic} results powered smarter {a_topic} interfaces?"),
    ("automation", "analysis", "What if {a_topic} could trigger {b_topic} runs automatically?"),
]


def _extract_clusters(summary: str) -> set:
    """Find which capability clusters a session summary touches."""
    words = set(summary.lower().split())
    matched = set()
    for cluster_name, keywords in _CLUSTERS.items():
        if words & keywords:
            matched.add(cluster_name)
    return matched


def _load_recent_sessions(sessions_file: Path, cutoff: date) -> list:
    """Load sessions from file, filtering to those on or after cutoff date."""
    if not sessions_file.exists():
        return []
    try:
        sessions = json.loads(sessions_file.read_text(encoding="utf-8"))
    except Exception:
        return []
    recent = []
    for s in sessions:
        try:
            session_date = date.fromisoformat(s.get("date", ""))
        except (ValueError, TypeError):
            continue
        if session_date >= cutoff:
            recent.append(s)
    return recent


def generate_dream_ideas(project_sessions: dict) -> list:
    """Generate cross-project ideas from recent session activity.

    Args:
        project_sessions: {project_name: Path_to_sessions_file}

    Returns:
        List of idea dicts with keys: idea, confidence, effort, date, projects
    """
    cutoff = date.today() - timedelta(days=1)
    today_str = date.today().isoformat()

    # Collect clusters per project
    project_clusters = {}  # {project: {cluster: [summaries]}}
    for name, sessions_file in project_sessions.items():
        recent = _load_recent_sessions(sessions_file, cutoff)
        if not recent:
            continue
        clusters_found = {}
        for s in recent:
            summary = s.get("summary", "")
            for c in _extract_clusters(summary):
                clusters_found.setdefault(c, []).append(summary)
        if clusters_found:
            project_clusters[name] = clusters_found

    if len(project_clusters) < 2:
        return []

    # Find cross-project connections
    ideas = []
    project_names = list(project_clusters.keys())
    for i, proj_a in enumerate(project_names):
        for proj_b in project_names[i + 1:]:
            clusters_a = set(project_clusters[proj_a].keys())
            clusters_b = set(project_clusters[proj_b].keys())
            for ca, cb, template in _IDEA_TEMPLATES:
                if ca in clusters_a and cb in clusters_b:
                    idea_text = template.format(a_topic=proj_a, b_topic=proj_b)
                    ideas.append({
                        "idea": idea_text,
                        "confidence": "medium",
                        "effort": "medium",
                        "date": today_str,
                        "projects": [proj_a, proj_b],
                    })
                elif cb in clusters_a and ca in clusters_b:
                    idea_text = template.format(a_topic=proj_b, b_topic=proj_a)
                    ideas.append({
                        "idea": idea_text,
                        "confidence": "medium",
                        "effort": "medium",
                        "date": today_str,
                        "projects": [proj_a, proj_b],
                    })

    # Deduplicate by idea text
    seen = set()
    unique = []
    for idea in ideas:
        if idea["idea"] not in seen:
            seen.add(idea["idea"])
            unique.append(idea)

    # Score confidence based on how many sessions contributed
    for idea in unique:
        total_sessions = sum(
            len(_load_recent_sessions(project_sessions[p], cutoff))
            for p in idea["projects"] if p in project_sessions
        )
        if total_sessions >= 4:
            idea["confidence"] = "high"
        elif total_sessions <= 1:
            idea["confidence"] = "low"

    return unique


def stress_test_idea(idea: dict) -> str:
    """Run the pursue/ruminate/forget gate on an idea.

    Uses 3 quick checks:
    1. Specificity: does it name concrete features/data, or is it vague?
    2. Effort vs impact: is the effort justified by the potential?
    3. User test: would a real user care, or is this engineer navel-gazing?

    Returns: "pursue" | "ruminate" | "forget"
    """
    text = idea.get("idea", "")
    conf = idea.get("confidence", "low")
    effort = idea.get("effort", "large")

    # Gate 1: Specificity — vague ideas get ruminated, not pursued
    vague_words = {"could", "might", "maybe", "possibly", "explore", "consider", "interesting"}
    vague_count = sum(1 for w in text.lower().split() if w in vague_words)
    is_vague = vague_count >= 2

    # Gate 2: Effort vs confidence
    effort_score = {"small": 1, "medium": 2, "large": 3}.get(effort, 3)
    conf_score = {"high": 3, "medium": 2, "low": 1}.get(conf, 1)

    # Gate 3: Does it create user value or just technical satisfaction?
    user_words = {"user", "farmer", "trader", "investor", "customer", "signup", "revenue", "retention"}
    has_user_value = any(w in text.lower() for w in user_words)

    # Decision
    if conf_score >= 3 and effort_score <= 2 and not is_vague:
        return "pursue"
    if conf_score >= 2 and has_user_value and not is_vague:
        return "pursue"
    if is_vague or (effort_score >= 3 and conf_score <= 1):
        return "forget"
    return "ruminate"


def write_dreams(ideas: list, output_path: Path) -> None:
    """Write dream ideas to markdown, stress-tested through pursue/ruminate/forget gate."""
    if not ideas:
        return

    today_str = date.today().isoformat()
    lines = [f"\n## {today_str} — DREAM synthesis\n"]

    pursue, ruminate, forget = [], [], []
    for idea in ideas:
        verdict = stress_test_idea(idea)
        idea["verdict"] = verdict
        if verdict == "pursue": pursue.append(idea)
        elif verdict == "ruminate": ruminate.append(idea)
        else: forget.append(idea)

    if pursue:
        lines.append("\n### PURSUE (add to backlog)\n")
        for idea in pursue:
            lines.append(f"- **{idea['idea']}** ({', '.join(idea['projects'])})\n")
    if ruminate:
        lines.append("\n### RUMINATE (revisit next week)\n")
        for idea in ruminate:
            lines.append(f"- {idea['idea']} ({', '.join(idea['projects'])})\n")
    if forget:
        lines.append(f"\n_Filtered out {len(forget)} low-value ideas._\n")

    new_content = "".join(lines)
    if output_path.exists():
        existing = output_path.read_text(encoding="utf-8")
        output_path.write_text(existing + new_content, encoding="utf-8")
    else:
        header = "# Dreams\n\nCross-project ideas generated by DREAM mode.\n"
        output_path.write_text(header + new_content, encoding="utf-8")

    return {"pursue": len(pursue), "ruminate": len(ruminate), "forget": len(forget)}
