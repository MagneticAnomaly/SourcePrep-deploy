# Phase 11 — Deployment TODO

## Links
- Spec: `README.md`
- Opportunities: `opportunities.md`
- Master orchestrator: `../MASTER_TODO.md`
- Tauri packaging: `../Phase08_Tauri_MVP/README.md`
- Decision log: `../DECISIONS.md`

## Research completion checklist (P11-R*)
- [ ] P11-R1 Decide macOS distribution approach (direct download vs App Store constraints)
- [ ] P11-R2 Specify signing/notarization requirements and minimum operational docs for MVP
- [ ] P11-R3 Define upgrade guarantees (what persists, what breaks, rebuild communication)

## Implementation backlog (P11-I*)
### Distribution artifacts
- [ ] P11-I1 Maintain macOS distribution plan doc (signing, notarization, installer)
- [ ] P11-I2 Maintain Windows distribution plan doc (signing, SmartScreen, installer)
- [ ] P11-I3 Maintain enterprise distribution guidance (air-gapped expectations)

### Offline-friendly posture
- [ ] P11-I4 Define “offline mode” guarantees (no mandatory internet calls)
- [ ] P11-I5 Provide a clear statement of what CoDRAG contacts (and what it never contacts)

### Licensing + feature gates
- [ ] P11-I6 Define offline license validation approach (signed keys)
- [ ] P11-I7 Define enforcement points:
  - 2-project limit (Free)
  - trace enablement (Pro)
  - team policy features (Team)
- [ ] P11-I8 Define UX affordances:
  - “upgrade to enable trace” messaging
  - license status view

### Upgrade safety
- [ ] P11-I9 Detect `format_version` incompatibility and surface single remediation (“Full rebuild”)
- [ ] P11-I10 Support bundle/diagnostics expectations for support without leaking code

## Testing & validation (P11-T*)
- [ ] P11-T1 Install/uninstall test per OS
- [ ] P11-T2 Upgrade test: old → new; verify registry/index/config persistence
- [ ] P11-T3 Air-gapped sanity test: app remains usable without internet

## Cross-phase strategy alignment
Relevant entries in `../MASTER_TODO.md`:
- [ ] STR-03 Manifest + format versioning
- [ ] STR-09 Licensing + feature gating

### Native engine cross-platform builds
- [ ] P11-I11 Set up GitHub Actions workflow for cross-platform `codrag_engine` wheel builds (see NATIVE_ENGINE_BUILD_STRATEGY.md)
- [ ] P11-I12 Publish `codrag_engine` to PyPI as optional dependency
- [ ] P11-I13 Integrate correct platform wheel into Tauri app bundle build
- [ ] P11-I14 Integrate correct platform wheel into VS Code extension sidecar build
- [x] P11-I15 Document target matrix and no-Intel-Mac decision

## Notes / blockers
- [ ] Decide if App Store is a target for MVP or a later milestone
- [x] Dev venv is x86_64 (Rosetta) — needs recreation with native ARM Python (see NATIVE_ENGINE_BUILD_STRATEGY.md)
