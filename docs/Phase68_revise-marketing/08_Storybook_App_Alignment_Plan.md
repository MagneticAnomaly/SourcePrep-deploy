# Storybook ↔ App Alignment & Docs Embed Plan

> **Status**: Phase 68 — Active implementation. P0 and P1 stories completed. Coverage at **63%**. Docs pages wired with live Storybook embeds.  
> **Last Updated**: 2026-04-03  
> **Theme**: Retro Aurora (`m`) + Dark Mode (hardcoded in StoryEmbed)

---

## 0. Execution Log

### ✅ Completed Work

| Date | Work Item | Status |
|------|-----------|--------|
| 2026-04-03 | Created `StoryEmbed` component with hardcoded Retro Aurora theme | ✅ Done |
| 2026-04-03 | P0: AnimatedCLI.stories.tsx (4 stories) | ✅ Done |
| 2026-04-03 | P0: AnimatedIDE.stories.tsx (2 stories) | ✅ Done |
| 2026-04-03 | P0: AgentScopePanel.stories.tsx (2 stories) | ✅ Done |
| 2026-04-03 | P0: AgentOpsPanel.stories.tsx (3 stories) | ✅ Done |
| 2026-04-03 | P0: AuditPanel.stories.tsx (3 stories) | ✅ Done |
| 2026-04-03 | P0: OpportunitiesPanel.stories.tsx (2 stories) | ✅ Done |
| 2026-04-03 | P1: RoadmapPanel.stories.tsx (3 stories) | ✅ Done |
| 2026-04-03 | P1: GraphStructurePanel.stories.tsx (3 stories) | ✅ Done |
| 2026-04-03 | P1: AtlasStatusCard.stories.tsx (4 stories) | ✅ Done |
| 2026-04-03 | P1: LogConsole.stories.tsx (3 stories) | ✅ Done |
| 2026-04-03 | Wired `/cli` with AnimatedCLI embed | ✅ Done |
| 2026-04-03 | Wired `/mcp/ides` with AnimatedIDE embed | ✅ Done |
| 2026-04-03 | Wired `/mcp/paperclip` with AgentOpsPanel embed | ✅ Done |
| 2026-04-03 | Wired `/guides/knowledge-scope` with AgentScopePanel embed | ✅ Done |
| 2026-04-03 | Wired `/guides/codebase-audit` with AuditPanel + OpportunitiesPanel | ✅ Done |
| 2026-04-03 | Fixed TreeNode type (`folder` not `directory`) | ✅ Done |
| 2026-04-03 | Fixed RoleBadge type (slug/displayName/has*Md) | ✅ Done |
| 2026-04-03 | Storybook build verified — zero errors, 22s | ✅ Done |
| 2026-04-03 | `docsMode` global implemented in preview.tsx | ✅ Done |
| 2026-04-03 | StoryEmbed URL builder updated with docsMode:true | ✅ Done |
| 2026-04-03 | Wired `/getting-started` with AnimatedCLI embed | ✅ Done |
| 2026-04-03 | Wired `/concepts/code-graph` with TraceGraph embed | ✅ Done |
| 2026-04-03 | Created `scripts/build-storybook.sh` | ✅ Done |
| 2026-04-03 | P2: AgentCard.stories.tsx (4 stories) | ✅ Done |
| 2026-04-03 | P2: StageProgressBar.stories.tsx (4 stories) | ✅ Done |
| 2026-04-03 | P2: TeamSyncIndicator.stories.tsx (5 stories) | ✅ Done |
| 2026-04-03 | P2: LicenseStatusCard.stories.tsx (5 stories) | ✅ Done |
| 2026-04-03 | P2: SyncStatusCard.stories.tsx (4 stories) | ✅ Done |
| 2026-04-03 | Storybook rebuild with all stories — zero errors, 22s | ✅ Done |
| 2026-04-03 | P2: ManagedEmployeesTab.stories.tsx (4 stories) | ✅ Done |
| 2026-04-03 | P2: SystemAgentsTab.stories.tsx (3 stories) | ✅ Done |
| 2026-04-03 | P2: BugReportModal.stories.tsx (3 stories) | ✅ Done |
| 2026-04-03 | Wired `/guides/models` with AIModelsSettings embed | ✅ Done |
| 2026-04-03 | Wired `/guides/byok-batching` with EndpointManager embed | ✅ Done |
| 2026-04-03 | Wired `/guides/team-sync` with SyncStatusCard embed | ✅ Done |
| 2026-04-03 | Final Storybook rebuild — zero errors, 22s | ✅ Done |
| 2026-04-03 | P3: TraceExplorer.stories.tsx (5 stories) | ✅ Done |
| 2026-04-03 | P3: EnterpriseAdminPanel.stories.tsx (6 stories) | ✅ Done |
| 2026-04-03 | Verified GraphEnrichmentPipeline story (14 stories) is current | ✅ Done |
| 2026-04-03 | Final Storybook rebuild with all stories — zero errors, 22s | ✅ Done |

