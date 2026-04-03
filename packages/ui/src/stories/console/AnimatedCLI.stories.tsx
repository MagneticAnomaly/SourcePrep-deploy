import type { Meta, StoryObj } from '@storybook/react';
import { AnimatedCLI } from '../../components/console/AnimatedCLI';
import { codragSearchDemo, codragImpactDemo, codragOverviewDemo } from '../../components/console/demo-scripts';

const meta: Meta<typeof AnimatedCLI> = {
  title: 'Console/AnimatedCLI',
  component: AnimatedCLI,
  parameters: {
    layout: 'padded',
    docs: { description: { component: 'Auto-animated terminal playback showing CoDRAG MCP tool calls in action.' } },
  },
};

export default meta;
type Story = StoryObj<typeof AnimatedCLI>;

/** Semantic search demo — shows codrag_search in action */
export const SemanticSearch: Story = {
  args: {
    script: codragSearchDemo,
    autoPlay: true,
    theme: 'dark',
  },
};

/** Impact analysis demo — shows codrag_impact */
export const ImpactAnalysis: Story = {
  args: {
    script: codragImpactDemo,
    autoPlay: true,
    theme: 'dark',
  },
};

/** Overview demo — shows codrag ambient context */
export const ProjectOverview: Story = {
  args: {
    script: codragOverviewDemo,
    autoPlay: true,
    theme: 'dark',
  },
};

/** Claude theme variant */
export const ClaudeTheme: Story = {
  args: {
    script: codragSearchDemo,
    autoPlay: true,
    theme: 'claude',
  },
};
