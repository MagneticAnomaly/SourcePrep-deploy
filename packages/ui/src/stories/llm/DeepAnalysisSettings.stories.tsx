import type { Meta, StoryObj } from '@storybook/react';
import { useState } from 'react';
import { DeepAnalysisSettings } from '../../components/llm/DeepAnalysisSettings';
import type { DeepAnalysisSchedule, DeepAnalysisStatus } from '../../components/llm/DeepAnalysisSettings';

const meta: Meta<typeof DeepAnalysisSettings> = {
  title: 'Dashboard/Widgets/Settings/DeepAnalysisSettings',
  component: DeepAnalysisSettings,
  tags: ['autodocs'],
  parameters: {
    layout: 'padded',
  },
};

export default meta;
type Story = StoryObj<typeof DeepAnalysisSettings>;

const defaultSchedule: DeepAnalysisSchedule = {
  mode: 'manual',
  threshold_percent: 20,
  frequency: 'weekly',
  day_of_week: 0,
  hour: 2,
  budget_enabled: true,
  budget_max_tokens: 50_000,
  budget_max_minutes: 30,
  budget_max_items: 100,
  priority: 'lowest_confidence',
};

const sampleStatus: DeepAnalysisStatus = {
  last_run_at: '2025-02-10T14:30:00Z',
  last_run_items: 47,
  last_run_tokens: 23_450,
  next_run_at: '2025-02-17T02:00:00Z',
  queue_size: 128,
  avg_confidence: 0.72,
};

function Wrapper({
  initialSchedule = defaultSchedule,
  ...props
}: Partial<React.ComponentProps<typeof DeepAnalysisSettings>> & {
  initialSchedule?: DeepAnalysisSchedule;
}) {
  const [schedule, setSchedule] = useState(initialSchedule);
  return (
    <div className="max-w-md">
      <DeepAnalysisSettings
        schedule={schedule}
        onScheduleChange={setSchedule}
        largeModelConfigured
        {...props}
      />
    </div>
  );
}

export const Manual: Story = {
  render: () => <Wrapper />,
};

export const Scheduled: Story = {
  render: () => (
    <Wrapper
      initialSchedule={{
        ...defaultSchedule,
        mode: 'scheduled',
        frequency: 'weekly',
        day_of_week: 1,
        hour: 3,
      }}
      status={sampleStatus}
    />
  ),
};

export const Threshold: Story = {
  render: () => (
    <Wrapper
      initialSchedule={{
        ...defaultSchedule,
        mode: 'threshold',
        threshold_percent: 30,
      }}
    />
  ),
};

export const WithStatus: Story = {
  render: () => (
    <Wrapper
      status={sampleStatus}
      onRunNow={() => alert('Running deep analysis...')}
    />
  ),
};

export const NoModel: Story = {
  render: () => {
    const [schedule, setSchedule] = useState(defaultSchedule);
    return (
      <div className="max-w-md">
        <DeepAnalysisSettings
          schedule={schedule}
          onScheduleChange={setSchedule}
          largeModelConfigured={false}
          onRunNow={() => {}}
        />
      </div>
    );
  },
};

export const Running: Story = {
  render: () => (
    <Wrapper
      status={sampleStatus}
      running
      onRunNow={() => {}}
    />
  ),
};

export const LargeQueue: Story = {
  render: () => (
    <Wrapper
      initialSchedule={{
        ...defaultSchedule,
        mode: 'scheduled',
        frequency: 'daily',
      }}
      status={{
        ...sampleStatus,
        queue_size: 1247,
        avg_confidence: 0.45,
      }}
      onRunNow={() => alert('Running...')}
    />
  ),
};
