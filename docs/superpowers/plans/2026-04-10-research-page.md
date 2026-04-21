# Research Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a public `/research` page on the CoDRAG marketing site that lists ~56 external research sources (papers, repos, essays, standards) the project draws on, with editorial spotlights for ~12 key works and a filterable appendix per problem area.

**Architecture:** Six new React components live in `@codrag/ui` under `components/marketing/research/`. A single `data/researchSources.ts` module is the source of truth for the source list and is consumed by both the marketing page and the Storybook stories. The marketing page reuses the existing `DetailPageLayout` shell (sticky sidebar TOC + 3+9 grid) and composes the new components inside.

**Tech Stack:** TypeScript, React, Next.js (app router) for the marketing app, Tailwind CSS, Storybook 7.6, lucide-react icons, `@codrag/ui` shared component library. No new dependencies. No unit-test framework is configured in `packages/ui` — gates are TypeScript typecheck, a runtime data-validator, Storybook visual smoke, and `next build`.

**Spec:** [`docs/superpowers/specs/2026-04-10-research-page-design.md`](../specs/2026-04-10-research-page-design.md)

---

## File Structure

**New files (`packages/ui`):**

| Path | Responsibility |
|---|---|
| `packages/ui/src/data/researchSources.ts` | Type definitions, source list (~56 entries), runtime validator |
| `packages/ui/src/components/marketing/research/SourceCard.tsx` | Compact appendix card (badge + title + citation + 1-line usage) |
| `packages/ui/src/components/marketing/research/SourceSpotlight.tsx` | Editorial feature card for the ~12 key works (badge + citation + headline + 2-3 sentence prose) |
| `packages/ui/src/components/marketing/research/ResearchHero.tsx` | Centered editorial hero rendered inside `DetailPageLayout`'s main column |
| `packages/ui/src/components/marketing/research/SourceFilterChips.tsx` | Type filter pills (`All / Papers / Repos / Essays / Specs / Books`) with `aria-pressed` |
| `packages/ui/src/components/marketing/research/ResearchAppendix.tsx` | "Further reading" block: filter chips + filtered grid of `SourceCard`s |
| `packages/ui/src/components/marketing/research/ResearchSection.tsx` | Wraps a problem-area section: heading + intro + spotlight stack + appendix |
| `packages/ui/src/components/marketing/research/index.ts` | Barrel export for the research components |
| `packages/ui/src/stories/marketing/research/SourceCard.stories.tsx` | Story for SourceCard |
| `packages/ui/src/stories/marketing/research/SourceSpotlight.stories.tsx` | Story for SourceSpotlight (one per type variant) |
| `packages/ui/src/stories/marketing/research/ResearchHero.stories.tsx` | Story for ResearchHero |
| `packages/ui/src/stories/marketing/research/SourceFilterChips.stories.tsx` | Story for filter chips (default + active states) |
| `packages/ui/src/stories/marketing/research/ResearchAppendix.stories.tsx` | Story for appendix block |
| `packages/ui/src/stories/marketing/research/ResearchSection.stories.tsx` | Story for full section with real Section 1 data |

**New files (`websites/apps/marketing`):**

| Path | Responsibility |
|---|---|
| `websites/apps/marketing/src/app/research/page.tsx` | Marketing page composing the new components |
| `websites/apps/marketing/src/app/research/layout.tsx` | Per-route metadata (title, description, og) |

**Modified files:**

| Path | Change |
|---|---|
| `packages/ui/src/components/marketing/index.ts` | Re-export research components and types |
| `packages/ui/src/index.ts` | Add research components to public API |
| `websites/apps/marketing/src/app/ClientLayout.tsx:21-38` | Add `Research` link to footer "Company" column |
| `websites/apps/marketing/src/app/sitemap.ts` | Add `/research` to routes array |
| `websites/apps/marketing/src/app/about/page.tsx` | Add 1-line callout to research page |
| `websites/apps/marketing/src/app/compare/page.tsx` | Add 1-line callout to research page |

---

## Phases & Review Checkpoints

- **Phase 1 — Data module** (Tasks 1–5): Data is the foundation. Ends with all sources committed and validated.
- **Phase 2 — Components in Storybook** (Tasks 6–11): Build each component with a story that uses real data from Phase 1. Visual review possible at end of phase.
- **Phase 3 — Page composition** (Task 12): Wire the page together inside the marketing app.
- **Phase 4 — Cross-linking & SEO** (Tasks 13–14): Footer link, sitemap, callouts.
- **Phase 5 — Final QA** (Task 15): Lint, typecheck, build, manual walk-through.

Each task ends with a commit. Commit messages follow `feat(research): …` style and **do not** include a `Co-Authored-By` trailer (per project convention).

---

## Phase 1 — Data Module

### Task 1: Scaffold the data module with types and validator

**Files:**
- Create: `packages/ui/src/data/researchSources.ts`

- [ ] **Step 1: Create the data file with types and an empty list**

```ts
// packages/ui/src/data/researchSources.ts

export type SourceType = 'paper' | 'repo' | 'blog' | 'spec' | 'book';
export type ProblemArea = 'retrieval' | 'compression' | 'chunking' | 'concepts';

export interface ResearchSource {
  /** kebab-case unique slug, used as React key and anchor */
  id: string;
  type: SourceType;
  title: string;
  /** "Liu et al." or "Anthropic" — optional, omitted for repos when redundant */
  authors?: string;
  /** "TACL 2024" | "ICLR 2021" | "Anthropic blog" | "GitHub" */
  venue?: string;
  year?: number;
  url: string;
  /** e.g. "2307.03172" — optional */
  arxivId?: string;
  /** One sentence, used in the appendix card */
  usage: string;
  /** 2-3 sentence editorial blurb. Required if spotlight === true. */
  spotlightProse?: string;
  problemArea: ProblemArea;
  spotlight: boolean;
}

export const RESEARCH_SOURCES: ResearchSource[] = [];

/**
 * Throws on any data shape error so Storybook and `next build` fail loudly
 * if a contributor adds a malformed entry.
 */
export function validateResearchSources(sources: ResearchSource[]): void {
  const seen = new Set<string>();
  for (const s of sources) {
    if (!s.id || !s.title || !s.url || !s.usage || !s.problemArea || !s.type) {
      throw new Error(
        `[researchSources] entry "${s.id ?? '(no id)'}" missing required field`,
      );
    }
    if (seen.has(s.id)) {
      throw new Error(`[researchSources] duplicate id "${s.id}"`);
    }
    seen.add(s.id);
    if (s.spotlight && (!s.spotlightProse || s.spotlightProse.trim().length === 0)) {
      throw new Error(`[researchSources] spotlight "${s.id}" missing spotlightProse`);
    }
    if (!/^[a-z0-9-]+$/.test(s.id)) {
      throw new Error(`[researchSources] id "${s.id}" must be kebab-case`);
    }
  }
}

validateResearchSources(RESEARCH_SOURCES);
```

- [ ] **Step 2: Verify typecheck passes**

