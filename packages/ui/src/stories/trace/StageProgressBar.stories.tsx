import type { Meta, StoryObj } from '@storybook/react';
import { StageProgressBar } from '../../components/trace/StageProgressBar';

const meta: Meta<typeof StageProgressBar> = {
  title: 'Trace/StageProgressBar',
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
