# Research Page — Design Spec

**Date:** 2026-04-10
**Owner:** Eric Bintner
**Status:** Draft, awaiting approval
**Source list:** [`docs/Phase99_Content/research/00_Research_Sources_Master_List.md`](../../Phase99_Content/research/00_Research_Sources_Master_List.md)

---

## 1. Goal & audience

A public page that establishes CoDRAG's intellectual lineage — the papers, repos, blogs, and standards the project was built on. Three jobs, in priority order:

1. **Credibility signal for evaluators** *(primary)* — devs and teams evaluating CoDRAG can spend 30–60 seconds and walk away thinking "this team knows their space."
2. **Honest attribution** *(secondary)* — the page reads as a sincere acknowledgment of the people whose work CoDRAG draws on, not a marketing flourish.
3. **Whitepaper-grade bibliography** *(tertiary)* — sortable, citation-style entries that can be linked from a deck, an essay, or the future whitepaper.

**Non-goals:** SEO landing page, blog post, lead capture, comparison piece, or recruiting pitch.

## 2. Placement & navigation

- **URL:** `/research` on the marketing site (`websites/apps/marketing`)
- **Routing:** standard Next.js app-router page at `src/app/research/page.tsx` + `layout.tsx`
- **Header nav:** **not** added to primary header nav (intentional — discovered, not pushed)
- **Footer:** add link under the Resources column ("Research")
- **Cross-links:**
  - One-line callout from `/about` ("→ Read the research CoDRAG was built on")
  - One-line callout from `/compare` ("We've actually read the papers behind every tool here. See our research →")
  - Future whitepaper / long-form blog posts deep-link to specific section anchors

**Out of scope:** subdomain, separate DNS, separate Next app.

## 3. Design system & reused components

| Layer | Component | Source |
|---|---|---|
| Page shell | `DetailPageLayout` | `@codrag/ui` (already used by `/security`, `/immune-system`, `/graph-enrichment`) |
| Sidebar TOC | Built into `DetailPageLayout` `sections` prop | same |
| Card grid (appendix) | `FeatureBlocks` `variant="cards"` | `@codrag/ui` |
| List with icon (spotlights) | `FeatureBlocks` `variant="list"` (extended) | `@codrag/ui` |
| Header/footer | `SiteHeader` / `SiteFooter` (auto-wrap via `ClientLayout`) | marketing app |
| Typography | IBM Plex Serif (headings), Inter (body), JetBrains Mono (citation IDs) | already configured globally |
| Color tokens | `text-text`, `text-text-muted`, `surface-raised`, `primary` | already configured |

**New components to build** (all live in `packages/ui/src/components/marketing/research/` with stories in `packages/ui/src/stories/marketing/research/`):

| Component | Purpose | Storybook stories |
|---|---|---|
| `ResearchHero` | Centered editorial hero — eyebrow ("Bibliography"), Plex-Serif headline, 1-paragraph subhead, no CTA. ~120px tall. | Default |
| `SourceSpotlight` | Feature treatment for the ~12 key works. Type badge, citation line (author, year, venue), title link, 2–3 short paragraphs of usage prose. Editorial card with rounded border, surface-raised bg. | Paper / Repo / Blog / Spec variants |
| `SourceCard` | Compact appendix entry. Type badge, title (linked), citation line, 1-sentence usage. Renders inside `FeatureBlocks` cards. | Default + with-long-title overflow case |
| `ResearchSection` | Wraps a problem-area section: heading + 1-paragraph intro + spotlight stack + collapsible appendix list. | Default + empty-appendix |
| `SourceFilterChips` | Type filters (`All / Papers / Repos / Blogs / Standards`) — toggles visibility on appendix entries within a section. Lightweight `useState`. | Default + active state |
| `ResearchAppendix` | The "Full bibliography" block at the bottom of each section. Renders a `SourceCard` grid filtered by `SourceFilterChips`. | Default + filtered |

**No new global hero variants.** `ResearchHero` is page-local, not added to `MarketingHero`.

## 4. Page architecture

```
┌─────────────────────────────────────────────────────────┐
│  SiteHeader (auto)                                      │
├─────────────────────────────────────────────────────────┤
│  ResearchHero                                           │
│    eyebrow: "Bibliography"                              │
│    h1:      "What CoDRAG was built on."                 │
│    subhead: 2-sentence editorial paragraph              │
├──────────────┬──────────────────────────────────────────┤
│ Sticky TOC   │  Section 1: Retrieval & Long Context     │
│ (sidebar)    │    1-paragraph intro                     │
│              │    [SourceSpotlight × 3]                 │
│  Retrieval   │    [ResearchAppendix with filter chips]  │
│  Compression │                                          │
│  Chunking &  │  Section 2: Compression & LOD            │
│   Structure  │    intro                                 │
│  Concepts &  │    [SourceSpotlight × 4]                 │
│   Standards  │    [ResearchAppendix]                    │
│              │                                          │
│  ─ docs link │  Section 3: Code Structure & Chunking    │
│              │    [SourceSpotlight × 3]                 │
│              │    [ResearchAppendix]                    │
│              │                                          │
│              │  Section 4: Concepts, Knowledge          │
│              │             & Standards                  │
│              │    [SourceSpotlight × 2]                 │
│              │    [ResearchAppendix]                    │
│              │                                          │
│              │  Closing note (1 paragraph)              │
├──────────────┴──────────────────────────────────────────┤
│  SiteFooter (auto)                                      │
└─────────────────────────────────────────────────────────┘
```

