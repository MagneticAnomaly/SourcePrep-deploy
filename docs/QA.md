# QA (Open Questions)

## Purpose
Single place to collect open questions discovered during autonomous planning/implementation so execution can continue without interruptions.

## Open questions
- **QA-01: API envelope single source of truth**
  - We currently have both `src/prep/api/envelope.py` and the older `src/prep/api/responses.py` implementing envelope helpers.
  - Decide: should `responses.py` be deleted, or turned into a thin compatibility wrapper around `envelope.py`?
- **QA-02: Manifest schema completeness for Phase03 incremental rebuild**
  - Phase03 README describes per-file fields in `manifest.json` (`path`, `content_hash`, `size_bytes`, `chunk_ids`, etc.).
  - Current `CodeIndex` manifest is high-level (build stats + config) and does not track per-file chunk membership.
  - Decide: extend `manifest.json` now (format bump) vs introduce a `manifest_v2.json` / `format_version` and a migration/rebuild policy.
- **QA-03: Span/line-range semantics**
  - `docs/API.md` expects search/context results to optionally include `span`.
  - Current `/projects/{project_id}/search` and `/projects/{project_id}/context` return placeholder spans.
  - Decide: treat span as required for code chunks only, optional for markdown, or always optional.
- **QA-04: Atomic build + last-known-good snapshot contract**
  - Phase01/Phase07 require atomic swap and “last known-good” behavior during rebuilds.
  - Current build writes `documents.json`/`embeddings.npy` in-place.
  - Decide: implement temp-dir + rename swap (and what to do on startup if a temp build dir exists).
- **QA-05: Staleness semantics**
  - UI types include `ProjectStatus.stale`.
  - `AutoRebuildWatcher.status()` currently always returns `stale: False` (placeholder).
  - Decide: what is authoritative for staleness (hash scan vs watcher events), and what minimum fields should be exposed in `GET /projects/{project_id}/status`.
- **QA-06: Test/runtime environment alignment**
  - `pyproject.toml` pytest `addopts` assumes coverage + asyncio plugins, but the active interpreter may not have them installed.
  - Decide: either add the missing dev dependencies, or reduce default pytest config so `pytest` works out-of-the-box.
- **QA-07: Web UI as a production surface**
  - The React dashboard is served by `prep serve` and wrapped by Tauri. Is "open in browser" a supported production path, or dev-only?
  - **Key insight:** The Tauri desktop app is the primary UI for ALL tiers (Free through Enterprise). It provides persistent license keys, native file dialogs (no browser permission prompts), a dedicated app window (no browser-tab hell), and a clean developer workflow. The web UI is a secondary/fallback surface — useful for admin dashboards, quick access from another machine, or no-install scenarios.
  - **File picker:** The project path file picker is ALWAYS local to the end-user's machine. Even in a team scenario (e.g., Prep daemon on a Linux server with a 5090 GPU, codebases on dev laptops), the dev picks their local codebase folder. The path is sent to the server, but file selection is local. Index storage location is an IT/admin concern configured server-side, not exposed in the everyday "Add Project" flow.
  - **Browser File System Access API:** Shows a permission prompt in any browser context. This is acceptable for the web fallback but irrelevant for production — Tauri uses native OS dialogs, VS Code uses its own dialog API.
  - **Recommendation:** Support web UI as a Team+ fallback (requires auth per Phase 06 spec when binding to non-loopback). Tauri remains the primary surface for all tiers. Gate `prep serve --host 0.0.0.0` behind Team+ license check.
  - Decide: confirm Tauri-primary strategy; clarify how team-mode file scanning works when codebases live on dev laptops but the daemon runs on a separate server (agent/sidecar vs shared mount vs git-based).
