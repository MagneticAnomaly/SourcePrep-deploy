# Agent Collaboration Infrastructure — Concept Overview

> For Paperclip users and agent operators | Updated 2026-04-06

---

## What is this?

When you run multiple AI agents on a codebase — a researcher investigating tech debt, a custodian cleaning up dead code, a reviewer checking PRs — they work in isolation. Each agent queries the codebase, does its job, and produces output. None of them know what the others are doing.

This creates real problems:

- Your researcher spends time investigating a file that your custodian is about to delete
- Your custodian marks a file as dead code that your researcher just identified as an important pattern
- Two agents push overlapping findings to Paperclip, and you can't tell which agent found what
- An agent starts a task without knowing that the codebase structure changed since its last session

**Agent Collaboration Infrastructure** is a set of capabilities that let your agents *see each other's work* and *avoid stepping on each other* — without requiring a central orchestrator to manage every interaction.

**Built for Paperclip first.** Prep provides structural intelligence that enriches Paperclip's existing coordination — it doesn't build a parallel PM system. Activity tracking, task routing, and conflict resolution live in Paperclip. Prep pushes signals that only the code graph can provide.

---

## How it works

Prep already sits at the center of your agents' data flow. Every agent calls Prep for code search, impact analysis, and structural context. We're extending Prep to also serve as the **shared awareness layer** between agents.

### Three capabilities, in plain terms

### 1. Agent Memory

Each agent gets its own memory space. When a researcher starts a new session, it can see what it found last time — without re-searching everything.

**Before:**
```
Agent starts → calls prep_search → calls prep_observe(get) → 
re-discovers what it already knew → starts actual work
```

**After:**
```
Agent starts → @prep://memory/researcher already in context → 
knows prior findings → starts actual work immediately
```

Agents can also browse *each other's* memory. Your dispatcher agent can see what the researcher found, what the custodian flagged, and what the watchdog detected — all in one place.

### 2. Structural Change Detection

Git tells you what *files* changed. Prep tells you what *structurally* shifted — new hub files that many other files depend on, modules that split or merged, dependency rankings that shifted.

When your agent starts a task, it can check: "Has the codebase architecture changed since my last session?" If a critical hub file emerged or a module restructured, the agent knows before it starts working.

This is especially valuable for long-running agent teams. A weekly researcher session needs to know that the module it investigated last week was split into two modules this week.

### 3. Conflict Detection → Paperclip Issues

When two agents disagree about the same file — one says "important pattern, consolidate" and the other says "dead code, delete" — Prep catches it and pushes it to Paperclip as an issue:

```
Prep Conflict: src/auth/legacy.py — researcher vs custodian

  Two agents disagree about this file:
  
  Researcher: "Important JWT refresh pattern — consolidate into shared validator"
  Custodian:  "No imports found — safe to delete"
```

The conflict appears in your normal Paperclip issue tracker. You can assign it, comment, resolve — using the same workflow you use for everything else. The key is that you *see* the disagreement instead of two agents silently pushing contradictory recommendations.

---

## What your agents get

### MCP Resources (browsable via `@` mention)

Three resources your agents can pull into their context on demand:

| Resource | What it provides |
|---|---|
| `@prep://memory/{role}` | An agent's own prior observations and findings |
| `@prep://agents/{role}/findings` | Another agent's recent work (cross-agent visibility) |
| `@prep://delta` | What changed structurally since the last snapshot |

### Paperclip Data Providers

Two data providers available in the Paperclip plugin UI:

| Provider | What it provides |
|---|---|
| `structural-delta` | Recent structural changes in the codebase graph (dashboard widget) |
| `agent-claims` | Files currently claimed by agents (agent detail tab) |

### MCP Prompts (structured workflows via `/` command)

| Prompt | What it does |
|---|---|
| `/prep-handoff` | When one agent finishes and another picks up — packages context transfer with memory, findings, and structural delta |
| `/prep-scope` | Shows an agent what modules it owns, what changed in its scope, and what findings are open in its domain |
| `/prep-enrich` | Enriches findings with structural intelligence — blast radius, hub involvement, cross-module analysis |

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

