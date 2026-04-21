# Phase 03 — Auto-Rebuild

## Problem statement
Manual rebuilds don’t scale: indexes become stale quickly, and users lose trust when search results don’t reflect recent changes. CoDRAG needs a predictable, low-noise way to keep indexes fresh with bounded compute.

## Goal
Make indexing maintain itself via file watching + incremental rebuild.

## Scope
### In scope
- Detect file changes per project (respect include/exclude)
- Debounced rebuild triggering
- Incremental rebuild (skip unchanged files/chunks)
- UX signals for “stale / rebuilding / fresh”

### Out of scope
- Cross-project dependency watching
- Perfect real-time rebuilds on every keystroke (avoid rebuild storms)

## Derived from (Phase69 sources)
- `../Phase00_Initial-Concept/IMPLEMENTATION.md` (incremental indexing strategy)

## Related
- `../Phase04_TraceIndex/README.md` (trace index build + query integration)
- `../Phase04_TraceIndex/TRACEABILITY_AUTOMATION_STRATEGY.md` (traceability automation options + how to avoid rebuild storms)

## Deliverables
- Per-project file watcher with debounce
- Incremental rebuild using file hashes in `manifest.json`
- UI indicators for staleness and rebuild progress

## Functional specification

### Goals and non-goals (functional)

Goals:
- Keep indexes fresh with bounded compute.
- Provide predictable behavior (no rebuild storms, no silent staleness).
- Maintain search availability while a rebuild is running.

Non-goals:
- “Rebuild on every keystroke” behavior.
- Cross-project dependency watching.

### Watcher architecture

- **Feature Gating (Monetization):**
  - **Free Tier:** Watchers are **disabled**. Users must trigger rebuilds manually (UI button or CLI).
  - **Starter/Pro/Team:** Watchers are **enabled** (subject to `auto_rebuild.enabled` config).
- Watchers are **per-project**.
- Watchers are controlled by a per-project setting `auto_rebuild.enabled`.
- Watchers must respect:
  - include globs
  - exclude globs
  - maximum file size limits

Event sources:
- Prefer OS file events where available.
- Provide a fallback polling mode (especially for network filesystems or edge platforms).

Watcher responsibilities:
- Observe changes in the project root.
- Classify changed paths as:
  - relevant (in-scope, included, not excluded)
  - irrelevant (excluded or outside include set)
- Coalesce relevant changes into a single rebuild request after debounce.

### Debounce + batching rules

Defaults:
- Debounce interval default: 5s.

Behavior:
- The debounce timer resets whenever a new relevant change is observed.
- When the timer elapses, CoDRAG triggers an incremental build.
- If a build is already running:
  - Do not start a second build.
  - Mark the project as “pending rebuild” and trigger a follow-up build after the current build completes (subject to debounce).

Batching semantics:
- The rebuild request should include the set of changed paths observed during the debounce window.
- CoDRAG should treat the changed set as advisory; the incremental builder remains authoritative (hash-based).

Storm protection:
- Impose a minimum gap between rebuilds (e.g., 2–5s) even if changes are continuous.
- If changes never settle, surface a UI warning: “Changes are continuous; auto-rebuild is throttled.”

### Incremental indexing rules

Incremental indexing is authoritative and must not depend on watcher correctness.

Manifest requirements:
- The index manifest must record enough information to decide whether a file’s derived chunks are unchanged.
- Minimum fields per file:
  - `path`
  - `content_hash`
  - `size_bytes`
  - `mtime` (optional; advisory)
  - `chunk_ids` (list)

Change detection:
- If `content_hash` differs from manifest, the file is considered changed.
- Deleted files must result in:
  - removal of their chunks from metadata
  - removal (or tombstoning) of their vectors
- Renames should be treated as delete+add unless a robust rename detector is implemented.

Stable chunk IDs:
- Chunk IDs must be stable enough to support incremental rebuilds.
- Preferred strategy (bounded complexity):
  - derive `chunk_id` from `path + span + content_hash_of_chunk`.
  - if chunking changes, affected chunks naturally get new IDs.

Atomicity and recovery:
- Builds should be committed atomically:
  - write to a temporary build directory
  - then swap/rename into place
- If an interrupted build is detected on startup:
  - the project status should show “recovery needed”
  - the next build should be forced full or should repair the partial state deterministically

### Avoiding watch loops (embedded mode and build outputs)

Even before Phase 06, loop avoidance must be defined.

Rules:
- Always exclude:
  - `.git/**`
  - `**/__pycache__/**`
  - `**/.venv/**`
  - `**/node_modules/**`
- In embedded mode, always exclude `.prep/**` from triggering rebuilds.
- In standalone mode, ensure the index directory is outside the watched tree.

### Restart behavior

On daemon startup:
- Watchers start for projects that have auto-rebuild enabled.
- CoDRAG performs a lightweight scan (or relies on manifest) to detect staleness.

Persisted “pending changes”:
- If the daemon restarts while changes are pending:
  - The project should be marked stale.
  - CoDRAG may trigger a rebuild on startup if configured.

### UX signals (Dashboard)

Status surface (per project):
- `fresh`: index exists and matches current files (best-effort).
- `stale`: changes detected since last successful build.
- `building`: build in progress.
- `pending`: build queued due to debounce or because a build is already running.

Suggested UI elements:
- Badge: Fresh / Stale / Building / Pending
- Counter: “N files changed since last build” (best-effort; derived from change set)
- Countdown: “Auto-rebuild in Xs” when in debounce window
- Action: “Rebuild now” (manual override; calls build endpoint)

## UI-facing API additions

Phase 02 defines the base dashboard API contract. Auto-rebuild adds fields to project status.

- `GET /projects/{project_id}/status`
  - Add `watch` block:

```json
{
  "watch": {
    "enabled": true,
    "state": "idle",
    "debounce_ms": 5000,
    "stale": false,
    "pending": false,
    "pending_paths_count": 0,
    "next_rebuild_at": null,
    "last_event_at": null,
    "last_rebuild_at": null
  }
}
```

Allowed `state` values:
- `disabled`
- `idle`
- `debouncing`
- `building`
- `throttled`

## Success criteria
- Editing a file in an indexed project results in stale-state detection within seconds.
- Auto-rebuild triggers after the debounce interval and completes without blocking search.
- Rebuild work is bounded: unchanged files/chunks are not re-embedded.

## Research deliverables
- Incremental indexing specification (stable IDs, hashing rules, and manifest updates)
- File watching strategy (library choice, debounce defaults, ignore patterns)
- Failure-mode and recovery plan (missed events, rebuild storms, partial indexes)

## Dependencies
- Phase 01 (core index persistence + build/search/context primitives)

## Open questions
- Watch implementation: polling vs OS events (cross-platform behavior)
- How to persist “pending changes” state when CoDRAG restarts
- How to avoid rebuild loops when build outputs are inside watched paths (embedded mode)

## Risks
- High CPU / constant rebuild loops on large repos
- Missed events on network filesystems or editor save patterns

## Testing / evaluation plan
- Integration test: modify file → stale flag → rebuild runs → search reflects change
- Regression test: rebuild does not re-embed unchanged files/chunks

## Research completion criteria
- Phase README satisfies `../PHASE_RESEARCH_GATES.md` (global checklist + Phase 03 gates)
