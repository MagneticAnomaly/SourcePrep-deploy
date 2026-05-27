# Phase 137 — Per-Page Audit

> **Status:** Populated 2026-05-14 against pre-Phase-138 URLs.
> **URL re-keying:** 8 pages will move to `/{new}/...` when Phase 138 lands
> (4 concepts pages + 4 explainer guides). Re-keying is mechanical — anchor
> IDs and placement decisions carry over. Pages affected are tagged
> **★ Phase 138 move** below.
> **Path defaults:** Native React (`<AnimatedCLI>` / `<AnimatedIDE>`) unless
> the page is already iframe-heavy. See `05_animation_showcase_strategy.md`
> for the rubric.

## How to use this doc

For each docs page in scope, fill in the template below. Use the inventory
in `02_asset_inventory.md` to pick candidate stories/animations. Verdicts:

- **EMBED** — `<StoryEmbed>` an existing story at a specific spot on the page
- **ANIMATE** — `<AnimatedCLI>` or `<AnimatedIDE>` with a named script
- **BOTH** — page wants one of each
- **NONE** — page should stay text-only (text-heavy reference, or no fitting asset)
- **GAP** — page would benefit but no fitting asset exists yet; file follow-up

## Per-page template

```markdown
### `/path/to/page`

**Current state:** [does the page have embeds today? which ones? where?]

**Page intent:** [one-line description of what this page is for]

**Recommendation:** EMBED | ANIMATE | BOTH | NONE | GAP

**Placement:**
1. After section "Section X" (#anchor-id) — <StoryEmbed storyId="..." height={...} caption="..." />
   - Why: [reasoning — what this story shows that the surrounding text describes]
2. Inline within section "Section Y" — <AnimatedCLI script={namedDemo} />
   - Why: [reasoning]

**Candidate story IDs / scripts:** [exact IDs from inventory; multiple if A/B]

**Gap flag:** [if a desired story doesn't exist yet, describe what it would be]

**Per-instance mods needed:** ⏸ deferred to implementation pass
  (Note ideas here, don't apply: e.g., "height={500} for this one; caption should
  mention 'live' explicitly")
```

---

## Pages in scope

The pages to audit. Each gets one section using the template above. Sorted
roughly by user-impact (onboarding first, optional guides last).

### Home / overview

- [x] `/` (home page)

### Onboarding (Tier A in Phase 132)

- [x] `/getting-started` (parent)
- [x] `/getting-started/installation`
- [x] `/getting-started/quick-start`

### MCP integration (Tier B in Phase 132)

- [x] `/mcp` (overview)
- [x] `/mcp/ides`
- [x] `/mcp/terminal`
- [x] `/mcp/paperclip`

### Concept pages (Tier C in Phase 132)

- [x] `/how-it-works/indexing` ★ Phase 138 move
- [x] `/how-it-works/code-graph` ★ Phase 138 move
- [x] `/how-it-works/graph-enrichment` ★ Phase 138 move
- [x] `/how-it-works/context` ★ Phase 138 move

### CLI reference (Tier E in Phase 132)

- [x] `/cli` (commands reference)

### Dashboard (Tier F in Phase 132)

- [x] `/dashboard`

### Guides (Tier D in Phase 132)

- [x] `/how-it-works/embeddings` ★ Phase 138 move
- [x] `/guides/audit-enrichment`
- [x] `/guides/codebase-audit`
- [x] `/how-it-works/smart-search` ★ Phase 138 move
- [x] `/how-it-works/compression` ★ Phase 138 move
- [x] `/guides/concurrency-discovery`
- [x] `/guides/path-weights`
- [x] `/guides/knowledge-scope`
- [x] `/guides/byok-batching`
- ~~`/guides/model-advisor`~~ — **DROPPED** 2026-05-14: deprecated and hidden from sidebar+sitemap per `project_llm_strategy.md`. Replaced by the simple recommendation list on `/guides/models` (AI Gateway).
- [x] `/guides/models` *(renamed to "AI Gateway"; was "Model Configuration")*
- [x] `/guides/team-sync` (may be deferred — README flags external repo dependency)
- [x] `/how-it-works/dynamic-model-loading` ★ Phase 138 move

### Other

- [x] `/search` (the docs search page)
- [x] `/troubleshooting`

---

## Audit notes

### `/` (home)

**Current state:** No embeds. 8-card grid of feature callouts only. The page is short and acts as a routing hub for the rest of the docs.

**Page intent:** Documentation hub landing — route the reader to the section they want.

**Recommendation:** NONE.

**Placement:** —

