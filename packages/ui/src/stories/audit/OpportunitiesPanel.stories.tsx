import { useState } from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import { OpportunitiesPanel, type OpportunitiesPanelProps, type OpportunityItem, type OpportunitiesSummary } from '../../components/audit/OpportunitiesPanel';

const meta: Meta<typeof OpportunitiesPanel> = {
  title: 'Audit/OpportunitiesPanel',
  component: OpportunitiesPanel,
  parameters: {
    layout: 'fullscreen',
    docs: { description: { component: 'Unified codebase improvement opportunities console. Shows health findings, spaghetti scores, advisor proposals, and TODO items with priority/category/source filters and multi-format export.' } },
  },
  decorators: [
    (Story) => (
      <div style={{ height: '700px', display: 'flex', flexDirection: 'column' }}>
        <Story />
      </div>
    ),
  ],
};

export default meta;
type Story = StoryObj<typeof OpportunitiesPanel>;

const now = new Date().toISOString();

const mockItems: OpportunityItem[] = [
  {
    id: 'OPP-001',
    title: 'Extract pipeline stage components from GraphEnrichmentPipeline',
    description: 'The 58KB monolith file handles all 9 stages inline. Splitting into individual stage components would improve maintainability and reduce coupling.',
    category: 'architecture',
    priority: 'P0',
    severity: 'critical',
    effort: 'large',
    source: 'health',
    analyzer: 'large_files',
    state: 'active',
    affected_files: ['packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx'],
    suggested_action: 'Create trace/stages/ directory with one component per pipeline stage.',
    evidence: 'File size: 58,301 bytes, 1,247 lines',
    mcp_command: 'prep_audit action="refactor" finding_ids=["SIZE-1"]',
    created_at: now,
    dismissed_at: '',
  },
  {
    id: 'OPP-002',
    title: 'Break circular dependency between search and trace modules',
    description: 'SearchPanel imports TraceGraph, TraceExplorer imports SearchResultsList — bidirectional dependency creates tight coupling.',
    category: 'architecture',
    priority: 'P1',
    severity: 'warning',
    effort: 'medium',
    source: 'health',
    analyzer: 'circular_deps',
    state: 'active',
    affected_files: ['src/components/search/SearchPanel.tsx', 'src/components/trace/TraceExplorer.tsx'],
    suggested_action: 'Extract SearchResultsList into a shared results/ module.',
    evidence: 'Cycle: search → trace → search',
    mcp_command: 'prep_audit action="refactor" finding_ids=["ARCH-1"]',
    created_at: now,
    dismissed_at: '',
  },
  {
    id: 'OPP-003',
    title: 'Remove dead import of GoalpostsPanel from bundle',
    description: 'Panel is marked hidden but still imported. Tree-shaking is not removing it because of the registry reference.',
    category: 'quality',
    priority: 'P1',
    severity: 'warning',
    effort: 'small',
    source: 'health',
    analyzer: 'dead_code',
    state: 'active',
    affected_files: ['src/components/goalposts/GoalpostsPanel.tsx', 'src/config/panelRegistry.ts'],
    suggested_action: 'Use React.lazy() or remove from registry entirely.',
    evidence: 'Hidden panel still in bundle: 22KB',
    mcp_command: 'prep_audit action="refactor" finding_ids=["QUAL-1"]',
    created_at: now,
    dismissed_at: '',
  },
  {
    id: 'OPP-004',
    title: 'Add integration tests for AgentScopePanel auto-populate',
    description: 'The Phase 67 auto-populate feature has zero test coverage.',
    category: 'coverage',
    priority: 'P2',
    severity: 'info',
    effort: 'medium',
    source: 'health',
    analyzer: 'test_coverage',
    state: 'active',
    affected_files: ['src/components/agents/AgentScopePanel.tsx'],
    suggested_action: 'Write tests with mock onAutoPopulate callbacks.',
    evidence: 'Coverage: 0% for auto-populate flow',
    mcp_command: '',
    created_at: now,
    dismissed_at: '',
  },
  {
    id: 'OPP-005',
    title: 'TODO: Implement retry logic for embedding failures',
    description: 'Found in-code TODO comment indicating missing retry logic.',
    category: 'quality',
    priority: 'P2',
    severity: 'info',
    effort: 'small',
    source: 'todo_scanner',
    analyzer: 'todo_scanner',
    state: 'active',
    affected_files: ['src/prep/core/embeddings.py'],
    suggested_action: 'Add exponential backoff retry with max 3 attempts.',
    evidence: 'Line 142: # TODO: add retry logic here',
    mcp_command: '',
    created_at: now,
    dismissed_at: '',
  },
  {
    id: 'OPP-006',
    title: 'Consider extracting auth middleware into shared package',
    description: 'The auth middleware pattern is duplicated across the MCP server and the dashboard API.',
    category: 'architecture',
    priority: 'P2',
    severity: 'info',
    effort: 'large',
    source: 'advisor',
    analyzer: 'advisor',
    state: 'active',
    affected_files: ['src/prep/mcp/auth.py', 'src/prep/dashboard/auth.py'],
    suggested_action: 'Create a shared auth/ package with the middleware and token validation logic.',
    evidence: 'Code similarity: 87% between the two auth files',
    mcp_command: '',
    created_at: now,
    dismissed_at: '',
  },
];

