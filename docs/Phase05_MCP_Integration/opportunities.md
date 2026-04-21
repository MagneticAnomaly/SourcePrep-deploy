# Opportunities — Phase 05 (MCP Integration)

## Purpose
Capture MCP-facing robustness and token-efficiency opportunities.

## Opportunities
- **Never corrupt JSON-RPC**: ensure MCP server never writes to stdout/stderr; route logs to a file when debugging is enabled.
- **Lean outputs by default**: consider emitting markdown for search results (paths + spans + snippets) to reduce token waste; keep `structured=true` for programmatic consumers.
- **Capability-aware schemas**: hide tool options when unavailable (e.g., semantic search if embeddings aren’t configured).
- **Output budgets**: enforce hard caps and dynamically return fewer results when near token limits.
- **Debug mode plumbing**: opt-in debug log file to diagnose indexing/rebuild without breaking MCP.

## Opportunities (dashboard tools + settings)
- **One-click MCP config**: surface “Copy MCP config” for pinned project mode and auto-detect mode.
- **MCP health + troubleshooting panel**:
  - daemon connectivity (health check)
  - selected project resolution (pinned vs auto)
  - last MCP error code + hint
  - link to “start daemon” instructions
- **Tool output mode toggle**:
  - default: lean markdown (optimized for LLM consumption)
  - optional: structured JSON (for programmatic clients)
- **Capability checklist UX**: show a simple “what works right now” table:
  - embeddings configured
  - trace available
  - reranker available (future)

## Opportunities (meaningful visualization)
- **Request budget indicators**: show effective caps for:
  - `search.k`
  - `context.max_chars`
  - trace neighbors caps
- **Bounded payload preview**: a small “estimated tokens/chars” preview in the dashboard for context settings (teaches users to stay within budgets).

## Hazards
- **Protocol fragility**: any accidental stdout/stderr logging corrupts JSON-RPC and breaks clients.
- **Schema drift across surfaces**: MCP tools must mirror the HTTP API contract; otherwise “works in UI” but fails in IDE.
- **Ambiguous project selection**: auto-detect mode can pick the wrong project in nested repos unless rules are explicit and debuggable.
- **Token bloat and latency**: large tool responses degrade agent loops; defaults must be conservative and enforce hard caps.
- **Error leakage**: in future remote mode, MCP error details must not leak filesystem paths or sensitive config.

## References
- ChunkHound stdio MCP server disables logging to protect JSON-RPC:
  - https://raw.githubusercontent.com/chunkhound/chunkhound/main/chunkhound/mcp_server/stdio.py
- ChunkHound issue #173 (JSON → lean markdown for MCP search)
- `docs/Phase05_MCP_Integration/README.md`
- `docs/API.md`
- `docs/WORKFLOW_RESEARCH.md` (A3-J1/J2)