Run from repo root: `cd packages/ui && npm run typecheck`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add packages/ui/src/data/researchSources.ts
git commit -m "feat(research): scaffold researchSources data module with types and validator"
```

---

### Task 2: Add Section 1 sources — Retrieval & Long Context

**Files:**
- Modify: `packages/ui/src/data/researchSources.ts`

- [ ] **Step 1: Replace the empty `RESEARCH_SOURCES` array with the Section 1 entries**

Find: `export const RESEARCH_SOURCES: ResearchSource[] = [];`
Replace with:

```ts
export const RESEARCH_SOURCES: ResearchSource[] = [
  // ─── Section 1: Retrieval & Long Context ──────────────────────────────
  {
    id: 'lost-in-the-middle',
    type: 'paper',
    title: 'Lost in the Middle: How Language Models Use Long Contexts',
    authors: 'Liu et al.',
    venue: 'TACL 2024',
    year: 2024,
    url: 'https://arxiv.org/abs/2307.03172',
    arxivId: '2307.03172',
    usage: 'Drives CoDRAG\u2019s conservative context-budget defaults and the rule that the most relevant chunks land at the edges of the window.',
    spotlightProse: 'Liu et al. show that language models attend to the start and end of a long context far more than the middle. The finding sets the ceiling for any retrieval system that pads its context na\u00efvely. CoDRAG ranks results by relevance and assembles them so the highest-scoring chunks bracket the prompt, never bury it.',
    problemArea: 'retrieval',
    spotlight: true,
  },
  {
    id: 'rag-vs-graphrag',
    type: 'paper',
    title: 'RAG vs. GraphRAG: A Systematic Evaluation and Key Insights',
    authors: 'Han et al.',
    venue: 'arXiv 2025',
    year: 2025,
    url: 'https://arxiv.org/abs/2502.11371',
    arxivId: '2502.11371',
    usage: 'Validates trace-graph expansion as the right answer for multi-hop queries.',
    spotlightProse: 'Han et al. compare flat-vector RAG against graph-augmented RAG across reasoning-heavy benchmarks and find that local community search wins on multi-hop questions. CoDRAG\u2019s `codrag_search` follows the same logic: vector hits seed the query, then a trace-graph hop expands the neighborhood before the final assembly.',
    problemArea: 'retrieval',
    spotlight: true,
  },
  {
    id: 'anthropic-contextual-retrieval',
    type: 'blog',
    title: 'Contextual Retrieval',
    authors: 'Anthropic',
    venue: 'Anthropic blog',
    year: 2024,
    url: 'https://www.anthropic.com/news/contextual-retrieval',
    usage: 'Adopted directly: prepend file-level context to each chunk before embedding.',
    spotlightProse: 'Anthropic\u2019s post argued that prepending a few lines of file-level context to each chunk before embedding reduced retrieval failures by 49% in their tests. CoDRAG\u2019s semantic chunker now does exactly this \u2014 every chunk carries a synopsis prefix derived from its enclosing module so the embedding sees the same neighborhood the model will reason over.',
    problemArea: 'retrieval',
    spotlight: true,
  },
  {
    id: 'context-length-alone-hurts',
    type: 'paper',
    title: 'Context Length Alone Hurts LLM Performance Despite Perfect Retrieval',
    authors: 'Chen et al.',
    venue: 'EMNLP 2025 Findings',
    year: 2025,
    url: 'https://arxiv.org/abs/2510.05381',
    arxivId: '2510.05381',
    usage: 'Reasoning degrades even with 100% retrieval accuracy \u2014 evidence for retrieve-then-solve over context padding.',
    problemArea: 'retrieval',
    spotlight: false,
  },
  {
    id: 'chroma-context-rot',
    type: 'blog',
    title: 'Context Rot: How Increasing Input Tokens Impacts LLM Performance',
    authors: 'Chroma Research',
    venue: 'trychroma.com',
    year: 2025,
    url: 'https://research.trychroma.com/context-rot',
    usage: '18-LLM evaluation showing distractor similarity compounds context degradation. Sets default min-score thresholds.',
    problemArea: 'retrieval',
    spotlight: false,
  },
  {
    id: 'databricks-long-context-rag',
    type: 'blog',
    title: 'Long Context RAG Performance of LLMs',
    authors: 'Databricks Research',
    venue: 'databricks.com',
    year: 2024,
    url: 'https://www.databricks.com/blog/long-context-rag-performance-llms',
    usage: 'Identifies the 4K\u201332K token RAG saturation point that justifies CoDRAG\u2019s 6K\u20138K conservative defaults.',
    problemArea: 'retrieval',
    spotlight: false,
  },
  {
    id: 'context-discipline-correlation',
    type: 'paper',
    title: 'Context Discipline and Performance Correlation',
    venue: 'arXiv 2025',
    year: 2025,
    url: 'https://arxiv.org/abs/2601.11564',
    arxivId: '2601.11564',
    usage: 'Documents latency cliffs past ~15K words \u2014 informs CoDRAG\u2019s per-client char-budget caps.',
    problemArea: 'retrieval',
    spotlight: false,
  },
  {
    id: 'rag-survey',
    type: 'paper',
    title: 'Retrieval-Augmented Code Generation: A Survey',
    venue: 'arXiv 2024',
    year: 2024,
    url: 'https://arxiv.org/abs/2510.04905',
    arxivId: '2510.04905',
    usage: 'Comprehensive map of code-RAG techniques. Used to position CoDRAG inside the repository-level RAG quadrant.',
    problemArea: 'retrieval',
    spotlight: false,
  },
  {
    id: 'context-engineering-survey',
    type: 'paper',
    title: 'Context Engineering for Large Language Models: A Survey',
    venue: 'arXiv 2025',
    year: 2025,
    url: 'https://arxiv.org/abs/2507.13334',
    arxivId: '2507.13334',
    usage: 'Umbrella framing for the broader context-engineering discipline.',
    problemArea: 'retrieval',
    spotlight: false,
  },
  {
    id: 'zilliztech-claude-context',
    type: 'repo',
    title: 'zilliztech/claude-context',
    venue: 'GitHub',
    url: 'https://github.com/zilliztech/claude-context',
    usage: 'MCP server reporting ~40% token reduction via vector search \u2014 external corroboration of CoDRAG\u2019s retrieval-first approach.',
    problemArea: 'retrieval',
    spotlight: false,
  },
];
```

- [ ] **Step 2: Verify typecheck and validator pass**

Run: `cd packages/ui && npm run typecheck`
Expected: no errors. The validator runs at module load — any malformed entry would already throw during typecheck if used elsewhere; here it runs during Storybook startup in later tasks.

- [ ] **Step 3: Commit**

```bash
git add packages/ui/src/data/researchSources.ts
git commit -m "feat(research): add Section 1 sources (retrieval & long context)"
```

---

### Task 3: Add Section 2 sources — Compression & Levels of Detail

**Files:**
- Modify: `packages/ui/src/data/researchSources.ts`

- [ ] **Step 1: Append Section 2 entries** to the `RESEARCH_SOURCES` array, immediately before the closing `];`

Insert this block:

```ts
  // ─── Section 2: Compression & Levels of Detail ────────────────────────
  {
    id: 'stingy-context',
    type: 'paper',
    title: 'Stingy Context: 18:1 Hierarchical Code Compression for LLM Auto-Coding',
    venue: 'arXiv 2026',
    year: 2026,
    url: 'https://arxiv.org/abs/2601.19929',
    arxivId: '2601.19929',
    usage: 'Primary inspiration for CoDRAG\u2019s LOD 0\u20135 extraction ladder.',
    spotlightProse: 'Stingy Context demonstrates that hierarchical level-of-detail extraction can compress code by 18:1 with negligible quality loss for auto-coding tasks. CoDRAG\u2019s context assembler implements the same ladder: full source for the focal file, compressed forms for callees, and one-line signatures for everything else.',
    problemArea: 'compression',
    spotlight: true,
  },
  {
    id: 'hierarchical-context-pruning',
    type: 'paper',
    title: 'Hierarchical Context Pruning: Optimizing Real-World Code Completion with Repository-Level Pretrained Code LLMs',
    venue: 'arXiv 2024',
    year: 2024,
    url: 'https://arxiv.org/abs/2406.18294',
    arxivId: '2406.18294',
    usage: 'Empirically validates that signatures-only context preserves ~90% of downstream quality.',
    spotlightProse: 'HCP measures, three pruning levels deep, the cost of dropping function bodies in favor of signatures only. The result \u2014 ~90% retention of completion quality \u2014 is the empirical backbone for CoDRAG\u2019s LOD 2 default. We promote bodies to LOD 0 only where the search score crosses a threshold.',
    problemArea: 'compression',
    spotlight: true,
  },
  {
    id: 'aider',
    type: 'repo',
    title: 'Aider-AI/aider',
    venue: 'GitHub',
    url: 'https://github.com/Aider-AI/aider',
    usage: 'Production proof for repo-map-style LOD 4 at scale \u2014 thousands of users in the wild.',
    spotlightProse: 'Aider\u2019s repo-map prunes a project into one-line signatures and ranks the visible set per turn. It is the public proof that LOD 4 works in production at scale, used by thousands of developers daily. CoDRAG\u2019s context assembler implements a similar selection step on top of the trace graph rather than a flat AST extract.',
    problemArea: 'compression',
    spotlight: true,
  },
  {
    id: 'microsoft-llmlingua',
    type: 'repo',
    title: 'microsoft/LLMLingua',
    venue: 'GitHub',
    url: 'https://github.com/microsoft/LLMLingua',
    usage: 'Adopted as the language/docs compressor half of CoDRAG\u2019s dual-compressor design.',
    spotlightProse: 'LLMLingua uses a small classifier to drop the lowest-information tokens from a prompt without losing meaning. CoDRAG runs LLMLingua-2 over Markdown and docstrings while letting code chunks flow through the structural LOD ladder \u2014 two compressors, one assembly.',
    problemArea: 'compression',
    spotlight: true,
  },
  {
    id: 'repoformer',
    type: 'paper',
    title: 'Repoformer: Selective Retrieval for Repository-Level Code Completion',
    authors: 'Wu et al.',
    venue: 'ICML 2024',
    year: 2024,
    url: 'https://arxiv.org/abs/2403.10059',
    arxivId: '2403.10059',
    usage: 'Validates score-gated retrieval \u2014 knowing when *not* to fetch context improves accuracy.',
    problemArea: 'compression',
    spotlight: false,
  },
  {
    id: 'graphcoder',
    type: 'paper',
    title: 'GraphCoder: Code Completion via Code Context Graph-based Retrieval',
    venue: 'arXiv 2024',
    year: 2024,
    url: 'https://arxiv.org/abs/2406.07003',
    arxivId: '2406.07003',
    usage: 'Baseline for graph-vs-embedding retrieval comparisons.',
    problemArea: 'compression',
    spotlight: false,
  },
  {
    id: 'repohyper',
    type: 'paper',
    title: 'RepoHyper: Search-Expand-Refine on Semantic Graphs for Repository-Level Code Completion',
    venue: 'arXiv 2024',
    year: 2024,
    url: 'https://arxiv.org/abs/2403.06095',
    arxivId: '2403.06095',
    usage: 'The Search\u2192Expand\u2192Refine pipeline maps 1:1 onto CoDRAG\u2019s search \u2192 trace expansion \u2192 LOD assembly.',
    problemArea: 'compression',
    spotlight: false,
  },
  {
    id: 'stall-plus',
    type: 'paper',
    title: 'STALL+: Boosting LLM-based Repository-Level Code Completion with Static Analysis',
    venue: 'arXiv 2024',
    year: 2024,
    url: 'https://arxiv.org/abs/2406.10018',
    arxivId: '2406.10018',
    usage: 'Static-analysis-at-prompting pattern; mirrors CoDRAG\u2019s use of trace-graph import edges to drive dependency-aware retrieval.',
    problemArea: 'compression',
    spotlight: false,
  },
  {
    id: 'in-line-with-context',
    type: 'paper',
    title: 'In Line with Context: Repository-Level Code Generation via Context Inlining',
    venue: 'arXiv 2026',
    year: 2026,
    url: 'https://arxiv.org/abs/2601.00376',
    arxivId: '2601.00376',
    usage: 'Flagged as a Phase-2 enhancement \u2014 inline callees/callers on top of existing LOD results.',
    problemArea: 'compression',
    spotlight: false,
  },
  {
    id: 'activation-beacon',
    type: 'paper',
    title: 'Long Context Compression with Activation Beacon',
    authors: 'Zhang et al.',
    venue: 'ICLR 2024',
    year: 2024,
    url: 'https://arxiv.org/abs/2401.03462',
    arxivId: '2401.03462',
    usage: 'Model-internal KV compression \u2014 explicitly complementary to CoDRAG\u2019s pre-prompt compression layer.',
    problemArea: 'compression',
    spotlight: false,
  },
  {
    id: 'llmlingua-2',
    type: 'paper',
    title: 'LLMLingua-2: Data Distillation for Prompt Compression',
    venue: 'arXiv 2023',
    year: 2023,
    url: 'https://arxiv.org/abs/2310.05736',
    arxivId: '2310.05736',
    usage: 'BERT-classifier token pruning. Adopted as the language/docs compressor.',
    problemArea: 'compression',
    spotlight: false,
  },
  {
    id: 'impacts-of-contexts',
    type: 'paper',
    title: 'On the Impacts of Contexts on Repository-Level Code Generation',
    venue: 'NAACL 2025',
    year: 2025,
    url: 'https://arxiv.org/abs/2505.09999',
    arxivId: '2505.09999',
    usage: 'Empirical evidence that signatures + docstrings are the highest-ROI context type.',
    problemArea: 'compression',
    spotlight: false,
  },
  {
    id: 'repomix',
    type: 'repo',
    title: 'yamadashy/repomix',
    venue: 'GitHub',
    url: 'https://github.com/yamadashy/repomix',
    usage: 'Production tree-sitter compression at ~70% reduction \u2014 evidence that LOD extraction is practical at scale.',
    problemArea: 'compression',
    spotlight: false,
  },
  {
    id: 'longcodezip',
    type: 'repo',
    title: 'YerbaPage/LongCodeZip',
    venue: 'GitHub',
    url: 'https://github.com/YerbaPage/LongCodeZip',
    usage: 'Evaluated as an off-the-shelf compressor; rejected due to 7B-model dependency incompatible with local-first architecture.',
    problemArea: 'compression',
    spotlight: false,
  },
  {
    id: 'coderag-bigraph',
    type: 'paper',
    title: 'CodeRAG: Supportive Code Retrieval on Bigraph',
    venue: 'arXiv 2025',
    year: 2025,
    url: 'https://arxiv.org/abs/2504.10046',
    arxivId: '2504.10046',
    usage: 'Bigraph retrieval reference \u2014 supports the case for graph-structured code representation.',
    problemArea: 'compression',
    spotlight: false,
  },
  {
    id: 'latent-reasoning-paper',
    type: 'paper',
    title: 'Continuous Latent Reasoning for RAG (arXiv 2511.18659)',
    venue: 'arXiv 2025',
    year: 2025,
    url: 'https://arxiv.org/abs/2511.18659',
    arxivId: '2511.18659',
    usage: 'Evaluated as a baseline; code/language retention measured at 20\u201329%, motivating CoDRAG\u2019s dual-compressor design.',
    problemArea: 'compression',
    spotlight: false,
  },