const mockSummary: OpportunitiesSummary = {
  total: mockItems.length,
  dismissed: 0,
  critical: 1,
  warning: 2,
  info: 3,
  actionable_count: 4,
  last_refresh: now,
  by_priority: { P0: 1, P1: 2, P2: 3 },
  by_category: { architecture: 3, quality: 2, coverage: 1 },
  by_source: { health: 4, todo_scanner: 1, advisor: 1 },
  by_analyzer: {},
  by_severity: { critical: 1, warning: 2, info: 3 },
  top_analyzers: [
    { analyzer: 'large_files', count: 1 },
    { analyzer: 'circular_deps', count: 1 },
    { analyzer: 'dead_code', count: 1 },
    { analyzer: 'test_coverage', count: 1 },
    { analyzer: 'todo_scanner', count: 1 },
    { analyzer: 'advisor', count: 1 },
  ],
};

/** Interactive wrapper with state management */
function OpportunitiesWrapper(props: Partial<OpportunitiesPanelProps>) {
  const [categoryFilter, setCategoryFilter] = useState<string | null>(null);
  const [priorityFilter, setPriorityFilter] = useState<string | null>(null);
  const [sourceFilter, setSourceFilter] = useState<string | null>(null);
  const [showDismissed, setShowDismissed] = useState(false);

  return (
    <OpportunitiesPanel
      items={mockItems}
      summary={mockSummary}
      loading={false}
      refreshing={false}
      error={null}
      onRefresh={() => console.log('Refresh')}
      onDismiss={(id) => console.log('Dismiss', id)}
      onRestore={(id) => console.log('Restore', id)}
      onExport={(fmt) => console.log('Export', fmt)}
      categoryFilter={categoryFilter}
      onCategoryFilterChange={setCategoryFilter}
      priorityFilter={priorityFilter}
      onPriorityFilterChange={setPriorityFilter}
      sourceFilter={sourceFilter}
      onSourceFilterChange={setSourceFilter}
      showDismissed={showDismissed}
      onShowDismissedChange={setShowDismissed}
      agentStatus={{
        enabled: true,
        auto_scan: true,
        cooldown_seconds: 300,
        running_task: null,
        last_scan_at: new Date(Date.now() - 1800000).toISOString(),
        last_scan_delta: {
          new_findings: [{ title: 'New circular dep found', severity: 'warning' }],
          resolved_findings: [{ title: 'Fixed naming issue', severity: 'info' }],
          unchanged_count: 4,
        },
      }}
      {...props}
    />
  );
}

/** Full opportunities panel with Pi Agent status and filters */
export const WithOpportunities: Story = {
  render: () => <OpportunitiesWrapper />,
};

/** Empty state — no opportunities found */
export const Empty: Story = {
  render: () => (
    <OpportunitiesWrapper
      items={[]}
      summary={null}
    />
  ),
};
