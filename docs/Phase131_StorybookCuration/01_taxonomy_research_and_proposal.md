# Storybook Taxonomy — Research and Proposal

**Status**: Draft (2026-05-08)
**Author**: TBD
**Companion to**: `00_curation_plan.md` (this is the §5.2 follow-up that organizes the curated set)

---

## 1. Why a new taxonomy

The current title hierarchy grew organically across phases. The audit found:

- `Console/` mixes marketing demos (`AnimatedCLI`, `AnimatedIDE`) with internal product surfaces (`LogConsole`, `BugReportModal`). The user flagged this directly: *"Console should go in Website section."*
- `Phase 119/` is a top-level prefix — internal-process artifact that must not appear in public navigation.
- `Trace/` exists as a top-level **and** as `Dashboard/Widgets/Trace/` — same domain split across two locations.
- `Settings/SettingRow` is a top-level entry by itself while `Dashboard/Widgets/Settings/*` holds six other settings stories — same concern split across two locations.
- Inconsistent suffix conventions (`Panel` vs `Card` vs `Widget` — already flagged in `docs/Phase13_Storybook/previous-app-legacy-research/SCHOOL_AND_ENTERPRISE_INSPIRATIONS.md`).
- `Goalposts/RoadmapPanel` is a one-entry top-level group.
- Inconsistent depth: `Foundations/Primitives/Button` is three levels; `Audit/AuditPanel` is two; `Phase 119/ProbeButton` is two but with a wrong root.

