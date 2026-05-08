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

Primitives/
├── Button
├── Select
├── SearchableSelect
├── Toggle
├── SettingRow
├── PathInput
├── InfoTooltip
├── ConfirmDialog
├── CopyButton
├── EmptyState
├── ProgressIndicator
├── StatusBadge
└── CitationBlock

Patterns/
├── State Patterns
├── Keyboard Shortcuts
├── Panel Chrome
└── Panel Picker

Product UI/                  (the desktop dashboard + VS Code extension surfaces)
├── Shell/
│   ├── App Shell
│   ├── Full Dashboard
│   └── Modular Dashboard
├── Search/
│   ├── Search Panel
│   ├── Search Components
│   ├── Symbol Search
│   ├── Context Options
│   └── Context Output
├── Trace/
│   ├── Graph
│   ├── Atlas Lens
│   ├── Graph Structure
│   ├── Coverage
│   ├── Node Detail
│   ├── Trace Explorer
│   └── Status Card
├── Pipeline/
│   ├── Build Card
│   ├── Build Progress
│   ├── Stage Progress
│   ├── Rebuild Dropdown
│   ├── Rebuilding Row
│   └── Recover Stage
├── Index/                  (formerly "Status")
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
│   └── Model Card
├── Settings/
│   ├── Section
│   ├── Advanced LLM
│   ├── Deep Analysis
│   ├── Project Settings
│   └── (other settings forms)
├── Watch/
│   ├── Watch Controls
│   └── Status Indicator
├── Agents/
│   ├── Agent Card
│   ├── Agent Ops
│   ├── Managed Employees
│   └── System Agents
└── Team/
    ├── License Status
    ├── Sync Status
    └── Team Sync Indicator

Marketing/                   (sourceprep.io — formerly "Website")
├── Layout/
│   ├── Site Header
│   └── Site Footer
├── Hero
├── Feature Blocks
├── Demos/                  (← MOVED from "Console/")
│   ├── Animated CLI
│   └── Animated IDE
└── Research/
    ├── Research Hero
    ├── Research Section
    ├── Research Appendix
    ├── Source Card
    ├── Source Filter Chips
    └── Source Spotlight
```

### 4.1 What changed vs current

| From | To | Why |
|---|---|---|
| `Console/AnimatedCLI`, `Console/AnimatedIDE` | `Marketing/Demos/Animated CLI`, `…/Animated IDE` | User flagged: marketing demos, not internal console |
| `Console/LogConsole`, `Console/BugReportModal` | (excluded — internal) | Already in §6 exclusion list |
| `Phase 119/*` | (excluded until renamed) | Internal phase namespace |
| `Trace/*` (top-level) | `Product UI/Trace/*` | Unify with `Dashboard/Widgets/Trace/*` |
| `Dashboard/Widgets/Trace/*` | `Product UI/Trace/*` | Same as above |
| `Dashboard/Widgets/Settings/*` | `Product UI/Settings/*` | Single home for settings |
| `Settings/SettingRow` (top-level) | `Primitives/SettingRow` | It's a primitive, not a Settings page |
| `Dashboard/Primitives/PanelChrome`, `PanelPicker` | `Patterns/Panel Chrome`, `Panel Picker` | Composite patterns, not atoms |
| `Foundations/Primitives/*` | `Primitives/*` | Promote primitives to top level — they're the design-system spine |
| `Foundations/Molecules/CopyButton`, `CitationBlock` | `Primitives/CopyButton`, `Primitives/CitationBlock` | "Molecule" tier doesn't carry weight given our scale; consolidate |
| `Foundations/Patterns/*` | `Patterns/*` | Top-level — Patterns are reused everywhere |
| `Application/Navigation/AppShell` | `Product UI/Shell/App Shell` | Consolidates app-shell concerns |
| `Goalposts/RoadmapPanel` | (excluded; if rehomed: `Product UI/Roadmap/Roadmap Panel`) | Single-entry "Goalposts" doesn't earn a top-level |
| `Audit/*` | `Product UI/Audit/*` (when rehomed) | Currently excluded; folds into Product UI |
| `Enterprise/*` | `Product UI/Enterprise/*` (when rehomed) | Currently excluded; folds into Product UI |
| `Pipeline/*` | `Product UI/Pipeline/*` (after rename) | Currently excluded under "Phase 119"; rename + rehome |
| `Website/*` | `Marketing/*` | Mirrors the actual brand — `sourceprep.io` is a marketing site |

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

---

## 7. Out of scope for this proposal

- Visual redesign of any component.
- Component-level refactors.
- Changes to the actual dashboard or marketing site renderings.

This is purely organizational — sidebar layout, story titles, and the public/internal split.
