# Agent Collaboration Infrastructure — Concept Overview

> For Paperclip users and agent operators

---

## What is this?

When you run multiple AI agents on a codebase — a researcher investigating tech debt, a custodian cleaning up dead code, a reviewer checking PRs — they work in isolation. Each agent queries the codebase, does its job, and produces output. None of them know what the others are doing.

This creates real problems:

- Your researcher spends time investigating a file that your custodian is about to delete
- Your custodian marks a file as dead code that your researcher just identified as an important pattern
- Two agents push overlapping findings to Paperclip, and you can't tell which agent found what
- An agent starts a task without knowing that the codebase structure changed since its last session

**Agent Collaboration Infrastructure** is a set of capabilities that let your agents *see each other's work* and *avoid stepping on each other* — without requiring a central orchestrator to manage every interaction.

---

## How it works

CoDRAG already sits at the center of your agents' data flow. Every agent calls CoDRAG for code search, impact analysis, and structural context. We're extending CoDRAG to also serve as the **shared awareness layer** between agents.

### Three capabilities, in plain terms

### 1. Agent Memory

Each agent gets its own memory space. When a researcher starts a new session, it can see what it found last time — without re-searching everything.

**Before:**
```
Agent starts → calls codrag_search → calls codrag_observe(get) → 
re-discovers what it already knew → starts actual work
```

**After:**
```
Agent starts → @codrag://memory/researcher already in context → 
knows prior findings → starts actual work immediately
```

Agents can also browse *each other's* memory. Your dispatcher agent can see what the researcher found, what the custodian flagged, and what the watchdog detected — all in one place.

### 2. Structural Change Detection

Git tells you what *files* changed. CoDRAG tells you what *structurally* shifted — new hub files that many other files depend on, resolved dependency cycles, modules that split or merged.

When your agent starts a task, it can check: "Has the codebase architecture changed since my last session?" If a critical hub file emerged or a dependency cycle was introduced, the agent knows before it starts working.

This is especially valuable for long-running agent teams. A weekly researcher session needs to know that the module it investigated last week was split into two modules this week.

### 3. Conflict Detection

When two agents disagree about the same file — one says "important pattern, consolidate" and the other says "dead code, delete" — CoDRAG catches it before either recommendation reaches Paperclip.

Conflicts surface as a clear report:

```
CONFLICT on src/auth/legacy.py:
  Researcher: "Important JWT refresh pattern — consolidate into shared validator"
  Custodian:  "No imports found — safe to delete"
  Status:     Deferred for human review
```

You decide how to resolve it. The key is that you *see* the disagreement instead of two agents silently pushing contradictory recommendations.

---

## What your agents get

### MCP Resources (browsable via `@` mention)

These are data your agents can pull into their context on demand:

| Resource | What it provides |
|---|---|
| `@codrag://memory/{role}` | An agent's own prior observations and findings |
| `@codrag://agents/{role}/findings` | Another agent's recent work (cross-agent visibility) |
| `@codrag://activity` | Timeline of all agent actions across your team |
| `@codrag://delta` | What changed structurally since a given date |
| `@codrag://conflicts` | Active disagreements between agents |
| `@codrag://consensus` | Findings that multiple agents independently flagged (high-confidence signals) |

### MCP Prompts (structured workflows via `/` command)

| Prompt | What it does |
|---|---|
| `/codrag-handoff` | When one agent finishes and another picks up — packages context transfer with the right structural data |
| `/codrag-scope` | Shows an agent what modules it owns, what changed in its scope, and what findings are open in its domain |
| `/codrag-triage` | Clusters findings by root cause and suggests which agent role should handle each cluster |
| `/codrag-attest` | Checks whether an agent has the capability to handle a specific task before it accepts the assignment |

### Enhanced Observations

Every observation now carries attribution:

```json
{
  "content": "JWT refresh logic duplicates session validation in 3 files",
  "created_by": "researcher",
  "category": "pattern",
  "file_path": "src/auth/refresh.py",
  "visibility": "shared"
}
```

You can see which agent found what, filter by agent, and trace findings back to their source.

---

## How this fits with Paperclip

CoDRAG doesn't replace Paperclip's orchestration. Paperclip decides *who* works on what and *when*. CoDRAG provides the intelligence that makes those decisions better.

```
                Paperclip (orchestration)
                ┌─────────────────────┐
                │ Assigns tasks       │
                │ Tracks progress     │
                │ Manages agents      │
                └────────┬────────────┘
                         │
                         │ "What should this agent know?"
                         │ "Are any agents conflicting?"
                         │ "What changed since last run?"
                         │
                ┌────────▼────────────┐
                │ CoDRAG (intelligence)│
                │ Agent memory        │
                │ Structural delta    │
                │ Conflict detection  │
                │ Consensus scoring   │
                │ Capability check    │
                └─────────────────────┘
```

**Concrete integration points:**

1. **Task assignment** — Before assigning a task, Paperclip can check `codrag-attest` to see if the agent can handle it. CoDRAG responds with scope size, dependency depth, and a recommended agent class (lightweight/standard/heavyweight).

2. **Agent startup** — When a Paperclip agent starts a session, its system prompt can include `@codrag://memory/{role}` so it has its prior work context immediately.

3. **Handoff** — When Agent A finishes and Agent B picks up, the `codrag-handoff` prompt packages what A found, what B should focus on, and the structural context for the relevant code area.

4. **Conflict resolution** — Paperclip can poll `@codrag://conflicts` to surface disagreements to the human operator, or build automation rules (e.g., "on conflict between researcher and custodian, always defer to researcher for actively-imported files").

5. **Consensus prioritization** — When multiple agents independently flag the same area, CoDRAG assigns a consensus score. Paperclip can use this to prioritize which issues get worked on first — high-consensus findings are more likely to be real problems.

---

## What makes this different

Most multi-agent coordination tools focus on **message passing** — Agent A sends a message to Agent B, who responds. This requires agents to know about each other and creates tight coupling.

CoDRAG's approach is **observation-mediated** — agents don't talk to each other directly. They leave traces of their work in a shared knowledge layer. Other agents (and humans) can browse those traces. Coordination emerges from shared awareness rather than explicit messaging.

This is more resilient (agents don't need to be online simultaneously), more transparent (all traces are inspectable), and works across any MCP client (Claude Code, Cursor, Windsurf, Gemini, or Paperclip-managed agents).

The other unique element is the **codebase graph as coordination medium**. CoDRAG knows the structural relationships between files — which files are hubs, which modules depend on each other, where cycles exist. When agents coordinate through CoDRAG, they coordinate through *structural understanding*, not just file paths. This means conflict detection catches semantic conflicts ("these two agents are working on structurally connected code") not just name collisions.

---

## Getting started

If you're already using the CoDRAG Paperclip plugin (`@codrag/paperclip-plugin`), collaboration infrastructure is available through the same MCP connection your agents already use.

1. **Agent attribution** — Pass `created_by: "your-agent-role"` when calling `codrag_observe`. Your agent's observations become browsable via `@codrag://memory/{role}`.

2. **Cross-agent awareness** — Have agents include `@codrag://activity` in their startup context to see what other agents have done recently.

3. **Conflict alerts** — Monitor `@codrag://conflicts` in your Paperclip dashboard or have agents check before pushing findings.

4. **Structural delta** — Have long-running agents check `@codrag://delta` at session start to understand what changed since their last run.

No orchestration changes required. Your existing agent workflows continue to work — these are additive capabilities that make them smarter.
