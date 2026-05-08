import type { Meta, StoryObj } from '@storybook/react';
import { BuildProgress } from '../../components/status/BuildProgress';

const meta: Meta<typeof BuildProgress> = {
  title: 'Dashboard/Build/BuildProgress',
  component: BuildProgress,
  tags: ['autodocs'],
  parameters: {
    layout: 'padded',
  },
};

export default meta;
type Story = StoryObj<typeof BuildProgress>;

export const Scanning: Story = {
  args: {
    phase: 'scanning',
    percent: 15,
    counts: {
      files_total: 1200,
      files_done: 180,
    },
  },
};

export const Chunking: Story = {
  args: {
    phase: 'chunking',
    percent: 35,
    counts: {
      files_total: 1200,
      files_done: 1200,
      chunks_total: 5400,
      chunks_done: 1890,
    },
  },
};

export const Embedding: Story = {
  args: {
    phase: 'embedding',
    percent: 72,
    counts: {
      chunks_total: 5400,
      chunks_done: 3888,
    },
  },
};

export const Writing: Story = {
  args: {
    phase: 'writing',
    percent: 95,
  },
};

export const Complete: Story = {
  args: {
    phase: 'complete',
    percent: 100,
    counts: {
      files_total: 1200,
      files_done: 1200,
      chunks_total: 5400,
      chunks_done: 5400,
    },
  },
};

export const IndeterminateProgress: Story = {
  args: {
    phase: 'embedding',
  },
};
