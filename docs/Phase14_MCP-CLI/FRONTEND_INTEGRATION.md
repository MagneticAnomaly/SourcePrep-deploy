# Frontend Integration: MCP-CLI (Phase 14)

## Goal
Expose **copy/paste MCP configuration** inside the Prep dashboard so users can connect Prep to Cursor/Windsurf/etc. without reading docs.

## Backend Contract
The dashboard should call:

- `GET /api/code-index/mcp-config`

Query params:
- `ide`: `cursor | windsurf | vscode | jetbrains | claude | all`
- `mode`: `direct | auto | project`
- `project_id`: only required when `mode=project`

Response shape (for single IDE):
- `daemon_url`: string
- `file`: string
- `path_hint`: string
- `config`: JSON object (IDE-specific)

Notes:
- `mode=direct` generates an MCP config that runs:
  - `prep mcp --mode direct`
- `mode=auto` and `mode=project` generate configs that assume a daemon:
  - `prep mcp --mode server --auto --daemon <url>`
  - `prep mcp --mode server --project <id> --daemon <url>`

## Dashboard Implementation
Implementation lives in:
- `src/prep/dashboard/src/App.tsx`

The dashboard adds an "IDE Integration (MCP)" panel that:
- Lets the user pick IDE + MCP mode.
- Fetches the config from `/api/code-index/mcp-config`.
- Renders the JSON in a `<pre>`.
- Includes a "Copy MCP Config" button.

## UX Notes
- Default to **Direct mode** for the lowest friction path.
- If the user selects `mode=project`, require `project_id` input before fetching.

## Non-Goals (Phase 14)
- No live MCP connection testing from the dashboard.
- No automatic writing of IDE config files.
- No multi-repo/project registry UX (Direct mode assumes one repo).
