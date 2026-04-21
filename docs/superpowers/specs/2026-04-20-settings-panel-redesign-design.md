# Settings Panel Redesign — Full-Screen Overlay with Scope-Split Nav

**Date:** 2026-04-20
**Status:** Design approved, pending implementation plan
**Scope:** Dashboard Settings only — no changes to dashboard panels, AI Gateway, Pipeline Queue, or backend.

## Problem

Today's Settings lives in a 500px right-edge drawer (`SettingsDrawer.tsx`, 736 LoC) with four horizontal tabs: Project, Global, Advanced, Developer. It is cramped, scrolls heavily, and — most critically — the "Advanced" tab mixes per-project controls (trace limits) with global controls (chunk sizes, checkpoint interval). The scope mixing is a latent source of user error: toggling a control in one tab can silently affect either the active project or the whole daemon, with no visual cue which.

## Goals

- Replace the right-edge drawer with a **full-screen overlay** containing a **left nav** — same pattern Claude Code's Settings uses.
- **Hard-separate project-scope and global-scope** settings in the navigation and on every page.
- Preserve today's four-tab content map in spirit, but redistribute "Advanced" so no single page mixes scopes.
- Keep the **Developer** section dev-only via a **build-time gate**, so it is compiled out of production bundles.
- Use `@prep/ui` design tokens exclusively — no raw hex, no arbitrary px values except the nav rail and top bar dimensions that match existing shell tokens.

## Non-Goals

- Any change to dashboard panels (LLM Status, Pipeline, Trace, Audit, Concepts, Atlas, Search, Files, etc.).
- Any change to the **AI Gateway** panel or the **Pipeline Queue** sidebar — both remain in the left panel and are not touched.
- Any change to the left sidebar, ProjectList, or AppShell.
- Any change to `GlobalConfig` / `ProjectConfig` schemas or the Python `/settings` routers.
- Moving configuration surfaces from the dashboard into Settings (e.g., AI Gateway config stays in AI Gateway; Settings → Integrations only **links out** to it).

## Left-Nav Structure

Three top-level groups. Every nav item belongs to exactly one group; no item spans scopes.

```
PROJECT · <active project name>
  Sources & Scope        include/exclude globs, gitignore, max file
                         size, hard limit, active, priority
  Trace & Indexing       per-project trace enable, ignore patterns,
                         trace limits (max_files/nodes/edges),
                         auto-rebuild debounce, graph_engine advanced
  Deep Analysis          mode, budgets (tokens/minutes/items),
                         auto_config flags, schedule
  Danger Zone            Rebuild Pipeline, Reset Enrichment,
                         Reset Finalize, Reset All (typed-confirm)

GLOBAL
  Appearance             color mode, theme, bg image
  Chunking & Embeddings  code/markdown chunk sizes, overlap
  Pipeline Defaults      checkpoint interval, min_edge_confidence,
                         max_active_projects
  License                tier, activation
  Integrations           AI Gateway shortcut (link-out only)

DEVELOPER  ─ build-time gated ─
  Debug Toggles          verbose telemetry, exploratory testing,
                         show dev panels, role/tier overrides
  Diagnostics            connection debugger, daemon health,
                         data dir status, dev tier badge, license details
  Selective Reset        atlas, group_reasoning, deep_enrichment
```

**Contents of the former "Advanced" tab are redistributed by scope:**
- Per-project trace limits → **Trace & Indexing** (Project group)
- Chunking sizes + overlap → **Chunking & Embeddings** (Global group)
- Checkpoint interval + min_edge_confidence → **Pipeline Defaults** (Global group)
- Reset All → **Danger Zone** (Project group)

The "Advanced" label disappears. Its content does not.

## Overlay Shell

```
┌──────────────────────────────────────────────────────────────┐
│  ← Settings                                        ⌘,  │ ✕ │  h-14 top bar
├────────────────────┬─────────────────────────────────────────┤
│                    │  Trace & Indexing    [Project chip]     │
│   PROJECT · my…    │  ───────────────────────────────────    │
│   ● Sources        │                                         │
│     Trace          │  (scrollable page body, max-w-3xl)      │
│     Deep Analysis  │                                         │
│     Danger Zone    │                                         │
│                    │                                         │
│   GLOBAL           │                                         │
│     Appearance     │                                         │
│     ...            │                                         │
│                    │                                         │
│   DEVELOPER (dev)  │                                         │
│     ...            │                                         │
└────────────────────┴─────────────────────────────────────────┘
      w-60 rail                        flex-1 main
```

**Container** — `fixed inset-0 z-50 bg-surface-canvas`. Opaque — takes over the viewport, no scrim. Portal-rendered.

**Top bar** — `h-14 border-b border-border-subtle px-4 flex items-center gap-3`. Back-arrow icon button, "Settings" title (`text-base font-medium`), spacer, keyboard-hint pill showing `⌘,`, close icon button.

