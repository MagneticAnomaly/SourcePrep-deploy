import type { Meta, StoryObj } from '@storybook/react';
import { LLMStatusWidget } from '../../components/dashboard/LLMStatusWidget';

const meta: Meta<typeof LLMStatusWidget> = {
  title: 'Dashboard/LLM/LLMStatusWidget',
  component: LLMStatusWidget,
  tags: ['autodocs'],
  parameters: {
    layout: 'centered',
  },
};

export default meta;
type Story = StoryObj<typeof LLMStatusWidget>;

export const Default: Story = {
  args: {
    services: [
      { name: 'Embedding', status: 'connected', type: 'other', url: 'nomic-embed-text' },
      { name: 'Small Model', status: 'connected', type: 'ollama', url: 'qwen2.5:3b' },
      { name: 'Large Model', status: 'disabled', type: 'ollama' },
    ],
  },
};

export const Bare: Story = {
  args: {
    bare: true,
    services: [
      { name: 'Embedding', status: 'connected', type: 'other', url: 'nomic-embed-text' },
      { name: 'Small Model', status: 'connected', type: 'ollama', url: 'qwen2.5:3b' },
      { name: 'Large Model', status: 'disabled', type: 'ollama' },
    ],
  },
};

export const Disconnected: Story = {
  args: {
    services: [
      { name: 'Embedding', status: 'disconnected', type: 'other', url: 'nomic-embed-text' },
      { name: 'Small Model', status: 'disconnected', type: 'ollama', url: 'qwen2.5:3b' },
      { name: 'Large Model', status: 'disabled', type: 'ollama' },
    ],
  },
};

export const NotConfigured: Story = {
  args: {
    services: [
      { name: 'Embedding', status: 'not-configured', type: 'other' },
      { name: 'Small Model', status: 'not-configured', type: 'ollama' },
      { name: 'Large Model', status: 'not-configured', type: 'ollama' },
    ],
  },
};