**Candidate story IDs / scripts:** —

**Gap flag:** —

**Per-instance mods needed:** —

**Why NONE:** The hero/tagline is off-limits for autonomous edits per memory `feedback_do_not_touch_hero`, and the body is a card grid that already does the routing job without ornament. An embed here would shift visual weight away from the cards and the marketing-site has its own front door for animation-led pitch.

---

### `/getting-started`

**Current state:** One existing `<StoryEmbed>` under step 2 ("Launch the App"):
`storyId="website-demos-animatedcli--project-overview"` (iframe path).

**Page intent:** End-to-end onboarding — 6 sequential steps from install → audit.

**Recommendation:** ANIMATE (refresh existing — swap iframe for native React; optionally add one more under step 6).

**Placement:**
1. Replace the existing iframe under `#start-daemon` (step 2 "Launch the App") with native React:
   - `<AnimatedCLI script={prepTldrOverviewDemo} className="my-6" />`
   - Why: the iframe boots a Storybook bundle before the animation starts; this is the first animation the visitor sees and should paint instantly. Same content, faster first paint, drops one network round-trip on the highest-traffic page.
2. After step 6 ("Run a quick audit", `#audit`) — `<AnimatedCLI script={auditPrSanityCheckDemo} />`
   - Why: the prose under this step describes the audit-handoff workflow; the animation closes the loop. Strong fit per 05's recommendation; risk is page length.

**Candidate story IDs / scripts:**
- Step 2 (refresh): `prepTldrOverviewDemo` (preferred); alternates `prepRateLimitingDemo`, `prepBuildWebhookDemo`.
- Step 6 (new): `auditPrSanityCheckDemo` (preferred); alternates `auditSecurityScanDemo`, `auditTightenTypesDemo`.

**Gap flag:** "Fresh project, first call to `prep`" script would fit even better than `prepTldrOverviewDemo` here, but the existing one is serviceable. Follow-up #1 in 05.

**Per-instance mods needed:** ⏸ deferred. Notes: caption can be dropped on the native React version (the surrounding prose already provides context). Consider `loop=false` so a first-time visitor doesn't see the animation restart mid-read.

**Decision call:** Adding the step 6 embed risks visual overload on an already long page. Implementation pass should decide based on what step 2 looks like after the swap; if the page reads well, add step 6. If it feels long, defer step 6 to a follow-up.

---

### `/getting-started/installation`

**Current state:** No embeds. Two-column platform grid + ordered lists, licensing info, upgrade info.

**Page intent:** Platform-specific install steps (macOS/Windows).

**Recommendation:** NONE.

**Placement:** —

**Candidate story IDs / scripts:** —

**Gap flag:** A screenshot of the installer / Gatekeeper unblock flow could help, but that's outside Phase 137 scope (this phase covers Storybook + animation embeds, not static screenshots).

**Per-instance mods needed:** —

**Why NONE:** Install steps are screenshot territory, not animation/panel territory. No story or script in the inventory shows a download or installer flow.

---

### `/getting-started/quick-start`

**Current state:** No embeds. Five numbered step cards.

**Page intent:** 5-minute rapid tutorial covering launch → index → MCP → scope → audit.

**Recommendation:** ANIMATE (lead visual under step 1 only).

**Placement:**
1. After step 1 in the `#five-minute-guide` section ("Launch the desktop app" card) — `<AnimatedCLI script={prepTldrOverviewDemo} className="my-6" />`
   - Why: the step cards are clear but visually identical; one animation early anchors "this is what the trust loop looks like" before the reader commits to the 5 minutes. Mirrors the same script used on `/getting-started` for consistency.

**Candidate story IDs / scripts:** `prepTldrOverviewDemo`. Alternates: `prepBuildWebhookDemo`.

**Gap flag:** —

**Per-instance mods needed:** ⏸ deferred. Consider matching the height/style to whatever step 2 of `/getting-started` lands on.

**Why not more:** A second animation (e.g., audit demo under step 5) would compete with `/getting-started` for the same content — the quick-start is the shorter mirror of `/getting-started`, not a parallel deep dive.

---

### `/mcp`

**Current state:** Two existing iframe embeds under `#live-preview`:
- `dashboard-search-searchpanel--default` (h280, "Semantic Search Panel")
- `dashboard-index-indexstatuscard--loaded` (h220, "Index Status Card")

**Page intent:** MCP overview — what MCP is, list of tools, dashboard preview.

**Recommendation:** BOTH (keep existing iframes + add one native CLI animation after the tools table).

