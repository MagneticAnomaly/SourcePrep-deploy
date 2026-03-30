# Phase 62 — Ecosystem Map & Recommended Configurations

> **Research Document 6 of 6** | Phase 62: Pi Integration Feasibility Study
> Date: 2026-03-30

---

## 1. The Real Question

The original question was "should we integrate Pi?" But the deeper question is:

> **CoDRAG is an intelligence layer, not a coding agent. How should it position itself in the broader ecosystem where users may be running Claude Code, Cursor, Antigravity, Pi, Paperclip, or some combination — and what should we recommend?**

---

## 2. The Ecosystem Map: What Each Tool Actually Is

The user's Paperclip document reveals a sophisticated stack:
**Paperclip → Claude Code → Sequential Thinking MCP → Superpowers plugin**

This is a fundamentally different concern than "Pi vs Claude Code." Let's define what each layer does:

```
┌─────────────────────────────────────────────────────────────────────────┐
│  LAYER 4: ORCHESTRATOR (Multi-Agent Management)                         │
│  ┌────────────┐                                                         │
│  │ Paperclip  │  Manages multiple agents as "employees"                 │
│  │            │  Heartbeat scheduling, budgets, org charts              │
│  └────────────┘                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│  LAYER 3: CODING AGENT (Execution Harness)                              │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐          │
│  │Claude Code │ │  Cursor    │ │Antigravity │ │    Pi      │          │
│  │(terminal)  │ │  (IDE)     │ │  (IDE)     │ │(terminal)  │          │
│  └────────────┘ └────────────┘ └────────────┘ └────────────┘          │
├─────────────────────────────────────────────────────────────────────────┤
│  LAYER 2: REASONING & WORKFLOW (Structured Thinking)                    │
│  ┌────────────────────┐  ┌────────────────────┐                        │
│  │ Sequential Thinking│  │ Superpowers Plugin │                        │
│  │ MCP Server         │  │ (TDD, Planning)    │                        │
│  └────────────────────┘  └────────────────────┘                        │
├─────────────────────────────────────────────────────────────────────────┤
│  LAYER 1: INTELLIGENCE (Codebase Understanding)                         │
│  ┌────────────────────┐  ┌────────────────────┐                        │
│  │ ★ CoDRAG ★        │  │ Context7 / Docs    │                        │
│  │ Structure, Search, │  │ Library docs       │                        │
│  │ Impact, Audit      │  │                    │                        │
│  └────────────────────┘  └────────────────────┘                        │
├─────────────────────────────────────────────────────────────────────────┤
│  LAYER 0: MODELS (LLM Infrastructure)                                   │
│  ┌────────────────────┐  ┌────────────────────┐                        │
│  │ Ollama (local)     │  │ Cloud APIs         │                        │
│  │ Kimi, Qwen, etc.   │  │ Anthropic, OpenAI  │                        │
│  └────────────────────┘  └────────────────────┘                        │
└─────────────────────────────────────────────────────────────────────────┘
```

### The Critical Insight

> **CoDRAG lives at Layer 1.** It is not competing with Claude Code, Cursor, Pi, or Antigravity (Layer 3). It is not competing with Sequential Thinking or Superpowers (Layer 2). It is not competing with Paperclip (Layer 4). **CoDRAG provides the foundational intelligence that makes ALL of these tools work better.**

This means:
- CoDRAG doesn't need to "pick" an agent
- CoDRAG needs to be **universally consumable** by any agent at Layer 3
- CoDRAG's recommendations should be about **which agent to pair with**, not which to replace

---

## 3. Does Pi Replace Claude Code? (No.)

| Dimension | Claude Code | Pi |
|---|---|---|
| **Backing company** | Anthropic (multi-billion $) | Solo dev (Mario Zechner) |
| **Model lock-in** | Claude models only | Any provider (15+) |
| **Sub-agents** | Built-in, polished | DIY via extension |
| **MCP support** | Native, first-class | None (anti-MCP philosophy) |
| **Plan mode** | Built-in | Extension |
| **Permissions** | Auto-mode classifier | YOLO (or DIY gate) |
| **Superpowers** | Native plugin support | N/A |
| **Sequential Thinking** | Works via MCP | Would need extension |
| **AGENTS.md** | ✅ Supported | ✅ Supported |
| **CoDRAG compatibility** | ✅ MCP + CLI | ✅ CLI + Skill |
| **Community** | Anthropic ecosystem | 29k stars, indie |
| **Cost** | Anthropic API pricing | Any model pricing |
| **Observability** | Moderate (improving) | Excellent (core design) |
| **Context engineering** | Automated (opaque) | Manual (transparent) |

