# Phase 08 — Tauri MVP

## Problem statement
A web dashboard is great for development, but most users want a simple installable desktop app experience. Tauri provides a small, cross-platform wrapper while keeping the Python daemon as a sidecar.

## Goal
Wrap the web dashboard into a native desktop app for MVP distribution.

## Scope
### In scope
- Tauri wrapper around the dashboard
- Bundling and launching the Python sidecar
- Installer builds (macOS/windows/linux where feasible)
- Basic update strategy (documented, even if manual for MVP)

### Out of scope
- Full auto-update system with delta updates and rollback
- Deep native OS integrations beyond basics (tray/menu can be staged)

## Derived from
- `docs/ROADMAP.md`
- `docs/ARCHITECTURE.md` (sidecar strategy)

## Deliverables
- Tauri wrapper + Python sidecar packaging
- Installers
- Basic update strategy

## Functional specification

### Desktop app architecture (MVP)

The Tauri app is a wrapper around the existing web dashboard, plus a process manager for the Python daemon.

Components:
- **WebView**: renders the React dashboard.
- **Rust host**: owns window lifecycle and sidecar lifecycle.
- **Python sidecar**: runs the Prep daemon (FastAPI).

Constraints:
- The desktop app should be usable without the user manually running `prep serve`.
- The daemon must bind to loopback by default.

### Sidecar lifecycle

Startup sequence:

1. Determine target API base (port selection; see below).
2. If a daemon is already running and healthy on that base:
   - do not start a new sidecar
   - connect the UI to the existing daemon
3. Otherwise:
   - launch the bundled Python sidecar
   - wait for `GET /health` to return `status=ok`
4. Load the dashboard pointing at the daemon base.

Shutdown sequence:

- On app quit, request graceful daemon shutdown (future endpoint) or terminate the sidecar process.
- Ensure no orphaned daemon is left running unless the user explicitly configured “keep daemon running”.

Crash recovery:

- If the daemon process exits unexpectedly:
  - UI displays a banner: “Backend stopped”
  - Provide actions: “Restart backend”, “View logs”, “Quit”

### Port and binding strategy

Default:
- Prefer `127.0.0.1:8400`.

Conflict handling:
- If 8400 is occupied:
  - first determine whether the occupant is Prep (health check)
  - if it is Prep, connect to it
  - otherwise select an ephemeral free port and start the sidecar there

Port discovery:
- The chosen port should be exposed to the WebView via:
  - an environment variable, or
  - a small local config file, or
  - a Tauri command that returns the base URL

Security:
- Sidecar must bind to loopback unless the user explicitly enables network mode (Phase 06).

### Single-instance behavior

MVP expectation:
- One desktop app instance per user.
- Launching the app when already running should focus the existing window.

Daemon behavior:
- Prefer one daemon per user.
- If the daemon is already running, the app attaches (does not start a second daemon).

### Data directory locations

The desktop app must store Prep data in OS-appropriate locations.

Rules:
- Default to platform conventions.
- Allow override via Prep config (advanced).

Recommended defaults:
- macOS: `~/Library/Application Support/Prep/`
- Windows: `%APPDATA%\\Prep\\`
- Linux: `~/.local/share/runprep/`

### Packaging strategy

Python sidecar packaging requirements:
- Must bundle Python + dependencies.
- Must be reproducible and signed where necessary.

MVP-friendly default:
- Prefer PyInstaller first (fast iteration), with a documented path to more advanced packaging later.

### Update strategy (MVP)

Out of scope is a full auto-update system with rollback.

Minimum viable update behavior:
- The app shows its current version.
- The app can check for updates (manual trigger) and display:
  - latest version
  - link to download
- Upgrades should preserve:
  - registry
  - project indexes
  - config

### Installer expectations

- Install/uninstall should not require deep technical steps.
- The installer must not silently enable network mode.

### UX requirements

- “Backend starting…” loading screen with a timeout.
- If startup times out:
  - show failure with actionable steps (open logs, retry, open settings)
- “Backend connected” indicator in a debug/about panel.

## Success criteria
- A user can install and launch Prep as a desktop app.
- The dashboard is accessible and the backend is started automatically.
- The app can be cleanly shut down without leaving stray processes.

## Research deliverables
- Packaging plan (PyInstaller/PyOxidizer choice and rationale)
- Port/binding strategy (avoid conflicts, detect already-running daemon)
- Signing/notarization plan (at least documented requirements)

## Dependencies
- Phase 02 (dashboard is stable)
- Phase 07 (stability baseline)

## Open questions
- How to handle multi-instance behavior (single-instance daemon vs per-window)
- Where to store the data directory on each OS
- Minimum supported platforms for MVP

## Risks
- Packaging complexity dominates schedule
- OS security policies (macOS notarization, Windows AV false positives)

## Testing / evaluation plan
- Install/uninstall test on each target OS
- Upgrade test (old version → new version)
- Crash recovery test (daemon dies; UI reports and can restart)

## Research completion criteria
- Phase README satisfies `../PHASE_RESEARCH_GATES.md` (global checklist + Phase 08 gates)
