# Skill: Git

## COMMIT TO THE PROJECT REPO
Work happens in the project's own repo. Read its root path, default branch, and any
commit rules from PROJECT.md — never hardcode or assume them.
```bash
git -C "$PROJECT" add <changed paths>
git -C "$PROJECT" commit -m "agent: <what> — <why>"
git -C "$PROJECT" push origin <default-branch>
```
- `$PROJECT` = the project root from PROJECT.md; `<default-branch>` = the branch PROJECT.md specifies.
- The engine's `.autoagent/` symlink is gitignored inside the project — NEVER `git add .autoagent/` (or `autoagent/`) from the project root.

## DECISION RULE
Before every commit ask:
- Did I change project source/tests/assets? → commit to the project repo with the `agent:` prefix.
- Stage only the paths you intended (`git add <paths>`), never `git add .` blindly.

## COMMIT MESSAGE FORMAT — EXPANDED
The 50-character convention was written for humans; agents read commit messages as cheap, persistent context. Expand beyond a one-line summary so the NEXT session can reconstruct intent without re-reading the diff.

**Required structure** for any non-trivial commit:
```
agent: <what changed> — <why>

<1-2 sentences on the decision: what approach was picked and what was rejected>
<1 sentence on constraints or assumptions baked in>
Tests: <count before → after>, <key test names if distinctive>
```

Example (good):
```
agent: add order-total aggregate endpoint — dashboard summary

Composed the per-line-item totals across an order
(considered recomputing per-group but rejected — duplicates line-item logic).
Assumes order_total = sum across line items, tax applied last.
Tests: 3128 → 3137, incl. mixed-currency aggregation and empty-order 404.
```

Example (bad — forces re-read of diff next session):
```
agent: order total endpoint
```

Why it matters: a future ghost-recovery session reading `git log --oneline -3` to cross-check activity_log can identify the task from the subject line alone; a debugging session can identify WHICH alternatives were rejected without re-running the analysis.

## BEFORE COMMITTING
1. Run tests — they must be green (non-regression gate: count_after ≥ count_before)
2. `git diff --stat` — confirm you changed what you intended
3. Never force push to the default/shared branch
4. Never commit .env files or API keys
5. Never skip hooks (`--no-verify`) unless the user explicitly authorizes it

## COMPOUND STAGE+COMMIT — closes the orphan-adoption race window
When ADOPTING orphan files (ghost recovery, crashed-session pickup), the gap between `git add` and `git commit` is the race window where a sibling session can claim the same orphans. Collapse staging and committing into ONE tool call with `&&`:

```bash
git -C "$PROJECT" add <paths> && git -C "$PROJECT" commit -m "<msg>" && git -C "$PROJECT" push origin main
```

**Why**: Session #395 adopted the same #210 orphans as sibling #397; both staged in the same ~5s window, #397 committed first, #395's commit failed "nothing added" and was a wasted no-op. The orphan-adoption commit-order rule (isolated test → commit → full suite) was followed but the `add`/`commit` split left room for the race. A single compound call eliminates the between-tool-calls gap entirely.

**When to use**: ANY orphan adoption, any ghost recovery, any commit where a sibling session might also be targeting the same files. For solo/claimed work the split form is fine — but the compound form is never wrong.

**Do NOT** compound `git add && git commit` with a pre-commit run of the full pytest suite — that re-opens the window AND burns 5 min of context. Ordering stays: isolated test → compound add+commit+push → full suite.