```

- [ ] **Step 2: Verify typecheck still passes**

Run: `cd packages/ui && npm run typecheck`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add packages/ui/src/data/researchSources.ts
git commit -m "feat(research): add Section 2 sources (compression & LOD)"
```

---

### Task 4: Add Section 3 sources — Code Structure & Chunking

**Files:**
- Modify: `packages/ui/src/data/researchSources.ts`

- [ ] **Step 1: Append Section 3 entries** to the array

Insert this block, immediately before the closing `];`:

```ts
  // ─── Section 3: Code Structure & Chunking ─────────────────────────────
  {
    id: 'gbrain',
    type: 'repo',
    title: 'garrytan/gbrain',
    venue: 'GitHub',
    url: 'https://github.com/garrytan/gbrain',
    usage: 'Catalyst for Phase 93 chunking work \u2014 informed CoDRAG\u2019s semantic chunker and multi-query retrieval.',
    spotlightProse: 'Garry Tan\u2019s gbrain pairs Savitzky\u2013Golay smoothing for semantic boundary detection with reciprocal-rank-fusion across multiple query expansions. Reading it kicked off Phase 93 and shaped CoDRAG\u2019s current chunker: smooth the similarity curve, cut on local minima, fuse vector and keyword hits with RRF.',
    problemArea: 'chunking',
    spotlight: true,
  },
  {
    id: 'cast',
    type: 'paper',
    title: 'cAST: Enhancing Code RAG with Structural Awareness',
    venue: 'arXiv 2025',
    year: 2025,
    url: 'https://arxiv.org/abs/2506.15655',
    arxivId: '2506.15655',
    usage: 'Confirms AST-boundary-respecting chunks beat naive splits.',
    spotlightProse: 'cAST shows that chunking on AST boundaries produces meaningfully better embeddings than fixed-window splits, particularly for languages with strong nesting structure. CoDRAG\u2019s tree-sitter chunker is grounded in this finding \u2014 we never split mid-function and the chunk header carries the full enclosing path.',
    problemArea: 'chunking',
    spotlight: true,
  },
  {
    id: 'graphrag',
    type: 'paper',
    title: 'GraphRAG: From Local to Global \u2014 A Graph-RAG Approach to Query-Focused Summarization',
    authors: 'Edge et al.',
    venue: 'Microsoft Research',
    year: 2024,
    url: 'https://arxiv.org/abs/2404.16130',
    arxivId: '2404.16130',
    usage: 'Inspired the atlas + module-summary layer: multi-stage community summaries rolled into project-level context.',
    spotlightProse: 'Edge et al. layer entity extraction, community detection, and per-community summarization to make a knowledge graph queryable as a hierarchy. CoDRAG\u2019s atlas does the same trick on code: directories and modules become communities, each with a generated synopsis that the assembler can hand to the model in place of the underlying files.',
    problemArea: 'chunking',
    spotlight: true,
  },
  {
    id: 'jina-late-chunking',
    type: 'blog',
    title: 'Late Chunking in Long-Context Embedding Models',
    authors: 'Jina AI',
    venue: 'Jina blog',
    year: 2024,
    url: 'https://jina.ai/news/late-chunking-in-long-context-embedding-models/',
    usage: 'Evaluated for long-context code files; kept as exploratory.',
    problemArea: 'chunking',
    spotlight: false,
  },
  {
    id: 'colbert',
    type: 'paper',
    title: 'ColBERT: Efficient and Effective Passage Search via Contextualized Late Interaction over BERT',
    authors: 'Khattab & Zaharia',
    venue: 'SIGIR 2020',
    year: 2020,
    url: 'https://arxiv.org/abs/2004.12832',
    arxivId: '2004.12832',
    usage: 'Token-level late interaction \u2014 reference paradigm for retrieval-quality upgrades.',
    problemArea: 'chunking',
    spotlight: false,
  },
  {
    id: 'reciprocal-rank-fusion',
    type: 'paper',
    title: 'Reciprocal Rank Fusion Outperforms Condorcet and Individual Rank Learning Methods',
    authors: 'Cormack, Clarke, Buettcher',
    venue: 'SIGIR 2009',
    year: 2009,
    url: 'https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf',
    usage: 'RRF (k=60) is the hybrid-fusion strategy CoDRAG uses to combine semantic and keyword search.',
    problemArea: 'chunking',
    spotlight: false,
  },
  {
    id: 'ragas',
    type: 'paper',
    title: 'RAGAS: Automated Evaluation of Retrieval Augmented Generation',
    authors: 'Shahul Es et al.',
    venue: 'EACL 2024',
    year: 2024,
    url: 'https://arxiv.org/abs/2309.15217',
    arxivId: '2309.15217',
    usage: 'Context-precision and context-recall metrics used to evaluate chunking-strategy experiments.',
    problemArea: 'chunking',
    spotlight: false,
  },
  {
    id: 'savitzky-golay',
    type: 'paper',
    title: 'Smoothing and Differentiation of Data by Simplified Least Squares Procedures',
    authors: 'Savitzky & Golay',
    venue: 'Analytical Chemistry',
    year: 1964,
    url: 'https://pubs.acs.org/doi/10.1021/ac60214a047',
    usage: 'The smoothing filter behind semantic-boundary detection on similarity curves.',
    problemArea: 'chunking',
    spotlight: false,
  },
  {
    id: 'codegraph',
    type: 'paper',
    title: 'CodeGraph: Code-Centric Knowledge Graphs for LLM-based Code Analysis',
    venue: 'arXiv 2023',
    year: 2023,
    url: 'https://arxiv.org/abs/2308.09687',
    arxivId: '2308.09687',
    usage: 'Early validation of graph-centric code understanding \u2014 shaped CoDRAG\u2019s TraceIndex node/edge model.',
    problemArea: 'chunking',
    spotlight: false,
  },
  {
    id: 'repoagent',
    type: 'paper',
    title: 'RepoAgent: An LLM-Powered Open-Source Framework for Repository-level Code Documentation Generation',
    venue: 'arXiv 2024',
    year: 2024,
    url: 'https://arxiv.org/abs/2402.16667',
    arxivId: '2402.16667',
    usage: 'Multi-pass LLM augmentation pattern that informs CoDRAG\u2019s per-node enrichment pipeline.',
    problemArea: 'chunking',
    spotlight: false,
  },
```