**Placement:**
1. Keep the two existing `<StoryEmbed>` calls under `#live-preview`. They are the right content for that section.
2. After the tools-reference table under `#tools-reference` — `<AnimatedCLI script={prepTldrOverviewDemo} className="my-6" />`
   - Why: the tools table is a tight reference, but it explains what each tool does without showing what calling one feels like. A single animation right after the table makes the abstraction concrete. 05 recommends this placement explicitly.

**Candidate story IDs / scripts:**
- Existing (keep): `dashboard-search-searchpanel--default`, `dashboard-index-indexstatuscard--loaded`.
- New: `prepTldrOverviewDemo`. Alternates: any `prepDemos[*]`.

**Gap flag:** —

**Per-instance mods needed:** ⏸ deferred. Caption could lean on "this is what an MCP call returns" to bridge the table → animation visually.

**Path choice (A vs B):** Page is already iframe-heavy under `#live-preview`, but the CLI animation sits in a different section. Path A is correct — paint speed matters more than visual consistency across sections.

---

### `/mcp/ides`

**Current state:** One existing iframe embed under `#setup`:
`storyId="website-demos-animatedide--default"` (height 500, "SourcePrep in an Agentic IDE").

**Page intent:** IDE integration guide — repeating per-IDE config snippets.

**Recommendation:** ANIMATE (swap iframe → native React).

**Placement:**
1. Replace the existing iframe under `#setup` with native React:
   - `<AnimatedIDE script={ideAddCsvExportDemo} className="my-6" />`
   - Why: the IDE animation is the lead visual on this page and is large (h500). Paint speed matters; the iframe path adds a Storybook bundle boot before the animation starts. Per 05's rubric: lead visual + multi-iframe-loading risk → Path A.

**Candidate story IDs / scripts:**
- New: `ideAddCsvExportDemo` (preferred — most expository). Alternates: `ideLoadingSkeletonDemo` (UI-leaning), `ideDoubleSubmitFixDemo` (bug-fix).

**Gap flag:** —

**Per-instance mods needed:** ⏸ deferred. Height can drop slightly without the Storybook chrome; consider 450 instead of 500.

---

### `/mcp/terminal`

**Current state:** No embeds. Per-CLI config snippets only.

**Page intent:** Terminal/CLI agent integration — repeating per-CLI MCP config snippets.

**Recommendation:** ANIMATE (single lead visual under `#setup`).

**Placement:**
1. After the `#setup` paragraph, before the first CLI's config block — `<AnimatedCLI script={prepSearchDemo} className="my-6" />`
   - Why: page is otherwise a series of code-block configs; one animation establishes what the terminal flow actually looks like when an agent calls `prep_search`. Symmetric with `/mcp/ides` having an IDE animation.

**Candidate story IDs / scripts:** `prepSearchDemo` (= `searchRetryReuseDemo`). Alternates: any `prepSearchDemos[*]`, or `prepTldrOverviewDemo` if a terminal-agent context call feels more representative.

**Gap flag:** —

**Per-instance mods needed:** ⏸ deferred. May want a "claude" theme variant if one exists; the page is terminal-flavored.

**Decision call:** Medium confidence — page is reference-heavy and a CLI animation may compete with the config code blocks below it. Implementation pass should confirm by previewing.

---

### `/mcp/paperclip`

**Current state:** One existing iframe embed under `#ui` ("Dashboard Extensions"):
`storyId="dashboard-agents-agentopspanel--active"` (height 400, "Agent Operations Panel").

**Page intent:** Paperclip plugin guide — installation, tools, UI extensions, agent workflow.

**Recommendation:** EMBED (keep existing).

**Placement:**
1. Keep the existing `<StoryEmbed>` under `#ui`. It is the right content for that section.

**Candidate story IDs / scripts:** `dashboard-agents-agentopspanel--active` (current).

**Gap flag:** —

**Per-instance mods needed:** —

**Why no animation added:** The page is workflow-heavy and the existing embed covers the "what does this feel like in Paperclip" question. A CLI/IDE animation here would compete with the ASCII architecture diagram and the agent-workflow steps. Stays as-is.

---

### `/how-it-works/indexing` ★ Phase 138 move

**Current state:** No embeds. Four-step pipeline icon-card grid, callouts, controls description.

**Page intent:** Vector indexing explanation — how files are discovered, parsed, embedded, stored.

**Recommendation:** NONE (current); **GAP** flag for follow-up.

**Placement:** —

**Candidate story IDs / scripts:** —

