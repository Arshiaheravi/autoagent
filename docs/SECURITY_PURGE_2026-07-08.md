# Security: purge leaked credentials from git history

**Status:** PREPARED — awaiting operator (Seb) action. Claude cannot rotate your
credentials or force-push history; this is a runbook you run yourself.

**Severity:** a live GitHub PAT and a live Telegram bot token were committed in
plaintext and still exist in git **history** (the working tree is already
redacted, HEAD is clean). Anyone with repo access — or anyone who ever cloned —
can recover them until history is rewritten AND the tokens are rotated.

---

## 1. What leaked, and where

Two real secrets, threaded through history across **5 file paths** (not one):

| Secret | Pattern | First introduced | Historical file paths |
|---|---|---|---|
| GitHub PAT | `ghp_` + 36 chars | `eed520d` ("add project git token") | `config.json`, `launcher.py`, `docs/AUDIT_2026-04-16.md` |
| Telegram bot token | `NNNNNNNN:` + 35 chars | `55bc7d0` ("Telegram communication") | `config.json`, `engine/comms.py`, `engine/director.py`, `docs/AUDIT_2026-04-16.md` |

- HEAD is clean — all five files now use env vars; `config.json` is gitignored
  (since `cb0b98a`). The exposure is **history only**.
- Because the secrets live in real source files (not just the audit doc), a
  path-delete (BFG `--delete-files`) is WRONG — it would nuke `comms.py` /
  `director.py` / `launcher.py`. The fix rewrites the token **values** in place
  across all 648 commits, leaving the files intact.

---

## 2. Do this in order

### Step 0 — ROTATE FIRST (most important, do before anything else)

History rewriting is slow and coordinated; rotation is instant and kills the
secrets no matter who already has them. **Rotate before you purge.**

- **GitHub PAT** — https://github.com/settings/tokens → revoke the leaked token
  → generate a replacement → update wherever it's used (`config.json` locally,
  any LaunchAgent/cron env, CI secrets).
- **Telegram bot token** — message **@BotFather** → `/revoke` → `/token` for a
  fresh one → update `engine/comms.py` / `engine/director.py` env (`.env` /
  plist). The old token stops working the instant BotFather reissues.

Once rotated, the historical copies are dead weight — but still purge them
(Step 2) so a scanner doesn't flag the repo and so you're not relying on
"rotated" as the only defense.

### Step 1 — back up the repo

```
git clone --mirror git@github.com:Arshiaheravi/autoagent.git ~/autoagent-backup-$(date +%Y%m%d).git
```

Keep this until you've confirmed the purge succeeded and everyone re-cloned.

### Step 2 — rewrite history (git-filter-repo, already installed)

The replacement rules use **regex** so you never paste the raw tokens anywhere.
The rules file is prepared at
`scratchpad/replace-rules.txt` (content shown below — recreate it if the
scratchpad is gone):

```
regex:ghp_[A-Za-z0-9]{36,}==>***REMOVED-GITHUB-PAT***
regex:github_pat_[A-Za-z0-9_]{20,}==>***REMOVED-GITHUB-PAT***
regex:[0-9]{8,}:[A-Za-z0-9_\-]{30,}==>***REMOVED-TELEGRAM-TOKEN***
```

Run against a fresh mirror (filter-repo prefers a clean clone):

```
git clone --mirror git@github.com:Arshiaheravi/autoagent.git ~/autoagent-purge.git
cd ~/autoagent-purge.git
git filter-repo --replace-text /path/to/replace-rules.txt --force
```

> The `ghp_` regex requires 36+ real chars, so it will NOT touch the short
> literal `ghp_` used as a detection *pattern* in `scripts/check_secrets.sh`,
> `skills/security.md`, `config.example.json`, or `templates/meta/AUDIT_PROMPT.md`
> — those stay intact. Only real full-length tokens are replaced.

### Step 3 — force-push the rewritten history (DESTRUCTIVE)

```
git remote add origin git@github.com:Arshiaheravi/autoagent.git
git push --force --mirror origin
```

`--mirror` force-updates **all** branches and tags. This rewrites shared
history — coordinate with Arshia first (Step 4).

### Step 4 — everyone re-clones

Every existing clone still contains the tokens and, if pushed, would
**reintroduce them**. After the force-push:

- Tell Arshia (repo owner `Arshiaheravi`) to delete their local clone and
  re-clone fresh. Same for any CI runner or server that has a working copy.
- Delete your own working clone at `~/Documents/autoagent` and re-clone, OR
  hard-reset it to the rewritten remote.

### Step 5 — verify + re-arm the hook

```
# From a FRESH clone:
git log --all -S 'ghp_' -G 'ghp_[A-Za-z0-9]{36}'      # expect: no real-token commits
scripts/install_hooks.sh                                # re-arm pre-commit (fresh clones have no hooks)
```

The pre-commit secret-scan hook (`scripts/check_secrets.sh`) already blocks
GitHub PATs, fine-grained PATs, Anthropic keys, OpenAI keys, AWS keys, Telegram
tokens, and private-key blocks on staged diffs. It is installed in the current
clone; a fresh clone needs `install_hooks.sh` to re-link it. **Never bypass it
with `--no-verify`.**

---

## 3. What Claude already did / could not do

- **Did:** pinned the exact commits + 5 file paths carrying each token,
  confirmed HEAD is clean, confirmed `git-filter-repo` is installed and the
  pre-commit hook covers every relevant pattern, and wrote this runbook + the
  regex rules file (no token values recorded anywhere).
- **Could not:** rotate your credentials or force-push rewritten history — both
  require your accounts and are destructive/irreversible. Those are Steps 0 and
  3 above, yours to run.
