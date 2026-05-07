# Storybook Curation Plan

**Status**: Draft (2026-05-07)
**Owner**: TBD
**Triggered by**: Public Storybook deploy at `storybook.sourceprep.io` revealed (a) orphaned/forgotten components, (b) "Phase NN" namespace pollution in story titles, (c) unclear public-vs-internal split.

> Note: `Phase130_DocsSiteStalenessSweep` was already taken; this work lives at `Phase131`.

---

## 1. Motivation

The `@prep/ui` package has accumulated stories over many phases. Some stories ship to production but the underlying component is no longer mounted in the dashboard. Some are tagged with internal phase numbers (`Phase 119 / ProbeButton`) that leak development-process artifacts to a public audience. Some surface mock data that names internal roadmap items.

Goals:
- A **public Storybook** that reads as a polished design system to design engineers.
- A clear **public/internal split**, enforced at build time.
- **Zero "Phase NN" prefixes** in user-visible story titles or labels.
- Identify components that are stranded (built, never mounted) so they can be either adopted, archived, or deleted.

Non-goals:
- No rewriting components.
- No refactoring beyond renames and story-config edits.

---

## 2. Audit signals

### 2.1 Story title categories

```
36  Dashboard/...
11  Foundations/...      (tokens, accessibility)
10  Website/Marketing/...
 4  Phase 119/...        ← namespace violation
 4  Trace/...
 4  Console/...
 4  Agents/...
 3  Team/...
 3  Pipeline/...
 2  Audit/...
 1  each: Goalposts, Enterprise, Application, Settings, …
```

`Dashboard/...` is the largest bucket and reflects the actual product. `Phase 119/...` is the only category whose name is an internal artifact rather than a feature surface.

### 2.2 Phase 119 components — usage check

| Component | Mounted in dashboard? | Mounted elsewhere? | Disposition |
|---|---|---|---|
| `ConcurrencyHealth` | ✅ `settings/v2/pages/Diagnostics.tsx` | — | **Keep, rename out of "Phase 119"** |
| `CapacityHealth` | ✅ `settings/v2/pages/Diagnostics.tsx` | — | **Keep, rename** |
| `RecentSwarmLogs` | ✅ `settings/v2/pages/Diagnostics.tsx` | — | **Keep, rename** |
| `ProbeButton` | ❌ direct mount; used as sub-component of `CapacityHealth` | — | **Keep as composable; demote to internal-only** |
| `PlanDropdown` | ❌ no callers found | — | **Investigate / archive** |
| `SidebarPipelineQueue` (old vs new) | ❓ — needs check | — | **Resolve old/new before public** |

Eric flagged: "We accidentally built something useful and aren't even using it." Confirmed for `ConcurrencyHealth` / `CapacityHealth` / `RecentSwarmLogs` — they live behind the Diagnostics settings page, not on the main dashboard. Likely worth promoting to a more visible surface, but that's a product decision, not a Storybook decision.

### 2.3 Components built but never mounted

Audit method: `grep -rln '<ComponentName\|from .*ComponentName' src/prep/dashboard packages/vscode`.

| Component | Story exists? | Used anywhere? | Disposition |
|---|---|---|---|
| `BugReportModal` | ✅ | ❌ | **Exclude from public; investigate replacement** |
| `EnterpriseAdminPanel` (45KB) | ❌ no story (per Phase68 doc) | ✅ via `useDashboardPanels.tsx` | Stays internal regardless |
| `AdvancedLLMSettings` | ✅ via stories | ❌ | **Investigate / archive** |
| `PlanDropdown` | ✅ | ❌ | **Investigate / archive** |
| `ProbeButton` | ✅ | sub-component only | **Keep, internal-only** |

This list is illustrative, not exhaustive. A full sweep is part of this phase.

### 2.4 Mock data surfaces with internal copy

Even with `autodocs: false` (story source hidden), some rendered stories display mock fixture data that mentions internal artifacts:

