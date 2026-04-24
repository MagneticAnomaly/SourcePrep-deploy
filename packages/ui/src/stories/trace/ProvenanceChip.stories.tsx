import type { Meta, StoryObj } from '@storybook/react';
import { ProvenanceChip } from '../../components/trace/ProvenanceChip';
import type { StageRebuildProvenance } from '../../types';

const meta: Meta<typeof ProvenanceChip> = {
  title: 'Dashboard/Widgets/Trace/ProvenanceChip',
  component: ProvenanceChip,
  tags: ['autodocs'],
  parameters: {
    layout: 'centered',
  },
};

export default meta;
type Story = StoryObj<typeof ProvenanceChip>;

// ── Fixtures ──────────────────────────────────────────────────

const matchProvenance: StageRebuildProvenance = {
  state: 'match',
  manifest_model: { provider: 'openai', model_name: 'gpt-4o' },
  current_config_model: { provider: 'openai', model_name: 'gpt-4o' },
  chip_text: null,
  rebuild_scope: null,
};

const driftProvenance: StageRebuildProvenance = {
  state: 'drift',
  manifest_model: { provider: 'openai', model_name: 'gpt-4o' },
  current_config_model: { provider: 'anthropic', model_name: 'claude-3-5-sonnet' },
  chip_text: 'gpt-4o → claude-3-5-sonnet',
  rebuild_scope: 'enrichment',
};

const stubProvenance: StageRebuildProvenance = {
  state: 'recovered_stub',
  manifest_model: null,
  current_config_model: { provider: 'openai', model_name: 'gpt-4o' },
  chip_text: 'provenance unknown',
  rebuild_scope: 'enrichment',
};

const softProvenance: StageRebuildProvenance = {
  state: 'recovered_soft',
  manifest_model: { provider: 'openai', model_name: 'gpt-4o-mini' },
  current_config_model: { provider: 'openai', model_name: 'gpt-4o' },
  chip_text: 'rebuilt with fallback model',
  rebuild_scope: 'enrichment',
};

// ── Stories ───────────────────────────────────────────────────

/**
 * Match state — chip is null (nothing rendered). The story still mounts the
 * component so Storybook can document its existence, but the canvas will be
 * empty.
 */
export const Match: Story = {
  args: {
    provenance: matchProvenance,
  },
};

/**
 * Drift state — model changed since last run. Renders as a clickable button
 * that triggers a scoped rebuild. The chip_text shows the before/after model.
 */
export const Drift: Story = {
  args: {
    provenance: driftProvenance,
    onRebuild: (scope) => {
      console.log('onRebuild called with scope:', scope);
    },
  },
};

/**
 * Drift with no onRebuild callback — renders as a non-interactive span since
 * there is no action to trigger.
 */
export const DriftNoCallback: Story = {
  args: {
    provenance: driftProvenance,
  },
};

/**
 * Recovered stub — provenance metadata was missing (e.g. stage was written
 * before Phase 117). Renders as an actionable warning chip.
 */
export const RecoveredStub: Story = {
  args: {
    provenance: stubProvenance,
    onRebuild: (scope) => {
      console.log('onRebuild called with scope:', scope);
    },
  },
};

/**
 * Recovered soft — stage was rebuilt with a fallback model during selfheal.
 * Informational only; renders as a non-clickable span.
 */
export const RecoveredSoft: Story = {
  args: {
    provenance: softProvenance,
  },
};

/**
 * Undefined provenance — component returns null, canvas is empty.
 */
export const MissingProvenance: Story = {
  args: {
    provenance: undefined,
  },
};
