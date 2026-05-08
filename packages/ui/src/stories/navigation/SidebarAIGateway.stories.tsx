import type { Meta, StoryObj } from '@storybook/react';
import { SidebarAIGateway } from '../../components/navigation/SidebarAIGateway';
import type { LLMSlotsStatus, RunningTask, LLMSlotStatus } from '../../types';

const meta: Meta<typeof SidebarAIGateway> = {
  title: 'Dashboard/Pipeline/SidebarAIGateway',
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
  project_name: 'Acme Search',
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
  project_name: 'Acme Search',
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

/**
 * Phase 119 Swarm Authority: when the orchestrator runs a real
 * coordinator → fan-out → synthesizer pattern, the AI Gateway shows
 * the high-level "Swarm" badge + worker count.
 *
 * Phase 119 amendment: the per-role coordinator/worker/synthesizer
 * breakdown that USED to render inline here was moved to
 * **Settings → Diagnostics**.  The sidebar itself only surfaces the
 * badge + count, which is what end users need.
 */
export const SwarmThreePhaseBreakdown: Story = {
  name: 'Swarm badge + count (per-role rows now in Settings → Diagnostics)',
  args: {
    slotsStatus: {
      ...baseSlots,
      running_task_id: 'group_reasoning',
      running_tasks: [
        {
          ...swarmTask,
          concurrent_workers: 7,
          swarm_phases: {
            coordinator: { active: 1, model: 'claude-sonnet-4.6' },
            workers: { active: 5, model: 'kimi-k2.5:cloud' },
            synthesizer: { active: 1, model: 'claude-sonnet-4.6' },
          },
        },
      ],
    },
  },
};

/**
 * Phase 119 Swarm Authority — fan-out only.
 *
 * Some "swarm-capable" stages (notably ``audit``) open a swarm window
 * but never run a coordinator or synthesizer LLM call.  The
 * Settings → Diagnostics ``SwarmActivityPanel`` surfaces only the
 * bucket that has actual work, so an audit-style swarm shows
 * "Workers ×5" rather than three rows with two at zero.  The sidebar
 * still shows the high-level badge.
 */
/**
 * Phase 119+ — separately-configured Swarm Coordinator.
 *
 * When the user disables ``inherit_from_large`` and assigns a distinct
 * endpoint+model to the coordinator slot (e.g. Qwen3.6-Plus on
 * OpenRouter while workers run Kimi 2.6 on Ollama Cloud), the sidebar
 * surfaces a fifth row labelled ``Coordinator`` between Thinking and
 * Code.  The default inherit-from-large case still hides the row —
 * see ``SwarmRunning`` above.
 */
export const SwarmWithSeparateCoordinator: Story = {
  name: 'Swarm with separate Coordinator (Qwen3.6-Plus + Kimi 2.6)',
  args: {
    slotsStatus: {
      ...baseSlots,
      large_model: { ...connectedSlot, model: 'kimi-k2.6:cloud', provider: 'ollama' },
      coordinator_model: {
        configured: true,
        enabled: true,
        model: 'qwen/qwen3.6-plus',
        provider: 'openai-compatible',
        status: 'connected',
        model_available: true,
      },
      running_task_id: 'group_reasoning',
      running_tasks: [
        {
          task_id: 'group_reasoning',
          project_id: 'p2',
          project_name: 'SourcePrep',
          group: 'deep_enrichment',
          stage: 'group_reasoning',
          model_slot: 'large',
          concurrent_workers: 10,
          compute_node: 'cloud:default_ollama',
          is_swarm: true,
          swarm_role: 'worker',
        },
        {
          task_id: 'group_reasoning',
          project_id: 'p2',
          project_name: 'SourcePrep',
          group: 'deep_enrichment',
          stage: 'group_reasoning',
          model_slot: 'coordinator',
          concurrent_workers: 1,
          compute_node: 'cloud:openrouter',
          is_swarm: true,
          swarm_role: 'coordinator',
        },
      ],
    },
  },
};

export const SwarmFanOutOnly: Story = {
  name: 'Swarm window open but only workers active (Settings → Diagnostics)',
  args: {
    slotsStatus: {
      ...baseSlots,
      running_task_id: 'audit',
      running_tasks: [
        {
          task_id: 'audit',
          project_id: 'p1',
          project_name: 'Acme Search',
          group: 'enrichment',
          stage: 'audit',
          model_slot: 'large',
          concurrent_workers: 5,
          compute_node: 'cloud:default_ollama',
          is_swarm: true,
          swarm_phases: {
            coordinator: { active: 0, model: null },
            workers: { active: 5, model: 'claude-sonnet-4.6' },
            synthesizer: { active: 0, model: null },
          },
        },
      ],
    },
  },
};
