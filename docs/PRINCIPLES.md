# Engineering Principles — Verre Noir Group

Opinionated working rules for a 2-person AI-focused dev team. Not a textbook. Use these to make decisions faster and argue less.

---

## Part 1: General Software Engineering

### SOLID

**Single Responsibility Principle**
*A class or module should have one reason to change.*
When a unit does too many things, every change risks breaking unrelated behavior. Keep things focused so you can edit confidently.

**Open/Closed Principle**
*Open for extension, closed for modification.*
You should be able to add behavior without rewriting existing code. If every new feature requires hacking core logic, the design is wrong.

**Liskov Substitution Principle**
*Subtypes must be substitutable for their base types without breaking the program.*
If you override a method and the behavior becomes surprising or restricted, you're violating this. It usually means inheritance was the wrong tool.

**Interface Segregation Principle**
*Don't force callers to depend on methods they don't use.*
Fat interfaces create tight coupling. Slim, focused interfaces let you swap implementations and test in isolation.

**Dependency Inversion Principle**
*Depend on abstractions, not concretions.*
High-level modules shouldn't know about database drivers or HTTP clients. Pass in dependencies; let the caller decide what to inject.

---

### DRY — Don't Repeat Yourself
*Every piece of knowledge should have a single, authoritative representation.*
Duplication isn't just about copy-paste — it's about two places that must change together when a rule changes. Consolidate the rule, not just the syntax.

### KISS — Keep It Simple, Stupid
*The simplest solution that works is the right solution.*
Complexity compounds. Every abstraction you add is a tax on every future developer, including yourself at 2am six months from now.

### YAGNI — You Aren't Gonna Need It
*Don't build things until they're actually needed.*
Speculative features add maintenance weight immediately and get deleted half the time anyway. Build what's required, not what seems smart.

### Separation of Concerns
*Different problems should be solved in different places.*
Mixing HTTP routing with business logic with database access means all three break together. Separate them so they can evolve independently.

### Fail Fast
*Surface errors as early and loudly as possible.*
A system that fails silently corrupts state and creates debugging nightmares. Crash early, with clear messages, before damage spreads.

### Single Source of Truth
*Each piece of data or logic should live in exactly one place.*
If the same value is stored or computed in two places, they will eventually diverge. Pick one canonical location and read from it everywhere.

### Composition over Inheritance
*Favor assembling behavior from small pieces over deep class hierarchies.*
Inheritance bakes in structure that's hard to change. Composition lets you swap parts without touching unrelated code.

### Principle of Least Astonishment
*The system should behave the way its users expect it to.*
If reading a function name and signature doesn't tell you what it does, the name is wrong or the function is doing something surprising. Either is a bug.

### Law of Demeter
*Talk to your immediate collaborators, not to their internals.*
`user.getAddress().getCity().getName()` is a red flag — you're depending on three layers of implementation detail. Ask for what you need, don't reach through the chain.

### Defensive Programming vs. Trust Internal Code
*Validate inputs at system boundaries; trust your own internals.*
External inputs — user data, API responses, file contents — are hostile and must be validated. Internal function calls between code you control don't need paranoid null-checks everywhere. Over-defending internal code hides bugs instead of surfacing them.

### Make It Work → Make It Right → Make It Fast
*In that order. Never skip steps.*
Optimizing code that's wrong wastes time. Cleaning up code that doesn't run is premature. Get it working first, then clean the design, then profile and optimize only if there's evidence of a real bottleneck.

---

## Part 2: AI Agent Design

### Single Responsibility per Agent
*Each agent should do one thing and hand off everything else.*
An agent that routes requests, calls APIs, formats output, and handles errors is impossible to test and impossible to debug. Narrow agents compose cleanly; Swiss Army knife agents fail messily.

### Prompt is Code
*Treat every system prompt like production code: version it, review it, test it.*
A prompt change is a behavior change. Unreviewed prompt edits in production are the equivalent of unreviewed code pushes. They deserve the same discipline.

### Token Budget Discipline
*Every agent run has a budget. Enforce it explicitly and fail before you exhaust it.*
Token overruns don't just cost money — they cause silent truncation, degraded context, and unpredictable behavior. Set hard caps and log usage per step so overruns are visible before they become incidents.

### Deterministic by Default, Stochastic by Choice
*Use temperature=0 unless you have a specific reason to introduce randomness.*
Non-determinism makes agents hard to test and debug. Default to reproducibility; opt into creativity only for tasks where variation is the feature.

