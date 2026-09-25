"""Task complexity estimator — split oversized tasks before starting."""

import re, math

COMPLEX_KEYWORDS = [
    "migrate", "migration", "refactor", "rewrite", "redesign",
    "overhaul", "replace", "rearchitect", "split", "merge",
]
SPLIT_THRESHOLD = 5


def _count_files(text: str) -> int:
    m = re.search(r"-\s*Files?:\s*(.+)", text, re.IGNORECASE)
    if m:
        return len([f.strip() for f in m.group(1).split(",") if f.strip()])
    return len(set(re.findall(r"\b[\w/]+\.(?:py|md|js|ts)\b", text)))


def _count_tests(text: str) -> int:
    return len(re.findall(r"\btest_\w+", text))


def _count_complex_keywords(text: str) -> int:
    lower = text.lower()
    return sum(1 for kw in COMPLEX_KEYWORDS if kw in lower)


def _compute_score(file_count: int, test_count: int, keyword_count: int) -> int:
    score = 1.0 + min(file_count, 8) * 0.8 + min(test_count, 10) * 0.3 + keyword_count * 0.7
    return min(10, max(1, math.ceil(score)))


def _generate_subtasks(text: str) -> list[str]:
    title_match = re.search(r"###?\s*(.+)", text)
    title = title_match.group(1).strip() if title_match else "Task"
    files_line = re.search(r"-\s*Files?:\s*(.+)", text, re.IGNORECASE)
    files = [f.strip() for f in files_line.group(1).split(",") if f.strip()] if files_line else []
    tests = re.findall(r"\btest_\w+", text)
    chunk_size = max(2, math.ceil(len(files) / 3)) if files else 2
    subtasks = []
    for i in range(0, max(len(files), 1), chunk_size):
        chunk_files = files[i : i + chunk_size]
        chunk_tests = tests[i : i + chunk_size] if tests else []
        part = i // chunk_size + 1
        desc = f"{title} (part {part})"
        if chunk_files:
            desc += f" — files: {', '.join(chunk_files)}"
        if chunk_tests:
            desc += f" — tests: {', '.join(chunk_tests)}"
        subtasks.append(desc)
    return subtasks[:3]


def estimate_complexity(task_text: str) -> dict:
    """Estimate task complexity from backlog text. Returns dict with
    score (1-10), should_split, subtasks, reason, file_count."""
    file_count = _count_files(task_text)
    test_count = _count_tests(task_text)
    keyword_count = _count_complex_keywords(task_text)
    score = _compute_score(file_count, test_count, keyword_count)
    should_split = score >= SPLIT_THRESHOLD
    reasons = []
    if file_count >= 5:
        reasons.append(f"{file_count} files (limit 4)")
    if test_count >= 6:
        reasons.append(f"{test_count} acceptance criteria")
    if keyword_count > 0:
        reasons.append(f"{keyword_count} complexity keywords")
    if not reasons:
        reasons.append("within normal bounds")
    subtasks = _generate_subtasks(task_text) if should_split else []
    return {
        "score": score,
        "should_split": should_split,
        "subtasks": subtasks,
        "reason": "; ".join(reasons),
        "file_count": file_count,
    }
