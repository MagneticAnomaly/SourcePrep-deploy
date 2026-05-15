# Phase 137 — Docs Live Asset Integration

> **Origin date:** 2026-05-14
> **Last updated:** 2026-05-14 (night) — post-Phase-132 desk completion
> **Source:** Phase 132 (docs behavioral fidelity) noticed live `<StoryEmbed>`
> iframes were 404-ing on the production docs site (`docs.sourceprep.io`).
> **Status:** Tech fix landed locally (not yet pushed). Phase 132 desk work
> COMPLETE. Page audit ready to start — but see new dependency on Phase 138
> below. Animation showcase strategy added as `05_animation_showcase_strategy.md`.

## Why this phase exists

The public docs site has two classes of "live" embedded content:

1. **Storybook iframes via `<StoryEmbed>`** (`websites/apps/docs/src/components/StoryEmbed.tsx`)
   — embeds real React panels from the `@prep/ui` design system, sandboxed and
   loaded from a separate origin (`storybook.sourceprep.io`).
2. **Animated CLI/IDE demos** (`packages/ui/src/components/console/AnimatedCLI.tsx`,
   `AnimatedIDE.tsx`) — scripted animations driven by `demo-scripts.ts`. Used
   inline on docs pages to show what a `prep` tool call *looks like* in
   Claude Code / Cursor / etc.

Two problems surfaced:

1. **Iframes broke in production.** The env var the iframe wrapper reads
   (`NEXT_PUBLIC_STORYBOOK_URL`) was unset on the docs Netlify environment,
   so every `<StoryEmbed>` fell back to a relative path `/storybook` — which
   on the docs origin resolves to `not-found.tsx`. Every embed rendered the
   docs site's own 404. Fixed locally in `01_tech_fix.md`; deploys when the
   netlify.toml change is pushed.
2. **Placement is ad-hoc.** Several docs pages that would clearly benefit from
   a live embed don't use one (most `/guides/*`, `/concepts/*` other than
   `/concepts/code-graph`). Others use embeds chosen opportunistically rather
   than from a survey. There's no inventory anywhere that lists what stories
   and animations are actually available — so authors of new docs pages don't
   know what to reach for.

This phase fixes both. The technical part is small (one env var). The
strategic part is the substantial work: walk every docs page, decide whether
it should host a live embed or animation, and write down exactly *where on
the page* it belongs.

## Sequencing — UPDATED 2026-05-14

**Phase 132 desk work is COMPLETE.** Text on every audited page is now stable
— see `docs/Phase132_DocsBehavioralFidelity/00_progress_tracker.md` for the
full ledger. But a new dependency emerged during Phase 132 audit:

**NEW BLOCKER: Phase 138 (Concepts rename + explainer migration) should land
BEFORE the Phase 137 page audit.** Phase 138 will:

1. Rename the `/concepts/` docs section (likely to `/how-it-works/`) — URL changes
2. Move 4 explainer guides (`/guides/embeddings`, `/guides/compression`,
   `/guides/smart-search`, `/guides/dynamic-model-loading`) into the renamed
   section — URL changes for 4 more pages
3. Migrate those 4 pages to `ConceptPageShell` layout — page structure changes

If Phase 137 page audit runs first, every placement decision for those 8
pages would need migration when Phase 138 lands. Phase 138 is small (URL
moves + layout wrap) but it touches the same set of pages we'd audit.

Updated order:

1. ✅ **Phase 132 desk work** — DONE.
2. **Phase 138** — Concepts rename + explainer migration. Blocked on user
   picking the new section name. Plan at
   `docs/Phase138_DocsConceptsRename/00_README.md`.
3. **Phase 137 page audit** — populate `03_page_audit.md` against the
   *post-Phase-138* URL structure.
4. **Phase 137 roll-up** — fill `04_placement_matrix.md`.
5. **Phase 137 implementation** — actually add `<StoryEmbed>` / `<AnimatedCLI>`
   nodes to pages. Per-instance customization (heights, captions, prop
   overrides) happens here too.

