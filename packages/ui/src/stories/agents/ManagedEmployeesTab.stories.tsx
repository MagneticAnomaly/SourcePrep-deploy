import type { Meta, StoryObj } from '@storybook/react';
import { ManagedEmployeesTab } from '../../components/agents/ManagedEmployeesTab';
import type { RoleBadge } from '../../components/agents/EmployeeBadges';

const meta: Meta<typeof ManagedEmployeesTab> = {
  title: 'Agents/ManagedEmployeesTab',
  component: ManagedEmployeesTab,
  parameters: {
    layout: 'padded',
    docs: { description: { component: 'Roster table for generated agent employees. Shows each role with its doc completion status (AGENTS.md, SOUL.md, KNOWLEDGE.md), plus badges and an add/generate action.' } },
  },
  decorators: [(Story) => <div style={{ maxWidth: 600 }}><Story /></div>],
};

export default meta;
type Story = StoryObj<typeof ManagedEmployeesTab>;

const mockRoles: RoleBadge[] = [
  { slug: 'lead_developer', displayName: 'Lead Developer', hasAgentsMd: true, hasSoulMd: true, hasKnowledgeMd: true },
  { slug: 'security', displayName: 'Security Engineer', hasAgentsMd: true, hasSoulMd: true, hasKnowledgeMd: false },
  { slug: 'ux_designer', displayName: 'UX Designer', hasAgentsMd: true, hasSoulMd: false, hasKnowledgeMd: false },
  { slug: 'devops', displayName: 'DevOps', hasAgentsMd: false, hasSoulMd: false, hasKnowledgeMd: false },
  { slug: 'intern', displayName: 'Intern', hasAgentsMd: true, hasSoulMd: true, hasKnowledgeMd: true },
];

/** Populated roster with 5 roles */
export const WithRoles: Story = {
  args: {
    data: {
      roles: mockRoles,
      readinessScore: 0.73,
      readyForList: true,
      readyForAuto: true,
    },
    onGenerate: (mode, names) => console.log('Generate:', mode, names),
  },
};

/** Empty state — no roles generated yet */
export const Empty: Story = {
  args: {
    data: {
      roles: [],
      readinessScore: 0.45,
      readyForList: false,
      readyForAuto: false,
    },
    onGenerate: (mode, names) => console.log('Generate:', mode, names),
  },
};

/** Ready for auto-generate */
export const ReadyForAuto: Story = {
  args: {
    data: {
      roles: [],
      readinessScore: 0.82,
      readyForList: true,
      readyForAuto: true,
    },
    onGenerate: (mode, names) => console.log('Generate:', mode, names),
  },
};

/** Null state — no data available */
export const NoData: Story = {
  args: { data: null },
};
