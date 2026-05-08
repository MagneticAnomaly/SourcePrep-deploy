import type { Meta, StoryObj } from '@storybook/react';
import { PlanDropdown, type PlanLimitsTable } from './PlanDropdown';

const FIXTURE: PlanLimitsTable = {
  version: 1,
  providers: {
    ollama_cloud: {
      label: 'Ollama Cloud',
      auto_detect: false,
      auto_detect_reason: 'Ollama Cloud silently queues; no x-ratelimit-* headers',
      tiers: [
        { tier_key: 'free', tier_label: 'Free', concurrent: 1, source_url: 'https://ollama.com/pricing' },
        { tier_key: 'pro', tier_label: 'Pro', concurrent: 3, source_url: 'https://ollama.com/pricing' },
        { tier_key: 'max', tier_label: 'Max', concurrent: 10, source_url: 'https://ollama.com/pricing' },
      ],
    },
    openai: {
      label: 'OpenAI',
      auto_detect: true,
      auto_detect_reason: 'x-ratelimit-remaining-requests headers',
      tiers: [
        { tier_key: 'tier_1', tier_label: 'Tier 1', concurrent: 5, source_url: 'https://platform.openai.com/docs/guides/rate-limits' },
        { tier_key: 'tier_3', tier_label: 'Tier 3', concurrent: 20, source_url: 'https://platform.openai.com/docs/guides/rate-limits' },
      ],
    },
  },
};

const meta: Meta<typeof PlanDropdown> = {
  title: 'Dashboard/Pipeline/PlanDropdown',
  component: PlanDropdown,
};
export default meta;

type Story = StoryObj<typeof PlanDropdown>;

export const OllamaCloudUnselected: Story = {
  args: {
    providerKey: 'ollama_cloud',
    value: undefined,
    customConcurrent: 1,
    limits: FIXTURE,
    onChange: () => {},
  },
};

export const OllamaCloudMaxSelected: Story = {
  args: {
    providerKey: 'ollama_cloud',
    value: 'max',
    customConcurrent: 1,
    limits: FIXTURE,
    onChange: () => {},
  },
};

export const OpenAIAutoDefault: Story = {
  args: {
    providerKey: 'openai',
    value: 'auto',
    customConcurrent: 1,
    limits: FIXTURE,
    onChange: () => {},
  },
};

export const CustomOverride: Story = {
  args: {
    providerKey: 'ollama_cloud',
    value: 'custom',
    customConcurrent: 7,
    limits: FIXTURE,
    onChange: () => {},
  },
};
