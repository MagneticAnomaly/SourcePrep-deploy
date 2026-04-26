import type { Meta, StoryObj } from '@storybook/react';
import {
  RecentSwarmLogs,
  type SwarmLogEvent,
  type SwarmLogFile,
} from './RecentSwarmLogs';

// Phase 119 verbose-logging — recent swarm logs browser. Lives in the
// AI Gateway developer popover behind the wrench. Replaces the prior
// static "Per-swarm event logs at: …" footer with a dynamic, expandable
// list backed by GET /system/swarm-events.

const meta: Meta<typeof RecentSwarmLogs> = {
  title: 'Pipeline/RecentSwarmLogs',
  component: RecentSwarmLogs,
  tags: ['autodocs'],
  parameters: {
    layout: 'centered',
    docs: {
      description: {
        component:
          'Phase 119 — developer-mode recent swarm logs panel. Polls GET /system/swarm-events for the file listing while the popover is open and lets the user expand any row to inspect the parsed JSONL events inline. Intended to replace the previous static path footer in the AI Gateway dev popover.',
      },
    },
  },
};

export default meta;
type Story = StoryObj<typeof RecentSwarmLogs>;

const NOW = Math.floor(Date.now() / 1000);

const SAMPLE_FILES: SwarmLogFile[] = [
  {
    name: 'swarm_20260426_124035_concept_seeding_run-demo.jsonl',
    size: 2640,
    mtime: NOW - 60 * 3,
  },
  {
    name: 'swarm_20260426_122001_group_reasoning_a1b2c3d4.jsonl',
    size: 5180,
    mtime: NOW - 60 * 12,
  },
  {
    name: 'swarm_20260426_120015_clustering_77ee99aa.jsonl',
    size: 1240,
    mtime: NOW - 60 * 30,
  },
  {
    name: 'swarm_20260426_115500_audit_swarm_deadbeef.jsonl',
    size: 920,
    mtime: NOW - 60 * 45,
  },
  {
    name: 'swarm_20260426_113000_atlas_swarm_cafef00d.jsonl',
    size: 4072,
    mtime: NOW - 60 * 75,
  },
];

// Sample JSONL fixture matching the spec for
// swarm_20260426_124035_concept_seeding_run-demo.jsonl.
const SAMPLE_EVENTS: SwarmLogEvent[] = [
  {
    ts: NOW - 60 * 3 - 12,
    elapsed_s: 0.0,
    kind: 'session_start',
    run_id: 'run-demo',
    stage: 'concept_seeding',
    project_id: 'proj-demo',
  },
  {
    ts: NOW - 60 * 3 - 12,
    elapsed_s: 0.05,
    kind: 'phase_start',
    phase: 'coordinator',
    model: 'claude-sonnet-4.6',
    n_items: 4,
  },
  {
    ts: NOW - 60 * 3 - 10,
    elapsed_s: 1.85,
    kind: 'phase_end',
    phase: 'coordinator',
    success: true,
    duration_s: 1.8,
    tokens: 942,
  },
  {
    ts: NOW - 60 * 3 - 10,
    elapsed_s: 1.9,
    kind: 'worker_dispatch',
    worker_id: 'w-0',
    item_id: 'group:0',
    model: 'kimi-k2.5:cloud',
    prompt_chars: 482,
  },
  {
    ts: NOW - 60 * 3 - 10,
    elapsed_s: 1.95,
    kind: 'worker_dispatch',
    worker_id: 'w-1',
    item_id: 'group:1',
    model: 'kimi-k2.5:cloud',
    prompt_chars: 510,
  },
  {
    ts: NOW - 60 * 3 - 8,
    elapsed_s: 3.6,
    kind: 'worker_complete',
    worker_id: 'w-0',
    item_id: 'group:0',
    success: true,
    duration_s: 1.7,
    response_chars: 1024,
    parse_ok: true,
  },
  {
    ts: NOW - 60 * 3 - 7,
    elapsed_s: 4.1,
    kind: 'parse_failure',
    where: 'worker:group:1',
    raw_chars: 220,
    reason: 'json_parse_failed',
  },
  {
    ts: NOW - 60 * 3 - 5,
    elapsed_s: 6.0,
    kind: 'phase_start',
    phase: 'synthesizer',
    model: 'claude-sonnet-4.6',
  },
  {
    ts: NOW - 60 * 3 - 4,
    elapsed_s: 7.5,
    kind: 'phase_end',
    phase: 'synthesizer',
    success: true,
    duration_s: 1.5,
    tokens: 540,
  },
  {
    ts: NOW - 60 * 3 - 4,
    elapsed_s: 7.6,
    kind: 'session_end',
    success: true,
    summary: {
      total_items: 4,
      workers_succeeded: 3,
      workers_failed: 1,
      duration_s: 7.6,
    },
  },
];

const FILE_WITH_EVENTS = SAMPLE_FILES[0]!;

export const Empty: Story = {
  name: 'Empty — no logs yet',
  args: {
    initialFiles: [],
  },
};

export const WithFiles: Story = {
  name: 'With files (collapsed)',
  args: {
    initialFiles: SAMPLE_FILES,
  },
};

export const WithExpandedEvents: Story = {
  name: 'One row expanded — JSONL events',
  args: {
    initialFiles: SAMPLE_FILES,
    initialEvents: { [FILE_WITH_EVENTS.name]: SAMPLE_EVENTS },
  },
};

const MANY: SwarmLogFile[] = Array.from({ length: 14 }).map((_, i) => ({
  name: `swarm_20260426_${String(13 - i).padStart(2, '0')}0000_stage_${i}_run${i.toString(16).padStart(8, '0')}.jsonl`,
  size: 1000 + i * 250,
  mtime: NOW - 60 * (i + 1) * 6,
}));

export const ManyFiles: Story = {
  name: 'Many files (trimmed to 10)',
  args: {
    initialFiles: MANY,
  },
};