### Verdict

Pi and Claude Code serve **different audiences**:
- **Claude Code** → Users who want a polished, batteries-included experience with Anthropic's models
- **Pi** → Power users who want full control over context, model selection, and tool composition

**Neither replaces the other.** A Paperclip user who runs Claude Code as their adapter will never use Pi for that same role. But a Pi user who values minimal context overhead will never use Claude Code's 10k-token system prompt.

**CoDRAG must serve both.**

---

## 4. How CoDRAG Fits the Paperclip + Sequential Thinking + Superpowers Stack

The user's existing stack is:

```
Paperclip (orchestrator)
  └→ Claude Code (claude-local adapter)
       ├→ Sequential Thinking MCP (structured reasoning)
       ├→ Superpowers Plugin (TDD, planning)
       └→ ??? CoDRAG goes HERE
```

### Where CoDRAG Adds Value

| Without CoDRAG | With CoDRAG |
|---|---|
| Agent reads files one at a time | Agent gets structural overview instantly |
| Agent guesses at dependencies | Agent queries blast radius before changes |
| Agent may miss related files | Agent gets trace-expanded context |
| Agent has no codebase memory | Agent has cross-session observations |
| Sequential Thinking reasons without structure | Sequential Thinking reasons WITH codebase graph |

### How to Connect

**For the Paperclip stack**, CoDRAG connects as an MCP server alongside Sequential Thinking:

```json
// ~/.claude/settings.json
{
  "mcpServers": {
    "codrag": {
      "command": "codrag",
      "args": ["mcp"]
    },
    "sequential-thinking": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"]
    }
  }
}
```

Superpowers is a plugin (not MCP), so it coexists without conflict.

**The enriched workflow becomes:**
1. Paperclip assigns a task to a Claude Code agent
2. Agent invokes **CoDRAG** → understands codebase structure, finds relevant files
3. Agent invokes **Sequential Thinking** → breaks down the problem with structural awareness
4. Agent follows **Superpowers** → brainstorm → plan → TDD → execute
5. Agent reports back to Paperclip via heartbeat

> [!IMPORTANT]
> **CoDRAG makes Sequential Thinking dramatically more valuable.** Without CoDRAG, Sequential Thinking reasons in a vacuum. With CoDRAG, each reasoning step is grounded in actual codebase structure.

---

## 5. Revised Recommendation: Don't Build Pi Features, Build Universal Access

Our original Phase 62 recommendations were Pi-centric. Here's the revised view:

### What Changed

| Original Rec | Revised Thinking |
|---|---|
| R1: CoDRAG Pi Skill File | ✅ Still good — but it's **one of many** |
| R2: AGENTS.md integration | ✅ Still good — works with ALL agents |
| R3: Pi Package (npm) | 🟡 Lower priority — Pi is one of many consumers |
| R4: CLI Tool Wrappers | ⬆️ **Higher priority** — agent-agnostic |
| R5: Pi RPC Execute Engine | ⬇️ **Lower priority** — Claude Code sub-agents are better |

### The New Priority Stack

```
Priority 1 (Universal):  Agent-agnostic access
Priority 2 (MCP):        MCP-native agent support (Claude Code, Cursor, Antigravity)
Priority 3 (CLI):        CLI/bash access (Pi, Claude Code bash, any terminal agent)
Priority 4 (Specific):   Agent-specific packages (Pi skill, Superpowers integration)
```

---

## 6. Recommended Configuration Profiles

CoDRAG should document and recommend **configuration profiles** — presets that tell users how to set up CoDRAG depending on their stack. Here's the framework:

### Profile A: "Minimal" (Solo Dev, Local-First)

> *"I just want better code search."*

