# Storybook Documentation Surfaces Plan

**Status**: Draft (2026-05-08)
**Companions**: `00_curation_plan.md`, `01_taxonomy_research_and_proposal.md`, `02_visual_design_plan.md`

> *"Ours only has the granular buttons but none of the organization outside of the core storybook functionality — we should revisit this and see what can be done to make this more robust and designed."*

This doc captures the gap between what we currently ship (a list of granular component stories) and what mature design systems ship (a designed *publication* with foundations specimens, composed patterns, and overview pages that put components in context). It lays out the surfaces to author, what content goes in each, and how to phase the work.

---

## 1. The gap

### What we currently have

| Surface | Status | Quality |
|---|---|---|
| `Introduction.mdx` | Exists | **Stale** — references `docs/Phase13_Storybook/theme-examples/` (legacy path), lists only 4 of 14 themes, plain text + bullets, no embedded components |
| `Accessibility.mdx` (Foundations) | Exists | Well-written narrative, but no live demonstrations — code blocks only |
| `VisualDirections.mdx` | Exists | A 14-row table of theme descriptions — no live preview, no specimens, "Retro-Futurism" listed as current default (stale per Phase 131 §2) |
| `Foundations/Tokens/Colors`, `Spacing`, `Typography` | Exists as `.stories.tsx` | Likely just swatches/scales — not specimen pages with usage rules and context |
| `layout/Introduction.mdx` | Exists | Good — architecture narrative for the modular dashboard. Only one section has this kind of overview. |
| Per-component stories | 92 files, ~334 entries | Granular variants; no composed examples |

### What mature design systems ship

From the Polaris research:

- **Top nav**: Getting started, Foundations, Design, Content, Patterns, Components, Tokens, Icons.
- **Landing page**: hero + four entry quadrants (Foundations / Components / Tokens / Icons), each with a description and CTA.
- **Foundations** are specimen pages with examples, do/don't, accessibility callouts, code samples — not narrative-only.
- **Patterns** are workflow recipes that compose multiple components. Polaris ships seven (App settings layout, Card layout, Common actions, Date picking, New features, Resource details/index layout). Each gets a dedicated page with visual thumbnails + descriptions.
- **Components** are individual stories *and* per-component overview pages (with usage, anatomy, props, accessibility, related components).
- **Voice/tone, content, motion** get their own sections.

Carbon and Atlassian follow the same shape — the Storybook list is a fraction of what they publish.

### What we're missing

1. **A real welcome page** that hooks the visitor and routes to each surface.
2. **Foundations as specimens, not glossaries** — Typography, Color, Spacing, Motion shown in context.
3. **Per-section overview pages** — `Dashboard/Search/Overview`, `Dashboard/Trace/Overview`, etc. — that compose the section's components into a narrative.
4. **Patterns / recipes** — composed examples solving real workflows (Search → Results → Context, Build → Progress → Recovery, Settings page composition, Modal flow, Empty/Loading/Error states).
5. **Theme gallery** with live previews of all 14 themes side-by-side, not a static table.
6. **Voice/tone and content guidelines** — the copy in the product is currently uneven.
7. **Motion guidelines** — when/how to animate, with live demos.
8. **Iconography page** — Lucide icons in context with usage rules.

---

## 2. What Storybook gives us for authoring

`@storybook/addon-essentials` ships `addon-docs`, which renders MDX with the full set of doc blocks even when `autodocs` is disabled at the page level. We already filter `autodocs: false` in public mode, so authored MDX docs are the canonical way to publish anything richer than story variants.

Useful blocks (from `@storybook/blocks`):

