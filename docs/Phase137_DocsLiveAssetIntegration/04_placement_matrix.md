# Phase 137 — Placement Matrix

> **Status:** Populated 2026-05-14 from `03_page_audit.md`. Engineering
> hand-off doc. Captions and detailed reasoning live in `03_page_audit.md`;
> this file is the cross-cutting view.
>
> **Implementation pass SHIPPED 2026-05-27 (commit pending — Lane A).**
> All 29 placements wired across the in-scope pages. `<StoryEmbed>` iframe
> wrapper deprecated and deleted; replaced by 24 native React `<Demo*>`
> wrappers in `websites/apps/docs/src/components/demos.tsx`. `next build`
> green; `tsc --noEmit` clean. Both `mcp/ides` and `mcp/terminal` also
> received `"use client"` directives in a follow-up commit so they could
> import `MCP_TOOLS` from the `@prep/ui` client bundle without the webpack
> server-component error.
>
> **Phase 138 URL re-key complete:** rows tagged ★ now live under
> `/how-it-works/`. Mechanical sweep; placement decisions carry over.

## Deep-think densification pass (2026-05-14 evening)

The original audit was too conservative on "NONE" verdicts. User feedback:
the named CLI scripts and storybook stories were always meant to power the
docs pages that describe those features — staging them in the design system
isn't the destination, it's the on-ramp. Re-audit produced 16 additional
placements across 11 pages, wired in the same evening.

**Misses pass (panels matched 1:1 to page content):**

| Page | Asset(s) added | Where |
|---|---|---|
| `/how-it-works/indexing` ★ | `BuildCard` (building) + `IndexStats` (default) + `IndexStatusCard` (loaded) | `#pipeline`, `#exclusions`, `#ui-controls` |
| `/how-it-works/embeddings` ★ | `ModelCard` (connected-with-model-and-test-result) | `#configuring` |
| `/how-it-works/compression` ★ | `ContextOutput` (default) | After `#response-metadata`, before `#supported-languages` |
| `/guides/concurrency-discovery` | `LLMStatusWidget` (default) | After `#what-youll-see` |
| `/how-it-works/dynamic-model-loading` ★ | `AdvancedLLMSettings` (default) | After `#how-it-works` |
| `/troubleshooting` | `LogConsole` (pipeline-run) + `<AnimatedIDE script={ideDoubleSubmitFixDemo}>` | `#performance`, new `#ai-handoff` section |

**Densification pass (additional embeds on already-wired pages):**

| Page | Asset(s) added | Where |
|---|---|---|
| `/getting-started` | `IndexStatusCard` (loaded) | After step 3 ("Add Your Repo") |
| `/mcp` | `AgentOpsPanel` (active) | Added to `#live-preview` grid |
| `/mcp/paperclip` | `<AnimatedCLI script={prepOverviewDemo}>` | After `#tools` heading |
| `/how-it-works/code-graph` ★ | `NodeDetailPanel` (file-node) | After visualization story embed |
| `/how-it-works/graph-enrichment` ★ | `AtlasLensPanel` (stale-with-segments) | Closing `#understanding` section |
| `/how-it-works/context` ★ | `ContextOutput` (default) | After the closing CLI animation |
| `/dashboard` | `AgentOpsPanel` + `RoadmapPanel` (with-content) + `ActivityHeatmap` (mixed-activity) + `<AnimatedIDE script={ideLoadingSkeletonDemo}>` | New h3 sub-sections under `#key-panels`, plus new `#agent-live` h2 |

**Total docs-site placements after both passes:** 29 across the in-scope pages (13 from the original implementation + 16 from the densification pass).

## Implementation pass notes (2026-05-14)

- **`@prep/ui` export expansion** — added `export` to the 21 named CliScript
  consts in `packages/ui/src/components/console/demo-scripts.ts` and extended
  the re-export list in `packages/ui/src/index.ts`. Docs pages can now import
  specific scenarios by name (`prepTldrOverviewDemo`, `auditPrSanityCheckDemo`,
  `impactExtractServiceDemo`, `ideAddCsvExportDemo`, etc.) instead of relying
  on the first-pick aliases.
- **Client-component boundary** — `@prep/ui/dist/index.js` uses
  `React.createContext` (client-only). Docs `page.tsx` files default to
  server components and several already export `metadata`, which is
  server-only. Added a thin client wrapper at
  `websites/apps/docs/src/components/cli-demos.tsx` that re-exports the
  animations + scripts with `"use client"` at the top, so pages can stay
  server components.
