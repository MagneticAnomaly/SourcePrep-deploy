import type { Meta, StoryObj } from '@storybook/react';
import { RebuildingRow } from '../../components/trace/RebuildingRow';

const meta: Meta<typeof RebuildingRow> = {
  title: 'Dashboard/Widgets/Trace/RebuildingRow',
  component: RebuildingRow,
  tags: ['autodocs'],
  parameters: {
    layout: 'padded',
  },
};

export default meta;
type Story = StoryObj<typeof RebuildingRow>;

// ── Stories ───────────────────────────────────────────────────

/**
 * Sync scope rebuild — the fast-sync stages (Structural, Catalogue,
 * Validation, Knowledge Embedding) are running. Shows stage 3 of 5.
 */
export const Sync: Story = {
  args: {
    scope: 'sync',
    currentStageIndex: 2,
    totalStagesInScope: 5,
    currentStageLabel: 'Fast Catalogue',
    percent: 38,
    onStop: () => {
      console.log('Stop clicked (Sync)');
    },
  },
};

/**
 * Enrichment scope rebuild — the deep-enrichment stages (Epistemic,
 * Clustering, Deepening, Deep Knowledge) are running. Shows stage 1 of 4.
 */
export const Enrichment: Story = {
  args: {
    scope: 'enrichment',
    currentStageIndex: 1,
    totalStagesInScope: 5,
    currentStageLabel: 'Epistemic Enrichment',
    percent: 12,
    onStop: () => {
      console.log('Stop clicked (Enrichment)');
    },
  },
};

/**
 * All-scope rebuild — every stage in the pipeline is being rebuilt from
 * scratch. Shows stage 7 of 15 (mid-run).
 */
export const All: Story = {
  args: {
    scope: 'all',
    currentStageIndex: 11,
    totalStagesInScope: 15,
    currentStageLabel: 'Group Reasoning',
    percent: 55,
    onStop: () => {
      console.log('Stop clicked (All)');
    },
  },
};
