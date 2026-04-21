# Phase 69 — MCP (Cascade/Windsurf) Local RAG Tooling

## Goal
Make **Cascade (Windsurf IDE assistant)** able to call a **local retrieval tool** (RAG) while coding.

This repo contains a local-first RAG/index implementation and HTTP APIs exposed by the **CoDRAG daemon**.

This document adds an MCP server wrapper so Windsurf/Cascade can call retrieval as a tool.

## What was added
Two MCP stdio server wrappers:

- Python (recommended): `code_index/mcp_codrag_py/server.py`
- Node: `code_index/mcp_codrag/index.mjs`

Both expose MCP tools:

- `codrag_status`
- `codrag_build`
- `codrag_search`
- `codrag` (context)

All tools proxy to `RAG_API_BASE` + `/{status|build|search|context}`.

## Tool guide (what to use when)

### `codrag_status`

What it does:
- Calls `GET {RAG_API_BASE}/status`
- Returns server/index state: whether an index is loaded, build status, last error, and basic stats.

When to use:
- First step when something feels “off” (no results, errors, stale index)
- Check whether a build is currently running
- Confirm which project you’re pointed at

Typical output includes:
- `building` (bool)
- `last_error` (string or null)
- `index.loaded` (bool)
- `index.total_documents` / embedding dimension / model (if available)

---

### `codrag_build`

What it does:
- Calls `POST {RAG_API_BASE}/build`
- Kicks off an **async** build (it returns quickly; you poll `codrag_status` to see completion).

When to use:
- After changing config (roots, include/exclude globs, file size limits)
- After pulling new code/docs and you want the index to reflect it
- When `codrag_status` says the index isn’t loaded

Important notes:
- This is an async job. Use `codrag_status` until `building=false`.
- Parameters are passed through to the HTTP server.

Common args:
- `repo_root` (string)
- `include_globs` (string[])
- `exclude_globs` (string[])
- `max_file_bytes` (int)

---

### `codrag_search`

What it does:
- Calls `POST {RAG_API_BASE}/search`
- Returns a ranked list of chunks (metadata + score). This is **for inspecting results**.

When to use:
- You want to see what the retriever would surface (debugging / exploration)
- You want filenames/sections and scores before asking for a context bundle
- You want to iterate on query phrasing and `min_score`

Common args:
- `query` (string, required)
- `k` (int, optional) — how many results
- `min_score` (number, optional) — filter weak matches

How to interpret:
- Use this when you want *control* and *visibility*.
- If you just want “a good context blob to paste into the LLM”, use `codrag` instead.

---

### `codrag`

What it does:
- Calls `POST {RAG_API_BASE}/context`
- Returns **one assembled text block** (the "best chunks" concatenated) intended for LLM injection.
- Headers include source file paths by default (for attribution).

When to use:
- You want the tool to do retrieval + packing for you
- You want something ready to paste into a prompt or feed into an agent step

**Arguments:**

| Arg | Type | Default | Description |
|-----|------|---------|-------------|
| `query` | string | (required) | Search query |
| `k` | int | 5 | Number of chunks to include |
| `max_chars` | int | 6000 | Maximum total characters in output |
| `include_sources` | bool | true | Include `@source_path` in chunk headers (for attribution) |
| `include_scores` | bool | false | Include `score=0.xxx` in headers (for debugging) |
| `min_score` | float | 0.15 | Minimum relevance score threshold |
| `structured` | bool | false | Return structured response with metadata |

**Output modes:**

1. **Default** (`structured=false`): Returns plain context string
   - Chunks separated by `---`
   - Headers: `[Name | XREF-ID | Section | @source/path.md]`

2. **Structured** (`structured=true`): Returns JSON with metadata
   ```json
   {
     "context": "...",
     "chunks": [
       {"source_path": "...", "xref_id": "...", "section": "...", "score": 0.85, "truncated": false},
       ...
     ],
     "total_chars": 4500,
     "estimated_tokens": 1125
   }
   ```

**Example calls:**

```
# Simple (just get context)
codrag(query="How is image generation implemented?")

# With score debugging
codrag(query="notification system", include_scores=true)

# Structured for programmatic use
codrag(query="temporal events", structured=true, k=8)

# Tighter filtering
codrag(query="Phase 70", min_score=0.25, max_chars=4000)
```

**Rule of thumb:**
- Use `codrag_search` to *debug/inspect*.
- Use `codrag` to *consume*.

---

### Implementation status

