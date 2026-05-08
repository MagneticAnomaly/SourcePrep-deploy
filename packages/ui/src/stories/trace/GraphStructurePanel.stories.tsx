import type { Meta, StoryObj } from '@storybook/react';
import { GraphStructurePanel } from '../../components/trace/GraphStructurePanel';
import type { TraceCoverageSummary, TraceCoverageFile, EpistemicStatus, AugmentationStatus, ModuleStatus, KnowledgeEmbeddingStatus } from '../../types';

const meta: Meta<typeof GraphStructurePanel> = {
  title: 'Dashboard/Trace/GraphStructurePanel',
  component: GraphStructurePanel,
  parameters: {
    layout: 'fullscreen',
    docs: { description: { component: 'Code Graph structure panel showing trace coverage (file-level and deep enrichment), untraced/stale file queues, and exclude pattern management. Per-path include/exclude now lives in the Scope panel (FolderTreePanel).' } },
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
type Story = StoryObj<typeof GraphStructurePanel>;

const now = new Date().toISOString();
const hourAgo = new Date(Date.now() - 3600000).toISOString();

const mockSummary: TraceCoverageSummary = {
  total: 847,
  traced: 812,
  untraced: 23,
  stale: 12,
  excluded: 45,
  coverage_pct: 95.9,
  pending_embedding: 8,
  last_build_at: hourAgo,
};

const mockEpistemic: EpistemicStatus = {
  enabled: true,
  enriched_nodes: 680,
  total_file_nodes: 812,
  avg_confidence: 0.82,
  running: false,
  pipeline_running: false,
};

const mockAugmentation: AugmentationStatus = {
  enabled: true,
  total_nodes: 812,
  augmented_nodes: 780,
  validated_nodes: 620,
  avg_confidence: 0.85,
  low_confidence_count: 42,
};

const mockModuleStatus: ModuleStatus = {
  enabled: true,
  module_count: 17,
  total_files_clustered: 812,
  running: false,
};

const mockKnowledge: KnowledgeEmbeddingStatus = {
  enabled: true,
  running: false,
  chunks_embedded: 4200,
  deep_chunks_embedded: 1800,
  last_run_at: hourAgo,
};

const makeFile = (path: string, lang: string): TraceCoverageFile => ({
  path, language: lang, size: 1024, modified: hourAgo, created: now,
});

const untracedFiles: TraceCoverageFile[] = [
  makeFile('src/prep/core/new_feature.py', 'python'),
  makeFile('src/prep/api/webhooks.py', 'python'),
  makeFile('packages/ui/src/components/new/Widget.tsx', 'typescript'),
];

const staleFiles: TraceCoverageFile[] = [
  makeFile('src/prep/core/embeddings.py', 'python'),
  makeFile('src/prep/mcp/routes.py', 'python'),
];

const excludedFiles: TraceCoverageFile[] = [
  makeFile('node_modules/react/index.js', 'javascript'),
  makeFile('dist/bundle.js', 'javascript'),
];

const noop = () => {};

/** Full panel with coverage bars, untraced/stale queues */
export const WithData: Story = {
  args: {
    summary: mockSummary,
    epistemic: mockEpistemic,
    augmentation: mockAugmentation,
    moduleStatus: mockModuleStatus,
    knowledgeStatus: mockKnowledge,
    untracedFiles,
    staleFiles,
    excludedFiles,
    building: false,
    loading: false,
    traceExists: true,
    onTraceAll: noop,
    onRetraceStale: noop,
    onAddExcludePattern: noop,
    onRemoveExcludePattern: noop,
    onRefresh: noop,
  },
};

/** Building state — pipeline in progress */
export const Building: Story = {
  args: {
    summary: { ...mockSummary, coverage_pct: 99.9 },
    epistemic: { ...mockEpistemic, pipeline_running: true },
    augmentation: mockAugmentation,
    moduleStatus: mockModuleStatus,
    knowledgeStatus: mockKnowledge,
    untracedFiles: [],
    staleFiles: [],
    excludedFiles,
    building: true,
    progress: { task_id: 'trace', message: 'Tracing file 47/50...', current: 47, total: 50, percent: 94, status: 'running' },
    loading: false,
    traceExists: true,
    onTraceAll: noop,
    onRetraceStale: noop,
    onAddExcludePattern: noop,
    onRemoveExcludePattern: noop,
    onRefresh: noop,
  },
};

/** All traced — empty queue */
export const AllTraced: Story = {
  args: {
    summary: { ...mockSummary, untraced: 0, stale: 0, coverage_pct: 100 },
    epistemic: mockEpistemic,
    untracedFiles: [],
    staleFiles: [],
    excludedFiles: [],
    building: false,
    loading: false,
    traceExists: true,
    onTraceAll: noop,
    onRetraceStale: noop,
    onAddExcludePattern: noop,
    onRemoveExcludePattern: noop,
    onRefresh: noop,
  },
};
