import type { Meta, StoryObj } from '@storybook/react';
import { StatusCard } from '../../components/status/StatusCard';

const meta: Meta<typeof StatusCard> = {
  title: 'Dashboard/Status/StatusCard',
  component: StatusCard,
  tags: ['autodocs'],
  parameters: {
    layout: 'padded',
  },
};

export default meta;
type Story = StoryObj<typeof StatusCard>;

export const FreshIndex: Story = {
  args: {
    projectName: 'my-project',
    status: 'fresh',
    lastBuildAt: '2 minutes ago',
    chunkCount: 1234,
  },
};

export const StaleIndex: Story = {
  args: {
    projectName: 'my-project',
    status: 'stale',
    lastBuildAt: '3 hours ago',
    chunkCount: 1234,
  },
};

export const Building: Story = {
  args: {
    projectName: 'my-project',
    status: 'building',
    lastBuildAt: '1 day ago',
  },
};

export const ErrorState: Story = {
  args: {
    projectName: 'my-project',
    status: 'error',
    lastBuildAt: '5 minutes ago',
    error: {
      code: 'OLLAMA_UNAVAILABLE',
      message: 'Could not connect to Ollama at localhost:11434',
      hint: 'Make sure Ollama is running and accessible.',
    },
  },
};

export const NoIndex: Story = {
  args: {
    projectName: 'new-project',
    status: 'pending',
  },
};
