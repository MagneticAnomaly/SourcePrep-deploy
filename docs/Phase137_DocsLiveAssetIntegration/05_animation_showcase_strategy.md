# Phase 137 — CLI + IDE Animation Showcase Strategy

> Added 2026-05-14. The other Phase 137 docs cover *whether* to embed and
> *what to embed*; this doc covers the substantive analysis for the
> CLI/IDE animations specifically — what we have, what each script teaches,
> where each one naturally belongs, and the integration-path decision rubric.
>
> Read this BEFORE filling in `03_page_audit.md` for any page that's a
> candidate for animations. The thinking here should drive the placement
> decisions.

## The two integration paths

The animations can land on a docs page two ways. The choice matters for
performance, theme consistency, and maintenance:

### Path A — Native React (`<AnimatedCLI>` / `<AnimatedIDE>`)

```tsx
import { AnimatedCLI, prepOverviewDemo } from '@prep/ui';

<AnimatedCLI script={prepOverviewDemo} className="my-8" />
```

**Pros:**
- Zero iframe overhead (no extra network round-trip, no sandboxing context switch)
- Inherits the docs site's theme automatically via CSS variables
- Smallest visual footprint — no Storybook chrome
- Server-rendered shell + client-side animation = fast first paint
- Easiest to A/B with different scripts (just swap the prop)

**Cons:**
- Pulls `@prep/ui` into the docs bundle (already a dependency, so the
  marginal cost is small but real)
- Requires the docs page to import + position the component explicitly
- Theme is locked to whatever the docs site renders — no per-instance
  theme experimentation

### Path B — Iframe via `<StoryEmbed>`

```tsx
import { StoryEmbed } from '../../components/StoryEmbed';

<StoryEmbed
  storyId="website-demos-animatedcli--project-overview"
  height={350}
  caption="The prep tool returns ambient context — modules, hubs, focus areas."
/>
```

**Pros:**
- Themed via Storybook's parameters — locks to `prepTheme:m` (Retro Aurora) +
  `docsMode:true` for consistency with other Storybook embeds on docs
- Sandboxed origin — no risk of script bleed into the docs page
- Same path as other panel embeds — visually consistent within a page that
  also uses iframe embeds for non-animation content
- Easy for design to iterate on themes without touching docs source

**Cons:**
- Iframe loading time (the storybook bundle has to boot before the animation
  starts)
- Extra origin round-trip (matters on slow networks)
- Requires the env var fix (`NEXT_PUBLIC_STORYBOOK_URL`) to be deployed
- Theme is locked to the Storybook parameter; no live override from docs

### Decision rubric

| Situation | Recommended path |
|---|---|
| The page already has other iframe embeds (panel screenshots, dashboard shots) and we want visual consistency | **Path B** (iframe) |
| The page is a pure prose explainer with one animation as the lead visual | **Path A** (native React) |
| The animation is THE main payload (e.g., MCP overview page) and we want it loading instantly | **Path A** (native React) |
| The animation needs the Storybook chrome (frame, viewport sizing controls visible) | **Path B** (iframe) |
| Multiple animations on one page — risk of "iframe slowness compounding" | **Path A** (native React) for all |

**Default:** Path A (native React) unless the page is already iframe-heavy.

## What animations exist (recap)

Detail in `02_asset_inventory.md`. Quick reference:

### CLI animations — `<AnimatedCLI>` driven by `demo-scripts.ts`

Six tools × 3 scenarios each = **18 CLI scripts**, plus 3 IDE scripts.
Each tool has a grouped array (`prep<X>Demos: CliScript[]`) and a
convenience "first demo" export (`prep<X>Demo: CliScript`).

| Tool | Grouped array | Scenarios |
|---|---|---|
| `prep` | `prepDemos` | rate-limiting overview · TLDR / atlas / hubs · "add a webhook" intent |
| `prep_search` | `prepSearchDemos` | retry/reuse · max-connections · build-worker |
| `prep_impact` | `prepImpactDemos` | delete-unused · extract-service · async-migration |
| `prep_audit` | `prepAuditDemos` | PR sanity check · security scan · type tightening |
| `prep_observe` | `prepObserveDemos` | caching recall · investigation recall · save ownership |
| `prep_concepts` | `prepConceptsDemos` | transaction rule · queue pitfalls · build/refund |

