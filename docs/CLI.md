# CoDRAG CLI Reference

The CoDRAG command-line interface provides complete control over project management, indexing, semantic search, and IDE integration.

## Installation

```bash
# Install from source (development)
pip install -e .

# Or install from PyPI (when published)
pip install codrag
```

After installation, the `codrag` command is available globally.

---

## Quick Start

```bash
# 1. Start the daemon
codrag serve

# 2. Add a project (in another terminal)
codrag add /path/to/your/repo

# 3. Build the index
codrag build

# 4. Search your codebase
codrag search "authentication middleware"

# 5. Get context for LLM prompts
codrag context "how does the login flow work"
```

---

## Global Options

All commands that interact with the daemon accept these options:

| Option | Default | Description |
|--------|---------|-------------|
| `--host` | `127.0.0.1` | Server host address |
| `--port` | `8400` | Server port |

---

## Commands

### `codrag serve`

Start the CoDRAG daemon server.

```bash
codrag serve [OPTIONS]
```

**Options:**

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--host` | `-h` | `127.0.0.1` | Host to bind to |
| `--port` | `-p` | `8400` | Port to bind to |
| `--reload` | | `false` | Enable auto-reload for development |

**Examples:**

```bash
# Start on default port
codrag serve

# Start on custom port
codrag serve --port 9000

# Development mode with auto-reload
codrag serve --reload
```

---

### `codrag add`

Register a new project with the daemon.

```bash
codrag add PATH [OPTIONS]
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `PATH` | Yes | Path to project root directory |

**Options:**

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--name` | `-n` | folder name | Custom project name |
| `--mode` | `-m` | `standalone` | Index mode: `standalone` (global data dir) or `embedded` (.codrag in repo) |

**Examples:**

```bash
# Add project with auto-detected name
codrag add /path/to/myproject

# Add with custom name
codrag add /path/to/myproject --name "My Awesome Project"

# Use embedded mode (stores index in .prep/ within repo)
codrag add /path/to/myproject --mode embedded
```

**Notes:**
- Adding a project does NOT automatically build the index
- Run `codrag build` after adding to create the index
- Embedded mode is useful for sharing index config via version control

---

### `codrag list`

List all registered projects.

```bash
codrag list [OPTIONS]
```

**Output columns:**
- **ID** - Unique project identifier
- **Name** - Project display name
- **Path** - Filesystem path
- **Mode** - `standalone` or `embedded`
- **Created** - Registration timestamp

**Example output:**

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CoDRAG Projects                             │
├──────────┬─────────────┬────────────────────────┬────────┬──────────┤
│ ID       │ Name        │ Path                   │ Mode   │ Created  │
├──────────┼─────────────┼────────────────────────┼────────┼──────────┤
│ abc123   │ my-app      │ /Users/dev/my-app      │ standalone │ 2024-01-15 │
│ def456   │ backend     │ /Users/dev/backend     │ embedded   │ 2024-01-16 │
└──────────┴─────────────┴────────────────────────┴────────┴──────────┘
```

---

### `codrag remove`

Unregister a project from the daemon.

```bash
codrag remove PROJECT_ID [OPTIONS]
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `PROJECT_ID` | Yes | Project ID to remove |

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--purge` | `false` | Also delete the index data from disk |

**Examples:**

```bash
# Unregister project (keeps index files)
codrag remove abc123

# Unregister and delete all index data
codrag remove abc123 --purge
```

---

### `codrag status`

Show index status for a project.

```bash
codrag status [PROJECT_ID] [OPTIONS]
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `PROJECT_ID` | No | Project ID (auto-detected if inside project directory) |

**Output includes:**
- Embeddings index status (chunks, model, last build)
- Trace index status (nodes, edges)
- Build progress if in progress

**Example output:**

```
╭─────────────────────────────────╮
│ Project Status: abc123          │
╰─────────────────────────────────╯
● Embeddings Index: Ready
  Chunks: 4,521
  Model: all-MiniLM-L6-v2
  Last Build: 2024-01-15 14:30:00

● Trace Index: Ready
  Nodes: 892
  Edges: 2,341
```

---

### `codrag build`

Trigger an index build for a project.

```bash
codrag build [PROJECT_ID] [OPTIONS]
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `PROJECT_ID` | No | Project ID (auto-detected if inside project directory) |

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--full` | `false` | Force full rebuild (ignore incremental cache) |

**Examples:**

```bash
# Incremental build (only changed files)
codrag build

# Full rebuild from scratch
codrag build --full

# Build specific project
codrag build abc123
```

**Notes:**
- Builds run asynchronously in the background
- Use `codrag status` to monitor progress
- Incremental builds are much faster for large codebases

---

### `codrag search`

Semantic search across the codebase.

```bash
codrag search QUERY [OPTIONS]
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `QUERY` | Yes | Natural language search query |

