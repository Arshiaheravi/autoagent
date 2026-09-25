"""Session diff summarizer — structured extraction of what changed.

Pure function: project_root → str summary.  No LLM needed.
"""

import subprocess
from pathlib import Path


def summarize_session_diff(project_root: Path, last_n: int = 1) -> str:
    """Summarize the last N commits: files changed + commit messages.

    Returns a human-readable one-liner per commit, or 'No changes' if
    last_n is 0 or there are no commits to show.
    """
    project_root = Path(project_root)

    if last_n <= 0:
        return "No changes detected (clean state)."

    # Get last N commit messages + stats
    try:
        log_result = subprocess.run(
            ["git", "-C", str(project_root), "log",
             f"-{last_n}", "--pretty=format:%h %s", "--stat", "--stat-width=60"],
            capture_output=True, text=True, timeout=10,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return "No changes detected (git unavailable)."

    output = log_result.stdout.strip()
    if not output:
        return "No changes detected (clean state)."

    # Parse into structured lines: "hash message | file1, file2, ..."
    lines = []
    current_hash_msg = None
    current_files = []

    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        # Stat summary line like "1 file changed, 2 insertions(+)"
        if "file changed" in line or "files changed" in line:
            continue
        # File stat line like "app.py | 1 +"
        if "|" in line and not line.startswith("|"):
            fname = line.split("|")[0].strip()
            if fname:
                current_files.append(fname)
        else:
            # New commit header — flush previous
            if current_hash_msg is not None:
                files_str = ", ".join(current_files) if current_files else "no files"
                lines.append(f"{current_hash_msg} | {files_str}")
            current_hash_msg = line
            current_files = []

    # Flush last commit
    if current_hash_msg is not None:
        files_str = ", ".join(current_files) if current_files else "no files"
        lines.append(f"{current_hash_msg} | {files_str}")

    return "\n".join(lines) if lines else "No changes detected (clean state)."