**Left rail** — `w-60 border-r border-border-subtle overflow-y-auto py-2`.
- Group labels: `text-xs uppercase tracking-wide text-text-muted px-3 pt-4 pb-1`
- Group separator: `border-t border-border-subtle mt-2` above each group after the first
- Nav items: `text-sm text-text-secondary hover:bg-surface-subtle rounded-md mx-2 px-3 py-1.5 cursor-pointer`
- Active item: `bg-surface-subtle text-text-primary font-medium`

**Main area** — `flex-1 overflow-y-auto`, content wrapper `max-w-3xl mx-auto px-8 py-8 space-y-8`.

**Scope chip** — in each page header, immediately after the title: `bg-surface-subtle text-text-muted text-xs rounded-full px-2 py-0.5`. Values: `Project`, `Global`, `Developer`. Removes scope ambiguity on every page.

**Transition** — overlay fades + scales from the Settings button's origin. `transform-origin: bottom right; scale: 0.96 → 1; opacity: 0 → 1; duration: 180ms; ease-out`. Matches the "grow from source" pattern; no drawer-slide.

## Page Layout Pattern

All pages use the same three-part structure to build muscle memory:

```tsx
<SettingsPage>
  <PageHeader
    title="Trace & Indexing"
    scope="project"
    description="Control how we crawl and re-index this project."
    actions={<SaveButton />}   // project pages only
  />

  <Section>
    <SettingRow
      label="Enable tracing"
      description="Record import edges as files change."
      control={<Switch … />} />
    <SettingRow … />
  </Section>

  <Section title="Advanced">
    <SettingRow … />
  </Section>
</SettingsPage>
```

