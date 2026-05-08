import type { Meta, StoryObj } from '@storybook/react';
import { CapacityHealth, type CapacityEndpoint, type SaturationSnapshot } from './CapacityHealth';
import type { ConcurrencyNode } from './ConcurrencyHealth';
import type { ProbeResult } from '../llm/ProbeButton';

const meta: Meta<typeof CapacityHealth> = {
  title: 'Dashboard/Pipeline/CapacityHealth',
  component: CapacityHealth,
  parameters: { layout: 'padded' },
};
export default meta;

type Story = StoryObj<typeof CapacityHealth>;

const ep1: CapacityEndpoint = {
  id: 'default_ollama',
  name: 'Ollama Cloud (Pro)',
  provider: 'ollama',
  url: 'https://ollama.com',
  plan_tier: 'pro',
  cloud_concurrency: 3,
};

const ep2: CapacityEndpoint = {
  id: 'openai_main',
  name: 'OpenAI Tier 3',
  provider: 'openai',
  url: 'https://api.openai.com/v1',
  plan_tier: 'tier_3',
  cloud_concurrency: 20,
};

const ep3: CapacityEndpoint = {
  id: 'anthropic_main',
  name: 'Anthropic',
  provider: 'anthropic',
  url: 'https://api.anthropic.com',
  plan_tier: 'auto',
  cloud_concurrency: 0,
};

const node1: ConcurrencyNode = {
  max_concurrent: 3,
  current_load: 2,
  in_flight_requests: 2,
  current_limit: 3,
  discovered_ceiling: 3,
  locked_until: Date.now() / 1000 + 90,
  aimd_mode: 'congestion_avoidance',
  state: 'locked',
};

const node2: ConcurrencyNode = {
  max_concurrent: 20,
  current_load: 5,
  in_flight_requests: 5,
  current_limit: 18,
  discovered_ceiling: null,
  locked_until: null,
  aimd_mode: 'jumpstart',
  state: 'probing',
};

const probe1: ProbeResult = {
  endpoint_id: 'default_ollama',
  probed_at: Date.now() / 1000 - 7200, // 2h ago
  burst_size: 20,
  wall_clock_ms: { p50: 1234, p90: 4567, p99: 12345 },
  saturation_point: 10,
  saturation_method: 'latency_staircase',
  recommended_concurrent: 9,
  successes: 20,
  errors: 0,
  histogram_path: null,
};

const probe2: ProbeResult = {
  endpoint_id: 'openai_main',
  probed_at: Date.now() / 1000 - 60,
  burst_size: 20,
  wall_clock_ms: { p50: 850, p90: 1100, p99: 1900 },
  saturation_point: null,
  saturation_method: 'none',
  recommended_concurrent: null,
  successes: 20,
  errors: 0,
  histogram_path: null,
};

const sat1: SaturationSnapshot = {
  score: 0.32,
  reason: 'x-ratelimit-remaining-requests=88/100',
  ts: Date.now() / 1000 - 5,
};

const sat2: SaturationSnapshot = {
  score: 0.85,
  reason: 'x-ratelimit-remaining-tokens=110/4000',
  ts: Date.now() / 1000 - 2,
};

export const ThreeEndpointsMixedHealth: Story = {
  args: {
    initialEndpoints: [ep1, ep2, ep3],
    initialNodes: {
      [`cloud:${ep1.id}`]: node1,
      [`cloud:${ep2.id}`]: node2,
    },
    initialProbes: {
      [ep1.id]: probe1,
      [ep2.id]: probe2,
    },
    initialSaturation: {
      [ep1.id]: sat1,
      [ep2.id]: sat2,
    },
    pollMs: 0,
  },
};

export const NoEndpoints: Story = {
  args: {
    initialEndpoints: [],
    initialNodes: {},
    initialProbes: {},
    initialSaturation: {},
    pollMs: 0,
  },
};

export const NoProbesYet: Story = {
  args: {
    initialEndpoints: [ep1, ep2],
    initialNodes: {
      [`cloud:${ep1.id}`]: node1,
      [`cloud:${ep2.id}`]: node2,
    },
    initialProbes: {},
    initialSaturation: {},
    pollMs: 0,
  },
};

export const HighSaturation: Story = {
  args: {
    initialEndpoints: [ep2],
    initialNodes: { [`cloud:${ep2.id}`]: node2 },
    initialProbes: { [ep2.id]: probe2 },
    initialSaturation: {
      [ep2.id]: { score: 0.92, reason: 'x-ratelimit-reset=12s', ts: Date.now() / 1000 - 1 },
    },
    pollMs: 0,
  },
};