You can see which agent found what, filter by agent, and trace findings back to their source. The Paperclip plugin automatically sets `created_by: "paperclip-agent"` for observations saved through it.

---

## How this fits with Paperclip

Prep doesn't replace Paperclip's orchestration. Paperclip decides *who* works on what and *when*. Prep provides the structural intelligence that makes those decisions better.

```
                Paperclip (orchestration)
                ┌─────────────────────┐
                │ Assigns tasks       │
                │ Tracks activity     │
                │ Manages agents      │
                │ Routes conflicts    │
                └────────┬────────────┘
                         │
                         │ Prep pushes:
                         │ • Structural delta (what shifted in the graph)
                         │ • Conflict issues (agents disagree about a file)
                         │ • File claims (what agents are working on)
                         │
                ┌────────▼────────────┐
                │ Prep (intelligence)│
                │ Agent memory        │
                │ Structural delta    │
                │ Conflict detection  │
                │ File-level claims   │
                └─────────────────────┘
```

**Prep provides three things Paperclip cannot compute:**

1. **Structural delta** — what changed in the dependency graph, not just what files changed
2. **File-level claims with structural awareness** — coordination at the code level, not the task level
3. **Pre-push conflict detection** — catch agent disagreements before they become separate Paperclip issues

Everything else (activity tracking, task routing, agent management, audit trail) belongs in Paperclip. Prep enriches Paperclip's coordination with structural intelligence. It doesn't replace it.

**Concrete integration points:**

1. **Agent startup** — When a Paperclip agent starts a session, its system prompt can include `@prep://memory/{role}` so it has its prior work context immediately.

2. **Handoff** — When Agent A finishes and Agent B picks up, the `prep-handoff` prompt packages what A found, what B should focus on, and the structural context for the relevant code area.

3. **Structural enrichment** — Before triaging findings, use `/prep-enrich` to add blast radius, hub involvement, and cross-module analysis to each finding. Paperclip gets better signal for routing.

4. **Conflict resolution** — Conflicts appear as Paperclip issues with both agents' assessments. Assign, comment, and resolve using your normal workflow.

5. **Structural awareness** — The `structural-delta` data provider shows what changed in the dependency graph since the last pipeline rebuild. Useful for scoping agent work and understanding codebase drift.

---

## What makes this different

Most multi-agent coordination tools focus on **message passing** — Agent A sends a message to Agent B, who responds. This requires agents to know about each other and creates tight coupling.

Prep's approach is **observation-mediated** — agents don't talk to each other directly. They leave traces of their work in a shared knowledge layer. Other agents (and humans) can browse those traces. Coordination emerges from shared awareness rather than explicit messaging.

This is more resilient (agents don't need to be online simultaneously), more transparent (all traces are inspectable), and works across any MCP client (Claude Code, Cursor, Windsurf, Gemini, or Paperclip-managed agents).

The other unique element is the **codebase graph as coordination medium**. Prep knows the structural relationships between files — which files are hubs, which modules depend on each other. When agents coordinate through Prep, they coordinate through *structural understanding*, not just file paths. This means conflict detection catches semantic conflicts ("these two agents are working on structurally connected code") not just name collisions.

---

## Getting started

If you're already using the Prep Paperclip plugin (`@prep/paperclip-plugin`), collaboration infrastructure is available through the same connection your agents already use.

1. **Agent attribution** — The plugin automatically sets `created_by` when agents save observations via `prep:observe`. Your agent's observations become browsable via `@prep://memory/{role}`.

2. **Cross-agent visibility** — Have agents include `@prep://agents/{role}/findings` in their startup context to see what other agents discovered.

3. **Structural delta** — Have long-running agents check `@prep://delta` at session start to understand what changed since their last run. Or view the `structural-delta` data provider in the Paperclip dashboard.

4. **Conflict alerts** — Conflicts automatically push to Paperclip as tagged issues. No polling or monitoring needed — they show up in your normal issue tracker.

5. **File claims** — The `agent-claims` data provider shows which files agents have claimed. View in the Paperclip agent detail tab to avoid routing conflicts.

No orchestration changes required. Your existing agent workflows continue to work — these are additive capabilities that make them smarter.
