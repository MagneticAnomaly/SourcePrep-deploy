# Phase 137 — Asset Inventory

> Snapshot of what's available to embed in docs pages, as of 2026-05-14.
> Storybook auto-deploys from `main`; this list will drift — re-derive from
> `find packages/ui/src/stories -name "*.stories.tsx"` and
> `grep -E "^const [A-Za-z]+(Demo|Script): CliScript" demo-scripts.ts`
> if you suspect staleness.

## How to embed each asset type

### Storybook iframe (`<StoryEmbed>`)

```tsx
import { StoryEmbed } from '../../components/StoryEmbed';

<StoryEmbed
  storyId="dashboard-widgets-searchpanel--default"   // see story ID conventions below
  height={400}                                        // px or CSS string; default 400
  title="Search Panel"                                // a11y; defaults to humanized story name
  caption="Optional caption shown below the iframe"
/>
```

**Story ID format:** Storybook generates the ID from the `title` field in
each `.stories.tsx` file plus the export name. For a story titled
`Dashboard/Widgets/SearchPanel` with export `Default`, the ID is
`dashboard-widgets-searchpanel--default` (lowercased, slashes → hyphens,
double-hyphen before the export). Open the story in
`https://storybook.sourceprep.io` and the URL hash gives you the exact ID.

**Theme:** All docs embeds are locked to dark + Retro Aurora (`prepTheme:m`)
+ `docsMode:true` by `StoryEmbed.tsx:48`. Per-page theme overrides are not
available; if you need a different theme for a specific embed, that requires
a `StoryEmbed.tsx` change (out of scope for this phase).

### Animated CLI / IDE

The animation components live in `@prep/ui` and are exported via
`packages/ui/src/index.ts`. Import them in docs pages and pass a `script`
prop from `demo-scripts.ts`:

```tsx
import { AnimatedCLI, prepOverviewDemo } from '@prep/ui';

<AnimatedCLI script={prepOverviewDemo} className="my-6" />
```

The animations are theme-aware via CSS variables; in docs they'll inherit the
docs site's dark theme automatically. The `loop` and `loopDelayMs` properties
are baked into the script definitions in `demo-scripts.ts`.

---

## Storybook stories — by category

Counts as of 2026-05-14. Each entry is a `.stories.tsx` file; many files
export multiple variants. Hover the story in Storybook to see all variants
for that file.

### Dashboard panels (7 files) — `stories/dashboard/`

The "heroes" for docs embedding. Use these wherever the docs describe what a
panel does or shows.

| Story file | What it shows |
|---|---|
| `BuildCard.stories.tsx` | Live build progress card with stage breakdown |
| `ContextOutput.stories.tsx` | Rendered context output the agent receives |
| `FullDashboard.stories.tsx` | Composed dashboard — multiple panels arranged |
| `IndexStats.stories.tsx` | Index size, file count, embedding model |
| `IndexStatusCard.stories.tsx` | Index health + last-built timestamp |
| `LLMStatusWidget.stories.tsx` | Configured LLM endpoints + health |
| `UsageGuidePanel.stories.tsx` | Onboarding hint panel |

### Search (2 files) — `stories/search/`

| Story file | What it shows |
|---|---|
| `SearchComponents.stories.tsx` | Smaller search building blocks |
| `SearchPanel.stories.tsx` | Full search panel with query, results, options |

### Trace / graph (14 files) — `stories/trace/`

The largest category. Use these on `/how-it-works/code-graph`,
`/how-it-works/graph-enrichment`, and dashboard pages describing trace.

| Story file | What it shows |
|---|---|
| `AtlasLensPanel.stories.tsx` | Atlas lens projection panel |
| `GraphEnrichmentPipeline.stories.tsx` | The 15-stage pipeline view |
| `GraphStructurePanel.stories.tsx` | Structural graph panel |
| `NodeDetailPanel.stories.tsx` | Per-node detail drawer |
| `ProvenanceChip.stories.tsx` | Stage-provenance chips (match/drift/healed) |
| `RebuildDropdown.stories.tsx` | Rebuild controls (fast/deep) |
| `RebuildingRow.stories.tsx` | Active rebuild row |
| `RecoverStagePanel.stories.tsx` | Stage recovery panel (Phase 128) |
| `StageProgressBar.stories.tsx` | Stage progress bar |
| `SymbolSearch.stories.tsx` | Symbol search UI |
| `TraceCoveragePanel.stories.tsx` | Trace coverage panel |
| `TraceExplorer.stories.tsx` | Full trace explorer |
| `TraceGraph.stories.tsx` | The graph itself |
| `TraceStatusCard.stories.tsx` | Trace status summary card |