**Options:**

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--project` | `-p` | auto | Project ID |
| `--limit` | `-k` | `10` | Number of results to return |
| `--min-score` | `-s` | `0.15` | Minimum similarity score (0-1) |

**Examples:**

```bash
# Basic search
codrag search "authentication middleware"

# Get more results
codrag search "error handling" --limit 20

# Higher precision (fewer but more relevant results)
codrag search "database connection" --min-score 0.5

# Search specific project
codrag search "API routes" --project abc123
```

**Example output:**

```
Found 5 results for 'authentication middleware':

1. src/auth/middleware.py:15-45 (score: 0.892)
   def authenticate_request(request): ...

2. src/api/routes.py:102-130 (score: 0.756)
   @app.middleware("http") async def auth_middleware...

3. docs/AUTH.md:1-50 (score: 0.623)
   # Authentication Guide ...
```

---

### `codrag context`

Assemble context for LLM prompts.

```bash
codrag context QUERY [OPTIONS]
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `QUERY` | Yes | Query to assemble context for |

**Options:**

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--project` | `-p` | auto | Project ID |
| `--limit` | `-k` | `5` | Number of chunks to include |
| `--max-chars` | `-c` | `8000` | Maximum characters in context |
| `--raw` | `-r` | `false` | Output only raw context (for piping) |

**Examples:**

```bash
# Get formatted context with stats
codrag context "how does the login flow work"

# Raw output for piping to LLM
codrag context "explain the database schema" --raw

# Larger context window
codrag context "summarize the API" --max-chars 16000 --limit 10
```

**Example output:**

```
╭─────────────────────────────────────────────╮
│ Context Assembly Stats                       │
│ Chunks: 5 | Chars: 4,521 | Est. Tokens: 1,130│
╰─────────────────────────────────────────────╯

--- src/auth/login.py:1-50 ---
def login(username: str, password: str):
    """Authenticate user and return JWT token."""
    ...

--- src/models/user.py:10-40 ---
class User(BaseModel):
    ...
```

**Piping to LLM:**

```bash
# Use with OpenAI CLI
codrag context "explain authentication" --raw | \
  openai api chat.completions.create \
    -m gpt-4 \
    -g user "Based on this code context, explain the authentication flow"
```

---

### `codrag ui`

Open the CoDRAG web dashboard in your browser.

```bash
codrag ui [OPTIONS]
```

**Options:**

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--port` | `-p` | `8400` | Dashboard port |

---

### `codrag mcp`

Run the Model Context Protocol (MCP) server for IDE integration.

```bash
codrag mcp [OPTIONS]
```

**Options:**

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--project` | `-p` | none | Pinned project ID |
| `--auto` | `-a` | `false` | Auto-detect project from CWD |
| `--mode` | `-m` | `server` | Mode: `server` or `direct` |
| `--daemon` | `-d` | `http://127.0.0.1:8400` | CoDRAG daemon URL |
| `--repo-root` | `-r` | CWD | Repository root (direct mode) |
| `--debug` |  | `false` | Enable debug logging (stderr) |
| `--log-file` |  | none | Write MCP debug logs to a file (rotating) |

**Modes:**

- **server** (default): Connects to running CoDRAG daemon
- **direct**: Runs CoDRAG engine in-process (no daemon required)

**Examples:**

```bash
# Server mode (requires daemon running)
codrag mcp

# Auto-detect project based on working directory
codrag mcp --auto

# Pin to specific project
codrag mcp --project abc123

# Direct mode (standalone, no daemon)
codrag mcp --mode direct --repo-root /path/to/repo
```

---

### `codrag mcp-config`

Generate MCP configuration for IDE integration.

```bash
codrag mcp-config [OPTIONS]
```

**Options:**

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--ide` | `-i` | `all` | Target IDE: `claude`, `cursor`, `windsurf`, `vscode`, `jetbrains`, `all` |
| `--mode` | `-m` | `auto` | Mode: `auto`, `project`, `direct` |
| `--daemon` | `-d` | `http://127.0.0.1:8400` | CoDRAG daemon URL |
| `--project` | `-p` | none | Project ID (required when `--mode project`) |

**Examples:**

```bash
# Generate config for all IDEs
codrag mcp-config

# Generate for specific IDE
codrag mcp-config --ide cursor

# Direct mode (no daemon)
codrag mcp-config --mode direct --ide cursor

# Pin to specific project
codrag mcp-config --mode project --project abc123 --ide cursor
```

**Example output (Claude Desktop):**

```json
{
  "mcpServers": {
    "codrag": {
      "command": "codrag",
      "args": ["mcp", "--auto", "--daemon", "http://127.0.0.1:8400"]
    }
  }
}
```

