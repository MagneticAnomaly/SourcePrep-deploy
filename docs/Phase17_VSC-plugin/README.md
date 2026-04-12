# Phase 17: VS Code Extension — CoDRAG for VS Code

## Overview

The CoDRAG VS Code extension is a **mid-weight UI surface** that sits between the headless CLI/MCP and the full Tauri desktop GUI. It provides visual access to CoDRAG's core features directly inside VS Code, styled to match the user's active editor theme, with full Free/Pro feature gating.

### Positioning in the Product Line

| Surface | Audience | UI | Requires Daemon | Multi-Project |
|:---|:---|:---|:---|:---|
| **MCP (Direct)** | Power users, agents | None (tool calls) | No | No (CWD) |
| **CLI** | Terminal users | Terminal output | Yes (most cmds) | Yes |
| **VS Code Extension** | VS Code users | Sidebar + panels | Yes | Yes (within limits) |
| **Tauri Desktop App** | Full GUI users | Native window | Bundled | Yes |

The extension is the **primary free-tier funnel for VS Code users** — it lets them experience CoDRAG visually without installing the full desktop app, while showing Pro features as disabled upsells.

---

## Architecture

### Communication Model

```
┌──────────────────────────────────────────────┐
│  VS Code Extension (TypeScript)              │
│  ┌──────────────┐  ┌──────────────────────┐  │
│  │  Sidebar UI  │  │  WebView Panels      │  │
│  │  (TreeView)  │  │  (React / @codrag/ui)│  │
│  └──────┬───────┘  └──────────┬───────────┘  │
│         │                     │               │
│         └─────────┬───────────┘               │
│                   │                           │
│         ┌─────────▼──────────┐                │
│         │  Extension Host    │                │
│         │  (API Client)      │                │
│         └─────────┬──────────┘                │
└───────────────────┼──────────────────────────┘
                    │ HTTP (localhost:8400)
         ┌──────────▼──────────┐
         │  CoDRAG Daemon      │
         │  (FastAPI server)   │
         └─────────────────────┘
```

### Key Architectural Decisions

1. **Daemon-required**: The extension talks to the CoDRAG daemon (`codrag serve`) over HTTP. It does NOT run the engine in-process (unlike Direct MCP mode). This avoids duplicating the full Python runtime inside the extension host.

2. **Daemon lifecycle management**: The extension can optionally auto-start the daemon (if `codrag` is on PATH) and offer a "Start Daemon" command when it detects the daemon is down.

3. **Shared API client**: Reuse `CodragApiClient` from `@codrag/ui` (or a lightweight TypeScript port) to call `/projects/{id}/*` endpoints.

4. **WebView for rich panels**: Use VS Code WebView API for panels that need rich rendering (search results, context preview, trace graph). These can import `@codrag/ui` components and respect VS Code CSS variables for theme matching.

5. **Native TreeView for file tree**: The sidebar file tree uses VS Code's native `TreeDataProvider` API, which automatically inherits the editor theme. This is the primary navigation surface.

---

## UI Design

### Sidebar (Activity Bar Icon)

A CoDRAG icon in the Activity Bar opens a sidebar with these tree views:

#### 1. Projects Tree
- Lists all registered projects from the daemon
- Each project node expands to show:
  - **Status** (indexed / building / stale)
  - **Quick actions** (Build, Search, Open in Dashboard)
- Context menu: Remove, Rebuild, Copy MCP Config
- **Free tier**: Only 1 project visible; additional projects show a lock icon + "Upgrade to Pro"

#### 2. File Tree (per-project)
- Shows the indexed file tree for the selected project
- Mirrors `FolderTreePanel` from the dashboard
- Files can be pinned/unpinned (pinned files get priority in context assembly)
- Coverage indicators (indexed vs excluded)
- Click to open file in editor

#### 3. Index Status
- Freshness indicator (last build time, stale file count)
- Build progress bar (when building)
- Watcher status (running/stopped) — **Free: disabled, shows "Pro" badge**

### Command Palette Commands

| Command | Free | Pro |
|:---|:---|:---|
| `CoDRAG: Search` | ✅ | ✅ |
| `CoDRAG: Assemble Context` | ✅ | ✅ |
| `CoDRAG: Build Index` | ✅ (manual only) | ✅ |
| `CoDRAG: Start Watcher` | ❌ (shows upgrade) | ✅ |
| `CoDRAG: Stop Watcher` | ❌ | ✅ |
| `CoDRAG: Trace Lookup` | ❌ (shows upgrade) | ✅ |
| `CoDRAG: Add Project` | ✅ (limited to 1) | ✅ |
| `CoDRAG: Remove Project` | ✅ | ✅ |
| `CoDRAG: Copy MCP Config` | ✅ | ✅ |
| `CoDRAG: Open Dashboard` | ✅ (opens browser) | ✅ |
| `CoDRAG: Enter License Key` | ✅ | ✅ |
| `CoDRAG: Start Daemon` | ✅ | ✅ |