- [ ] **Step 2: Typecheck**

Run: `cd packages/ui && npm run typecheck`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add packages/ui/src/data/researchSources.ts
git commit -m "feat(research): add Section 3 sources (code structure & chunking)"
```

---

### Task 5: Add Section 4 sources — Concepts, Knowledge & Standards

**Files:**
- Modify: `packages/ui/src/data/researchSources.ts`

- [ ] **Step 1: Append Section 4 entries** to the array

Insert this block, immediately before the closing `];`:

```ts
  // ─── Section 4: Concepts, Knowledge & Standards ───────────────────────
  {
    id: 'graphcodebert',
    type: 'paper',
    title: 'GraphCodeBERT: Pre-training Code Representations with Data Flow',
    authors: 'Guo et al.',
    venue: 'ICLR 2021',
    year: 2021,
    url: 'https://arxiv.org/abs/2009.08366',
    arxivId: '2009.08366',
    usage: 'Justifies why data-flow information improves code understanding \u2014 the rationale behind PDG-style edges in the trace graph.',
    spotlightProse: 'Guo et al. show that pre-training code models on data-flow graphs (not just token streams) measurably improves downstream code understanding. CoDRAG\u2019s trace index encodes the same intuition by carrying control- and data-flow edges alongside symbol references, so retrievers can hop on dependency, not just on text similarity.',
    problemArea: 'concepts',
    spotlight: true,
  },
  {
    id: 'seci-model',
    type: 'book',
    title: 'The Knowledge-Creating Company (SECI Model)',
    authors: 'Nonaka & Takeuchi',
    venue: 'Oxford University Press',
    year: 1995,
    url: 'https://global.oup.com/academic/product/the-knowledge-creating-company-9780195092691',
    usage: 'Epistemological frame for the concepts system: tacit \u2192 explicit knowledge transfer.',
    spotlightProse: 'Nonaka & Takeuchi\u2019s SECI model frames organizational knowledge as a four-step cycle: socialize, externalize, combine, internalize. CoDRAG\u2019s concepts feature is a literal externalization tool \u2014 the tacit "we don\u2019t do it that way" assumptions in a team\u2019s head become typed, anchored, testable artifacts that downstream agents can read.',
    problemArea: 'concepts',
    spotlight: true,
  },
  {
    id: 'mcp-spec',
    type: 'spec',
    title: 'Model Context Protocol',
    authors: 'Anthropic',
    venue: 'modelcontextprotocol.io',
    year: 2024,
    url: 'https://modelcontextprotocol.io',
    usage: 'The protocol CoDRAG ships its primary interface on.',
    spotlightProse: 'MCP is the protocol surface CoDRAG ships its primary interface on. Every `codrag_*` tool, the resources system, and the per-client context budgets are MCP-shaped from the ground up. Without this spec there is no CoDRAG MCP server, and the page CoDRAG advertises to any agent in any IDE would not exist.',
    problemArea: 'concepts',
    spotlight: true,
  },
  {
    id: 'pdg-ferrante',
    type: 'paper',
    title: 'The Program Dependence Graph and its Use in Optimization',
    authors: 'Ferrante, Ottenstein, Warren',
    venue: 'ACM TOPLAS',
    year: 1987,
    url: 'https://dl.acm.org/doi/10.1145/24039.24041',
    usage: 'Classical PDG reference; grounds CoDRAG\u2019s combined control-flow + data-flow trace graph.',
    problemArea: 'concepts',
    spotlight: false,
  },
  {
    id: 'leiden',
    type: 'paper',
    title: 'From Louvain to Leiden: Guaranteeing Well-Connected Communities',
    authors: 'Traag, Waltman, van Eck',
    venue: 'Scientific Reports',
    year: 2019,
    url: 'https://www.nature.com/articles/s41598-019-41695-z',
    usage: 'Theoretical backing for community-detection-driven concept clustering.',
    problemArea: 'concepts',
    spotlight: false,
  },
  {
    id: 'formal-concept-analysis',
    type: 'book',
    title: 'Formal Concept Analysis: Mathematical Foundations',
    authors: 'Ganter & Wille',
    venue: 'Springer',
    year: 1999,
    url: 'https://link.springer.com/book/10.1007/978-3-642-59830-2',
    usage: 'Mathematical justification for lattice-based concept organization.',
    problemArea: 'concepts',
    spotlight: false,
  },
  {
    id: 'brooks-comprehension',
    type: 'paper',
    title: 'Towards a Theory of the Comprehension of Computer Programs',
    authors: 'Ruven Brooks',
    venue: 'IJMMS',
    year: 1983,
    url: 'https://www.sciencedirect.com/science/article/abs/pii/S0020737383800313',
    usage: 'Top-down program comprehension theory \u2014 the cognitive basis for hypothesis-driven retrieval.',
    problemArea: 'concepts',
    spotlight: false,
  },
  {
    id: 'pennington',
    type: 'paper',
    title: 'Stimulus Structures and Mental Representations in Expert Comprehension of Computer Programs',
    authors: 'Nancy Pennington',
    venue: 'Cognitive Psychology',
    year: 1987,
    url: 'https://www.sciencedirect.com/science/article/abs/pii/0010028587900076',
    usage: 'Bottom-up comprehension counterpart to Brooks; CoDRAG\u2019s structural trace index supports this mode.',
    problemArea: 'concepts',
    spotlight: false,
  },
  {
    id: 'millers-law',
    type: 'paper',
    title: 'The Magical Number Seven, Plus or Minus Two',
    authors: 'George A. Miller',
    venue: 'Psychological Review',
    year: 1956,
    url: 'https://psychclassics.yorku.ca/Miller/',
    usage: 'Cognitive-load rationale for concept clustering at human-readable cardinality.',
    problemArea: 'concepts',
    spotlight: false,
  },
  {
    id: 'nygard-adrs',
    type: 'blog',
    title: 'Documenting Architecture Decisions',
    authors: 'Michael Nygard',
    venue: 'cognitect.com',
    year: 2011,
    url: 'https://www.cognitect.com/blog/2011/11/15/documenting-architecture-decisions',
    usage: 'ADR template convention; CoDRAG concepts extend ADRs beyond per-node decisions.',
    problemArea: 'concepts',
    spotlight: false,
  },
  {
    id: 'karma',
    type: 'paper',
    title: 'KARMA: Multi-Agent Knowledge Graph Enrichment and Verification',
    venue: 'NeurIPS 2025',
    year: 2025,
    url: 'https://arxiv.org/abs/2410.04085',
    arxivId: '2410.04085',
    usage: 'Multi-agent KG enrichment that parallels CoDRAG\u2019s multi-pass enrichment pipeline.',
    problemArea: 'concepts',
    spotlight: false,
  },
  {
    id: 'llms4ol',
    type: 'paper',
    title: 'LLMs4OL Challenge \u2014 Large Language Models for Ontology Learning',
    venue: 'ISWC',
    year: 2024,
    url: 'https://sites.google.com/view/llms4ol',
    usage: 'Establishes SOTA for automated concept extraction; informed CoDRAG\u2019s hybrid embedding+LLM concept-discovery pipeline.',
    problemArea: 'concepts',
    spotlight: false,
  },
  {
    id: 'tracebert',
    type: 'paper',
    title: 'Traceability Transformed: Generating More Accurate Links with Pre-Trained BERT Models (TraceBERT)',
    venue: 'arXiv 2021',
    year: 2021,
    url: 'https://arxiv.org/abs/2102.04411',
    arxivId: '2102.04411',
    usage: 'Researched for requirements\u2194code linking; rejected as too heavy for the CoDRAG architecture but kept as a baseline.',
    problemArea: 'concepts',
    spotlight: false,
  },
  {
    id: 'nasa-swe-072',
    type: 'spec',
    title: 'NASA SWE-072: Bidirectional Traceability',
    venue: 'NASA SWE Handbook',
    url: 'https://swehb.nasa.gov/display/SWEHBVB/SWE-072+-+Bidirectional+Traceability',
    usage: 'Grounds CoDRAG\u2019s curated traceability framework in an established engineering standard.',
    problemArea: 'concepts',
    spotlight: false,
  },
  {
    id: 'acp-spec',
    type: 'spec',
    title: 'Agent Client Protocol (ACP)',
    venue: 'agentclientprotocol.com',
    url: 'https://agentclientprotocol.com',
    usage: 'Zed-backed standard \u2014 CoDRAG\u2019s multi-editor integration target.',
    problemArea: 'concepts',
    spotlight: false,
  },
  {
    id: 'a2a-spec',
    type: 'spec',
    title: 'Agent-to-Agent Protocol (A2A)',
    authors: 'Google / Linux Foundation',
    venue: 'a2a-protocol.org',
    year: 2025,
    url: 'https://a2a-protocol.org',
    usage: 'Identified as a future Layer 4 target for cross-agent discovery.',
    problemArea: 'concepts',
    spotlight: false,
  },
  {
    id: 'sarif-spec',
    type: 'spec',
    title: 'SARIF 2.1.0 \u2014 Static Analysis Results Interchange Format',
    venue: 'OASIS',
    year: 2020,
    url: 'https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-v2.1.0.html',
    usage: 'SARIF-in / SARIF-out enrichment is a shipped `codrag_audit` capability.',
    problemArea: 'concepts',
    spotlight: false,
  },
  {
    id: 'ocsf-spec',
    type: 'spec',
    title: 'OCSF \u2014 Open Cybersecurity Schema Framework',
    venue: 'ocsf.io',
    url: 'https://ocsf.io',
    usage: 'Alternative audit-export format; AWS/Splunk-backed.',
    problemArea: 'concepts',
    spotlight: false,
  },
  {
    id: 'agents-md',
    type: 'spec',
    title: 'agents.md',
    venue: 'agents.md',
    url: 'https://agents.md/',
    usage: 'Emerging convention for agent-facing context files \u2014 CoDRAG auto-generates AGENTS.md via `rules_generator.py`.',
    problemArea: 'concepts',
    spotlight: false,
  },
