import type { PrepTaskId } from '../types';

export type TokenVolume = 'Low' | 'Medium' | 'High' | 'Extreme';

export interface TaskTokenEstimate {
  volume: TokenVolume;
  tokensPerUnit: number;
  unitLabel: string;
  multiplier: (fileCount: number) => number;
  description: (fileCount: number) => string;
}

const TASK_TOKEN_HEURISTICS: Record<PrepTaskId, TaskTokenEstimate> = {
  catalogue: {
    volume: 'Extreme',
    tokensPerUnit: 800,
    unitLabel: 'file',
    multiplier: (f) => f,
    description: (f) => `~${fmt(800 * f)} tokens (${f} files × ~800 tok/file)`,
  },
  inferred_edges: {
    volume: 'High',
    tokensPerUnit: 1200,
    unitLabel: 'file',
    multiplier: (f) => f,
    description: (f) => `~${fmt(1200 * f)} tokens (${f} files × ~1.2k tok/file)`,
  },
  enrichment: {
    volume: 'Extreme',
    tokensPerUnit: 1500,
    unitLabel: 'file',
    multiplier: (f) => f,
    description: (f) => `~${fmt(1500 * f)} tokens (${f} files × ~1.5k tok/file)`,
  },
  group_reasoning: {
    volume: 'Medium',
    tokensPerUnit: 3000,
    unitLabel: 'group',
    multiplier: (f) => Math.max(1, Math.ceil(f / 10)),
    description: (f) => {
      const groups = Math.max(1, Math.ceil(f / 10));
      return `~${fmt(3000 * groups)} tokens (${groups} groups × ~3k tok/group)`;
    },
  },
  clustering: {
    volume: 'Medium',
    tokensPerUnit: 2000,
    unitLabel: 'cluster',
    multiplier: (f) => Math.max(1, Math.ceil(f / 15)),
    description: (f) => {
      const clusters = Math.max(1, Math.ceil(f / 15));
      return `~${fmt(2000 * clusters)} tokens (${clusters} clusters × ~2k tok/cluster)`;
    },
  },
  atlas: {
    volume: 'Low',
    tokensPerUnit: 5000,
    unitLabel: 'segment',
    multiplier: (f) => Math.max(1, Math.ceil(f / 100)) + 1,
    description: (f) => {
      const segments = Math.max(1, Math.ceil(f / 100)) + 1;
      return `~${fmt(5000 * segments)} tokens (${segments} segments × ~5k tok/segment)`;
    },
  },
  deepening: {
    volume: 'High',
    tokensPerUnit: 2000,
    unitLabel: 'weak edge',
    multiplier: (f) => Math.ceil(f * 0.3),
    description: (f) => {
      const edges = Math.ceil(f * 0.3);
      return `~${fmt(2000 * edges)} tokens (~${edges} weak edges × ~2k tok/edge)`;
    },
  },
  search_intent: {
    volume: 'Low',
    tokensPerUnit: 500,
    unitLabel: 'query',
    multiplier: () => 1,
    description: () => `~500 tokens per search query`,
  },
  audit: {
    volume: 'Low',
    tokensPerUnit: 4000,
    unitLabel: 'report',
    multiplier: () => 5,
    description: () => `~20k tokens (5 reports × ~4k tok/report)`,
  },
  augmentation: {
    volume: 'Low',
    tokensPerUnit: 600,
    unitLabel: 'trace',
    multiplier: () => 1,
    description: () => `~600 tokens per trace request`,
  },
};

function fmt(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}k`;
  return String(n);
}

export function getTaskTokenEstimate(taskId: PrepTaskId): TaskTokenEstimate {
  return TASK_TOKEN_HEURISTICS[taskId];
}

export function estimateTaskTokens(taskId: PrepTaskId, fileCount: number): number {
  const h = TASK_TOKEN_HEURISTICS[taskId];
  return h.tokensPerUnit * h.multiplier(fileCount);
}

export function getTaskTokenDescription(taskId: PrepTaskId, fileCount: number): string {
  return TASK_TOKEN_HEURISTICS[taskId].description(fileCount);
}

export function getTaskTokenVolume(taskId: PrepTaskId): TokenVolume {
  return TASK_TOKEN_HEURISTICS[taskId].volume;
}
