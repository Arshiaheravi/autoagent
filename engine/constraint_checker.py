"""
ContextCov Constraint Checker — extract NEVER/ALWAYS/MUST rules from .md files
and validate changed files against file-pattern constraints.

Pure functions: Path in, dicts out. No ProjectContext coupling.
"""
import re
from pathlib import Path

# Match lines containing uppercase NEVER, ALWAYS, or MUST as whole words
_CONSTRAINT_RE = re.compile(
    r'^.*?\b(NEVER|ALWAYS|MUST)\b.*$', re.MULTILINE
)

# Extract file/dir patterns from backtick-wrapped content (e.g. `autoagent/`)
# Matches path-like tokens: word/ or word/word or ./word
_BACKTICK_PATH_RE = re.compile(r'`[^`]*?(\b[\w._-]+/[\w._/-]*)`|`(\./[\w._/-]+)`')

# Also catch .ext patterns like .env, .secret
_DOT_FILE_RE = re.compile(r'`(\.[a-zA-Z0-9_]+)`')


def extract_constraints(md_path: Path) -> list[dict]:
    """Parse a single .md file for NEVER/ALWAYS/MUST constraint lines.

    Returns list of dicts: {keyword, rule, source_file, line_num}
    """
    if not md_path.exists():
        return []

    text = md_path.read_text(encoding="utf-8", errors="replace")
    results = []

    for i, line in enumerate(text.splitlines(), start=1):
        m = _CONSTRAINT_RE.match(line)
        if m:
            keyword = m.group(1)
            results.append({
                "keyword": keyword,
                "rule": line.strip(),
                "source_file": str(md_path),
                "line_num": i,
            })

    return results


def extract_all_constraints(directory: Path) -> list[dict]:
    """Scan all .md files in a directory for constraints."""
    if not directory.exists():
        return []

    results = []
    for md_file in sorted(directory.glob("*.md")):
        results.extend(extract_constraints(md_file))
    return results


def classify_constraint(rule: dict) -> dict:
    """Add type and file_pattern fields to a constraint dict.

    - If the rule text contains a backtick-wrapped path (with /), set file_pattern
    - If the rule text contains a backtick-wrapped .ext, set file_pattern
    - Otherwise, mark as behavioral (not auto-checkable)
    """
    text = rule["rule"]
    classified = dict(rule)

    # Try backtick path first (e.g. `autoagent/`, `secrets/`)
    path_match = _BACKTICK_PATH_RE.search(text)
    if path_match:
        classified["file_pattern"] = path_match.group(1) or path_match.group(2)
        classified["type"] = "file_pattern"
        return classified

    # Try dot-file pattern (e.g. `.env`)
    dot_match = _DOT_FILE_RE.search(text)
    if dot_match:
        classified["file_pattern"] = dot_match.group(1)
        classified["type"] = "file_pattern"
        return classified

    classified["file_pattern"] = None
    classified["type"] = "behavioral"
    return classified


# Match "N tests must stay green" in PROJECT.md
_TEST_COUNT_RE = re.compile(r'\b(\d+)\s+tests\s+must\s+stay\s+green\b')

# Split activity_log.md into session blocks
_SESSION_HEADER_RE = re.compile(r'^## .+', re.MULTILINE)


def validate_session(prompt_path: Path, activity_path: Path) -> list[dict]:
    """Check activity_log.md sessions against behavioral constraints in PROMPT.md.

    For each behavioral constraint (NEVER/ALWAYS/MUST), scan each session block
    in activity_log.md. A violation is flagged when:
    - A NEVER rule's key phrase appears in a session's DONE/IMPACT text
    - An ALWAYS rule's key phrase is negated (e.g. "without running tests")

    Returns list of dicts: {session_header, rule, keyword, reason}
    """
    if not prompt_path.exists() or not activity_path.exists():
        return []

    constraints = extract_constraints(prompt_path)
    if not constraints:
        return []

    activity_text = activity_path.read_text(encoding="utf-8", errors="replace")

    # Split into session blocks
    headers = list(_SESSION_HEADER_RE.finditer(activity_text))
    if not headers:
        return []

    sessions = []
    for i, header_match in enumerate(headers):
        start = header_match.start()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(activity_text)
        sessions.append({
            "header": header_match.group(0),
            "body": activity_text[start:end],
        })

    violations = []
    for session in sessions:
        body_lower = session["body"].lower()
        for constraint in constraints:
            keyword = constraint["keyword"]
            rule_text = constraint["rule"]

            if keyword == "NEVER":
                # Extract the action phrase after NEVER
                # e.g. "NEVER commit red tests" -> check if session mentions
                # "commit red tests" or related phrases
                action = re.sub(r'^.*?\bNEVER\b\s*', '', rule_text, flags=re.IGNORECASE).strip()
                action = re.sub(r'\s*—.*$', '', action)  # strip trailing explanation
                # Check key words from the action in the session body
                action_words = [w.lower() for w in action.split() if len(w) > 3]
                if action_words and all(w in body_lower for w in action_words):
                    violations.append({
                        "session_header": session["header"],
                        "rule": rule_text,
                        "keyword": keyword,
                        "reason": f"Session text contains all key words from NEVER rule: {action_words}",
                    })

            elif keyword == "ALWAYS":
                # "ALWAYS run tests before committing" -> check for "without running tests"
                action = re.sub(r'^.*?\bALWAYS\b\s*', '', rule_text, flags=re.IGNORECASE).strip()
                action = re.sub(r'\s*—.*$', '', action)
                action_words = [w.lower() for w in action.split() if len(w) > 3]
                # Look for negation patterns + action words
                negation_patterns = ["without", "didn't", "did not", "forgot to", "skipped", "failed to"]
                for neg in negation_patterns:
                    if neg in body_lower and action_words and any(w in body_lower for w in action_words):
                        violations.append({
                            "session_header": session["header"],
                            "rule": rule_text,
                            "keyword": keyword,
                            "reason": f"Session contains negation '{neg}' near ALWAYS-required action: {action_words}",
                        })
                        break  # one violation per rule per session

    return violations


def auto_fix_test_count(
    project_md_path: Path, actual_count: int
) -> tuple[bool, int | None, int]:
    """Compare PROJECT.md 'N tests must stay green' with actual_count.

    Returns (updated: bool, old_count: int|None, new_count: int).
    If the count is already correct or no pattern is found, updated=False.
    """
    if not project_md_path.exists():
        return False, None, actual_count

    text = project_md_path.read_text(encoding="utf-8", errors="replace")
    match = _TEST_COUNT_RE.search(text)
    if not match:
        return False, None, actual_count

    old_count = int(match.group(1))
    if old_count == actual_count:
        return False, old_count, actual_count

    new_text = text[:match.start(1)] + str(actual_count) + text[match.end(1):]
    project_md_path.write_text(new_text, encoding="utf-8")
    return True, old_count, actual_count


def check_file_constraints(
    rules: list[dict], changed_files: list[str]
) -> list[dict]:
    """Check changed files against file-pattern constraints.

    Args:
        rules: list of constraint dicts (must have file_pattern key)
        changed_files: list of file paths (relative to repo root)

    Returns:
        list of violation dicts: {file, rule}
    """
    violations = []
    for rule in rules:
        pattern = rule.get("file_pattern")
        if not pattern:
            continue
        for f in changed_files:
            if pattern in f:
                violations.append({"file": f, "rule": rule})
    return violations