- **Bundle-size cost** — any page that imports from `cli-demos.tsx`
  currently pulls the full `@prep/ui` chunk into its first-load JS. Animation
  pages jumped from ~88 kB first-load to ~647 kB (+560 kB). This is a real
  cost on docs-site cold loads. Mitigation options for a follow-up phase:
  (a) tree-shake `@prep/ui` by switching to per-component exports;
  (b) carve out a dedicated `@prep/ui/console` entry point with only the
  CLI/IDE components and scripts; (c) copy the animation components into
  the docs site directly. Not addressing in this phase — flagged for
  user awareness.
- **`Image as ImageIcon` cleanup** — `/guides/path-weights/page.tsx` had a
  stale `ImageIcon` import only used by the screenshot placeholder I
  replaced. Cleaned up. `/getting-started/page.tsx` also has a stale
  `ImageIcon` import; left as-is because removing it is outside this
  phase's scope.

## How to use this doc

This is the engineering hand-off. After the per-page audit in
`03_page_audit.md` is complete, fill in the matrix below. Each populated row
should be implementable without re-reading `03_page_audit.md` — captions and
heights live there; this doc is for the cross-cutting view.

## Placement matrix

| Page | Asset(s) | Location on page | Story ID / script | Path | Status |
|---|---|---|---|---|---|
| `/` | NONE | — | — | — | ❌ punted (hero off-limits + card grid suffices) |
| `/getting-started` | `<AnimatedCLI>` (swap existing iframe) | After step 2 "Launch the App" (`#start-daemon`) | `prepTldrOverviewDemo` | A | ✅ shipped (swap landed) |
| `/getting-started` | `<AnimatedCLI>` (new, optional) | After step 6 "Run a quick audit" (`#audit`) | `auditPrSanityCheckDemo` | A | ✅ shipped |
| `/getting-started/installation` | NONE | — | — | — | ❌ punted (install steps = screenshot territory, out of scope) |
| `/getting-started/quick-start` | `<AnimatedCLI>` | After step 1 in `#five-minute-guide` | `prepTldrOverviewDemo` | A | ✅ shipped |
| `/mcp` | `<StoryEmbed>` × 2 (existing) | Under `#live-preview` | `dashboard-search-searchpanel--default`, `dashboard-index-indexstatuscard--loaded` | B | ✅ shipped (verify in dev-server walkthrough) |
| `/mcp` | `<AnimatedCLI>` (new) | After the tools-reference table (`#tools-reference`) | `prepTldrOverviewDemo` | A | ✅ shipped |
| `/mcp/ides` | `<AnimatedIDE>` (swap existing iframe) | Under `#setup` | `ideAddCsvExportDemo` | A | ✅ shipped (swap landed; page also got `"use client"` so MCP_TOOLS import works) |
| `/mcp/terminal` | `<AnimatedCLI>` | Under `#setup`, before first CLI config block | `prepSearchDemo` | A | ✅ shipped (page also got `"use client"` so MCP_TOOLS import works) |
| `/mcp/paperclip` | `<StoryEmbed>` (existing) | Under `#ui` | `dashboard-agents-agentopspanel--active` | B | ✅ shipped (verify in dev-server walkthrough) |
| `/how-it-works/indexing` ★ | NONE | — | — | — | ❌ punted; 🔵 gap flagged for "indexing-in-progress" panel (low priority) |
| `/how-it-works/code-graph` ★ | `<StoryEmbed>` (existing) | Under `#visualization` | `dashboard-trace-graph--default` | B | ✅ shipped (verify in dev-server walkthrough) |
| `/how-it-works/code-graph` ★ | `<AnimatedCLI>` (new) | After numbered list under `#usage` | `impactExtractServiceDemo` | A | ✅ shipped |
| `/how-it-works/graph-enrichment` ★ | `<StoryEmbed>` (new) | After `#journey` overview, before Sync stage cards | `dashboard-pipeline-graphenrichmentpipeline--full-pipeline-running` | B | ✅ shipped — **highest-value new embed; 05 worksheet said "existing" but it isn't on this page** |
| `/how-it-works/context` ★ | `<AnimatedCLI>` (new) | After `#formatting`, before `#ui-controls` | `prepTldrOverviewDemo` | A | ✅ shipped |
| `/cli` | `<AnimatedCLI>` (swap existing iframe) | Under `#common-workflows` | `prepSearchDemo` | A | ✅ shipped (swap landed) |
| `/dashboard` | `<StoryEmbed>` × 6 (existing) | `#overview`, `#adding-panels`, `#index-status`, `#code-graph-coverage`, `#pipeline`, `#search-context` | `dashboard-layouts-fulldashboard--full-dashboard`, `patterns-panelpicker--default`, `dashboard-index-indexstatuscard--loaded`, `dashboard-trace-coveragepanel--default`, `dashboard-pipeline-graphenrichmentpipeline--full-pipeline-running`, `dashboard-search-searchpanel--full-search-demo` | B | ✅ shipped (verify in dev-server walkthrough) |
| `/how-it-works/embeddings` ★ | NONE | — | — | — | ❌ punted (selection guide; no fitting asset) |
| `/guides/audit-enrichment` | NONE (pending gap) | — | — | — | 🔵 gap — wants `prep_audit(findings=...)` enrichment animation (medium priority) |
| `/guides/codebase-audit` | `<StoryEmbed>` × 2 (existing) | `#overview`, `#pipeline-connection` | `dashboard-audit-auditpanel--with-findings`, `dashboard-audit-opportunitiespanel--with-opportunities` | B | ✅ shipped (verify in dev-server walkthrough) |
| `/guides/codebase-audit` | `<AnimatedCLI>` (new) | After `cli` subsection (h3) within `#quick-start` | `auditPrSanityCheckDemo` | A | ✅ shipped |
| `/how-it-works/smart-search` ★ | `<AnimatedCLI>` × 2–3 (new) | Within `#intents` paired with LOCATE + RATIONALE; optionally after `#evaluation-order` | `searchRetryReuseDemo`, `conceptsTransactionRuleDemo`, optional `searchMaxConnectionsDemo` | A | ✅ shipped — multi-animation outlier; 🔵 gap for routing-comparison script may collapse this to one |
| `/how-it-works/compression` ★ | NONE | — | — | — | ❌ punted (technical reference; tables carry it) |
| `/guides/concurrency-discovery` | NONE | — | — | — | ❌ punted (operational/FAQ; animation distracts) |
| `/guides/path-weights` | `<DemoFolderTreePathWeights>` (replaces placeholder) | Under `#using-the-dashboard` | path-weights-specific variant (page-tailored, supersedes original `scope-panel-named-populated` storyId) | A | ✅ shipped (implementer chose a dedicated demo variant over the generic story — better fit) |
| `/guides/path-weights` | `<AnimatedCLI>` (optional) | After `#how-it-works`, before dashboard section | `searchBuildWorkerDemo` | A | ⏸ deferred (low-confidence optional add; flagged for dev-server walkthrough decision) |
| `/guides/knowledge-scope` | `<StoryEmbed>` (existing) | Under `#using-the-dashboard` | `dashboard-project-foldertreepanel--scope-panel-named-populated` | B | ✅ shipped (verify in dev-server walkthrough) |
| `/guides/byok-batching` | `<StoryEmbed>` (existing) | Under `#how-batching-works` | `dashboard-llm-endpointmanager--interactive` | B | ✅ shipped (verify in dev-server walkthrough); 🔵 gap for future cost-banner panel (low priority) |
| `/guides/models` | `<StoryEmbed>` (existing) | Under `#model-slots` | `dashboard-llm-aimodelssettings--default` | B | ✅ shipped (verify in dev-server walkthrough) |
| `/guides/team-sync` | `<StoryEmbed>` (existing) | Under `#how-it-works` | `dashboard-team-syncstatuscard--up-to-date` | B | ✅ shipped (verify in dev-server walkthrough); further work deferred (external-repo dependency) |
| `/how-it-works/dynamic-model-loading` ★ | NONE | — | — | — | ❌ punted (informational; local LLMs secondary path) |
| `/search` | NONE | — | — | — | ❌ punted (page is itself an interactive UI) |
| `/troubleshooting` | NONE | — | — | — | ❌ punted (text-heavy reference); 🔵 gap for `BugReportModal` placement (defer — needs copy work) |

