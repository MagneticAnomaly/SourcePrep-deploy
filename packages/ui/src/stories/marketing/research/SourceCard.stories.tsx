import type { Meta, StoryObj } from '@storybook/react';
import { SourceCard } from '../../../components/marketing/research/SourceCard';
import { RESEARCH_SOURCES } from '../../../data/researchSources';

const meta: Meta<typeof SourceCard> = {
  title: 'Website/Marketing/Research/SourceCard',
  component: SourceCard,
  parameters: { layout: 'centered' },
  tags: ['autodocs'],
  decorators: [
    (Story) => (
      <div style={{ width: 320 }}>
        <Story />
      </div>
    ),
  ],
};

export default meta;
type Story = StoryObj<typeof SourceCard>;

const findById = (id: string) => {
  const s = RESEARCH_SOURCES.find((x) => x.id === id);
  if (!s) throw new Error(`Story fixture missing source "${id}"`);
  return s;
};

export const Paper: Story = { args: { source: findById('lost-in-the-middle') } };
export const Repo: Story = { args: { source: findById('aider') } };
export const Essay: Story = { args: { source: findById('anthropic-contextual-retrieval') } };
export const Spec: Story = { args: { source: findById('mcp-spec') } };
export const Book: Story = { args: { source: findById('seci-model') } };
