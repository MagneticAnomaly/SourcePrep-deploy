import type { Meta, StoryObj } from '@storybook/react';
import { StageProgressBar } from '../../components/trace/StageProgressBar';

const meta: Meta<typeof StageProgressBar> = {
  title: 'Dashboard/Build/StageProgressBar',
  component: StageProgressBar,
  parameters: {
    layout: 'padded',
    docs: { description: { component: 'Thin progress bar used within pipeline stages. Supports normal progress mode and rerun mode (green done + orange stale sections).' } },
  },
  decorators: [(Story) => <div style={{ maxWidth: 400 }}><Story /></div>],
};

export default meta;
type Story = StoryObj<typeof StageProgressBar>;

/** 60% progress — standard build */
export const InProgress: Story = {
  args: { progress: 60, color: 'bg-blue-500' },
};

/** 100% complete */
export const Complete: Story = {
  args: { progress: 100, color: 'bg-success' },
};

/** Zero/indeterminate */
export const Empty: Story = {
  args: { progress: 0 },
};

/** Rerun mode — green (done) + orange (stale) */
export const Rerun: Story = {
  args: {
    progress: 45,
    rerun: { donePercent: 70, stalePercent: 30 },
  },
};

/** Initialize variant — simple single-color progress bar for first-time index builds */
export const Initialize: Story = {
  args: { variant: 'initialize', progress: 60, color: 'bg-blue-500', className: 'h-1.5' },
};

/** Incremental variant — rerun mode showing done + stale sections for partial re-indexing */
export const Incremental: Story = {
  args: {
    variant: 'incremental',
    progress: 50,
    className: 'h-1.5',
    rerun: { donePercent: 70, stalePercent: 30 },
  },
};

/** Rebuild variant — green bottom half (old index live) + orange top half (rebuild progress) */
export const Rebuild: Story = {
  args: { variant: 'rebuild', rebuildPercent: 35, className: 'h-2' },
};

/** Rebuild variant — paused state overlay on the rebuild progress bar */
export const RebuildPaused: Story = {
  args: { variant: 'rebuild', rebuildPercent: 35, rebuildStateOverlay: 'paused', className: 'h-2' },
};

/** Rebuild variant — failed state overlay on the rebuild progress bar */
export const RebuildFailed: Story = {
  args: { variant: 'rebuild', rebuildPercent: 35, rebuildStateOverlay: 'failed', className: 'h-2' },
};