### WebView Panels

#### Search Results Panel
- Opens as an editor tab (WebView)
- Query input + results list with file/line references, scores, previews
- Click result → opens file at line in editor
- Styled with VS Code CSS variables

#### Context Preview Panel
- Shows assembled context with source citations
- Copy button (for pasting into prompts)
- Token estimate display

#### Trace Panel (Pro only)
- Symbol search → node details → incoming/outgoing edges
- Click edge → navigate to definition
- Free tier: panel opens but shows "Upgrade to Pro" overlay

### Status Bar Item

A persistent status bar item showing:
- **Daemon status**: 🟢 Connected / 🔴 Disconnected (click to start)
- **Active project**: Name + freshness dot
- **License tier**: `FREE` / `PRO` / `TEAM` (click to manage)

---

## Feature Gating (Free vs Pro)

The extension enforces the **exact same tier limits** as the daemon/dashboard:

### Free Tier (Default — no license)

| Feature | Behavior |
|:---|:---|
| **Projects** | 3 active projects max (daemon enforces) |
| **Search** | Standard keyword/embedding search |
| **Context assembly** | ✅ Full |
| **Trace Index** | ✅ Full |
| **Real-time watcher** | ✅ Full |
| **MCP tools** | Standard set |
| **File tree / pin** | ✅ Full |
| **Build** | ✅ Full (manual + auto) |

### Pro Tier ($79 perpetual)

| Feature | Behavior |
|:---|:---|
| **Projects** | Unlimited |
| **Search** | Full (including trace-expanded results) |
| **Context assembly** | ✅ Full |
| **Trace Index** | ✅ Full panel + trace lookup command |
| **Real-time watcher** | ✅ Start/stop from extension |
| **MCP tools** | Full suite |
| **File tree / pin** | ✅ Full |
| **Build** | ✅ Manual + auto (via watcher) |

### How gating works technically

1. Extension calls `GET /health` or a license-status endpoint on the daemon.
2. Daemon returns the current tier + feature flags (from the signed license file).
3. Extension caches the tier locally and uses it to show/hide/disable UI elements.
4. **The extension never validates the license itself** — the daemon is authoritative.
5. When a gated feature is invoked, the extension shows a non-blocking "Upgrade" prompt with a link to `codrag.io/pricing`.

### "Show but disable" pattern

Pro-only features are **always visible** in the UI but rendered in a disabled/dimmed state with a small lock icon or "PRO" badge. This is a deliberate upsell pattern:
- Trace panel header: `Trace Index 🔒 PRO`
- Watcher toggle: grayed out + tooltip "Upgrade to Pro to enable real-time indexing"
- Project list: 2nd+ projects show lock overlay

---

## Theme Integration

The extension MUST look native to the user's VS Code theme.

### Strategy

1. **Native TreeViews**: Automatically inherit the theme (no custom styling needed).
2. **WebView panels**: Inject VS Code's CSS variables into the WebView:
   ```css
   body {
     background: var(--vscode-editor-background);
     color: var(--vscode-editor-foreground);
     font-family: var(--vscode-font-family);
     font-size: var(--vscode-font-size);
   }
   .card {
     background: var(--vscode-editorWidget-background);
     border: 1px solid var(--vscode-editorWidget-border);
   }
   .button-primary {
     background: var(--vscode-button-background);
     color: var(--vscode-button-foreground);
   }
   ```
3. **@codrag/ui bridge**: Create a thin CSS layer that maps VS Code CSS variables to `@codrag/ui`'s CSS custom properties (the same token system used in the dashboard). This lets us reuse `@codrag/ui` components inside WebViews while respecting the VS Code theme.
4. **Theme change listener**: Listen for `vscode.window.onDidChangeActiveColorTheme` to re-inject variables when the user switches themes.

---

## Licensing & Abuse Prevention

### License Activation Flow (same as desktop app)

1. User purchases on `codrag.io` → Lemon Squeezy issues a license key.
2. User runs `CoDRAG: Enter License Key` in VS Code.
3. Extension sends the key to the daemon's license endpoint.
4. Daemon calls `api.codrag.io/activate` (the "Activation Exchange"):
   - Sends: `{ license_key, machine_id }` where `machine_id` is a hash of hostname + OS + hardware identifiers.
   - Receives: A signed Ed25519 offline license file (or an error if limits exceeded).