### LLM / model config (5 files) — `stories/llm/`

| Story file | What it shows |
|---|---|
| `AIModelsSettings.stories.tsx` | Models settings tab |
| `AdvancedLLMSettings.stories.tsx` | Advanced LLM knobs |
| `DeepAnalysisSettings.stories.tsx` | Deep-analysis (enrichment) toggles |
| `EndpointManager.stories.tsx` | Endpoint manager (BYOK config) |
| `ModelCard.stories.tsx` | Single model card |

### Agents (4 files) — `stories/agents/`

| Story file | What it shows |
|---|---|
| `AgentCard.stories.tsx` | Agent card |
| `AgentOpsPanel.stories.tsx` | Agent ops panel |
| `ManagedEmployeesTab.stories.tsx` | Managed-employees tab |
| `SystemAgentsTab.stories.tsx` | System-agents tab |

### Audit (2 files) — `stories/audit/`

| Story file | What it shows |
|---|---|
| `AuditPanel.stories.tsx` | The audit findings panel |
| `OpportunitiesPanel.stories.tsx` | Opportunities panel |

### Concepts (no concepts/ story dir yet)

Note: there's no `stories/concepts/` directory. Concepts UI lives in
`packages/ui/src/components/concepts/ConceptsPanel.tsx` but isn't currently
storied. **Gap** — Phase 137 audit may flag this if a concepts page wants a
live embed.

### Enterprise / Team / Project / Goalposts / Watch / Status / Layout

Single-purpose categories, smaller story counts:

- `stories/enterprise/EnterpriseAdminPanel.stories.tsx` (1)
- `stories/goalposts/RoadmapPanel.stories.tsx` (1)
- `stories/team/`: `LicenseStatusCard`, `SyncStatusCard`, `TeamSyncIndicator` (3)
- `stories/project/`: `FolderTree`, `FolderTreePanel`, `ProjectSettingsPanel` (3)
- `stories/watch/`: `WatchControls`, `WatchStatusIndicator` (2)
- `stories/status/`: `BuildProgress`, `StatusBadge`, `StatusCard` (3)
- `stories/layout/`: `ModularDashboard`, `PanelChrome`, `PanelPicker` (3)
- `stories/viz/ActivityHeatmap.stories.tsx` (1)
- `stories/docs/MobileDocsDrawer.stories.tsx` (1)

### Foundations / Primitives / Molecules / Patterns

Lower-level building blocks. Less likely to be useful as docs embeds (they're
abstractions, not panels), but listed for completeness:

- `stories/foundations/`: `Colors`, `Spacing`, `Typography`
- `stories/primitives/`: `Button`, `PathInput`, `SearchableSelect`, `Select`
- `stories/molecules/`: `CitationBlock`, `CopyButton`
- `stories/patterns/StatePatterns.stories.tsx`
- `stories/navigation/`: `AppShell`, `SidebarAIGateway`, `SidebarPipelineQueue`

### Console / animations

The animation components are also storied so design can iterate on them:

- `stories/console/AnimatedCLI.stories.tsx` — variants: `SemanticSearch`,
  `ImpactAnalysis`, `ProjectOverview`, `ClaudeTheme`
- `stories/console/AnimatedIDE.stories.tsx` — variants: `Default`, `Paused`
- `stories/console/BugReportModal.stories.tsx`
- `stories/console/LogConsole.stories.tsx`

These can be embedded via `<StoryEmbed>` *or* used as live React components
via the `AnimatedCLI` / `AnimatedIDE` imports (next section). Prefer the
React-component path for live demos; iframe-embed them only if you need the
themed Storybook chrome.

### Marketing / Site / Demos / Research

Mostly used on the marketing site, but available:

- `stories/site/`: `SiteFooter`, `SiteHeader`
- `stories/marketing/`: `FeatureBlocks`, `MarketingHero`, plus a research/
  subfolder with `ResearchAppendix`, `ResearchHero`, `ResearchSection`,
  `SourceCard`, `SourceFilterChips`, `SourceSpotlight`
- `stories/demos/`: `Dashboard`, `DesignSystem`

---

## CLI / IDE animation scripts — `demo-scripts.ts`

The scripts are the source data for `<AnimatedCLI>` and `<AnimatedIDE>`.
There are 21 named `const` scripts plus 7 grouped arrays:

### Per-tool grouped arrays (preferred for variety)

| Export | Contents |
|---|---|
| `prepDemos: CliScript[]` | All `prep` ambient-context demos |
| `prepSearchDemos: CliScript[]` | All `prep_search` demos |
| `prepImpactDemos: CliScript[]` | All `prep_impact` demos |
| `prepAuditDemos: CliScript[]` | All `prep_audit` demos |
| `prepObserveDemos: CliScript[]` | All `prep_observe` demos |
| `prepConceptsDemos: CliScript[]` | All `prep_concepts` demos |
| `ideDemos: CliScript[]` | All IDE-style demos (for `<AnimatedIDE>`) |

### "First demo of each tool" convenience exports

If you just want one canonical demo per tool:

| Export | Use case |
|---|---|
| `prepOverviewDemo` | "What does `prep` show me?" — most-used `prep` demo |
| `prepSearchDemo` | First `prep_search` demo |
| `prepImpactDemo` | First `prep_impact` demo |
| `prepAuditDemo` | First `prep_audit` demo |
| `prepObserveDemo` | First `prep_observe` demo |
| `prepConceptsDemo` | First `prep_concepts` demo |
| `ideDemoScript` | First IDE demo |

### Full named-script inventory (21)

`prep` (3):
- `prepRateLimitingDemo` — agent asks "where does rate limiting fit?"; `prep` returns module map
- `prepTldrOverviewDemo` — agent asks "tldr on this codebase"; `prep` returns structural summary
- `prepBuildWebhookDemo` — agent asks "add a webhook endpoint"; `prep` returns relevant hub files

`prep_search` (3):
- `searchRetryReuseDemo`
- `searchMaxConnectionsDemo`
- `searchBuildWorkerDemo`

`prep_impact` (3):
- `impactDeleteUnusedDemo`
- `impactExtractServiceDemo`
- `impactAsyncMigrationDemo`

`prep_audit` (3):
- `auditPrSanityCheckDemo`
- `auditSecurityScanDemo`
- `auditTightenTypesDemo`

`prep_observe` (3):
- `observeCachingRecallDemo`
- `observeInvestigationRecallDemo`
- `observeSaveOwnershipDemo`

`prep_concepts` (3):
- `conceptsTransactionRuleDemo`
- `conceptsQueuePitfallsDemo`
- `conceptsBuildRefundDemo`

IDE (3):
- `ideDoubleSubmitFixDemo`
- `ideLoadingSkeletonDemo`
- `ideAddCsvExportDemo`

---

## What's missing (initial gap list)

These are gaps observed during inventory; will be refined during the page
audit in `03_page_audit.md`:

1. **No concepts/ Storybook stories.** `ConceptsPanel` isn't storied; pages
   like `/how-it-works/indexing` would benefit from a live concepts panel embed.
2. **No "scope picker" / "knowledge scope" story.** The Scope panel is
   referenced in onboarding and `/guides/knowledge-scope` but there's no
   dedicated story for it. Closest matches: `FolderTreePanel`,
   `ProjectSettingsPanel`.
3. **No pricing/usage story.** `/guides/byok-batching` and
   `/guides/model-advisor` mention cost-tier UI but there's no story for
   the cost-banner / token-counter panel.
4. **No troubleshooting story.** `/troubleshooting` is text-heavy with no
   embed; that's probably correct, but a small `BugReportModal` embed near
   "How to file a bug" could fit.
5. **No "graph scope queue" story** matching the dashboard panel by the same
   name. Closest match: `FolderTreePanel`.

These get re-evaluated during the per-page audit; the audit may surface
additional gaps and may remove ones above if a closer-fit story exists that
I missed.