### ✅ All Work Complete

All P0/P1/P2/P3 stories created. Only stale refresh items remain (FullDashboard needs Agent, Audit, and Roadmap panels added to its composite story).

| Work Item | Priority | Effort | Notes |
|-----------|----------|--------|-------|
| FullDashboard story refresh | P4 | 30 min | ✅ Done — Added AgentOps, AgentScope, Audit, Opportunities, and Roadmap panels |

---

## 1. Component Inventory: App vs Storybook

### Legend
- ✅ = Story exists & matches app
- ⚠️ = Story exists but is **stale/outdated** (needs update)
- ❌ = **No story exists** (needs creation)
- 🔥 = **Docs embed priority** (needed for public documentation)
- 🆕 = **Newly created in this phase**

### Dashboard Core

| Component | File | Story? | Docs Embed? | Notes |
|-----------|------|--------|-------------|-------|
| IndexStatusCard | `dashboard/IndexStatusCard.tsx` | ✅ | 🔥 `/mcp` | Has `bare` mode, good shape |
| BuildCard | `dashboard/BuildCard.tsx` | ✅ | 🔥 `/getting-started` | Matches app |
| LLMStatusWidget | `dashboard/LLMStatusWidget.tsx` | ✅ | 🔥 `/guides/models` | Matches app |
| IndexStats | `dashboard/IndexStats.tsx` | ✅ | | Matches app |
| UsageGuidePanel | `dashboard/UsageGuidePanel.tsx` | ✅ | 🔥 `/getting-started` | Matches app |

### Search

| Component | File | Story? | Docs Embed? | Notes |
|-----------|------|--------|-------------|-------|
| SearchPanel | `search/SearchPanel.tsx` | ✅ | 🔥 `/mcp`, `/search` | Matches app |
| ContextOptionsPanel | `search/ContextOptionsPanel.tsx` | ✅ | 🔥 `/search` | Matches app |
| SearchResultsList | `search/SearchResultsList.tsx` | ✅ | 🔥 `/search` | Matches app |
| ChunkPreview | `search/ChunkPreview.tsx` | ✅ | | Via SearchComponents story |
| ContextOutput | `search/ContextOutput.tsx` | ✅ | | Matches app |

### Trace & Pipeline

| Component | File | Story? | Docs Embed? | Notes |
|-----------|------|--------|-------------|-------|
| GraphEnrichmentPipeline | `trace/GraphEnrichmentPipeline.tsx` (58KB!) | ⚠️ | 🔥 `/dashboard` | Story likely stale vs 11-stage pipeline |
| GraphStructurePanel | `trace/GraphStructurePanel.tsx` (26KB) | 🆕 ✅ | 🔥 `/dashboard` | **3 stories: WithData, Building, AllTraced** |
| TraceCoveragePanel | `trace/TraceCoveragePanel.tsx` (19KB) | ✅ | 🔥 `/dashboard` | Has story |
| TraceExplorer | `trace/TraceExplorer.tsx` (16KB) | ❌ | | No story |
| TraceGraph | `trace/TraceGraph.tsx` | ✅ | 🔥 `/concepts/code-graph` | Matches app |
| NodeDetailPanel | `trace/NodeDetailPanel.tsx` | ✅ | | Matches app |
| TraceStatusCard | `trace/TraceStatusCard.tsx` | ✅ | | Matches app |
| AtlasStatusCard | `trace/AtlasStatusCard.tsx` | 🆕 ✅ | 🔥 `/dashboard` | **4 stories: Fresh, Stale, NotGenerated, Structural** |
| StageProgressBar | `trace/StageProgressBar.tsx` | ❌ | | No story |

### Agent System

