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

export const RESEARCH_SOURCES: ResearchSource[] = [];

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