**Gap flag:** The page describes the indexing pipeline but no `IndexStatusCard` *running* visual is in scope here (the loaded story exists but already lives on `/dashboard`). A future "indexing in progress — discovery → parse → embed" animation or storied panel would fit `#pipeline`. Low priority.

**Per-instance mods needed:** —

**Why NONE now:** 05 worksheet flagged this NONE; the page is a pipeline narrative and the four-icon grid already does the visual work. No clean animation fit.

---

### `/how-it-works/code-graph` ★ Phase 138 move

**Current state:** One existing iframe embed under `#visualization`:
`storyId="dashboard-trace-graph--default"` (height 450, "Interactive Code Graph").

**Page intent:** Structural code graph explanation — precision layer for definitions, references, imports.

**Recommendation:** BOTH (keep existing + add CLI animation under `#usage`).

**Placement:**
1. Keep the existing `<StoryEmbed>` under `#visualization`.
2. After the numbered list under `#usage` ("1. Find via vector ... 4. Expand context") — `<AnimatedCLI script={impactExtractServiceDemo} className="my-6" />`
   - Why: the page narrative is already strong on what the graph *is*; the usage section ends with "agents use this to expand context" but doesn't show it. An `impact` demo closes that loop — agent asks about a function, graph expands, dependents surface. 05 recommends this placement.

**Candidate story IDs / scripts:**
- Existing (keep): `dashboard-trace-graph--default`.
- New: `impactExtractServiceDemo` (preferred — most impactful visual). Alternates: `impactDeleteUnusedDemo`, `impactAsyncMigrationDemo`.

**Gap flag:** —

**Per-instance mods needed:** ⏸ deferred. Two embeds on the same page need consistent rhythm — match `my-6` margins between them.

---

### `/how-it-works/graph-enrichment` ★ Phase 138 move

**Current state:** No embeds. 15 stage cards across 3 phases (Sync/Enrich/Finalize), understanding score grid, decay table.

**Page intent:** 15-stage enrichment pipeline narrative — Sync → Enrich → Finalize, plus understanding scores and decay.

**Recommendation:** EMBED.

**Placement:**
1. After the `#journey` overview, before the Sync stage cards begin — `<StoryEmbed storyId="dashboard-pipeline-graphenrichmentpipeline--full-pipeline-running" height={500} caption="The 15-stage pipeline in action." />`
   - Why: the page is the narrative explanation of the pipeline; the `GraphEnrichmentPipeline` story shows the same pipeline running live. The story exists, is high-fidelity, and already proves itself on `/dashboard`. This is the canonical "live = static narrative + dynamic widget" pairing.

**Candidate story IDs / scripts:** `dashboard-pipeline-graphenrichmentpipeline--full-pipeline-running` (preferred — same story used on `/dashboard`). Alternates: `dashboard-pipeline-graphenrichmentpipeline--*` other variants if one suits the concept page better.

**Gap flag:** Worksheet in 05 said this page "already has" the pipeline embed — **not true**; it does not exist on this page today. Treating this as the highest-value *new* embed in the audit. (The story is currently used on `/dashboard` only.)

**Per-instance mods needed:** ⏸ deferred. Height likely needs to be tall enough to show the stage chips; verify with a dev-server preview.

**Path choice:** Path B (iframe) — page has no other animations and the pipeline component is heavy; iframe sandboxing prevents docs-bundle bloat.

---

### `/how-it-works/context` ★ Phase 138 move

**Current state:** No embeds. Five-step assembly pipeline with numbered cards + a two-column panel-control grid.

**Page intent:** Context assembly pipeline — retrieval, scoring, budgeting, compression, formatting.

**Recommendation:** ANIMATE (one canonical, end of page).

**Placement:**
1. After `#formatting` (the last numbered step), before the `#ui-controls` section — `<AnimatedCLI script={prepTldrOverviewDemo} className="my-8" />`
   - Why: the page narrative walks through "how context gets assembled" step by step; ending with a `prep` call shows what comes out the other end. Acts as a closing visual.

**Candidate story IDs / scripts:** `prepTldrOverviewDemo` (preferred — clean overview output). Alternates: `observeCachingRecallDemo` if persistence-leaning framing wins.

**Gap flag:** —

**Per-instance mods needed:** ⏸ deferred. `my-8` (slightly more margin than other pages) so the animation reads as a "result" rather than another step.

---

### `/cli`

**Current state:** One existing iframe embed under `#common-workflows`:
`storyId="website-demos-animatedcli--semantic-search"` (height 350).

**Page intent:** CLI hub — two-card grid (Commands / Configuration) + workflows overview.

