import type { Meta, StoryObj } from '@storybook/react';
import { ProbeButton, type ProbeResult } from './ProbeButton';

const meta: Meta<typeof ProbeButton> = {
  title: 'Dashboard/Pipeline/ProbeButton',
  component: ProbeButton,
};
export default meta;

type Story = StoryObj<typeof ProbeButton>;

const goodResult: ProbeResult = {
  endpoint_id: 'default_ollama',
  probed_at: 1777212109,
  burst_size: 20,
  wall_clock_ms: { p50: 1234, p90: 4567, p99: 12345 },
  saturation_point: 10,
  saturation_method: 'latency_staircase',
  recommended_concurrent: 9,
  successes: 20,
  errors: 0,
  histogram_path: '/Users/x/.local/share/sourceprep/probes/default_ollama_2026-04-26.json',
};

const headerResult: ProbeResult = {
  endpoint_id: 'openai_main',
  probed_at: 1777212109,
  burst_size: 20,
  wall_clock_ms: { p50: 850, p90: 1100, p99: 1900 },
  saturation_point: 12,
  saturation_method: 'header',
  recommended_concurrent: 11,
  successes: 20,
  errors: 0,
  histogram_path: null,
};

const flatResult: ProbeResult = {
  endpoint_id: 'anthropic_main',
  probed_at: 1777212109,
  burst_size: 20,
  wall_clock_ms: { p50: 410, p90: 520, p99: 640 },
  saturation_point: null,
  saturation_method: 'none',
  recommended_concurrent: null,
  successes: 20,
  errors: 0,
  histogram_path: null,
};

export const Idle: Story = {
  args: {
    endpointId: 'default_ollama',
    burstSize: 20,
    onApply: (n) => console.log('apply', n),
  },
};

export const Probing: Story = {
  args: {
    endpointId: 'default_ollama',
    burstSize: 20,
    initialState: 'probing',
  },
};

export const DoneWithRecommendation: Story = {
  args: {
    endpointId: 'default_ollama',
    burstSize: 20,
    initialResult: goodResult,
    initialDurationMs: 24300,
    onApply: (n) => console.log('apply', n),
  },
};

export const DoneFromHeaders: Story = {
  args: {
    endpointId: 'openai_main',
    burstSize: 20,
    initialResult: headerResult,
    initialDurationMs: 18200,
    onApply: (n) => console.log('apply', n),
  },
};

export const DoneNoSaturation: Story = {
  args: {
    endpointId: 'anthropic_main',
    burstSize: 20,
    initialResult: flatResult,
    initialDurationMs: 9100,
  },
};

export const Error: Story = {
  args: {
    endpointId: 'broken_ep',
    burstSize: 20,
    initialState: 'error',
  },
};
