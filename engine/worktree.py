#!/usr/bin/env python3
"""Git worktree isolation — each agent gets its own working copy.

Enables true parallelism: multiple agents work simultaneously without
file conflicts or git merge issues. Each worktree is a lightweight
checkout on its own branch.

Lifecycle:
  1. create_worktree(ctx, agent, session) → WorktreeSession
  2. Agent runs Claude CLI inside worktree_dir
  3. merge_worktree(ws) → merges changes back to main branch
  4. cleanup_worktree(ws) → removes worktree directory

Based on learn-claude-code s12 (worktree task isolation pattern).
"""
import logging
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

WORKTREE_BASE = ".autoagent/worktrees"


@dataclass
class WorktreeSession:
    """Represents an isolated agent worktree."""
    agent_name: str
    session_num: int
    branch_name: str
    worktree_dir: Path
    base_branch: str
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    merged: bool = False


def _git_output(project_root: Path, args: list[str], timeout: int = 10) -> tuple[int, str, str]:
    result = subprocess.run(
        args,
        cwd=str(project_root),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result.returncode, result.stdout, result.stderr


def create_worktree(project_root: Path, agent_name: str,
                    session_num: int) -> Optional[WorktreeSession]:
    """Create an isolated git worktree for an agent session.

    Creates a new branch `agent/<agent_name>/s<session_num>` and checks
    it out in a separate directory. The agent can commit freely without
    affecting the main branch.

    Returns WorktreeSession on success, None on failure.
    """
    # Determine base branch
    try:
        base = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(project_root), capture_output=True, text=True, timeout=10
        )
        base_branch = base.stdout.strip() or "main"
    except Exception:
        base_branch = "main"

    # Sanitize agent name to prevent path traversal
    import re as _re
    if not _re.match(r'^[a-zA-Z0-9_-]+$', agent_name):
        logger.error("Invalid agent name rejected: %s", agent_name)
        return None

    branch_name = f"agent/{agent_name}/s{session_num}"
    worktree_dir = project_root / WORKTREE_BASE / f"{agent_name}-s{session_num}"

    # Refuse to overwrite an existing worktree path or branch. They may hold
    # unmerged agent work from a prior session.
    if worktree_dir.exists():
        logger.error("Worktree path already exists, refusing to overwrite: %s", worktree_dir)
        return None
    try:
        branch_exists = subprocess.run(
            ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch_name}"],
            cwd=str(project_root), capture_output=True, timeout=10
        )
        if branch_exists.returncode == 0:
            logger.error("Branch already exists, refusing to delete: %s", branch_name)
            return None
    except Exception as e:
        logger.error("Branch existence check failed: %s", e)
        return None

    # Create the worktree with a new branch
    try:
        result = subprocess.run(
            ["git", "worktree", "add", "-b", branch_name, str(worktree_dir), base_branch],
            cwd=str(project_root), capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            logger.error("Failed to create worktree: %s", result.stderr)
            return None
    except Exception as e:
        logger.error("Worktree creation error: %s", e)
        return None

    # Copy .autoagent config into worktree (symlink would cause issues)
    autoagent_src = project_root / ".autoagent"
    autoagent_dst = worktree_dir / ".autoagent"
    if autoagent_src.exists() and not autoagent_dst.exists():
        try:
            # Symlink the entire .autoagent dir — agents read from it, write to memory/
            autoagent_dst.symlink_to(autoagent_src)
        except Exception:
            # Fallback: copy critical files only
            autoagent_dst.mkdir(parents=True, exist_ok=True)
            for f in ["PROMPT.md", "PROJECT.md", "NORTH_STAR.md"]:
                src = autoagent_src / f
                if src.exists():
                    shutil.copy2(str(src), str(autoagent_dst / f))
            # Copy memory dir
            mem_src = autoagent_src / "memory"
            mem_dst = autoagent_dst / "memory"
            if mem_src.exists():
                shutil.copytree(str(mem_src), str(mem_dst), dirs_exist_ok=True)

    ws = WorktreeSession(
        agent_name=agent_name,
        session_num=session_num,
        branch_name=branch_name,
        worktree_dir=worktree_dir,
        base_branch=base_branch,
    )
    logger.info("Created worktree for %s at %s (branch: %s)",
                agent_name, worktree_dir, branch_name)
    return ws


def has_changes(ws: WorktreeSession) -> bool:
    """Check if the worktree has uncommitted or unpushed changes."""
    try:
        # Check for uncommitted changes
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(ws.worktree_dir), capture_output=True, text=True, timeout=10
        )
        if status.stdout.strip():
            return True

        # Check for commits ahead of base
        log = subprocess.run(
            ["git", "log", f"{ws.base_branch}..HEAD", "--oneline"],
            cwd=str(ws.worktree_dir), capture_output=True, text=True, timeout=10
        )
        return bool(log.stdout.strip())
    except Exception:
        return False


