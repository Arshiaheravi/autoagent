"""Context engineering utilities — KV-cache-friendly prompt manipulation."""


def recite_todos(prompt: str, todos: list[str]) -> str:
    """Append open TODO items to prompt tail, keeping prefix byte-identical for KV-cache."""
    if not todos:
        return prompt
    block = "\n\n--- OPEN ITEMS (recital) ---\n"
    for i, item in enumerate(todos, 1):
        block += f"{i}. {item}\n"
    return prompt + block


def append_context(prompt: str, new_turn: str) -> str:
    """Append context turn to prompt tail. Prior content never modified (append-only)."""
    return prompt + "\n" + new_turn