**Recommendation:** ANIMATE (refresh existing — swap iframe for native React).

**Placement:**
1. Replace the existing iframe under `#common-workflows` with native React:
   - `<AnimatedCLI script={prepSearchDemo} className="my-6" />`
   - Why: same content (semantic-search demo), faster first paint, drops the Storybook bundle boot.

**Candidate story IDs / scripts:** `prepSearchDemo` (= `searchRetryReuseDemo`, the existing iframe variant). Alternates: `prepTldrOverviewDemo`, `prepImpactDemo`.

**Gap flag:** —

**Per-instance mods needed:** ⏸ deferred. May want height 320 instead of 350 once Storybook chrome is gone.

**Why not more:** The page itself is a hub; the embed is correct for it but no additional animations belong here. Sub-pages (`/cli/commands`, `/cli/config`) are reference-only and don't need embeds.

---

### `/dashboard`

**Current state:** Six existing iframe embeds across the page:
- `dashboard-layouts-fulldashboard--full-dashboard` (h600) under `#overview`
- `patterns-panelpicker--default` (h350) under `#adding-panels`
- `dashboard-index-indexstatuscard--loaded` (h220) under `#index-status`
- `dashboard-trace-coveragepanel--default` (h350) under `#code-graph-coverage`
- `dashboard-pipeline-graphenrichmentpipeline--full-pipeline-running` (h450) under `#pipeline`
- `dashboard-search-searchpanel--full-search-demo` (h350) under `#search-context`

**Page intent:** Dashboard guide — modular panel-based UI for monitoring, searching, context assembly.

**Recommendation:** EMBED (keep all existing).

**Placement:**
1. Keep all six existing `<StoryEmbed>` calls in place. This page is the canonical demonstration of every dashboard panel and is the model the rest of the audit references.

**Candidate story IDs / scripts:** All six current IDs (preserve).

**Gap flag:** —

**Per-instance mods needed:** ⏸ deferred. Visual regression sweep should verify all six load correctly post-netlify-fix.

**Why no animations added:** Page is already iframe-heavy and the embeds carry the visual load. A CLI/IDE animation would compete and stretch the page further.

---

### `/how-it-works/embeddings` ★ Phase 138 move

**Current state:** No embeds. Three tier boxes + comparison table + configuration subsections + API reference.

**Page intent:** Three embedding model tiers — recommendation + setup reference.

**Recommendation:** NONE.

**Placement:** —

**Candidate story IDs / scripts:** —

**Gap flag:** —

**Per-instance mods needed:** —

**Why NONE:** Page is a selection guide with strong table content; no story or script in the inventory shows model selection or download. Confirmed in 05 worksheet.

---

### `/guides/audit-enrichment`

**Current state:** No embeds. Bullet list of enrichment fields, two JSON code blocks (input + enriched output), SARIF workflow.

**Page intent:** Pipe lint findings through `prep_audit` to enrich with structural context.

**Recommendation:** GAP (placement willing; no fitting script).

**Placement:**
- *If proceeding with the closest fit:*
1. After the SARIF code block under `#sarif`, before `#why` — `<AnimatedCLI script={auditSecurityScanDemo} className="my-6" />`
   - Why: the audit-enrichment narrative is "lint finding goes in, structural context comes out". `auditSecurityScanDemo` shows the closest analog (triggering an audit) but doesn't show enrichment-of-existing-findings, which is the page's real subject.

**Candidate story IDs / scripts:** `auditSecurityScanDemo` if we want something now; otherwise gap.

**Gap flag:** **GAP — no animation shows `prep_audit(findings=[...])` enrichment.** 05 follow-up #3. The existing audit scripts show *triggering* an audit; this page is specifically about enriching external findings. A new script piping a ruff JSON payload through `prep_audit` and showing the enriched output would be the right fit. Priority: medium — workflow is mentioned in concepts (CLAUDE.md) and worth visualizing.

**Per-instance mods needed:** ⏸ deferred. Implementation pass should decide between (a) ship without animation and file the gap, or (b) ship with `auditSecurityScanDemo` as a stand-in. Recommendation: ship without animation and file the gap as a follow-up; the page's two JSON code blocks already carry the explanatory weight.

---

### `/guides/codebase-audit`

**Current state:** Two existing iframe embeds:
- `dashboard-audit-auditpanel--with-findings` (h600) under `#overview`
- `dashboard-audit-opportunitiespanel--with-opportunities` (h600) under `#pipeline-connection`

**Page intent:** Autonomous codebase audit — 11 analyzers, 5 LLM reports, AI handoff.

