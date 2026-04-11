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
  /** Required editorial blurb (2–3 sentences recommended). Must be set when spotlight === true. */
  spotlightProse?: string;
  problemArea: ProblemArea;
  spotlight: boolean;
}

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
    spotlightProse: 'Han et al. compare flat-vector RAG against graph-augmented RAG across reasoning-heavy benchmarks and find that local community search wins on multi-hop questions. CoDRAG\u2019s codrag_search follows the same logic: vector hits seed the query, then a trace-graph hop expands the neighborhood before the final assembly.',
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
    id: 'rag-survey',
    type: 'paper',
    title: 'Retrieval-Augmented Code Generation: A Survey',
    venue: 'arXiv 2025',
    year: 2025,
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
  // ─── Section 2: Compression & Levels of Detail ────────────────────────
  {
    id: 'stingy-context',
    type: 'paper',
    title: 'Stingy Context: 18:1 Hierarchical Code Compression for LLM Auto-Coding',
    authors: 'Ostby',
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
    authors: 'Liang et al.',
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
    authors: 'Liu et al.',
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
    authors: 'Guo et al.',
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
    id: 'clara-paper',
    type: 'paper',
    title: 'CLaRa: Bridging Retrieval and Generation with Continuous Latent Reasoning',
    venue: 'arXiv 2025',
    year: 2025,
    url: 'https://arxiv.org/abs/2511.18659',
    arxivId: '2511.18659',
    usage: 'Evaluated as a baseline; code/language retention measured at 20\u201329%, motivating CoDRAG\u2019s dual-compressor design.',
    problemArea: 'compression',
    spotlight: false,
  },
];

const REQUIRED_FIELDS = ['id', 'title', 'url', 'usage', 'problemArea', 'type'] as const;
const KEBAB_CASE_RE = /^[a-z0-9]+(-[a-z0-9]+)*$/;

/**
 * Throws on any data shape error so Storybook and `next build` fail loudly
 * if a contributor adds a malformed entry.
 */
export function validateResearchSources(sources: ResearchSource[]): void {
  const seen = new Set<string>();
  for (const s of sources) {
    for (const field of REQUIRED_FIELDS) {
      if (!s[field]) {
        throw new Error(
          `[researchSources] entry "${s.id ?? '(no id)'}" missing required field "${field}"`,
        );
      }
    }
    if (!KEBAB_CASE_RE.test(s.id)) {
      throw new Error(
        `[researchSources] id "${s.id}" must be kebab-case (lowercase alphanumerics separated by single hyphens)`,
      );
    }
    if (seen.has(s.id)) {
      throw new Error(`[researchSources] duplicate id "${s.id}"`);
    }
    seen.add(s.id);
    if (s.spotlight && (!s.spotlightProse || s.spotlightProse.trim().length === 0)) {
      throw new Error(`[researchSources] spotlight "${s.id}" missing spotlightProse`);
    }
  }
}

// Runs on every import — intentional. Storybook startup and `next build` should
// abort loudly if data drifts. Cost is microseconds at 56 entries.
validateResearchSources(RESEARCH_SOURCES);