```

- [ ] **Step 2: Typecheck**

Run: `cd packages/ui && npm run typecheck`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add packages/ui/src/data/researchSources.ts
git commit -m "feat(research): add Section 4 sources (concepts, knowledge & standards)"
```

---

## Phase 2 — Components in Storybook

### Task 6: Build SourceCard component

**Files:**
- Create: `packages/ui/src/components/marketing/research/SourceCard.tsx`
- Create: `packages/ui/src/stories/marketing/research/SourceCard.stories.tsx`

- [ ] **Step 1: Create the component**

```tsx
// packages/ui/src/components/marketing/research/SourceCard.tsx
"use client";

import { ExternalLink } from 'lucide-react';
import { cn } from '../../../lib/utils';
import type { ResearchSource } from '../../../data/researchSources';

const TYPE_BADGES: Record<ResearchSource['type'], { label: string; cls: string }> = {
  paper: { label: 'Paper', cls: 'bg-primary/10 text-primary border-primary/30' },
  repo:  { label: 'Repo',  cls: 'bg-success/10 text-success border-success/30' },
  blog:  { label: 'Essay', cls: 'bg-warning/10 text-warning border-warning/30' },
  spec:  { label: 'Spec',  cls: 'bg-text/10 text-text border-border' },
  book:  { label: 'Book',  cls: 'bg-text-muted/10 text-text-muted border-border' },
};

export interface SourceCardProps {
  source: ResearchSource;
  className?: string;
}

export function SourceCard({ source, className }: SourceCardProps) {
  const badge = TYPE_BADGES[source.type];
  const citation = [source.authors, source.venue, source.year].filter(Boolean).join(' \u00b7 ');

  return (
    <a
      href={source.url}
      target="_blank"
      rel="noopener noreferrer"
      className={cn(
        'group flex flex-col rounded-lg border border-border bg-surface p-4 transition-all hover:border-primary/40 hover:shadow-md',
        className,
      )}
    >
      <div className="flex items-center justify-between mb-2">
        <span className={cn('text-[10px] font-mono font-semibold uppercase tracking-wider rounded-full px-2 py-0.5 border', badge.cls)}>
          {badge.label}
        </span>
        <ExternalLink className="w-3 h-3 text-text-muted opacity-0 group-hover:opacity-100 transition-opacity" />
      </div>
      <h4 className="text-sm font-semibold text-text leading-snug mb-1 group-hover:text-primary transition-colors">
        {source.title}
      </h4>
      {citation && <p className="text-xs text-text-muted mb-2">{citation}</p>}
      <p className="text-xs text-text-muted leading-relaxed mt-auto">{source.usage}</p>
      <span className="sr-only">(opens in new tab)</span>
    </a>
  );
}
```

- [ ] **Step 2: Create the story file using real data**

```tsx
// packages/ui/src/stories/marketing/research/SourceCard.stories.tsx
import type { Meta, StoryObj } from '@storybook/react';
import { SourceCard } from '../../../components/marketing/research/SourceCard';
import { RESEARCH_SOURCES } from '../../../data/researchSources';

const meta: Meta<typeof SourceCard> = {
  title: 'Website/Marketing/Research/SourceCard',
  component: SourceCard,
  parameters: { layout: 'centered' },
  tags: ['autodocs'],
  decorators: [
    (Story) => (
      <div style={{ width: 320 }}>
        <Story />
      </div>
    ),
  ],
};

export default meta;
type Story = StoryObj<typeof SourceCard>;

const findById = (id: string) => {
  const s = RESEARCH_SOURCES.find((x) => x.id === id);
  if (!s) throw new Error(`Story fixture missing source "${id}"`);
  return s;
};

export const Paper: Story = { args: { source: findById('lost-in-the-middle') } };
export const Repo: Story = { args: { source: findById('aider') } };
export const Essay: Story = { args: { source: findById('anthropic-contextual-retrieval') } };
export const Spec: Story = { args: { source: findById('mcp-spec') } };
export const Book: Story = { args: { source: findById('seci-model') } };
```

- [ ] **Step 3: Typecheck**

Run: `cd packages/ui && npm run typecheck`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add packages/ui/src/components/marketing/research/SourceCard.tsx \
        packages/ui/src/stories/marketing/research/SourceCard.stories.tsx
git commit -m "feat(research): add SourceCard component and story"
```

---

### Task 7: Build SourceSpotlight component

**Files:**
- Create: `packages/ui/src/components/marketing/research/SourceSpotlight.tsx`
- Create: `packages/ui/src/stories/marketing/research/SourceSpotlight.stories.tsx`

- [ ] **Step 1: Create the component**

```tsx
// packages/ui/src/components/marketing/research/SourceSpotlight.tsx
"use client";

import { ExternalLink } from 'lucide-react';
import { cn } from '../../../lib/utils';
import type { ResearchSource } from '../../../data/researchSources';

const TYPE_LABELS: Record<ResearchSource['type'], string> = {
  paper: 'Paper',
  repo:  'Repository',
  blog:  'Essay',
  spec:  'Specification',
  book:  'Book',
};

export interface SourceSpotlightProps {
  source: ResearchSource;
  className?: string;
}

export function SourceSpotlight({ source, className }: SourceSpotlightProps) {
  const citation = [source.authors, source.venue, source.year].filter(Boolean).join(' \u00b7 ');

  return (
    <article
      className={cn(
        'rounded-2xl border border-border bg-surface-raised p-6 sm:p-8 transition-shadow hover:shadow-lg',
        className,
      )}
    >
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 mb-3">
        <span className="text-[11px] font-mono font-semibold uppercase tracking-widest text-primary">
          {TYPE_LABELS[source.type]}
        </span>
        {citation && <span className="text-xs text-text-muted">{citation}</span>}
      </div>
      <h3 className="text-xl sm:text-2xl font-semibold text-text mb-3 leading-snug tracking-tight">
        <a
          href={source.url}
          target="_blank"
          rel="noopener noreferrer"
          className="hover:text-primary transition-colors inline-flex items-baseline gap-2"
        >
          {source.title}
          <ExternalLink className="w-4 h-4 self-center" />
          <span className="sr-only">(opens in new tab)</span>
        </a>
      </h3>
      <p className="text-text-muted leading-relaxed text-base">
        {source.spotlightProse}
      </p>
    </article>
  );
}
```

- [ ] **Step 2: Create the story**

```tsx
// packages/ui/src/stories/marketing/research/SourceSpotlight.stories.tsx
import type { Meta, StoryObj } from '@storybook/react';
import { SourceSpotlight } from '../../../components/marketing/research/SourceSpotlight';
import { RESEARCH_SOURCES } from '../../../data/researchSources';

const meta: Meta<typeof SourceSpotlight> = {
  title: 'Website/Marketing/Research/SourceSpotlight',
  component: SourceSpotlight,
  parameters: { layout: 'padded' },
  tags: ['autodocs'],
  decorators: [
    (Story) => (
      <div style={{ maxWidth: 640 }}>
        <Story />
      </div>
    ),
  ],
};

export default meta;
type Story = StoryObj<typeof SourceSpotlight>;

const findById = (id: string) => {
  const s = RESEARCH_SOURCES.find((x) => x.id === id);
  if (!s) throw new Error(`Story fixture missing source "${id}"`);
  return s;
};

export const Paper: Story = { args: { source: findById('lost-in-the-middle') } };
export const Repository: Story = { args: { source: findById('gbrain') } };
export const Essay: Story = { args: { source: findById('anthropic-contextual-retrieval') } };
export const Specification: Story = { args: { source: findById('mcp-spec') } };
export const Book: Story = { args: { source: findById('seci-model') } };
```

- [ ] **Step 3: Typecheck**

Run: `cd packages/ui && npm run typecheck`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add packages/ui/src/components/marketing/research/SourceSpotlight.tsx \
        packages/ui/src/stories/marketing/research/SourceSpotlight.stories.tsx
git commit -m "feat(research): add SourceSpotlight component and story"
```

---

### Task 8: Build ResearchHero component

**Files:**
- Create: `packages/ui/src/components/marketing/research/ResearchHero.tsx`
- Create: `packages/ui/src/stories/marketing/research/ResearchHero.stories.tsx`

- [ ] **Step 1: Create the component**

```tsx
// packages/ui/src/components/marketing/research/ResearchHero.tsx
import { cn } from '../../../lib/utils';

export interface ResearchHeroProps {
  className?: string;
}

/**
 * Editorial hero rendered inside DetailPageLayout's main content column.
 * The page-level h1 lives in DetailPageLayout's sidebar, so this hero uses h2.
 */
export function ResearchHero({ className }: ResearchHeroProps) {
  return (
    <header className={cn('text-center max-w-3xl mx-auto pb-10 sm:pb-14 border-b border-border', className)}>
      <p className="text-[11px] font-mono font-semibold uppercase tracking-[0.2em] text-primary mb-4">
        Bibliography
      </p>
      <h2 className="text-4xl sm:text-5xl font-semibold text-text leading-tight tracking-tight mb-6">
        What CoDRAG was built on.
      </h2>
      <p className="text-lg text-text-muted leading-relaxed">
        A working list of the papers, repositories, essays, and standards CoDRAG draws on. Each entry includes a one-line note on how it shaped the project &mdash; and what we changed when we needed better suit our goals.
      </p>
    </header>
  );
}
```

