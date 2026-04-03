import type { Meta, StoryObj } from '@storybook/react';
import { AgentScopePanel } from '../../components/agents/AgentScopePanel';
import type { TreeNode } from '../../components/project/FolderTree';

const meta: Meta<typeof AgentScopePanel> = {
  title: 'Agents/AgentScopePanel',
  component: AgentScopePanel,
  parameters: {
    layout: 'padded',
    docs: { description: { component: 'Per-agent file tree selection panel. Each Paperclip agent gets a curated Knowledge Scope to ensure focused, hallucination-free context retrieval.' } },
  },
  decorators: [
    (Story) => (
      <div style={{ height: '600px', display: 'flex', flexDirection: 'column' }}>
        <Story />
      </div>
    ),
  ],
};

export default meta;
type Story = StoryObj<typeof AgentScopePanel>;

// Mock file tree — TreeNode uses type: 'file' | 'folder', no 'path' prop
const mockTree: TreeNode[] = [
  {
    name: 'src',
    type: 'folder',
    children: [
      {
        name: 'api',
        type: 'folder',
        children: [
          { name: 'routes.py', type: 'file', status: 'indexed', chunks: 24 },
          { name: 'middleware.py', type: 'file', status: 'indexed', chunks: 12 },
          { name: 'auth.py', type: 'file', status: 'indexed', chunks: 15 },
        ],
      },
      {
        name: 'services',
        type: 'folder',
        children: [
          { name: 'payment.py', type: 'file', status: 'indexed', chunks: 31 },
          { name: 'billing.py', type: 'file', status: 'indexed', chunks: 20 },
          { name: 'notifications.py', type: 'file', status: 'indexed', chunks: 8 },
        ],
      },
      {
        name: 'models',
        type: 'folder',
        children: [
          { name: 'user.py', type: 'file', status: 'indexed', chunks: 6 },
          { name: 'order.py', type: 'file', status: 'indexed', chunks: 9 },
          { name: 'product.py', type: 'file', status: 'indexed', chunks: 5 },
        ],
      },
    ],
  },
  {
    name: 'tests',
    type: 'folder',
    children: [
      { name: 'test_api.py', type: 'file', status: 'indexed', chunks: 14 },
      { name: 'test_services.py', type: 'file', status: 'indexed', chunks: 22 },
    ],
  },
  {
    name: 'docs',
    type: 'folder',
    children: [
      { name: 'README.md', type: 'file', status: 'indexed', chunks: 8 },
      { name: 'architecture.md', type: 'file', status: 'indexed', chunks: 28 },
    ],
  },
];

// Mock scopes
const mockScopes = {
  roles: ['CEO', 'Security Lead', 'DevOps'],
  scopes: {
    'CEO': ['src/api', 'src/services', 'docs'],
    'Security Lead': ['src/api/auth.py', 'src/api/middleware.py'],
    'DevOps': ['tests', 'docs'],
  },
};

const noopAsync = async () => {};

/** With scopes configured for multiple agents */
export const WithScopes: Story = {
  args: {
    projectId: 'demo-project',
    data: mockTree,
    onFetchScopes: async () => mockScopes,
    onSetScope: noopAsync,
    onAddPaths: noopAsync,
    onRemovePaths: noopAsync,
    onDeleteScope: noopAsync,
    onAutoPopulate: async (_pid: string, role: string) => ({
      role,
      resolved_as: role.toLowerCase().replace(/\s+/g, '_'),
      recommended_paths: ['src/api', 'src/services'],
      scored: [
        { path: 'src/api', score: 0.92, layer: 'api', tags: ['auth', 'routing'] },
        { path: 'src/services', score: 0.87, layer: 'domain', tags: ['payments', 'billing'] },
      ],
      count: 2,
      total_scored: 12,
      applied: true,
      elapsed_ms: 340,
    }),
    bare: true,
  },
};

/** Empty state — no project selected */
export const NoProject: Story = {
  args: {
    projectId: null,
    data: mockTree,
    onFetchScopes: async () => ({ roles: [], scopes: {} }),
    onSetScope: noopAsync,
    onAddPaths: noopAsync,
    onRemovePaths: noopAsync,
    onDeleteScope: noopAsync,
    bare: true,
  },
};