**Recommendation:** BOTH (keep existing + add CLI animation).

**Placement:**
1. Keep both existing iframes.
2. After the `#quick-start` section's `cli` subsection (h3) — `<AnimatedCLI script={auditPrSanityCheckDemo} className="my-6" />`
   - Why: the `cli` subsection shows raw command syntax; the animation shows the workflow that command unlocks (audit → findings → next step). 05 recommends this placement.

**Candidate story IDs / scripts:**
- Existing (keep): `dashboard-audit-auditpanel--with-findings`, `dashboard-audit-opportunitiespanel--with-opportunities`.
- New: `auditPrSanityCheckDemo` (preferred — most relatable). Alternates: `auditSecurityScanDemo`, `auditTightenTypesDemo`.

**Gap flag:** —

**Per-instance mods needed:** ⏸ deferred. Three embeds on one page is a lot; height of the CLI animation should be modest (320–360) so the page rhythm doesn't break.

**Path choice (A vs B for the new animation):** Path A — page already has heavy iframes (h600 × 2), so a Path A CLI animation in between gives the page a faster mid-page paint and breaks the iframe-loading-compounding risk 05 calls out.

---

### `/how-it-works/smart-search` ★ Phase 138 move

**Current state:** No embeds. Seven intent definition blocks, override paragraph, evaluation-order numbered list.

**Page intent:** Query intent classification — 7 intents route to different backends.

**Recommendation:** ANIMATE (multi).

**Placement:**
1. Within `#intents`, paired with the LOCATE definition block — `<AnimatedCLI script={searchRetryReuseDemo} className="my-6" />`
   - Why: shows a "find me X" query routing to symbol lookup.
2. Within `#intents`, paired with the RATIONALE definition block — `<AnimatedCLI script={conceptsTransactionRuleDemo} className="my-6" />`
   - Why: shows a "why" query routing to concepts. Demonstrates the intent → backend routing the page describes.
3. After `#evaluation-order`, optionally — `<AnimatedCLI script={searchMaxConnectionsDemo} className="my-6" />`
   - Why: third example, config-tuning intent. Reinforces variety. Optional; trim if page gets too long.

**Candidate story IDs / scripts:** `searchRetryReuseDemo`, `conceptsTransactionRuleDemo`, `searchMaxConnectionsDemo`. Alternates: any `prepSearchDemos[*]`, `prepConceptsDemos[*]`.

**Gap flag:** **GAP — no "intent routing comparison" animation.** 05 follow-up #2. A side-by-side animation showing "where is X" → LOCATE vs "why does X use Y" → RATIONALE would replace the two animations above with one tighter visual. Priority: medium.

**Per-instance mods needed:** ⏸ deferred. Implementation pass: confirm three CLI animations on this page is not visual overload; trim to two (LOCATE + RATIONALE) if so.

**Decision call:** This is the multi-animation outlier 05 explicitly flagged. Justification: the page's whole point is "different inputs route to different backends" — showing two routings side-by-side is what makes the abstraction concrete. If gap follow-up #2 ships first, replace all three with the new comparison script.

---

### `/how-it-works/compression` ★ Phase 138 move

**Current state:** No embeds. LOD level table, tier table, ASCII flow diagram.

**Page intent:** LOD structural compression — variable fidelity based on relevance and tier.

**Recommendation:** NONE.

**Placement:** —

**Candidate story IDs / scripts:** —

**Gap flag:** A "side-by-side LOD before/after code" visual could fit, but it's not in scope for this phase (would require a custom storied component, not an animation script).

**Per-instance mods needed:** —

**Why NONE:** Page is a technical reference with strong table content. No fitting story or script.

---

### `/guides/concurrency-discovery`

**Current state:** No embeds. Status-line examples, reset options, FAQ-style content.

**Page intent:** Concurrency ceiling discovery for cloud LLM endpoints — adaptive probing with 24h lock.

**Recommendation:** NONE.

**Placement:** —

**Candidate story IDs / scripts:** —

**Gap flag:** —

**Per-instance mods needed:** —

**Why NONE:** Operational/troubleshooting content — animation would distract from the FAQ rhythm. Confirmed in 05 worksheet.

---

### `/guides/path-weights`

**Current state:** No embeds. Three numbered how-it-works boxes, dashboard image placeholder, API reference cards. Note: page has a "Screenshot: Path Weight Badges" placeholder that needs a real visual.

**Page intent:** Path weights for search ranking — boost/suppress folders at query time without rebuild.

**Recommendation:** EMBED (replace screenshot placeholder) + optional ANIMATE.