**Fallback if Phase 138 keeps slipping:** the page audit could run on the
pre-Phase-138 URLs as a pencil draft, then get re-keyed to the post-138
URLs once they land. Adds maybe 30 minutes of mechanical work. Not free,
but not blocking.

The technical fix (env var in `websites/apps/docs/netlify.toml`) is
independent of this sequencing and ships immediately — it doesn't depend on
either phase being complete.

## Out of scope for Phase 137

- **Authoring new stories or animations.** If the audit finds a needed asset
  doesn't exist (e.g., no story for `RoadmapPanel` in a configuration we want
  to feature), file a follow-up; don't author it inline.
- **Per-instance customization** of embeds. Get placement right first; tune
  heights, captions, and prop overrides in a separate pass.
- **Marketing site embeds.** Marketing has its own embed posture and is not
  in scope.
- **Refactoring `StoryEmbed.tsx` or the animation components.** Use as-is.
- **New docs page authoring.** This phase audits existing pages.

## Folder map

| File | Status | Purpose |
|---|---|---|
| `00_README.md` | ✅ this file | Phase intro + handoff context |
| `01_tech_fix.md` | ✅ landed locally | netlify env-var fix; iframe security audit |
| `02_asset_inventory.md` | ✅ initial inventory | All stories + CLI/IDE assets available, by category |
| `03_page_audit.md` | ⏸ skeleton only | Per-page audit template + page list — populate after Phase 138 |
| `04_placement_matrix.md` | ⏸ skeleton only | Summary table + gap list — populated last |
| `05_animation_showcase_strategy.md` | ✅ added 2026-05-14 | CLI + IDE animation analysis: what we have, where it belongs, when to use the native React path vs the iframe path |

## Definition of done

1. **Live iframes render on docs.sourceprep.io.** Verify after the netlify
   env-var change ships — visit `/dashboard`, `/mcp`, `/cli`, the embed should
   show the real Storybook component, not the docs 404. DevTools Network
   should show iframe `src` starting with `https://storybook.sourceprep.io/`.
2. **Every docs page in scope has a row in `03_page_audit.md`** with one of:
   "embed X at location Y", "animation Z at location W", or an explicit
   "no embed/animation needed" verdict.