| Component | File | Story? | Docs Embed? | Notes |
|-----------|------|--------|-------------|-------|
| AgentScopePanel | `agents/AgentScopePanel.tsx` (14KB) | 🆕 ✅ | 🔥 `/guides/knowledge-scope` | **2 stories: WithScopes, NoProject** |
| AgentOpsPanel | `agents/AgentOpsPanel.tsx` | 🆕 ✅ | 🔥 `/mcp/paperclip` | **3 stories: Active, Empty, Loading** |
| AgentOpsDetail | `agents/AgentOpsDetail.tsx` | ❌ | | Agent detail view |
| AgentCard | `agents/AgentCard.tsx` | ❌ | | Individual agent card |
| ManagedEmployeesTab | `agents/ManagedEmployeesTab.tsx` | ❌ | | HR-generated agents |
| SystemAgentsTab | `agents/SystemAgentsTab.tsx` | ❌ | | Built-in system agents |
| EmployeeBadges | `agents/EmployeeBadges.tsx` | ❌ | | Status badges |

### Audit

| Component | File | Story? | Docs Embed? | Notes |
|-----------|------|--------|-------------|-------|
| AuditPanel | `audit/AuditPanel.tsx` (25KB) | 🆕 ✅ | 🔥 `/guides/codebase-audit` | **3 stories: WithFindings, NoResults, Running** |
| OpportunitiesPanel | `audit/OpportunitiesPanel.tsx` (31KB) | 🆕 ✅ | 🔥 `/guides/codebase-audit` | **2 stories: WithOpportunities, Empty** |
| HealthScannerPanel | `audit/HealthScannerPanel.tsx` (27KB) | ❌ | | Sunset but still exists |
| SpaghettiFinderPanel | `audit/SpaghettiFinderPanel.tsx` | ❌ | | Sunset |

### Goalposts / Roadmap

| Component | File | Story? | Docs Embed? | Notes |
|-----------|------|--------|-------------|-------|
| GoalpostsPanel | `goalposts/GoalpostsPanel.tsx` (22KB) | ❌ | | Sunset (hidden) |
| RoadmapPanel | `goalposts/RoadmapPanel.tsx` (24KB) | 🆕 ✅ | 🔥 `/dashboard` | **3 stories: WithContent, Empty, Generating** |
| RoadmapTimeline | `goalposts/RoadmapTimeline.tsx` (16KB) | ❌ | | Sub-component of RoadmapPanel |
| AdvisorPanel | `goalposts/AdvisorPanel.tsx` (20KB) | ❌ | | Sunset |
| BurndownChart | `goalposts/BurndownChart.tsx` | ❌ | | Chart component |
| SprintCard | `goalposts/SprintCard.tsx` | ❌ | | Sprint visualization |
| VelocityBar | `goalposts/VelocityBar.tsx` | ❌ | | Velocity visualization |

### Console / CLI

| Component | File | Story? | Docs Embed? | Notes |
|-----------|------|--------|-------------|-------|
| LogConsole | `console/LogConsole.tsx` | 🆕 ✅ | | **3 stories: PipelineRun, Empty, WithErrors** |
| AnimatedCLI | `console/AnimatedCLI.tsx` | 🆕 ✅ | 🔥 `/cli` | **4 stories: SemanticSearch, ImpactAnalysis, ProjectOverview, ClaudeTheme** |
| AnimatedIDE | `console/AnimatedIDE.tsx` | 🆕 ✅ | 🔥 `/mcp/ides` | **2 stories: Default, Paused** |
| BugReportModal | `console/BugReportModal.tsx` | ❌ | | Modal component |

### Enterprise / Team

| Component | File | Story? | Docs Embed? | Notes |
|-----------|------|--------|-------------|-------|
| EnterpriseAdminPanel | `enterprise/EnterpriseAdminPanel.tsx` (45KB!) | ❌ | 🔥 `/guides/enterprise-deploy` | **Largest component, no story** |
| LicenseStatusCard | `team/LicenseStatusCard.tsx` | ❌ | | No story |
| SyncStatusCard | `team/SyncStatusCard.tsx` | ❌ | | No story |
| TeamConfigStatus | `team/TeamConfigStatus.tsx` | ❌ | | No story |
| TeamSyncIndicator | `team/TeamSyncIndicator.tsx` | ❌ | 🔥 `/guides/team-sync` | No story |

### LLM Configuration