### IDE animations — `<AnimatedIDE>` driven by `ideDemos: CliScript[]`

| Script | Scenario |
|---|---|
| `ideDoubleSubmitFixDemo` | Agent fixing a double-submit bug |
| `ideLoadingSkeletonDemo` | Agent adding loading skeleton |
| `ideAddCsvExportDemo` | Agent adding CSV export |

The IDE animations show *the AI editing code in an IDE pane while SourcePrep
context is visible alongside*. These are heavier visuals — closer to "watch
a 90-second screencast" than "tiny CLI vignette".

## Where each animation naturally belongs

This is the placement thesis that should drive the page audit. Each
recommendation here is a starting point; the audit can override with
better evidence.

### `prep` — ambient context

**Best fit:** any page describing "what `prep` returns when called with no args".

- **`/getting-started`** (parent) — already has a CLI embed; refresh it to
  use `prepOverviewDemo` (`prepTldrOverviewDemo` or `prepRateLimitingDemo`)
  via native React. Pulls double duty: "this is what the trust loop
  feels like" + "this is what `prep` actually shows you".
- **`/mcp`** (overview page) — the `prep` row in the tool table would
  benefit from a small inline `<AnimatedCLI>` (any `prepDemos[*]`) sitting
  right after the row.
- **`/concepts/context`** — the page's narrative is the assembly pipeline;
  a `prep` demo at the bottom anchors "this is what comes out the other end".

**Script picks:**
- `prepTldrOverviewDemo` — best for first-page placements (most expository)
- `prepRateLimitingDemo` — best for security-leaning placements
- `prepBuildWebhookDemo` — best for "agent about to make a change" placements

### `prep_search` — semantic search

**Best fit:** any page about querying.

- **`/guides/smart-search`** — the seven-intent classifier description begs
  for a "what does this look like?" companion. Native React,
  `prepSearchDemos[*]`. Possibly multiple scripts side-by-side to show
  different intents routing differently.
- **`/concepts/context`** — Retrieval step on the assembly pipeline page.
- **`/guides/path-weights`** — show how a weighted path changes ranking
  output. `searchBuildWorkerDemo` or similar.

**Script picks:**
- `searchRetryReuseDemo` — typical "find me X" scenario
- `searchMaxConnectionsDemo` — config-tuning intent
- `searchBuildWorkerDemo` — operational/debugging intent

### `prep_impact` — blast radius

**Best fit:** any page about safe code change.

- **`/concepts/code-graph`** — the page narrative already describes how
  agents use the graph for trace expansion. An `impactExtractServiceDemo`
  embed after the "How Agents Use It" section closes the loop.
- **`/guides/codebase-audit`** — adjacent to the refactor workflow
  description: show `prep_impact` finding dependents before the audit
  triggers a refactor.

**Script picks:**
- `impactDeleteUnusedDemo` — simplest mental model
- `impactExtractServiceDemo` — most impactful visual (lots of dependents)
- `impactAsyncMigrationDemo` — production-leaning scenario

### `prep_audit` — structural findings

**Best fit:** any page about codebase health.

- **`/guides/codebase-audit`** — obviously. The page already describes the
  analyzer set and the `prep_opportunities` CLI; an inline animation of
  `auditPrSanityCheckDemo` makes the workflow tangible.
- **`/guides/audit-enrichment`** — show the enrichment payload arriving
  via `auditSecurityScanDemo` or similar.
- **`/getting-started`** Step 6 (audit) — already references `prep_audit`;
  pair the prose with one of the audit demos.

**Script picks:**
- `auditPrSanityCheckDemo` — most relatable workflow
- `auditSecurityScanDemo` — security-leaning, good for marketing-adjacent pages
- `auditTightenTypesDemo` — code-quality framing

### `prep_observe` — cross-session memory

**Best fit:** any page about persistence + collaboration.

- **`/concepts/context`** — under the assembly pipeline, observe is what
  prevents "the agent forgets everything next session". One demo here
  makes the narrative concrete.
- **(Future) `/guides/observations`** — if/when a dedicated guide gets
  authored. Today the user-facing surface is limited; might be skippable.

**Script picks:**
- `observeCachingRecallDemo` — common debugging recall
- `observeInvestigationRecallDemo` — pair-investigation framing
- `observeSaveOwnershipDemo` — collaboration framing

