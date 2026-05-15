import type { Meta, StoryObj } from '@storybook/react';
import { IndexStatusCard, type IndexStats } from '../../components/dashboard/IndexStatusCard';

// IndexStatusCard Stories
const indexStatusMeta: Meta<typeof IndexStatusCard> = {
  title: 'Dashboard/Index/IndexStatusCard',
  component: IndexStatusCard,
  tags: ['autodocs'],
  parameters: {
    layout: 'padded',
  },
};

export default indexStatusMeta;
type IndexStatusStory = StoryObj<typeof IndexStatusCard>;

// Shared fixture — a small, focused knowledge base for "loaded" stories.
// Numbers are deliberately low so the docs page that embeds this story
// models a tight, scoped knowledge base — not an "index everything"
// posture. Reflects a realistic feature-folder scope.
const LOADED_STATS: IndexStats = {
  loaded: true,
  index_dir: '~/code/sourceprep',
  model: 'nomic-embed-text',
  built_at: new Date(Date.now() - 1000 * 60 * 5).toISOString(), // 5 min ago
  embedding_dim: 768,
  total_documents: 22,
  build: {
    mode: 'incremental',
    files_total: 13,
    files_reused: 11,
    files_embedded: 2,
    files_deleted: 0,
    files_code: 6,
    files_docs: 7,
    chunks_total: 22,
    chunks_code: 10,
    chunks_docs: 12,
    lines_code: 480,
    lines_docs: 540,
  },
};

const LOADED_TRACE_CHUNKS = 18;

export const Loaded: IndexStatusStory = {
  args: {
    stats: LOADED_STATS,
    traceChunks: LOADED_TRACE_CHUNKS,
    bare: true,
  },
};

export const NotLoaded: IndexStatusStory = {
  args: {
    stats: {
      loaded: false,
    },
  },
};

export const Building: IndexStatusStory = {
  args: {
    stats: {
      loaded: true,
      total_documents: 14,
      model: 'nomic-embed-text',
      built_at: new Date(Date.now() - 1000 * 60 * 60 * 2).toISOString(), // 2 hours ago
    },
    building: true,
  },
};

export const WithError: IndexStatusStory = {
  args: {
    stats: {
      loaded: false,
    },
    lastError: 'Could not connect to Ollama at localhost:11434',
  },
};

// ── Auto/Manual toggle stories ──────────────────────────────

export const ManualWithRebuild: IndexStatusStory = {
  name: 'Manual — Rebuild Button Visible',
  args: {
    stats: LOADED_STATS,
    traceChunks: LOADED_TRACE_CHUNKS,
    autoRebuild: false,
    onAutoRebuildChange: (auto) => console.log('Auto rebuild:', auto),
    onBuild: () => alert('Rebuilding index...'),
    isPro: true,
  },
};

export const AutoMode: IndexStatusStory = {
  name: 'Auto — No Rebuild Button',
  args: {
    stats: LOADED_STATS,
    traceChunks: LOADED_TRACE_CHUNKS,
    autoRebuild: true,
    onAutoRebuildChange: (auto) => console.log('Auto rebuild:', auto),
    onBuild: () => alert('Rebuilding index...'),
    isPro: true,
  },
};

export const FreeUserManualOnly: IndexStatusStory = {
  name: 'Free User — Toggle Disabled',
  args: {
    stats: LOADED_STATS,
    traceChunks: LOADED_TRACE_CHUNKS,
    autoRebuild: false,
    onAutoRebuildChange: (auto) => console.log('Auto rebuild:', auto),
    onBuild: () => alert('Rebuilding index...'),
    isPro: false,
  },
};

export const StaleManual: IndexStatusStory = {
  name: 'Stale — Manual Rebuild (amber)',
  args: {
    stats: {
      ...LOADED_STATS,
      built_at: new Date(Date.now() - 1000 * 60 * 60 * 24).toISOString(), // 1 day ago
    },
    traceChunks: LOADED_TRACE_CHUNKS,
    stale: true,
    autoRebuild: false,
    onAutoRebuildChange: (auto) => console.log('Auto rebuild:', auto),
    onBuild: () => alert('Rebuilding stale index...'),
    isPro: true,
  },
};

