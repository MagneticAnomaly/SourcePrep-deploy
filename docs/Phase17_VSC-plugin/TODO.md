# Phase 17: VS Code Extension — TODO

## Pre-Implementation Research

- [x] **R-01**: Audit VS Code extension examples with daemon-backed architecture (GitLens, Docker, Remote-SSH) for patterns
- [x] **R-02**: Prototype VS Code CSS variable → `@prep/ui` token bridge (test with Dark+, Light+, Monokai, Dracula)
- [x] **R-03**: Evaluate `@vscode/webview-ui-toolkit` vs `@prep/ui`-in-WebView bundle size trade-off
- [x] **R-04**: Test VS Code `vscode.env.machineId` availability and stability across OS restarts / updates
- [x] **R-05**: Confirm Lemon Squeezy activation limit API (create test product, hit limit, verify error shape)
- [x] **R-06**: Prototype daemon auto-start from extension host (spawn `prep serve`, health-poll, graceful teardown)

## Sprint 1: Skeleton + Daemon Connection

- [x] **S1-01**: Scaffold extension project (`yo code` or manual: `package.json`, `tsconfig.json`, esbuild config)
- [x] **S1-02**: Register Activity Bar icon + empty sidebar container
- [x] **S1-03**: Implement `PrepDaemonClient` (TypeScript HTTP client wrapping `/health`, `/projects`, `/projects/{id}/status`)
- [x] **S1-04**: Implement daemon discovery (settings → env vars → default `127.0.0.1:8400`)
- [x] **S1-05**: Status bar item: daemon connection status (🟢/🔴) + click-to-start
- [x] **S1-06**: Command: `Prep: Start Daemon` (spawn `prep serve` if on PATH)
- [x] **S1-07**: Graceful degradation UI when daemon is unreachable

## Sprint 2: Sidebar — Projects + File Tree

- [x] **S2-01**: `ProjectsTreeDataProvider` — list projects from daemon, show name/status/mode
- [x] **S2-02**: Project context menu: Remove, Rebuild, Copy MCP Config
- [x] **S2-03**: `FileTreeDataProvider` — show indexed file tree for selected project (call `/projects/{id}/roots` + `/projects/{id}/file-content`)
- [x] **S2-04**: File click → open in editor; pin/unpin support
- [x] **S2-05**: Index status tree section: freshness, chunk count, last build time
- [x] **S2-06**: Build progress indicator (poll `/projects/{id}/status` during build)

## Sprint 3: Commands + Feature Gating

- [x] **S3-01**: Command: `Prep: Search` — input box → call `/projects/{id}/search` → open results WebView
- [x] **S3-02**: Command: `Prep: Assemble Context` — input box → call `/projects/{id}/context` → open preview WebView
- [x] **S3-03**: Command: `Prep: Build Index` — trigger `/projects/{id}/build`
- [x] **S3-04**: Command: `Prep: Add Project` — folder picker → `POST /projects`
- [x] **S3-05**: Command: `Prep: Copy MCP Config` — generate JSON for active project/IDE
- [x] **S3-06**: Tier detection: call daemon license endpoint, cache tier in `globalState`
- [x] **S3-07**: Feature gate wrappers: disable watcher/trace commands on Free tier, show upgrade prompt
- [x] **S3-08**: "PRO" badge rendering on locked sidebar items

## Sprint 4: WebView Panels

- [x] **S4-01**: Scaffold WebView build pipeline (Vite + React, separate from extension host bundle)
- [x] **S4-02**: VS Code CSS variable injection into WebView (`--vscode-*` → `@prep/ui` tokens)
- [x] **S4-03**: Search Results WebView: query input, results list, click-to-open-file messaging
- [x] **S4-04**: Context Preview WebView: assembled context, copy button, token estimate
- [x] **S4-05**: Trace Panel WebView (Pro only): symbol search, node details, edge navigation
- [x] **S4-06**: Free tier overlay for Trace Panel ("Upgrade to Pro" + link)
- [x] **S4-07**: Theme change listener (`onDidChangeActiveColorTheme`) → re-inject variables

## Sprint 5: Licensing Integration

- [x] **S5-01**: Command: `Prep: Enter License Key` — input box → forward to daemon license endpoint
- [x] **S5-02**: Command: `Prep: Deactivate License` — call daemon deactivation endpoint
- [x] **S5-03**: License status display in status bar (`FREE` / `PRO` / `TEAM`)
- [x] **S5-04**: Activation error handling: `ACTIVATION_LIMIT_REACHED` → show machine management link
- [x] **S5-05**: License change listener: re-fetch tier when license file changes, update UI gating

## Sprint 6: Polish + Marketplace

- [x] **S6-01**: Test against top 10 VS Code themes (see README.md list)
- [x] **S6-02**: Multi-root workspace handling: auto-detect projects from workspace folders
- [x] **S6-03**: Keyboard shortcuts for common commands (search, build, context)
- [x] **S6-04**: Extension settings UI (`contributes.configuration` in `package.json`)
- [x] **S6-05**: Marketplace listing assets: icon, banner, screenshots, README
- [x] **S6-06**: Privacy policy compliance (declare network access, link to runprep.io/privacy)
- [x] **S6-07**: CI pipeline: build, test, package `.vsix`, publish to Marketplace
- [x] **S6-08**: Telemetry opt-in (if any): aggregate counters only, no file contents

## Post-MVP / Stretch

- [ ] **PM-01**: Copilot Chat tool provider (register Prep tools via `lm` API when stable)
- [ ] **PM-02**: Direct mode fallback (spawn `prep mcp --mode direct` when daemon is down, single-repo only)
- [ ] **PM-03**: Inline code lens: show Prep trace info (callers/callees) inline in editor
- [ ] **PM-04**: Watcher control panel in sidebar (Pro only)
- [ ] **PM-05**: "Open in Dashboard" button (launches browser to `http://localhost:8400`)
- [ ] **PM-06**: Auto-install daemon prompt (brew/pip/binary download)

## Dependencies

| Dependency | Status | Blocking |
|:---|:---|:---|
| Daemon `/health` endpoint | ✅ Exists | — |
| Daemon `/projects/*` API | ✅ Exists | — |
| Daemon license-status endpoint (`GET /license`) | ✅ Exists | — |
| Daemon `/license/activate` endpoint | ✅ Exists | — |
| Daemon `/license/deactivate` endpoint | ✅ Exists | — |
| Daemon MCP config endpoint (`GET /api/code-index/mcp-config`) | ✅ Exists | — |
| Daemon activation exchange endpoint (`api.runprep.io`) | ❌ Not yet | S5-01 |
| Lemon Squeezy product + activation limits | ❌ Not yet | S5-01 |
| `@prep/ui` CSS token system documentation | ✅ Exists | S4-02 |
| Signed Prep binaries on PATH | ❌ Not yet (dev only) | S1-06 |