### `prep_concepts` — business rationale

**Best fit:** any page about codified rules.

- **`/guides/smart-search`** RATIONALE intent section — show
  `conceptsTransactionRuleDemo` as the "why" answer.
- **(Future) `/concepts/concepts-pipeline`** — there's no dedicated page
  yet, but Phase 125 work may produce one.

**Script picks:**
- `conceptsTransactionRuleDemo` — clean business-rule case
- `conceptsQueuePitfallsDemo` — operational lessons-learned case
- `conceptsBuildRefundDemo` — domain-specific decision case

### IDE animations

**Best fit:** any page showing "what it looks like in a real editor".

- **`/mcp/ides`** — page already embeds `website-demos-animatedide--default`
  via iframe. **Recommend swap to native React** with `ideDemoScript`
  (`ideAddCsvExportDemo`) for the lead visual; keep iframe path for any
  secondary placements.
- **`/getting-started`** Step 4 (connect editor) — possibly. The page
  already has an `AnimatedCLI` embed for Step 2 ("Launch the App"); a
  second IDE embed under Step 4 risks visual overload. Decide during the
  audit.
- **`/`** (home page) — out of scope per memory `feedback_do_not_touch_hero`,
  but if a future iteration revisits the hero, this is a strong candidate.

**Script picks:**
- `ideAddCsvExportDemo` — most expository (clearly shows agent adding
  feature with `prep_impact` informing the decision)
- `ideLoadingSkeletonDemo` — UI-focused, good for visual-leaning placements
- `ideDoubleSubmitFixDemo` — bug-fixing scenario, paired well with
  audit/refactor narratives

## Asset gaps to file as follow-ups

Found during this analysis. None of them block the audit, but each one is
a candidate "follow-up phase" item:

1. **No `prep` "ambient context — first call" script** — the existing
   `prepDemos` cover specific tasks. A dedicated "fresh project, what does
   `prep` show?" script for the onboarding page would be cleaner than
   reusing `prepTldrOverviewDemo`. Low priority; the existing one is
   serviceable.
2. **No "intent routing" comparison animation** — `/guides/smart-search`
   would benefit from a side-by-side showing "where is X" routing to LOCATE
   vs "why does X use Y" routing to RATIONALE. Today you'd need to embed
   two separate `<AnimatedCLI>` instances.
3. **No animation showing `prep_audit(findings=...)` enrichment** — the
   audit-enrichment workflow page would benefit from a demo of piping a
   ruff JSON payload through `prep_audit` and getting structural context
   back. The existing audit scripts show *triggering* an audit, not
   enriching external findings.
4. **No "Concepts panel" Storybook story** — already flagged in
   `02_asset_inventory.md`. Affects any concepts/context-pipeline page.
5. **No "Scope panel — Knowledge Scope variant" story** — closest match is
   `FolderTreePanel.stories.tsx` `ScopePanelNamedPopulated` export. Verify
   during audit whether that's sufficient or if a dedicated variant helps.

## Recommended implementation order

When the page audit is done and we're ready to apply placements:

1. **Push the netlify env-var fix first.** Currently any existing iframe
   embeds 404 on production. Push gates on user signal but this is the
   prerequisite for anything else to work.
2. **Audit dependencies on Phase 138.** Whatever the 8 affected pages look
   like post-rename, the embed placements need to land on the new URLs.
