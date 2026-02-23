# Getting Started with CoDRAG

CoDRAG is a local-first semantic code search and context assembly tool that helps AI coding assistants understand your codebase.

## Prerequisites

- **Python 3.11+**
- **Ollama** (optional) — only needed if you want GPU-accelerated or code-specialized embeddings, or small/large LLM models for analysis

CoDRAG ships with a **built-in embedding model** (nomic-embed-text-v1.5, ~132 MB quantized ONNX) that downloads automatically and **runs entirely on CPU** — no GPU, no Ollama, no configuration required.

### Embedding model tiers

| Tier | Model | Size | GPU? | Notes |
|---|---|---|---|---|
| **Recommended** | `nomic-embed-code` via Ollama | ~4 GB | Required | Code-specialized, best retrieval quality |
| **Middle** | `nomic-embed-text` via Ollama | ~274 MB | Optional | General-purpose, good quality |
| **Default/Fallback** | `nomic-embed-text-v1.5` (built-in ONNX) | ~132 MB | None | CPU-only, zero-config |

See the [Embedding Models guide](./docs/Phase28_ContextWindowResearch/EMBEDDING_MODEL_RESEARCH.md) for full details.

## Installation

### 1. Install CoDRAG

```bash
pip install codrag
```

Or install from source:

```bash
git clone https://github.com/MagneticAnomaly/CoDRAG-MCP.git
cd CoDRAG
pip install -e ".[dev]"
```

### 2. (Optional) Pre-download the Built-in Embedding Model

The built-in ONNX model downloads automatically on first build (~132 MB, CPU-only). To pre-download:

```bash
codrag models
```

Model is cached at `~/.cache/huggingface/` and never re-downloaded.

### 3. (Optional) Install Ollama for GPU Embeddings or LLMs

If you have a GPU and want the best code retrieval quality, or want small/large LLM models for analysis:

```bash
# macOS
brew install ollama

# Linux
curl -fsSL https://ollama.com/install.sh | sh

# Pull embedding models (choose one based on your hardware)
ollama pull manutic/nomic-embed-code  # Recommended — code-specialized, ~4 GB, GPU required
ollama pull nomic-embed-text          # Alternative — general-purpose, ~274 MB, GPU optional

# Pull analysis models
ollama pull ministral-3:3b      # Small model for fast analysis
ollama pull ministral-3:14b     # Large model for complex reasoning
```

Then in the dashboard go to **Settings → AI Models → Embedding → Use Endpoint** and select your Ollama instance. After changing the embedding model, trigger a full rebuild.

## Quick Start

### Start the Daemon

```bash
codrag serve
```

This starts the CoDRAG daemon at `http://127.0.0.1:8400`.

### Add Your First Project

```bash
codrag add /path/to/your/repo --name "My Project"
```

### Build the Index

```bash
codrag build
```

This scans your repository, chunks the code, and creates semantic embeddings.

### Search Your Code

```bash
codrag search "how does authentication work?"
```

### Get Context for an LLM

```bash
codrag context "implement a new API endpoint" --max-chars 8000
```

## Using with AI Assistants

### MCP Integration (Recommended)

CoDRAG provides an MCP server that integrates with compatible AI assistants:

```bash
codrag mcp
```

See [MCP_ONBOARDING.md](./MCP_ONBOARDING.md) for detailed setup instructions.

### Manual Context Injection

For assistants without MCP support, use the CLI to get context:

```bash
# Get context and copy to clipboard (macOS)
codrag context "your question here" --raw | pbcopy
```

## Project Configuration

### File Filtering

Control which files are indexed:

```bash
# Include patterns (default: common code extensions)
codrag config set include_globs '["**/*.py", "**/*.ts", "**/*.md"]'

# Exclude patterns (default: .git, node_modules, etc.)
codrag config set exclude_globs '["**/node_modules/**", "**/.venv/**"]'
```

### Primer Files

Create an `AGENTS.md` file in your repository root to provide project context that's always prioritized in search results:

```markdown
# Project Context

## Tech Stack
- Python 3.10+ with FastAPI
- React 18 with TypeScript

## Key Conventions
- Use type hints everywhere
- Follow PEP 8 style guide
```

## Common Commands

| Command | Description |
|---------|-------------|
| `codrag serve` | Start the daemon |
| `codrag add <path>` | Register a project |
| `codrag build` | Build/rebuild the index |
| `codrag search <query>` | Search for code |
| `codrag context <query>` | Get assembled context |
| `codrag status` | Check project status |
| `codrag watch start` | Enable auto-rebuild on file changes |

## Dashboard (Optional)

CoDRAG includes a web dashboard for visual project management:

```bash
codrag serve --dashboard
```

Open `http://127.0.0.1:8400` in your browser.

## AI Models Configuration

CoDRAG uses up to 4 model slots, all configurable from the dashboard **Settings → AI Models** page:

| Slot | Purpose | Default |
|------|---------|--------|
| **Embedding** | Semantic search vectors | Built-in (nomic-embed-text-v1.5 via ONNX) |
| **Small** | Fast analysis & parsing | None (optional, e.g. `ministral-3:3b`) |
| **Large** | Complex reasoning & summaries | None (optional, e.g. `ministral-3:14b`) |
| **CLaRa** | 16× context compression | None (optional) |

Changing the embedding model/source requires a **full index rebuild**.

## Troubleshooting

### Ollama Connection Failed

```
Error: OLLAMA_UNAVAILABLE
```

**Solution:** Ensure Ollama is running (only needed if using Ollama-based models):
```bash
ollama serve
```

### Index Not Built

```
Error: INDEX_NOT_BUILT
```

**Solution:** Build the index first:
```bash
codrag build
```

### Large Repository Performance

For repositories with many files:

1. Increase `max_file_bytes` if needed:
   ```bash
   codrag config set max_file_bytes 500000
   ```

2. Exclude large directories:
   ```bash
   codrag config set exclude_globs '["**/vendor/**", "**/dist/**"]'
   ```

3. Use selective roots:
   ```bash
   codrag build --roots src,lib
   ```

## Next Steps

- [MCP Onboarding](./MCP_ONBOARDING.md) — Set up AI assistant integration
- [API Reference](./API.md) — HTTP API documentation
- [Error Codes](./ERROR_CODES.md) — Error handling reference
- [Budgets Policy](./BUDGETS_POLICY.md) — Understanding limits and defaults

## Getting Help

- **Issues:** [GitHub Issues](https://github.com/MagneticAnomaly/CoDRAG-MCP/issues)
- **Discussions:** [GitHub Discussions](https://github.com/MagneticAnomaly/CoDRAG-MCP/discussions)