def merge_worktree(ws: WorktreeSession, project_root: Path) -> bool:
    """Merge the agent's worktree branch back into the base branch.

    Uses --no-ff to preserve the agent branch history in the merge commit.
    Returns True on success, False if merge fails (conflict).
    """
    if not has_changes(ws):
        logger.info("Worktree %s has no changes, skipping merge.", ws.agent_name)
        ws.merged = True
        return True

    try:
        branch_code, branch, _ = _git_output(
            project_root, ["git", "rev-parse", "--abbrev-ref", "HEAD"]
        )
        if branch_code != 0 or branch.strip() != ws.base_branch:
            logger.error("Refusing merge: current branch is %s, expected %s",
                         branch.strip() or "(unknown)", ws.base_branch)
            return False

        status_code, status, _ = _git_output(project_root, ["git", "status", "--porcelain"])
        if status_code != 0 or status.strip():
            logger.error("Refusing merge into dirty project root: %s", project_root)
            return False

        wt_status_code, wt_status, _ = _git_output(ws.worktree_dir, ["git", "status", "--porcelain"])
        if wt_status_code != 0 or wt_status.strip():
            logger.error("Refusing merge: worktree has uncommitted changes at %s", ws.worktree_dir)
            return False

        # Merge agent branch into base branch
        result = subprocess.run(
            ["git", "merge", ws.branch_name, "--no-ff",
             "-m", f"agent: merge {ws.agent_name} session #{ws.session_num}"],
            cwd=str(project_root), capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            logger.error("Merge failed for %s: %s", ws.branch_name, result.stderr)
            # Abort the failed merge
            subprocess.run(
                ["git", "merge", "--abort"],
                cwd=str(project_root), capture_output=True, timeout=10
            )
            return False

        ws.merged = True
        logger.info("Merged %s into %s", ws.branch_name, ws.base_branch)
        return True
    except Exception as e:
        logger.error("Merge error: %s", e)
        return False


def cleanup_worktree(ws: WorktreeSession, project_root: Path,
                     delete_branch: bool = True):
    """Remove the worktree directory and optionally delete the branch."""
    if not ws.merged and has_changes(ws):
        logger.warning(
            "Preserving unmerged worktree with changes: %s (branch: %s)",
            ws.worktree_dir, ws.branch_name,
        )
        return

    try:
        subprocess.run(
            ["git", "worktree", "remove", str(ws.worktree_dir), "--force"],
            cwd=str(project_root), capture_output=True, timeout=15
        )
    except Exception:
        shutil.rmtree(ws.worktree_dir, ignore_errors=True)

    if delete_branch and ws.merged:
        try:
            subprocess.run(
                ["git", "branch", "-d", ws.branch_name],
                cwd=str(project_root), capture_output=True, timeout=10
            )
        except Exception:
            pass

    # Prune stale worktree references
    try:
        subprocess.run(
            ["git", "worktree", "prune"],
            cwd=str(project_root), capture_output=True, timeout=10
        )
    except Exception:
        pass

    logger.info("Cleaned up worktree for %s", ws.agent_name)


def list_active_worktrees(project_root: Path) -> list[dict]:
    """List all active agent worktrees."""
    try:
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            cwd=str(project_root), capture_output=True, text=True, timeout=10
        )
        worktrees = []
        current = {}
        for line in result.stdout.splitlines():
            if line.startswith("worktree "):
                if current and "agent/" in current.get("branch", ""):
                    worktrees.append(current)
                current = {"path": line.split(" ", 1)[1]}
            elif line.startswith("branch "):
                current["branch"] = line.split(" ", 1)[1]
            elif line == "":
                if current and "agent/" in current.get("branch", ""):
                    worktrees.append(current)
                current = {}
        if current and "agent/" in current.get("branch", ""):
            worktrees.append(current)
        return worktrees
    except Exception:
        return []