3. **Per-page application, in user-impact order:**
   1. **`/getting-started` and `/mcp`** — onboarding + integration overview.
      First-time-visitor surfaces. Highest impact.
   2. **`/concepts/*`** — second visit, deeper learning. Anchors each
      concept with one canonical animation.
   3. **`/guides/{smart-search, codebase-audit, audit-enrichment}`** — the
      remaining guides with strong animation fits.
   4. **`/cli`** — small, may not need animations (it's a reference page);
      verify during audit.
   5. **`/dashboard` and `/troubleshooting`** — most text-heavy; likely
      minimal animation placements.
4. **Per-instance customization pass** (heights, captions, prop overrides
   like `loop` / `loopDelayMs`) — separate sub-pass once placement is
   right.
5. **Visual regression sweep** — once embeds are in, do a dev-server
   walkthrough to confirm no broken layouts, no animation overlap with
   text, no oversized embeds breaking page rhythm.

## Per-page placement worksheet

A starter cross-table to seed `03_page_audit.md`. Columns:
- **Page** — the route
- **Animation** — the recommended script (one or more, comma-separated)
- **Path** — A (native React) or B (iframe)
- **Confidence** — how strong is this recommendation?
- **Notes** — context / caveats / alternates

| Page | Animation | Path | Confidence | Notes |
|---|---|---|---|---|
| `/getting-started` | `prepTldrOverviewDemo` | A | High | Refresh existing CLI embed to use named script |
| `/getting-started` Step 4 | `ideAddCsvExportDemo` (or NONE) | A | Medium | May be visual overload with Step 2 already showing CLI |
| `/getting-started` Step 6 | `auditPrSanityCheckDemo` | A | Medium | Strong fit; small risk of page getting too long |
| `/mcp` | `prepTldrOverviewDemo` | A | High | After the prep row in the tool table |
| `/mcp/ides` | `ideAddCsvExportDemo` | A | High | Replaces current iframe embed |
| `/mcp/terminal` | `prepSearchDemos[0]` | A | Medium | Native React via `<AnimatedCLI>` |
| `/concepts/code-graph` | `impactExtractServiceDemo` | A | High | After "How Agents Use It" section |
| `/concepts/context` | `prepTldrOverviewDemo` (or `observeCachingRecallDemo`) | A | Medium | One canonical at end of page |
| `/concepts/indexing` | NONE | — | Medium | Page is pipeline narrative; no clean animation fit |
| `/concepts/graph-enrichment` | (existing pipeline panel embed) | B | High | Already iframe-embedded; keep |
| `/guides/smart-search` | 2–3 of `prepSearchDemos[*]` side-by-side | A | High | Different scripts show different intents |
| `/guides/codebase-audit` | `auditPrSanityCheckDemo` | A | High | Already has `<StoryEmbed>` for AuditPanel; pair with CLI animation |
| `/guides/audit-enrichment` | `auditSecurityScanDemo` (or GAP — see follow-up #3) | A | Medium | Existing scripts don't perfectly fit; flag gap |
| `/guides/path-weights` | `searchBuildWorkerDemo` | A | Low | Animation fit is okay but page is reference-heavy |
| `/guides/embeddings` | NONE | — | High | Page is selection guide; no animation fit |
| `/guides/compression` | NONE | — | High | Page is technical reference |
| `/guides/concurrency-discovery` | NONE | — | High | Operational/troubleshooting; animation would distract |
| `/guides/knowledge-scope` | (existing FolderTreePanel embed) | B | High | Iframe-embedded panel is the fit |
| `/guides/models` (AI Gateway) | NONE | — | High | Page is configuration reference; AIModelsSettings panel embed already there |
| `/guides/byok-batching` | NONE | — | Medium | Possible cost-banner panel embed via iframe once that story exists |
| `/guides/dynamic-model-loading` | NONE | — | High | Informational only |
| `/guides/team-sync` | NONE | — | Medium | External-repo dependency; defer with that work |
| `/guides/enterprise-deploy` | NONE | — | High | Out-of-scope until enterprise ships |
| `/cli` | One `prepDemos[*]` per landing slot | A | Medium | Or NONE — page is a reference, animations may distract |
| `/dashboard` | (existing embeds) | B | High | Multiple iframe embeds already; no new animation needs |
| `/troubleshooting` | NONE | — | High | Text-heavy; animations would distract |

**Confidence legend:** High = strong fit, defaults likely correct.
Medium = fit is reasonable, may need taste-level adjustment.
Low = unclear; let the audit decide whether to include at all.

This worksheet is **a starting point**. Override based on per-page audit
findings.

## What success looks like

When this phase ships, a user landing on the docs site should:

1. **See animations on pages where they amplify the prose** — and not on
   pages that are pure reference.
2. **Recognize the same animation style across pages** — same chrome
   (or same lack of chrome), same theme, same pacing.
3. **Not wait for iframes to load on pages where the animation is the
   lead visual** — those should be native React, first paint near-instant.
4. **Not encounter visual overload** — most pages have 0 or 1 animation;
   only `/guides/smart-search` is the multi-animation outlier and it's
   justified by the side-by-side intent comparison.

If the audit and implementation hit those four marks, this phase has done
its job.