**`SettingRow`** — new `@prep/ui` primitive.
- Two-column layout: label + description on the left, control on the right.
- Fixed right-column width so toggles and selects align vertically down the page (matches Claude Code's visual rhythm).
- Row separator: `py-4 border-b border-border-subtle` (last row suppresses the border).
- Description uses `text-sm text-text-muted`; label uses `text-sm font-medium text-text-primary`.

**`Section`** — optional `title` (`text-xs uppercase tracking-wide text-text-muted mb-2`). Sections within a page are separated by `space-y-8` on the wrapper.

**`PageHeader`** — title + scope chip + description + actions slot. Sticks to top of main area via `sticky top-0 bg-surface-canvas z-10 pb-4 border-b border-border-subtle mb-6` so the save button stays reachable on long pages.

## Save Semantics (Scope-Dependent)

- **Global pages**: autosave on change with debounce. Already the current pattern; matches Claude Code's snappy feel.
- **Project pages**: explicit **Save** button in the page header. Dirty flag tracked; "Unsaved changes" banner renders while dirty. Prevents mid-typing commits of sensitive fields like include/exclude globs.
- **Developer pages**: autosave (they are developer-only, and the debug toggles are intentionally cheap to flip).

**Dirty-state guards (Project pages only):**
- Clicking another nav item while dirty → inline confirm: "Discard changes?" with `Discard` / `Keep editing`.
- Closing the overlay (back-arrow, Esc, `⌘,`) while dirty → same confirm, blocks close until resolved.
- Switching projects from the sidebar while a Project settings page is dirty → typed-confirm (reuses Phase 114 `RebuildGate` pattern).

## Interactions

**Open:**
- Floating Settings button (bottom-right, unchanged).
- Keyboard: `⌘,` on macOS, `Ctrl+,` elsewhere — binds at AppShell.
- URL param: `?settings=<page>` deep-links; sharable; survives reload.

**Close:**
- Back-arrow top-left.
- `Esc` key.
- `⌘,` toggles (second press closes).
- All three strip the `?settings=...` param.

**Nav between pages:**
- Clicking an item updates `?settings=<page>` via `replaceState` — no history spam.
- Single history entry for "settings is open" — browser back button closes the overlay and returns to the exact prior dashboard state.

**Scope boundary cues (redundant on purpose):**
- Scope chip on every page header.
- Grouped rail with labels + hairline separators.
- Active-project name inlined in the `PROJECT · <name>` group label.
- If no project is active: Project group disabled with "Select a project first" hint, nav items non-clickable.

## Developer-Group Gate

**Build-time gate** (not runtime):

```tsx
{import.meta.env.DEV && <DeveloperNavGroup />}
```

In production builds (`vite build`), Vite's dead-code elimination removes the Developer nav group and every page component under it. No shipped user can reach these surfaces.

The settings router additionally refuses any `?settings=developer-*` param in production and silently redirects to the first Global page. Defence in depth.

The `developer_show_dev_panels` field on `GlobalConfig` is **not removed** — it still gates *dashboard* dev panels, which are out of scope here. It no longer gates this Settings Developer group.

## Component Inventory

| Component | Location | Status |
|-----------|----------|--------|
| `SettingsOverlay` | `src/prep/dashboard/src/components/settings/SettingsOverlay.tsx` | new — portal root, top bar, routing |
| `SettingsNav` | `src/prep/dashboard/src/components/settings/SettingsNav.tsx` | new — left rail, grouped |
| `SettingsPage` | `src/prep/dashboard/src/components/settings/SettingsPage.tsx` | new — page shell + scope chip + save area |
| `SettingRow` | `packages/ui/src/components/settings/SettingRow.tsx` | new — shared label/description/control row |
| `Section` | `packages/ui/src/components/settings/Section.tsx` | new — optional-titled group within a page |
| Page: `Sources` | `…/settings/pages/Sources.tsx` | new — lifted from `SettingsDrawer` Project tab |
| Page: `TraceIndexing` | `…/settings/pages/TraceIndexing.tsx` | new — Project tab + per-project Advanced |
| Page: `DeepAnalysis` | `…/settings/pages/DeepAnalysis.tsx` | new — lifted from Project tab |
| Page: `DangerZone` | `…/settings/pages/DangerZone.tsx` | new — lifted from Project tab + Reset All |
| Page: `Appearance` | `…/settings/pages/Appearance.tsx` | new — lifted from Global tab |
| Page: `ChunkingEmbeddings` | `…/settings/pages/ChunkingEmbeddings.tsx` | new — Global tab + Advanced global |
| Page: `PipelineDefaults` | `…/settings/pages/PipelineDefaults.tsx` | new — Global tab + Advanced global |
| Page: `License` | `…/settings/pages/License.tsx` | new — lifted from Global tab |
| Page: `Integrations` | `…/settings/pages/Integrations.tsx` | new — AI Gateway link-out, other shortcuts |
| Page: `DevToggles` | `…/settings/pages/DevToggles.tsx` | new, dev-gated |
| Page: `Diagnostics` | `…/settings/pages/Diagnostics.tsx` | new, dev-gated |
| Page: `SelectiveReset` | `…/settings/pages/SelectiveReset.tsx` | new, dev-gated |
| `useSettingsRoute` | `…/settings/useSettingsRoute.ts` | new — reads/writes `?settings=<page>` |
| `useSettingsDirty` | `…/settings/useSettingsDirty.ts` | new — dirty flag + leave guard |
| `SettingsDrawer.tsx` | existing | **deleted** after migration |
| `AdvancedSettingsPanel.tsx` | existing | **deleted** after migration |

## Data Flow

Unchanged. Pages read and write through the same hooks and API calls the drawer uses today:
- Global settings: `api.getGlobalConfig()` / `api.updateGlobalConfig()` (debounced autosave).
- Project settings: `api.getProjectConfig(id)` / `api.updateProjectConfig(id, …)` (explicit save).
- Reset endpoints: existing `/projects/{id}/reset*` and `/projects/{id}/rebuild` routes.
- `/settings` SQLite-backed key-value store: unchanged.

## Migration & Rollout

1. Land new components in parallel with the existing drawer — no visible UI change yet.
2. Add a feature flag `settings_overlay_v2` (localStorage, developer-only initially) that replaces the drawer with the overlay when on.
3. Internal dogfood for one release cycle.
4. Flip the flag default to on; remove the drawer floating button's old handler.
5. Delete `SettingsDrawer.tsx` and `AdvancedSettingsPanel.tsx` in a follow-up commit; remove the flag.

No backend migration required.

## Testing

- **Unit** — each page's save/dirty behaviour; scope chip renders correct value; nav item active state follows `?settings=<page>`; URL param deep-link loads the correct page.
- **Integration** — one test per scope boundary:
  1. Global autosave writes through to `updateGlobalConfig` without a Save click.
  2. Project edit sets dirty flag; Save clears it; leaving dirty triggers confirm.
  3. `import.meta.env.DEV=false` build omits `DeveloperNavGroup` from the DOM and redirects `?settings=developer-toggles` to the first Global page.
- **Visual** — Storybook stories for `SettingRow`, `SettingsPage` (Project / Global / Developer variants), `SettingsNav`.
- **Manual** — `⌘,` open/close, Esc close, back-button behaviour, deep-link reload, resize overlay to 900px / 1200px / 1920px.

## Accessibility

- Overlay traps focus while open (first focusable element = back-arrow).
- `Esc` closes from any nested focus state.
- Left rail is a `<nav>` with `aria-label="Settings"`, items are `<button>` with `aria-current="page"` when active.
- Scope chip has `aria-label="Project-scoped setting"` / `"Global-scoped setting"` / `"Developer-only setting"`.
- All colour pairings meet WCAG AA against `@prep/ui` tokens (tokens already audited).

## Open Questions

None blocking. Minor follow-ups tracked for the implementation plan:
- Exact icon for each nav item (or icon-less — Claude Code is icon-less and reads clean).
- Whether `Integrations` should also list Cursor / Windsurf / VS Code rule files status, or only the AI Gateway shortcut in v1.
