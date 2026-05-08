import type { Meta, StoryObj } from '@storybook/react';
import { WatchControlPanel } from '../../components/watch/WatchControlPanel';
import { WatchStatusIndicator } from '../../components/watch/WatchStatusIndicator';
import type { WatchStatus } from '../../types';

const meta: Meta<typeof WatchControlPanel> = {
  title: 'Dashboard/Watch/WatchControls',
  component: WatchControlPanel,
  tags: ['autodocs'],
  parameters: {
    layout: 'padded',
  },
};

export default meta;
type Story = StoryObj<typeof WatchControlPanel>;

const disabledStatus: WatchStatus = {
  enabled: false,
  state: 'disabled',
  stale: false,
  pending: false,
  debounce_ms: 5000,
  stale_since: null,
  pending_paths_count: 0,
  next_rebuild_at: null,
  last_event_at: null,
  last_rebuild_at: null,
};

const idleStatus: WatchStatus = {
  enabled: true,
  state: 'idle',
  stale: false,
  pending: false,
  debounce_ms: 5000,
  stale_since: null,
  pending_paths_count: 0,
  next_rebuild_at: null,
  last_event_at: null,
  last_rebuild_at: null,
};

const staleStatus: WatchStatus = {
  enabled: true,
  state: 'idle',
  stale: true,
  pending: false,
  debounce_ms: 5000,
  stale_since: new Date(Date.now() - 1000 * 60).toISOString(),
  pending_paths_count: 3,
  next_rebuild_at: null,
  last_event_at: null,
  last_rebuild_at: null,
};

const debouncingStatus: WatchStatus = {
  enabled: true,
  state: 'debouncing',
  stale: true,
  pending: true,
  debounce_ms: 5000,
  stale_since: new Date(Date.now() - 1000 * 30).toISOString(),
  pending_paths_count: 5,
  next_rebuild_at: '2026-02-05T15:01:00Z',
  last_event_at: new Date().toISOString(),
  last_rebuild_at: null,
};

const buildingStatus: WatchStatus = {
  enabled: true,
  state: 'building',
  stale: false,
  pending: false,
  debounce_ms: 5000,
  stale_since: null,
  pending_paths_count: 0,
  next_rebuild_at: null,
  last_event_at: new Date().toISOString(),
  last_rebuild_at: null,
};

export const Disabled: Story = {
  args: {
    status: disabledStatus,
    onStartWatch: () => console.log('start'),
    onStopWatch: () => console.log('stop'),
  },
};

export const Watching: Story = {
  args: {
    status: idleStatus,
    onStartWatch: () => console.log('start'),
    onStopWatch: () => console.log('stop'),
  },
};

export const Stale: Story = {
  args: {
    status: staleStatus,
    onStartWatch: () => console.log('start'),
    onStopWatch: () => console.log('stop'),
    onRebuildNow: () => console.log('rebuild'),
  },
};

export const Debouncing: Story = {
  args: {
    status: debouncingStatus,
    onStartWatch: () => console.log('start'),
    onStopWatch: () => console.log('stop'),
    onRebuildNow: () => console.log('rebuild'),
  },
};

export const Building: Story = {
  args: {
    status: buildingStatus,
    onStartWatch: () => console.log('start'),
    onStopWatch: () => console.log('stop'),
  },
};

export const Loading: Story = {
  args: {
    status: disabledStatus,
    onStartWatch: () => console.log('start'),
    onStopWatch: () => console.log('stop'),
    loading: true,
  },
};

export const IndicatorOnly: StoryObj<typeof WatchStatusIndicator> = {
  render: () => (
    <div className="space-y-4">
      <WatchStatusIndicator status={disabledStatus} />
      <WatchStatusIndicator status={idleStatus} />
      <WatchStatusIndicator status={staleStatus} onRebuildNow={() => {}} showDetails />
      <WatchStatusIndicator status={debouncingStatus} showDetails />
      <WatchStatusIndicator status={buildingStatus} />
    </div>
  ),
};
