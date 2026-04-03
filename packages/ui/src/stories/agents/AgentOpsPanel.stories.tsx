import type { Meta, StoryObj } from '@storybook/react';
import { AgentOpsPanel, type AgentOpsData } from '../../components/agents/AgentOpsPanel';

const meta: Meta<typeof AgentOpsPanel> = {
  title: 'Agents/AgentOpsPanel',
  component: AgentOpsPanel,
  parameters: {
    layout: 'padded',
    docs: { description: { component: 'Agent Operations dashboard panel showing the three CoDRAG agents (HR, Researcher, Custodian) with action buttons and managed employee badges.' } },
  },
};

export default meta;
type Story = StoryObj<typeof AgentOpsPanel>;

const activeData: AgentOpsData = {
  hr: {
    role_count: 5,
    roles: ['CEO', 'CTO', 'UX Designer', 'DevOps', 'Security Lead'],
  },
  researcher: {
    run_count: 3,
    latest_run: new Date(Date.now() - 3600000).toISOString(),
  },
  custodian: {
    archive_count: 12,
  },
  roster: [
    { slug: 'ceo', displayName: 'CEO', hasAgentsMd: true, hasSoulMd: true, hasKnowledgeMd: true },
    { slug: 'cto', displayName: 'CTO', hasAgentsMd: true, hasSoulMd: true, hasKnowledgeMd: true },
    { slug: 'ux_designer', displayName: 'UX Designer', hasAgentsMd: true, hasSoulMd: true, hasKnowledgeMd: false },
    { slug: 'devops', displayName: 'DevOps', hasAgentsMd: true, hasSoulMd: false, hasKnowledgeMd: false },
    { slug: 'security_lead', displayName: 'Security Lead', hasAgentsMd: true, hasSoulMd: false, hasKnowledgeMd: false },
  ],
};

const emptyData: AgentOpsData = {
  hr: { role_count: 0, roles: [] },
  researcher: { run_count: 0, latest_run: null },
  custodian: { archive_count: 0 },
};

/** Active agents with roles generated and research runs completed */
export const Active: Story = {
  args: {
    data: activeData,
    loading: false,
    onHRGenerate: () => console.log('HR Generate'),
    onResearchRun: () => console.log('Research Run'),
    onCustodianRun: () => console.log('Custodian Run'),
  },
};

/** Empty state — no agents have been used yet */
export const Empty: Story = {
  args: {
    data: emptyData,
    loading: false,
    onHRGenerate: () => console.log('HR Generate'),
    onResearchRun: () => console.log('Research Run'),
    onCustodianRun: () => console.log('Custodian Run'),
  },
};

/** Loading state */
export const Loading: Story = {
  args: {
    data: null,
    loading: true,
  },
};
