# Phase 138 — Docs "Concepts" Rename + Explainer Migration

> **STATUS: SHIPPED 2026-05-26.** Section name "How It Works" confirmed by
> Eric. Commits: `d66eed89` (rename + ConceptPageShell migration),
> `2bb3a281` (mcp/ides + mcp/terminal client-component fix to restore
> green `next build`). Cross-repo URL re-key for `packages/ui` panels +
> stories + marketing `next.config.js` redirect landed alongside.
>
> **Scaffolded 2026-05-14 during Phase 132.** Deferred until Phase 132 completes
> to keep momentum on the behavioral-fidelity audit. This is the structural
> follow-up that came out of the Tier D "what is a Guide anyway?" question.

## Problem

Two distinct issues bundled into one phase because they ship together:

### 1. Naming collision — "Concepts"

`/concepts/` is the docs top-level section that explains how SourcePrep
works (indexing, code-graph, graph-enrichment, context). **But "Concepts"
is also a live product feature** — the `prep_concepts` MCP tool, the
Concepts panel in the dashboard, and the concept-promotion pipeline that
captures business rationale + design decisions.

The collision is confusing in user-facing copy ("read the Concepts docs"
vs "concepts the app records") and in the codebase ("concept pages" vs
"concept store").

### 2. Explainer guides belong with the conceptual section

Four `/guides/*` pages are not really how-tos — they're explainers about
how automated machinery works (per the Tier D structural audit):

- `/guides/embeddings` — three-tier embedding model architecture
- `/guides/compression` — LOD compression mechanics
- `/guides/smart-search` — query intent classification routing
- `/guides/dynamic-model-loading` — VRAM balancing for local LLMs

These four should live alongside `indexing`/`code-graph`/`graph-enrichment`/`context`
under the same renamed section. They also need their layout migrated to
the `ConceptPageShell` component for visual consistency.

## Scope

| Item | Effort | Notes |
|---|---|---|
| Pick a new section name | low | See "Naming options" below |
| Rename top-level docs URL `/concepts/` → `/{new}/` | medium | URL change; need permanent redirects from the old paths so external links don't break |
| Move 4 explainer guides into the new section | low | Plain file moves; redirects from `/guides/*` paths |
| Migrate the 4 moved pages to `ConceptPageShell` layout | medium | Rewrap content in the shell component (subtitle, title, description, sections array). Existing 4 concepts pages already use it — match that pattern. |
| Update sidebar `docs.ts` + `sitemap.ts` + cross-page links | low | Sweep references across docs + marketing |
| Update any in-code references (`<a href="/concepts/...">`) | low | grep + edit |
| Update CLAUDE.md / AGENTS.md guidance if it mentions the section | low | Cross-reference check |
| Coordinate with marketing-site copy if it links here | low | A handful of links per prior audits |

## Naming options for the rename

Two distinct angles to consider — pick whichever fits the broader brand voice.

| Candidate | Why | Tradeoff |
|---|---|---|
| **How It Works** | Plain-language, exactly describes the content | Slightly informal; two words; verb-y |
| **Internals** | Tight, technical, no app-feature collision | Reads as "advanced only" to some readers |
| **Foundations** | Suggests "build on top of these ideas" | Slightly marketing-y |
| **Architecture** | Direct, technical | Too narrow — the section covers more than architecture |
| **Under the Hood** | Friendly + descriptive | Idiomatic; may not translate well |
| **Reference** | Standard docs vocabulary | Too vague; reads like an API reference |

Recommendation: **"How It Works"** unless there's a brand preference for
something tighter. Aligns with the existing voice on `/concepts/graph-enrichment`
("The Journey", "Always Running") and the marketing-vs-docs split rule
(docs = HOW-TO; this section is "how the automation works", which fits).

## Execution checklist

1. **Decide the new name.** (User decision — block phase start until set.)
2. **Create new top-level route**, e.g. `/how-it-works/`, in `websites/apps/docs/src/app/`.
3. **Move pages**:
   - `/concepts/indexing` → `/{new}/indexing`
   - `/concepts/code-graph` → `/{new}/code-graph`
   - `/concepts/graph-enrichment` → `/{new}/graph-enrichment`
   - `/concepts/context` → `/{new}/context`
   - `/guides/embeddings` → `/{new}/embeddings`
   - `/guides/compression` → `/{new}/compression`
   - `/guides/smart-search` → `/{new}/smart-search`
   - `/guides/dynamic-model-loading` → `/{new}/dynamic-model-loading`
4. **Migrate the 4 ex-guide pages to `ConceptPageShell`**:
   - Wrap content with `<ConceptPageShell subtitle="..." title="..." description="..." sections={SECTIONS}>`
   - Define `SECTIONS` array matching the existing pattern (id + label per anchor)
   - Replace `<AnchorHeading>` calls with the standard pattern used by the 4 existing concepts pages
5. **Add Next.js redirects** in `next.config` for all 8 old paths.
6. **Update sidebar (`docs.ts`)** to the new section name and order.
7. **Update sitemap (`sitemap.ts`)** with new paths.
8. **Grep and update cross-links**:
   - `websites/apps/docs/src/` — internal `<a href="/concepts/...">` and `<a href="/guides/...">` references to moved pages
   - `websites/apps/marketing/src/` — outbound links from marketing pages
   - `websites/apps/support/`, `websites/apps/payments/` — same sweep
9. **Update CLAUDE.md** if it references `/concepts/` as a section.
10. **Verify** with a dev-server walkthrough: no 404s, redirects fire, sidebar
    renders correctly, all `StoryEmbed`s still resolve.

## Definition of done

- New top-level section route exists with the 8 pages.
- All 4 ex-guide pages use `ConceptPageShell` and visually match the existing
  4 concepts pages.
- Old `/concepts/*` and `/guides/{embeddings,compression,smart-search,dynamic-model-loading}`
  URLs return permanent redirects.
- Sidebar reflects the new structure. `/guides/` section now contains only
  the 9 procedural how-tos.
- No broken internal links remain (sweep + dev-server walkthrough).
- Memory `project_llm_strategy.md` and Phase 132 progress tracker updated
  with the rename outcome.

## Not in scope

- Rewriting the content of any moved page. (Phase 132 already verified
  fidelity for these 8 pages; this is a structural move only.)
- Renaming the `prep_concepts` MCP tool, the dashboard Concepts panel, the
  concept store, or any code-level "concept" naming. The app feature keeps
  its name; only the docs section moves.

## Cross-references

- Phase 132 progress tracker: `docs/Phase132_DocsBehavioralFidelity/00_progress_tracker.md`
- Phase 132 Tier D audit (where the structural question was raised):
  `docs/Phase132_DocsBehavioralFidelity/04_TierD_guides.md`
- Phase 137 (docs live-asset integration) — Phase 138 should land BEFORE
  Phase 137's page-audit pass to avoid having to re-place live embeds after
  URL changes.
