# Phase 62 — Extensions, Agents & Industry Standards

> **Research Document 3 of 5** | Phase 62: Pi Integration Feasibility Study
> Date: 2026-03-30

---

## 1. Pi's Extension Ecosystem in Detail

### 1.1 Extension Anatomy

A Pi extension is a TypeScript module that exports a function receiving a context object:

```typescript
// example-extension.ts
import { PiExtension } from '@mariozechner/pi-coding-agent';

export default function myExtension(ctx: PiExtension) {
  // Register a custom tool
  ctx.addTool({
    name: 'codrag_search',
    description: 'Search codebase structure using CoDRAG',
    parameters: { query: { type: 'string' } },
    execute: async (args) => {
      const result = await fetch('http://localhost:8400/search', {
        method: 'POST',
        body: JSON.stringify({ query: args.query })
      });
      return { output: await result.text() };
    }
  });

  // Register a slash command
  ctx.addCommand('/codrag', 'Search codebase with CoDRAG', async (args) => {
    ctx.sendMessage(`Search CoDRAG for: ${args}`);
  });

  // Hook into session lifecycle
  ctx.on('sessionStart', async () => {
    // Auto-inject CoDRAG context at session start
    const overview = await fetch('http://localhost:8400/codrag');
    ctx.injectSystemMessage(await overview.text());
  });
}
```

### 1.2 What Extensions Can Access

| Capability | Description | CoDRAG Relevance |
|---|---|---|
| **Custom tools** | Register new LLM-callable tools | Map all 5 CoDRAG MCP tools |
| **Commands** | Slash commands in the TUI | `/codrag`, `/impact`, `/audit` |
| **Keyboard shortcuts** | Custom keybindings | Quick-access to CoDRAG features |
| **Session events** | Intercept turn boundaries | Auto-inject CoDRAG context |
| **Dynamic context** | Inject messages before each turn | Live codebase awareness |
| **Message filtering** | Filter/modify conversation history | Compress old CoDRAG results |
| **TUI overlays** | Custom UI components | Display dependency graphs |
| **State persistence** | Store data within sessions | Cache CoDRAG search results |

### 1.3 Pi Skills vs Extensions

| Aspect | Skills | Extensions |
|---|---|---|
| Loaded when | On-demand (`/skill:name`) | Always active |
| Format | Markdown + CLI tools | TypeScript modules |
| Context cost | Only when invoked | Always in context |
| Capabilities | Instructions + bash tools | Full programmatic access |
| Best for | Progressive disclosure | Always-on integration |

> [!IMPORTANT]
> **For CoDRAG, a hybrid approach is optimal:** A lightweight extension that registers CoDRAG's tools + a skill file that provides detailed usage instructions loaded on-demand.

---

## 2. Industry-Standard Agent Extensions & Integrations

### 2.1 MCP (Model Context Protocol)

The **de facto industry standard** for tool/data source integration:

| Aspect | Details |
|---|---|
| Created by | Anthropic |
| Adopted by | Cursor, Windsurf, Cline, Continue, Zed, VS Code, JetBrains |
| Transport | stdio, SSE, WebSocket |
| Protocol | JSON-RPC 2.0 |
| CoDRAG status | **Already implemented** (stdio transport) |

> CoDRAG's existing MCP server is the most portable integration. It works with every MCP-compatible agent, including Pi (via extension adapter).

### 2.2 OpenAI Function Calling / Tool Use

The universal tool interface that all major LLMs support natively:
- OpenAI, Anthropic, Google, Mistral all support tool/function schemas
- Pi's `pi-ai` layer handles cross-provider tool calling
- CoDRAG could define tool schemas that any agent can use

### 2.3 AGENTS.md Convention

Industry-wide convention for agent context files:
- **Adopted by:** Antigravity (Google), Claude Code, Pi, Cursor, Windsurf, and 22+ tools
- **CoDRAG status:** Already generates AGENTS.md content; manages the `.agents/` directory
- **Pi support:** Loads AGENTS.md hierarchically (global → project)

