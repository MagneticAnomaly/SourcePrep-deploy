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
