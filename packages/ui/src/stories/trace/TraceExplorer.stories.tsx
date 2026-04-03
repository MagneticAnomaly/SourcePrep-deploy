import type { Meta, StoryObj } from '@storybook/react';
import { TraceExplorer } from '../../components/trace/TraceExplorer';

const meta: Meta<typeof TraceExplorer> = {
  title: 'Trace/TraceExplorer',
  component: TraceExplorer,
  parameters: {
    layout: 'fullscreen',
    docs: { description: { component: 'Interactive code graph explorer — search symbols, browse node details + in/out connections, and navigate through the trace graph. Includes disabled, not-built, and building states.' } },
  },
  decorators: [(Story) => <div style={{ height: 500, display: 'flex' }}><Story /></div>],
};

export default meta;
type Story = StoryObj<typeof TraceExplorer>;

// Mock async handlers that simulate backend responses
const mockSearch = async (_query: string) => ({
  nodes: [
    { id: 'n1', name: 'useProjectManager', kind: 'symbol', file_path: 'src/hooks/useProjectManager.ts', metadata: { symbol_type: 'function', docstring: 'Main project state management hook.' }, span: { start_line: 45, end_line: 120 } },
    { id: 'n2', name: 'ProjectList', kind: 'symbol', file_path: 'src/components/ProjectList.tsx', metadata: { symbol_type: 'function' }, span: { start_line: 12, end_line: 89 } },
    { id: 'n3', name: 'project_crud.py', kind: 'file', file_path: 'src/codrag/services/projects/crud.py', metadata: {}, span: null },
    { id: 'n4', name: 'ProjectConfig', kind: 'symbol', file_path: 'src/codrag/core/config.py', metadata: { symbol_type: 'class' }, span: { start_line: 200, end_line: 280 } },
    { id: 'n5', name: 'build_project', kind: 'symbol', file_path: 'src/codrag/services/pipeline.py', metadata: { symbol_type: 'async_function', docstring: 'Orchestrates the full pipeline build for a project.' }, span: { start_line: 88, end_line: 145 } },
  ],
});

const mockGetNode = async (nodeId: string) => ({
  node: { id: nodeId, name: 'useProjectManager', kind: 'symbol', file_path: 'src/hooks/useProjectManager.ts', language: 'TypeScript', metadata: { symbol_type: 'function', docstring: 'Central hook managing project CRUD, activity toggling, and pipeline status polling. Used by ProjectList and DashboardLayout.' }, span: { start_line: 45, end_line: 120 } },
  in_degree: 8,
  out_degree: 5,
});

const mockGetNeighbors = async (nodeId: string) => ({
  nodes: [
    { id: nodeId, name: 'useProjectManager', kind: 'symbol' },
    { id: 'n-api', name: 'projectApi', kind: 'symbol' },
    { id: 'n-config', name: 'ProjectConfig', kind: 'symbol' },
    { id: 'n-list', name: 'ProjectList', kind: 'symbol' },
    { id: 'n-dash', name: 'DashboardLayout', kind: 'symbol' },
  ],
  edges: [
    { id: 'e1', source: nodeId, target: 'n-api', kind: 'calls' },
    { id: 'e2', source: nodeId, target: 'n-config', kind: 'imports' },
    { id: 'e3', source: 'n-list', target: nodeId, kind: 'imports' },
    { id: 'e4', source: 'n-dash', target: nodeId, kind: 'imports' },
  ],
});

/** Active explorer with graph data */
export const Active: Story = {
  args: {
    traceEnabled: true,
    traceExists: true,
    traceBuilding: false,
    traceCounts: { nodes: 5085, edges: 21767 },
    onSearchTrace: mockSearch,
    onGetNode: mockGetNode,
    onGetNeighbors: mockGetNeighbors,
    onBuildTrace: () => console.log('Build trace'),
    engine: 'rust',
  },
};

/** Disabled state */
export const Disabled: Story = {
  args: {
    traceEnabled: false,
    traceExists: false,
    traceBuilding: false,
    traceCounts: { nodes: 0, edges: 0 },
    onSearchTrace: mockSearch,
    onGetNode: mockGetNode,
    onGetNeighbors: mockGetNeighbors,
    onBuildTrace: () => {},
    onEnableTrace: () => console.log('Enable trace'),
  },
};

/** Not built yet */
export const NotBuilt: Story = {
  args: {
    traceEnabled: true,
    traceExists: false,
    traceBuilding: false,
    traceCounts: { nodes: 0, edges: 0 },
    onSearchTrace: mockSearch,
    onGetNode: mockGetNode,
    onGetNeighbors: mockGetNeighbors,
    onBuildTrace: () => console.log('Build'),
  },
};

/** Currently building */
export const Building: Story = {
  args: {
    traceEnabled: true,
    traceExists: false,
    traceBuilding: true,
    traceCounts: { nodes: 0, edges: 0 },
    progress: { task_id: 'trace-build', status: 'running' as const, percent: 45, message: 'Parsing symbols...', current: 230, total: 512 },
    onSearchTrace: mockSearch,
    onGetNode: mockGetNode,
    onGetNeighbors: mockGetNeighbors,
    onBuildTrace: () => {},
  },
};

/** Python engine fallback with degraded state (nodes but no edges) */
export const PythonFallback: Story = {
  args: {
    traceEnabled: true,
    traceExists: true,
    traceBuilding: false,
    traceCounts: { nodes: 320, edges: 0 },
    onSearchTrace: mockSearch,
    onGetNode: mockGetNode,
    onGetNeighbors: async () => ({ nodes: [], edges: [] }),
    onBuildTrace: () => {},
    engine: 'python',
  },
};