3. **`04_placement_matrix.md` summarizes the full plan** as one cross-table
   (page × asset) plus a gap list (stories/animations that should exist but
   don't, with rationale).
4. **Implementation** — every recommendation in the matrix is either
   applied to the page or punted to a follow-up phase with a reason.

## Handoff context for the next AI session

If you're picking this up fresh (e.g., after `/compact`), read this section
first — it covers what's loaded in context already and what you need to
re-derive.

### What's already done

- `websites/apps/docs/netlify.toml` was edited to add
  `NEXT_PUBLIC_STORYBOOK_URL = "https://storybook.sourceprep.io"`.
  The change is **local only** — not yet committed, not yet pushed. Per
  memory `feedback_explicit_push_only.md`, do not push without explicit user
  signal ("push", "deploy", "ship").
- Phase 137 folder is scaffolded with all six docs. `00`, `01`, `02`, `05`
  have content; `03` and `04` have skeletons only and are ready to populate
  *after Phase 138 lands*.
- **Phase 132 (docs behavioral fidelity) is COMPLETE for desk work.**
  ~17 fidelity fixes landed across 13+ pages. Progress tracker at
  `docs/Phase132_DocsBehavioralFidelity/00_progress_tracker.md`. Findings
  memo at `docs/Phase132_DocsBehavioralFidelity/99_findings_memo.md`.
- **Phase 138 scaffolded** at `docs/Phase138_DocsConceptsRename/00_README.md`.
  Blocked on user picking the new section name. Need to land before Phase
  137 page audit.
- **Animation showcase strategy** drafted at `05_animation_showcase_strategy.md`.
  This is the substantive analysis of *what CLI/IDE animations exist, where
  they naturally belong, and how to embed them*. Read this before starting
  the page audit — it's the thinking that should drive animation placements.

### What's NOT done

- The page audit in `03_page_audit.md` is still skeleton only. **Do not
  start it until Phase 138 lands** (or accept the rework cost of
  retro-keying URLs).
- The placement matrix in `04_placement_matrix.md` is empty.
- No new embeds have been added to any pages yet.
- The netlify.toml change has not been pushed and is therefore not live.

### What changed in Phase 132 that affects Phase 137 inputs

Phase 132 rewrote substantive content on several pages. The asset inventory
and animation showcase strategy below were updated to account for the
new state:

- `/guides/models` was renamed to **"AI Gateway"** and rewritten — the
  Model Setup Advisor (`/guides/model-advisor`) was deprecated and hidden
  from sidebar+sitemap. **Page list correction:** drop
  `/guides/model-advisor` from the audit scope. It's unreachable.
- `/guides/codebase-audit` had its "Four MCP tools" section rewritten into
  a single-tool-with-action-modes section. The old `prep_audit_*` aliases
  are LEGACY routing artifacts not surfaced to MCP clients.
- `/getting-started/page.tsx` had its Free-tier-trace claim rewritten and
  the "language-aware compression: built in" claim reworded as roadmap.
- `/concepts/indexing` storage backend claim was tightened to "stored
  locally on your machine" (was incorrectly claiming LanceDB/Qdrant/Chroma).
- `/concepts/context` scoring step was rewritten to reference the real
  7-intent classifier + file-type weights (was a confused 4-bucket claim).
- The 4 explainer guides (`embeddings`, `compression`, `smart-search`,
  `dynamic-model-loading`) are slated to migrate to a renamed Concepts
  section in Phase 138. Their content is final; only their URL + layout
  changes pending.

These changes don't invalidate any embeds already on those pages, but the
section/anchor IDs may have shifted slightly. Re-derive anchors from each
page during the audit.

### Decision points the next AI should confirm with the user

1. **When to push the netlify fix.** It's safe — single env var, no behavior
   changes, no security regression — but the user gates pushes explicitly.
2. **Wait for Phase 138 or run the page audit now and re-key URLs later?**
   Recommended: wait if Phase 138 is going to land within a week or two.
   Otherwise run the page audit now and accept the ~30-minute URL re-keying
   cost when Phase 138 lands.
3. **Scope of "in scope" docs pages.** After Phase 132 corrections, the
   current scope is ~23 pages (dropping `/guides/model-advisor` which is now
   hidden). Phase 138 will not change the count, just the URLs of 8 of them.
4. **Native React vs iframe path for CLI/IDE animations.** See
   `05_animation_showcase_strategy.md` for the recommended rubric.
   Confirm with user before mass-implementing one path or the other; this is
   a perf + maintenance tradeoff worth surfacing.

### Key files for context

| File | Purpose |
|---|---|
| `websites/apps/docs/src/components/StoryEmbed.tsx` | The iframe wrapper (theme-locked, sandboxed) |
| `websites/apps/docs/src/components/StoryEmbed.css` | StoryEmbed styling |
| `packages/ui/src/components/console/AnimatedCLI.tsx` | Animated CLI component |
| `packages/ui/src/components/console/AnimatedIDE.tsx` | Animated IDE component |
| `packages/ui/src/components/console/demo-scripts.ts` | 21+ named CliScript exports + 7 grouped CliScript[] arrays |
| `packages/ui/src/stories/**/*.stories.tsx` | All Storybook stories (~80 files across 24 categories) |
| `packages/ui/netlify.toml` | Storybook deploy config — CSP allows `frame-ancestors *.sourceprep.io` |
| `websites/apps/docs/netlify.toml` | Docs deploy config — env var added in this phase |
| `docs/Phase68_revise-marketing/07_Storybook_Embed_Architecture.md` | Iframe security design of record |
| `docs/Phase131_StorybookCuration/02_visual_design_plan.md` | Storybook theme defaults for docs embeds |

### How to read this folder

- `01_tech_fix.md` — read first if a future fidelity issue with iframes shows
  up; documents the security model end-to-end.
- `02_asset_inventory.md` — read whenever you need to know what's available
  to embed.
- `03_page_audit.md` — the main working doc once Phase 132 is done.
- `04_placement_matrix.md` — the deliverable for engineering hand-off; one
  table you can scan to see the full plan.