- `RoadmapPanel` mock items: *"Implement MCP streaming responses"* (P0), *"Extract pipeline stages from GraphEnrichmentPipeline"*, *"GraphEnrichmentPipeline.tsx exceeds 58KB"*, *"GoalpostsPanel is hidden but still ships in the bundle"*.
- `AuditPanel` mock findings: *"Inconsistent naming: 'Panel' vs 'Card' vs 'Widget' suffixes"*, *"Circular dependency between search and trace modules"*.
- `BugReportModal` mock log entries: internal logger names (`prep.core.augmenter`, `prep.services.pipeline`).

These are visible to anyone viewing the rendered story, regardless of `autodocs` setting. They need to be replaced with neutral fixture content for any story shipped publicly.

### 2.5 "Phase NN" comment pollution in component source

47 component files reference `Phase NN` in inline comments (e.g. `// Phase 119 Phase A: …`, `// Phase 117: per-stage rebuild provenance`). These leak through `react-docgen` if `autodocs` is ever re-enabled, and are otherwise dev-cosmetics. Lower priority than story titles and mock data.

---

## 3. Decision framework — three buckets

Each story file gets categorized:

### Bucket A — Public-Polish
Goes into the public bundle. Rendered component looks clean and represents a real product surface a design engineer would find compelling.
- Tokens, primitives, layout patterns
- Polished dashboard panels (Search, Index Status, Build, Trace Graph, Atlas Lens)
- Marketing/website components
- Foundational stories (Accessibility, Visual Directions)

### Bucket B — Internal-Only
Stays in the storybook for local dev but is excluded from the public build.
- BugReportModal (could spam support endpoint)
- Anything tagged "Phase NN" before rename
- Highly technical dev panels (ConcurrencyHealth, CapacityHealth, RecentSwarmLogs, ProbeButton, PlanDropdown — until renamed and/or polished)
- Old-vs-new comparison stories
- Audit / Roadmap / Goalposts panels until mock data is sanitized
- AdvancedLLMSettings if not currently mounted

### Bucket C — Orphaned / Archive
Component has no production caller and isn't actively useful in dev. Either:
- Promote to product (file an issue)
- Archive (delete the story, leave the component with a deprecation comment)
- Delete outright

Criterion: zero callers in `src/prep/dashboard` AND `packages/vscode` AND no roadmap intent.

---

## 4. Naming rules

For all stories shipped publicly:

1. **No `Phase NN` in `title`.** Replace with the user-visible feature category.
   - `Phase 119 / ProbeButton` → `Pipeline/ProbeButton` (or kept internal until renamed)
   - `Phase 119 / CapacityHealth` → `Pipeline/CapacityHealth`
2. **No internal version markers** (`Old vs New`, `v2`, `Legacy`) in public titles.
3. **Title hierarchy** = user mental model, not internal subsystem boundary. Top-level tokens for public exposure: `Foundations`, `Primitives`, `Patterns`, `Dashboard`, `Trace`, `Pipeline`, `Search`, `Agents`, `Team`, `Audit`, `Marketing` (= "Website"), `Layout`.
4. **Story IDs are stable contracts** for `<StoryEmbed storyId="…">` in the docs site. When renaming a `title`, audit the docs site for any `StoryEmbed` referencing the old ID and update in lockstep.

---

## 5. Action items

### 5.1 Build-time (this PR — pre-public-deploy)
- [ ] Env-gate `autodocs: false` for the public build via `STORYBOOK_PUBLIC=true`.
- [ ] Story-glob exclusions for the obvious internal-only set:
  - `BugReportModal.stories.*`
  - `EnterpriseAdminPanel.stories.*` (when it exists)
  - `**/Phase 119*` story files (pending rename)
- [ ] Re-audit `storybook-static/` after rebuild: `originalSource` count = 0, excluded story IDs absent from `stories.json`.