- [ ] **Step 2: Create the story**

```tsx
// packages/ui/src/stories/marketing/research/ResearchHero.stories.tsx
import type { Meta, StoryObj } from '@storybook/react';
import { ResearchHero } from '../../../components/marketing/research/ResearchHero';

const meta: Meta<typeof ResearchHero> = {
  title: 'Website/Marketing/Research/ResearchHero',
  component: ResearchHero,
  parameters: { layout: 'padded' },
  tags: ['autodocs'],
};

export default meta;
type Story = StoryObj<typeof ResearchHero>;

export const Default: Story = {};
```

- [ ] **Step 3: Typecheck**

Run: `cd packages/ui && npm run typecheck`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add packages/ui/src/components/marketing/research/ResearchHero.tsx \
        packages/ui/src/stories/marketing/research/ResearchHero.stories.tsx
git commit -m "feat(research): add ResearchHero component and story"
```

---

### Task 9: Build SourceFilterChips component

**Files:**
- Create: `packages/ui/src/components/marketing/research/SourceFilterChips.tsx`
- Create: `packages/ui/src/stories/marketing/research/SourceFilterChips.stories.tsx`

- [ ] **Step 1: Create the component**

```tsx
// packages/ui/src/components/marketing/research/SourceFilterChips.tsx
"use client";

import { cn } from '../../../lib/utils';
import type { SourceType } from '../../../data/researchSources';

export type FilterValue = 'all' | SourceType;

const FILTERS: { value: FilterValue; label: string }[] = [
  { value: 'all',   label: 'All' },
  { value: 'paper', label: 'Papers' },
  { value: 'repo',  label: 'Repos' },
  { value: 'blog',  label: 'Essays' },
  { value: 'spec',  label: 'Specs' },
  { value: 'book',  label: 'Books' },
];

export interface SourceFilterChipsProps {
  active: FilterValue;
  onChange: (value: FilterValue) => void;
  /** Set of types present in the section. Filters not in this set are hidden. */
  available: Set<SourceType>;
  className?: string;
}

