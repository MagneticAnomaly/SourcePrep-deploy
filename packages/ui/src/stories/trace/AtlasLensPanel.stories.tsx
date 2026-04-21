import type { Meta, StoryObj } from '@storybook/react';
import { useState } from 'react';
import { AtlasLensPanel } from '../../components/trace/AtlasLensPanel';
import type { AtlasStatus } from '../../types';

const meta: Meta<typeof AtlasLensPanel> = {
  title: 'Trace/AtlasLensPanel',
  component: AtlasLensPanel,
  parameters: { layout: 'padded' },
};

export default meta;
type Story = StoryObj<typeof AtlasLensPanel>;

// ── Fixtures ────────────────────────────────────────────────────────

const now = new Date('2026-04-14T15:00:00Z').toISOString();

const segments = [
  { segment_id: 'seg_src', segment_name: 'src/prep', dir_path: 'src/prep', file_count: 323, char_count: 2100, mode: 'structural' as const, generated_at: now, stale: false },
  { segment_id: 'seg_ui', segment_name: 'packages/ui', dir_path: 'packages/ui', file_count: 291, char_count: 1800, mode: 'structural' as const, generated_at: now, stale: false },
  { segment_id: 'seg_sites', segment_name: 'websites', dir_path: 'websites', file_count: 73, char_count: 800, mode: 'structural' as const, generated_at: now, stale: true },
];

const baseAtlas: AtlasStatus = {
  exists: true,
  content: 'IDENTITY: RunPrep is a multi-segment AI coding assistant platform...\nSTACK: Python 323 files, TypeScript 334 files...',
  mode: 'structural',
  model: 'structural',
  generated_at: now,
  file_count: 687,
  module_count: 18,
  char_count: 4700,
  stale: false,
  segmented: true,
  segments,
};

const roleAtlas: AtlasStatus = {
  ...baseAtlas,
  role: 'engineering',
  role_atlas: `[Software Engineer View]

Modules (scored for engineering relevance):
- src/prep/core/ — indexing + embedding pipeline
- src/prep/services/pipeline/ — orchestration + retry
- packages/ui/src/components/ — dashboard React components
- Key files: server.py, indexer.py, pipeline/orchestrator.py
`,
  role_atlas_chars: 280,
  applied_role: {
    role_id: 'engineering',
    display_name: 'Software Engineer',
    layer_weights: {
      presentation: 0.5,
      business_logic: 0.9,
      data: 0.7,
      infrastructure: 0.4,
      configuration: 0.4,
      testing: 0.5,
      documentation: 0.3,
      build: 0.3,
      unknown: 0.2,
    },
    domain_affinity: ['architecture', 'pipeline', 'orchestration', 'state-management', 'data-persistence', 'error-handling'],
    centrality_weight: 0.4,
    detail_level: 0.8,
    max_chars: 4000,
  },
  override: null,
};

const roleAtlasWithOverride: AtlasStatus = {
  ...roleAtlas,
  applied_role: { ...roleAtlas.applied_role!, max_chars: 2500 },
  override: {
    role_id: 'engineering',
    max_chars: 2500,
    pinned_concept_ids: ['c-auth-decision', 'c-pipeline-rule'],
    updated_at: Date.now() / 1000,
  },
};

// ── Stories ─────────────────────────────────────────────────────────

function Harness({ initial }: { initial: AtlasStatus }) {
  const [role, setRole] = useState<string | null>(initial.role ?? null);
  return (
    <div style={{ height: 700, maxWidth: 900 }}>
      <AtlasLensPanel
        atlas={initial}
        role={role}
        onRoleChange={setRole}
        onRegenerate={() => alert('regenerate triggered')}
      />
    </div>
  );
}

export const Fresh: Story = {
  render: () => <Harness initial={baseAtlas} />,
};

export const StaleWithSegments: Story = {
  render: () => <Harness initial={{ ...baseAtlas, stale: true }} />,
};

export const NoAtlasYet: Story = {
  render: () => (
    <div style={{ height: 700, maxWidth: 900 }}>
      <AtlasLensPanel
        atlas={{ exists: false, content: null, stale: true, segments: [] }}
        role={null}
        onRoleChange={() => {}}
        onRegenerate={() => alert('regenerate triggered')}
      />
    </div>
  ),
};

export const RoleSelectedDefault: Story = {
  render: () => <Harness initial={roleAtlas} />,
};

export const RoleSelectedWithOverride: Story = {
  render: () => <Harness initial={roleAtlasWithOverride} />,
};

export const RoleProjectionError: Story = {
  render: () => (
    <Harness
      initial={{
        ...baseAtlas,
        role: 'engineering',
        role_atlas_error: 'no epistemic data for role projection',
      }}
    />
  ),
};

function InteractiveHarness() {
  const [role, setRole] = useState<string | null>('engineering');
  const [maxChars, setMaxChars] = useState(4000);
  const [pinnedIds, setPinnedIds] = useState<string[]>(['c-auth-decision', 'c-pipeline-rule']);

  const atlas: AtlasStatus = {
    ...baseAtlas,
    role: role ?? undefined,
    role_atlas: role
      ? `[${role} View]\n\nBudget: ${maxChars.toLocaleString()} chars\nPinned: ${pinnedIds.length} concepts\n\n(Mock projection.)`
      : undefined,
    role_atlas_chars: role ? 120 + pinnedIds.length * 30 : undefined,
    applied_role: role
      ? {
          ...roleAtlas.applied_role!,
          role_id: role,
          max_chars: maxChars,
        }
      : undefined,
    override: role && (maxChars !== 4000 || pinnedIds.length > 0)
      ? { role_id: role, max_chars: maxChars, pinned_concept_ids: pinnedIds, updated_at: Date.now() / 1000 }
      : null,
  };

  return (
    <div style={{ height: 700, maxWidth: 900 }}>
      <AtlasLensPanel
        atlas={atlas}
        role={role}
        onRoleChange={setRole}
        onRegenerate={() => alert('regenerate')}
        getDefaultMaxChars={() => 4000}
        onCommitMaxChars={(_r, chars) => setMaxChars(chars)}
        onResetOverride={() => { setMaxChars(4000); setPinnedIds([]); }}
        onUnpinConcept={(_r, id) => setPinnedIds((prev) => prev.filter(x => x !== id))}
        resolveConceptTitle={(id) => ({
          'c-auth-decision': 'JWT Auth Decision',
          'c-pipeline-rule': 'Pipeline Sequencing Rule',
        }[id])}
      />
    </div>
  );
}

export const InteractiveTuning: Story = {
  name: 'Interactive tuning (Step 7)',
  render: () => <InteractiveHarness />,
};
