# 01 — Opportunity Landscape: How Do We Better Prepare an AI?

## Frame

"Preparing an AI" is not a single act. It's the full journey from *cold start* (new session, zero context) through *operating* (in the flow, making edits) to *hand-off* (ending the session, leaving state for the next agent or the human). CoDRAG today is excellent at cold-start orientation via atlas. It's thin everywhere else.

Below is a first-principles inventory of what an AI needs to work well inside a codebase, mapped to where CoDRAG stands today and where the opportunity sits.

## The 12 preparation dimensions

| # | Dimension | Question it answers | CoDRAG today | Opportunity |
|---|---|---|---|---|
| 1 | Orientation | What is this project? | Atlas in CLAUDE.md | — (solid) |
| 2 | Navigation | How do I find things? | `codrag_search` | Improve retrieval quality; current 0-match hits return noise |
| 3 | Impact awareness | What breaks if I change X? | `codrag_impact` | Surface blast radius *proactively* on edit, not on query |
| 4 | Business rationale | Why is the code this way? | Concepts (366 seeds, 0 active) | **Activate seeds; emit into artifacts** |
| 5 | Guardrails | What must I not do? | Antibodies (informational) | **Install as hooks; actually block** |
| 6 | Workflow repertoire | What are the canonical tasks here? | MCP prompts | **Emit as `.claude/commands/`** |
| 7 | Team / in-flight context | What's changing right now? | — | Git+paperclip integration |
| 8 | Role / perspective | What lens am I operating through? | Role projection (internal only) | **Emit as `.claude/agents/*.md`** |
| 9 | Feedback / verification | Did I do it right? | — | PostToolUse hooks, test-map |
| 10 | Memory | What have I learned? | Observations | Compaction + retrieval by context |
| 11 | Runtime awareness | What's running? What ports? | — | Live environment block in atlas |
| 12 | Style | What's idiomatic here? | — | Convention mining from AST+lint |

Dimensions marked **bold** are the highest-leverage: unique to CoDRAG, not covered by competitors, and directly improve agent behavior.

## Deeper analysis by dimension

### Concept activation (dim 4)

We have 366 concept seeds across 10+ categories. Zero are active. A seed becomes an active concept when it has been validated (assertions run, anchors confirmed, audience scoped). Today concepts are hidden behind a tool call (`codrag_concepts`) most agents never make.

**The opportunity:** A concept with an anchor to a specific file is a natural piece of CLAUDE.md-scoped documentation for that file. A concept attached to a hub file belongs in the atlas. A constraint concept *is* an antibody and belongs in a hook. We should be emitting concepts into the artifacts the AI already reads.

**Three concept categories, three emission paths:**
- **Constraint** → antibody → PostToolUse/PreToolUse hook
- **Decision / rationale** → inline comment pointer in CLAUDE.md near the relevant module listing
- **Pattern / convention** → skill reference file (`.claude/skills/codrag/references/patterns.md`)

### Antibodies as hooks (dim 5)

Today antibodies are informational — they surface in `codrag()` ambient context as warnings. That requires the agent to have called `codrag` recently *and* to notice the warning *and* to care.

**The opportunity:** Every antibody with a clear trigger (file pattern + edit type) should be installable as a PreToolUse hook in `.claude/settings.json`. Example: antibody "Pi Agent must not import LLM libraries" → PreToolUse hook on `Edit` to `src/codrag/agents/pi_agent/*.py` that checks the diff for `import openai|anthropic|langchain` and either warns or blocks.

**Three enforcement levels, user-selectable:**
- `advisory` — hook prints warning to stderr, allows action
- `blocking` — hook returns non-zero, requires user override
- `silent` — hook logs to CoDRAG telemetry only (for audit)

Default is `advisory`. Enterprise gets `blocking`. This is also a pricing hook.

### Slash commands (dim 6)

MCP prompts only work where the client surfaces them well. Claude Code surfaces them via `/mcp__codrag__codrag-onboard` — discoverable but verbose. A generated `.claude/commands/codrag-review.md` file appears as `/codrag-review` — native, clean, version-controllable in git.

**The opportunity:** Emit 5–10 slash commands mirroring our MCP prompts plus project-specific ones:
- `/codrag-onboard` — our existing onboard prompt
- `/codrag-review <file>` — impact + concepts + antibodies for a file
- `/codrag-plan <description>` — plan-mode with structural pre-analysis
- `/codrag-health` — audit summary
- `/codrag-concept <topic>` — surface rationale concepts on a topic
- `/pipeline-status` — CoDRAG-specific (would require user opt-in to project-custom commands)

Each command is a markdown file with a templated prompt body. Generation cost: cheap. Discoverability gain: large.

### Role-projected subagents (dim 8)

This is our biggest sleeping asset. `role_projection.py` computes per-role views of the atlas with detail tiers (executive / manager / practitioner). We have role vectors for CEO, UX designer, architect, engineering, design, data engineer, devops, product, writer. None of this reaches the AI.

**The opportunity:** Emit `.claude/agents/<role>.md` files. Each one is a subagent definition: a name, a one-line trigger description, a system prompt, and an embedded role-projected atlas. Claude Code's `Task` tool dispatches to these subagents with fresh context.

