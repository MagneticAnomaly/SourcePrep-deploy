# Prep Component Inventory

This document catalogs all UI components needed for Prep across all tiers and phases.

## Component Status Legend
- ✅ Scaffolded (wireframe exists)
- 🔲 Needed (to be scaffolded)
- 📋 Planned (future phase)

---

## 1. Core Features (MVP - Phases 01-02)

### 1.1 Status Components ✅
| Component | Status | Purpose |
|-----------|--------|---------|
| `StatusBadge` | ✅ | Visual status indicator (Fresh/Stale/Building/Error) |
| `StatusCard` | ✅ | Project status overview card |
| `BuildProgress` | ✅ | Build progress with phases and counters |

### 1.2 Navigation Components ✅
| Component | Status | Purpose |
|-----------|--------|---------|
| `AppShell` | ✅ | Main layout container |
| `Sidebar` | ✅ | Collapsible sidebar |
| `ProjectList` | ✅ | Project list with selection |
| `ProjectTabs` | ✅ | Open project tabs |

### 1.3 Search Components ✅
| Component | Status | Purpose |
|-----------|--------|---------|
| `SearchInput` | ✅ | Query input with submit |
| `SearchResultRow` | ✅ | Single search result |
| `ChunkViewer` | ✅ | Full chunk detail panel |

### 1.4 Context Components ✅
| Component | Status | Purpose |
|-----------|--------|---------|
| `ContextViewer` | ✅ | Assembled context output |
| `CitationBlock` | ✅ | Source attribution |
| `CopyButton` | ✅ | Copy-to-clipboard action |

### 1.5 Pattern Components ✅
| Component | Status | Purpose |
|-----------|--------|---------|
| `EmptyState` | ✅ | No data placeholder |
| `LoadingState` | ✅ | Loading indicator |
| `ErrorState` | ✅ | Actionable error display |

---

## 2. Project Management (Phase 01-02)

### 2.1 Project CRUD
| Component | Status | Purpose |
|-----------|--------|---------|
| `AddProjectModal` | ✅ | Add new project dialog |
| `ProjectSettingsPanel` | ✅ | Per-project config (include/exclude, trace, auto-rebuild) |
| `RemoveProjectConfirm` | 🔲 | Confirmation for project removal |
| `ProjectModeSelector` | 🔲 | Standalone vs Embedded mode selection |

### 2.2 Settings
| Component | Status | Purpose |
|-----------|--------|---------|
| `GlobalSettingsModal` | 🔲 | LLM endpoints, defaults |
| `GlobPatternEditor` | 🔲 | Include/exclude pattern editor |
| `ModelSelector` | 🔲 | Embedding model selection |

---

## 3. Auto-Rebuild (Phase 03)

### 3.1 Watch Status
| Component | Status | Purpose |
|-----------|--------|---------|
| `WatchStatusIndicator` | ✅ | Watch state badge (idle/debouncing/building/throttled) |
| `StalenessIndicator` | 🔲 | Files changed since last build counter |
| `DebounceCountdown` | 🔲 | "Auto-rebuild in Xs" timer |
| `RebuildNowButton` | 🔲 | Manual rebuild trigger |

### 3.2 Build History
| Component | Status | Purpose |
|-----------|--------|---------|
| `BuildHistoryList` | 🔲 | List of recent builds |
| `BuildHistoryItem` | 🔲 | Single build entry (status, duration, stats) |

---

## 4. Trace Index (Phase 04)

### 4.1 Symbol Browser
| Component | Status | Purpose |
|-----------|--------|---------|
| `TraceStatusCard` | ✅ | Trace index status (enabled, exists, counts) |
| `SymbolSearchInput` | ✅ | Symbol name search |
| `SymbolResultList` | 🔲 | Symbol search results |
| `SymbolResultRow` | ✅ | Single symbol result (name, kind, file) |

### 4.2 Node Detail
| Component | Status | Purpose |
|-----------|--------|---------|
| `NodeDetailPanel` | ✅ | Symbol metadata (kind, span, docstring) |
| `EdgeList` | 🔲 | Inbound/outbound edges grouped by kind |
| `EdgeItem` | 🔲 | Single edge (kind, target, confidence) |
| `NodeReferenceLink` | 🔲 | Clickable link to navigate to node |

