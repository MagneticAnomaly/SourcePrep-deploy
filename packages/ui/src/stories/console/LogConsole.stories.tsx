import type { Meta, StoryObj } from '@storybook/react';
import { LogConsole } from '../../components/console/LogConsole';
import type { LogEntry } from '../../types';

const meta: Meta<typeof LogConsole> = {
  title: 'Dashboard/Console/LogConsole',
  component: LogConsole,
  parameters: {
    layout: 'fullscreen',
    docs: { description: { component: 'Live log console with multi-select filter buttons (Pipeline, Info, Warning, Error, HTTP), auto-scroll, and integrated Bug Report modal. Streams backend daemon events in real-time.' } },
  },
  decorators: [
    (Story) => (
      <div style={{ height: '400px', display: 'flex', flexDirection: 'column' }}>
        <Story />
      </div>
    ),
  ],
};

export default meta;
type Story = StoryObj<typeof LogConsole>;

const baseTime = Date.now() / 1000;
const mockLogs: LogEntry[] = [
  { timestamp: baseTime - 120, level: 'INFO', logger: 'prep.server', message: 'Prep daemon started on http://0.0.0.0:8400', created: baseTime - 120 },
  { timestamp: baseTime - 115, level: 'INFO', logger: 'prep.server', message: 'Loaded 3 projects: Prep, Halley, demo-app', created: baseTime - 115 },
  { timestamp: baseTime - 100, level: 'INFO', logger: 'prep.services.pipeline', message: '[Prep] Fast Sync starting: structural → inferred_edges → catalogue → validation → knowledge', created: baseTime - 100 },
  { timestamp: baseTime - 95, level: 'INFO', logger: 'prep.services.pipeline', message: '[Prep] Stage 1/5: structural — scanning 1143 files', created: baseTime - 95 },
  { timestamp: baseTime - 80, level: 'INFO', logger: 'prep.services.pipeline', message: '[Prep] Stage 1/5: structural — traced 847 files, 5085 nodes, 21767 edges (12.4s)', created: baseTime - 80 },
  { timestamp: baseTime - 75, level: 'INFO', logger: 'prep.services.pipeline', message: '[Prep] Stage 2/5: inferred_edges — discovering hidden relationships', created: baseTime - 75 },
  { timestamp: baseTime - 60, level: 'WARNING', logger: 'prep.core.inferred_edges', message: 'Code model slot not configured — skipping AI-powered edge discovery. Using heuristic fallback.', created: baseTime - 60 },
  { timestamp: baseTime - 55, level: 'INFO', logger: 'prep.services.pipeline', message: '[Prep] Stage 3/5: catalogue — augmenting 812 nodes', created: baseTime - 55 },
  { timestamp: baseTime - 40, level: 'INFO', logger: 'prep.core.augmenter', message: 'Augmented 780/812 nodes (96.1%), avg confidence: 0.85', created: baseTime - 40 },
  { timestamp: baseTime - 35, level: 'ERROR', logger: 'prep.core.augmenter', message: 'LLM timeout on node "GraphEnrichmentPipeline.tsx" — retrying with reduced context (attempt 2/3)', created: baseTime - 35 },
  { timestamp: baseTime - 30, level: 'INFO', logger: 'prep.core.augmenter', message: 'Retry succeeded for GraphEnrichmentPipeline.tsx', created: baseTime - 30 },
  { timestamp: baseTime - 25, level: 'INFO', logger: 'prep.services.pipeline', message: '[Prep] Stage 4/5: validation — checking 21767 edges', created: baseTime - 25 },
  { timestamp: baseTime - 15, level: 'INFO', logger: 'prep.services.pipeline', message: '[Prep] Stage 5/5: knowledge — embedding 4200 chunks', created: baseTime - 15 },
  { timestamp: baseTime - 5, level: 'INFO', logger: 'prep.services.pipeline', message: '[Prep] Fast Sync completed in 115.2s ✓', created: baseTime - 5 },
  { timestamp: baseTime - 3, level: 'INFO', logger: 'uvicorn.access', message: 'GET /projects/abc123/pipeline/status 200 OK (2ms)', created: baseTime - 3 },
  { timestamp: baseTime - 2, level: 'INFO', logger: 'uvicorn.access', message: 'GET /health 200 OK (1ms)', created: baseTime - 2 },
];

/** Logs from a typical pipeline run */
export const PipelineRun: Story = {
  args: {
    logs: mockLogs,
    onClear: () => console.log('Clear logs'),
  },
};

/** Empty console — no logs yet */
export const Empty: Story = {
  args: {
    logs: [],
    onClear: () => console.log('Clear logs'),
  },
};

/** Error-heavy logs */
export const WithErrors: Story = {
  args: {
    logs: [
      ...mockLogs,
      { timestamp: baseTime, level: 'ERROR', logger: 'prep.core.embeddings', message: 'OpenAI API key invalid — embedding request rejected (401 Unauthorized)', created: baseTime },
      { timestamp: baseTime + 1, level: 'CRITICAL', logger: 'prep.server', message: 'Unhandled exception in /projects/abc123/build — see logs above', created: baseTime + 1 },
      { timestamp: baseTime + 2, level: 'ERROR', logger: 'prep.core.watcher', message: 'FSEvents watcher for /Volumes/4TB-BAD/HumanAI/Prep failed: Permission denied', created: baseTime + 2 },
    ],
    onClear: () => console.log('Clear logs'),
  },
};
