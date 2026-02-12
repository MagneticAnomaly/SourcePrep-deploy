# Phase 08 — Tauri MVP TODO

## Links
- Spec: `README.md`
- Opportunities: `opportunities.md`
- Master orchestrator: `../MASTER_TODO.md`
- Research backlog: `../RESEARCH_BACKLOG.md`
- Deployment spec: `../Phase11_Deployment/README.md`

## Research completion checklist (P08-R*)
- [x] P08-R1 Choose packaging approach (PyInstaller vs PyOxidizer) and document rationale ✅ **DONE: PyInstaller (see PACKAGING_STRATEGY.md)**
- [x] P08-R2 Specify port/binding strategy and single-instance behavior ✅ **DONE: Port 8400 / 127.0.0.1 (see PACKAGING_STRATEGY.md)**
- [x] P08-R3 Specify OS-specific data directories and signing/notarization requirements ✅ **DONE: Standard paths (see PACKAGING_STRATEGY.md)**

## Implementation backlog (P08-I*)
### Sidecar lifecycle
- [x] P08-I1 Startup sequence: ✅ **DONE: `src/main.rs`**
  - determine API base (default 8400)
  - connect to existing daemon if healthy
  - else launch bundled python sidecar and wait for `/health`
- [x] P08-I2 Shutdown sequence: ✅ **DONE: `src/main.rs` uses `SidecarState` + `RunEvent::Exit`**
  - graceful shutdown endpoint (if available) or terminate sidecar
  - avoid orphan processes
- [x] P08-I3 Crash recovery UX: ✅ **DONE: `App.tsx` ConnectionGuard**
  - banner when backend stopped
  - actions: restart backend / view logs

### Port strategy
- [x] P08-I4 Prefer `127.0.0.1:8400` ✅ **DONE: `src/main.rs`**
- [ ] P08-I5 If port occupied, detect whether it’s CoDRAG; otherwise use fallback port
- [x] P08-I6 Expose chosen base URL to WebView reliably ✅ **DONE: `get_daemon_config` command**

### UX surfaces
- [x] P08-I7 “Backend starting…” screen with timeout + actionable failure state ✅ **DONE: `StartupScreen.tsx`**
- [x] P08-I8 Optional backend lifecycle panel (PID/port local-only) ✅ **DONE: `ConnectionGuard` handles status**

## Testing & validation (P08-T*)
- [x] P08-T1 Install and first-run: backend starts automatically and dashboard loads ✅ **DONE: Verified `.app` creation & sidecar build**
- [ ] P08-T2 Port conflict test: occupied 8400 handled correctly
- [ ] P08-T3 Crash recovery test: sidecar dies mid-run → UI surfaces and can restart

## Cross-phase strategy alignment
Relevant entries in `../MASTER_TODO.md`:
- [ ] STR-08 Packaging strategy (python sidecar)
- [ ] STR-03 Format versioning (upgrade/rebuild prompts in app UX)

## Notes / blockers
- [ ] Decide whether “keep backend running after app close” exists in MVP
- [ ] Decide minimum platform support for MVP packaging