5. Daemon saves the license file locally.
6. All subsequent validation is **offline** (signature verification only).

### "Installed Too Many Times" — Activation Limit Enforcement

This is handled at the **Activation Exchange** layer (`api.codrag.io`), NOT in the extension itself.

#### For Paid Tiers (Pro / Starter / Team)

Lemon Squeezy natively supports **activation limits** per license key:
- **Pro**: 3 machine activations per key (user can deactivate old machines via `codrag.io/account`).
- **Starter**: 2 machine activations.
- **Team**: N activations (matches seat count).

When the user tries to activate on a 4th machine (Pro example):
1. `api.codrag.io/activate` calls Lemon Squeezy's activation API.
2. Lemon Squeezy returns `ACTIVATION_LIMIT_REACHED`.
3. `api.codrag.io` returns an error to the daemon.
4. The extension shows: "License activation limit reached (3/3 machines). Deactivate a machine at codrag.io/account or upgrade your plan."

#### For Free Tier (No License Key)

The free tier does NOT require a license key (default state). Abuse prevention for the free tier uses a **lightweight anonymous activation** model:

1. On first launch, the extension generates a **machine fingerprint** (SHA-256 hash of: hostname + OS username + VS Code machine ID from `vscode.env.machineId`).
2. The extension stores this fingerprint locally in `globalState`.
3. **No server call is required** for free tier — the daemon enforces limits locally (1 project, no trace, no watcher).
4. **Sharing prevention**: Since the daemon runs locally and enforces the 1-project limit, there's no meaningful abuse vector. The "free tier" is inherently bounded by the machine it runs on.

> **Key insight**: Unlike a SaaS where free accounts can be created infinitely, CoDRAG's free tier is limited by **local machine resources** (you must install the daemon, Ollama, etc.). The 1-project limit is enforced server-side (daemon). The VS Code extension is just a UI — it doesn't unlock anything the daemon wouldn't already allow.

#### VS Code Marketplace Considerations

- VS Code extensions cannot prevent installation. Anyone can install from the Marketplace.
- The extension itself is **always free to install** — it's a thin client.
- Feature gating happens at the daemon layer, not the extension layer.
- This is the same model as e.g. GitLens (free extension, paid features gated by account).

### Deactivation

- `CoDRAG: Deactivate License` command sends a deactivation request to `api.codrag.io`.
- Frees up the machine slot for use elsewhere.
- Daemon reverts to free tier behavior.

---

## Daemon Discovery & Lifecycle

### Discovery

1. **Default**: `http://127.0.0.1:8400`
2. **Settings**: User can configure `codrag.daemon.url` in VS Code settings.
3. **Environment**: Respects `CODRAG_HOST` and `CODRAG_PORT` env vars.

### Auto-Start (Optional)

If the daemon is not running and `codrag` is on PATH:
1. Extension prompts: "CoDRAG daemon is not running. Start it?"
2. If accepted, spawns `codrag serve` as a background process.
3. Monitors health via `GET /health` polling.
4. Shows status in the status bar.

### Graceful Degradation

When the daemon is unreachable:
- Sidebar shows "Daemon offline" state with a "Start" button.
- All feature commands show an error with instructions to start the daemon.
- The extension does NOT crash or spam errors.

---

## Limitations & Constraints

### 1. No In-Process Engine
Unlike Direct MCP mode, the extension cannot run the CoDRAG Python engine in-process. It requires the daemon. This is a deliberate trade-off:
- **Pro**: No Python runtime bundling, smaller extension size, single source of truth for index state.
- **Con**: User must have the daemon running (but auto-start mitigates this).

### 2. WebView Restrictions
- VS Code WebViews run in sandboxed iframes with limited API access.
- No direct filesystem access from WebViews — must message back to extension host.
- WebView state is lost when the tab is hidden (unless `retainContextWhenHidden` is set, which uses more memory).

### 3. Theme Mapping Is Approximate
- `@codrag/ui` uses a specific design token system. Mapping VS Code CSS variables to these tokens will be ~95% accurate but may have edge cases with unusual themes.
- Mitigation: Test against the top 10 most popular VS Code themes (Dark+, Light+, Monokai, Dracula, One Dark, Solarized, GitHub, Nord, Catppuccin, Gruvbox).

