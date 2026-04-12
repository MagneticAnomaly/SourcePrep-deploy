# Phase 94 — CoDRAG + OpenClaw: Minimal Integration Path

**Date:** 2026-04-09
**Goal:** Verify CoDRAG works with OpenClaw, document the clear path, build nothing.

---

## 1. Why This Works Out of the Box

CoDRAG exposes an MCP server via **stdio transport** — the same transport OpenClaw's `mcporter` skill natively supports. No adapters, no plugins, no glue code needed.

```
OpenClaw Gateway
  └─ mcporter skill (stdio MCP client)
       └─ codrag mcp (stdio MCP server)
            └─ CoDRAG daemon (:8400)
```

All 6 CoDRAG tools are read-only with `readOnlyHint: True` and `idempotentHint: True`. OpenClaw cannot corrupt CoDRAG state.

---

## 2. Configuration (Zero Code)

### Step 1: Ensure CoDRAG daemon is running

```bash
codrag serve  # default port 8400
```

### Step 2: Add MCP server to OpenClaw

In your OpenClaw workspace `openclaw.json`:

```json
{
  "mcp": {
    "servers": {
      "codrag": {
        "transport": "stdio",
        "command": "/path/to/your/project/.venv/bin/codrag",
        "args": ["mcp", "--mode", "server", "--daemon", "http://127.0.0.1:8400"],
        "env": {}
      }
    }
  }
}
```

Or if using the wrapper script (handles venv activation and logging):

```json
{
  "mcp": {
    "servers": {
      "codrag": {
        "transport": "stdio",
        "command": "/path/to/your/project/codrag-mcp-wrapper.sh",
        "args": [],
        "env": {}
      }
    }
  }
}
```

### Step 3: Restrict tool access per agent

In the agent's SOUL.md or OpenClaw agent config:

```json
{
  "tools": {
    "allow": [
      "codrag",
      "codrag_search",
      "codrag_impact",
      "codrag_audit",
      "codrag_observe",
      "codrag_concepts"
    ]
  }
}
```

That's it. OpenClaw discovers the tools at gateway startup and makes them available to permitted agents.

---

## 3. Tools Available to OpenClaw Agents

| Tool | What It Returns | Typical Use |
|------|----------------|-------------|
| `codrag` | Module map, hub files, focus areas, immune system alerts | Agent orientation at start of task |
| `codrag_search` | Semantic code search with structural trace expansion | "Where is the auth middleware?" |
| `codrag_impact` | Dependencies + dependents for a file/symbol | "What breaks if I change server.py?" |
| `codrag_audit` | Structural findings (coupling, cycles, drift) | Daily health digest |
| `codrag_observe` | Cross-session notes and observations | Save/retrieve decisions |
| `codrag_concepts` | Business rationale, architecture decisions | "Why does the pipeline have 11 stages?" |

All tools accept an optional `project_id` parameter for multi-project setups.

---

## 4. Example SOUL.md Fragment

For a "Code Intelligence Reporter" agent that posts daily digests:

```markdown
# SOUL.md — CoDRAG Reporter

You are a code intelligence reporter. You use CoDRAG tools to analyze
codebase health and report findings to the team.

## Rules

- You are READ-ONLY. Never execute shell commands, modify files, or take
  actions based on CoDRAG findings.
- Present all findings as informational summaries, not commands.
- When CoDRAG is unavailable, say so and stop. Do not retry or attempt
  workarounds.
- Limit reports to the configured schedule. Do not send unsolicited messages.
- Always include the source tool and query in your reports so findings
  are traceable.

## Workflow

1. Call `codrag` for structural overview
2. Call `codrag_audit` for current findings
3. Summarize: what changed, what's healthy, what needs attention
4. Format as a concise digest (under 500 words)
```

---

## 5. Scoped Agent Recipes

### Recipe A: Standup Bot (Slack/Discord)

**Tools needed:** `codrag`, `codrag_audit`
**Schedule:** Daily, 9am
**Behavior:** Posts a 3-bullet summary of codebase health — new findings, resolved findings, hub file changes.

### Recipe B: PR Review Assistant

**Tools needed:** `codrag_impact`, `codrag_search`
**Trigger:** Webhook on PR open
**Behavior:** Calls `codrag_impact` on changed files, reports blast radius and affected modules in PR thread.

### Recipe C: Architecture Drift Monitor

