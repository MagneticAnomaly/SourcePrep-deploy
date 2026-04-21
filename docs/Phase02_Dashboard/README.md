# Phase 02 — Dashboard

## Problem statement
CLI-only workflows slow adoption and make index state hard to understand. CoDRAG needs a first-class dashboard that exposes project management, build status, search results, and context assembly in a way that builds user trust.

## Goal
Deliver a usable web dashboard for CoDRAG (multi-project management, build, search, context).

## Scope
### In scope
- Multi-project navigation (project list + tabs)
- Build trigger + status polling
- Search UI (results list + chunk viewer)
- Context assembly UI (copyable output + citations)
- Settings UI (include/exclude, model/URLs where applicable)

### Out of scope
- Full trace graph visualization (beyond basic trace toggles and basic trace fields)
- Enterprise admin UX (user management, audit logs)

## Derived from (Phase69 sources)
- `../Phase00_Initial-Concept/IMPLEMENTATION.md`

## Deliverables
- Project list + tabs
- Build/status UX
- Search results + chunk viewer
- Context assembly viewer

## Functional specification

### Information architecture

Project-scoped pages (within the selected project):
- Status
- Search
- Context
- Trace (only if trace is enabled for the project)
- Settings

Global UI:
- use https://github.com/tremorlabs/tremor
- Sidebar: project list + add/remove
- Project tabs: open projects + quick switching
- Global settings modal: LLM endpoints and defaults

### Core concepts and naming

- **Project**: a registered repo root with per-project config.
- **Index build**: generates/updates the embedding index (and optionally the trace index).
- **Stale**: project contents have changed since last successful build (Phase 03), or index missing.
- **Context**: an assembled text blob intended to be pasted into an LLM prompt, with citations.

### Primary user flows

#### First-run / empty state

- If no projects exist:
  - Show an empty-state screen in the main pane.
  - Provide a single primary CTA: “Add project”.
  - Provide a short explanation of local-first behavior: “Projects are indexed locally; nothing is uploaded.”

#### Add project

Inputs (minimum viable):
- **Path**: required.
- **Name**: optional (defaults to folder name).
- **Mode**: standalone (default) vs embedded (Phase 06).

Validation rules (UI-side + server-side):
- Path must exist.
- Path must be a directory.
- If the path already exists as a registered project:
  - UI should surface a clear “already added” error and offer a “Go to project” action.

#### Select/open projects

- Selecting a project in the sidebar opens a tab (if not already open) and makes it active.
- Tabs persist across refresh (localStorage is acceptable in dev; later may be server-backed).

#### Build + status

- Status page must clearly answer:
  - “Is this project indexed?”
  - “Is a build running?”
  - “When was the last successful build?”
  - “If it failed, why, and what do I do next?”

Actions:
- **Build (incremental)**: default.
- **Full rebuild**: secondary; confirms destructive rebuild.
- **Cancel build**: only if supported by backend later (spec the button as disabled until supported).

Progress:
- Show a coarse phase indicator even if fine-grained counters are unavailable.
- When counters exist, show a progress bar + counts.

#### Search

- Query input + results list.
- Result rows show:
  - file path (relative to project root)
  - a short preview/snippet
  - score (optional; default hidden behind a “Show scores” toggle)
  - chunk type (code/doc) where available

Chunk inspection:
- Selecting a result opens a detail drawer/panel with:
  - full chunk text
  - source path
  - span info (line range if available)
  - “Copy chunk” action

#### Context assembly

- Query input + advanced options:
  - `max_chars`
  - `k`
  - `min_score`
  - include sources
  - include scores (debug)
  - structured output (debug/programmatic)

Output:
- Context viewer must support:
  - copy-to-clipboard
  - clear citation headers per chunk
  - a compact “sources list” view (derived from citations)

#### Settings

Per-project settings:
- **Knowledge Sources (Folder Tree)**:
  - Checkboxes for file/folder inclusion.
  - **Ancestor Selection**: Selecting a folder implicitly selects all its descendants (loaded or not).
  - **Orphan Cleanup**: Unchecking a folder removes all latent descendant paths from storage.