### 4. Extension Size Limits
- VS Code Marketplace has a **50MB** package size limit.
- If we bundle `@codrag/ui` + React into WebViews, we must tree-shake aggressively.
- Mitigation: Lazy-load WebView bundles only when panels are opened.

### 5. No Background Processing
- VS Code extensions are deactivated when the window closes.
- The extension cannot keep the watcher running — that's the daemon's job.
- The extension is purely a UI/control surface, not a background service.

### 6. Multi-Root Workspace Complexity
- VS Code supports multi-root workspaces (multiple folders open).
- The extension must handle this: offer project selection when the workspace root matches multiple registered projects.
- Auto-detect: match workspace folder paths against daemon's project registry.

### 7. Marketplace Review Requirements
- Microsoft reviews extensions for: malware, telemetry disclosure, permission justification.
- We must declare: network access (to `localhost:8400` and `api.codrag.io` for activation).
- Privacy policy link required (use `codrag.io/privacy`).

### 8. Competing Extensions
- Other code-context tools may offer VS Code extensions (Augment, Cody, Continue.dev).
- CoDRAG's differentiator: **local-first, no code upload, BYOK, structural trace**.
- The extension should emphasize this in the Marketplace listing.

---

## Relationship to MCP

The VS Code extension and the MCP server are **complementary, not competing**:

| Concern | VS Code Extension | MCP Server |
|:---|:---|:---|
| **User** | Human developer | AI agent (Copilot, etc.) |
| **Interaction** | Visual (click, browse) | Programmatic (tool calls) |
| **Discovery** | "What can CoDRAG do?" | "Give me context for this task" |
| **Value** | Browsing, configuration, upsell | Agentic workflows |

Both talk to the same daemon. The extension can also help configure MCP:
- `CoDRAG: Copy MCP Config` generates the JSON for the user's IDE config.
- Extension settings could auto-configure `settings.json` MCP entries (if the user opts in).

### Can the Extension Also Be an MCP Host?

VS Code's Copilot Chat supports MCP tool providers. In the future, the extension could register CoDRAG tools directly with Copilot Chat (via the `lm` API). This would make CoDRAG tools available to Copilot without separate MCP config. **This is a post-MVP stretch goal.**

---

## Technology Stack

| Layer | Technology | Rationale |
|:---|:---|:---|
| Extension host | TypeScript + VS Code API | Required |
| Sidebar trees | `TreeDataProvider` | Native theme, best perf |
| WebView panels | React + `@codrag/ui` subset | Component reuse from dashboard |
| WebView styling | VS Code CSS vars → `@codrag/ui` token bridge | Theme matching |
| HTTP client | Built-in `fetch` or `axios` | Talk to daemon |
| Bundler | esbuild (extension) + Vite (WebView) | Fast builds |
| Testing | VS Code Extension Test framework + Vitest (WebView) | Standard |
| CI | GitHub Actions | Marketplace publish |

---

## Marketplace Strategy

### Listing

- **Name**: `CoDRAG — Local Code Context Engine`
- **Publisher**: `magnetic-anomaly` (or `codrag`)
- **Category**: `Other` (or `Machine Learning` if accepted)
- **Tags**: `code search`, `context`, `RAG`, `MCP`, `local-first`, `semantic search`
- **Pricing**: Free (features gated by daemon license)

### README / Marketplace Page

- Hero: Screenshot of sidebar + search results
- Value prop: "Local-first code context for AI workflows. No code upload. Works with Copilot, Cursor, Windsurf via MCP."
- Quick start: Install extension → Install CoDRAG daemon → Add project → Search
- Feature table: Free vs Pro
- Link to `codrag.io` for full details

### Analytics

- VS Code Marketplace provides download counts and ratings.
- Extension telemetry (if any): opt-in only, aggregated, no file contents (same policy as daemon).

---

## Open Questions

1. **Should the extension bundle a minimal "direct mode" fallback?** (e.g., spawn `codrag mcp --mode direct` for zero-config single-repo usage when the daemon isn't running) — This would lower friction but increase complexity.

2. **Should WebView panels use `@codrag/ui` directly or a lighter VS Code-native component set?** Using `@codrag/ui` maximizes reuse but adds bundle size. A VS Code-native approach (using `@vscode/webview-ui-toolkit`) would be lighter but means maintaining two component sets.

3. **Should the extension auto-install the daemon?** (e.g., prompt to install via `brew install codrag` or `pip install codrag`) — Good for onboarding but risky (permissions, PATH issues).

4. **Copilot Chat tool provider**: When VS Code's MCP-in-extension API stabilizes, should we register CoDRAG tools natively? This could replace the separate `codrag mcp` process for VS Code users entirely.