| Block | Use |
|---|---|
| `<Meta title="…" />` | Sets the sidebar location |
| `<Story id="…" />` | Embeds an existing story by ID |
| `<Canvas of={Story} />` | Story preview frame, optionally with code |
| `<Source of={Story} />` | Code-only block (we'll mostly avoid; reveals JSX) |
| `<ColorPalette>` / `<ColorItem>` | Built-in swatch grids |
| `<Typeset>` | Built-in type specimen |
| `<IconGallery>` / `<IconItem>` | Icon grid |
| Free MDX | Markdown + JSX import any component |

Plus we can import live components from `@prep/ui` directly into MDX — so a Typography page can render real text in real component CSS, not screenshot mockups.

**Caveat for public builds**: any `<Source />` block resurrects the originalSource concern from the security audit. Stick to `<Canvas />` and free Markdown for the public build; keep `<Source />` for dev-only docs (gated by the same `STORYBOOK_PUBLIC` filter we use for stories).

---

## 3. Proposed surfaces

The taxonomy from `01_taxonomy_research_and_proposal.md` defines *where* things live. This section adds *what content* lives at each location — the MDX inventory.

### 3.1 Welcome page (root)

**File**: `src/stories/Welcome.mdx` (replaces the current `Introduction.mdx`)
**Title**: `Introduction`
**Content**:
- Hero: SourcePrep wordmark + one-liner (*"The design system behind the SourcePrep desktop app, VS Code extension, and marketing site."*)
- Visual: a small live `<FullDashboard>` snapshot or animated CLI/IDE demo
- Four entry quadrants, each linking into Storybook with a thumbnail:
  - **Foundations** — tokens, type, color, motion, accessibility
  - **Primitives** — buttons, inputs, controls
  - **Patterns** — composed recipes
  - **Dashboard** — product surfaces in context
- One quadrant for **Website / Marketing** components
- Footer: links to GitHub, sourceprep.io, Phase 131 plan

### 3.2 Foundations — specimen pages

Each becomes a real specimen, not a token glossary.

| Page | Content |
|---|---|
| `Foundations/Introduction` | What design tokens are, how the multi-theme system works, where to start |
| `Foundations/Color` | Per-theme palette grids (Slate Developer prominent; others under accordion); semantic-token explanation; contrast pairs with WCAG annotations; do/don't examples |
| `Foundations/Typography` | Full type scale rendered in real prose, weight axes, code-vs-prose pairings, tabular figures example, line-height + measure rules, do/don't |
| `Foundations/Spacing` | Visual rhythm strips for the 4px scale; spacing applied in real component layouts; gap vs margin guidance |
| `Foundations/Motion` | Live demos of standard easings + durations; reduced-motion handling; do/don't |
| `Foundations/Iconography` | Lucide grid with usage rules (size, semantic mapping, pairing with text); custom icons (if any) |
| `Foundations/Accessibility` | Existing content + live focus-ring demo + screen-reader callouts demonstrated |
| `Foundations/Visual Directions` | **Live gallery** — render a small representative panel under each of the 14 `data-prep-theme` values side-by-side (or stacked); replaces the current static table |

### 3.3 Primitives / Patterns — overview MDX

Each top-level gets one MDX intro page that:
- Frames what's in this tier
- Shows thumbnails of each story (linked)
- Calls out usage guidelines

| Page | Content |
|---|---|
| `Primitives/Introduction` | Map of the atomic building blocks; how to compose them |
| `Patterns/Introduction` | Map of recipes (links to each composed pattern) |

### 3.4 Patterns — composed recipes (the big new tier)

Each pattern is a workflow story that composes multiple components. These are the design-system equivalent of Polaris's "App settings layout" / "Resource details layout" pages.

| Pattern | Composes |
|---|---|
| `Patterns/Search Workflow` | SearchPanel + ContextOptions + SearchResults + ContextOutput — narrative: "user types query, refines context, reads result with citations" |
| `Patterns/Build Workflow` | BuildCard + BuildProgress + StatusBadge — narrative: "user kicks off build, watches progress, sees status outcome" |
| `Patterns/Settings Composition` | Section + SettingRow + Toggle + Select — narrative: "how a settings page is laid out" |
| `Patterns/Modular Dashboard Composition` | ModularDashboard + PanelChrome + PanelPicker — adapted from the existing `layout/Introduction.mdx` |
| `Patterns/State Patterns` | EmptyState + Loading + Error variants — already exists as a story; promote to a richer page |
| `Patterns/Modal Flow` | Confirm Dialog + Bug Report Modal (when sanitized) — focus traps, escape handling, accessible labels |
| `Patterns/Theme Switching` | Live demo of toggling theme/mode; shows how tokens cascade |
| `Patterns/Embedding in Marketing` | Demonstrates `<StoryEmbed>` usage in docs.sourceprep.io |

### 3.5 Dashboard — section overviews

Each Dashboard sub-section (Search, Trace, Build, Index, etc.) gets an `Overview.mdx` that introduces the section and embeds its components in a story-driven narrative.

| Page | Composes the section's stories |
|---|---|
| `Dashboard/Introduction` | Top-level intro to the dashboard surface |
| `Dashboard/Search/Overview` | SearchPanel, Components, ContextOutput, SymbolSearch in a workflow |
| `Dashboard/Trace/Overview` | Graph, AtlasLensPanel, NodeDetail, StatusCard |
| `Dashboard/Build/Overview` | BuildCard + BuildProgress (recovery panels stay internal until sanitized) |
| `Dashboard/Index/Overview` | IndexStatusCard + IndexStats + ActivityHeatmap + UsageGuide |
| `Dashboard/Project/Overview` | FolderTree, FolderTreePanel, FileExplorer, ProjectSettings |
| `Dashboard/LLM/Overview` | LLMStatus, EndpointManager, ModelCard |
| `Dashboard/Settings/Overview` | Section, AdvancedLLM, DeepAnalysis, Project Settings |
| `Dashboard/Watch/Overview` | WatchControls + StatusIndicator |
| `Dashboard/Agents/Overview` | AgentCard, AgentOps, ManagedEmployees, SystemAgents |
| `Dashboard/Team/Overview` | LicenseStatus, SyncStatus, TeamSyncIndicator |

### 3.6 Website — section overviews

| Page | Composes |
|---|---|
| `Website/Introduction` | Top-level intro: marketing site + docs + payments + support |
| `Website/Marketing/Overview` | Hero + FeatureBlocks + (eventual) full landing recipe |
| `Website/Demos/Overview` | AnimatedCLI + AnimatedIDE — narrative on how marketing demos are built |
| `Website/Research/Overview` | ResearchHero + ResearchSection + SourceCard + filters — narrative: how citations and sources work |

### 3.7 Voice / Content / Motion (future)

Polaris has dedicated `Content` and `Design` sections covering voice, copy patterns, and motion philosophy. These are lower priority but should be on the roadmap.

---

## 4. Authoring conventions

To keep contributions consistent:

1. **Every top-level section has an `Introduction.mdx`** that maps the section.
2. **Foundations are specimens, not glossaries** — render real components in real CSS to demonstrate the token. No "here's a hex code" tables.
3. **Patterns are workflows, not lists** — show the user journey through 2+ components composed.
4. **Use `<Canvas of={Story} />` to embed** existing stories rather than re-creating them inline. One source of truth.
5. **Avoid `<Source />` blocks in pages that ship publicly** — they re-introduce the originalSource leak from the security audit.
6. **Do/Don't examples are paired** — every "Do" gets a matching "Don't" with the visual contrast explicit.
7. **All embedded code samples are runnable** — copy-pasteable into a real `@prep/ui` consumer.
8. **MDX file naming**: PascalCase matching the title (e.g. `SearchOverview.mdx`); collocated with the section's stories where possible.

---

## 5. Phasing

Given 92 story files and ~334 entries, doing this all at once is unrealistic. Suggested phasing:

### v1 — Welcome + Foundations specimens (highest leverage)
- Rewrite `Introduction.mdx` as the welcome landing page
- Author `Foundations/Color`, `Foundations/Typography`, `Foundations/Spacing` as live specimens
- Refresh `Foundations/Visual Directions` with live theme gallery
- Update stale references in existing MDX (theme defaults, paths)

### v2 — Per-section overviews
- One `Overview.mdx` per Dashboard sub-section and Website sub-section
- Two-paragraph framing + embedded `<Canvas />` of representative stories

### v3 — Patterns
- The 8 patterns listed in §3.4
- Each one composes 2+ components into a workflow with narrative

### v4 — Voice / Motion / Iconography
- Polaris-style `Content` section (voice, tone, copy patterns)
- `Foundations/Motion` with live demos
- `Foundations/Iconography` with full Lucide grid

### v5 — Use cases / tutorials
- "Build your first dashboard panel" walkthrough
- "Embed components in a marketing site" tutorial (using `StoryEmbed`)
- "Theme switching" tutorial

---

## 6. Coupling with the taxonomy plan

The taxonomy in `01_taxonomy_research_and_proposal.md` defines the sidebar tree. This doc layers content onto that tree. Sequencing:

1. **Apply the taxonomy first** (renames, moves, hard rules from §3.5 of doc 01) — gets the structure right.
2. **Author Welcome + Foundations specimens (v1)** — gets the "designed-ness" baseline up.
3. **Author per-section overviews (v2) as those sections are migrated** — natural pairing with the taxonomy work.
4. **Patterns / Voice / Motion (v3 and v4)** — once the structural work is done.

Concretely: when the migration touches `Dashboard/Search/*`, the same PR or follow-up adds `Dashboard/Search/Overview.mdx`. Migration and authoring stay paired so we don't end up with renamed-but-empty sections.

---

## 7. Open questions

1. **Designer vs. dev authoring**: do we have someone authoring specimen MDX with real visual taste, or do we treat these as engineering artifacts? Polaris has a content team. We don't yet.
2. **Which themes are "supported" in public**: ship live previews of all 14 in `Foundations/Visual Directions`, or only 3–4 polished ones (Slate Developer + a couple of stylized variants)? The 14 might dilute the design-portfolio impression.
3. **Brand image refresh**: the welcome page hero needs visual hooks (logo, screenshot, mini-demo). What assets do we have, and do we want to commission anything?
4. **Source previews on patterns**: Patterns benefit from showing real composed JSX. Do we accept the `<Source />` IP-leak risk for Patterns (they're showcase-y) or stick with `<Canvas />`-only? If we accept it, scope to Pattern pages and audit the rendered JSX.
5. **Marketing/website parity**: should the marketing site (sourceprep.io) reuse this Storybook for design-eng visitors, or maintain its own showcase? Probably keep one.
6. **Scope of v1**: is "Welcome + 4 Foundations specimens + Visual Directions live gallery" the right v1 cut, or is that too much for a first pass?

---

## 8. Out of scope

- New components (this is purely documentation work).
- Visual redesign of existing components.
- Changes to the taxonomy (those live in doc 01).
- Marketing-site copy.

---

## 9. Status of menu restructure plan

Doc 01's hard rules (§3.5) and complete misplacement table (§4.1.a, 4.1.b) are the current taxonomy spec. Open items still under review:

- **Source-of-truth question**: doc 01 §6.5 — should we rename component files to match story titles, or only rename the story `title:` strings? File renames touch the components, the imports, and the dashboard. Story-only renames are 1-for-1 with the table.
- **VS Code surface** (doc 01 §6.3): should `Dashboard/VS Code/` exist as a sub-tree, or do VS Code components reuse `Dashboard/...` stories without distinction? Defer until the VS Code extension's UI catalog stabilizes.
- **`Patterns/` tier earning its keep**: doc 01 §6.2 — the v1 plan keeps four entries (PanelChrome, PanelPicker, StatePatterns, KeyboardShortcuts). The new patterns from §3.4 of *this* doc would push the count to ~12, justifying the tier solidly.
- **Modals/ population**: BugReportModal + ConfirmDialog start it. Need a third before it visibly earns its top-level — Pattern `Modal Flow` (§3.4) can pull double duty as the section intro.

The taxonomy is "ideal" enough to begin executing; further iteration belongs in PRs as we hit edge cases. Recommend re-running this through `prep` MCP once the daemon is back up, scoped to `packages/ui/src/`, to surface anything we've missed at the structural level.
