import type { Meta, StoryObj } from '@storybook/react';
import { useState } from 'react';
import { DeepAnalysisSettings } from '../../components/llm/DeepAnalysisSettings';
import type { DeepAnalysisSchedule } from '../../components/llm/DeepAnalysisSettings';

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
    />
  ),
};

export const Threshold: Story = {
  render: () => (
    <Wrapper
      initialSchedule={{
        ...defaultSchedule,
        mode: 'scheduled',
        threshold_percent: 30,
      }}
    />
  ),
};

export const WithStatus: Story = {
  render: () => (
    <Wrapper />
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
        />
      </div>
    );
  },
};

export const Running: Story = {
  render: () => (
    <Wrapper />
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
    />
  ),
};
