import type { Meta, StoryObj } from '@storybook/react';
import { NodeDetailPanel } from '../../components/trace/NodeDetailPanel';
import type { TraceNode } from '../../types';

const meta: Meta<typeof NodeDetailPanel> = {
  title: 'Dashboard/Trace/NodeDetailPanel',
  component: NodeDetailPanel,
  tags: ['autodocs'],
  parameters: {
    layout: 'fullscreen', // Panel usually takes full height
  },
  decorators: [
    (Story) => (
      <div className="h-[600px] relative bg-background border border-border">
        <div className="absolute right-0 top-0 bottom-0">
          <Story />
        </div>
      </div>
    ),
  ],
};

export default meta;
type Story = StoryObj<typeof NodeDetailPanel>;

const mockNode: TraceNode = {
  id: 'src/components/Button.tsx',
  name: 'Button',
  kind: 'file',
  file_path: 'src/components/Button.tsx',
  language: 'TypeScript',
  span: { start_line: 10, end_line: 45 },
  metadata: {
    is_public: true,
    docstring: 'A flexible button component with variants.',
    decorators: ['memo'],
  },
};

export const FileNode: Story = {
  args: {
    node: mockNode,
    inEdges: [
      { id: 'e1', source: 'src/App.tsx', target: 'src/components/Button.tsx', kind: 'imports', metadata: { confidence: 1 } },
      { id: 'e2', source: 'src/components/Form.tsx', target: 'src/components/Button.tsx', kind: 'imports', metadata: { confidence: 1 } },
    ],
    outEdges: [
      { id: 'e3', source: 'src/components/Button.tsx', target: 'react', kind: 'imports', metadata: { confidence: 1 } },
    ],
  },
};

export const SymbolNode: Story = {
  args: {
    node: {
      ...mockNode,
      id: 'Button.handleClick',
      name: 'handleClick',
      kind: 'symbol',
      metadata: {
        symbol_type: 'method',
        is_async: true,
        is_public: false,
      },
    },
    inEdges: [],
    outEdges: [],
  },
};
