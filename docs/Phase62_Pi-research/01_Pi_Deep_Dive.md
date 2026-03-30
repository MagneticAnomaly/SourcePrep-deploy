# Phase 62 — Pi Deep Dive: Tool, Architecture & Philosophy

> **Research Document 1 of 5** | Phase 62: Pi Integration Feasibility Study
> Date: 2026-03-30

---

## 1. What Is Pi?

**Pi** (officially at [shittycodingagent.ai](https://shittycodingagent.ai) / [pi.dev](https://pi.dev)) is a minimal, opinionated, terminal-based coding agent created by **Mario Zechner** ([@badlogic](https://github.com/badlogic/pi-mono)). It is MIT-licensed, open-source, and built in TypeScript as a monorepo of layered packages.

> **GitHub Stats:** 29.3k stars, 3.1k forks (as of March 2026)

### Core Philosophy
Pi's mantra is **"Primitives, not features."** Instead of baking in sub-agents, plan mode, permission gates, MCP support, or background bash, Pi provides a minimal core that users extend via TypeScript extensions, skills, prompt templates, and packages.

| Feature | Pi | Claude Code | Codex |
|---|---|---|---|
| Core tools | 4 (read, write, edit, bash) | ~20+ | ~5 |
| System prompt | <1000 tokens | ~10,000+ tokens | ~1000 tokens |
| Sub-agents | Extension (DIY) | Built-in | Built-in |
| MCP support | Extension (DIY) | Built-in | N/A |
| Plan mode | Extension (DIY) | Built-in | N/A |
| Background bash | Use tmux | Built-in | N/A |
| Permissions | YOLO/DIY | Permission gates | Sandboxed |

---

## 2. Architecture: The pi-mono Stack

Pi is a layered monorepo with five key packages:

```
┌─────────────────────────────────────────┐
│       pi-coding-agent (CLI)              │  ← Session management, tools, themes
├─────────────────────────────────────────┤
│       pi-agent-core                      │  ← Agent loop, state, events
├─────────────────────────────────────────┤
│       pi-ai                              │  ← Unified LLM API (15+ providers)
├─────────────────────────────────────────┤
│       pi-tui / pi-web-ui                 │  ← Terminal/Web rendering
├─────────────────────────────────────────┤
│       pi-pods                            │  ← GPU deployment (RunPod, Vast.ai)
└─────────────────────────────────────────┘
```

### 2.1 `pi-ai` — Unified LLM API
- Abstracts Anthropic, OpenAI, Google, Azure, Bedrock, Mistral, Groq, Cerebras, xAI, HuggingFace, Kimi, MiniMax, OpenRouter, Ollama
- **Cross-provider context handoff** — switch models mid-session while preserving conversation state
- **Abort/partial results** — full AbortController support throughout the pipeline
- **TypeBox schemas** — automatic JSON Schema validation for tool arguments
- **Streaming with partial JSON parsing** — progressive tool argument parsing for real-time UI

### 2.2 `pi-agent-core` — Agent Loop
- Processes user messages → tool calls → LLM responses → repeat until done
- No max-step limits; the loop runs until the agent says it's done
- Event-driven architecture for reactive UIs
- Message queuing (steering vs follow-up messages)

### 2.3 `pi-coding-agent` — The CLI
- 4 core tools: `read`, `write`, `edit`, `bash`
- Session management with tree-structured branching/history
- AGENTS.md context files (hierarchical: global → project-specific)
- SYSTEM.md for custom system prompts
- Compaction: auto-summarizes older messages as context usage approaches limit

---

## 3. Four Operational Modes

This is the most architecturally significant feature for integration purposes:

### 3.1 Interactive Mode
Full TUI experience in the terminal. Not relevant for programmatic integration.

### 3.2 Print / JSON Mode
```bash
pi -p "query"              # One-shot, human-readable output
pi -p "query" --mode json  # Structured JSON event stream
```
**Use case:** CI/CD pipelines, automated scripting, piping results into other tools.

### 3.3 RPC Mode
JSON protocol over stdin/stdout. Spawn Pi as a **subprocess** and communicate via JSONL.
- **Language agnostic** — any language that can read/write JSON lines
- **Cross-process isolation** — Pi runs in its own process
- **Ideal for:** IDE plugins, web UIs, custom automation pipelines

### 3.4 SDK Mode
Direct TypeScript/Node.js embedding:
```typescript
import { AgentSession } from '@mariozechner/pi-coding-agent';
// Full control over session lifecycle, events, tools, state
```
- **Ideal for:** Deep integrations, embedding agentic capabilities in applications

---

## 4. Extension System

Extensions are TypeScript modules with access to:
- **Custom tools** — register new capabilities the LLM can call
- **Commands** — add slash commands to the TUI
- **Keyboard shortcuts** — custom keybindings
- **Events/hooks** — intercept session start, turn boundaries, tool calls
- **TUI components** — custom UI overlays, status bars, editors
- **Dynamic context injection** — messages injected before each turn, context filtering, RAG

### Extension Examples (50+ in the repo)
| Extension | Description |
|---|---|
| `subagent/` | Sub-agent orchestration via tmux or Pi SDK |
| `plan-mode/` | Planning mode with read-only tool access |
| `permission-gate.ts` | Confirmation prompts before destructive actions |
| `protected-paths.ts` | Prevent writes to critical directories |
| `ssh.ts` | Execute commands on remote machines |
| `sandbox/` | Docker/container isolation for execution |
| `custom-compaction.ts` | Custom context compaction strategies |
| `doom-overlay/` | Yes, Doom runs inside Pi |

### Packages
Bundle extensions + skills + prompts + themes into distributable packages:
```bash
pi install npm:@foo/pi-tools
pi install git:github.com/user/repo
```

### Skills
Capability packages loaded on-demand (progressive disclosure):
- Instructions + tools loaded only when invoked via `/skill:name`
- Avoids polluting the base context window

---

## 5. The Anti-MCP Argument

Pi explicitly does **not** include MCP support. Mario's position (from his blog):

> **MCP servers are overkill for most use cases.** Popular MCP servers like Playwright MCP (21 tools, 13.7k tokens) dump their entire tool descriptions into context on every session. That's 7-9% of your context window gone before you even start working.

**Pi's alternative:** CLI tools with README files.
- The agent reads the README only when needed (progressive disclosure)
- Token cost is paid only on use, not on every session
- CLI tools are composable (pipe outputs, chain commands)
- Easy to create, modify, and extend

> [!NOTE]
> This is a **strong philosophical argument** but runs counter to CoDRAG's existing MCP-first architecture. CoDRAG *is* an MCP server. This tension is a key decision point.

---

## 6. Benchmark Performance

Pi with Claude Opus 4.5 placed competitively on Terminal-Bench 2.0 against Claude Code, Codex, Cursor, and Windsurf — despite having a <1000 token system prompt and only 4 tools. This validates the "minimal harness" approach.

---

## 7. Key Takeaways for CoDRAG

| Aspect | Relevance | Notes |
|---|---|---|
| `pi-ai` unified LLM API | ⭐⭐⭐ | CoDRAG already has its own multi-provider `llm_client.py` |
| RPC/SDK modes | ⭐⭐⭐⭐ | Could embed CoDRAG intelligence *into* Pi |
| Extension system | ⭐⭐⭐⭐⭐ | CoDRAG could be a Pi extension/package |
| Skills concept | ⭐⭐⭐⭐ | CoDRAG context could be a Pi skill |
| Anti-MCP philosophy | ⚠️ Tension | CoDRAG is an MCP server; Pi doesn't do MCP |
| Context engineering | ⭐⭐⭐⭐ | Pi's progressive disclosure aligns with CoDRAG's LOD compression |
| CLI-first tooling | ⭐⭐⭐ | CoDRAG already has a CLI |

---

*Next: [02_CoDRAG_Epistemology.md](./02_CoDRAG_Epistemology.md) — CoDRAG's architecture and where Pi might fit*