### 4.3 Context Expansion
| Component | Status | Purpose |
|-----------|--------|---------|
| `TraceExpandToggle` | 🔲 | Enable trace expansion for context |
| `TraceExpandSettings` | 🔲 | Hops, edge kinds, limits |

---

## 5. MCP Integration (Phase 05)

### 5.1 MCP Status
| Component | Status | Purpose |
|-----------|--------|---------|
| `MCPConnectionStatus` | 🔲 | MCP server connection indicator |
| `MCPConfigGenerator` | 🔲 | Generate copy-paste MCP config |
| `MCPConfigPreview` | 🔲 | Preview generated config |

### 5.2 Tool Surface
| Component | Status | Purpose |
|-----------|--------|---------|
| `MCPToolList` | 🔲 | Available MCP tools |
| `MCPToolDoc` | 🔲 | Tool documentation (inputs/outputs) |

---

## 6. LLM Services

### 6.1 LLM Status
| Component | Status | Purpose |
|-----------|--------|---------|
| `LLMStatusWidget` | ✅ | Ollama connection status |
| `OllamaStatusBadge` | 🔲 | Ollama connection state |
| `ModelList` | 🔲 | Available embedding models |

### 6.2 LLM Settings
| Component | Status | Purpose |
|-----------|--------|---------|
| `LLMEndpointConfig` | 🔲 | URL configuration for Ollama |
| `LLMTestButton` | 🔲 | Force connectivity check |

---

## 7. Team Features (Phase 06 - Team Tier)

### 7.1 Server Mode
| Component | Status | Purpose |
|-----------|--------|---------|
| `ServerModeBanner` | 🔲 | "Remote mode" persistent indicator |
| `ServerModeIndicator` | ✅ | Local vs Remote badge |
| `BindingWarning` | 🔲 | Security warning for 0.0.0.0 binding |

### 7.2 Authentication
| Component | Status | Purpose |
|-----------|--------|---------|
| `APIKeyInput` | 🔲 | API key entry field |
| `APIKeyDisplay` | 🔲 | Masked key with copy/reveal |
| `AuthRequiredBanner` | 🔲 | Notice when auth is required |

### 7.3 Shared Configuration
| Component | Status | Purpose |
|-----------|--------|---------|
| `TeamConfigStatus` | ✅ | team_config.json detection indicator |
| `TeamConfigViewer` | 🔲 | View applied team settings |
| `TeamConfigOverrideWarning` | 🔲 | Warning when local settings differ |
| `ConfigExportButton` | 🔲 | Export team config action |

### 7.4 Embedded Mode
| Component | Status | Purpose |
|-----------|--------|---------|
| `EmbeddedModeIndicator` | ✅ | .runprep/ directory indicator |
| `EmbeddedIndexStatus` | 🔲 | Embedded index health |
| `MergeConflictWarning` | 🔲 | Git merge conflict detection |
| `CommitPolicySelector` | 🔲 | Committed vs gitignored choice |

### 7.5 Team Onboarding
| Component | Status | Purpose |
|-----------|--------|---------|
| `OnboardingWizard` | 🔲 | Clone → Add → Search flow |
| `OnboardingStep` | 🔲 | Single onboarding step |
| `QuickStartCard` | 🔲 | Getting started guidance |

---

## 8. Enterprise Features (Phase 06 - Enterprise Tier)

### 8.1 Admin Dashboard
| Component | Status | Purpose |
|-----------|--------|---------|
| `AdminLayout` | 📋 | Enterprise admin shell |
| `UserList` | 📋 | User management list |
| `UserRow` | 📋 | Single user with role/status |
| `SeatCounter` | 📋 | Seats used / available |

### 8.2 License Management
| Component | Status | Purpose |
|-----------|--------|---------|
| `LicenseStatusCard` | ✅ | License tier and validity |
| `LicenseKeyInput` | 🔲 | License key entry |
| `LicenseActivation` | 🔲 | Activation flow |
| `LicenseExpiry` | 🔲 | Expiration warning/renewal |

