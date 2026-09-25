#!/usr/bin/env python3
"""Terminal director shell — chat with the agency from a dedicated terminal."""
import html
import re

from director_brain import ask_brain
from director_helpers import handle_command
from director_router import ShellState, prompt_text, route_shell_input


_TAG_RE = re.compile(r"</?[^>]+>")


def render_terminal(text: str) -> str:
    """Convert Telegram-style HTML output into terminal-friendly plain text."""
    clean = html.unescape(text or "")
    for tag in ("<b>", "</b>", "<i>", "</i>", "<code>", "</code>"):
        clean = clean.replace(tag, "")
    clean = clean.replace("<pre>", "\n").replace("</pre>", "\n")
    clean = clean.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    clean = _TAG_RE.sub("", clean)
    return clean.strip()


def handle_turn(text: str, state: ShellState) -> tuple[str | None, ShellState, str]:
    """Handle one shell turn and return (response, next_state, transient_status)."""
    decision = route_shell_input(text, state)
    if decision.kind == "noop":
        return "", decision.state, ""
    if decision.kind == "quit":
        return None, decision.state, ""
    if decision.kind == "response":
        return decision.response, decision.state, ""
    if decision.kind == "command":
        response = handle_command(decision.payload)
        if decision.payload == "/help":
            response += (
                "\n\n<b>Shell shortcuts</b>\n"
                "/ship [project] — focus a ship\n"
                "/clearship — clear ship focus\n"
                "Free text like 'what's next?', 'status update', or 'run it' uses the focused ship."
            )
        return response, decision.state, decision.status
    return ask_brain(decision.payload, active_project=decision.state.active_project), decision.state, decision.status


def route_input(text: str) -> str | None:
    """Backward-compatible stateless wrapper for tests."""
    response, _, _ = handle_turn(text, ShellState())
    return response


def main():
    print("IdeaShips Bridge")
    print("Free text routes through the shell router. Type /help for commands. Type /quit to leave.\n")
    state = ShellState()
    while True:
        try:
            user_input = input(prompt_text(state))
        except (EOFError, KeyboardInterrupt):
            print("\nDirector offline.")
            break

        response, state, label = handle_turn(user_input, state)
        if label:
            print(label, flush=True)

        if response is None:
            print("Director offline.")
            break
        if response:
            print(render_terminal(response))
            print()


if __name__ == "__main__":
    main()
