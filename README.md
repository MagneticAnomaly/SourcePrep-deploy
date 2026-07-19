<p align="center">
  <img src="docs/assets/prep-github-header.png" alt="SourcePrep" width="100%">
</p>

<h2 align="center"><em>Give your AI access to the epistemic context <br>it needs to understand your codebase.</em></h2>

<p align="center">
  <a href="LICENSE"><img alt="License: Apache-2.0" src="https://img.shields.io/badge/license-Apache--2.0-blue.svg"></a>
  <img alt="Python" src="https://img.shields.io/badge/python-3.11+-blue.svg">
  <img alt="Rust" src="https://img.shields.io/badge/rust-stable-orange.svg">
  <img alt="MCP" src="https://img.shields.io/badge/MCP-native-purple.svg">
</p>


**SourcePrep: prep the context before any AI call.** Epistemic trace intelligence for autonomous agents and codebase orchestration.

AI assistants are only as good as the context they receive. Most tools send fragments — a single file, a keyword match — and the model fills in the gaps with hallucinations. SourcePrep fixes this by building a **persistent, semantic index** of your entire codebase (or multiple repos) and serving bounded, source-cited context on demand.

### Core capabilities

- **Semantic search** — find code by intent, not just keywords. Results are ranked by relevance across every file in the project.
- **Code Graph** — a structural code graph (symbols, imports, call chains) so agents can reason about *how* code connects, not just *where* it lives.
- **Context assembly** — returns bounded, LLM-ready chunks with source attribution. No more "which file was that from?"
- **Role-aware context** — each AI agent gets a context view shaped for its job. A security agent sees auth and data boundaries. A UI agent sees components and design tokens. Works with any agentic framework, zero configuration.
- **MCP for AI tools** — plug into Cursor, Windsurf, Claude Code, VS Code, Gemini CLI, Qwen Code, GitHub Copilot, or JetBrains via Model Context Protocol. The agent gets the same index you do.
- **Sovereign Context** — your code never leaves your machine. The epistemic trace graph is stored securely offline.

---

## CLI + MCP Quickstart

SourcePrep is primarily used in two ways:

- **CLI**: manage projects, build indexes, search, and assemble context.
- **MCP tool/server**: expose SourcePrep capabilities to AI tools (Cursor, Windsurf, Claude Code, Gemini CLI, Qwen Code, Copilot) via the Model Context Protocol.

### CLI (daemon mode)

```bash
# 1) Start the daemon
prep serve

# 2) Register a repo
prep add /path/to/your/repo

# 3) Build the index (async)
prep build

# 4) Semantic search
prep search "authentication middleware"

# 5) Assemble LLM-ready context
prep context "explain the login flow" --raw
```

### MCP (IDE integration)

```bash
# Start MCP in server mode (connects to the running daemon)
prep mcp --auto

# Generate IDE config (prints JSON)
prep mcp-config --ide cursor
```

For the full CLI reference, see `docs/CLI.md`.

### GUI (Dashboard)

SourcePrep also ships with a **GUI dashboard** for day-to-day workflows:

- **Project visibility** (index status, staleness, trace status)
- **Build controls** and configuration editing
- **Search + preview** and **context assembly** (LLM-ready output)
- A modular layout you can tailor to your workflow

<img src="dashboard-demo.png" width="100%" alt="SourcePrep dashboard" />

```bash
# Open the dashboard in your browser
prep ui
```

## Vision

SourcePrep is an **epistemic, team-ready** application that provides:

- **Semantic code search** across multiple codebases simultaneously
- **Trace indexing** for structural understanding (symbols, imports, call graphs)
- **LLM augmentation** for intelligent summaries and context assembly
- **Unified dashboard** with project tabs, search, and visualization
- **MCP integration** for AI tools (Cursor, Windsurf, Claude Code, Gemini CLI, Qwen Code, VS Code, Copilot)

### Why SourcePrep?

