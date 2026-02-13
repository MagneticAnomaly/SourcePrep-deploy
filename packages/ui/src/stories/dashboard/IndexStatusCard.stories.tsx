import type { Meta, StoryObj } from '@storybook/react';
import { IndexStatusCard } from '../../components/dashboard/IndexStatusCard';

// IndexStatusCard Stories
const indexStatusMeta: Meta<typeof IndexStatusCard> = {
  title: 'Dashboard/Widgets/IndexStatusCard',
  component: IndexStatusCard,
  tags: ['autodocs'],
  parameters: {
    layout: 'padded',
  },
};

export default indexStatusMeta;
type IndexStatusStory = StoryObj<typeof IndexStatusCard>;

export const Loaded: IndexStatusStory = {
  args: {
    stats: {
      loaded: true,
      total_documents: 1847,
      model: 'nomic-embed-text',
      built_at: new Date(Date.now() - 1000 * 60 * 5).toISOString(), // 5 min ago
      embedding_dim: 768,
    },
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
      total_documents: 1234,
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
    stats: {
      loaded: true,
      total_documents: 1847,
      model: 'nomic-embed-text',
      built_at: new Date(Date.now() - 1000 * 60 * 5).toISOString(),
      embedding_dim: 768,
    },
    autoRebuild: false,
    onAutoRebuildChange: (auto) => console.log('Auto rebuild:', auto),
    onBuild: () => alert('Rebuilding index...'),
    isPro: true,
  },
};

export const AutoMode: IndexStatusStory = {
  name: 'Auto — No Rebuild Button',
  args: {
    stats: {
      loaded: true,
      total_documents: 1847,
      model: 'nomic-embed-text',
      built_at: new Date(Date.now() - 1000 * 60 * 5).toISOString(),
      embedding_dim: 768,
    },
    autoRebuild: true,
    onAutoRebuildChange: (auto) => console.log('Auto rebuild:', auto),
    onBuild: () => alert('Rebuilding index...'),
    isPro: true,
  },
};

export const FreeUserManualOnly: IndexStatusStory = {
  name: 'Free User — Toggle Disabled',
  args: {
    stats: {
      loaded: true,
      total_documents: 1847,
      model: 'nomic-embed-text',
      built_at: new Date(Date.now() - 1000 * 60 * 5).toISOString(),
      embedding_dim: 768,
    },
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
      loaded: true,
      total_documents: 1234,
      model: 'nomic-embed-text',
      built_at: new Date(Date.now() - 1000 * 60 * 60 * 24).toISOString(),
      embedding_dim: 768,
    },
    stale: true,
    autoRebuild: false,
    onAutoRebuildChange: (auto) => console.log('Auto rebuild:', auto),
    onBuild: () => alert('Rebuilding stale index...'),
    isPro: true,
  },
};

