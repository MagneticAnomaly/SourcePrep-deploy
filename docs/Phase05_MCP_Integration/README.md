# Phase 05 — MCP Integration

## Problem statement
Prep must be usable inside IDE agent workflows. MCP is the fastest path to integrating with tools like Windsurf and Cursor without writing and maintaining multiple IDE plugins.

## Goal
Make Prep callable as an IDE tool (Windsurf, Cursor, etc.) via MCP.

## Scope
### In scope
- MCP tool definitions + schemas for: status/build/search/context (and trace where available)
- Project selection strategy (explicit project id and cwd auto-detection)
- User-friendly config generation (copy/paste)

### Out of scope
- IDE-specific plugins/extensions
- Advanced auth flows for network mode (Phase 06)

## Derived from (Phase69 sources)
- `../Phase00_Initial-Concept/MCP.md`

## Deliverables
- MCP server exposes: status/build/search/context (+ trace where available)
- Project auto-detection (cwd → project)
- Copy-paste MCP config output

## Functional specification

### Design constraints

- **No IDE-specific plugins**: MCP is the integration surface.
- **Local-first by default**: MCP should assume a local daemon on `127.0.0.1:8400`.
- **Stable schemas**: MCP tool outputs must not drift from the HTTP API contract the dashboard uses.
- **Bounded outputs**: defaults must be conservative (context size, k, graph neighbors).
- **Licensing consistency**: MCP errors must be stable and actionable when features are gated or usage limits are exceeded.
- **No mandatory telemetry**: MCP operation must not require analytics; any telemetry must be opt-in and must not leak repo content.

### Architecture

Recommended MVP architecture: **MCP stdio server proxies to the Prep daemon HTTP API**.

Rationale:
- Single source of truth (daemon).
- Shared error shapes and limits with the dashboard.
- Naturally supports future network mode by changing the base URL.

Transport:
- MCP server process communicates with the daemon via HTTP.
- Default base URL: `http://127.0.0.1:8400`.
- Optional override via env var: `PREP_API_BASE`.

Additional architecture (Phase 14): **Direct MCP mode**
- Single-repo, zero-daemon mode: `prep mcp --mode direct`
- The MCP server imports `prep.core` and runs indexing/search in-process.
- This is the preferred path for the lowest-friction IDE onboarding.

Daemon availability behavior:
- On startup, MCP server should perform a health check (`GET /health`).
- If unreachable:
  - tools must return an actionable `DAEMON_UNAVAILABLE` error with hint to start `prep serve` (or the desktop app in Phase 08).

### Project selection

The MCP server can be launched in one of two modes:

- **Pinned project mode**: `prep mcp --project <project_id>`
  - All tools operate on that single project by default.

- **Auto-detect mode**: `prep mcp --auto`
  - Project is selected based on the MCP server process CWD.
  - Selection rule: choose the registered project whose `path` is the **longest prefix** of `cwd`.
  - If no match, return `PROJECT_NOT_FOUND` with hint: “Add the project or run MCP with --project.”

Ambiguity:
- If multiple projects share the same root path (should be prevented by registry), return `PROJECT_SELECTION_AMBIGUOUS`.

### Tool surface

Prep’s MCP server exposes a small set of tools. Tool naming should match ADR-010.

#### `prep_status`

Purpose:
- Determine daemon connectivity, selected project identity, and index state.

Inputs:
- `project_id` (string, optional) — override selection.

Outputs (recommended shape):

```json
{
  "project": {"id": "...", "name": "...", "path": "...", "mode": "standalone"},
  "status": {
    "building": false,
    "index": {"exists": true, "total_chunks": 1234, "embedding_model": "nomic-embed-text"},
    "trace": {"enabled": false, "exists": false},
    "watch": {"enabled": false, "state": "disabled"}
  },
  "llm": {"ollama_connected": true, "prep-compress_connected": false}
}
```

#### `prep_build`

Purpose:
- Trigger a rebuild (incremental by default).

Inputs:
- `project_id` (string, optional)
- `full` (bool, optional; default `false`)

Outputs:

```json
{
  "started": true,
  "building": true,
  "build_id": "..."
}
```

#### `prep_search`

Purpose:
- Return inspectable ranked results (for debugging/exploration).

Inputs:
- `project_id` (string, optional)
- `query` (string, required)
- `k` (int, optional; default 10)
- `min_score` (number, optional; default 0.15)

Outputs:

```json
{
  "results": [
    {
      "chunk_id": "...",
      "source_path": "src/prep/server.py",
      "span": {"start_line": 142, "end_line": 175},
      "preview": "Trigger project index build...",
      "score": 0.83
    }
  ]
}
```

#### `prep`

