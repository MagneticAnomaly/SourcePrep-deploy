# Prep API Specification

This document is the **authoritative** HTTP API contract for the Prep daemon.

## Conventions

- **Base URL (default):** `http://127.0.0.1:8400`
- **Content-Type:** `application/json`
- **Local-first:** in default local mode the daemon binds to loopback and requires no auth.
- **Project-scoped API:** most endpoints are under `/projects/{project_id}/...`.
- **Code Graph** — a structural code graph (symbols, imports, call chains) so agents can reason about *how* code connects, not just *where* it lives.

## Authentication (Phase 06)

Local-only mode (default):
- Authentication is optional.

Network/team mode:
- Authentication is required for all endpoints except `GET /health`.
- Recommended header:
  - `Authorization: Bearer <api_key>`

## Response envelope

All JSON endpoints return a stable envelope.

### Success

```json
{
  "success": true,
  "data": {"...": "..."},
  "error": null
}
```

### Error

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "PROJECT_NOT_FOUND",
    "message": "Project with ID 'xyz' not found",
    "hint": "Add the project first or select an existing project.",
    "details": {}
  }
}
```

Notes:
- `hint` and `details` are optional but recommended.
- In remote mode, error details must not leak sensitive filesystem paths.

## HTTP status codes

- `200` for successful reads/actions.
- `400` for validation errors.
- `401` for auth failures (network mode).
- `404` for missing resources.
- `403` for feature-gated actions (upgrade required).
- `409` for conflicts (already exists, build already running).
- `500` for internal errors.

The envelope is returned even when non-200 status codes are used.

## Error codes

Minimum stable set:

- `VALIDATION_ERROR`
- `PROJECT_NOT_FOUND`
- `PROJECT_ALREADY_EXISTS`
- `INDEX_NOT_BUILT`
- `BUILD_ALREADY_RUNNING`
- `BUILD_FAILED`
- `OLLAMA_UNAVAILABLE`
- `OLLAMA_MODEL_NOT_FOUND`
- `PERMISSION_DENIED`
- `IO_ERROR`
- `NOT_IMPLEMENTED`
- `INTERNAL_ERROR`

Phase 05 (MCP) adds:
- `DAEMON_UNAVAILABLE`
- `PROJECT_SELECTION_AMBIGUOUS`

Phase 11 (Tier Enforcement) adds:
- `FEATURE_GATED` — returned with HTTP 403 when a feature requires a higher tier.
  Includes `hint` (upgrade URL) and `details.feature`, `details.current_tier`, `details.required_tier`.

## Pagination

List endpoints that can grow should support offset/limit.

Recommended envelope payload shape:

```json
{
  "success": true,
  "data": {
    "items": [],
    "total": 0,
    "offset": 0,
    "limit": 50
  },
  "error": null
}
```

## Endpoints

### Health

#### `GET /health`

Purpose:
- Liveness/readiness probe.

Response (no envelope; stable for external probes):

```json
{
  "status": "ok",
  "version": "0.1.0"
}
```

### Root

#### `GET /`

Purpose:
- Human-friendly API info.

Response:

```json
{
  "name": "Prep",
  "version": "0.1.0",
  "description": "Code Documentation and RAG",
  "docs": "/docs",
  "health": "/health"
}
```

### Projects

#### `GET /projects`

Purpose:
- List registered projects.

Response `data`:

```json
{
  "projects": [
    {
      "id": "proj_123",
      "name": "LinuxBrain",
      "path": "/abs/path/to/repo",
      "mode": "standalone",
      "created_at": "2026-01-01T00:00:00Z",
      "updated_at": "2026-01-01T00:00:00Z"
    }
  ],
  "total": 1
}
```

#### `POST /projects`

Purpose:
- Register a new project.

Request:

```json
{
  "path": "/abs/path/to/repo",
  "name": "optional name",
  "mode": "standalone"
}
```

Notes:
- `mode` is `standalone` by default.
- `embedded` becomes first-class in Phase 06.

Response `data`:

```json
{
  "project": {
    "id": "proj_123",
    "name": "LinuxBrain",
    "path": "/abs/path/to/repo",
    "mode": "standalone",
    "config": {}
  }
}
```

#### `GET /projects/{project_id}`

Purpose:
- Fetch project details.

Response `data`:

```json
{
  "project": {
    "id": "proj_123",
    "name": "LinuxBrain",
    "path": "/abs/path/to/repo",
    "mode": "standalone",
    "config": {}
  }
}
```

#### `PUT /projects/{project_id}`

Purpose:
- Update project metadata/config.

Request:

```json
{
  "name": "optional new name",
  "config": {
    "include_globs": ["**/*.py", "**/*.md"],
    "exclude_globs": ["**/node_modules/**"],
    "max_file_bytes": 200000,
    "trace": {"enabled": false},
    "auto_rebuild": {"enabled": false}
  }
}
```

Response `data`:

```json
{
  "project": {"id": "proj_123", "name": "...", "path": "...", "mode": "standalone", "config": {}}
}
```

#### `DELETE /projects/{project_id}?purge=false`

Purpose:
- Remove a project from the registry.

Query params:
- `purge`:
  - `false` (default): unregister only
  - `true`: also delete project index files

Response `data`:

```json
{
  "removed": true,
  "purged": false
}
```

#### `DELETE /projects/{project_id}/trace/destroy`

Purpose:
- Permanently delete all trace graph data for a project.
- Removes: structural graph, augmentation, inferred edges, epistemic enrichment, cluster modules.
- Embeddings and search index remain intact.

Fails with `409 PIPELINE_RUNNING` if any pipeline stage is active.

CLI equivalent: `prep reset-graph`

Response `data`:

```json
{
  "deleted": ["trace_nodes.jsonl", "trace_edges.jsonl", "..."],
  "errors": []
}
```

#### `DELETE /projects/{project_id}/index/destroy`

Purpose:
- **Full reset**: permanently delete ALL project data.
- Removes: embeddings, search index (FTS), trace graph, all enrichment, and knowledge index.
- Project registration remains — you will need to rebuild from scratch.

Fails with `409 PIPELINE_RUNNING` if any pipeline stage or index build is active.

CLI equivalent: `prep reset`

Response `data`:

```json
{
  "deleted": ["documents.json", "embeddings.npy", "trace_nodes.jsonl", "..."],
  "errors": []
}
```

### Project status and build

#### `GET /projects/{project_id}/status`

Purpose:
- Provide a stable “truth” view for UI/CLI/MCP.

Response `data`:

```json
{
  "building": false,
  "stale": false,
  "index": {
    "exists": true,
    "total_chunks": 1234,
    "embedding_dim": 768,
    "embedding_model": "nomic-embed-text",
    "last_build_at": "2026-01-01T00:00:00Z",
    "last_error": null
  },
  "trace": {
    "enabled": false,
    "exists": false,
    "building": false,
    "counts": {"nodes": 0, "edges": 0},
    "last_build_at": null,
    "last_error": null
  },
  "watch": {
    "enabled": false,
    "state": "disabled"
  }
}
```

#### `POST /projects/{project_id}/build?full=false`

Purpose:
- Trigger a build.

Query params:
- `full`:
  - `false` (default): incremental build
  - `true`: full rebuild

Response `data`:

```json
{
  "started": true,
  "building": true,
  "build_id": "build_abc"
}
```

Progress reporting (recommended):
- Expose the current phase and coarse counters in `GET /projects/{project_id}/status`.

### Search

#### `POST /projects/{project_id}/search`

Request:

```json
{
  "query": "how does auth work?",
  "k": 10,
  "min_score": 0.15
}
```

Response `data`:

```json
{
  "results": [
    {
      "chunk_id": "chunk_...",
      "source_path": "src/prep/server.py",
      "span": {"start_line": 142, "end_line": 175},
      "preview": "Trigger project index build...",
      "score": 0.83
    }
  ]
}
```

### Context assembly

#### `POST /projects/{project_id}/context`

Request:

```json
{
  "query": "how does auth work?",
  "k": 5,
  "max_chars": 8000,
  "min_score": 0.15,
  "include_sources": true,
  "include_scores": false,
  "structured": false,
  "trace_expand": {
    "enabled": false,
    "hops": 1,
    "direction": "both",
    "edge_kinds": ["imports"],
    "max_nodes": 20,
    "max_additional_chunks": 10,
    "max_additional_chars": 2000
  }
}
```

Response `data` when `structured=false`:

```json
{
  "context": "..."
}
```

Response `data` when `structured=true`:

```json
{
  "context": "...",
  "chunks": [
    {
      "chunk_id": "chunk_...",
      "source_path": "...",
      "span": {"start_line": 1, "end_line": 10},
      "score": 0.83,
      "text": "..."
    }
  ],
  "total_chars": 7123,
  "estimated_tokens": 1800
}
```

### Code Graph (Phase 04)

#### `GET /projects/{project_id}/trace/status`

Response `data`:

```json
{
  "enabled": false,
  "exists": false,
  "building": false,
  "counts": {"nodes": 0, "edges": 0},
  "last_build_at": null,
  "last_error": null
}
```

#### `POST /projects/{project_id}/trace/search`

Request:

```json
{
  "query": "build_project",
  "kinds": ["symbol"],
  "limit": 20
}
```

Response `data`:

```json
{
  "nodes": [
    {
      "id": "node-...",
      "kind": "symbol",
      "name": "build_project",
      "file_path": "src/prep/server.py",
      "span": {"start_line": 142, "end_line": 175},
      "language": "python",
      "preview": "Trigger project index build..."
    }
  ]
}
```

#### `GET /projects/{project_id}/trace/node/{node_id}`

Response `data`:

```json
{
  "node": {"id": "node-...", "kind": "symbol", "name": "..."},
  "in_degree": 0,
  "out_degree": 2
}
```

#### `GET /projects/{project_id}/trace/neighbors/{node_id}`

Query params:
- `direction`: `in|out|both` (default `both`)
- `edge_kinds`: repeatable (default `imports`)
- `hops`: default 1
- `max_nodes`: default 25
- `max_edges`: default 50

Response `data`:

```json
{
  "nodes": [{"id": "node-...", "kind": "file", "name": "..."}],
  "edges": [{"id": "edge-...", "kind": "imports", "source": "node-...", "target": "node-..."}]
}
```

### License & Tier

#### `GET /license`

Purpose:
- Get current license tier and feature availability.

Response `data`:

```json
{
  "license": {
    "tier": "free",
    "valid": true,
    "email": null,
    "expires_at": null,
    "seats": 1,
    "features": []
  },
  "features": {
    "auto_rebuild": false,
    { category: 'Indexing & Search', name: 'Structural Code Graph (imports, calls, symbol graphs)', free: false, pro: true },
    "mcp_tools": true,
    "mcp_trace_expand": false,
    "path_weights": true,
    "multi_repo_agent": false,
    "team_config": false,
    "audit_log": false,
    "projects_max": 1
  }
}
```

Notes:
- `tier` is one of: `free`, `monthly`, `perpetual`, `team`, `enterprise`.
- `features` map shows boolean availability for each gated feature at current tier.
- `projects_max` is a numeric limit (1 for free, 999 for monthly/perpetual+).

#### `POST /license/activate`

Purpose:
- Save/activate a license key on this machine.

Request:

```json
{
  "key": "..."
}
```

Response `data`:
- Same shape as `GET /license`.

#### `POST /license/deactivate`

Purpose:
- Remove the locally stored license on this machine (reverts to Free tier behavior).

Response `data`:
- Same shape as `GET /license`.

### MCP Tools

The Prep MCP server exposes the following tools via the Model Context Protocol:

| Tool | Required Params | Description |
|------|----------------|-------------|
| `prep_status` | — | Index status and daemon health |
| `prep_build` | — | Trigger async index build |
| `prep_search` | `query` | Semantic search, returns ranked chunks |
| `prep` | `query` | Assembled context for LLM prompt injection |
| `prep_trace_search` | `query` | Search code graph for symbols |
| `prep_trace_neighbors` | `node_id` | Get neighbors in code graph |
| `prep_trace_coverage` | — | Trace coverage statistics |
| `hi_prep` | — | Project overview, health check, and suggested prompts |

All tools accept an optional `project_id` parameter. If omitted, the project is auto-detected from workspace roots or CWD.

#### `hi_prep` — Project Overview Tool

Purpose:
- First-contact tool for new users: "What can Prep help me with?"
- Developer diagnostic: quick sanity check of project state after changes.
- Returns a markdown summary + structured diagnostics JSON.

Parameters:
- `project_id` (optional): Prep project ID to target.

Response:
```json
{
  "summary": "# Prep — my-app\n\n**Status:** Index loaded (847 chunks)...\n**Suggested prompts:**\n1. \"How is my-app structured?\"...",
  "diagnostics": {
    "project_id": "proj_abc",
    "project_name": "my-app",
    "index_loaded": true,
    "total_chunks": 847,
    "building": false,
    "stale": false,
    "stale_count": 0,
    "trace_enabled": true,
    "trace_nodes": 523,
    "trace_edges": 641,
    "trace_coverage_pct": 80,
    "watch_enabled": true,
    "included_paths_count": 120,
    "path_weights": {},
    "other_projects": ["backend-api"]
  }
}
```

The `summary` field contains markdown suitable for direct display in IDE chat. The `diagnostics` field provides structured data for programmatic use.

### MCP / IDE Integration

#### `GET /api/code-index/mcp-config`

Purpose:
- Generate copy/paste MCP configuration for IDE setup.

Query params:
- `ide`: `cursor | windsurf | vscode | jetbrains | claude | all`
- `mode`: `direct | auto | project`
- `daemon_url`: optional override for the daemon URL included in generated configs
- `project_id`: required when `mode=project`

Response `data` (single IDE):

```json
{
  "daemon_url": "http://127.0.0.1:8400",
  "file": ".cursor/mcp.json",
  "path_hint": "Project root or ~/.cursor/",
  "config": {"mcpServers": {"prep": {"command": "prep", "args": ["mcp", "--auto", "--daemon", "http://127.0.0.1:8400"]}}}
}
```

Response `data` (`ide=all`):

```json
{
  "daemon_url": "http://127.0.0.1:8400",
  "configs": {
    "cursor": {"file": ".cursor/mcp.json", "path_hint": "...", "config": {}},
    "vscode": {"file": ".vscode/mcp.json", "path_hint": "...", "config": {}}
  }
}
```

### File watcher (auto-rebuild)

#### `POST /projects/{project_id}/watch/start`

Purpose:
- Enable auto-rebuild file watcher for a project.
- **Requires MONTHLY+ tier** (gated by `auto_rebuild` feature).

Query params:
- `debounce_ms`: debounce delay in ms (default 5000, range 500-60000)
- `min_gap_ms`: minimum gap between rebuilds in ms (default 2000, range 500-30000)

Response `data`:

```json
{
  "enabled": true,
  "status": {
    "enabled": true,
    "state": "idle",
    "debounce_ms": 5000,
    "stale": false,
    "pending": false,
    "pending_paths_count": 0
  }
}
```

Notes:
- When file changes are detected, watcher triggers both index and trace rebuilds (if trace enabled).
- Watcher uses project config for include/exclude globs.

#### `POST /projects/{project_id}/watch/stop`

Purpose:
- Disable file watcher.

Response `data`:

```json
{
  "enabled": false
}
```

#### `GET /projects/{project_id}/watch/status`

Purpose:
- Get watcher status.

Response `data`:

```json
{
  "enabled": true,
  "state": "idle",
  "debounce_ms": 5000,
  "stale": false,
  "stale_since": null,
  "pending": false,
  "pending_paths_count": 0,
  "next_rebuild_at": null,
  "last_event_at": null,
  "last_rebuild_at": null
}
```

### Path weights

#### `GET /projects/{project_id}/path_weights`

Purpose:
- Get user-defined path weight multipliers.

Response `data`:

```json
{
  "path_weights": {
    "src/core/": 1.5,
    "docs/": 0.5
  }
}
```

#### `PUT /projects/{project_id}/path_weights`

Purpose:
- Update path weight multipliers (0.0–2.0 range, clamped).

Request:

```json
{
  "path_weights": {
    "src/core/": 1.5,
    "docs/": 0.5
  }
}
```

### Included paths (Knowledge Scope)

#### `GET /projects/{project_id}/included_paths`

Purpose:
- Get the list of files/folders the user has selected in the Knowledge Scope (file tree).

Response `data`:

```json
{
  "included_paths": ["src", "docs/README.md", "tests/test_main.py"]
}
```

Notes:
- Empty list means no scope restriction (all files matching globs are indexed).
- Paths are relative to project root.
- Persisted in SQLite project config — survives browser clear, works across clients.

#### `PUT /projects/{project_id}/included_paths`

Purpose:
- Set the full list of included paths (replaces previous selection).

Request:

```json
{
  "included_paths": ["src", "docs/README.md"]
}
```

Response `data`:

```json
{
  "project": {"id": "proj_123", "...": "..."},
  "included_paths": ["docs/README.md", "src"]
}
```

Notes:
- Paths are deduplicated and sorted.
- Empty strings are filtered out.
- Used by the dashboard to sync the canonical scope to the server.

### Knowledge Scope pipeline

#### `GET /projects/{project_id}/scope/status`

Purpose:
- Get the Knowledge Scope pipeline status (debounce state, pending changes, included paths).

Response `data`:

```json
{
  "state": "idle",
  "pending_adds": 0,
  "pending_removes": 0,
  "pending_changes": 0,
  "total_pending": 0,
  "auto_rebuild": true,
  "debounce_ms": 3000,
  "error": null,
  "last_rebuild_at": null,
  "stale_since": null,
  "is_stale": false,
  "included_paths": ["src", "docs/README.md"]
}
```

Notes:
- `state` is one of: `idle`, `debouncing`, `building`, `failed`, `stale`.
- `included_paths` is the canonical persisted set from project config.
- `auto_rebuild` is `true` for Pro tier, `false` for Free (manual rebuild via `/scope/rebuild`).

#### `POST /projects/{project_id}/scope/add`

Purpose:
- Add files/folders to the Knowledge Scope.
- Persists the updated `included_paths` set to project config.
- Triggers a debounced CodeIndex rebuild (Pro) or marks as stale (Free).

Request:

```json
{
  "paths": ["src/core", "docs/API.md"]
}
```

Response `data`:

```json
{
  "added": 2,
  "included_paths": ["docs/API.md", "src", "src/core"],
  "status": {"state": "debouncing", "...": "..."}
}
```

Notes:
- Adding a parent folder automatically removes explicit children from the set.

#### `POST /projects/{project_id}/scope/remove`

Purpose:
- Remove files/folders from the Knowledge Scope.
- Persists the updated `included_paths` set to project config.
- Triggers a debounced CodeIndex rebuild (Pro) or marks as stale (Free).

Request:

```json
{
  "paths": ["docs/API.md"]
}
```

Response `data`:

```json
{
  "removed": 1,
  "included_paths": ["src"],
  "status": {"state": "debouncing", "...": "..."}
}
```

Notes:
- Removing a path also removes all descendants.

#### `POST /projects/{project_id}/scope/rebuild`

Purpose:
- Manually trigger a Knowledge Scope rebuild (for Free-tier or force rebuild).

Response `data`:

```json
{
  "started": true,
  "status": {"state": "building", "...": "..."}
}
```

Errors:
- `409 SCOPE_ALREADY_BUILDING` — rebuild already in progress.
- `409 NO_PENDING_CHANGES` — nothing to rebuild.

### Code Graph (Phase 04) — additional endpoints

#### `POST /projects/{project_id}/trace/build`

Purpose:
- Trigger trace index build.

Response `data`:

```json
{
  "started": true,
  "building": true
}
```

#### `GET /projects/{project_id}/trace/coverage`

Purpose:
- Get trace coverage statistics (traced, untraced, stale, ignored files).

Response `data`:

```json
{
  "summary": {
    "total_files": 42,
    "traced_files": 35,
    "untraced_files": 5,
    "stale_files": 2,
    "ignored_files": 0,
    "coverage_pct": 83.3
  },
  "untraced": [{"path": "...", "language": "python", "size": 1234}],
  "stale": [{"path": "...", "language": "python", "size": 1234}],
  "ignored": []
}
```

#### `POST /projects/{project_id}/trace/ignore`

Purpose:
- Add or remove trace-specific ignore patterns.

Request:

```json
{
  "action": "add",
  "patterns": ["tests/**", "*_test.py"]
}
```

### Activity & Coverage

#### `GET /projects/{project_id}/activity`

Purpose:
- Get activity heatmap data for the project.

Response `data`:

```json
{
  "activity": []
}
```

Notes:
- Returns activity data for visualization in the dashboard heatmap panel.

#### `GET /projects/{project_id}/coverage`

Purpose:
- Get index coverage statistics for the project.

Response `data`:

```json
{
  "summary": {
    "total_files": 100,
    "indexed_files": 85,
    "pending_files": 10,
    "ignored_files": 5,
    "coverage_pct": 85.0
  },
  "tree": []
}
```

### Files & roots

#### `GET /projects/{project_id}/roots`

Purpose:
- Get working roots for the project.

Response `data`:

```json
{
  "roots": ["/abs/path/to/repo"]
}
```

#### `GET /projects/{project_id}/files`

Purpose:
- Get file tree for the project.

Query params:
- `path`: subdirectory path (default: project root)
- `depth`: max depth (default 3)

Response `data`:

```json
{
  "path": "/abs/path",
  "tree": [
    {"name": "src", "type": "folder", "children": []},
    {"name": "README.md", "type": "file"}
  ]
}
```

#### `GET /projects/{project_id}/file`

Purpose:
- Get content of a single file (repo-root-relative path).

Query params:
- `path`: repo-root-relative file path (required)

Response `data`:

```json
{
  "content": "file contents...",
  "path": "src/main.py",
  "size": 1234
}
```

Notes:
- Path traversal (`..`) and absolute paths are rejected.
- File must be within project root and pass include/exclude policy.

### Embedding & Compression

#### `GET /embedding/status`

Purpose:
- Get native embedding model status and current embedding provider info.

Response `data`:

```json
{
  "available": true,
  "model": "nomic-embed-text-v1.5",
  "dim": 768,
  "downloaded": true
  // native built-in ONNX fallback
}
```

#### `POST /embedding/download`

Purpose:
- Download/verify native embedding model (HuggingFace ONNX).

### LLM Proxy & Model Management

These endpoints support the dashboard's AI Models settings page.

#### `GET /api/llm/status`

Purpose:
- Legacy status check for Ollama connectivity.

Response `data`:

```json
{
  "ollama": {"url": "http://localhost:11434", "connected": true, "models": ["nomic-embed-text"]}
}
```

#### `POST /api/llm/proxy/models`

Purpose:
- Fetch available models from an endpoint (Ollama or compatible).

Request body:

```json
{
  "provider": "ollama",
  "url": "http://localhost:11434"
}
```

Response `data`:

```json
{
  "models": ["nomic-embed-text:latest", "ministral-3:3b", "ministral-3:14b"]
}
```

#### `POST /api/llm/proxy/test`

Purpose:
- Test connectivity to an endpoint.

#### `POST /llm/test`

Purpose:
- Legacy endpoint for testing LLM connectivity.

Notes:
- Alias for `/api/llm/test`.

#### `POST /api/llm/proxy/test-model`

Purpose:
- Test a specific model with readiness-aware logic. Handles embedding models
  differently (uses `/api/embeddings` instead of `/api/generate`).

Request body:

```json
{
  "provider": "ollama",
  "url": "http://localhost:11434",
  "model": "nomic-embed-text",
  "kind": "embedding"
}
```

Response `data`:

```json
{
  "success": true,
  "message": "Model responded successfully (load: 0.3s)",
  "model_status": "ready"
}
```

Notes:
- `kind` can be `"embedding"`, `"small"`, `"large"`, or `"code"`.
- Embedding models bypass the `/api/generate` preload and use `/api/embeddings` directly.
- Generous timeouts (120s) accommodate cold-start model loading.

#### `POST /api/llm/model-status`

Purpose:
- Check model readiness status without sending a test request.

### Global Configuration

### Legacy Endpoints (Deprecated)

These endpoints use a global singleton index and do not support multi-project configurations.
They are deprecated and will be removed in a future version. Use project-scoped equivalents.

#### `POST /api/code-index/context` (Deprecated)

Purpose:
- Get assembled context for LLM injection.

Notes:
- **Deprecated**: Use `POST /projects/{project_id}/context` instead.
- Uses global singleton index.
- Sunset date: 2026-06-01.

#### `POST /api/code-index/chunk` (Deprecated)

Purpose:
- Get a specific chunk by ID.

Request:

```json
{
  "chunk_id": "chunk_abc123"
}
```

Notes:
- **Deprecated**: Use `POST /projects/{project_id}/search` instead.
- Uses global singleton index.
- Sunset date: 2026-06-01.

#### `GET /api/code-index/config` (Deprecated)

Purpose:
- Get global UI configuration including LLM settings.

Notes:
- The `llm_config` section drives the backend's embedding behavior.
- Changing `llm_config.embedding.source` or `llm_config.embedding.model` invalidates
  cached indexes so the next build uses the updated embedder.

#### `PUT /api/code-index/config`

Purpose:
- Update global UI configuration (deep merge).
- Auto-saves to `ui_config.json` in the index directory.
- If the embedding config changes, cached project indexes are cleared.
