import type { Meta, StoryObj } from '@storybook/react';
import { TraceGraph, TraceGraphMini } from '../../components/trace/TraceGraph';
import type { TraceNode } from '../../components/trace/TraceGraph';

const meta: Meta<typeof TraceGraph> = {
  title: 'Dashboard/Trace/Graph',
  component: TraceGraph,
  tags: ['autodocs'],
  parameters: {
    layout: 'padded',
  },
};

export default meta;
type Story = StoryObj<typeof TraceGraph>;

const mockNodes: TraceNode[] = [
  { id: '1', name: 'App.tsx', kind: 'file', language: 'TypeScript', inDegree: 0, outDegree: 5 },
  { id: '2', name: 'Button.tsx', kind: 'file', language: 'TypeScript', inDegree: 3, outDegree: 0 },
  { id: '3', name: 'useAuth', kind: 'symbol', inDegree: 2, outDegree: 1 },
  { id: '4', name: '/api/login', kind: 'endpoint', inDegree: 1, outDegree: 0 },
];

export const Default: Story = {
  args: {
    nodes: mockNodes,
    edges: [],
  },
};

export const Selected: Story = {
  args: {
    nodes: mockNodes,
    edges: [],
    selectedNode: '3',
  },
};

export const MiniGraph: StoryObj<typeof TraceGraphMini> = {
  render: () => (
    <div className="w-64">
      <TraceGraphMini nodeCount={150} edgeCount={450} />
    </div>
  ),
};