```
Models:     Built-in ONNX embeddings (zero config)
Agent:      Any (Cursor, VS Code, terminal)
MCP:        Optional (can use CLI)
Extra:      None
Cost:       $0 (fully local)
```

**CoDRAG Setup:**
```bash
pip install codrag
codrag add /path/to/project
codrag build
codrag search "how does X work?"
```

---

### Profile B: "Standard" (Daily Dev with AI Assistant)

> *"I use Cursor/Claude Code and want CoDRAG context."*

```
Models:     Ollama nomic-embed-code (GPU) + Kimi 2.5 k1:cloud (analysis)
Agent:      Claude Code / Cursor / Antigravity
MCP:        ✅ CoDRAG MCP server
Extra:      AGENTS.md in repo root
Cost:       Ollama (free) + cloud model API costs
```

**CoDRAG Setup:**
```bash
pip install codrag
codrag add /path/to/project --name "My Project"
codrag build
codrag serve

# Add to your AI assistant's MCP config:
# "codrag": { "command": "codrag", "args": ["mcp"] }
```

---

### Profile C: "Power User" (Claude Code + Reasoning Stack)

> *"I use Claude Code with Sequential Thinking and Superpowers."*

```
Models:     Ollama nomic-embed-code + Kimi 2.5 k1:cloud
Agent:      Claude Code (primary)
MCP:        ✅ CoDRAG + Sequential Thinking
Plugins:    Superpowers (Claude Code plugin)
Extra:      CLAUDE.md + AGENTS.md
Cost:       Anthropic API + Ollama (free)
```

**CoDRAG Setup:**
```bash
pip install codrag
codrag add /path/to/project
codrag build
codrag serve

# MCP config (add alongside sequential-thinking):
claude mcp add codrag -- codrag mcp
claude mcp add sequential-thinking -- npx -y @modelcontextprotocol/server-sequential-thinking
```

---

### Profile D: "Enterprise" (Paperclip Multi-Agent)

> *"I run Paperclip with multiple Claude Code agents."*

```
Models:     Ollama nomic-embed-code + cloud models
Agent:      Paperclip → Claude Code (claude-local adapter)
MCP:        ✅ CoDRAG (user-scope, inherited by all Paperclip agents)
Plugins:    Superpowers (user-scope)
Extra:      AGENTS.md + Per-agent prompt templates referencing CoDRAG
Cost:       Anthropic API + orchestration overhead
```

**CoDRAG Setup:**
```bash
pip install codrag
codrag serve  # Daemon must run before Paperclip spawns agents

# User-scope MCP (inherited by all Paperclip-spawned agents):
claude mcp add codrag --scope user -- codrag mcp
claude mcp add sequential-thinking --scope user -- npx -y @modelcontextprotocol/server-sequential-thinking
```

**Paperclip Agent Prompt Template:**
```
Before starting work:
1. Use codrag to get the codebase overview
2. Use codrag_search to find relevant files for this task
3. Use codrag_impact to check blast radius before changes
4. Use sequential_thinking to plan the implementation
5. Follow Superpowers TDD workflow for execution
```

---

### Profile E: "Minimalist" (Pi Power User)

> *"I use Pi and want codebase intelligence without MCP bloat."*

```
Models:     Any (via Pi's pi-ai, or Ollama for CoDRAG)
Agent:      Pi
MCP:        ❌ (Pi doesn't use MCP)
Integration: CoDRAG CLI via bash / Pi skill file
Extra:      AGENTS.md (auto-loaded by Pi)
Cost:       Any model API + Ollama (free)
```

**CoDRAG Setup:**
```bash
pip install codrag
codrag add /path/to/project
codrag build
codrag serve

# Pi loads AGENTS.md automatically
# Use CoDRAG via bash in Pi sessions:
# > Search CoDRAG for auth implementation
# Pi runs: codrag search "auth implementation"
```

---

### Profile F: "Antigravity Native" (Google Ecosystem)

> *"I use Antigravity and want the deepest integration."*

```
Models:     Ollama nomic-embed-code + Kimi 2.5 k1:cloud
Agent:      Google Antigravity
MCP:        ✅ CoDRAG MCP server (auto-detected)
Extra:      AGENTS.md (managed by CoDRAG)
Cost:       Antigravity subscription + Ollama (free)
```

