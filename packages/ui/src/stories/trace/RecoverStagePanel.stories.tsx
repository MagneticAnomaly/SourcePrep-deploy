import React from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import { RecoverStagePanel } from '../../components/trace/RecoverStagePanel';
import type { ApiClient } from '../../api/client';
import type { StageBackup, StageBackupsResponse, StageRestoreResponse } from '../../types';

// ── Shared fixtures ───────────────────────────────────────────

const NOW = Date.now() / 1000;

const GOLDEN: StageBackup = {
  snapshot_id: 'golden',
  kind: 'golden',
  branch: null,
  created_at: NOW - 7200,
  size_bytes: 4321,
  file_count: 1,
  record_count: null,
};

const BRANCH_MAIN: StageBackup = {
  snapshot_id: 'main_2026-04-15T12-00-00',
  kind: 'branch',
  branch: 'main',
  created_at: NOW - 86400,
  size_bytes: 8765,
  file_count: 2,
  record_count: null,
};

const BRANCH_FEATURE: StageBackup = {
  snapshot_id: 'feature_foo_2026-04-14T18-30-00',
  kind: 'branch',
  branch: 'feature/foo',
  created_at: NOW - 172800,
  size_bytes: 6543,
  file_count: 2,
  record_count: null,
};

// ── Mock client builders ──────────────────────────────────────

function makeClient(overrides: Partial<Pick<ApiClient, 'listStageBackups' | 'restoreStageFromSnapshot'>> = {}): ApiClient {
  return {
    listStageBackups: async (): Promise<StageBackupsResponse> => ({
      stage_id: 'atlas',
      backups: [GOLDEN, BRANCH_MAIN, BRANCH_FEATURE],
    }),
    restoreStageFromSnapshot: async (_pid: string, stageId: string, snapshotId: string): Promise<StageRestoreResponse> => ({
      restored: true as const,
      stage_id: stageId,
      snapshot_id: snapshotId,
      files_restored: ['atlas_manifest.json'],
    }),
    ...overrides,
  } as unknown as ApiClient;
}

// ── Meta ──────────────────────────────────────────────────────

const meta: Meta<typeof RecoverStagePanel> = {
  title: 'Dashboard/Build/RecoverStagePanel',
  component: RecoverStagePanel,
  tags: ['autodocs'],
  parameters: {
    layout: 'padded',
  },
  args: {
    projectId: 'proj_demo',
    stageId: 'atlas',
    stageLabel: 'Atlas',
    onRestored: (snapshotId: string) => console.log('Restored from', snapshotId),
  },
};

export default meta;
type Story = StoryObj<typeof RecoverStagePanel>;

// ── Stories ───────────────────────────────────────────────────

/** Default: golden + 2 branch snapshots, panel closed. */
export const Default: Story = {
  args: {
    apiClient: makeClient(),
  },
};

/** EmptyBackups: API returns no snapshots — shows helpful empty state. */
export const EmptyBackups: Story = {
  args: {
    apiClient: makeClient({
      listStageBackups: async (): Promise<StageBackupsResponse> => ({
        stage_id: 'atlas',
        backups: [],
      }),
    }),
  },
};

/** Loading: fetch is in flight — shows spinner. */
export const Loading: Story = {
  args: {
    apiClient: makeClient({
      listStageBackups: (): Promise<StageBackupsResponse> =>
        new Promise(() => { /* never resolves — simulates in-flight */ }),
    }),
  },
  // Decorator opens the panel immediately so the loading state is visible
  decorators: [
    (StoryComponent: React.ComponentType) => {
      return (
        <div>
          {/* Note: open state is internal; click the Recover button to see loading */}
          <p className="mb-2 text-xs text-text-muted">Click "Recover…" to see the loading state.</p>
          <StoryComponent />
        </div>
      );
    },
  ],
};

/** LoadError: fetch fails — shows error message. */
export const LoadError: Story = {
  args: {
    apiClient: makeClient({
      listStageBackups: async (): Promise<StageBackupsResponse> => {
        throw new Error('Network error: connection refused');
      },
    }),
  },
};

/** Restoring: POST in flight — shows in-progress indicator. */
export const Restoring: Story = {
  args: {
    apiClient: makeClient({
      restoreStageFromSnapshot: (): Promise<StageRestoreResponse> =>
        new Promise(() => { /* never resolves — simulates in-flight POST */ }),
    }),
  },
};

/** Disabled: pipeline is running this stage — button is greyed out. */
export const Disabled: Story = {
  args: {
    apiClient: makeClient(),
    disabled: true,
  },
};
