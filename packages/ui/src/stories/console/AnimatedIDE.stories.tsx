import type { Meta, StoryObj } from '@storybook/react';
import { AnimatedIDE } from '../../components/console/AnimatedIDE';
import { ideDemoScript } from '../../components/console/demo-scripts';

const meta: Meta<typeof AnimatedIDE> = {
  title: 'Console/AnimatedIDE',
  component: AnimatedIDE,
  parameters: {
    layout: 'fullscreen',
    docs: { description: { component: 'Simulated IDE split-view with a code editor (left) and an agent chat sidebar (right). Demonstrates SourcePrep MCP tool calls within an agentic IDE workflow.' } },
  },
};

export default meta;
type Story = StoryObj<typeof AnimatedIDE>;

/** Full IDE demo — file open, code edit, MCP tool calls */
export const Default: Story = {
  args: {
    script: ideDemoScript,
    autoPlay: true,
  },
};

/** Paused — shows the IDE in its initial idle state */
export const Paused: Story = {
  args: {
    script: ideDemoScript,
    autoPlay: false,
  },
};
