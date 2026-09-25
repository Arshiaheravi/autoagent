#!/usr/bin/env python3
"""Intent router for the terminal agency shell."""
from dataclasses import dataclass


@dataclass(frozen=True)
class ShellState:
    active_project: str | None = None


@dataclass(frozen=True)
class RouteDecision:
    kind: str
    payload: str = ""
    response: str = ""
    state: ShellState = ShellState()
    status: str = ""


_QUIT = {"quit", "exit", "/quit", "/exit", ":q"}
_NEXT_PHRASES = (
    "what's next", "whats next", "what is next", "next task",
    "what should we work on", "what should i work on", "what should we do next",
)
_STATUS_PHRASES = (
    "status", "status update", "how are things",
    "what's going on", "whats going on",
    "where are we", "give me an update", "give me a status update",
)
_PROJECTS_PHRASES = (
    "projects", "show projects", "list projects", "what projects",
    "which projects", "what ships", "which ships",
)
_RUN_PREFIXES = ("run ", "start ", "launch ")
_RUN_EXACT = {"run it", "start it", "launch it", "run this", "start this", "launch this"}
_FOCUS_PREFIXES = ("/ship ", "focus on ", "work on ", "switch to ")


def _projects() -> list[str]:
    from registry import list_projects
    return [p["name"] for p in list_projects()]


def resolve_project_name(raw: str) -> str | None:
    name = raw.strip().strip("/").strip()
    if not name:
        return None
    for project in _projects():
        if project.lower() == name.lower():
            return project
    return None


def find_project_in_text(text: str) -> str | None:
    lowered = text.lower()
    for project in _projects():
        if project.lower() in lowered:
            return project
    return None


def _question_with_focus(text: str, project: str | None) -> str:
    if not project:
        return text
    lowered = text.lower()
    if project.lower() in lowered:
        return text
    return f"For {project}, {text}"


def route_shell_input(text: str, state: ShellState) -> RouteDecision:
    stripped = text.strip()
    lowered = " ".join(stripped.lower().split())

    if not stripped:
        return RouteDecision(kind="noop", state=state)
    if lowered in _QUIT:
        return RouteDecision(kind="quit", state=state)

    if lowered == "/clearship":
        return RouteDecision(
            kind="response",
            response="Ship focus cleared.",
            state=ShellState(),
        )

    if lowered in ("/ship", "ship"):
        return RouteDecision(
            kind="response",
            response="Usage: /ship <project>",
            state=state,
        )

    for prefix in _FOCUS_PREFIXES:
        if lowered.startswith(prefix):
            project = resolve_project_name(stripped[len(prefix):])
            if not project:
                return RouteDecision(
                    kind="response",
                    response="Unknown ship. Try /projects or use a registered project name.",
                    state=state,
                )
            return RouteDecision(
                kind="response",
                response=f"Focused on {project}.",
                state=ShellState(active_project=project),
            )

    if stripped.startswith("/"):
        normalized = stripped.split(maxsplit=1)
        head = normalized[0].lower()
        payload = head if len(normalized) == 1 else f"{head} {normalized[1]}"
        return RouteDecision(kind="command", payload=payload, state=state, status="processing...")

    mentioned_project = find_project_in_text(stripped)
    target_project = mentioned_project or state.active_project

    if any(phrase in lowered for phrase in _PROJECTS_PHRASES):
        return RouteDecision(
            kind="command",
            payload="/projects",
            state=state if mentioned_project is None else ShellState(active_project=target_project),
            status="checking ships...",
        )

    if any(phrase in lowered for phrase in _STATUS_PHRASES):
        if target_project:
            return RouteDecision(
                kind="command",
                payload=f"/orchestrator {target_project}",
                state=state if mentioned_project is None else ShellState(active_project=target_project),
                status="checking route...",
            )
        return RouteDecision(
            kind="command",
            payload="/status",
            state=state,
            status="checking status...",
        )

    if target_project and any(phrase in lowered for phrase in _NEXT_PHRASES):
        return RouteDecision(
            kind="command",
            payload=f"/orchestrator {target_project}",
            state=state if mentioned_project is None else ShellState(active_project=target_project),
            status="routing...",
        )
    if any(phrase in lowered for phrase in _NEXT_PHRASES):
        return RouteDecision(
            kind="response",
            response="No ship is in focus. Use /ship <project> or mention a project by name.",
            state=state,
        )

    for prefix in _RUN_PREFIXES:
        if lowered.startswith(prefix):
            project = resolve_project_name(stripped[len(prefix):]) or target_project
            if project:
                return RouteDecision(
                    kind="command",
                    payload=f"/run {project}",
                    state=ShellState(active_project=project),
                    status="launching...",
                )
    if lowered in _RUN_EXACT and target_project:
        return RouteDecision(
            kind="command",
            payload=f"/run {target_project}",
            state=ShellState(active_project=target_project),
            status="launching...",
        )

    return RouteDecision(
        kind="brain",
        payload=_question_with_focus(stripped, target_project),
        state=state if mentioned_project is None else ShellState(active_project=mentioned_project),
        status="thinking...",
    )


def prompt_text(state: ShellState) -> str:
    return f"bridge:{state.active_project}> " if state.active_project else "bridge> "
