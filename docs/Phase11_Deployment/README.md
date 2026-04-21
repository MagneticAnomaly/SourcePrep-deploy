# Phase 11 — Deployment

## Problem statement
Prep is intended to ship as a **desktop companion app** (macOS + Windows), wrapping the dashboard in Tauri and bundling the Python daemon as a sidecar.

Deployment must support:
- Individual developers installing quickly.
- A credible path to app store distribution.
- A future enterprise tier with per-seat licensing and IT-friendly rollout.

## Goal
Define the deployment targets, constraints, and minimum operational guidance required for MVP and the enterprise roadmap.

This phase primarily supports:
- A0-J2 (Download, upgrade, and recover)
- A4-J2 (Desktop app “it just works”)

## Scope
### In scope
- Deployment targets and trade-offs:
  - macOS direct distribution vs Mac App Store
  - Windows direct distribution vs Microsoft Store
  - enterprise distribution patterns (MDM/IT rollout assumptions)
- Signing / notarization requirements
- Installer formats and update channels (documented)
- **Auto-update system:** in-app update checks, download, signature verification, and restart
- Constraints from bundling a Python sidecar in a Tauri app
- Minimum operational guidance for MVP (install/start/stop/logs/data dirs)
- **Licensing Enforcement:**
  - Offline-friendly license validation (signed keys).
  - Feature gating logic (Pro vs Free limits).
  - "Founder's Edition" activation flow.

### Out of scope
- Differential/delta updates (full bundle replacement is sufficient for MVP)
- Implementing full enterprise governance features (SSO/SCIM/audit) (these are roadmap anchors)


## Derived from
- `docs/DECISIONS.md` (ADR-004: Web UI first, Tauri for MVP)
- `docs/Phase08_Tauri_MVP/README.md` (packaging and sidecar lifecycle)
- `docs/Phase06_Team_And_Enterprise/README.md` (network mode safety + auth)
- `docs/WORKFLOW_RESEARCH.md` (journeys, acceptance criteria, MVP boundaries)

## Deliverables
- [MACOS_DISTRIBUTION.md](MACOS_DISTRIBUTION.md)
- [WINDOWS_DISTRIBUTION.md](WINDOWS_DISTRIBUTION.md)
- [ENTERPRISE_DISTRIBUTION_AND_LICENSING.md](ENTERPRISE_DISTRIBUTION_AND_LICENSING.md)
- [LICENSING_IMPLEMENTATION.md](LICENSING_IMPLEMENTATION.md) (Offline validation specs)
- [NATIVE_ENGINE_BUILD_STRATEGY.md](NATIVE_ENGINE_BUILD_STRATEGY.md) (Cross-platform Rust engine wheel builds)
- [AUTO_UPDATE_STRATEGY.md](AUTO_UPDATE_STRATEGY.md) (In-app auto-update system)

## Deployment targets (summary)

### macOS (Apple Silicon only — no Intel release)
- **Architecture**: `aarch64-apple-darwin` (M1+). No `x86_64-apple-darwin` builds will be shipped.
- Direct distribution:
  - Requires code signing and notarization for a smooth user experience.
  - Tauri signing/notarization references:
    - https://v2.tauri.app/distribute/sign/macos/
- App Store:
  - Requires Apple Developer enrollment + App Sandbox.
  - Tauri App Store references:
    - https://v2.tauri.app/distribute/app-store/

### Windows
- Direct distribution:
  - Requires code signing to reduce SmartScreen friction.
  - Tauri Windows signing references:
    - https://v2.tauri.app/distribute/sign/windows/
- Microsoft Store:
  - Requires dev enrollment and additional packaging considerations.
  - Tauri Microsoft Store references:
    - https://v2.tauri.app/distribute/microsoft-store/

### Enterprise (Air-Gapped Support)
- Expect direct download / internal distribution to dominate.
- **Requirement:** Specialized builds or configuration flags to disable all public internet calls (telemetry, updates, BYOK checks).
- Plan early for:
  - offline-friendly licensing (cryptographic keys, no "phone home")
  - safe network-mode defaults
  - upgrade stability and data directory guarantees


## Minimum operational guidance (MVP)
- Install/uninstall on macOS and Windows.
- Where data lives (OS-appropriate data directories).
- How to view logs.
- How the sidecar is started/stopped.
- Security defaults:
  - bind the daemon to loopback by default
  - require auth for remote bind (Phase 06)

## Risks
- App store sandboxing may conflict with:
  - scanning/indexing arbitrary repos
  - running a Python sidecar
- Signing is a gating item for a smooth UX.
- Windows SmartScreen reputation can be a major adoption friction.

## Testing / evaluation plan
- Install/uninstall on each target OS.
- Upgrade test (old → new) and verify:
  - registry persistence
  - index persistence
  - config persistence
- macOS sandbox test (if targeting App Store): verify the full “add repo → build → search” workflow in sandbox context.

## Research completion criteria
- This README satisfies `../PHASE_RESEARCH_GATES.md` (global checklist + Phase 11 gates).