| Feature | Status |
|---------|--------|
| `/status` exposes `context_defaults` | Done |
| `min_score` filtering | Done |
| `include_sources` (attribution) | Done |
| `include_scores` (debugging) | Done |
| `structured` mode with metadata | Done |
| `estimated_tokens` in structured output | Done |
| Dedupe near-identical chunks | Future |
| `max_per_file` cap | Future |
| context compression layer | Future (Phase 3)

## Prerequisites
- A running RAG HTTP server:
  - CoDRAG daemon: `http://localhost:8400`

## 1) Run the MCP server
### Option A (recommended): Python MCP stdio server
This avoids npm registry/auth issues and is the most portable option for other developers.

Install dependencies:

```bash
# IMPORTANT: install and run with the SAME Python interpreter.

python3 -m pip install mcp httpx anyio
```

Run the server (stdio; it will appear “silent” until Windsurf connects — this is normal):

```bash
RAG_API_BASE="http://localhost:8400/projects/<project-id>" \
python3 \
  /absolute/path/to/CoDRAG/src/codrag/mcp_codrag_py/server.py
```

Env vars:
- `RAG_API_BASE` (example: `http://localhost:8400/projects/<project-id>`)
- `RAG_TIMEOUT_S` (default: `30`)

### Option B: Node MCP stdio server
From repo root:

```bash
cd code_index/mcp_codrag
npm install
RAG_API_BASE="http://localhost:8400/projects/<project-id>" npm run start
```

Notes:
- `RAG_API_BASE` should include the project prefix so the MCP tools are scoped.

## 2) Build the index (once)
You can build via the MCP tool `codrag_build`, or directly over HTTP.

### CoDRAG build example
```bash
curl -sS -X POST "http://localhost:8400/projects/<project-id>/build" \
  -H "Content-Type: application/json" \
  -d '{"repo_root":"/absolute/path/to/your/repo","include_globs":["**/*.md","**/*.py"],"exclude_globs":["**/.git/**","**/node_modules/**"]}'
```

## 3) Configure Windsurf (Cascade) to use this MCP server
Add an MCP server entry in Windsurf pointing to the stdio server.

Example config (you must adapt paths).

Notes:
- Prefer using a venv so the `mcp` dependency is guaranteed to be installed.

### Python MCP server config

```json
{
  "mcpServers": {
    "codrag": {
      "command": "python3",
      "args": [
        "/absolute/path/to/CoDRAG/src/codrag/mcp_codrag_py/server.py"
      ],
      "env": {
        "RAG_API_BASE": "http://localhost:8400/projects/<project-id>",
        "RAG_TIMEOUT_S": "30"
      }
    }
  }
}
```

If you want to use `python3` instead of the venv (works only if your global python has `mcp` installed):

```json
{
  "mcpServers": {
    "codrag": {
      "command": "python3",
      "args": [
        "/absolute/path/to/CoDRAG/src/codrag/mcp_codrag_py/server.py"
      ],
      "env": {
        "RAG_API_BASE": "http://localhost:8400/projects/<project-id>",
        "RAG_TIMEOUT_S": "30"
      }
    }
  }
}
```

### Node MCP server config

```json
{
  "mcpServers": {
    "codrag": {
      "command": "node",
      "args": [
        "/absolute/path/to/LinuxBrain/code_index/mcp_codrag/index.mjs"
      ],
       "env": {
         "RAG_API_BASE": "http://localhost:8400/projects/<project-id>",
         "RAG_TIMEOUT_MS": "30000"
       }
     }
   }
 }
```

## Troubleshooting
- If Windsurf shows the MCP server as “crashing immediately”, verify the `command` is pointing at a Python interpreter that has `mcp` installed (recommended: repo `.venv`).
- If you see connection errors, verify `RAG_API_BASE` points at a running CoDRAG daemon and includes `/projects/<project-id>`.
- If `npm install` fails with `404 Not Found` for `@modelcontextprotocol/server`, use the Python MCP server option.
- If `npm` mentions an expired token, run `npm logout` then `npm login` (or switch to Python).

## 4) Validate end-to-end
- Call `codrag_status` (should show `loaded` and/or build state)
- Call `codrag` with a query like:
  - “Where is the image generation endpoint implemented?”

## Reuse in another codebase
To use this MCP server in another repo:

- Copy `code_index/mcp_codrag_py/` (recommended) or `code_index/mcp_codrag/` (Node)
- Ensure a compatible RAG HTTP server exists (either:
  - reuse `code_index/server.py` in that repo, or
  - provide the same 4 endpoints)
- Point Windsurf’s MCP server config to the copied server entrypoint and set `RAG_API_BASE`
