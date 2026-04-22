import type { Meta, StoryObj } from '@storybook/react';
import { BugReportModal } from '../../components/console/BugReportModal';
import type { LogEntry } from '../../types';

const meta: Meta<typeof BugReportModal> = {
  title: 'Console/BugReportModal',
  component: BugReportModal,
  parameters: {
    layout: 'fullscreen',
    docs: { description: { component: 'Full bug report modal with severity picker, description/steps fields, diagnostic data preview, and submit/download actions. Auto-attaches platform info and recent logs.' } },
  },
};

export default meta;
type Story = StoryObj<typeof BugReportModal>;

const now = Date.now() / 1000;
const mockLogs: LogEntry[] = [
  { timestamp: now - 120, level: 'INFO', logger: 'prep.server', message: 'SourcePrep daemon started on http://0.0.0.0:8400', created: now - 120 },
  { timestamp: now - 60, level: 'WARNING', logger: 'prep.core.inferred_edges', message: 'Code model slot not configured — skipping AI-powered edge discovery.', created: now - 60 },
  { timestamp: now - 30, level: 'ERROR', logger: 'prep.core.augmenter', message: 'LLM timeout on node "GraphEnrichmentPipeline.tsx" — retrying (attempt 2/3)', created: now - 30 },
  { timestamp: now - 25, level: 'ERROR', logger: 'prep.core.augmenter', message: 'All retries exhausted for GraphEnrichmentPipeline.tsx', created: now - 25 },
  { timestamp: now - 10, level: 'INFO', logger: 'prep.services.pipeline', message: '[SourcePrep] Fast Sync completed in 115.2s ✓', created: now - 10 },
  { timestamp: now - 5, level: 'INFO', logger: 'uvicorn.access', message: 'GET /health 200 OK (1ms)', created: now - 5 },
];

/** Open modal with logs and diagnostics */
export const Open: Story = {
  args: {
    open: true,
    onClose: () => console.log('Close'),
    logs: mockLogs,
    diagnosticData: {
      project: { name: 'SourcePrep', mode: 'active', file_count: 1143 },
      license_tier: 'pro',
      project_status: { building: false, stale: false },
      daemon_version: '0.67.2',
      uptime_seconds: 3600,
    },
  },
};

/** Open modal with no logs */
export const EmptyLogs: Story = {
  args: {
    open: true,
    onClose: () => console.log('Close'),
    logs: [],
  },
};

/** Closed state — renders nothing */
export const Closed: Story = {
  args: {
    open: false,
    onClose: () => console.log('Close'),
    logs: [],
  },
};
