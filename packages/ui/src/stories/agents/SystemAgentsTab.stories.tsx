import type { Meta, StoryObj } from '@storybook/react';
import { SystemAgentsTab } from '../../components/agents/SystemAgentsTab';

const meta: Meta<typeof SystemAgentsTab> = {
  title: 'Agents/SystemAgentsTab',
  component: SystemAgentsTab,
  parameters: {
    layout: 'padded',
    docs: { description: { component: 'Per-agent configuration panel for the three built-in CoDRAG agents: HR (Staffing), Researcher, and Digital Custodian. Shows readiness scores, run stats, and action buttons.' } },
  },
  decorators: [(Story) => <div style={{ maxWidth: 600 }}><Story /></div>],
};

export default meta;
type Story = StoryObj<typeof SystemAgentsTab>;

const weekAgo = new Date(Date.now() - 7 * 86400000).toISOString();

/** All agents active with data */
export const Active: Story = {
  args: {
    data: {
      hr: {
        readiness: { score: 0.85, ready_for_list: true, ready_for_auto: true, missing: [] },
        roleCount: 5,
      },
      researcher: {
        runCount: 12,
        latestRun: weekAgo,
      },
      custodian: {
        archiveCount: 42,
      },
    },
    onResearchRun: (n) => console.log('Research run:', n),
    onCustodianRun: (dry) => console.log('Custodian run, dry:', dry),
  },
};

/** Fresh setup — no runs yet */
export const Fresh: Story = {
  args: {
    data: {
      hr: {
        readiness: { score: 0.42, ready_for_list: false, ready_for_auto: false, missing: ['Atlas not generated', 'Module synthesis incomplete'] },
        roleCount: 0,
      },
      researcher: {
        runCount: 0,
        latestRun: null,
      },
      custodian: {
        archiveCount: 0,
      },
    },
    onResearchRun: (n) => console.log('Research run:', n),
    onCustodianRun: (dry) => console.log('Custodian run, dry:', dry),
  },
};

/** No data available */
export const NoData: Story = {
  args: { data: null },
};
