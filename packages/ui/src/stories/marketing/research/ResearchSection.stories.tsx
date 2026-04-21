import type { Meta, StoryObj } from '@storybook/react';
import { ResearchSection } from '../../../components/marketing/research/ResearchSection';
import { RESEARCH_SOURCES } from '../../../data/researchSources';

const meta: Meta<typeof ResearchSection> = {
  title: 'Website/Marketing/Research/ResearchSection',
  component: ResearchSection,
  parameters: { layout: 'padded' },
  tags: ['autodocs'],
};

export default meta;
type Story = StoryObj<typeof ResearchSection>;

export const Retrieval: Story = {
  args: {
    id: 'retrieval',
    title: 'Retrieval & Long Context',
    intro:
      'Why context engineering matters more than raw context size — and what changes when language models meet long, noisy windows.',
    sources: RESEARCH_SOURCES.filter((s) => s.problemArea === 'retrieval'),
  },
};

export const Compression: Story = {
  args: {
    id: 'compression',
    title: 'Compression & Levels of Detail',
    intro:
      'Why Prep\u2019s context assembler ladders code from full source down to one-line signatures.',
    sources: RESEARCH_SOURCES.filter((s) => s.problemArea === 'compression'),
  },
};

export const Concepts: Story = {
  args: {
    id: 'concepts',
    title: 'Concepts, Knowledge & Standards',
    intro:
      'Why Prep treats concepts as first-class artifacts and where the protocol surface comes from.',
    sources: RESEARCH_SOURCES.filter((s) => s.problemArea === 'concepts'),
  },
};