### 8.3 Governance
| Component | Status | Purpose |
|-----------|--------|---------|
| `AuditLogViewer` | 📋 | Audit trail display |
| `AuditLogEntry` | 📋 | Single audit event |
| `PolicyEditor` | 📋 | Organization-wide policy settings |

### 8.4 SSO/SCIM (Future)
| Component | Status | Purpose |
|-----------|--------|---------|
| `SSOConfigPanel` | 📋 | SSO provider configuration |
| `SCIMStatus` | 📋 | SCIM sync status |

---

## 9. Page-Level Components

### 9.1 Project Pages
| Component | Status | Purpose |
|-----------|--------|---------|
| `StatusPage` | 🔲 | Project status overview |
| `SearchPage` | 🔲 | Search UI composition |
| `ContextPage` | 🔲 | Context assembly UI |
| `TracePage` | 🔲 | Symbol browser UI |
| `SettingsPage` | 🔲 | Project settings UI |

### 9.2 Global Pages
| Component | Status | Purpose |
|-----------|--------|---------|
| `DashboardHome` | 🔲 | Landing/overview page |
| `LLMStatusPage` | 🔲 | LLM services status |
| `TeamSettingsPage` | 📋 | Team admin page |

---

## Component Priority Matrix

### P0 - Critical Path (MVP)
Already scaffolded: Status, Navigation, Search, Context, Patterns

### P1 - Next Sprint
- `AddProjectModal`
- `ProjectSettingsPanel`
- `GlobalSettingsModal`
- `LLMStatusWidget`
- `WatchStatusIndicator`
- `TraceStatusCard`
- `LicenseStatusCard`

### P2 - Team Features
- `ServerModeIndicator`
- `APIKeyInput`
- `TeamConfigStatus`
- `EmbeddedModeIndicator`
- `OnboardingWizard`

### P3 - Polish
- `BuildHistoryList`
- `MCPConfigGenerator`
- Page compositions

### P4 - Enterprise (Post-MVP)
- Admin components
- Governance components
- SSO/SCIM

---

## Type Additions Needed

```typescript
// Watch state (Phase 03)
export type WatchState = 'disabled' | 'idle' | 'debouncing' | 'building' | 'throttled';

// Build phase
export type BuildPhase = 'scanning' | 'chunking' | 'embedding' | 'writing' | 'complete' | 
                         'trace_scan' | 'trace_parse' | 'trace_write';

// Server mode (Phase 06)
export type ServerMode = 'local' | 'remote';

// Project mode
export type ProjectMode = 'standalone' | 'embedded';

// Node kind (Phase 04)
export type NodeKind = 'file' | 'symbol' | 'external_module';

// Edge kind (Phase 04)
export type EdgeKind = 'contains' | 'imports' | 'calls' | 'implements' | 'documented_by';

// License tier
export type LicenseTier = 'free' | 'starter' | 'pro' | 'team' | 'enterprise';

// Team config status
export type TeamConfigStatus = 'none' | 'applied' | 'overridden' | 'conflict';
```

---

## API Response Types Needed

```typescript
// Watch status (Phase 03)
interface WatchStatus {
  enabled: boolean;
  state: WatchState;
  debounce_ms: number;
  stale: boolean;
  pending: boolean;
  pending_paths_count: number;
  next_rebuild_at: string | null;
  last_event_at: string | null;
  last_rebuild_at: string | null;
}

// Trace node (Phase 04)
interface TraceNode {
  id: string;
  kind: NodeKind;
  name: string;
  file_path: string;
  span: { start_line: number; end_line: number };
  language: string | null;
  metadata: Record<string, unknown>;
}

// Trace edge (Phase 04)
interface TraceEdge {
  id: string;
  kind: EdgeKind;
  source: string;
  target: string;
  metadata: { confidence: number; [key: string]: unknown };
}

// LLM status
interface LLMStatus {
  ollama: { url: string; connected: boolean; models: string[] };
}

// Server status (Phase 06)
interface ServerStatus {
  mode: ServerMode;
  requires_auth: boolean;
}

// Team config (Phase 06)
interface TeamConfig {
  include_globs: string[];
  exclude_globs: string[];
  trace_enabled: boolean;
  embedding_model: string;
}
```