**CoDRAG Setup:**
```bash
pip install codrag
codrag add /path/to/project
codrag build
codrag serve

# Antigravity auto-discovers CoDRAG MCP when AGENTS.md is present
```

---

## 7. What Should We Build?

### Must Build (Agent-Agnostic)

| Item | Description | Serves |
|---|---|---|
| ✅ **Config Profiles docs** | Document the 6 profiles above | All users |
| ✅ **CLI tool wrappers** | Standalone bash scripts with README | Every agent |
| ✅ **AGENTS.md best practices** | Guide for CoDRAG + AGENTS.md setup | All agents that read AGENTS.md |
| ✅ **MCP onboarding updates** | Add Sequential Thinking co-existence guide | Claude Code, Cursor, Antigravity |

### Should Build (High-Value)

| Item | Description | Serves |
|---|---|---|
| 🟡 **Pi skill file** | Progressive disclosure for Pi users | Pi users |
| 🟡 **Superpowers integration guide** | How CoDRAG enriches Superpowers TDD workflow | Claude Code power users |
| 🟡 **Paperclip config template** | Agent prompt templates with CoDRAG tools | Paperclip users |

### Could Build (Specific)

| Item | Description | Serves |
|---|---|---|
| 🔵 Pi npm package | Distributable Pi package | Pi community |
| 🔵 Cursor extension | Native Cursor integration | Cursor users |
| 🔵 Antigravity plugin | Deep Antigravity integration | Antigravity users |

### Should NOT Build

| Item | Why Not |
|---|---|
| ❌ Pi RPC as execute engine | Claude Code sub-agents are more mature for this |
| ❌ Agent-specific lock-in features | CoDRAG must remain agent-agnostic |
| ❌ Replace Sequential Thinking | CoDRAG is intelligence, not reasoning — they complement |
| ❌ Replace Superpowers | CoDRAG is intelligence, not workflow — they complement |

---

## 8. The Versatility Principle

> *"I want this CoDRAG app to be versatile enough it can be simple, but also have recommended implementation configs"*

This is exactly right. CoDRAG's positioning should be:

```
┌──────────────────────────────────────────────────────────────┐
│                    CoDRAG                                     │
│                                                               │
│   "Codebase intelligence that works with YOUR tools."         │
│                                                               │
│   ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐          │
│   │  MCP    │ │  CLI    │ │  HTTP   │ │AGENTS.md│          │
│   │(Claude  │ │(Pi,any) │ │(custom) │ │(all)    │          │
│   │ Code,   │ │         │ │         │ │         │          │
│   │Cursor,  │ │         │ │         │ │         │          │
│   │Antigrav)│ │         │ │         │ │         │          │
│   └─────────┘ └─────────┘ └─────────┘ └─────────┘          │
│                                                               │
│   Zero config to start. Recommended configs for power users.  │
└──────────────────────────────────────────────────────────────┘
```

Like how CoDRAG currently recommends `nomic-embed-code` via Ollama but works fine with built-in ONNX, it should recommend **Profile C** (Claude Code + Sequential Thinking + CoDRAG MCP) as the "power user" setup while making **Profile A** work with zero configuration.

---

## 9. Updated Summary Table

| Tool | Relationship to CoDRAG | Action |
|---|---|---|
| **Claude Code** | Primary consumer via MCP | ✅ Already works. Enhance docs. |
| **Cursor** | Consumer via MCP | ✅ Already works. |
| **Antigravity** | Consumer via MCP | ✅ Already works (we're using it now). |
| **Pi** | Consumer via CLI/skill | 🟡 Create skill file + CLI wrappers. |
| **Sequential Thinking** | Complementary MCP server | 📄 Document co-existence best practices. |
| **Superpowers** | Complementary Claude plugin | 📄 Document how CoDRAG enriches TDD. |
| **Paperclip** | Orchestrator (Layer 4) | 📄 Provide agent prompt templates. |
| **Ollama** | Model infrastructure (Layer 0) | ✅ Already integrated. Keep recommending. |

---

*This document supersedes the Pi-specific recommendations in [05_Recommendations.md](./05_Recommendations.md) with a broader ecosystem-aware strategy.*
