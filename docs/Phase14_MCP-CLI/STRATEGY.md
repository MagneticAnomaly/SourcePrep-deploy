# Strategy: Direct MCP & CLI

## Current Architecture (Split Process)
Currently, Prep uses a Client-Server model:
1.  **Daemon**: `prep serve` (FastAPI, holds the Index in memory).
2.  **CLI/MCP**: `prep mcp` (Connects to Daemon via HTTP).

**Pros:** Multi-project, persistent caching, dashboard support.
**Cons:** User must start/manage the daemon. Complexity for simple usage.

## Target Architecture (Direct Mode)
We need a **Direct Mode** where the CLI/MCP process *owns* the Index directly.

### 1. `DirectMCPServer`
A new implementation of the MCP Protocol that imports `prep.core` directly instead of making HTTP calls.

*   **State**: Holds `CodeIndex` and `TraceIndex` in memory (lazy loaded).
*   **Concurrency**: Since `CodeIndex` methods (search, build) are blocking (SQLite, NumPy), we must run them in `asyncio.to_thread` to keep the MCP stdio transport responsive.
*   **Lifecycle**:
    *   On `initialize`: Identify the `cwd` as the project root.
    *   On `tools/call`: Load index if needed, perform operation.
    *   On `exit`: Clean up.

### 2. Auto-Indexing (Zero Config)
When running in Direct Mode:
*   Default index directory is: `<repo_root>/.prep/index`.
*   The server lazily loads any existing index artifacts from disk.
*   Builds are triggered explicitly via `prep_build` (runs in background).

### 3. The "One Repo" Assumption
Direct Mode assumes the current working directory (CWD) is the Repository Root.
*   No `project_id` complexity.
*   No database of projects.
*   Just `index_dir = ./.prep/index`.

## Implementation Steps

### A. Refactor `prep.core`
Ensure `prep.core` is truly decoupled from `prep.server`.
*   *Status*: Looks good. `CodeIndex`, `TraceIndex`, `Embedder` are independent.

### B. Create `prep.mcp_direct`
A new module implementing the MCP server interface but calling `core` directly.
*   Duplicate the `tools` definitions from `mcp_server.py`.
*   Implement `handle_tools_call` using `CodeIndex.search()`, etc.
*   Wrap blocking calls in `await asyncio.to_thread(...)`.

### C. Update CLI Entry Point
Modify `prep mcp` command:
```bash
prep mcp --mode direct
```
Server mode remains available:
```bash
prep mcp --mode server --auto --daemon http://127.0.0.1:8400
```

### D. Dashboard Integration
The daemon exposes an MCP config endpoint:
- `GET /api/code-index/mcp-config`

The dashboard uses this endpoint to provide a copy/paste IDE setup flow.

## Risks & Mitigations
*   **Memory Usage**: Running the index inside the IDE's MCP process (managed by the IDE) might consume RAM.
    *   *Mitigation*: The IDE usually spawns a separate process for the MCP server, so this is fine. It won't crash the IDE UI.
*   **Build Performance**: Building the index (embedding) is CPU intensive.
    *   *Mitigation*: Run build in a separate thread/process so the MCP "ping" still responds.
