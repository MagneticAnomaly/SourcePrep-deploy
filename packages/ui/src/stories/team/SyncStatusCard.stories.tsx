import type { Meta, StoryObj } from '@storybook/react';
import { SyncStatusCard } from '../../components/team/SyncStatusCard';

const meta: Meta<typeof SyncStatusCard> = {
  title: 'Team/SyncStatusCard',
  component: SyncStatusCard,
  parameters: {
    layout: 'padded',
    docs: { description: { component: 'Expanded sync status card with icon, description, last-synced timestamp, remote commit hash, and a Sync Now button. Used in team settings.' } },
  },
  decorators: [(Story) => <div style={{ maxWidth: 520 }}><Story /></div>],
};

export default meta;
type Story = StoryObj<typeof SyncStatusCard>;

const now = Date.now() / 1000;

/** Up to date — last synced recently */
export const UpToDate: Story = {
  args: {
    status: {
      enabled: true, is_syncing: false, error: null,
      last_sync_at: now - 300, last_sync_commit: 'a1b2c3d4e5f6789012345678',
      remote_version: 42, remote_timestamp: now - 300, behind_minutes: 0,
    },
    onSyncNow: () => console.log('Sync now'),
  },
};

/** Currently syncing */
export const Syncing: Story = {
  args: {
    status: {
      enabled: true, is_syncing: true, error: null,
      last_sync_at: now - 3600, last_sync_commit: 'abc123def456',
      remote_version: 43, remote_timestamp: now - 60, behind_minutes: null,
    },
    onSyncNow: () => console.log('Sync now'),
  },
};

/** Remote is ahead */
export const RemoteAhead: Story = {
  args: {
    status: {
      enabled: true, is_syncing: false, error: null,
      last_sync_at: now - 7200, last_sync_commit: 'abc123def456',
      remote_version: 43, remote_timestamp: now - 60, behind_minutes: 120,
    },
    onSyncNow: () => console.log('Sync now'),
  },
};

/** Error state */
export const Error: Story = {
  args: {
    status: {
      enabled: true, is_syncing: false, error: 'AWS credentials expired — run `aws configure` to refresh.',
      last_sync_at: now - 86400, last_sync_commit: 'abc123def456',
      remote_version: null, remote_timestamp: null, behind_minutes: null,
    },
    onSyncNow: () => console.log('Sync now'),
  },
};
