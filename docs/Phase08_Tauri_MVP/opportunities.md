# Opportunities — Phase 08 (Tauri MVP)

## Purpose
Capture packaging + desktop UX opportunities that improve reliability and trust.

## Opportunities
- **First-class log/diagnostics surfacing**: expose per-project build logs and a “Copy diagnostics” action in-app.
- **Safe background behavior**: make it explicit when the daemon is running in the background; provide a “Quit backend” action.
- **Crash recovery polish**: if the sidecar dies mid-index, the UI should keep the last good snapshot usable and offer a one-click restart.
- **Port conflict and process ownership**: robust single-instance behavior and clear attribution when a port is occupied (Prep vs other).
- **Offline-friendly UX**: ensure the app behaves predictably when no internet is available (BYOK provider checks must be non-blocking).

## Opportunities (desktop controls)
- **Backend lifecycle panel**: show:
  - backend status (starting/healthy/stopped)
  - PID + port (local-only)
  - start time + uptime
  - actions: restart, quit backend, open logs
- **Port conflict resolution UX**:
  - detect “port occupied by Prep” vs “port occupied by other”
  - show selected fallback port when needed
- **Version alignment guardrails**:
  - show UI version + backend version
  - warn when incompatible (and offer an auto-restart)
- **Safe notifications**:
  - optional desktop notifications for: build finished, build failed, backend restarted
  - ensure notifications don’t leak project paths in shared environments

## Opportunities (meaningful visualization)
- **Backend stability indicators**:
  - restart/crash count (bounded history)
  - “time since last crash”
- **Build activity timeline**: lightweight timeline of recent builds (status + duration) so users can correlate “my machine is slow” with background indexing.
- **Storage footprint view**: per-project index size and total disk usage (helps users manage space).

## Hazards
- **Sidecar lifecycle complexity**: race conditions at startup/shutdown can leave orphan processes or broken ports.
- **UI/backend version skew**: mismatched releases can create subtle schema drift and broken UI states.
- **OS security friction**: macOS notarization/Windows SmartScreen can block installs or background processes, harming trust.
- **Port conflicts and false attribution**: misidentifying the process that owns a port can confuse users and cause unsafe actions.
- **Privacy leaks via logs/UI**: diagnostics and notifications may reveal sensitive paths or repo names unless redacted appropriately.

## References
- `docs/Phase07_Polish_Testing/README.md`
- `docs/Phase11_Deployment/README.md`
- `docs/Phase08_Tauri_MVP/README.md`
