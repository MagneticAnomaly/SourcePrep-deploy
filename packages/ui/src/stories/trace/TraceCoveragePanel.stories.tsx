import type { Meta, StoryObj } from '@storybook/react';
import { TraceCoveragePanel } from '../../components/trace/TraceCoveragePanel';
import type { TraceCoverageFile, TraceCoverageSummary } from '../../types';

const now = new Date().toISOString();
const hourAgo = new Date(Date.now() - 3_600_000).toISOString();
const dayAgo = new Date(Date.now() - 86_400_000).toISOString();
const weekAgo = new Date(Date.now() - 604_800_000).toISOString();

const sampleUntraced: TraceCoverageFile[] = [
  { path: 'src/api/handlers.ts', language: 'typescript', size: 4200, modified: hourAgo, created: dayAgo },
  { path: 'src/utils/logger.ts', language: 'typescript', size: 1800, modified: dayAgo, created: weekAgo },
  { path: 'src/core/scheduler.py', language: 'python', size: 6100, modified: hourAgo, created: dayAgo },
  { path: 'src/models/user.py', language: 'python', size: 2400, modified: weekAgo, created: weekAgo },
  { path: 'src/routes/auth.ts', language: 'typescript', size: 3500, modified: dayAgo, created: dayAgo },
];

const sampleStale: TraceCoverageFile[] = [
  { path: 'src/core/index.py', language: 'python', size: 8900, modified: hourAgo, created: weekAgo },
  { path: 'src/api/client.ts', language: 'typescript', size: 5600, modified: hourAgo, created: weekAgo },
];

const sampleExcluded: TraceCoverageFile[] = [
  { path: 'tests/test_api.py', language: 'python', size: 3200, modified: dayAgo, created: weekAgo },
  { path: 'tests/fixtures/mock_data.json', language: null, size: 12000, modified: weekAgo, created: weekAgo },
  { path: 'scripts/deploy.sh', language: null, size: 800, modified: dayAgo, created: weekAgo },
];

const fullSummary: TraceCoverageSummary = {
  total: 42,
  traced: 35,
  untraced: 5,
  stale: 2,
  excluded: 3,
  coverage_pct: 83.3,
  last_build_at: hourAgo,
};

const meta: Meta<typeof TraceCoveragePanel> = {
  title: 'Dashboard/Trace/CoveragePanel',
  component: TraceCoveragePanel,
  tags: ['autodocs'],
  parameters: {
    layout: 'padded',
  },
  argTypes: {
    onTraceAll: { action: 'traceAll' },
    onRetraceStale: { action: 'retraceStale' },
    onAddExcludePattern: { action: 'addExcludePattern' },
    onRemoveExcludePattern: { action: 'removeExcludePattern' },
    onRefresh: { action: 'refresh' },
  },
  decorators: [
    (Story) => (
      <div style={{ maxWidth: 420, height: 600 }}>
        <Story />
      </div>
    ),
  ],
};

export default meta;
type Story = StoryObj<typeof TraceCoveragePanel>;

export const Default: Story = {
  args: {
    summary: fullSummary,
    untracedFiles: sampleUntraced,
    staleFiles: sampleStale,
    excludedFiles: sampleExcluded,
    building: false,
    loading: false,
  },
};

export const Bare: Story = {
  name: 'Bare (Dashboard Mode)',
  args: {
    summary: fullSummary,
    untracedFiles: sampleUntraced,
    staleFiles: sampleStale,
    excludedFiles: sampleExcluded,
    building: false,
    loading: false,
    bare: true,
  },
};

export const Compact: Story = {
  name: 'Compact (Narrow Width)',
  args: {
    summary: fullSummary,
    untracedFiles: sampleUntraced,
    staleFiles: sampleStale,
    excludedFiles: sampleExcluded,
    building: false,
    loading: false,
    bare: true,
  },
  decorators: [
    (Story) => (
      <div style={{ maxWidth: 320, height: 600 }}>
        <Story />
      </div>
    ),
  ],
};

export const FullCoverage: Story = {
  args: {
    summary: {
      total: 50,
      traced: 50,
      untraced: 0,
      stale: 0,
      excluded: 3,
      coverage_pct: 100.0,
      last_build_at: now,
    },
    untracedFiles: [],
    staleFiles: [],
    excludedFiles: sampleExcluded,
    building: false,
    loading: false,
  },
};

export const Building: Story = {
  args: {
    summary: fullSummary,
    untracedFiles: sampleUntraced,
    staleFiles: sampleStale,
    excludedFiles: sampleExcluded,
    building: true,
    loading: false,
  },
};

export const Loading: Story = {
  args: {
    summary: null,
    untracedFiles: [],
    staleFiles: [],
    excludedFiles: [],
    building: false,
    loading: true,
  },
};

export const LowCoverage: Story = {
  args: {
    summary: {
      total: 80,
      traced: 12,
      untraced: 60,
      stale: 8,
      excluded: 5,
      coverage_pct: 15.0,
      last_build_at: weekAgo,
    },
    untracedFiles: [
      ...sampleUntraced,
      { path: 'src/services/payment.ts', language: 'typescript', size: 7200, modified: dayAgo, created: dayAgo },
      { path: 'src/services/email.ts', language: 'typescript', size: 3100, modified: dayAgo, created: weekAgo },
      { path: 'src/middleware/auth.ts', language: 'typescript', size: 2900, modified: hourAgo, created: dayAgo },
      { path: 'src/middleware/rate_limit.ts', language: 'typescript', size: 1500, modified: dayAgo, created: dayAgo },
      { path: 'src/db/migrations.py', language: 'python', size: 4800, modified: weekAgo, created: weekAgo },
    ],
    staleFiles: [
      ...sampleStale,
      { path: 'src/core/embedder.py', language: 'python', size: 9200, modified: hourAgo, created: weekAgo },
      { path: 'src/core/chunker.py', language: 'python', size: 6700, modified: hourAgo, created: weekAgo },
    ],
    excludedFiles: sampleExcluded,
    building: false,
    loading: false,
  },
};

export const NoBuild: Story = {
  name: 'No Previous Build',
  args: {
    summary: {
      total: 30,
      traced: 0,
      untraced: 30,
      stale: 0,
      excluded: 0,
      coverage_pct: 0,
      last_build_at: null,
    },
    untracedFiles: sampleUntraced,
    staleFiles: [],
    excludedFiles: [],
    building: false,
    loading: false,
  },
};