> [!TIP]
> CoDRAG already writes to AGENTS.md. If Pi is installed in a project, it will automatically load CoDRAG's AGENTS.md content. **This is zero-effort integration.**

### 2.4 Language Server Protocol (LSP)

The original IDE integration standard for code intelligence:
- **Not relevant** for agent integration (designed for editors, not LLMs)
- CoDRAG's graph-level intelligence goes far beyond what LSP provides

### 2.5 VS Code Extension API

CoDRAG already has a VS Code extension (`packages/vscode/`):
- Daemon integration, embeddings, RAG features
- Webview UI for code navigation
- **Not Pi-specific** but represents CoDRAG's existing IDE integration story

---

## 3. Sub-Agent Architectures

### 3.1 Pi's Approach: DIY via bash/tmux

Pi doesn't have built-in sub-agents. The recommended patterns:

**Pattern A: Direct bash invocation**
```bash
pi --print "Analyze this code for security issues" --provider anthropic --model claude-sonnet-4-5
```

**Pattern B: tmux sessions**
```bash
tmux new-session -d -s "review" "pi --print 'Review PR #42'"
# Later: tmux capture-pane -t review -p
```

**Pattern C: SDK embedding**
```typescript
const session = createAgentSession({ tools: [...] });
const result = await session.run("Analyze security...");
```

### 3.2 Claude Code's Approach: Built-in Sub-Agents
- Orchestrating agent spawns sub-agents for task decomposition
- Poor observability (black box within black box)
- Context transfer is opaque and uncontrollable

### 3.3 Codex's Approach: Multi-Agent Groups
- Parallel agent groups for high-throughput tasks
- Optimized for velocity, not for deep understanding
- Well-suited for CI/CD and batch operations

### 3.4 Industry Trend: Agent-as-a-Service

Emerging pattern where specialized agents are invoked as services:
```
Orchestrator Agent
├── CoDRAG Agent (codebase intelligence)
├── Testing Agent (test generation)
├── Review Agent (code review)
└── Deploy Agent (CI/CD management)
```

> [!IMPORTANT]
> **This is where CoDRAG's highest value lies with Pi.** CoDRAG isn't another general-purpose coding agent — it's a **specialized intelligence service** that any agent can query. The question isn't "should we replace something with Pi?" but "should we make CoDRAG available as a Pi skill/extension so Pi users get codebase intelligence?"

---

## 4. Community Extensions We Could Leverage

### 4.1 Existing Pi Packages

| Package | Relevance | Source |
|---|---|---|
| `pi-tidy-mcp-adapter` | Bridges MCP → Pi tools | Community |
| Sub-agent extension | Orchestration patterns | Official examples |
| Custom compaction | Context management | Official examples |
| Protected paths | Safety for CoDRAG data | Official examples |

### 4.2 CoDRAG-Specific Extensions We Could Build

| Extension | Description | Effort |
|---|---|---|
| `pi-codrag` | Full CoDRAG tool registration | 🟡 Medium |
| `pi-codrag-skill` | Markdown skill file for progressive loading | 🟢 Low |
| `pi-codrag-context` | Auto-inject CoDRAG overview at session start | 🟢 Low |
| `pi-codrag-impact` | Pre-change blast radius analysis | 🟡 Medium |

---

## 5. Comparison: Pi Extensions vs CoDRAG MCP Tools

| Dimension | Pi Extension | CoDRAG MCP Tool |
|---|---|---|
| Portability | Pi only | Any MCP client |
| Context cost | Minimal (lazy) | ~2-3k tokens upfront |
| Composability | Full bash piping | JSON-RPC only |
| Customizability | Full TypeScript | Schema-defined |
| Community reach | Growing (29k stars) | Broad (MCP standard) |
| Maintenance | Separate package | Already exists |

---

*Next: [04_Opportunities_Analysis.md](./04_Opportunities_Analysis.md) — Concrete opportunities for leveraging Pi in CoDRAG's pipelines*
