# Phase 62 — CoDRAG Epistemology & Integration Surface Analysis

> **Research Document 2 of 5** | Phase 62: Pi Integration Feasibility Study
> Date: 2026-03-30

---

## 1. CoDRAG's Identity & Architecture

CoDRAG is a **local-first, AI-powered codebase intelligence system** that maps structural relationships in codebases — modules, dependencies, hub files, and architectural patterns. It delivers this intelligence through multiple interfaces.

### Core Stack
| Layer | Technology | Purpose |
|---|---|---|
| Engine | Python (FastAPI) | 11-stage indexing pipeline, LLM orchestration |
| Graph DB | JSONL + SQLite | Trace nodes/edges, project registry |
| Embeddings | ONNX / Ollama | Semantic search vectors |
| Parser | Rust (codrag_engine) | AST parsing, symbol extraction |
| Dashboard | React (Tauri) | Visual exploration UI |
| CLI | Python (`codrag`) | Scripting & automation |
| MCP Server | Python (stdio) | IDE integration (Windsurf, Cursor, Antigravity) |
| VS Code | TypeScript | Extension with webview UI |

### The 11-Stage Pipeline
```
Stage 1:  File Discovery (scan repo)
Stage 2:  Inferred Edges (LLM-based, coder model)
Stage 3:  Catalogue (LLM-based, small/instruct model)
Stage 4:  Chunking (text segmentation)
Stage 5:  Embeddings (vector generation)
─── Fast Sync boundary ───
Stage 6:  Epistemic Analysis (LLM deep reasoning)
Stage 7:  Module Clustering (LLM-based grouping)
Stage 8:  Module Synthesis (LLM summary generation)
Stage 9:  Deep Enrichment (hub analysis)
Stage 10: Atlas Generation (codebase overview)
Stage 11: Finalization (manifest, cleanup)
```

### CoDRAG's MCP Tools
CoDRAG exposes **5 MCP tools**:
1. `codrag` — Structural overview (modules, hubs, focus areas)
2. `codrag_search` — Semantic search with structural trace expansion
3. `codrag_impact` — Dependency/dependent analysis (blast radius)
4. `codrag_audit` — Codebase health findings
5. `codrag_observe` — Cross-session memory (save/retrieve observations)

### Current LLM Client
CoDRAG has its own `llm_client.py` supporting:
- **Providers:** Ollama, OpenAI, OpenAI-compatible, Anthropic, Google
- **Features:** Output monitoring, repetition detection, rate-limit handling, JSON repair, thinking-token stripping, VRAM-aware concurrency
- **Model slots:** Embedding, Small/Fast, Coder, Large/Deep

---

## 2. CoDRAG's Integration Surfaces

### 2.1 Where Coding Agents Already Touch CoDRAG

CoDRAG is **already designed to be consumed by coding agents**. Its primary consumers are:

```
┌──────────────┐     MCP (stdio)     ┌──────────────┐
│  Antigravity │ ──────────────────→  │   CoDRAG     │
│  Claude Code │                      │   MCP Server │
│  Cursor      │                      └──────────────┘
│  Windsurf    │
│  Pi (?)      │
└──────────────┘
```

### 2.2 CLI as the Other Entry Point

CoDRAG's CLI (`codrag`) provides the same capabilities as the MCP server but via bash:
```bash
codrag search "how does auth work?" --project-id <id>
codrag context "how does auth work?" --max-chars 8000
codrag build <project-id>
codrag audit
```

### 2.3 HTTP API
The FastAPI server on `localhost:8400` serves all interfaces:
- `POST /projects/{id}/search` — semantic search
- `POST /projects/{id}/context` — context assembly
- `POST /projects/{id}/build` — trigger pipeline
- `GET /projects/{id}/trace/nodes` — graph queries

---

## 3. CoDRAG's Epistemological Model

CoDRAG's intelligence is built on layers of increasingly deep understanding:

