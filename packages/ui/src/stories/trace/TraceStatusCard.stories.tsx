import type { Meta, StoryObj } from '@storybook/react';
import { TraceStatusCard } from '../../components/trace/TraceStatusCard';

const meta: Meta<typeof TraceStatusCard> = {
  title: 'Dashboard/Trace/StatusCard',
  component: TraceStatusCard,
  tags: ['autodocs'],
  parameters: {
    layout: 'padded',
  },
};

export default meta;
type Story = StoryObj<typeof TraceStatusCard>;

export const Disabled: Story = {
  args: {
    status: {
      enabled: false,
      exists: false,
      building: false,
      counts: { nodes: 0, edges: 0 },
      last_build_at: null,
      last_error: null,
    },
  },
};

export const Ready: Story = {
  args: {
    status: {
      enabled: true,
      exists: true,
      building: false,
      counts: { nodes: 1245, edges: 3890 },
      last_build_at: '2024-02-03 14:30',
      last_error: null,
    },
  },
};

export const Building: Story = {
  args: {
    status: {
      enabled: true,
      exists: true,
      building: true,
      counts: { nodes: 1245, edges: 3890 },
      last_build_at: '2024-02-03 14:30',
      last_error: null,
    },
  },
};

export const Error: Story = {
  args: {
    status: {
      enabled: true,
      exists: false,
      building: false,
      counts: { nodes: 0, edges: 0 },
      last_build_at: null,
      last_error: 'Failed to parse src/core/graph.ts: SyntaxError',
    },
  },
};
