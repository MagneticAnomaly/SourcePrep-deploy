import type { Meta, StoryObj } from '@storybook/react';
import { IndexStats } from '../../components/dashboard/IndexStats';

const meta: Meta<typeof IndexStats> = {
  title: 'Dashboard/Index/IndexStats',
  component: IndexStats,
  parameters: {
    layout: 'padded',
  },
  tags: ['autodocs'],
};

export default meta;
type Story = StoryObj<typeof IndexStats>;

const sampleStats = [
  { label: 'Total Files', value: 1234, change: '+12 today', trend: 'up' as const },
  { label: 'Chunks', value: 12904, change: '+847 today', trend: 'up' as const },
  { label: 'Embeddings', value: '768-dim', change: 'nomic-embed-text', trend: 'neutral' as const },
  { label: 'Last Build', value: '2m ago', change: 'Auto-rebuild on', trend: 'neutral' as const },
];

export const Default: Story = {
  args: {
    stats: sampleStats,
  },
};

export const Compact: Story = {
  args: {
    stats: sampleStats,
    variant: 'compact',
  },
};

export const Large: Story = {
  args: {
    stats: sampleStats,
    variant: 'large',
  },
};

export const MarketingExample: Story = {
  args: {
    stats: [
      { label: 'Indexed Files', value: '50K+', trend: 'neutral' },
      { label: 'Search Latency', value: '<100ms', trend: 'down', change: '-15% vs cloud' },
      { label: 'Context Assembly', value: '<200ms', trend: 'neutral' },
      { label: 'Token Savings', value: '60%+', trend: 'up' },
    ],
    variant: 'large',
  },
};