| Developer Problem | SourcePrep Solution |
|---------|-----------------|
| "Managing separate RAG indexes for 5+ repos is tedious" | Single daemon manages all projects |
| "Each IDE tool spins up its own Ollama connection" | Shared LLM connection pool |
| "Juggling multiple ports/processes per project" | One port (8400), project tabs in UI |
| "Finding relevant code takes 20+ minutes for new devs" | Pre-indexed codebase with instant semantic search |
| "AI assistants forget codebase context between sessions" | Persistent trace index + structural memory |
| "Running multiple AI agents — they all get the same noisy context" | Role-aware context shaping — each agent sees only what's relevant to its job |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              Prep                                       │
├─────────────────────────────────────────────────────────────────────────┤
│  Dashboard (React/Vite → Tauri for MVP)                                 │
│  ├── Project Tabs (LinuxBrain, HalleyApp, Website, ...)                 │
│  ├── Search / Context / Trace views                                     │
│  └── Settings / LLM Status                                              │
├─────────────────────────────────────────────────────────────────────────┤   
│  HTTP API (FastAPI @ :8400)                                             │
│  ├── /projects/*           Project management                           │
│  ├── /projects/{id}/build  Index building                               │
│  ├── /projects/{id}/search Semantic search                              │
│  ├── /projects/{id}/trace  Structural queries                           │
│  └── /llm/*                LLM service status                           │
├─────────────────────────────────────────────────────────────────────────┤
│  Core Engine                                                            │
│  ├── ProjectRegistry       SQLite-backed project config                 │
│  ├── EmbeddingIndex        Semantic vector search (per project)         │
│  ├── TraceIndex            Symbol graph + import edges                  │
│  ├── FileWatcher           Auto-rebuild on changes                      │
│  └── LLMCoordinator        Ollama connection management                 │
├─────────────────────────────────────────────────────────────────────────┤
│  CLI                                                                    │
│  prep serve | add | build | search | ui | mcp                           │
└─────────────────────────────────────────────────────────────────────────┘
            │                                        │
            ▼                                        ▼
       ┌─────────┐                              ┌─────────┐
       │ Ollama  │                              │ Project │
       │ :11434  │                              │  Dirs   │
       └─────────┘                              └─────────┘
```

---

## Key Features

### Multi-Project Management
- Add multiple local codebases to single daemon
- Each project maintains isolated index data
- Switch between projects via tabs or CLI
- Cross-project search (enterprise tier only)

### Hybrid Index Mode
- **Standalone mode** (default): Index stored in `~/.local/share/sourceprep/projects/`
- **Embedded mode** (team): Index stored in project `.sourceprep/` directory
- Teams can commit embedded indexes to git to skip initial indexing time

### Code Graph
Beyond keyword/semantic search, SourcePrep builds a **structural graph**:
- **Nodes:** Files, symbols, classes, functions, endpoints
- **Edges:** Imports, calls, inheritance relationships
- Queries: Find all callers of a function, trace import chains, explore class hierarchies

### Graph Enrichment (Multi-Pass Pipeline)
The structural graph is just the skeleton. A multi-pass enrichment pipeline layers understanding on top:
- **Pass 0** — Rust parses code (tree-sitter) and docs (Markdown scanner) into a rich graph in ~100ms
- **Pass 1** — A fast 3b model catalogues every file with summaries, roles, and relationship hypotheses
- **Pass 0.5** — Rust validates the LLM's hypotheses against the graph (hallucinations discarded, confirmed edges boosted)
- **Pass 2** — A 14b model enriches each node with domain tags, architecture layer, design patterns, and cross-references
- **Pass 3** — Cluster synthesis groups files into subsystem modules with entry points and data-flow summaries
- **Pass 4+** — Continuous deepening: re-enriches nodes whose neighbors changed, converges when all epistemic scores ≥ 0.95

Each node gets an **epistemic score** (0.0–1.0) measuring how well the graph understands it. Scores decay on change, ensuring the graph stays current.

### LLM Integration
- **Embeddings:** Ollama (`nomic-embed-text-v2-moe` recommended) or native ONNX v1.5 as a zero-dependency fallback
- **Compression:** Built-in LOD (structural code compression, 3–20×, no model needed)
- **Augmentation:** Mistral/Llama (optional) for code summaries
- Reuses single Ollama connection across all indexed projects

### AGENTS.md Generation
Generate [AGENTS.md](https://agents.md/) documentation from trace index:
- Project structure with file counts and organization
- Detected entry points and key modules
- Discovered build/test commands from common files
- API endpoints extracted from route definitions
- **Role-aware context on demand** — any agent in any agentic pipeline can call `prep(role="security")` or `prep(role="design engineer")` to get a context view filtered to what matters for their specific job. No re-indexing, no extra pipeline steps.

---

## Installation

### Prerequisites
- macOS 11+ or Windows 10+
- 4GB free disk space
- Ollama (optional, for embeddings)

### Quick Start

```bash
# Download and install from sourceprep.io
# Or install via package manager:

# macOS (Homebrew)
brew install --cask prep

# Windows (winget)
winget install MagneticAnomaly.Prep

# Start the daemon
prep serve

# Add a project
prep add /path/to/your/project --name "MyProject"

# Open dashboard
prep ui
```

### With Ollama

```bash
# Install Ollama (if not installed)
curl -fsSL https://ollama.com/install.sh | sh

# Pull the recommended embedding model
ollama pull nomic-embed-text-v2-moe   # recommended (~957 MB)
# ollama pull nomic-embed-text        # lighter alternative (~274 MB)

# Prep will auto-detect Ollama at localhost:11434
# No Ollama? Run: prep models  (downloads v1.5 ONNX backup, ~132 MB)
```

---

## CLI Reference

The CLI is implemented with Typer; run `prep --help` or `prep <command> --help` for detailed help.

Full reference: `docs/CLI.md`.

### Common examples

```bash
# Start the daemon
prep serve

# Add a repo
prep add /path/to/your/repo

# Build the index (async)
prep build

# Search your codebase
prep search "authentication middleware"

# Assemble context for an LLM
prep context "explain the login flow" --raw

# IDE integration (MCP)
prep mcp --auto
```

### Full options (reference)

```bash
# Tip: most daemon-backed commands accept --host/--port (default: 127.0.0.1:8400)

# Daemon
prep serve [--host 127.0.0.1] [--port 8400] [--reload]              # Start the daemon

# Projects
prep add <path> [--name "Name"] [--mode standalone|embedded] \
  [--host 127.0.0.1] [--port 8400]                                     # Register project
prep list [--host 127.0.0.1] [--port 8400]                            # List projects
prep remove <project-id> [--purge] [--host 127.0.0.1] [--port 8400]   # Unregister project

# Index lifecycle
prep status [project-id] [--host 127.0.0.1] [--port 8400]             # Index status
prep build [project-id] [--full] [--host 127.0.0.1] [--port 8400]     # Trigger build (async)

# Retrieval
prep search "query" [--project <project-id>] [--limit 10] [--min-score 0.15] \
  [--host 127.0.0.1] [--port 8400]                                      # Semantic search
prep context "query" [--project <project-id>] [--limit 5] [--max-chars 8000] [--raw] \
  [--host 127.0.0.1] [--port 8400]                                      # Assemble context

# UI
prep ui [--port 8400]                                                 # Open dashboard

# MCP (IDE integration)
prep mcp [--mode server|direct] [--daemon http://127.0.0.1:8400] \
  [--auto] [--project <project-id>] [--repo-root <path>]                # Run MCP server (stdio)
prep mcp-config [--ide claude|cursor|windsurf|vscode|jetbrains|all] \
  [--mode auto|project|direct] [--daemon http://127.0.0.1:8400] [--project <project-id>]  # Print IDE config JSON

# Extras
prep activity [--weeks 12] [--no-legend] [--no-labels] [--json] \
  [--host 127.0.0.1] [--port 8400]                                      # Activity heatmap
prep coverage [--project <id>] [--host 127.0.0.1] [--port 8400]       # Coverage visualization
prep overview [--weeks 12] [--host 127.0.0.1] [--port 8400]            # Terminal overview dashboard
prep drift [--project <id>] [--host 127.0.0.1] [--port 8400]          # Index drift report
prep flow [--project <id>] [--host 127.0.0.1] [--port 8400]           # RAG flow visualization
prep config [key] [value] [--host 127.0.0.1] [--port 8400]            # View/modify config
prep version                                                          # Version
```

---

## Configuration

### Global Config

```yaml
# ~/.config/prep/config.yaml

# LLM Services
ollama:
  url: http://localhost:11434
  embedding_model: nomic-embed-text-v2-moe  # recommended; fallback: nomic-embed-text-v1.5 (ONNX)
  augmentation_model: mistral  # optional
  
# Index Settings
index:
  data_dir: ~/.local/share/sourceprep
  max_size_gb: 10

# Auto-Rebuild
watch:
  enabled: true
  debounce_ms: 5000

# Server
server:
  port: 8400
  host: 0.0.0.0  # for team access
```

### Per-Project Config

```yaml
# Set via CLI or dashboard
project:
  name: "LinuxBrain"
  path: LinuxBrain
  mode: standalone  # or "embedded"
  
  include:
    - "**/*.py"
    - "**/*.md"
    - "**/*.ts"
    - "**/*.tsx"
    
  exclude:
    - "**/node_modules/**"
    - "**/.venv/**"
    - "**/dist/**"
    - "**/__pycache__/**"
    
  trace:
    enabled: true
    languages: [python, typescript]
    
  auto_rebuild: true
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PREP_ENGINE` | `auto` | Selects the indexing engine: `auto` (detect best available), `rust` (faster, requires Rust build), `python` (pure Python fallback) |
| `PREP_TIER` | (from license) | Override license tier for development/testing: `free`, `starter`, `pro`, `team`, `enterprise` |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL (standard Ollama env var) |

**Example:**
```bash
# Use Python engine for debugging
PREP_ENGINE=python prep serve