**Reading flow:** sticky TOC lets an evaluator jump to a problem area immediately. Each section opens with a 2–3 sentence framing of the problem, then 2–4 spotlight sources with editorial treatment, then a collapsible appendix of supporting/related sources.

## 5. Information architecture — sections & spotlights

Four sections, ~12 spotlights total, ~40 supporting sources in appendices.

### Section 1 — Retrieval & Long Context

**Intro framing:** Why context engineering matters more than raw context size.

**Spotlights (3):**
- **Liu et al. — *Lost in the Middle: How Language Models Use Long Contexts*** (TACL 2024, [arXiv 2307.03172](https://arxiv.org/abs/2307.03172))
  Drives CoDRAG's conservative context-budget defaults and the "rank, then place at the edges" assembly rule.
- **Han et al. — *RAG vs. GraphRAG: A Systematic Evaluation*** ([arXiv 2502.11371](https://arxiv.org/abs/2502.11371))
  Validates trace-graph expansion as the right answer for multi-hop queries — directly motivates `codrag_search`'s expansion hop.
- **Anthropic — *Contextual Retrieval*** ([Sept 2024](https://www.anthropic.com/news/contextual-retrieval))
  Adopted directly: prepend file-level context to each chunk before embedding. Reported 49% retrieval-failure reduction.

**Appendix:** Chen et al. *Context Length Alone Hurts*, Chroma *Context Rot*, Databricks *Long Context RAG Performance*, *Context Discipline & Performance Correlation*, *Retrieval-Augmented Code Generation: A Survey*, *Context Engineering Survey*, `zilliztech/claude-context`.

### Section 2 — Compression & Levels of Detail

**Intro framing:** Why CoDRAG's context assembler ladders code from full source down to one-line signatures.

**Spotlights (4):**
- **Stingy Context: 18:1 Hierarchical Code Compression** ([arXiv 2601.19929](https://arxiv.org/abs/2601.19929))
  Primary inspiration for the LOD 0–5 extraction ladder.
- **Hierarchical Context Pruning** ([arXiv 2406.18294](https://arxiv.org/abs/2406.18294))
  Empirical validation that signatures-only context preserves ~90% of downstream quality. Backbone for LOD 2.
- **Aider** ([github.com/Aider-AI/aider](https://github.com/Aider-AI/aider))
  Production proof for repo-map-style LOD 4 at scale. The "this works in the wild" reference.
- **microsoft/LLMLingua** ([github.com/microsoft/LLMLingua](https://github.com/microsoft/LLMLingua))
  BERT-classifier token pruning. Adopted as the language/docs compressor half of CoDRAG's dual-compressor design.

**Appendix:** Repoformer (ICML 2024), GraphCoder, RepoHyper, STALL+, *In Line with Context*, Activation Beacon, LLMLingua-2, *On the Impacts of Contexts*, Repomix, LongCodeZip, CodeRAG-Bigraph, CLaRa.

### Section 3 — Code Structure & Chunking

**Intro framing:** Why chunking on AST boundaries beats character splits for code.

**Spotlights (3):**
- **garrytan/gbrain** ([github.com/garrytan/gbrain](https://github.com/garrytan/gbrain))
  Catalyst for Phase 93. Savitzky-Golay semantic boundary detection and RRF hybrid search directly informed CoDRAG's semantic chunker and multi-query retrieval.
- **cAST: Enhancing Code RAG with Structural Awareness** ([arXiv 2506.15655](https://arxiv.org/abs/2506.15655))
  Confirms AST-boundary-respecting chunks beat naive splits — basis for the tree-sitter chunker.
- **Edge et al. — *GraphRAG: From Local to Global*** ([arXiv 2404.16130](https://arxiv.org/abs/2404.16130))
  Inspired the atlas + module-summary layer: multi-stage community summaries rolled into project-level context.

**Appendix:** Jina *Late Chunking*, ColBERT (SIGIR 2020), Reciprocal Rank Fusion (Cormack et al., SIGIR 2009), RAGAS, Savitzky-Golay (1964), *CodeGraph*, *RepoAgent*.

### Section 4 — Concepts, Knowledge & Standards

**Intro framing:** Why CoDRAG treats concepts as first-class artifacts and where the protocol surface comes from.

**Spotlights (3):**
- **Guo et al. — *GraphCodeBERT: Pre-training Code Representations with Data Flow*** (ICLR 2021)
  Justifies why data-flow information improves code understanding — the rationale behind PDG-style edges in the trace graph.
- **Nonaka & Takeuchi — *The Knowledge-Creating Company* (SECI model)** (Oxford UP, 1995)
  Epistemological frame for the concepts system: tacit→explicit knowledge transfer ("externalization") is exactly what CoDRAG's concepts capture.
- **Anthropic — *Model Context Protocol*** ([modelcontextprotocol.io](https://modelcontextprotocol.io))
  The protocol CoDRAG ships its primary interface on. Every `codrag_*` tool, the resources surface, and the per-client context budgets are MCP-shaped from the ground up — without this spec there is no CoDRAG MCP server.

**Appendix:** Ferrante et al. *Program Dependence Graph* (1987), Traag et al. *Leiden Algorithm* (2019), Ganter & Wille *Formal Concept Analysis* (1999), Brooks *Top-Down Comprehension* (1983), Pennington (1987), Miller's Law (1956), Nygard ADRs, KARMA (NeurIPS 2025), LLMs4OL (ISWC), TraceBERT, NASA SWE-072, KIT fine-grained traceability papers, ACP, A2A, SARIF, OCSF, agents.md.

### Cuts (not on the page)

| Removed | Why |
|---|---|
| Tremor, plotext, react-grid-layout | UI implementation deps — not research. |
| EricBintner/CLaRa-Remembers-It-All | CoDRAG's own historical work. |
| MagneticAnomaly/CoDRAG-MCP and `codrag/codrag-mcp` | Self-references. |
| Trivy / Gitleaks / Cosign / Syft / Presidio / DataFog / NeMo Guardrails / Pytector / OSSF Scorecard / LLM Guard | Enterprise security tooling — meaningful for the security page, not for the bibliography. (Could revive on `/security` if it doesn't already cite them.) |
| Greptile / Cursor / Continue / Augment / Sourcegraph / Ragie | Competitors — belong on `/compare`, not here. The page is about influences, not the field. |
| Ollama, Apple CLaRa-7B, Nomic Embed, Voyage Code 3 | Model/runtime evaluations — implementation choices, not research influences. (Voyage and Nomic blog posts could be moved into Section 1 appendix if you want them; flagged.) |

**Result:** ~50 sources on the page (12 spotlight + ~38 appendix). Open question: do you want Voyage / Nomic blog posts kept as appendix in Section 1? Default: kept.

## 6. Copy & tone

**Register:** restrained third-person (T2) as the spine, with brief first-person flickers (T1) inside spotlight blurbs *only* — never in section intros, never in the hero.

**Hero copy** (draft):

> **Bibliography**
> ## What CoDRAG was built on.
> A working list of the papers, repositories, essays, and standards CoDRAG draws on. Each entry includes a one-line note on how it shaped the project — and what we changed when we disagreed.

**Spotlight blurb format:**
- 2–3 sentences max
- Lead with what the source argues or proves
- Close with how CoDRAG implements (or rejects) it
- Verbs: *adopted*, *adapted*, *evaluated*, *rejected*, *informed*, *grounds*, *validates*
- Avoid: *leveraged*, *utilized*, *industry-leading*, *game-changing*

**Appendix entry format:**
- One sentence. Same verbs.

**Section intros** (~2 sentences each): plain prose, no marketing language. Frame the *problem*, not the *product*.

**Closing note** (~3 sentences):

> This list is incomplete. We add to it as we read, and we welcome corrections — if we've cited your work badly, or missed work we should know about, open an issue on [the repo](https://github.com/MagneticAnomaly/CoDRAG-MCP/issues). We'll fix it.

## 7. Interactivity

- **Filter chips** (`SourceFilterChips`) on each appendix block: `All / Paper / Repo / Blog / Spec`. Toggling filters the cards within that section's appendix only. Pure `useState`, no URL state.
- **Sticky sidebar TOC** (built into `DetailPageLayout`).
- **Anchor links** on each section (`#retrieval`, `#compression`, `#chunking`, `#concepts`) for deep linking.
- No search box. No global filter. No sort.

**Out of scope:** client-side full-text search, fuzzy filtering, dark/light toggle (inherited), pagination, infinite scroll.

## 8. Storybook integration

Every new component is documented as a Storybook story under `packages/ui/src/stories/marketing/research/`:

```
packages/ui/src/stories/marketing/research/
├── ResearchHero.stories.tsx
├── SourceSpotlight.stories.tsx       # variants: paper / repo / blog / spec
├── SourceCard.stories.tsx            # default + long-title overflow
├── ResearchSection.stories.tsx       # full section with spotlights + appendix
├── SourceFilterChips.stories.tsx     # default + each active state
└── ResearchAppendix.stories.tsx      # default + filtered states
```

Each story uses realistic data drawn from the master list (no Lorem). Stories double as the visual review surface during build.

## 9. Data model

A single TypeScript module `packages/ui/src/data/researchSources.ts` exporting:

```ts
export type SourceType = 'paper' | 'repo' | 'blog' | 'spec' | 'book';

export interface ResearchSource {
  id: string;                    // slug, e.g. "lost-in-the-middle"
  type: SourceType;
  title: string;
  authors?: string;              // "Liu et al."
  venue?: string;                // "TACL 2024" | "ICLR 2021" | "github" | "Anthropic blog"
  year?: number;
  url: string;
  arxivId?: string;              // e.g. "2307.03172"
  usage: string;                 // 1-sentence appendix blurb
  spotlightProse?: string;       // 2-3 sentence spotlight body, only if spotlighted
  problemArea: 'retrieval' | 'compression' | 'chunking' | 'concepts';
  spotlight: boolean;
}

export const RESEARCH_SOURCES: ResearchSource[] = [ /* ~50 entries */ ];
```

The marketing page imports and groups them at render time. Section components receive `sources={sources.filter(s => s.problemArea === 'retrieval')}`.

This shape is also what Storybook stories consume — single source of truth.

## 10. Responsive behavior

- **≥1024px:** sidebar TOC + 2-column spotlight stack + 3-column appendix card grid
- **768–1023px:** TOC collapses to a top-of-page anchor menu, spotlights become 1-column, appendix cards become 2-column
- **<768px:** single column throughout, anchor menu becomes a `<details>` dropdown, filter chips wrap

Inherited from `DetailPageLayout`.

## 11. Accessibility

- Heading hierarchy: `h1` (page title in hero), `h2` (section titles), `h3` (spotlight titles), `h4` (appendix card titles)
- Filter chips: `role="tablist"` with `aria-pressed`
- TOC: `nav aria-label="On this page"`
- All external links have `rel="noopener noreferrer"` and `target="_blank"` with visually hidden "(opens in new tab)" text
- Color contrast: inherits from existing tokens (already AA)

## 12. Build phases

**Phase 1 — Data + components in storybook**
1. Write `researchSources.ts` with all ~50 entries (port from master list, write spotlight prose for the 12)
2. Build `SourceCard`, `SourceSpotlight`, `ResearchHero`, `SourceFilterChips`, `ResearchAppendix`, `ResearchSection`
3. Write Storybook stories for each, using real data
4. Visual review in Storybook (`npm run storybook` in `packages/ui`)

**Phase 2 — Page composition**
5. Create `websites/apps/marketing/src/app/research/page.tsx` and `layout.tsx`
6. Compose hero + 4 sections using the new components
7. Verify sticky TOC, anchor links, filter chips work in the running marketing app

**Phase 3 — Wiring**
8. Add Footer link under Resources column
9. Add `/about` callout
10. Add `/compare` callout
11. Update sitemap (`websites/apps/marketing/src/app/sitemap.ts`)
12. Visual + lighthouse + a11y check

**Phase 4 — Review**
13. Build the marketing app, walk the page, capture screenshots
14. Eric reviews; iterate on copy, cuts, tone

**Out of scope this round:** SEO og:image generation, dynamic citation BibTeX export, "submit a source" form, RSS, internationalization.

## 13. Open questions for the reviewer

1. ~~**Section 4 spotlight count.**~~ Resolved 2026-04-10: promoted **MCP** to a third Section 4 spotlight so the section's "Standards" half has a flagship.
2. **Voyage / Nomic embedding blogs.** Keep in Section 1 appendix, move to a "tools we evaluated" callout, or cut?
3. **Closing note GitHub link.** Use `MagneticAnomaly/CoDRAG-MCP` (current canonical) or wait for the post-rebrand canonical URL?
4. **Footer column.** Confirm "Resources" is the right column for the link (vs. "Company" or a new "Reference" column).
5. **Spotlight prose length cap.** I've drafted 2–3 sentences. Want longer (paragraph) or shorter (1 line) for the spotlight tier?

## 14. Definition of done

- `/research` route renders in the marketing app at `localhost:3000/research` (or whichever port `npm run dev` picks)
- All ~50 sources appear, grouped into the 4 sections
- 12 spotlights have feature treatment, ~38 appendix entries are card-list
- Filter chips toggle visibility within their section
- Sidebar TOC scrolls with the page and highlights the current section
- Footer link works; `/about` and `/compare` callouts work
- Every new component has a Storybook story rendering with real data
- Lighthouse a11y ≥ 95
- No new dependencies installed