### 5.2 Curation (subsequent PRs)
- [ ] Rename the four `Phase 119/` titles to their feature category.
- [ ] Sweep 47 `// Phase NN:` comments in component source. Keep ones that document a non-obvious *why*; delete ones that just date the change.
- [ ] Sanitize mock fixture data in stories shipped publicly:
  - `RoadmapPanel` mock items → generic feature labels.
  - `AuditPanel` mock findings → generic naming/coupling examples.
  - `BugReportModal` mock log entries → noop (story is internal-only anyway).
- [ ] Decide each Bucket C component: promote / archive / delete.
- [ ] Add a story-tagging convention (e.g. `tags: ['internal']`) so the build glob is data-driven, not file-list-driven.

### 5.3 Docs-site coupling
- [ ] List all `<StoryEmbed storyId="…">` references in `websites/apps/docs/`.
- [ ] For each, confirm the underlying story is in Bucket A and survives renames.

---

## 6. Public/internal split — applied 2026-05-07

`packages/ui/.storybook/main.ts` filters out the following stories when
`STORYBOOK_PUBLIC=true`:

| Story | Reason |
|---|---|
| `BugReportModal` | Could spam support endpoint; mock logs reference `prep.core.*` |
| `EnterpriseAdminPanel` | Admin surface |
| `ConcurrencyHealth`, `CapacityHealth`, `RecentSwarmLogs` | Phase 119 diagnostics — technical and named after internal phase |
| `ProbeButton`, `PlanDropdown` | Phase 119; ProbeButton is sub-component-only, PlanDropdown not mounted |
| `SidebarPipelineQueue` | "Old vs New" internal comparison |
| `RoadmapPanel` | Mock data names internal P0 roadmap items |
| `AuditPanel`, `OpportunitiesPanel` | Mock findings name internal architectural debt |
| `GraphEnrichmentPipeline` | Internal pipeline-stage names + Phase comments |
| `LogConsole` | Mock log entries reference internal logger module names |

Result: 465 → 334 entries shipped. `originalSource` blocks reduced from 400 to 334; the remainder are safe public-bucket stories (UI primitives, layout, marketing). No "Implement MCP streaming responses" / "GraphEnrichmentPipeline.tsx exceeds…" / "GoalpostsPanel is hidden" / "Circular dependency" strings remain in the bundle. autodocs disabled, `.d.ts` filtered, source maps off, no real fetches at render time.

### 6.1 Known residuals — accepted for now, address in §5.2

- **`Phase 102`–`Phase 120` strings** still appear in the bundle, leaked through component-source JSDoc comments via the originalSource embedding (e.g. `// Phase 117: per-stage rebuild provenance`). Surfaces in the Controls panel's prop description for any story whose component has a phase-prefixed comment. Mitigation: §5.2 component-comment sweep.
- **`prep.core.*` / `prep.services.*` logger names** still appear in `FullDashboard` mock log fixtures. Acceptable: Python module conventions, no algorithm content. Mitigation: §5.2 mock-data sweep can replace with neutral logger names.
- **Mock file paths** (`src/prep/api/auth.py`, etc.) in fixtures. Accepted per threat model — generic Python module paths, no algorithm leak; backend distribution is Nuitka-compiled binary.

---

## 7. Open questions

1. Should `ConcurrencyHealth` / `CapacityHealth` / `RecentSwarmLogs` be **promoted** out of the Diagnostics page to a more discoverable dashboard surface? They're useful and currently buried. (Product question, not a Storybook question.)
2. Is `BugReportModal` superseded by the support site (`support.sourceprep.io`) and therefore fully dead? If so, delete the component, not just the story.
3. Naming: is `"Pipeline"` the right top-level for the dev panels (`ConcurrencyHealth`, etc.), or a separate `"Diagnostics"` top-level?
4. Tag convention: `internal` vs `dev-only` vs `wip` — pick one and standardize.

---

## 8. Out of scope for Phase 131

- Refactoring component implementations.
- Deleting the components themselves (only their stories from the public build, or marking for archive).
- Moving stories between files.
- Visual/UX redesign.