**Path column:** `A` = native React (`<AnimatedCLI>` / `<AnimatedIDE>` imported from `@prep/ui`); `B` = iframe via `<StoryEmbed>`. See `05_animation_showcase_strategy.md` for the rubric.

**★ Phase 138 move:** URL re-keys to `/{new}/...` when Phase 138 lands (concepts rename + 4 explainer guides migration). Anchor IDs and placement decisions carry over unchanged.

Status legend:
- ⏸ pending audit — entry not filled in yet
- 🟡 audit done, implementation pending — row populated, embed not yet wired
- ✅ shipped — embed is live on the page
- ❌ punted — no embed; reason in `03_page_audit.md`
- 🔵 gap — needs a story/animation that doesn't exist yet

## Gap list

Stories/animations that should exist but don't, identified during the audit.
Each entry becomes a follow-up task.

| # | Gap | Pages that want it | Why | Priority | Follow-up task |
|---|---|---|---|---|---|
| 1 | "Fresh project — first call to `prep`" script | `/getting-started`, `/getting-started/quick-start` | Onboarding-specific framing; existing `prepTldrOverviewDemo` is serviceable but reuses a generic task-driven script | Low | TBD (file when Phase 137 implementation pass runs) |
| 2 | "Intent routing comparison" animation (side-by-side LOCATE vs RATIONALE) | `/how-it-works/smart-search` | Page thesis is "different inputs route to different backends"; side-by-side is the cleanest visual; today requires 2–3 separate `<AnimatedCLI>` instances | Medium | TBD |
| 3 | `prep_audit(findings=[...])` enrichment animation | `/guides/audit-enrichment` | Existing audit scripts show *triggering* an audit; this page is about *enriching* external lint findings — different workflow | Medium | TBD |
| 4 | "Path Weights" / weight-badge Storybook variant | `/guides/path-weights` | Page has a `Screenshot: Path Weight Badges` placeholder; current `FolderTreePanel` scope-panel variant may not show weight badges — verify during implementation | Medium | TBD |
| 5 | "Concepts panel" Storybook story | (none in-scope today) | `ConceptsPanel` lives in `packages/ui/src/components/concepts/` but isn't storied; blocks future concepts-pipeline page | Low | TBD |
| 6 | Cost-banner / token-counter panel story | `/guides/byok-batching` (future) | Page mentions cost-tier UI; no story exists yet | Low | TBD |
| 7 | "Indexing in progress" panel (discovery → parse → embed) | `/how-it-works/indexing` | Page describes the pipeline but no "live running" visual exists; `IndexStatusCard--loaded` shows steady state, not progress | Low | TBD |
| 8 | `BugReportModal` placement on `/troubleshooting` | `/troubleshooting` | Story exists; needs page copy authorship (new "How to file a bug" section) to host it — not a story gap so much as a docs-content gap | Low | TBD (Phase 132 desk follow-up territory) |