### Layer 1: Structural (Fast)
- File discovery, AST parsing, import edge extraction
- **No LLM required** — pure static analysis via Rust

### Layer 2: Semantic (Medium)
- Embedding-based similarity search
- Chunking with boundary awareness
- LOD compression for token-efficient context

### Layer 3: Epistemic (Deep)
- LLM-generated file catalogues (purpose, role, relationships)
- Inferred edges (dynamic calls, runtime relationships)
- Confidence-weighted knowledge graph

### Layer 4: Architectural (Synthesis)
- Module clustering and synthesis
- Hub file identification (most-connected nodes)
- Codebase Atlas (narrative overview)
- Cross-session observations and memory

### The Key Insight
> CoDRAG transforms a raw codebase into a **navigable knowledge graph** with multiple levels of detail. Any coding agent that can query this graph gets significantly better at understanding code structure, making targeted changes, and predicting blast radius.

---

## 4. Where Pi Could Interface with CoDRAG

### Surface A: Pi as a CoDRAG Consumer (via CLI/bash)
Pi's philosophy aligns with using CoDRAG as CLI tools:
```bash
# Pi's agent calls CoDRAG via bash:
codrag search "authentication flow" --project-id abc123
codrag impact --file src/auth/login.py --direction dependents
```

**Pros:**
- Zero new code needed — CoDRAG CLI already exists
- Fits Pi's anti-MCP philosophy perfectly
- Progressive disclosure via README/skill file

**Cons:**
- CoDRAG daemon must be running separately
- CLI output may need formatting optimization for token efficiency

### Surface B: Pi as a CoDRAG Consumer (via MCP extension)
A Pi extension could bridge to CoDRAG's MCP server:
```
Pi Extension → MCP Client → CoDRAG MCP Server
```

**Pros:**
- Reuses existing MCP tool definitions
- Community MCP adapter for Pi exists (`pi-tidy-mcp-adapter`)

**Cons:**
- Goes against Pi's anti-MCP philosophy
- Adds 5 tool descriptions to context (~2-3k tokens)

### Surface C: CoDRAG as a Pi Skill
Create a Pi skill that wraps CoDRAG's capabilities:
```markdown
# CoDRAG Skill
Available via `/skill:codrag`

## Search Code
codrag search "query" --project-id <id>

## Impact Analysis
codrag impact --file <path> --direction dependents

## Codebase Overview
codrag context --max-chars 8000
```

**Pros:**
- Progressive disclosure (loaded only when needed)
- Minimal context overhead
- Follows Pi's established patterns

### Surface D: CoDRAG Intelligence Embedded in Pi (via SDK)
Use Pi's SDK to embed CoDRAG's Python intelligence:
- Spawn CoDRAG's FastAPI server as a sidecar
- Pi extension registers tools that call CoDRAG's HTTP API
- Full programmatic control from TypeScript

### Surface E: Pi Embedded in CoDRAG (via RPC)
CoDRAG could spawn Pi as an embedded agent:
- Pi runs as a subprocess (RPC mode over stdin/stdout)
- CoDRAG orchestrates Pi for agentic tasks
- Used for "Execute with LLM" features in the dashboard

---

## 5. Opportunity Matrix

| Integration Path | Effort | Value | Risk | Priority |
|---|---|---|---|---|
| A: CLI consumer | 🟢 Low | ⭐⭐⭐ | Low | Consider |
| B: MCP extension | 🟡 Medium | ⭐⭐ | Medium | Skip |
| C: Pi Skill | 🟢 Low | ⭐⭐⭐⭐ | Low | **Recommended** |
| D: SDK embedding | 🔴 High | ⭐⭐⭐⭐ | High | Future |
| E: Pi as sub-agent | 🟡 Medium | ⭐⭐⭐⭐⭐ | Medium | **Recommended** |

---

*Next: [03_Extensions_And_Agents.md](./03_Extensions_And_Agents.md) — Deep dive into Pi extensions, agents, and industry-standard alternatives*
