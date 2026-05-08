import type { Meta, StoryObj } from '@storybook/react';
import { useState } from 'react';
import { AdvancedLLMSettings } from '../../components/llm/AdvancedLLMSettings';
import type { AdvancedLLMSettings as AdvancedSettings } from '../../types';

const meta: Meta<typeof AdvancedLLMSettings> = {
  title: 'Dashboard/LLM/AdvancedLLMSettings',
  component: AdvancedLLMSettings,
  tags: ['autodocs'],
  parameters: {
    layout: 'padded',
  },
};

export default meta;
type Story = StoryObj<typeof AdvancedLLMSettings>;

function Wrapper({ initialValue }: { initialValue: AdvancedSettings }) {
  const [value, setValue] = useState<AdvancedSettings>(initialValue);
  return (
    <div className="max-w-md">
      <AdvancedLLMSettings value={value} onChange={setValue} />
    </div>
  );
}

export const Default: Story = {
  render: () => (
    <Wrapper
      initialValue={{
        enforce_cloud_token_safety: true,
        max_thinking_budget: 24576,
      }}
    />
  ),
};
