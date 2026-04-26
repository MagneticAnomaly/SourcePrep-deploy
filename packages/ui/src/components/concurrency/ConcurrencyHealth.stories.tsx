import type { Meta, StoryObj } from '@storybook/react';
import {
  ConcurrencyHealth,
  type ConcurrencyEvent,
  type ConcurrencyNode,
} from './ConcurrencyHealth';

// Phase 119 Task 15: weather-report dashboard panel.

const meta: Meta<typeof ConcurrencyHealth> = {
  title: 'Pipeline/ConcurrencyHealth',
  component: ConcurrencyHealth,
  tags: ['autodocs'],
  parameters: {
    layout: 'fullscreen',
    docs: {
      description: {
        component:
          'Phase 119 weather-report panel. Shows live AIMD state for each cloud LLM node, plus a recent-event timeline and current_limit sparkline. Polls /compute/scheduler and /compute/concurrency/history every 2 s when wired to a daemon.',
      },
    },
  },
};

export default meta;

type Story = StoryObj<typeof ConcurrencyHealth>;

const NOW = Math.floor(Date.now() / 1000);

const mockHealthyNode: ConcurrencyNode = {
  max_concurrent: 64,
  current_load: 4,
  in_flight_requests: 5,
  current_limit: 52,
  discovered_ceiling: 64,
  locked_until: NOW + 3600 * 12,
  aimd_mode: 'congestion_avoidance',
  state: 'locked',
};

const mockProbingNode: ConcurrencyNode = {
  max_concurrent: 64,
  current_load: 2,
  in_flight_requests: 8,
  current_limit: 16,
  discovered_ceiling: null,
  locked_until: 0,
  aimd_mode: 'jumpstart',
  state: 'probing',
};

const mockBackingOffNode: ConcurrencyNode = {
  max_concurrent: 64,
  current_load: 1,
  in_flight_requests: 12,
  current_limit: 24,
  discovered_ceiling: 48,
  locked_until: NOW + 3600 * 23,
  aimd_mode: 'congestion_avoidance',
  state: 'backing_off',
};

const mockRecoveringNode: ConcurrencyNode = {
  max_concurrent: 64,
  current_load: 0,
  in_flight_requests: 3,
  current_limit: 30,
  discovered_ceiling: 48,
  locked_until: NOW - 60,
  aimd_mode: 'congestion_avoidance',
  state: 'recovering',
};

const sampleEvents: ConcurrencyEvent[] = [
  { ts: NOW - 600, node_id: 'cloud:openai-prod', before: 0, after: 5, reason: 'hydrate', in_flight: 0, mode: 'jumpstart' },
  { ts: NOW - 540, node_id: 'cloud:openai-prod', before: 5, after: 10, reason: 'jumpstart', in_flight: 5, mode: 'jumpstart' },
  { ts: NOW - 480, node_id: 'cloud:openai-prod', before: 10, after: 20, reason: 'jumpstart', in_flight: 10, mode: 'jumpstart' },
  { ts: NOW - 420, node_id: 'cloud:openai-prod', before: 20, after: 40, reason: 'jumpstart', in_flight: 20, mode: 'jumpstart' },
  { ts: NOW - 360, node_id: 'cloud:openai-prod', before: 40, after: 64, reason: 'jumpstart', in_flight: 38, mode: 'jumpstart' },
  { ts: NOW - 320, node_id: 'cloud:openai-prod', before: 64, after: 32, reason: 'backoff', in_flight: 64, mode: 'congestion_avoidance' },
  { ts: NOW - 320, node_id: 'cloud:openai-prod', before: 32, after: 32, reason: 'edge_lock', in_flight: 64, mode: 'congestion_avoidance' },
  { ts: NOW - 280, node_id: 'cloud:openai-prod', before: 32, after: 33, reason: 'additive_increase', in_flight: 30, mode: 'congestion_avoidance' },
  { ts: NOW - 220, node_id: 'cloud:openai-prod', before: 33, after: 34, reason: 'demand_recovery', in_flight: 33, mode: 'congestion_avoidance' },
  { ts: NOW - 160, node_id: 'cloud:openai-prod', before: 34, after: 40, reason: 'additive_increase', in_flight: 30, mode: 'congestion_avoidance' },
  { ts: NOW - 100, node_id: 'cloud:openai-prod', before: 40, after: 48, reason: 'additive_increase', in_flight: 35, mode: 'congestion_avoidance' },
  { ts: NOW - 40, node_id: 'cloud:openai-prod', before: 48, after: 52, reason: 'demand_recovery', in_flight: 48, mode: 'congestion_avoidance' },
];

const probingEvents: ConcurrencyEvent[] = [
  { ts: NOW - 90, node_id: 'cloud:gemini', before: 5, after: 10, reason: 'jumpstart', in_flight: 5, mode: 'jumpstart' },
  { ts: NOW - 30, node_id: 'cloud:gemini', before: 10, after: 16, reason: 'jumpstart', in_flight: 10, mode: 'jumpstart' },
];

const backingOffEvents: ConcurrencyEvent[] = sampleEvents.slice(0, 8).map((e) => ({
  ...e,
  node_id: 'cloud:anthropic',
}));

const recoveringEvents: ConcurrencyEvent[] = sampleEvents.slice(5).map((e) => ({
  ...e,
  node_id: 'cloud:azure-openai',
}));

export const AllStates: Story = {
  args: {
    pollMs: 0,
    initialNodes: {
      'cloud:openai-prod': mockHealthyNode,
      'cloud:gemini': mockProbingNode,
      'cloud:anthropic': mockBackingOffNode,
      'cloud:azure-openai': mockRecoveringNode,
    },
    initialHistory: {
      'cloud:openai-prod': sampleEvents,
      'cloud:gemini': probingEvents,
      'cloud:anthropic': backingOffEvents,
      'cloud:azure-openai': recoveringEvents,
    },
  },
};

export const SingleLockedNode: Story = {
  args: {
    pollMs: 0,
    initialNodes: { 'cloud:openai-prod': mockHealthyNode },
    initialHistory: { 'cloud:openai-prod': sampleEvents },
  },
};

export const EmptyHistory: Story = {
  name: 'Probing — no events yet',
  args: {
    pollMs: 0,
    initialNodes: {
      'cloud:openai-prod': { ...mockProbingNode, current_limit: 5 },
    },
    initialHistory: {
      'cloud:openai-prod': [],
    },
  },
};

export const NoCloudNodes: Story = {
  args: {
    pollMs: 0,
    initialNodes: {
      __local__: {
        max_concurrent: 1,
        current_load: 0,
        in_flight_requests: 0,
        current_limit: 1,
        aimd_mode: 'congestion_avoidance',
        state: 'probing',
      },
    },
    initialHistory: {},
  },
};

export const SoftCapBelowCeiling: Story = {
  name: 'User soft-cap below ceiling',
  args: {
    pollMs: 0,
    initialNodes: {
      'cloud:openai-prod': {
        ...mockHealthyNode,
        max_concurrent: 16,
        current_limit: 16,
        discovered_ceiling: 64,
      },
    },
    initialHistory: { 'cloud:openai-prod': sampleEvents },
  },
};
