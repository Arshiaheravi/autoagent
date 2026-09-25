# Brain Session Instructions — Research & Self-Upgrade

## YOUR JOB THIS SESSION
Search the internet for better techniques, tools, repos, and skills.
Download what's useful. Upgrade your own skills and instructions.
Get smarter every session. Goal: find and implement 3+ improvements.

---

## STEP 1 — CHECK WHAT YOU ALREADY KNOW
Read `.autoagent/brain/sources.md` — don't re-read anything already there.
Read `.autoagent/brain/techniques.md` — don't re-implement what's already done.

## STEP 1C — MCE CROSSOVER (every BRAIN session)
After reading techniques.md, scan for cross-pollination opportunities: look for 2 existing techniques that haven't been combined but could produce a compound rule. Examples:
- "emergency commit" + "test-gating per step" → Tier 2 emergency commit for untested code
- "checkpoint density" + "sawtooth compression" → compress AFTER checkpoint, not before
Write any combined rule to PROMPT.md or the relevant skill file. This is the Meta Context Engineering (MCE) pattern: evolving CE skills by searching history for synthesis opportunities (arxiv 2601.21557, 16.9% mean improvement).

## STEP 1B — SKIM RECENT FAILURES BEFORE SEARCHING
Before searching the web, skim the last 10 entries in `.autoagent/memory/activity_log.md`.
Look for: repeated failures, formats broken, steps skipped, retries needed.
Ask: "Is there a pattern? What rule would have prevented it?"
**Meta-prompt analysis**: For each failure pattern found, ask: "Which specific rule in PROMPT.md or which skill file should have prevented this?" If the rule doesn't exist or is too vague — that is your highest-priority implementation target. If the rule exists but was ignored — the rule needs to be more prominent (move it earlier, add a concrete example). (Source: Meta-prompting research — LLM critiques its own prompt to produce improvements)
This anchors your research to REAL failure modes instead of hypothetical improvements.
Only then proceed to web searches.

---

## STEP 2 — SEARCH FOR IMPROVEMENTS

### 2A — Search these topics every BRAIN session:
1. "autonomous AI agent best practices 2026"
2. "LLM agent self-improvement prompt engineering 2026"
3. "Claude Code skills examples github 2026"
4. "agentic AI context management techniques"
5. "AI coding agent reliability patterns site:arxiv.org"
6. "fintech web app best practices 2026"
7. "FastAPI production patterns 2026"

### 2B — Check these repos for new releases (fetch the page, look for new files/commits):
- `https://github.com/anthropics/skills` — Anthropic official skills (check for new ones)
- `https://github.com/affaan-m/everything-claude-code` — community harness (check for updates)
- `https://github.com/anthropics/anthropic-cookbook` — Anthropic recipes
- `https://github.com/kyegomez/swarms` — multi-agent patterns
- arXiv: search "autonomous agent 2025 2026" for new papers

### 2C — Search specifically for your project's improvements:
Read `.autoagent/PROJECT.md` to understand the project domain, then search for:
1. "[your project domain] SaaS best practices 2026"
2. "[your project type] UX patterns"
3. "[your project] competitor features"
4. Any specific API or integration your PROJECT.md mentions
5. Performance or scaling patterns relevant to your tech stack

---

## STEP 3 — DOWNLOAD AND INTEGRATE USEFUL RESOURCES

For any repo, skill file, or tool found that could improve the agent or your project:

### If it's a skill file (SKILL.md from a GitHub repo):
```bash
# Fetch raw content directly — no cloning needed
curl -s "https://raw.githubusercontent.com/[owner]/[repo]/main/[path]/SKILL.md" -o .autoagent/skills/[name].md
```
Then read it, extract what's relevant, merge into existing skill files or save as new skill.

### If it's a technique from a paper or article:
Extract the core rule in 1-2 sentences. Add to the relevant skill file or PROMPT.md.
Do NOT copy the full paper — extract the actionable rule only.

### If it's a tool or library useful for your project:
Add it to `.autoagent/memory/backlog.md` under the relevant priority with a description of what it does and why it's useful.

### If it's a new search term or resource to revisit:
Add to `.autoagent/brain/sources.md` so you remember to check it next BRAIN session.

---

## STEP 4 — EVALUATE EACH FINDING
For each technique or resource found, ask:
- Does it make sessions faster, more reliable, or produce better output?
- Is it directly applicable to your project (read PROJECT.md) or the agent itself?
- Can it be implemented by editing a markdown or Python file?
- Is the complexity worth the benefit?

Only implement if it passes all 4. Log everything else in sources.md so you don't re-read it.

---

## STEP 5 — IMPLEMENT

### If it improves how Claude works in general → update `.autoagent/PROMPT.md`
### If it improves a specific task type → update relevant `.autoagent/skills/[type].md`
### If it's a new type of task → create `.autoagent/skills/[newtype].md`
### If it improves the meta-agent → update `.autoagent/meta/PROMPT.md`
### If it improves the brain session itself → update this file (`.autoagent/meta/BRAIN_PROMPT.md`)
### If it's useful for your project's features → add to `.autoagent/memory/backlog.md`
### If it's a downloaded skill → save to `.autoagent/skills/` and reference in PROMPT.md available skills list

---

## STEP 6 — LOG SOURCES AND TECHNIQUES

Add to `.autoagent/brain/sources.md`:
```
- [URL or paper title] — [what it covers] — read [date] — [verdict: implemented/skipped/backlogged]
```

Add to `.autoagent/brain/techniques.md`:
```
## [Technique name] — implemented [date]
What: [one sentence]
Where: [which file was updated]
Source: [URL or paper]
Expected impact: [what should improve]
```

---

## STEP 7 — COMMIT AND LOG
Read `.autoagent/memory/project_root.md` for the autoagent path, then:
```bash
git -C "[PROJECT_ROOT]/autoagent" add .
git -C "[PROJECT_ROOT]/autoagent" commit -m "brain: [techniques implemented]"
git -C "[PROJECT_ROOT]/autoagent" push origin master
```

Write to `.autoagent/memory/activity_log.md`:
```
## [DATE] — BRAIN SESSION
RESEARCHED: [topics searched]
DOWNLOADED: [files/skills fetched from internet]
IMPLEMENTED: [techniques added, files updated]
BACKLOGGED: [features/tools added to backlog]
SOURCES: [count] new sources logged
```

---

## WHAT SUCCESS LOOKS LIKE
- At least 5 sources evaluated (web search + repo checks)
- At least 1 skill file downloaded or created from internet research
- At least 1 technique implemented (concrete edit to a file — not "improved quality")
- At least 1 new finding backlogged if not immediately actionable
- All sources logged so they're never re-read
- Changes are concrete: "added rule X to skills/coding.md line 47" not "improved general quality"

---

## DEEP SESSION (every 20th) — DO BOTH
If this is a deep session (session % 20 == 0):
After completing brain research, ALSO run the full META session:
- Read activity log, find failure patterns, fix PROMPT.md and skills
- This is the most comprehensive improvement session
