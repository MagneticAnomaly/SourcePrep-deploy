import type { Meta, StoryObj } from '@storybook/react';
import { ResearchAppendix } from '../../../components/marketing/research/ResearchAppendix';
import { RESEARCH_SOURCES } from '../../../data/researchSources';

const meta: Meta<typeof ResearchAppendix> = {
  title: 'Website/Marketing/Research/ResearchAppendix',
  component: ResearchAppendix,
  parameters: { layout: 'padded' },
  tags: ['autodocs'],
};

export default meta;
type Story = StoryObj<typeof ResearchAppendix>;

const retrievalAppendix = RESEARCH_SOURCES.filter(
  (s) => s.problemArea === 'retrieval' && !s.spotlight,
);
const conceptsAppendix = RESEARCH_SOURCES.filter(
  (s) => s.problemArea === 'concepts' && !s.spotlight,
);

export const Retrieval: Story = {
  args: { sources: retrievalAppendix },
};

export const Concepts: Story = {
  args: { sources: conceptsAppendix },
};

export const Empty: Story = {
  args: { sources: [] },
};
