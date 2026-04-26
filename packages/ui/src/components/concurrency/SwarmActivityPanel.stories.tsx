import type { Meta, StoryObj } from '@storybook/react';
import { SwarmActivityPanel } from './SwarmActivityPanel';
import type { RunningTask } from '../../types';

// Phase 119 verbose-logging: developer-popover panel that lists all
// active swarms with coordinator / worker / synthesizer breakdown.
// Used to live inline in the sidebar AI Gateway; moved here because
// per-role rows are debugging detail, not status for end users.

const meta: Meta<typeof SwarmActivityPanel> = {
  title: 'Pipeline/SwarmActivityPanel',
  component: SwarmActivityPanel,
  tags: ['autodocs'],
  parameters: {
    layout: 'centered',
    docs: {
      description: {
        component:
          'Phase 119 — lists all currently-running swarms with their three-phase role breakdown (coordinator/workers/synthesizer). Empty role buckets are suppressed so audit-style swarms (no coordinator, no synthesizer) only show the workers row. Lives in the AI Gateway developer popover behind the wrench icon.',
      },
    },
  },
};

export default meta;
type Story = StoryObj<typeof SwarmActivityPanel>;

const PROJECT: Pick<RunningTask, 'project_id' | 'project_name' | 'group'> = {
  project_id: 'proj-linuxbrain',
  project_name: 'LinuxBrain',
  group: 'enrichment',
};

export const Empty: Story = {
  name: 'No active swarms',
  args: {
    runningTasks: [],
  },
};

export const ThreePhaseSwarm: Story = {
  name: 'Three-phase swarm (coordinator + workers + synth)',
  args: {
    runningTasks: [
      {
        task_id: 'group_reasoning',
        ...PROJECT,
        stage: 'group_reasoning',
        model_slot: 'large',
        concurrent_workers: 7,
        compute_node: 'cloud:default_ollama',
        is_swarm: true,
        swarm_phases: {
          coordinator: { active: 1, model: 'claude-sonnet-4.6' },
          workers: { active: 5, model: 'kimi-k2.5:cloud' },
          synthesizer: { active: 1, model: 'claude-sonnet-4.6' },
        },
      },
    ],
  },
};

export const FanOutOnly: Story = {
  name: 'Audit-style fan-out (workers only, no coord/synth)',
  args: {
    runningTasks: [
      {
        task_id: 'audit',
        ...PROJECT,
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
};

export const MultipleConcurrentSwarms: Story = {
  name: 'Two projects swarming in parallel',
  args: {
    runningTasks: [
      {
        task_id: 'group_reasoning',
        project_id: 'proj-1',
        project_name: 'LinuxBrain',
        group: 'enrichment',
        stage: 'group_reasoning',
        model_slot: 'large',
        concurrent_workers: 7,
        is_swarm: true,
        swarm_phases: {
          coordinator: { active: 1, model: 'claude-sonnet-4.6' },
          workers: { active: 5, model: 'kimi-k2.5:cloud' },
          synthesizer: { active: 1, model: 'claude-sonnet-4.6' },
        },
      },
      {
        task_id: 'clustering',
        project_id: 'proj-2',
        project_name: 'click-python',
        group: 'enrichment',
        stage: 'clustering',
        model_slot: 'large',
        concurrent_workers: 4,
        is_swarm: true,
        swarm_phases: {
          coordinator: { active: 1, model: 'qwen3:14b' },
          workers: { active: 3, model: 'qwen3:14b' },
          synthesizer: { active: 0, model: null },
        },
      },
    ],
  },
};
