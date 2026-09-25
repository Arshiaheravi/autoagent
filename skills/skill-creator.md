# Skill: Skill Creator (Meta-Skill)

**When to use**: When you discover a reusable pattern during a task that doesn't have a skill file yet.
Create a new skill so future sessions don't re-derive the same knowledge.

## When to create a new skill

- You spent >15 min figuring out a library or tool pattern
- You hit a non-obvious gotcha that would slow down future sessions
- A task type recurs in the backlog but no skill file covers it
- You find a better approach than what's in an existing skill

## Skill file structure

```markdown
# Skill: [Name]

**When to use**: [1-2 sentence trigger description — be specific about what task types warrant this skill]

## [Main section — key workflow/commands/patterns]

[Code examples, commands, rules]

## [Second section if needed]

[...]

## Project usage
[How this applies to the CURRENT project — read PROJECT.md, never a past project]
```

## Quality checklist before saving

- [ ] "When to use" is specific enough that the agent can decide YES/NO without reading the whole file
- [ ] Contains at least one working code example or command
- [ ] Includes at least one "CRITICAL" or "NEVER" rule (the non-obvious gotcha)
- [ ] Under 100 lines — if longer, split into sections or trim examples
- [ ] Has a "Project usage" section grounding it in the current project (from PROJECT.md)

## After creating

1. Save to `autoagent/skills/[name].md`
2. Add a row to `autoagent/skills/INDEX.md` with the task type and when to use it
3. Commit both files: `git -C autoagent add skills/ && git -C autoagent commit -m "meta: add [name] skill"`