Goal: a taxonomy that reads cleanly to an outside design engineer, separates product UI from marketing UI (the user's explicit ask), and matches the patterns of mature design systems.

---

## 2. Research — how mature design systems organize their components

Three references, each representing a different organizing principle.

### 2.1 GitHub Primer — product-focused split

Top-level categories at primer.style:

- **Product UI** — the design system for GitHub's product surfaces.
- **Brand UI** — for digital marketing experiences (separate site at `primer.style/brand`).
- **Brand Toolkit** — at `brand.github.com`, for branded content creation.
- Cross-cutting: **Accessibility**, **Octicons** (icons), **Primitives** (color/spacing/typography tokens).

Insight: Primer doesn't try to make one Storybook serve two audiences. Product UI and marketing components live in **different surfaces** with **shared foundations** underneath.

### 2.2 Atlassian Design System — functional grouping

Top-level categories at atlassian.design:

1. Forms and inputs
2. Images and icons
3. Layout and structure
4. Loading
5. Messaging
6. Navigation
7. Overlays and layering
8. Status indicators
9. Text and data display
10. Primitives (Box, Stack, Flex)
11. Libraries (tokens, CSS utilities, motion)
12. Tooling (providers, lint plugins)
13. Deprecated

Insight: Components are grouped by **what they do for the user**, not by which app uses them. A `Button` lives under "Forms and inputs" regardless of where it appears.

### 2.3 Shopify Polaris — functional grouping (close cousin)

1. Actions
2. Layout and structure
3. Selection and input
4. Images and icons
5. Feedback indicators
6. Typography
7. Tables
8. Lists
9. Navigation
10. Overlays
11. Utilities
12. Deprecated

Insight: Same shape as Atlassian — categories named after **user intent**.

### 2.4 Internal prior research

`docs/Phase13_Storybook/previous-app-legacy-research/` already studied this for Halley:
- `DESIGN_SYSTEMS_RESEARCH.md` — comparative analysis of shadcn/ui, Radix Themes, Tailwind UI, custom, hybrid.
- `SCHOOL_AND_ENTERPRISE_INSPIRATIONS.md` — inspirations from Cranbrook/Yale/RISD/CalArts plus IBM Carbon, Atlassian, Polaris, Microsoft Fluent, NN/g.
- `COMPONENT_INVENTORY.md` — the source-of-truth inventory.
- Decision: **hybrid posture** — different surfaces (product / marketing) get different visual postures while sharing foundations.

This Phase 131 work continues that line, applying it to our Storybook organization.

---

## 3. Insights for SourcePrep

We have **four distinct consumer surfaces** for the same component package:

| Surface | Where it lives | Audience |
|---|---|---|
| Tauri dashboard | `src/prep/dashboard/` | Power users running the desktop app |
| VS Code extension | `packages/vscode/` | Developers in VS Code |
| Marketing site | `websites/apps/marketing/` (sourceprep.io) | Prospective customers |
| Docs site | `websites/apps/docs/` (docs.sourceprep.io) | Developers learning the product |

The Tauri and VS Code surfaces share most of `@prep/ui`. The marketing/docs sites consume **different** components — heroes, feature blocks, animated demos, research/citation primitives.

**This maps cleanly to Primer's Product UI / Brand UI split.** It does *not* map cleanly to Atlassian's purely-functional grouping, because we'd lose the signal of which components are part of the *product* vs which are *marketing surface only*.

So the proposed pattern is: **Primer-style top-level split + Atlassian-style functional grouping within each surface.**

---

## 3.5b Reconciliation with internal source-of-truth docs (added after prep MCP review, 2026-05-08)

A second pass via the `prep` MCP surfaced two pre-existing internal documents that needed to be reconciled against this proposal:

### `packages/ui/src/COMPONENT_ARCHITECTURE.md`

The original Phase 02 component spec organizes components into **five functional categories** at the file-system level: `status/`, `navigation/`, `search/`, `context/`, `patterns/`. Its §"Storybook Organization" prescribed a matching 5-folder Storybook tree.

That doc is **stale relative to the current state**: the codebase has since grown to 28 directories under `packages/ui/src/components/` (agents, architecture, audit, concepts, concurrency, console, context, dashboard, docs, enterprise, goalposts, layout, llm, marketing, navigation, patterns, pipeline, primitives, project, search, settings, site, status, team, trace, viz, watch). The original 5-category Storybook tree never updated to reflect that growth.

**Phase 131 supersedes the Storybook organization section of `COMPONENT_ARCHITECTURE.md`.** The file-system layout (the 28 directories) stays as-is — file moves are out of scope. Only Storybook `title:` strings change.

### `packages/ui/src/components/dashboard/` — naming conflict

The directory `packages/ui/src/components/dashboard/` holds only **five components**: `IndexStatusCard`, `IndexStats`, `LLMStatusWidget`, `UsageGuidePanel`, `BuildCard`. It's a misleading name — the directory is a small "overview-widgets" subset, not the dashboard surface as a whole.

This proposal's top-level `Dashboard/` Storybook section means *the entire desktop-app surface*, not the 5 components in `components/dashboard/`. The five files inside that directory get split across `Dashboard/Index/`, `Dashboard/Build/`, and `Dashboard/LLM/` per §4.1.a.

**Recommendation**: live with the directory misnomer for now. A future cleanup could rename the directory to `components/overview/` (small refactor, touches 5 files + their imports). Not blocking Phase 131; tracked as an open question (§6.7).

### `packages/ui/src/REFACTOR_PLAN.md`

Phase 1/2/3 component extraction plan from earlier work. Listed extractions are mostly complete (the components referenced exist now in `packages/ui/src/components/`). No taxonomy implications.

## 3.5 Hard rules (decided 2026-05-08)

These are non-negotiable rules the taxonomy must satisfy. Every story migration is checked against them.

1. **All dashboard-app panels live under `Dashboard/`.** No more parallel top-level sections (`Trace/`, `Pipeline/`, `Audit/`, `Goalposts/`, `Agents/`, `Team/`, `Application/`, `Enterprise/`, etc.) for components that render inside the dashboard. If it's a panel mounted by the dashboard app or a power-user feature surface, its story title starts with `Dashboard/`.
2. **Modal components get their own top-level `Modals/` section** — `BugReportModal`, `ConfirmDialog`, future modal flows. Modals are not Dashboard panels even though some are launched from the dashboard; they have a distinct interaction model (overlay, dismissable, focus-trapped) and should be browseable as a class.
3. **Marketing components live under `Website/`** — heroes, feature blocks, demos, research/citation primitives, site header/footer. The Console section is dissolved; CLI/IDE animations are demos and belong here.
4. **`Console/` is dissolved entirely.** It mixed two unrelated kinds of components (marketing animations + dashboard log surfaces) and the name was misleading.
5. **Foundations / Primitives / Patterns are cross-cutting and surface-agnostic.** Anything specific to the dashboard or website goes under those top-levels — not under Foundations.
6. **No empty-shell single-entry top-levels.** If only one story would live there, it belongs in a parent section instead.

## 4. Proposed taxonomy

The Storybook sidebar reads:

```
Foundations/
├── Introduction (existing MDX)
├── Accessibility (existing MDX)
├── Visual Directions (existing MDX)
└── Tokens/
    ├── Colors
    ├── Spacing
    └── Typography

Primitives/                          (atomic UI building blocks)
├── Button
├── Select
├── SearchableSelect
├── Toggle
├── SettingRow                       (← MOVED from top-level Settings/)
├── Section                          (← MOVED from top-level Settings/)
├── PathInput
├── InfoTooltip
├── CopyButton                       (← MOVED from Foundations/Molecules/)
├── CitationBlock                    (← MOVED from Foundations/Molecules/)
├── EmptyState
├── ProgressIndicator
└── StatusBadge

Patterns/                            (composed primitives, UX recipes)
├── State Patterns                   (← MOVED from Foundations/Patterns/)
├── Keyboard Shortcuts               (← MOVED from Foundations/Patterns/)
├── Panel Chrome                     (← MOVED from Dashboard/Primitives/)
└── Panel Picker                     (← MOVED from Dashboard/Primitives/)

Modals/                              (NEW — overlay/dismissable surfaces)
├── Bug Report Modal                 (← MOVED from Console/, after sanitization)
└── Confirm Dialog                   (← MOVED from Primitives/)

Dashboard/                           (every dashboard-app surface — Tauri + VS Code)
├── Introduction                     (existing MDX)
├── Layouts/
│   ├── App Shell                    (← MOVED from Application/Navigation/)
│   ├── Full Dashboard
│   └── Modular Dashboard
├── Search/
│   ├── Search Panel
│   ├── Search Components
│   ├── Symbol Search
│   ├── Context Options
│   └── Context Output
├── Trace/                           (consolidates top-level Trace/ AND Dashboard/Widgets/Trace/)
│   ├── Graph
│   ├── Atlas Lens                   (← MOVED from top-level Trace/)
│   ├── Graph Structure              (← MOVED from top-level Trace/, currently excluded)
│   ├── Coverage                     (currently excluded — TraceCoveragePanel)
│   ├── Node Detail
│   ├── Trace Explorer               (← MOVED from top-level Trace/, currently excluded)
│   └── Status Card
├── Pipeline/                        (currently excluded — Phase 119 rename pending)
│   ├── Concurrency Health
│   ├── Capacity Health
│   ├── Recent Swarm Logs
│   ├── Probe Button
│   ├── Plan Dropdown
│   ├── Sidebar Pipeline Queue
│   ├── Swarm Activity
│   └── Sidebar AI Gateway
├── Build/
│   ├── Build Card
│   ├── Build Progress
│   ├── Stage Progress               (currently excluded)
│   ├── Rebuild Dropdown             (currently excluded)
│   ├── Rebuilding Row               (currently excluded)
│   └── Recover Stage                (currently excluded)
├── Index/
│   ├── Index Status Card
│   ├── Index Stats
│   ├── Activity Heatmap
│   └── Usage Guide
├── Project/
│   ├── Folder Tree
│   ├── Folder Tree Panel
│   ├── File Explorer
│   ├── Project Settings
│   └── Project Tabs
├── LLM/
│   ├── LLM Status
│   ├── Endpoint Manager
│   ├── Model Card
│   ├── AI Models Settings           (currently excluded — Phase 119 rename pending)
│   ├── Advanced LLM Settings
│   └── Deep Analysis Settings
├── Status/
│   ├── Status Badge
│   └── Status Card
├── Watch/
│   ├── Watch Controls
│   └── Status Indicator
├── Navigation/                      (NEW — addressed by prep review; currently no stories)
│   ├── Sidebar                      (when story is authored)
│   ├── Project List                 (when story is authored)
│   └── Project Tabs                 (when story is authored)
├── Architecture/                    (NEW — addressed by prep review; currently no stories)
│   ├── Architecture Diagram Panel   (8+ files in components/architecture/)
│   ├── Architecture Diagram Detail
│   ├── Diagram Toolbar
│   └── Breadcrumb Nav
├── Concepts/                        (NEW — addressed by prep review; currently no stories)
│   ├── Concepts Panel
│   └── Concepts Detail
├── Visualization/                   (NEW — viz components from components/viz/)
│   ├── Activity Heatmap             (currently Dashboard/Widgets/ActivityHeatmap)
│   ├── Index Health Panel           (when story is authored)
│   └── Token Budget Panel           (when story is authored)
├── Console/                         (NEW Dashboard subsection)
│   └── Log Console                  (← MOVED from top-level Console/, currently excluded)
├── Audit/                           (currently excluded — mock-data sweep pending)
│   ├── Audit Panel
│   └── Opportunities Panel
├── Roadmap/                         (currently excluded — mock-data sweep pending)
│   └── Roadmap Panel                (← MOVED from top-level Goalposts/)
├── Enterprise/                      (currently excluded — internal admin surface)
│   └── Enterprise Admin Panel
├── Agents/                          (← MOVED from top-level Agents/)
│   ├── Agent Card
│   ├── Agent Ops
│   ├── Managed Employees
│   └── System Agents
└── Team/                            (← MOVED from top-level Team/)
    ├── License Status
    ├── Sync Status
    └── Team Sync Indicator

Website/                             (sourceprep.io marketing + docs surfaces)
├── Layout/
│   ├── Site Header
│   └── Site Footer
├── Marketing/
│   ├── Hero
│   └── Feature Blocks
├── Demos/                           (NEW — was Console/)
│   ├── Animated CLI                 (← MOVED from Console/)
│   └── Animated IDE                 (← MOVED from Console/)
├── Research/
│   ├── Research Hero
│   ├── Research Section
│   ├── Research Appendix
│   ├── Source Card
│   ├── Source Filter Chips
│   └── Source Spotlight
└── Docs/                            (NEW — components/docs/ for docs.sourceprep.io)
    ├── Docs Layout                  (when story is authored)
    ├── Docs Sidebar Nav             (when story is authored)
    └── Table Of Contents            (when story is authored)
```

> **Naming note**: this version uses `Dashboard/` (concrete, matches the Tauri app) instead of the earlier draft's `Product UI/` (abstract). VS Code extension components, when they earn their own stories, can live under `Dashboard/VS Code/` rather than splitting the surface tree.

### 4.1 Currently misplaced — full mapping

Every story whose current `title` is wrong under §3.5 hard rules. Currently-public stories first, then currently-excluded (with their planned destinations once content is sanitized).

#### 4.1.a Currently public — needs rename

| Current title | Target title | Reason |
|---|---|---|
| `Application/Navigation/AppShell` | `Dashboard/Layouts/AppShell` | Dashboard layout, not its own section |
| `Trace/AtlasLensPanel` | `Dashboard/Trace/Atlas Lens` | Top-level Trace/ duplicates Dashboard/Widgets/Trace/ |
| `Settings/Section` | `Primitives/Section` | Layout primitive |
| `Settings/SettingRow` | `Primitives/SettingRow` | Layout primitive |
| `Agents/AgentCard` | `Dashboard/Agents/Agent Card` | Dashboard panel |
| `Agents/AgentOpsPanel` | `Dashboard/Agents/Agent Ops` | Dashboard panel |
| `Agents/ManagedEmployeesTab` | `Dashboard/Agents/Managed Employees` | Dashboard panel |
| `Agents/SystemAgentsTab` | `Dashboard/Agents/System Agents` | Dashboard panel |
| `Team/LicenseStatusCard` | `Dashboard/Team/License Status` | Dashboard panel |
| `Team/SyncStatusCard` | `Dashboard/Team/Sync Status` | Dashboard panel |
| `Team/TeamSyncIndicator` | `Dashboard/Team/Team Sync Indicator` | Dashboard panel |
| `Console/AnimatedCLI` | `Website/Demos/Animated CLI` | Marketing demo |
| `Console/AnimatedIDE` | `Website/Demos/Animated IDE` | Marketing demo |
| `Foundations/Molecules/CitationBlock` | `Primitives/CitationBlock` | "Molecule" tier doesn't earn its own level |
| `Foundations/Molecules/CopyButton` | `Primitives/CopyButton` | Same |
| `Foundations/Patterns/KeyboardShortcuts` | `Patterns/Keyboard Shortcuts` | Promote Patterns to top-level |
| `Foundations/Patterns/StatePatterns` | `Patterns/State Patterns` | Same |
| `Foundations/Primitives/Button` | `Primitives/Button` | Promote Primitives to top-level |
| `Foundations/Primitives/PathInput` | `Primitives/PathInput` | Same |
| `Foundations/Primitives/SearchableSelect` | `Primitives/SearchableSelect` | Same |
| `Foundations/Primitives/Select` | `Primitives/Select` | Same |
| `Dashboard/Primitives/PanelChrome` | `Patterns/Panel Chrome` | Composite, not a primitive |
| `Dashboard/Primitives/PanelPicker` | `Patterns/Panel Picker` | Same |
| `Dashboard/Layouts/Introduction` | `Dashboard/Introduction` | Layout intro for the section, not a layout itself |
| `Design System/Visual Directions` | `Foundations/Visual Directions` | Foundations is the right top-level for design-system docs |
| `Introduction` (root, no prefix) | `Foundations/Introduction` | Avoid orphan top-level entries |

#### 4.1.b Currently excluded — destination for when content is sanitized

| Story | Planned title | Blocker |
|---|---|---|
| `Console/LogConsole` | `Dashboard/Console/Log Console` | Mock log entries reference `prep.core.*` logger names |
| `Console/BugReportModal` | `Modals/Bug Report Modal` | Could spam support endpoint; mock logs reference internal modules |
| `Goalposts/RoadmapPanel` | `Dashboard/Roadmap/Roadmap Panel` | Mock data names internal roadmap items |
| `Audit/AuditPanel` | `Dashboard/Audit/Audit Panel` | Mock findings name internal architectural debt |
| `Audit/OpportunitiesPanel` | `Dashboard/Audit/Opportunities` | Same |
| `Dashboard/Widgets/Trace/GraphEnrichmentPipeline` | `Dashboard/Pipeline/Graph Enrichment` | Pipeline-stage names + Phase comments |
| `Phase 119/CapacityHealth` | `Dashboard/Pipeline/Capacity Health` | Phase 119 namespace |
| `Phase 119/PlanDropdown` | `Dashboard/Pipeline/Plan Dropdown` | Same |
| `Phase 119/ProbeButton` | `Dashboard/Pipeline/Probe Button` | Same |
| `Phase 119/Old vs New SidebarPipelineQueue` | `Dashboard/Pipeline/Sidebar Pipeline Queue` | Same; drop "Old vs New" from public |
| `Pipeline/ConcurrencyHealth` | `Dashboard/Pipeline/Concurrency Health` | (already not phase-prefixed but in wrong top-level) |
| `Pipeline/RecentSwarmLogs` | `Dashboard/Pipeline/Recent Swarm Logs` | Same |
| `Pipeline/SwarmActivityPanel` | `Dashboard/Pipeline/Swarm Activity` | Same |
| `Application/Navigation/SidebarAIGateway` | `Dashboard/Pipeline/Sidebar AI Gateway` | Phase 119 description text |
| `Dashboard/Widgets/Settings/AIModelsSettings` | `Dashboard/LLM/AI Models Settings` | Phase 119 prop JSDoc |
| `Dashboard/Widgets/Trace/ProvenanceChip` | `Dashboard/Trace/Provenance Chip` | Phase 117 in JSDoc |
| `Trace/GraphStructurePanel` | `Dashboard/Trace/Graph Structure` | Internal diagnostic; ok after JSDoc cleanup |
| `Trace/StageProgressBar` | `Dashboard/Build/Stage Progress` | Internal pipeline UI; ok after cleanup |
| `Trace/TraceExplorer` | `Dashboard/Trace/Trace Explorer` | Internal trace inspector |
| `Dashboard/Widgets/Trace/RebuildDropdown` | `Dashboard/Build/Rebuild Dropdown` | Pipeline recovery UI |
| `Dashboard/Widgets/Trace/RebuildingRow` | `Dashboard/Build/Rebuilding Row` | Same |
| `Dashboard/Widgets/Trace/RecoverStagePanel` | `Dashboard/Build/Recover Stage` | Same |
| `Dashboard/Widgets/Trace/TraceCoveragePanel` | `Dashboard/Trace/Coverage` | Diagnostic |
| `Enterprise/EnterpriseAdminPanel` | `Dashboard/Enterprise/Enterprise Admin` (or stay excluded) | Admin surface; user decides |

### 4.2 Naming rules

1. **No phase numbers** anywhere in titles or component descriptions. Phase comments in source code get swept (the 47-file pass).
2. **No `v2`, `Old vs New`, `Legacy`** in public titles.
3. **Suffix consistency**: prefer no suffix when the component name is unambiguous (`Search Panel`, not `SearchPanelWidget`). When a suffix is needed, prefer `Panel` for full-width composites, `Card` for bordered modular blocks, no suffix for primitives. Resolve `Widget` ambiguity by absorbing them into either `Panel` or `Card` based on size.
4. **Two depth levels max** for most stories (e.g. `Product UI/Search` then story name). Three levels only for natural sub-categorization (e.g. `Marketing/Research/Source Card`).
5. **Story IDs are stable contracts** for `<StoryEmbed storyId="…">`. Renaming a `title` changes the ID. Audit `websites/apps/docs/` for embeds before renaming.

### 4.3 What "Product UI" earns its place

A story belongs in `Product UI/` when:
- Its component is mounted somewhere in `src/prep/dashboard/` or `packages/vscode/`, **or**
- It's a polished candidate for those surfaces (in active design).

A story belongs in `Marketing/` when:
- Its component is rendered on `websites/apps/marketing/` or `websites/apps/docs/`, **or**
- It only exists as a marketing demo (animated CLI/IDE, research components, etc.).

A story is **excluded from public** (per §6 of `00_curation_plan.md`) when:
- It's internal-only (admin, dev diagnostics, internal modal flow), **or**
- Mock data references roadmap/debt/phase content that hasn't been sanitized.

These three buckets are mutually exclusive and exhaustive.

---

## 5. Migration plan

### 5.1 Sequence

Order matters because story ID stability is a contract with the docs site.

1. **Inventory `<StoryEmbed>` usages** in `websites/apps/docs/src/app/`. List each story ID currently embedded and the page that embeds it.
2. **Rename in lockstep**: for each story whose `title` changes, update the corresponding `StoryEmbed storyId="…"` in the docs site in the same commit.
3. **Move source files only if needed** — a story file's location on disk doesn't have to match its title path. Renaming `title` is sufficient.
4. **Sweep source-comment phase tags** (the 47-file pass per `00_curation_plan.md` §5.2). Replace `Phase NN: …` JSDoc with neutral language or delete if it just dates the change.
5. **Sanitize mock data** in stories returning to public bucket: `RoadmapPanel`, `AuditPanel`, `OpportunitiesPanel`, `GraphEnrichmentPipeline`, `LogConsole`, `SwarmActivityPanel`, `SidebarAIGateway`, `AIModelsSettings`, `ProvenanceChip`. Generic placeholders (`"Add caching to API layer"`, `"prep.frontend.theme"`) that don't name internal incidents.
6. **Phase 119 rename**: `ConcurrencyHealth`, `CapacityHealth`, `RecentSwarmLogs`, `ProbeButton`, `PlanDropdown`, `SidebarPipelineQueue` move from `Phase 119/` to `Product UI/Pipeline/Diagnostics/` (or similar) once their internal naming is removed from titles + descriptions.
7. **Re-include cleaned stories** in the public build by removing them from the regex in `.storybook/main.ts`.

### 5.2 Per-story migration checklist

For each story being renamed:

- [ ] Update `title:` in the meta export.
- [ ] Update any `description.story` / `description.component` parameters that use phase tags.
- [ ] Update `StoryEmbed storyId=` in any docs page that embeds it.
- [ ] Update entries in `docs/Phase68_revise-marketing/08_Storybook_App_Alignment_Plan.md` (story-to-docs mapping).
- [ ] Run `npm run build-storybook:public` and verify the renamed story shows in `stories.json` with the new ID.

---

## 6. Open questions

1. **One Storybook for two audiences, or two Storybooks?** Primer ships separate sites for Product UI vs Brand UI. We currently ship one. Trade-off: one is simpler to maintain; two is cleaner separation. Recommendation: keep one; use the `Product UI/` vs `Marketing/` top-level split. Revisit if/when the brand site grows substantially.
2. **`Patterns/` vs absorbing into `Primitives/`**: many design systems don't carry a Patterns tier explicitly. Decision needed: do we want a third tier, or is two (Primitives + composed Product UI) enough?
3. **VS Code surface visibility**: do we expose a `Product UI/VS Code/` slice, or assume VS Code reuses the same components without separate stories?
4. **Roadmap / Goalposts**: is this part of the product (if so, where does it live in `Product UI/`?), or is it a planning concept that doesn't earn a story?
5. **Component rename audit**: current code uses `…Panel`, `…Card`, `…Widget` inconsistently. Do we rename component files too, or only the story `title` strings? File renames are higher cost (touch the components, the imports, the dashboard).
6. **`SiteFooter.stories.tsx` mock**: currently embeds `github.com/MagneticAnomaly/SourcePrep-MCP` (private repo). Decide what URL to mock once SiteFooter is in the Marketing/ bucket publicly.
7. **`packages/ui/src/components/dashboard/` directory rename**: the 5-component subset (IndexStatusCard, IndexStats, LLMStatusWidget, UsageGuidePanel, BuildCard) lives in a misleadingly-named directory. Rename to `components/overview/`? Small refactor, touches 5 files + their imports, but disambiguates against the Storybook top-level `Dashboard/`. Not blocking; track separately.
8. **Architecture/Concepts/Viz/Docs/Navigation stories**: components exist but no stories yet. Should this Phase 131 work commission stories for them, or stay scoped to renaming what already exists? Recommendation: stay scoped; story-authoring is doc-03 v2 territory.

---

## 7. Out of scope for this proposal

- Visual redesign of any component.
- Component-level refactors.
- Changes to the actual dashboard or marketing site renderings.

This is purely organizational — sidebar layout, story titles, and the public/internal split.
