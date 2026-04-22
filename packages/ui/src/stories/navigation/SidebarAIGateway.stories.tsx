import type { Meta, StoryObj } from '@storybook/react';
import { SidebarAIGateway } from '../../components/navigation/SidebarAIGateway';
import type { LLMSlotsStatus, RunningTask, LLMSlotStatus } from '../../types';

const meta: Meta<typeof SidebarAIGateway> = {
  title: 'Application/Navigation/SidebarAIGateway',
  component: SidebarAIGateway,
  tags: ['autodocs'],
  parameters: { layout: 'centered' },
  decorators: [
    (Story) => (
      <div className="w-[260px] bg-surface border border-border rounded-lg p-1">
        <Story />
      </div>
    ),
  ],
};

export default meta;
type Story = StoryObj<typeof SidebarAIGateway>;

// ── Mock data ────────────────────────────────────────────────────

const connectedSlot: LLMSlotStatus = {
  configured: true,
  enabled: true,
  model: 'kimi-k2.5:cloud',
  provider: 'ollama',
  status: 'connected',
  model_available: true,
};

const disabledSlot: LLMSlotStatus = {
  configured: true,
  enabled: false,
  model: 'qwen3-coder:30b',
  provider: 'ollama',
  status: 'connected',
  model_available: true,
};

const localEmbedding: LLMSlotStatus = {
  configured: true,
  enabled: true,
  source: 'huggingface',
  status: 'local',
};

const baseSlots: LLMSlotsStatus = {
  assignment_mode: 'structured',
  running_task_id: null,
  running_tasks: [],
  embedding: localEmbedding,
  small_model: connectedSlot,
  large_model: { ...connectedSlot, model: 'claude-sonnet-4.6', provider: 'anthropic' },
  code_model: disabledSlot,
};

const concurrentTask: RunningTask = {
  task_id: 'catalogue',
  project_id: 'p1',
  project_name: 'LinuxBrain',
  group: 'fast_sync',
  stage: 'catalogue',
  model_slot: 'small',
  concurrent_workers: 10,
  compute_node: 'cloud:default_ollama',
  is_swarm: false,
};

const swarmTask: RunningTask = {
  task_id: 'group_reasoning',
  project_id: 'p2',
  project_name: 'SourcePrep',
  group: 'deep_enrichment',
  stage: 'group_reasoning',
  model_slot: 'large',
  concurrent_workers: 10,
  compute_node: 'cloud:default_ollama',
  is_swarm: true,
};

const clusteringSwarm: RunningTask = {
  task_id: 'clustering',
  project_id: 'p1',
  project_name: 'LinuxBrain',
  group: 'deep_enrichment',
  stage: 'clustering',
  model_slot: 'large',
  concurrent_workers: 5,
  compute_node: 'cloud:default_ollama',
  is_swarm: true,
};

// ── Stories ───────────────────────────────────────────────────────

export const Idle: Story = {
  args: { slotsStatus: baseSlots },
};

export const ConcurrentRunning: Story = {
  args: {
    slotsStatus: {
      ...baseSlots,
      running_task_id: 'catalogue',
      running_tasks: [concurrentTask],
    },
  },
};

export const SwarmRunning: Story = {
  args: {
    slotsStatus: {
      ...baseSlots,
      running_task_id: 'group_reasoning',
      running_tasks: [swarmTask],
    },
  },
};

export const SwarmVsConcurrent: Story = {
  name: 'Swarm vs Concurrent (both running)',
  args: {
    slotsStatus: {
      ...baseSlots,
      running_task_id: 'catalogue',
      running_tasks: [concurrentTask, swarmTask],
    },
  },
};

export const MultipleSwarmStages: Story = {
  name: 'Multiple swarm stages',
  args: {
    slotsStatus: {
      ...baseSlots,
      running_task_id: 'group_reasoning',
      running_tasks: [swarmTask, clusteringSwarm],
    },
  },
};

export const CollapsedConcurrent: Story = {
  args: {
    collapsed: true,
    slotsStatus: {
      ...baseSlots,
      running_task_id: 'catalogue',
      running_tasks: [concurrentTask],
    },
  },
};

export const CollapsedSwarm: Story = {
  args: {
    collapsed: true,
    slotsStatus: {
      ...baseSlots,
      running_task_id: 'group_reasoning',
      running_tasks: [swarmTask],
    },
  },
};

export const LowConcurrencySwarm: Story = {
  name: '3×Swarm (low concurrency)',
  args: {
    slotsStatus: {
      ...baseSlots,
      running_task_id: 'clustering',
      running_tasks: [{
        ...clusteringSwarm,
        concurrent_workers: 3,
      }],
    },
  },
};