---

### `codrag version`

Show version information.

```bash
codrag version
```

---

### `codrag activity`

Show index activity heatmap (GitHub-style contribution graph).

```bash
codrag activity [OPTIONS]
```

**Options:**

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--weeks` | `-w` | `12` | Number of weeks to display |
| `--no-legend` | | `false` | Hide color legend |
| `--no-labels` | | `false` | Hide day/month labels |
| `--json` | `-j` | `false` | Output raw JSON data |

---

### `codrag coverage`

Show file tree coverage visualization.

```bash
codrag coverage [OPTIONS]
```

Shows which files are indexed vs excluded with a visual tree representation.

---

### `codrag overview`

Show comprehensive dashboard overview in terminal.

```bash
codrag overview [OPTIONS]
```

**Options:**

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--weeks` | `-w` | `12` | Number of weeks for activity |

Combines health stats, activity heatmap, and trace statistics.

---

### `codrag drift`

Show index drift report (stale files, freshness metrics).

```bash
codrag drift [OPTIONS]
```

**Options:**

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--project` | `-p` | auto | Project ID |

Shows which files have drifted since the last index build.

---

### `codrag flow`

Show RAG flow visualization (query → retrieval → context).

```bash
codrag flow [OPTIONS]
```

**Options:**

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--project` | `-p` | auto | Project ID |

Visualizes the RAG pipeline: embedding, search, context assembly.

---

### `codrag config`

View or modify CoDRAG configuration.

```bash
codrag config [KEY] [VALUE] [OPTIONS]
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `KEY` | No | Config key (dot-notation, e.g. `llm_config.embedding.source`) |
| `VALUE` | No | Value to set |

**Examples:**

```bash
# Show full config
codrag config

# Get specific key
codrag config llm_config.embedding.source

# Set specific key
codrag config llm_config.embedding.source huggingface
```

---

## Project Resolution

Many commands accept an optional `PROJECT_ID` argument. When omitted, CoDRAG resolves the project automatically:

1. **CWD matching**: If you're inside a registered project directory, that project is used
2. **Single project**: If only one project is registered, it's used automatically
3. **Ambiguous**: If multiple projects exist and CWD doesn't match, you must specify `--project`

**Example:**

```bash
# Inside /Users/dev/my-app (registered project)
cd /Users/dev/my-app
codrag build        # Builds my-app automatically

# Outside any project
cd /tmp
codrag build abc123 # Must specify project ID
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CODRAG_HOST` | `127.0.0.1` | Default server host |
| `CODRAG_PORT` | `8400` | Default server port |
| `CODRAG_DATA_DIR` | `~/.local/share/prep` | Data directory for standalone indexes |
| `CODRAG_ENGINE` | `auto` | Indexing engine: `auto`, `rust`, or `python` |
| `CODRAG_TIER` | (from license) | Override license tier: `free`, `starter`, `pro`, `team`, `enterprise` |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL (standard Ollama env var) |

**Examples:**

```bash
# Use Python engine for debugging
CODRAG_ENGINE=python codrag serve

# Test Pro features locally
CODRAG_TIER=pro codrag serve

# Use custom Ollama server
OLLAMA_HOST=http://192.168.1.100:11434 codrag serve
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | General error (connection failed, invalid input, etc.) |

---

## Common Workflows

### Initial Setup

```bash
# Start daemon in background
codrag serve &

# Add your projects
codrag add ~/projects/frontend --name "Frontend App"
codrag add ~/projects/backend --name "Backend API"

# Build indexes
codrag build --project frontend
codrag build --project backend
```

### Daily Development

```bash
# Quick search
codrag search "payment processing"

# Get context for code review
codrag context "explain the order validation logic" --raw > context.txt

# Check index freshness
codrag status
```

### IDE Integration

```bash
# Generate config and add to your IDE
codrag mcp-config --ide cursor

# Copy the JSON to your IDE's MCP configuration file
```

---

## Troubleshooting

### "Cannot connect to CoDRAG daemon"

The daemon isn't running. Start it with:

```bash
codrag serve
```

### "No projects found"

Register a project first:

```bash
codrag add /path/to/your/project
```

### "Multiple projects available"

Specify the project explicitly or run the command from within the project directory:

```bash
# Option 1: Specify project
codrag search "query" --project abc123

# Option 2: Run from project directory
cd /path/to/project
codrag search "query"
```

### "Index not ready"

Build the index first:

```bash
codrag build
```

Wait for the build to complete (check with `codrag status`).

---

## See Also

- [API Documentation](./API.md)
- [Architecture Overview](./ARCHITECTURE.md)
- [MCP Integration Guide](./MCP.md)
