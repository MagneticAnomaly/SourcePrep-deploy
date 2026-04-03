import type { Meta, StoryObj } from '@storybook/react';
import { TeamSyncIndicator } from '../../components/team/TeamSyncIndicator';

const meta: Meta<typeof TeamSyncIndicator> = {
  title: 'Team/TeamSyncIndicator',
  component: TeamSyncIndicator,
  parameters: {
    layout: 'centered',
    docs: { description: { component: 'Compact pill badge showing team remote sync status — syncing, synced, behind, error, or disabled. Includes hover tooltip with details.' } },
  },
};

export default meta;
type Story = StoryObj<typeof TeamSyncIndicator>;

const now = Date.now() / 1000;

/** Synced — up to date */
export const Synced: Story = {
  args: {
    status: {
      enabled: true, is_syncing: false, error: null,
      last_sync_at: now - 300, last_sync_commit: 'a1b2c3d4e5f6789012345678',
      remote_version: 42, remote_timestamp: now - 300, behind_minutes: 0,
    },
  },
};

/** Syncing — in progress */
export const Syncing: Story = {
  args: {
    status: {
      enabled: true, is_syncing: true, error: null,
      last_sync_at: now - 3600, last_sync_commit: 'abc123def456',
      remote_version: 43, remote_timestamp: now - 60, behind_minutes: null,
    },
  },
};

/** Behind — remote has newer data */
export const Behind: Story = {
  args: {
    status: {
      enabled: true, is_syncing: false, error: null,
      last_sync_at: now - 7200, last_sync_commit: 'abc123def456',
      remote_version: 43, remote_timestamp: now - 60, behind_minutes: 120,
    },
  },
};

/** Error state */
export const Error: Story = {
  args: {
    status: {
      enabled: true, is_syncing: false, error: 'S3 bucket access denied — check AWS credentials.',
      last_sync_at: now - 86400, last_sync_commit: 'abc123def456',
      remote_version: null, remote_timestamp: null, behind_minutes: null,
    },
  },
};

/** Disabled — returns null */
export const Disabled: Story = {
  args: {
    status: {
      enabled: false, is_syncing: false, error: null,
      last_sync_at: null, last_sync_commit: '',
      remote_version: null, remote_timestamp: null, behind_minutes: null,
    },
  },
};