**Placement:**
1. Under `#using-the-dashboard`, replace the screenshot placeholder — `<StoryEmbed storyId="<scope-or-folder-tree-panel>" height={400} caption="Path weight badges in the Scope panel." />`
   - Why: the page has a documented "Screenshot:" placeholder that's been waiting for a real asset. The Scope panel (used in `/guides/knowledge-scope`) is the closest visual home for path weight badges.
2. (Optional) After `#how-it-works`, before dashboard section — `<AnimatedCLI script={searchBuildWorkerDemo} className="my-6" />`
   - Why: 05 suggests this placement to show how a weighted path changes ranking. Low confidence — the script doesn't specifically demonstrate path-weight tuning; it shows operational search.

**Candidate story IDs / scripts:**
- Embed: closest match is `dashboard-project-foldertreepanel--scope-panel-named-populated`; **verify it shows weight badges** during implementation.
- Animation (optional): `searchBuildWorkerDemo`. Alternates: any `prepSearchDemos[*]`.

**Gap flag:** **GAP — no dedicated "Path Weights" story.** If the FolderTreePanel scope-panel variant doesn't visibly show weight badges, file a follow-up to add a `PathWeights` story variant. Verify during implementation. Priority: medium.

**Per-instance mods needed:** ⏸ deferred. The placeholder text on the page should be removed entirely once the embed lands.

**Decision call:** Confidence on the animation is **Low** (per 05). Implementation pass: ship the embed; skip the animation unless preview shows it adds value.

---

### `/guides/knowledge-scope`

**Current state:** One existing iframe embed under `#using-the-dashboard`:
`storyId="dashboard-project-foldertreepanel--scope-panel-named-populated"` (h500).

**Page intent:** Knowledge Scope selector — which files are in the index (binary in/out control).

**Recommendation:** EMBED (keep existing).

**Placement:**
1. Keep the existing `<StoryEmbed>` under `#using-the-dashboard`.

**Candidate story IDs / scripts:** `dashboard-project-foldertreepanel--scope-panel-named-populated` (current).

**Gap flag:** —

**Per-instance mods needed:** —

**Why no animation:** Page is panel-centric and the embed is the right content. CLI/IDE animation would compete.

---

### `/guides/byok-batching`

**Current state:** One existing iframe embed under `#how-batching-works`:
`storyId="dashboard-llm-endpointmanager--interactive"` (h400, "Endpoint Manager").

**Page intent:** Cloud batch processing for BYOK LLMs — reduces API calls and cost.

**Recommendation:** EMBED (keep existing); flag for future cost-banner panel.

**Placement:**
1. Keep the existing `<StoryEmbed>` under `#how-batching-works`.

**Candidate story IDs / scripts:** `dashboard-llm-endpointmanager--interactive` (current).

**Gap flag:** **GAP — no cost-banner / token-counter panel story.** 02_asset_inventory.md follow-up #3. The page mentions cost-tier UI but no story exists. Future addition; priority low.

**Per-instance mods needed:** —

**Why no animation:** Page is configuration-focused; embed carries the right load. Confirmed in 05.

---

### `/guides/models` (AI Gateway)

**Current state:** One existing iframe embed under `#model-slots`:
`storyId="dashboard-llm-aimodelssettings--default"` (h500, "AI Models Settings Panel").

**Page intent:** AI model slot configuration (Embedding, Fast, Code, Thinking, Swarm Coordinator); recommended stacks.

**Recommendation:** EMBED (keep existing).

**Placement:**
1. Keep the existing `<StoryEmbed>` under `#model-slots`.

**Candidate story IDs / scripts:** `dashboard-llm-aimodelssettings--default` (current).

**Gap flag:** —

**Per-instance mods needed:** —

**Why no animation:** Page is configuration reference; AIModelsSettings panel embed already carries the visual load. Confirmed in 05.

---

### `/guides/team-sync`

**Current state:** One existing iframe embed under `#how-it-works`:
`storyId="dashboard-team-syncstatuscard--up-to-date"` (h200, "Team Sync Status").

**Page intent:** Team sync / BYOC — headless CI/CD indexing so teams share pre-built index.

**Recommendation:** EMBED (keep existing); defer further work to external-repo coordination.

**Placement:**
1. Keep the existing `<StoryEmbed>` under `#how-it-works`.

**Candidate story IDs / scripts:** `dashboard-team-syncstatuscard--up-to-date` (current).

**Gap flag:** —

**Per-instance mods needed:** —

**Why no additional work:** Page is tied to external-repo BYOC tooling; README flags the dependency. Hold further embed work until that lands.

