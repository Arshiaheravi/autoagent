# Memory Directory

This directory contains **project-specific runtime memory** for the agent.

These files are **gitignored** — they belong to your project instance, not the reusable autoagent framework.

---

## Files in this directory

| File | Purpose |
|------|---------|
| `backlog.md` | Open tasks ordered by priority. Agent picks from here each session. |
| `current_task.md` | The task currently in progress. Agent writes steps here before coding. |
| `done.md` | Completed tasks log. One line per task. |
| `activity_log.md` | Session-by-session activity log. DONE / IMPACT / FILES per session. |
| `knowledge.md` | Rules learned from experience. Agent appends after each session. |
| `north_star.md` | Copy of project north star metrics for quick reference. |
| `project_root.md` | Absolute path to the project root on this machine. |

---

## Getting started

When you first clone autoagent for a new project:

1. Copy `../NORTH_STAR.example.md` → `../NORTH_STAR.md` and fill it in
2. Copy `../PROJECT.example.md` → `../PROJECT.md` and fill it in
3. Copy `../config.example.json` → `../config.json` and fill in your tokens
4. Create `backlog.md` with your first tasks
5. Create `current_task.md` with content: `# No current task`
6. Create `activity_log.md`, `done.md`, `knowledge.md` as empty files

The agent populates everything else automatically.
