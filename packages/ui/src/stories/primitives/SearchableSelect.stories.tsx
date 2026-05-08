import type { Meta, StoryObj } from '@storybook/react';
import { useState } from 'react';
import { SearchableSelect } from '../../components/primitives/SearchableSelect';

const meta: Meta<typeof SearchableSelect> = {
  title: 'Primitives/SearchableSelect',
  component: SearchableSelect,
  tags: ['autodocs'],
  decorators: [
    (Story) => (
      <div className="w-[420px] bg-surface border border-border rounded-lg p-4">
        <Story />
      </div>
    ),
  ],
};

export default meta;
type Story = StoryObj<typeof SearchableSelect>;

const FIVE = [
  { value: 'light',   label: 'Light' },
  { value: 'dark',    label: 'Dark' },
  { value: 'system',  label: 'System' },
  { value: 'sepia',   label: 'Sepia' },
  { value: 'monoglow',label: 'Monoglow' },
];

// Caricature of an OpenRouter catalog — 369-ish models, deeply alphabetical.
function makeLargeCatalog(): { value: string; label: string }[] {
  const providers = [
    'anthropic/claude-3-haiku', 'anthropic/claude-4-sonnet',
    'anthropic/claude-4.5-sonnet', 'anthropic/claude-4.6-sonnet',
    'anthropic/claude-opus-4', 'anthropic/claude-opus-4.6',
    'cohere/command-r-plus', 'deepseek/deepseek-r1',
    'deepseek/deepseek-v3.5', 'google/gemini-2.5-pro',
    'google/gemini-3-flash', 'google/gemini-3-pro',
    'meta-llama/llama-3.3-70b', 'meta-llama/llama-4-405b',
    'mistralai/mistral-large-2', 'mistralai/mixtral-8x22b',
    'openai/gpt-4o', 'openai/gpt-5', 'openai/gpt-5-thinking',
    'qwen/qwen3.6-27b', 'qwen/qwen3.6-35b-a3b',
    'qwen/qwen3.6-flash', 'qwen/qwen3.6-max-preview',
    'qwen/qwen3.6-plus', 'qwen/qwen3.6-plus:free',
    'x-ai/grok-3', 'x-ai/grok-3-fast',
  ];
  // Pad to 50 with synthetic entries so the search threshold (8) kicks in.
  const padded = [...providers];
  for (let i = padded.length; i < 50; i++) padded.push(`provider-${i}/model-${i}`);
  return padded.map((id) => ({ value: id, label: id }));
}

const LARGE = makeLargeCatalog();

export const FewOptions: Story = {
  name: 'Few options (no search input — under threshold)',
  render: () => {
    const [v, setV] = useState('dark');
    return <SearchableSelect options={FIVE} value={v} onChange={setV} />;
  },
};

export const LargeCatalog: Story = {
  name: '50-model catalog (search engaged)',
  render: () => {
    const [v, setV] = useState('qwen/qwen3.6-plus');
    return <SearchableSelect options={LARGE} value={v} onChange={setV} placeholder="Pick a model..." />;
  },
};

export const Empty: Story = {
  name: 'Empty selection',
  render: () => {
    const [v, setV] = useState('');
    return <SearchableSelect options={LARGE} value={v} onChange={setV} placeholder="Select a model..." />;
  },
};

export const Disabled: Story = {
  render: () => (
    <SearchableSelect options={FIVE} value="light" onChange={() => {}} disabled />
  ),
};

export const SmallSize: Story = {
  render: () => {
    const [v, setV] = useState('');
    return <SearchableSelect options={FIVE} value={v} onChange={setV} size="sm" placeholder="Compact..." />;
  },
};

export const WithDisabledOption: Story = {
  name: 'Disabled / blocked option (e.g. policy-blocked model)',
  render: () => {
    const opts = [
      { value: 'allowed-1', label: 'allowed-1' },
      { value: 'allowed-2', label: 'allowed-2' },
      { value: 'blocked',   label: '🚫 blocked-by-policy', disabled: true },
    ];
    const [v, setV] = useState('allowed-1');
    return <SearchableSelect options={opts} value={v} onChange={setV} />;
  },
};
