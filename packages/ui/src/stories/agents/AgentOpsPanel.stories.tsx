import type { Meta, StoryObj } from '@storybook/react';
import { AgentOpsPanel, type AgentOpsData } from '../../components/agents/AgentOpsPanel';

const meta: Meta<typeof AgentOpsPanel> = {
  title: 'Agents/AgentOpsPanel',
  component: AgentOpsPanel,
  parameters: {
    layout: 'padded',
    docs: { description: { component: 'Config-only Agent Operations panel: engine controls, Paperclip connection, push settings.' } },
  },
};

export default meta;
type Story = StoryObj<typeof AgentOpsPanel>;

const activeData: AgentOpsData = {
  hr: { last_run: '2 hours ago', push_count: 5 },
  researcher: { last_run: '45 min ago', push_count: 3 },
  custodian: { last_run: '1 day ago', push_count: 0 },
};

const emptyData: AgentOpsData = {
  hr: { last_run: null, push_count: 0 },
  researcher: { last_run: null, push_count: 0 },
  custodian: { last_run: null, push_count: 0 },
};

/** Active engines with recent runs and push counts */
export const Active: Story = {
  args: {
    data: activeData,
    loading: false,
    onHRGenerate: () => console.log('HR Generate'),
    onResearchRun: () => console.log('Research Run'),
    onCustodianRun: () => console.log('Custodian Run'),
    pushSettings: { auto_push: true, min_significance: 'recommended', paperclip_project: '' },
    onPushSettingsUpdate: (s) => console.log('Push settings update', s),
  },
};

/** Empty state — no engines have run yet */
export const Empty: Story = {
  args: {
    data: emptyData,
    loading: false,
    onHRGenerate: () => console.log('HR Generate'),
    onResearchRun: () => console.log('Research Run'),
    onCustodianRun: () => console.log('Custodian Run'),
    pushSettings: { auto_push: false, min_significance: 'recommended', paperclip_project: '' },
  },
};

/** Loading state */
export const Loading: Story = {
  args: {
    data: null,
    loading: true,
  },
};