---

### `/how-it-works/dynamic-model-loading` ★ Phase 138 move

**Current state:** No embeds. Provider table, MLX vs GGUF comparison, recommended-setup subsections, pipeline-safety explanation.

**Page intent:** Dynamic model loading for local LLMs — VRAM management, MLX vs GGUF, recommended setups.

**Recommendation:** NONE.

**Placement:** —

**Candidate story IDs / scripts:** —

**Gap flag:** —

**Per-instance mods needed:** —

**Why NONE:** Informational/reference; no fitting story or script. Confirmed in 05. Also note: local LLMs are the secondary path per memory `project_llm_strategy.md`; don't over-invest visual budget here.

---

### `/search`

**Current state:** No embeds. Client-side search results page.

**Page intent:** Docs search — interactive search box + results.

**Recommendation:** NONE.

**Placement:** —

**Candidate story IDs / scripts:** —

**Gap flag:** —

**Per-instance mods needed:** —

**Why NONE:** Page is itself an interactive UI; embedding another interactive element would be redundant.

---

### `/troubleshooting`

**Current state:** No embeds. Seven h2 sections of bordered problem/solution boxes.

**Page intent:** Common issues and fixes.

**Recommendation:** NONE.

**Placement:** —

**Candidate story IDs / scripts:** —

**Gap flag:** Bug-reporting flow could host a `BugReportModal` story embed near a "How to file a bug" section, but the section doesn't currently exist on this page; would require copy work in addition to embedding. Defer.

**Per-instance mods needed:** —

**Why NONE:** Text-heavy reference; embeds would interrupt the scan-and-find rhythm.

---

## Gaps surfaced during audit

Mirror these to `04_placement_matrix.md` gap list.

1. **No "fresh project — first call to `prep`" script** (existing follow-up #1 from 05). Wanted by `/getting-started`. Priority: low.
2. **No "intent routing comparison" animation** (existing follow-up #2). Wanted by `/how-it-works/smart-search`. Priority: medium.
3. **No "`prep_audit(findings=...)` enrichment" animation** (existing follow-up #3). Wanted by `/guides/audit-enrichment`. Priority: medium.
4. **No "Path Weights" / "weight badges" Storybook variant** (new). Wanted by `/guides/path-weights`. The current `FolderTreePanel` scope-panel variant may or may not show weight badges; verify during implementation. Priority: medium.
5. **No "Concepts panel" Storybook story** (existing follow-up #4). Not consumed by any in-scope page today; flagged for future pages. Priority: low.
6. **No cost-banner / token-counter panel story** (existing follow-up). Wanted by `/guides/byok-batching` (future). Priority: low.
7. **No `BugReportModal` placement context on `/troubleshooting`** (new). Would require copy authorship + section creation, not just an embed. Priority: low.

## Decisions log

- **Defaulted to Path A (native React)** for every new animation, per 05 rubric. Existing iframes that are panel/dashboard embeds stay as Path B. Existing iframes that are CLI/IDE animations (`/getting-started`, `/mcp/ides`, `/cli`) get **swapped to Path A** because they are animations, not panels, and paint speed dominates.
- **05 worksheet correction:** The worksheet claimed `/how-it-works/graph-enrichment` "already has" the pipeline embed via iframe. **It does not.** The `GraphEnrichmentPipeline` story exists but is consumed by `/dashboard` only. Treating the concepts-page placement as the highest-value *new* embed in the audit.
- **Multi-animation on `/how-it-works/smart-search`** is deliberate per 05. The page's whole thesis is "different inputs route to different backends"; showing the routings side-by-side is what makes the abstraction concrete. If gap #2 lands first, collapse to a single comparison animation.
- **`/getting-started/quick-start`** gets a single animation, not multiple, to avoid duplicating the longer `/getting-started` page's content. The quick-start is a 5-minute mirror.
- **`/cli` sub-pages (`/cli/commands`, `/cli/config`)** are out of scope: they are reference pages with no animation fit. The hub page `/cli` carries the embed.
- **`/guides/audit-enrichment`** ships without animation pending gap #3. The page's two JSON code blocks already carry the explanatory weight.
- **`/troubleshooting` `BugReportModal` placement** is deferred because it needs copy work (new section), not just an embed; out of Phase 137 scope.
- **★ Phase 138 affected pages** keep their audit verdict as written; URLs re-key mechanically when 138 lands. Anchor IDs are not expected to change (page bodies migrate to `ConceptPageShell` for the 4 ex-guides, which preserves the anchor scheme).
