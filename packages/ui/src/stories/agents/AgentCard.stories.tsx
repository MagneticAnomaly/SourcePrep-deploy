import type { Meta, StoryObj } from '@storybook/react';
import { AgentCard } from '../../components/agents/AgentCard';
import { Users, BookOpen, Archive } from 'lucide-react';

const meta: Meta<typeof AgentCard> = {
  title: 'Dashboard/Agents/AgentCard',
  component: AgentCard,
  parameters: {
    layout: 'padded',
    docs: { description: { component: 'Compact card showing one SourcePrep agent\u2019s status \u2014 name, status badge, key metric, and last run timestamp. Used inside AgentOpsPanel.' } },
  },
  decorators: [(Story) => <div style={{ maxWidth: 320 }}><Story /></div>],
};

export default meta;
type Story = StoryObj<typeof AgentCard>;

/** HR Agent — roles generated, fresh status */
export const HR: Story = {
  args: {
    name: 'HR Agent',
    description: 'Generates role-specific agent personas from the Codebase Atlas.',
    icon: <Users className="w-5 h-5" />,
    status: 'fresh',
    metric: '5',
    metricLabel: 'roles generated',
    lastRun: new Date(Date.now() - 3600000).toISOString(),
    actionLabel: 'Generate',
    onAction: () => console.log('Run HR'),
  },
};

/** Researcher Agent — active/building */
export const Researcher: Story = {
  args: {
    name: 'Researcher',
    description: 'Deep-dives into opaque modules using LLM chat loops.',
    icon: <BookOpen className="w-5 h-5" />,
    status: 'building',
    metric: '3',
    metricLabel: 'runs completed',
    lastRun: new Date(Date.now() - 7200000).toISOString(),
    actionLabel: 'Run',
    onAction: () => console.log('Run Researcher'),
  },
};

/** Custodian Agent — pending state */
export const Custodian: Story = {
  args: {
    name: 'Custodian',
    description: 'Archives observations and compresses knowledge for persistent memory.',
    icon: <Archive className="w-5 h-5" />,
    status: 'pending',
    metric: '12',
    metricLabel: 'items archived',
    lastRun: null,
  },
};

/** Disabled agent */
export const Disabled: Story = {
  args: {
    name: 'Inactive Agent',
    description: 'This agent is currently disabled.',
    icon: <Users className="w-5 h-5" />,
    status: 'disabled',
    metric: '0',
    metricLabel: 'runs',
    lastRun: null,
  },
};