### Graceful Degradation — Fallback Chains
*Every agent dependency should have a fallback.*
If the primary model is unavailable or over budget, have a cheaper or free alternative queued up. Silent failure with no fallback turns a rate limit into a production outage.

### Idempotency — Agents That Can Be Safely Retried
*Running an agent twice on the same input should produce the same outcome without side effects.*
Networks fail, timeouts happen, and retries are inevitable. An agent that sends emails, writes records, or calls APIs without idempotency guarantees will cause double-actions in the wild.

### Observability First
*Log every tool call, every model response, every decision branch before you ship.*
Agents are black boxes without structured logs. When something goes wrong in production — and it will — you need a full trace to reconstruct what happened. Add observability before you need it, not after.

### Human-in-the-Loop Escalation Thresholds
*Define explicit conditions under which an agent stops and asks a human.*
Autonomous agents should not make irreversible decisions under uncertainty. Set clear thresholds — confidence scores, cost limits, error rates — that trigger escalation rather than guessing forward.

### Context Window Hygiene
*Be intentional about what enters the context and prune aggressively.*
Bloated context degrades performance, inflates cost, and dilutes the signal the model uses to reason. Only include what's necessary for the current task; summarize or drop historical turns that no longer inform the decision.

### Advisor Pattern
*Use a fast model for execution and a strong model for decisions.*
Running Opus on every turn is expensive and usually overkill. The executor (Sonnet or Haiku) handles mechanical steps; it calls the Advisor (Opus) only at genuine decision points. This gets you near-Opus quality at Sonnet cost on most workloads.

### Hard Loop Caps
*Every agent loop must have a maximum iteration count and a maximum retry count.*
Autonomous loops with no ceiling will run until they hit a resource limit, not until they're done. Set explicit maximums, log when they're hit, and fail loudly — not silently.

### Agent Failure Modes to Avoid

**Kitchen Sink** — When an agent accumulates tools, context, and responsibilities because "it might need them." If an agent has more than ~5 tools, it's doing too much.

**Infinite Exploration** — When an agent loops through research and discovery without ever committing to output. Define done before you start.

**Symptom Suppression** — When an agent catches errors and continues as if nothing happened. Silent exception handling in agent code is catastrophic. Fail loudly or escalate; never swallow errors to appear functional.

---

## Part 3: Team Principles

### Code Is Read 10x More Than It's Written
*Optimize for the reader, not the writer.*
The 20 seconds you save by writing a shorthand costs every future reader (including you) 2 minutes of decoding. Write for reading.

### Naming Is Design
*If you can't name something clearly, you don't understand it yet.*
Bad names are a symptom of unclear thinking, not just a style problem. When naming is hard, stop and clarify what the thing actually is before you name it.

### One PR, One Thing
*A pull request should have a single, describable purpose.*
Mixed-concern PRs are hard to review, hard to revert, and impossible to bisect. If you find yourself writing "and also" in the PR description, split it.

### Tests Are Documentation
*A good test suite tells the story of what the system is supposed to do.*
Tests that are hard to read are a design smell — either the tests or the code under test is too complex. Write tests like examples, not proofs.

### Ship Often, Ship Small
*Small deploys are safer, faster to review, and easier to roll back.*
The bigger the diff, the harder it is to find the bug it introduced. Prefer 10 small deploys to 1 large one. Merge to main frequently.

### Leave It Better Than You Found It (But Don't Over-Scope)
*Fix one nearby problem when you see it. Don't refactor the universe.*
If you're in a file for a bug fix and you spot a clear issue, clean it up. But don't turn a 10-line fix into a 400-line refactor that nobody asked for and everyone has to review.

### Ownership Mentality
*If you shipped it, you verified it.*
"It worked locally" is not verification. Check the build logs, smoke test the deploy, confirm the behavior in the environment it actually runs in. You're not done when you write the code.

### Make It Obvious, Not Clever
*Clever code is a liability. Obvious code is an asset.*
The smartest-looking solution is often the hardest to maintain. If the next person reading your code needs to be impressed rather than informed, rewrite it.

### Review for Intent, Not Just Correctness
*Ask "does this solve the right problem?" before "is the syntax correct?"*
A technically correct implementation of the wrong thing is still wrong. Code review should catch misaligned assumptions, not just missing semicolons.

### Async by Default, Sync When Necessary
*Default to written async communication. Reserve synchronous time for what actually needs it.*
Most decisions can be made in a thread. Defaulting to calls for work that could be a message fragments focus and doesn't scale. Sync when you're blocked, misaligned, or need to move fast together — not as a reflex.