# Test Pro features locally
PREP_TIER=pro prep serve
```

---

## API Reference

### Projects

```
GET  /projects                    List all projects
POST /projects                    Add new project
GET  /projects/{id}               Get project details
PUT  /projects/{id}               Update project config
DELETE /projects/{id}             Remove project
```

### Indexing

```
GET  /projects/{id}/status        Index status
POST /projects/{id}/build         Trigger build
GET  /projects/{id}/build/status  Build progress
```

### Search & Context

```
POST /projects/{id}/search        Semantic search
POST /projects/{id}/context       Assemble context for LLM
```

### Trace

```
GET  /projects/{id}/trace/status  Trace index status
POST /projects/{id}/trace/search  Symbol search
POST /projects/{id}/trace/node    Get node details
POST /projects/{id}/trace/neighbors  Graph expansion
```

### LLM

```
GET  /llm/status                  Ollama connection status
POST /llm/test                    Test connections
```

---

## Team / Enterprise Features

### Embedded Mode for Teams

```bash
# Team lead sets up project with embedded index
prep add /path/to/team-project --embedded

# Index lives in /path/to/team-project/.sourceprep/
# Commit to git:
git add .sourceprep/
git commit -m "Add Prep index"

# Team members clone and use existing index
git clone <repo>
prep add /path/to/repo --embedded  # Uses committed index, skips rebuild
# Note: Index may need refresh if codebase has changed since commit
```

### Network Mode (Enterprise)

```bash
# Run Prep server on team machine
prep serve --host 0.0.0.0 --port 8400