export function SourceFilterChips({ active, onChange, available, className }: SourceFilterChipsProps) {
  return (
    <div role="tablist" aria-label="Filter sources by type" className={cn('flex flex-wrap gap-2', className)}>
      {FILTERS.filter((f) => f.value === 'all' || available.has(f.value as SourceType)).map((f) => {
        const isActive = active === f.value;
        return (
          <button
            key={f.value}
            type="button"
            role="tab"
            aria-pressed={isActive}
            onClick={() => onChange(f.value)}
            className={cn(
              'text-xs font-medium px-3 py-1.5 rounded-full border transition-colors',
              isActive
                ? 'bg-primary text-white border-primary'
                : 'bg-surface text-text-muted border-border hover:border-primary/40 hover:text-text',
            )}
          >
            {f.label}
          </button>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 2: Create the story**

```tsx
// packages/ui/src/stories/marketing/research/SourceFilterChips.stories.tsx
import { useState } from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import {
  SourceFilterChips,
  type FilterValue,
} from '../../../components/marketing/research/SourceFilterChips';
import type { SourceType } from '../../../data/researchSources';

const meta: Meta<typeof SourceFilterChips> = {
  title: 'Website/Marketing/Research/SourceFilterChips',
  component: SourceFilterChips,
  parameters: { layout: 'centered' },
  tags: ['autodocs'],
};

export default meta;
type Story = StoryObj<typeof SourceFilterChips>;

const allTypes = new Set<SourceType>(['paper', 'repo', 'blog', 'spec', 'book']);
const someTypes = new Set<SourceType>(['paper', 'repo']);

const Interactive = ({ available }: { available: Set<SourceType> }) => {
  const [active, setActive] = useState<FilterValue>('all');
  return <SourceFilterChips active={active} onChange={setActive} available={available} />;
};

export const AllTypes: Story = {
  render: () => <Interactive available={allTypes} />,
};

export const PartialAvailability: Story = {
  render: () => <Interactive available={someTypes} />,
};

export const PaperActive: Story = {
  args: { active: 'paper', onChange: () => {}, available: allTypes },
};
```

- [ ] **Step 3: Typecheck**

Run: `cd packages/ui && npm run typecheck`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add packages/ui/src/components/marketing/research/SourceFilterChips.tsx \
        packages/ui/src/stories/marketing/research/SourceFilterChips.stories.tsx
git commit -m "feat(research): add SourceFilterChips component and story"
```

---

### Task 10: Build ResearchAppendix component

**Files:**
- Create: `packages/ui/src/components/marketing/research/ResearchAppendix.tsx`
- Create: `packages/ui/src/stories/marketing/research/ResearchAppendix.stories.tsx`

- [ ] **Step 1: Create the component**

```tsx
// packages/ui/src/components/marketing/research/ResearchAppendix.tsx
"use client";

import { useMemo, useState } from 'react';
import { cn } from '../../../lib/utils';
import type { ResearchSource, SourceType } from '../../../data/researchSources';
import { SourceCard } from './SourceCard';
import { SourceFilterChips, type FilterValue } from './SourceFilterChips';

export interface ResearchAppendixProps {
  /** Heading shown above the chips */
  title?: string;
  sources: ResearchSource[];
  className?: string;
}

export function ResearchAppendix({
  title = 'Further reading',
  sources,
  className,
}: ResearchAppendixProps) {
  const [filter, setFilter] = useState<FilterValue>('all');

  const available = useMemo<Set<SourceType>>(
    () => new Set(sources.map((s) => s.type)),
    [sources],
  );

  const filtered = useMemo(
    () => (filter === 'all' ? sources : sources.filter((s) => s.type === filter)),
    [filter, sources],
  );

  if (sources.length === 0) return null;

  return (
    <div className={cn('mt-12', className)}>
      <div className="flex flex-wrap items-center justify-between gap-4 mb-5">
        <h4 className="text-xs font-mono font-semibold text-text uppercase tracking-widest">
          {title}
        </h4>
        <SourceFilterChips active={filter} onChange={setFilter} available={available} />
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {filtered.map((source) => (
          <SourceCard key={source.id} source={source} />
        ))}
      </div>
      {filtered.length === 0 && (
        <p className="text-sm text-text-muted italic mt-4">
          No sources of this type in this section.
        </p>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Create the story**

```tsx
// packages/ui/src/stories/marketing/research/ResearchAppendix.stories.tsx
import type { Meta, StoryObj } from '@storybook/react';
import { ResearchAppendix } from '../../../components/marketing/research/ResearchAppendix';
import { RESEARCH_SOURCES } from '../../../data/researchSources';

const meta: Meta<typeof ResearchAppendix> = {
  title: 'Website/Marketing/Research/ResearchAppendix',
  component: ResearchAppendix,
  parameters: { layout: 'padded' },
  tags: ['autodocs'],
};

export default meta;
type Story = StoryObj<typeof ResearchAppendix>;

const retrievalAppendix = RESEARCH_SOURCES.filter(
  (s) => s.problemArea === 'retrieval' && !s.spotlight,
);
const conceptsAppendix = RESEARCH_SOURCES.filter(
  (s) => s.problemArea === 'concepts' && !s.spotlight,
);

export const Retrieval: Story = {
  args: { sources: retrievalAppendix },
};

export const Concepts: Story = {
  args: { sources: conceptsAppendix },
};

export const Empty: Story = {
  args: { sources: [] },
};
```

- [ ] **Step 3: Typecheck**

Run: `cd packages/ui && npm run typecheck`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add packages/ui/src/components/marketing/research/ResearchAppendix.tsx \
        packages/ui/src/stories/marketing/research/ResearchAppendix.stories.tsx
git commit -m "feat(research): add ResearchAppendix component and story"
```

---

### Task 11: Build ResearchSection component + barrel exports

**Files:**
- Create: `packages/ui/src/components/marketing/research/ResearchSection.tsx`
- Create: `packages/ui/src/components/marketing/research/index.ts`
- Create: `packages/ui/src/stories/marketing/research/ResearchSection.stories.tsx`
- Modify: `packages/ui/src/components/marketing/index.ts`
- Modify: `packages/ui/src/index.ts`

- [ ] **Step 1: Create ResearchSection**

```tsx
// packages/ui/src/components/marketing/research/ResearchSection.tsx
"use client";

import { cn } from '../../../lib/utils';
import type { ResearchSource } from '../../../data/researchSources';
import { SourceSpotlight } from './SourceSpotlight';
import { ResearchAppendix } from './ResearchAppendix';

export interface ResearchSectionProps {
  /** Anchor id used by the sidebar TOC */
  id: string;
  title: string;
  intro: string;
  sources: ResearchSource[];
  className?: string;
}

export function ResearchSection({
  id,
  title,
  intro,
  sources,
  className,
}: ResearchSectionProps) {
  const spotlights = sources.filter((s) => s.spotlight);
  const appendix = sources.filter((s) => !s.spotlight);

  return (
    <section
      id={id}
      className={cn(
        'scroll-mt-24 py-12 first:pt-0 border-b border-border last:border-b-0',
        className,
      )}
    >
      <h3 className="text-2xl sm:text-3xl font-semibold text-text mb-3 tracking-tight">
        {title}
      </h3>
      <p className="text-text-muted leading-relaxed max-w-3xl mb-8">{intro}</p>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {spotlights.map((source) => (
          <SourceSpotlight key={source.id} source={source} />
        ))}
      </div>
      <ResearchAppendix sources={appendix} />
    </section>
  );
}
```

- [ ] **Step 2: Create the research barrel export**

```ts
// packages/ui/src/components/marketing/research/index.ts
export { SourceCard, type SourceCardProps } from './SourceCard';
export { SourceSpotlight, type SourceSpotlightProps } from './SourceSpotlight';
export { ResearchHero, type ResearchHeroProps } from './ResearchHero';
export {
  SourceFilterChips,
  type SourceFilterChipsProps,
  type FilterValue,
} from './SourceFilterChips';
export { ResearchAppendix, type ResearchAppendixProps } from './ResearchAppendix';
export { ResearchSection, type ResearchSectionProps } from './ResearchSection';
```

- [ ] **Step 3: Re-export from the marketing barrel**

Open `packages/ui/src/components/marketing/index.ts`. After the existing 7 lines, append:

```ts
export {
  SourceCard,
  SourceSpotlight,
  ResearchHero,
  SourceFilterChips,
  ResearchAppendix,
  ResearchSection,
} from './research';
export type {
  SourceCardProps,
  SourceSpotlightProps,
  ResearchHeroProps,
  SourceFilterChipsProps,
  FilterValue,
  ResearchAppendixProps,
  ResearchSectionProps,
} from './research';
```

- [ ] **Step 4: Re-export from the package root**

Open `packages/ui/src/index.ts`. Find line 168:

```ts
export { MarketingHero, FeatureBlocks, codragFeatures, marketingFeatures, TierComparison, tierComparisonFeatures, TechStackMatrix, techStackComponents, CompetitorMatrix, DetailPageLayout } from './components/marketing';
```

Replace with:

```ts
export { MarketingHero, FeatureBlocks, codragFeatures, marketingFeatures, TierComparison, tierComparisonFeatures, TechStackMatrix, techStackComponents, CompetitorMatrix, DetailPageLayout, SourceCard, SourceSpotlight, ResearchHero, SourceFilterChips, ResearchAppendix, ResearchSection } from './components/marketing';
```

Then find line 169 (the type re-export immediately below) and replace with:

```ts
export type { MarketingHeroProps, FeatureBlocksProps, Feature, TierComparisonProps, TierFeature, TechStackMatrixProps, StackComponent, CompetitorMatrixProps, DetailPageLayoutProps, DetailPageSection, SourceCardProps, SourceSpotlightProps, ResearchHeroProps, SourceFilterChipsProps, FilterValue, ResearchAppendixProps, ResearchSectionProps } from './components/marketing';
```

Then add a new line directly below those, exporting the data module:

```ts
export { RESEARCH_SOURCES, validateResearchSources } from './data/researchSources';
export type { ResearchSource, SourceType, ProblemArea } from './data/researchSources';
```

- [ ] **Step 5: Create the section story**

```tsx
// packages/ui/src/stories/marketing/research/ResearchSection.stories.tsx
import type { Meta, StoryObj } from '@storybook/react';
import { ResearchSection } from '../../../components/marketing/research/ResearchSection';
import { RESEARCH_SOURCES } from '../../../data/researchSources';

const meta: Meta<typeof ResearchSection> = {
  title: 'Website/Marketing/Research/ResearchSection',
  component: ResearchSection,
  parameters: { layout: 'padded' },
  tags: ['autodocs'],
};

export default meta;
type Story = StoryObj<typeof ResearchSection>;

export const Retrieval: Story = {
  args: {
    id: 'retrieval',
    title: 'Retrieval & Long Context',
    intro:
      'Why context engineering matters more than raw context size — and what changes when language models meet long, noisy windows.',
    sources: RESEARCH_SOURCES.filter((s) => s.problemArea === 'retrieval'),
  },
};

export const Compression: Story = {
  args: {
    id: 'compression',
    title: 'Compression & Levels of Detail',
    intro:
      'Why CoDRAG\u2019s context assembler ladders code from full source down to one-line signatures.',
    sources: RESEARCH_SOURCES.filter((s) => s.problemArea === 'compression'),
  },
};

export const Concepts: Story = {
  args: {
    id: 'concepts',
    title: 'Concepts, Knowledge & Standards',
    intro:
      'Why CoDRAG treats concepts as first-class artifacts and where the protocol surface comes from.',
    sources: RESEARCH_SOURCES.filter((s) => s.problemArea === 'concepts'),
  },
};
```

- [ ] **Step 6: Typecheck the package**

Run: `cd packages/ui && npm run typecheck`
Expected: no errors.

- [ ] **Step 7: Boot Storybook and visually smoke-test**

Run: `cd packages/ui && npm run storybook`
Expected: Storybook starts on port 6006. Navigate to `Website / Marketing / Research` and visually verify each story renders without React errors. Look for: badges visible on cards, citation lines correct, links open in new tabs, filter chips toggle.

If anything looks broken, fix it before committing. Stop the storybook process with Ctrl+C.

- [ ] **Step 8: Commit**

```bash
git add packages/ui/src/components/marketing/research/ \
        packages/ui/src/stories/marketing/research/ \
        packages/ui/src/components/marketing/index.ts \
        packages/ui/src/index.ts
git commit -m "feat(research): add ResearchSection and wire research barrel exports"
```

**Phase 2 review checkpoint:** All six components and seven stories exist. Pause here, browse Storybook, and tell the implementer if any visual treatment needs revision before composing the page.

---

## Phase 3 — Page Composition

### Task 12: Compose the marketing page

**Files:**
- Create: `websites/apps/marketing/src/app/research/page.tsx`
- Create: `websites/apps/marketing/src/app/research/layout.tsx`

- [ ] **Step 1: Create the route layout with metadata**

```tsx
// websites/apps/marketing/src/app/research/layout.tsx
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Research \u2014 CoDRAG',
  description:
    'A bibliography of the papers, repositories, essays, and standards CoDRAG was built on, with notes on how each one was used.',
  openGraph: {
    title: 'Research \u2014 CoDRAG',
    description:
      'A bibliography of the papers, repositories, essays, and standards CoDRAG was built on.',
    type: 'website',
  },
};

export default function ResearchLayout({ children }: { children: React.ReactNode }) {
  return children;
}
```

- [ ] **Step 2: Create the page**

```tsx
// websites/apps/marketing/src/app/research/page.tsx
"use client";

import {
  DetailPageLayout,
  ResearchHero,
  ResearchSection,
  RESEARCH_SOURCES,
} from '@prep/ui';

const SECTIONS = [
  { id: 'retrieval',   label: 'Retrieval & Long Context' },
  { id: 'compression', label: 'Compression & LOD' },
  { id: 'chunking',    label: 'Code Structure & Chunking' },
  { id: 'concepts',    label: 'Concepts, Knowledge & Standards' },
];

const INTROS = {
  retrieval:
    'Why context engineering matters more than raw context size \u2014 and what changes when language models meet long, noisy windows.',
  compression:
    'Why CoDRAG\u2019s context assembler ladders code from full source down to one-line signatures, and the research that makes signature-only context defensible.',
  chunking:
    'Why chunking on AST boundaries beats character splits for code, and how structural awareness changes retrieval quality.',
  concepts:
    'Why CoDRAG treats concepts as first-class artifacts, where the protocol surface comes from, and the older work that grounds the system in something deeper than recent papers.',
};

export default function ResearchPage() {
  const byArea = (area: 'retrieval' | 'compression' | 'chunking' | 'concepts') =>
    RESEARCH_SOURCES.filter((s) => s.problemArea === area);

  return (
    <DetailPageLayout
      title="Research"
      subtitle="Bibliography"
      description="What CoDRAG was built on. Notes on the papers, repositories, essays, and standards that shaped the project."
      sections={SECTIONS}
      docsUrl="https://docs.codrag.io"
      docsLabel="Read the docs"
    >
      <ResearchHero />

      <ResearchSection
        id="retrieval"
        title="Retrieval & Long Context"
        intro={INTROS.retrieval}
        sources={byArea('retrieval')}
      />
      <ResearchSection
        id="compression"
        title="Compression & Levels of Detail"
        intro={INTROS.compression}
        sources={byArea('compression')}
      />
      <ResearchSection
        id="chunking"
        title="Code Structure & Chunking"
        intro={INTROS.chunking}
        sources={byArea('chunking')}
      />
      <ResearchSection
        id="concepts"
        title="Concepts, Knowledge & Standards"
        intro={INTROS.concepts}
        sources={byArea('concepts')}
      />

      <footer className="pt-10 text-sm text-text-muted leading-relaxed border-t border-border max-w-3xl">
        This list is incomplete. We add to it as we read, and we welcome
        corrections &mdash; if we&rsquo;ve cited your work badly, or missed work we
        should know about, open an issue on{' '}
        <a
          href="https://github.com/MagneticAnomaly/CoDRAG-MCP/issues"
          className="text-primary hover:underline"
          target="_blank"
          rel="noopener noreferrer"
        >
          the repo
        </a>
        . We&rsquo;ll fix it.
      </footer>
    </DetailPageLayout>
  );
}
```

- [ ] **Step 3: Typecheck the marketing app**

Run: `cd websites/apps/marketing && npm run typecheck`
Expected: no errors.

- [ ] **Step 4: Run the dev server and walk the page**

Run: `cd websites/apps/marketing && npm run dev`
Expected: Next.js starts on port 3000. Open `http://localhost:3000/research`.

Verify in the browser:
1. Sidebar shows "Bibliography / Research / description" + 4-section TOC
2. Main content opens with the centered ResearchHero
3. Four sections render in order, each with spotlights on top and an appendix grid below
4. Filter chips on each appendix toggle visibility (try clicking "Papers" then "All")
5. Clicking a sidebar TOC link smooth-scrolls to the right section
6. External links open in a new tab
7. No console errors

Stop the dev server with Ctrl+C when done.

- [ ] **Step 5: Commit**

```bash
git add websites/apps/marketing/src/app/research/
git commit -m "feat(research): compose /research marketing page"
```

**Phase 3 review checkpoint:** The page renders end-to-end. Pause here, walk it in the browser, and tell the implementer about copy/cut/visual revisions before the cross-linking phase.

---

## Phase 4 — Cross-Linking & SEO

### Task 13: Add footer link and sitemap entry

**Files:**
- Modify: `websites/apps/marketing/src/app/ClientLayout.tsx:21-38`
- Modify: `websites/apps/marketing/src/app/sitemap.ts`

- [ ] **Step 1: Add Research link to the footer Company column**

Open `websites/apps/marketing/src/app/ClientLayout.tsx`. Find the `footerSections` array (around line 21):

```ts
const footerSections = [
  {
    title: 'Product',
    links: [
      { label: 'Download', href: '/download' },
      { label: 'Pricing', href: '/pricing' },
      { label: 'Changelog', href: '/changelog' },
      { label: 'Documentation', href: DOCS_URL },
    ],
  },
  {
    title: 'Company',
    links: [
      { label: 'FAQ', href: '/faq' },
      { label: 'Support', href: SUPPORT_URL },
    ],
  },
];
```

Change the Company column to:

```ts
  {
    title: 'Company',
    links: [
      { label: 'FAQ', href: '/faq' },
      { label: 'Research', href: '/research' },
      { label: 'Support', href: SUPPORT_URL },
    ],
  },
```

- [ ] **Step 2: Add /research to the sitemap**

Open `websites/apps/marketing/src/app/sitemap.ts`. Inside the `routes` array, add `'/research'` after `'/blog'`:

```ts
  const routes = [
    '',
    '/download',
    '/setup',
    '/pricing',
    '/faq',
    '/security',
    '/contact',
    '/careers',
    '/changelog',
    '/blog',
    '/research',
    '/privacy',
    '/terms',
  ].map((route) => ({
```

- [ ] **Step 3: Typecheck**

Run: `cd websites/apps/marketing && npm run typecheck`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add websites/apps/marketing/src/app/ClientLayout.tsx \
        websites/apps/marketing/src/app/sitemap.ts
git commit -m "feat(research): wire /research into footer and sitemap"
```

---

### Task 14: Add cross-link callouts to /about and /compare

**Files:**
- Modify: `websites/apps/marketing/src/app/about/page.tsx`
- Modify: `websites/apps/marketing/src/app/compare/page.tsx`

- [ ] **Step 1: Add the callout to /about**

Open `websites/apps/marketing/src/app/about/page.tsx`. Find the closing `</section>` of the "Our Mission" block (around line 41 — the `</section>` that closes `<section className="space-y-6 mb-16">`).

Immediately AFTER that closing `</section>`, insert:

```tsx
            {/* Research callout */}
            <aside className="mb-16 rounded-2xl border border-border bg-surface p-6">
              <p className="text-[11px] font-mono font-semibold uppercase tracking-widest text-primary mb-2">
                Bibliography
              </p>
              <p className="text-text-muted leading-relaxed mb-3">
                CoDRAG draws on a long list of papers, repositories, and standards. We keep the working list public.
              </p>
              <a
                href="/research"
                className="inline-flex items-center gap-2 text-sm font-medium text-primary hover:underline"
              >
                Read the research CoDRAG was built on \u2192
              </a>
            </aside>
```

(Replace the `\u2192` with a literal `→` arrow when typing.)

- [ ] **Step 2: Add the callout to /compare**

Open `websites/apps/marketing/src/app/compare/page.tsx`. Find the line with `<CompetitorMatrix mobileVariant="detailed" />` (around line 26). Immediately AFTER that line, insert:

```tsx
        <aside className="mt-16 rounded-2xl border border-border bg-surface p-6 max-w-3xl mx-auto text-center">
          <p className="text-[11px] font-mono font-semibold uppercase tracking-widest text-primary mb-2">
            Bibliography
          </p>
          <p className="text-text-muted leading-relaxed mb-3">
            We&rsquo;ve actually read the papers and source for every tool on this page. Here&rsquo;s the working list.
          </p>
          <a
            href="/research"
            className="inline-flex items-center gap-2 text-sm font-medium text-primary hover:underline"
          >
            See our research \u2192
          </a>
        </aside>
```

(Replace `\u2192` with `→`.)

- [ ] **Step 3: Typecheck**

Run: `cd websites/apps/marketing && npm run typecheck`
Expected: no errors.

- [ ] **Step 4: Visually verify both pages**

Run: `cd websites/apps/marketing && npm run dev`
Visit `http://localhost:3000/about` and `http://localhost:3000/compare`. Confirm both callouts render and the link goes to `/research`. Stop the dev server.

- [ ] **Step 5: Commit**

```bash
git add websites/apps/marketing/src/app/about/page.tsx \
        websites/apps/marketing/src/app/compare/page.tsx
git commit -m "feat(research): add /research callouts on /about and /compare"
```

---

## Phase 5 — Final QA

### Task 15: Lint, typecheck, build, manual walkthrough

**Files:** none modified unless fixes are needed.

- [ ] **Step 1: Lint the whole workspace**

Run from repo root: `npm run lint`
Expected: 0 new errors. If new errors come from the research files, fix them before continuing.

- [ ] **Step 2: Typecheck the whole workspace**

Run from repo root: `npm run typecheck`
Expected: 0 new errors. Fix any introduced by the research changes.

- [ ] **Step 3: Build the marketing app**

Run: `cd websites/apps/marketing && npm run build`
Expected: build succeeds. Confirm the build log lists `/research` as a generated route.

- [ ] **Step 4: Boot Storybook and walk every research story**

Run: `cd packages/ui && npm run storybook`
Expected: every story under `Website / Marketing / Research` renders without console errors. Spot-check spotlights, cards, filter chips toggling, and the full ResearchSection variants. Stop with Ctrl+C.

- [ ] **Step 5: Boot the marketing app and walk the page end to end**

Run: `cd websites/apps/marketing && npm run dev`

Check:
1. `/research` renders, all 4 sections present, ~12 spotlights and ~44 appendix entries visible
2. Sidebar TOC sticks on scroll, anchor links work
3. Filter chips toggle correctly within each section
4. External links open new tabs
5. Footer "Research" link works from any other page
6. `/about` and `/compare` callouts work
7. Lighthouse a11y score \u2265 95 (run Chrome DevTools \u2192 Lighthouse \u2192 Accessibility on `/research`)
8. No browser console errors anywhere

Stop the dev server.

- [ ] **Step 6: Final commit if any fixes were needed**

If steps 1\u20135 surfaced fixes, commit them:

```bash
git add -A
git commit -m "fix(research): address QA findings"
```

Otherwise skip this step.

- [ ] **Step 7: Hand back to Eric for review**

Report:
- Final route URL: `http://localhost:3000/research`
- Storybook URL: `http://localhost:6006/?path=/story/website-marketing-research-researchsection--retrieval`
- Section / spotlight / appendix counts
- Lighthouse a11y score
- Any deviations from the spec
- Any open follow-ups

---

## Self-Review Notes (filled in by plan author)

**Spec coverage check:**

| Spec section | Plan tasks |
|---|---|
| §1 Goal & audience | Implicit throughout; copy in hero + closing footer reflect A+B+D |
| §2 Placement & navigation | T13 (footer + sitemap), T14 (callouts) |
| §3 Reused components / new components | T6\u2013T11 |
| §4 Page architecture | T12 |
| §5 Information architecture (4 sections, ~12 spotlights) | T2\u2013T5 (data), T12 (composition) |
| §6 Copy & tone | Hero in T8, section intros in T12, closing footer in T12, spotlight prose in T2\u2013T5 |
| §7 Interactivity (filter chips, sticky TOC, anchors) | T9 (chips), T11 (section anchors), T12 (DetailPageLayout TOC) |
| §8 Storybook integration | Story file in every component task (T6\u2013T11) |
| §9 Data model | T1 (types/validator), T2\u2013T5 (entries), T11 (export) |
| §10 Responsive | Inherited from DetailPageLayout + Tailwind responsive classes already in components |
| §11 Accessibility | Aria-pressed in T9, sr-only labels in T6/T7, h-hierarchy in T8/T11/T12, Lighthouse check in T15 |
| §12 Build phases | This plan's Phase 1\u20135 |
| §14 Definition of done | T15 |

**Placeholder scan:** none. All code is concrete, all commands are exact.

**Type consistency:** `ResearchSource`, `SourceType`, `ProblemArea`, `FilterValue` are defined in T1 and consistently referenced in T6\u2013T11. `RESEARCH_SOURCES` is the single export consumed by stories and the page.

**Known known soft-spot:** a few arXiv IDs in §1\u2013§5 of the data encode post-2025 publication years (`2511.18659`, `2601.19929`, `2601.11564`, `2601.00376`). These are preserved verbatim from the master list per the spec\u2019s \u201ckeep citations as the docs present them\u201d rule. If link resolution fails during T15 spot-check, flag those entries as needing canonical-URL replacement before public publish.
