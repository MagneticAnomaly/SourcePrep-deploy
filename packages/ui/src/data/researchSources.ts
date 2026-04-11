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