**Tools needed:** `codrag`, `codrag_audit`, `codrag_concepts`
**Schedule:** Weekly
**Behavior:** Compares current structural findings against recorded architecture concepts. Flags drift.

### Recipe D: Ad-Hoc Query Responder

**Tools needed:** All 6 tools
**Trigger:** Direct message
**Behavior:** Team member asks "what depends on server.py?" in Slack, agent calls `codrag_impact` and replies in-thread.

---

## 6. What We Do NOT Build

| Item | Reason |
|------|--------|
| OpenClaw plugin/npm package | Stdio MCP works natively. No wrapper needed. |
| OpenClaw-specific endpoints in CoDRAG | MCP is the universal interface. |
| Write operations from OpenClaw | CoDRAG governance stays with Paperclip and direct IDE usage. |
| ClawHub skill (for now) | Validate locally first. Publish only if demand emerges. |
| Agent-to-agent protocol | A2A not ready on either side. Premature. |

---

## 7. Verification Checklist

To confirm "CoDRAG works with OpenClaw":

- [ ] CoDRAG daemon running (`codrag serve`)
- [ ] OpenClaw gateway started with `codrag` MCP server in `openclaw.json`
- [ ] Gateway logs show successful MCP handshake and tool discovery (6 tools)
- [ ] Agent can call `codrag` and receive structural overview
- [ ] Agent can call `codrag_search` with a natural language query
- [ ] Agent can call `codrag_impact` on a known file path
- [ ] Agent can call `codrag_audit` and receive findings
- [ ] Tool allowlisting works (agent without `codrag_impact` in allowlist cannot call it)
- [ ] Agent respects SOUL.md constraints (no execution, informational only)

---

## 8. Risk Boundaries

**What CoDRAG controls:**
- Tool schemas and behavior (read-only, idempotent)
- Response format and content
- Daemon availability

**What OpenClaw controls (not our problem):**
- Agent execution safety
- Channel routing and message delivery
- Credential management
- Skill registry security

**The boundary is clean:** CoDRAG is a read-only MCP server. It doesn't know or care whether the client is Claude Code, Cursor, OpenClaw, or anything else. The MCP protocol is the contract.

---

## 9. Architectural Position: CoDRAG as Knowledge Tool, Not Agent Host

### CoDRAG's role is clear: knowledge provider via MCP.

OpenClaw agents consume CoDRAG the same way Claude Code and Cursor do — as a read-only intelligence source. CoDRAG does not run OpenClaw, manage OpenClaw agents, or depend on OpenClaw for any core functionality.

### Paperclip manages the agents, not CoDRAG.

The natural orchestration path is:

```
Paperclip (governance, task routing, agent lifecycle)
  └─ OpenClaw agent (execution, messaging, scheduling)
       └─ CoDRAG MCP (read-only codebase intelligence)
```

Paperclip decides WHEN and WHY an agent runs. OpenClaw is the HOW — it provides the runtime, messaging channels, and scheduling. CoDRAG provides the WHAT — structural context, search, impact analysis. Each layer does one thing.

This means:
- Paperclip can spin up an OpenClaw agent for a specific task (e.g., "post weekly drift report to #architecture")
- Paperclip governs the agent's lifecycle, permissions, and output destinations
- CoDRAG just answers MCP queries — it doesn't know or care who's asking

### The Researcher angle: promising but not yet clear enough.

The one place OpenClaw could run as an agent FOR CoDRAG is the Researcher role — an OpenClaw agent that:
- Crawls documentation, GitHub issues, changelogs for external projects
- Feeds findings back to CoDRAG's observation/concept stores
- Monitors ecosystem changes relevant to the indexed codebase

This is interesting because it gives CoDRAG an "outward eye" it currently lacks. But:
- The write path (observations, concepts) needs governance guardrails
- The research workflow needs clearer definition (what triggers research? what's the output format? who reviews findings before they enter the knowledge base?)
- It's close to a purposeful integration but needs one more round of design to be concrete

**Status:** Park this as a research opportunity. Revisit when the Researcher engine's external data ingestion patterns are better defined.

---

## 10. Future Path (Only If Validated)

```
Now:     Documentation + config examples (this document)
         ↓
If used: Paperclip recipe for OpenClaw + CoDRAG agent coordination
         ↓
If Researcher design matures: OpenClaw as external research agent feeding CoDRAG
         ↓
If A2A lands: Agent Card at /.well-known/agent.json
```

Each step is gated on real usage or design clarity from the previous step. No speculative investment.
