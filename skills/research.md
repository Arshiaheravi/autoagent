# Skill: Research

## ORDER OF OPERATIONS — ALWAYS IN THIS ORDER
1. Check `autoagent/memory/knowledge.md` — answer may already be there
2. Check `autoagent/brain/sources.md` — avoid re-reading what was already read
3. Read relevant source files in the codebase
4. ONLY search the web if steps 1-3 didn't answer the question

## WHEN SEARCHING THE WEB
- Be specific: "FastAPI dependency injection pattern" not "how to use FastAPI"
- Prefer: official docs, GitHub source code, arXiv papers
- Cap reading time: if a page doesn't answer in first 3000 chars, move on
- Save findings to `autoagent/memory/knowledge.md` before finishing

## SAVING RESEARCH FINDINGS
Add to `autoagent/memory/knowledge.md`:
```
## [Topic] — [Date]
- Key finding 1
- Key finding 2
- Source: [URL or paper name]
```

Add to `autoagent/brain/sources.md` so it's never re-read:
```
- [URL] — [what it covers] — read [date]
```

## RESEARCH SESSION END
Always end with at least 3 concrete findings saved to knowledge.md.
An empty knowledge.md after a research session = session failed.
