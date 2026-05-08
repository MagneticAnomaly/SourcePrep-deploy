import type { Meta, StoryObj } from '@storybook/react';
import { StatusBadge } from '../../components/status/StatusBadge';

const meta: Meta<typeof StatusBadge> = {
  title: 'Dashboard/Status/StatusBadge',
  component: StatusBadge,
  tags: ['autodocs'],
  argTypes: {
    status: {
      control: 'select',
      options: ['fresh', 'stale', 'building', 'pending', 'error', 'disabled'],
      description: 'Current status state',
    },
    showLabel: {
      control: 'boolean',
      description: 'Whether to show the status label text',
    },
    labelOverride: {
      control: 'text',
      description: 'Optional label override (e.g. "Swarming" instead of "Building")',
    },
  },
};

export default meta;
type Story = StoryObj<typeof StatusBadge>;

export const Fresh: Story = {
  args: {
    status: 'fresh',
    showLabel: true,
  },
};

export const Stale: Story = {
  args: {
    status: 'stale',
    showLabel: true,
  },
};

export const Building: Story = {
  args: {
    status: 'building',
    showLabel: true,
  },
};

export const Pending: Story = {
  args: {
    status: 'pending',
    showLabel: true,
  },
};

export const Error: Story = {
  args: {
    status: 'error',
    showLabel: true,
  },
};

export const Disabled: Story = {
  args: {
    status: 'disabled',
    showLabel: true,
  },
};

export const Swarming: Story = {
  args: {
    status: 'building',
    showLabel: true,
    labelOverride: 'Swarming',
  },
};

export const AllStates: Story = {
  render: () => (
    <div className="flex flex-wrap gap-2">
      <StatusBadge status="fresh" />
      <StatusBadge status="stale" />
      <StatusBadge status="building" />
      <StatusBadge status="building" labelOverride="Swarming" />
      <StatusBadge status="pending" />
      <StatusBadge status="error" />
      <StatusBadge status="disabled" />
    </div>
  ),
};
