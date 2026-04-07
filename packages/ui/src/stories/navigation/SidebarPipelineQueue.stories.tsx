import type { Meta, StoryObj } from '@storybook/react';
import { useEffect } from 'react';
import { SidebarPipelineQueue } from '../../components/navigation/SidebarPipelineQueue';
import type { QueueItem } from '../../components/navigation/SidebarPipelineQueue';

/**
 * Mock fetch to return queue data for Storybook.
 * The component polls `${baseUrl}/system/pipeline-queue`.
 */
function withMockQueue(items: QueueItem[]) {
  return function Decorator(Story: React.ComponentType) {
    useEffect(() => {
      const origFetch = window.fetch;
      window.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = typeof input === 'string' ? input : input.toString();
        if (url.includes('/system/pipeline-queue')) {
          return new Response(JSON.stringify({
            data: { queue: items, nodes: {}, ghost_locks_purged: 0 },
          }), { status: 200, headers: { 'Content-Type': 'application/json' } });
        }
        return origFetch(input, init);
      }) as typeof fetch;
      return () => { window.fetch = origFetch; };
    }, []);
    return <Story />;
  };
}

const meta: Meta<typeof SidebarPipelineQueue> = {
  title: 'Application/Navigation/SidebarPipelineQueue',
  component: SidebarPipelineQueue,
  tags: ['autodocs'],
  parameters: { layout: 'centered' },
  args: { baseUrl: 'http://localhost:8400' },
  decorators: [
    (Story) => (
      <div className="w-[260px] bg-surface border border-border rounded-lg p-1">
        <Story />
      </div>
    ),
  ],
};

export default meta;
type Story = StoryObj<typeof SidebarPipelineQueue>;

// ── Mock data ────────────────────────────────────────────────────

const runningConcurrent: QueueItem = {
  project_id: 'p1',
  project_name: 'LinuxBrain',
  group: 'fast_sync',
  phase: 'running',
  current_stage: 'catalogue',
  started_at: Date.now() / 1000 - 120,
  elapsed_seconds: 120,
  wait_seconds: null,
  priority: 'exclusive',
  compute_node: 'cloud:default_ollama',
  concurrent_workers: 10,
  is_swarm: false,
};

const runningSwarming: QueueItem = {
  project_id: 'p2',
  project_name: 'CoDRAG',
  group: 'deep_enrichment',
  phase: 'running',
  current_stage: 'group_reasoning',
  started_at: Date.now() / 1000 - 45,
  elapsed_seconds: 45,
  wait_seconds: null,
  priority: 'boost',
  compute_node: 'cloud:default_ollama',
  concurrent_workers: 10,
  is_swarm: true,
};

const queued: QueueItem = {
  project_id: 'p3',
  project_name: 'Website',
  group: 'fast_sync',
  phase: 'queued',
  current_stage: null,
  started_at: null,
  elapsed_seconds: null,
  wait_seconds: 30,
  priority: 'none',
  compute_node: null,
  concurrent_workers: 1,
};

// ── Stories ───────────────────────────────────────────────────────

export const Empty: Story = {
  decorators: [withMockQueue([])],
};

export const ConcurrentBuild: Story = {
  decorators: [withMockQueue([runningConcurrent])],
};

export const SwarmBuild: Story = {
  decorators: [withMockQueue([runningSwarming])],
};

export const MixedQueue: Story = {
  decorators: [withMockQueue([runningConcurrent, runningSwarming, queued])],
};

export const SwarmVsConcurrent: Story = {
  name: 'Swarm vs Concurrent comparison',
  decorators: [withMockQueue([
    { ...runningConcurrent, project_name: 'Project A (concurrent)', concurrent_workers: 3, is_swarm: false },
    { ...runningSwarming, project_name: 'Project B (swarm)', concurrent_workers: 3, is_swarm: true },
  ])],
};
