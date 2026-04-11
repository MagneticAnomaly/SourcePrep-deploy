import type { Meta, StoryObj } from '@storybook/react';
import { SourceSpotlight } from '../../../components/marketing/research/SourceSpotlight';
import { RESEARCH_SOURCES } from '../../../data/researchSources';

const meta: Meta<typeof SourceSpotlight> = {
  title: 'Website/Marketing/Research/SourceSpotlight',
  component: SourceSpotlight,
  parameters: { layout: 'padded' },
  tags: ['autodocs'],
  decorators: [
    (Story) => (
      <div style={{ maxWidth: 640 }}>
        <Story />
      </div>
    ),
  ],
};

export default meta;
type Story = StoryObj<typeof SourceSpotlight>;

const findById = (id: string) => {
  const s = RESEARCH_SOURCES.find((x) => x.id === id);
  if (!s) throw new Error(`Story fixture missing source "${id}"`);
  return s;
};

export const Paper: Story = { args: { source: findById('lost-in-the-middle') } };
export const Repository: Story = { args: { source: findById('gbrain') } };
export const Essay: Story = { args: { source: findById('anthropic-contextual-retrieval') } };
export const Specification: Story = { args: { source: findById('mcp-spec') } };
export const Book: Story = { args: { source: findById('seci-model') } };