- Include globs / exclude globs
- `max_file_bytes`
- Trace enabled toggle
- Auto-rebuild enabled toggle (Phase 03)

Global settings (modal):
- Ollama URL
- Default embedding model


### UX states and error handling

The dashboard should consistently render one of:
- Loading
- Empty (no data)
- Ready
- Error (actionable)
- **Transient Complete**: After a successful build, the progress bar forces a "100% Complete" green state for 5 seconds before reverting to the standard status view.

Error state requirements:
- Always show:
  - a human-readable summary
  - a “Details” expandable block (raw `error.code` + message)
  - a recommended next action (retry, open settings, rebuild)

### UI polling model

- Use polling for build state in Phase 02 (SSE/websocket optional later).
- Suggested polling cadence:
  - While `building=true`: poll every 1–2s.
  - Otherwise: poll every 10–30s (or on window focus).

## UI-facing API contract

This dashboard consumes CoDRAG’s daemon API (FastAPI). CoDRAG should follow the authoritative contract in `../API.md`.

### Response envelope

Success:

```json
{
  "success": true,
  "data": { "...": "..." },
  "error": null
}
```

Error:

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "PROJECT_NOT_FOUND",
    "message": "Project with ID 'xyz' not found",
    "hint": "Add the project first or select an existing project."
  }
}
```

## Deep research notes (Phase01 + Phase02)

### User archetypes

- **Solo developer (local-first default)**
  - Needs: frictionless add/build/search, “what changed?” clarity, fast copyable context.
  - Primary fear: the tool is “lying” because it’s stale or indexing the wrong paths.

- **Staff engineer / tech lead (multi-repo, onboarding)**
  - Needs: repeatable project config, quick switching between repos, high-trust status.
  - Primary fear: “index state is opaque” and “new teammates can’t reproduce results”.

- **IDE agent user (MCP consumer)**
  - Needs: predictable context assembly + bounded output, stable citations.
  - Primary fear: context overflow / runaway latency during agent loops.

- **Ops/security-conscious user (pre-Phase06)**
  - Needs: clear local-only messaging, explicit network-mode guardrails.
  - Primary fear: accidental data exposure.

### Workflow analysis (trust-first UX)

The dashboard’s job is to help the user answer three questions quickly:

1. **Am I looking at the right project?**
   - Show repo path prominently (relative path + “copy path” action).
2. **Is the index fresh enough?**
   - Show “fresh/stale/building” state with a clear timestamp.
3. **Can I verify the answer?**
   - Every search/context output must link back to source path + span.

Recommended workflow loops:

- **Loop A: First-run → trust bootstrap**
  - Add project
  - Build
  - Search a known file/symbol
  - Open chunk → confirm file/span

- **Loop B: Daily usage (fast context)**
  - Search
  - Inspect 1–2 chunks
  - Generate context
  - Copy + paste to LLM

- **Loop C: “Why is it wrong?” debugging**
  - Status page shows stale/build failure details
  - Settings page shows include/exclude + max file size
  - User triggers full rebuild

### Scope refinements (Phase02)

To keep Phase02 shippable and coherent:

- **MVP dashboard is a “trust console”**, not a full IDE.
- UI should prioritize:
  - clear status + errors
  - inspectability (chunk viewer)
  - bounded context assembly

Tremor implications:
- Prefer Tremor primitives (layout, cards, tables, tabs, badges) for consistent dashboard UX.
- Keep custom components minimal and centered around:
  - chunk viewer
  - context output viewer

### Error codes (minimum set)

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
- `INTERNAL_ERROR`

### Projects

- `GET /projects`
  - Returns:
    - `projects`: list of `{id, name, path, mode, created_at, updated_at}`
    - `total`

- `POST /projects`
  - Request:
    - `name` (optional)
    - `path` (required)
    - `mode` (optional; `standalone` default)
  - Response:
    - `project`: `{id, name, path, mode, config}`

- `GET /projects/{project_id}`
  - Response:
    - `project`: `{id, name, path, mode, config}`

- `PUT /projects/{project_id}`
  - Request:
    - `name` (optional)
    - `config` (optional)
  - Response:
    - `project`

- `DELETE /projects/{project_id}?purge=false`
  - Response:
    - `removed=true`
    - `purged=true|false`

### Project status and build

- `GET /projects/{project_id}/status`
  - Response:
    - `building` (bool)
    - `index`: `{exists, total_chunks, embedding_dim, embedding_model, last_build_at, last_error}`
    - `trace`: `{enabled, exists, last_build_at, last_error}`
    - `llm`: `{ollama_connected, clara_connected}` (optional convenience)

- `POST /projects/{project_id}/build?full=false`
  - Response:
    - `started` (bool)
    - `building` (bool)
    - `build_id` (string, optional)

Progress granularity (recommended for UI):

```json
{
  "phase": "chunking",
  "percent": 0.42,
  "counts": {
    "files_total": 1200,
    "files_done": 312,
    "chunks_total": 5400,
    "chunks_done": 1800
  }
}
```

### Search

- `POST /projects/{project_id}/search`
  - Request:
    - `query` (required)
    - `k` (optional)
    - `min_score` (optional)
  - Response:
    - `results`: list of:
      - `chunk_id`
      - `source_path`
      - `span` (optional)
      - `preview` (string)
      - `score` (number)

### Context

- `POST /projects/{project_id}/context`
  - Request:
    - `query` (required)
    - `k` (optional)
    - `max_chars` (optional)
    - `include_sources` (optional)
    - `include_scores` (optional)
    - `min_score` (optional)
    - `structured` (optional)
  - Response:
    - `structured=false`: `{ "context": "..." }`
    - `structured=true`:

```json
{
  "context": "...",
  "chunks": [
    {
      "chunk_id": "...",
      "source_path": "...",
      "span": {"start_line": 1, "end_line": 20},
      "score": 0.85,
      "truncated": false
    }
  ],
  "total_chars": 4500,
  "estimated_tokens": 1125
}
```

## Limits and defaults (dashboard behavior)

- Search default `k`: 10
- Context default `k`: 5
- Context default `max_chars`: 6000–8000 (match CLI defaults)
- Default `min_score`: 0.15

## Security / local-first constraints

- The dashboard must not require any external network connectivity for core use.
- The UI should treat “network mode” (Phase 06) as a distinct, explicitly configured mode.
- If CoDRAG is bound to a non-loopback interface, the UI should display a conspicuous “Remote mode” indicator (and later require auth).

## Success criteria
- A user can add/select a project and understand whether it is indexed.
- A user can trigger a build and see clear progress/failure states.
- Search results are navigable (path + preview + full chunk view).
- Context output is copyable and includes clear citations.

## Research deliverables
- Dashboard information architecture (pages/tabs, navigation, empty states)
- API contract the UI consumes (request/response schemas and error shapes)
- UX constraints and non-goals (what is intentionally not shown in v1)

## Dependencies
- Phase 01 (core index build/search/context)
- A stable FastAPI surface for dashboard calls (multi-project routing)

## Open questions
- Which settings are global vs per-project (ollama URL, embedding model, include/exclude)
- How to present build progress (coarse state vs per-file/chunk counters)
- How to handle network mode auth in the UI (future Phase 06)

## Risks
- Scope creep (dashboard becomes “the product” too early)
- UI design diverges from API capabilities, creating rework

## Testing / evaluation plan
- E2E smoke test: add project → build → search → view chunk → context
- Error-state test: Ollama down, bad path, build failure

## Current implementation status
- `src/codrag/dashboard/src/App.tsx` is currently the primary repair target due to missing/truncated state + handlers (notably for `AIModelsSettings`).
- Backend endpoints required for the legacy single-project settings round-trip have been confirmed:
  - `GET/PUT /api/code-index/config`
  - `GET /api/llm/proxy/models`
  - `POST /api/llm/proxy/test-model`
  - `GET /llm/status`
- Immediate next step is to restore LLM config state + handler wiring in `App.tsx` so the dashboard compiles and settings persist.

## Research completion criteria
- Phase README satisfies `../PHASE_RESEARCH_GATES.md` (global checklist + Phase 02 gates)

## Notes
This is UI/UX for the standalone daemon (not Halley’s Dev tab).

Importantly -- this will grow significantly as we add more features to CoDRAG.