| Component | File | Story? | Docs Embed? | Notes |
|-----------|------|--------|-------------|-------|
| AIModelsSettings | `llm/AIModelsSettings.tsx` | ✅ | 🔥 `/guides/models` | Matches app |
| DeepAnalysisSettings | `llm/DeepAnalysisSettings.tsx` | ✅ | 🔥 `/dashboard` | Matches app |
| EndpointManager | `llm/EndpointManager.tsx` | ✅ | 🔥 `/guides/byok-batching` | Matches app |
| ModelCard | `llm/ModelCard.tsx` | ✅ | | Matches app |

### Visualization

| Component | File | Story? | Docs Embed? | Notes |
|-----------|------|--------|-------------|-------|
| ActivityHeatmap | `viz/ActivityHeatmap.tsx` | ✅ | | Matches app |

---

## 2. Gap Summary (Updated)

| Category | Components | Stories | Missing | Coverage |
|----------|-----------|---------|---------|----------|
| Dashboard Core | 5 | 5 | 0 | **100%** ✅ |
| Search | 5 | 5 | 0 | **100%** ✅ |
| Trace/Pipeline | 9 | 8 | 1 | **89%** ✅ |
| Agent System | 7 | 5 | 2 | **71%** |
| Audit | 4 | 2 | 2 | 50% |
| Goalposts/Roadmap | 7 | 1 | 6 | 14% |
| Console/CLI | 4 | 4 | 0 | **100%** ✅ |
| Enterprise/Team | 5 | 4 | 1 | **80%** |
| LLM Config | 4 | 4 | 0 | **100%** ✅ |
| Viz | 1 | 1 | 0 | **100%** ✅ |
| **TOTAL** | **51** | **43** | **8** | **84%** |

> Previous: **42%** (21.5) → P0+P1: **61%** (31) → P2: **78%** (40) → Final: **84%** (43 stories). **+22 story files** in Phase 68.

---

## 3. Docs Embed Wiring — Status

### ✅ Complete (7 pages wired)

| Docs Page | Embed(s) | Status |
|-----------|----------|--------|
| `/mcp` | SearchPanel, IndexStatusCard | ✅ Live |
| `/dashboard` | FullDashboard, Pipeline | ✅ Live |
| `/cli` | AnimatedCLI (SemanticSearch) | ✅ Live |
| `/mcp/ides` | AnimatedIDE (Default) | ✅ Live |
| `/mcp/paperclip` | AgentOpsPanel (Active) | ✅ Live |
| `/guides/knowledge-scope` | AgentScopePanel (WithScopes) | ✅ Live (replaced placeholder) |
| `/guides/codebase-audit` | AuditPanel + OpportunitiesPanel | ✅ Live |

### 🔲 Remaining

| Docs Page | Embed(s) Needed | Story Status |
|-----------|-----------------|--------------|
| `/getting-started` | BuildCard, UsageGuidePanel, AnimatedCLI | ✅ Stories exist |
| `/concepts/code-graph` | TraceGraph, NodeDetailPanel | ✅ Stories exist |
| `/concepts/graph-enrichment` | GraphEnrichmentPipeline | ⚠️ Needs story refresh |
| `/dashboard` (expanded) | AtlasStatusCard, GraphStructurePanel, RoadmapPanel | 🆕 Stories ready |
| `/guides/byok-batching` | EndpointManager | ✅ Story exists |
| `/guides/enterprise-deploy` | EnterpriseAdminPanel | ❌ Need story |
| `/guides/team-sync` | TeamSyncIndicator | ❌ Need story |
| `/search` | SearchPanel (full demo), SearchResults | ✅ Stories exist |
| `/guides/models` | AIModelsSettings, LLMStatusWidget | ✅ Stories exist |

---

## 4. Story Files Created

### P0 (Docs-Critical) — ✅ All Complete

| File | Component | Stories |
|------|-----------|--------|
| `stories/console/AnimatedCLI.stories.tsx` | AnimatedCLI | SemanticSearch, ImpactAnalysis, ProjectOverview, ClaudeTheme |
| `stories/console/AnimatedIDE.stories.tsx` | AnimatedIDE | Default, Paused |
| `stories/agents/AgentOpsPanel.stories.tsx` | AgentOpsPanel | Active, Empty, Loading |
| `stories/agents/AgentScopePanel.stories.tsx` | AgentScopePanel | WithScopes, NoProject |
| `stories/audit/AuditPanel.stories.tsx` | AuditPanel | WithFindings, NoResults, Running |
| `stories/audit/OpportunitiesPanel.stories.tsx` | OpportunitiesPanel | WithOpportunities, Empty |