Purpose:
- Return an assembled prompt-ready context string (default), or a structured response when requested.

Inputs:
- `project_id` (string, optional)
- `query` (string, required)
- `k` (int, optional; default 5)
- `max_chars` (int, optional; default 6000)
- `include_sources` (bool, optional; default true)
- `include_scores` (bool, optional; default false)
- `min_score` (number, optional; default 0.15)
- `structured` (bool, optional; default false)
- `trace_expand` (object, optional; see Phase 04)

Outputs:
- If `structured=false`: `{ "context": "..." }`
- If `structured=true`: `{ "context": "...", "chunks": [...], "total_chars": N, "estimated_tokens": N }`

#### `prep_trace`

Purpose:
- Provide symbol lookup and lightweight neighborhood expansion.

Inputs:
- `project_id` (string, optional)
- `query` (string, required)
- `kinds` (string[], optional)
- `neighbors` (object, optional)
  - `hops` (int, default 1)
  - `direction` (`in|out|both`, default `both`)
  - `edge_kinds` (string[], default `["imports"]`)
  - `max_nodes` (int, default 25)
  - `max_edges` (int, default 50)

Outputs:

```json
{
  "nodes": [{"id": "...", "kind": "symbol", "name": "...", "file_path": "...", "span": {"start_line": 1, "end_line": 10}}],
  "edges": []
}
```

### Mapping to daemon HTTP API

By default, MCP tools call these HTTP endpoints:

- `prep_status` → `GET /projects/{id}/status` + `GET /llm/status`
- `prep_build` → `POST /projects/{id}/build?full=false`
- `prep_search` → `POST /projects/{id}/search`
- `prep` → `POST /projects/{id}/context`
- `prep_trace` → `POST /projects/{id}/trace/search` and optionally `GET /projects/{id}/trace/neighbors/{node_id}`

### Limits and backpressure policy

Server-enforced caps (recommended):
- `search.k` max: 50
- `context.max_chars` max: 20000
- `trace.neighbors.max_nodes` max: 100
- `trace.neighbors.max_edges` max: 200

Build concurrency:
- Only one build per project at a time.
- If a build is already running, `prep_build` returns `BUILD_ALREADY_RUNNING`.

Rate limiting:
- Optional in MVP; at minimum, reject pathological requests with clear errors.

### Error model (tool-facing)

MCP tool errors should mirror the daemon’s error envelope and codes.

Minimum additional MCP-specific codes:
- `DAEMON_UNAVAILABLE`
- `PROJECT_SELECTION_AMBIGUOUS`

Recommended license/entitlement codes (mirrors daemon envelope):
- `LICENSE_REQUIRED`
- `LICENSE_INVALID`
- `LICENSE_TIER_INSUFFICIENT`
- `LICENSE_LIMIT_REACHED`

License error UX requirements:
- Errors MUST include an actionable hint (where to enter a license, or which command to run).
- In future network mode, errors MUST avoid leaking server filesystem paths.

### Analytics / measurement posture (cross-distribution)

Prep is local-first and MUST NOT require telemetry.

If analytics are enabled (opt-in), MCP-related measurement should be:
- aggregated counters (e.g., tool call counts, build success/failure counts, error code counts)
- no code, file contents, or raw query strings
- no absolute filesystem paths

### Config generation

CLI:
- `prep mcp-config` prints a ready-to-paste MCP config.

Config characteristics:
- Must support both:
  - pinned project mode (explicit)
  - auto-detect mode

## Success criteria
- An MCP client can call `prep_search` and get stable, well-shaped results.
- Project auto-detection works for common repo layouts.
- Errors are actionable (project not found, index missing, Ollama down).

## Research deliverables
- Tool surface definition (names, schemas, error shapes)
- Project auto-detection rules and precedence
- Limits policy (max k, max chars, rate limiting / backpressure if needed)

## Dependencies
- Phase 01 (core build/search/context)
- Prep server/daemon running locally (or a defined transport for remote mode)

## Open questions
- Should MCP talk to the daemon over HTTP or call engine directly in-process
  - Answer: both are supported. HTTP proxy mode remains the default for the multi-project daemon; Phase 14 added direct mode for single-repo workflows.
- How to handle multi-project selection when cwd matches multiple projects
- How to handle auth tokens for network mode (future)

## Risks
- Schema drift between MCP tool outputs and dashboard/API
- Large contexts causing slow responses in IDE agent workflows

## Testing / evaluation plan
- Integration test: invoke MCP tools against a known project (status/build/search/context)
- Backpressure test: multiple concurrent requests do not corrupt build state

## Research completion criteria
- Phase README satisfies `../PHASE_RESEARCH_GATES.md` (global checklist + Phase 05 gates)
