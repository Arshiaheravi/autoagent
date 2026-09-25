"""Small CLI parsing helpers shared by command modules."""


def parse_positive_int(args: list[str], flag: str, default=None,
                       minimum: int = 1) -> tuple[int | None, str | None]:
    """Parse a positive integer flag value without raising on user input."""
    if flag not in args:
        return default, None
    idx = args.index(flag)
    if idx + 1 >= len(args):
        return default, f"{flag} requires a value"
    raw = args[idx + 1]
    try:
        value = int(raw)
    except ValueError:
        return default, f"{flag} expects an integer, got '{raw}'"
    if value < minimum:
        return default, f"{flag} must be >= {minimum}"
    return value, None