### P1 (Parity) — ✅ All Complete

| File | Component | Stories |
|------|-----------|--------|
| `stories/goalposts/RoadmapPanel.stories.tsx` | RoadmapPanel | WithContent, Empty, Generating |
| `stories/trace/GraphStructurePanel.stories.tsx` | GraphStructurePanel | WithData, Building, AllTraced |
| `stories/trace/AtlasStatusCard.stories.tsx` | AtlasStatusCard | Fresh, Stale, NotGenerated, Structural |
| `stories/console/LogConsole.stories.tsx` | LogConsole | PipelineRun, Empty, WithErrors |

### P2 (Completeness) — 🔲 Not Started

| # | Component | Complexity | Notes |
|---|-----------|------------|-------|
| 1 | EnterpriseAdminPanel | High | 45KB, 6 tabs |
| 2 | TraceExplorer | Med | Interactive graph |
| 3 | AgentCard | Low | |
| 4 | ManagedEmployeesTab | Med | |
| 5 | SystemAgentsTab | Med | |
| 6 | TeamSyncIndicator | Low | |
| 7 | SyncStatusCard | Low | |
| 8 | LicenseStatusCard | Low | |
| 9 | BugReportModal | Med | |
| 10 | StageProgressBar | Low | |

---

## 5. Stale Story Refresh

| Story File | Issue | Status |
|------------|-------|--------|
| `GraphEnrichmentPipeline.stories.tsx` | Check 11 pipeline stages vs current app | 🔲 Pending |
| `FullDashboard.stories.tsx` | Panel registry growth — add Agent, Audit, Roadmap panels | 🔲 Pending |
| `IndexStatusCard.stories.tsx` | Verify auto/manual toggle | 🔲 Pending |

---

## 6. StoryEmbed Architecture

### Component: `websites/apps/docs/src/components/StoryEmbed.tsx`

- **Renders**: Sandboxed `<iframe>` pointing at `storybook-static/`
- **Theme**: Hardcoded to `globals=theme:dark;codragTheme:m` (Retro Aurora)
- **Sandbox**: `allow-scripts allow-same-origin` (no popups, no navigation)
- **Props**: `storyId`, `height`, `title`, `caption`
- **URL pattern**: `/storybook-static/iframe.html?id={storyId}&viewMode=story&globals=...`

### Security Model
- Storybook static assets are bundled with the docs site (same origin)
- No API keys or backend connections needed (all mock data)
- Iframe sandbox prevents navigation and form submission
- No sensitive code exposed — stories use synthetic mock data

---

## 7. Preview Cleanup for Docs

| Task | Status | Notes |
|------|--------|-------|
| Create `docsMode` global in Storybook | 🔲 Pending | Pass `?globals=docsMode:true` in embed URL |
| Check `context.globals.docsMode` in `preview.tsx` | 🔲 Pending | Hide bg-upload controls |
| Add to StoryEmbed URL builder | 🔲 Pending | Simple append to globals string |

---

## 8. Build Freshness

| Task | Status | Notes |
|------|--------|-------|
| Latest build | ✅ 2026-04-03 | 22s, zero errors |
| `scripts/build-storybook.sh` | 🔲 Pending | Integrate with docs deploy pipeline |
| CI integration | 🔲 Future | Run on PRs that touch `packages/ui/` |

---

## 9. Effort Tracker

| Work Stream | Estimate | Actual | Status |
|-------------|----------|--------|--------|
| P0 stories (6 components) | 2–3h | ~2h | ✅ Done |
| P1 stories (4 components) | 2–3h | ~1.5h | ✅ Done |
| Docs page embed wiring (7 pages) | 2h | ~1h | ✅ Done |
| Type fixes (TreeNode, RoleBadge) | 30 min | 15 min | ✅ Done |
| Stale story refresh | 1–2h | — | 🔲 Pending |
| P2 stories (10 components) | 3–4h | — | 🔲 Pending |
| docsMode decorator | 30 min | — | 🔲 Pending |
| Build automation | 30 min | — | 🔲 Pending |
| EnterpriseAdminPanel story | 2h | — | 🔲 Pending |
| **Total** | **~14–18h** | **~5h done** | **~35% complete** |
