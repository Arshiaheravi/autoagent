"""Code churn tracker — per-file modification frequency from git history.

Pure function: project_root → dict with file churn scores.
High-churn files are unstable and may need attention.
"""

import subprocess
from collections import Counter
from pathlib import Path


def compute_churn_score(project_root: Path, last_n_commits: int = 20) -> dict:
    """Count per-file modifications in last N commits.

    Returns {"files": [{"path": str, "modifications": int}, ...]}
    sorted by modifications descending.
    """
    project_root = Path(project_root)

    if last_n_commits <= 0:
        return {"files": []}

    try:
        result = subprocess.run(
            ["git", "-C", str(project_root), "log",
             f"-{last_n_commits}", "--pretty=format:", "--name-only"],
            capture_output=True, text=True, timeout=10,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return {"files": []}

    if result.returncode != 0 or not result.stdout.strip():
        return {"files": []}

    counts = Counter()
    for line in result.stdout.splitlines():
        line = line.strip()
        if line:
            counts[line] += 1

    files = [{"path": path, "modifications": count}
             for path, count in counts.most_common()]

    return {"files": files}