Example: `.claude/agents/security-engineer.md` contains:
- System prompt: "You are a security-focused reviewer for this codebase."
- Role atlas: files tagged auth/crypto/session, concepts tagged security, antibodies enforced in security scope.
- Tool permissions: read-only over most of repo, write to `docs/security/*`.
- Gotchas: pulled from security-tagged concepts and past security observations.

**Why this beats generic "security engineer" personas:** The atlas is the real codebase. The concepts are our specific decisions. The antibodies are our specific constraints. The agent doesn't have to imagine — it sees.

### PostToolUse hooks (dim 9)

After an AI edits a file, what happens? In most setups, nothing until the next test run. That's a long feedback loop.

**The opportunity:** Emit a PostToolUse hook that, after an `Edit` or `Write`, runs a tiny CoDRAG command:
- `codrag impact-check <file>` — if blast radius > threshold, print warning
- `codrag antibody-check <file> <diff>` — if any antibody fires on the diff, surface it
- `codrag concept-check <file>` — if the edit touches a concept anchor, remind the AI of the concept

These are 50–200ms operations. Feedback loop shrinks from "test failure in CI" to "warning in next turn."

### Test map (dim 9 + 2)

Every file has a relationship to tests. Sometimes obvious (`foo.py` ↔ `test_foo.py`), sometimes not. Today an AI editing a file doesn't automatically know which tests are most relevant to run.

**The opportunity:** Add test edges to the graph. For each source file, emit (in its atlas card, or queryable via `codrag_tests(<file>)`) the N tests most likely to cover it — by name match, by import chain, by coverage data if available. On edit, the PostToolUse hook suggests the targeted test command.

### Runtime awareness (dim 11)

An AI entering a session doesn't know what's running. Is the daemon up? Which ports? Is there a dev server on 5174? CoDRAG has this information — it's literally our daemon.

**The opportunity:** Inject a small "runtime state" block into CLAUDE.md (or a separate small `.claude/rules/codrag-runtime.md` refreshed on daemon start):
```
CoDRAG daemon: running on :8400 since 14:03
Dashboard: running on :5174
Recent activity: 7 files edited in last 24h (src/codrag/services/pipeline/*)
Last index rebuild: 2 hours ago, 3 files reindexed
```
Zero tool calls, immediate context.

### Style / convention mining (dim 12)

Agents tend to write code that *looks plausible* but doesn't match the codebase. A codebase's conventions are latent in its AST. With tree-sitter already in our pipeline, we can extract:
- "Async functions here always declare explicit return types."
- "Test files use `pytest.fixture` not `unittest.TestCase`."
- "React components in `packages/ui` use `@codrag/ui` primitives, not raw HTML elements."

**The opportunity:** A `codrag_conventions(<path>)` tool that returns the top N observed patterns. Even better — emit the top patterns for hub files into the atlas, so the AI sees them without asking.

### Predictive context (dim 1+3 elevated)

The current model is reactive: the AI asks, CoDRAG answers. A better model is proactive: CoDRAG observes what the AI is doing and prepares what it will likely need next.

**The opportunity:** A session-aware context layer. After the AI edits `src/codrag/services/pipeline/resume.py`, the next MCP response can include:
- related concepts (pipeline_resume, pipeline_sequencing_bug, incremental_state)
- related tests (`tests/test_pipeline_resume.py`)
- downstream files that import this one
- recent observations about this file or module

This is the biggest UX leap — the AI stops having to guess what to ask, because the system is already offering it.

## Cross-cutting themes

### Budget composition

Each artifact has its own budget, but the *total* context an AI sees on cold start is the sum across artifacts. We should track: "on cold start, how many chars does a fresh agent see from CoDRAG-generated content?" and hold a hard ceiling (say, 8 KB). If we exceed it, we split or demote to on-demand.

### Artifact freshness

A generated subagent file has an atlas hash stamped in. When the atlas drifts (new hub file, new import cycle), the subagent file is stale. We need:
- Freshness markers in every generated file.
- A `codrag refresh --agents` command that regenerates stale artifacts.
- A PreToolUse hook (or daemon heartbeat) that warns if an artifact's hash is stale.

### Observation → concept → artifact flywheel

Today observations are isolated notes. They should feed a pipeline:
1. Observation recorded via `codrag_observe`.
2. Repeated pattern detected → observation promoted to concept seed.
3. Concept validated (anchors confirmed, assertions testable) → promoted to active concept.
4. Active concept with constraint type → emitted as antibody + hook.
5. Active concept with rationale type → emitted into skill references.

This is the loop that makes CoDRAG *learn the project over time* rather than just index it.

### Multi-agent coordination

If Claude Code spawns subagents in parallel worktrees, they need a shared brain. CoDRAG's concept graph and observation store *are* that shared brain. We should make writes (observe, concept record) instantly visible to sibling agents, not just to the next session.

## What this unlocks

An AI prepared this way opens a session with:
- The right role lens (from `.claude/agents/<role>.md`).
- Project-specific commands (`/codrag-review`, `/pipeline-status`).
- Guardrails installed as hooks that fire on edit.
- Live runtime state visible without querying.
- Skills with scripted helpers and Gotchas pulled from actual project incidents.
- Predictive next-context pushed based on what they just touched.

That agent is operating in a richly prepared environment. The ones without CoDRAG are operating blind.