# Team members connect remotely (read-only access to indexes)
prep config set server.remote_url http://team-server:8400

# Search/context requests use shared server's indexes
# Note: Each client still needs local Prep installation
```

### Access Control (Roadmap)

- Project-level permissions
- API key authentication
- Audit logging

---

## Development

### Project Structure

```
Prep/
├── src/
│   └── prep/
│       ├── __init__.py
│       ├── cli.py              # CLI entry point
│       ├── server.py           # FastAPI app
│       ├── core/
│       │   ├── registry.py     # Project registry (SQLite)
│       │   ├── embedding.py    # Embedding index
│       │   ├── code-graph.py   # Code graph index
│       │   ├── watcher.py      # File watcher
│       │   └── llm.py          # LLM coordinator
│       └── api/
│           ├── projects.py     # /projects routes
│           ├── search.py       # /search routes
│           ├── code-graph.py   # /code-graph routes
│           └── llm.py          # /llm routes
├── dashboard/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/
│   │   └── pages/
│   ├── package.json
│   └── vite.config.ts
├── docs/
│   ├── ARCHITECTURE.md
│   ├── ROADMAP.md
│   └── API.md
├── tests/
├── pyproject.toml
└── README.md
```

### Running in Development

```bash
# Terminal 1: Backend
source .venv/bin/activate
uvicorn prep.server:app --reload --port 8400

# Terminal 2: Dashboard
cd dashboard
npm run dev

# Open http://localhost:5173 (Vite dev server proxies to :8400)
```

### Testing

```bash
pytest tests/
npm run test --prefix dashboard
```

---

## Roadmap

See [PHASES.md](docs/PHASES.md) for the authoritative phase index and [ROADMAP.md](docs/ROADMAP.md) for detailed phase writeups.

| Phase | Focus | Timeline |
|-------|-------|----------|
| **01: Foundation** | Core engine, CLI, basic API | |
| **02: Dashboard** | UI, project management, search/context views | |
| **03: Auto-Rebuild** | File watching, incremental builds | |
| **04: Code Graph** | Symbol extraction, graph queries | |
| **05: MCP Integration** | IDE tool support | |
| **06: Team & Enterprise** | Embedded mode + enterprise guardrails | |
| **07: Polish & Testing** | Reliability, UX, regression coverage | |
| **08: Tauri MVP** | Native app wrapper (MVP milestone) | |
| **09: Post-MVP** | Structured expansion proposals | |
| **10: Business & Competitive Research** | Pricing, positioning, licensing | |
| **11: Deployment** | Packaging, distribution, updates | |
| **12: Marketing / Docs / Website** | Documentation + public-facing assets | |
| **13: Storybook** | Design system + UI component library | |

---

## Related Projects

- **[Ollama](https://ollama.com/)** — Local LLM serving (SourcePrep uses for embeddings)
- **[Model Context Protocol](https://modelcontextprotocol.io)** — The standard SourcePrep speaks natively

---

## License

SourcePrep is free and open source software, licensed under the
**Apache License 2.0**. See [LICENSE](LICENSE) for the full text. The
[NOTICE](NOTICE) file lists third-party attributions.

Contributions are welcome. By submitting a contribution you agree to the
[Developer Certificate of Origin](https://developercertificate.org/) — certify
your commits with `git commit -s`. See [CONTRIBUTING.md](CONTRIBUTING.md) for
how to get started, and [SECURITY.md](SECURITY.md) for vulnerability reporting.