## Implementation order

Once all rows are populated, suggested implementation order:

1. **Push the netlify env-var fix first.** Gate on user signal. Without it, every existing iframe 404s on production. See `01_tech_fix.md`.
2. **Verify-existing pass.** Walk every row marked "verify keeps" with a dev-server preview. Cheap and surfaces any drift from the inventory. Affected: `/mcp`, `/mcp/paperclip`, `/how-it-works/code-graph`, `/dashboard` (×6 embeds), `/guides/codebase-audit` (×2), `/guides/knowledge-scope`, `/guides/byok-batching`, `/guides/models`, `/guides/team-sync`.
3. **High-impact swaps and adds — onboarding + MCP**, in this order:
   1. `/getting-started` step 2 swap → Path A
   2. `/mcp/ides` swap → Path A
   3. `/cli` swap → Path A
   4. `/mcp` + tools-table animation
   5. `/getting-started/quick-start` lead animation
   6. `/getting-started` step 6 animation (only if rhythm allows after step 2 lands)
   7. `/mcp/terminal` lead animation
4. **Concept-page additions:**
   1. `/how-it-works/graph-enrichment` pipeline embed — **highest-value new asset; 05 worksheet was wrong about this being "existing"**
   2. `/how-it-works/code-graph` impact animation
   3. `/how-it-works/context` closing animation
5. **Guide additions:**
   1. `/guides/codebase-audit` CLI animation
   2. `/how-it-works/smart-search` multi-animation (LOCATE + RATIONALE)
   3. `/guides/path-weights` scope embed (replaces screenshot placeholder)
6. **Per-instance customization pass.** Captions, heights, prop overrides (`loop`, `loopDelayMs`). Last pass, informed by what looks right in production after step 1-5 ship.
7. **Visual regression sweep.** Dev-server walkthrough. Confirm no broken layouts, no animation overlap with text, no oversized embeds breaking page rhythm.
8. **File gap follow-ups.** Open phase/task tickets for the 8 gap-list entries. Don't block Phase 137 close on these.

## Definition of done

- Every row populated (no ⏸ left) — ✅ complete
- Every gap has a follow-up task ID — ⏸ pending implementation pass (tickets opened at step 8)
- Implementation order is clear enough for engineering to start at the top
  without re-reading `03_page_audit.md` — ✅ complete
