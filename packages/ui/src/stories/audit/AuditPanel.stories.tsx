import type { Meta, StoryObj } from '@storybook/react';
import { AuditPanel } from '../../components/audit/AuditPanel';
import type { AuditFinding, AuditStatus, AuditReport } from '../../types';

const meta: Meta<typeof AuditPanel> = {
  title: 'Audit/AuditPanel',
  component: AuditPanel,
  parameters: {
    layout: 'fullscreen',
    docs: { description: { component: 'Autonomous codebase health audit panel with tabbed findings view (Summary, Architecture, Quality, Coverage, Tech Debt), severity breakdowns, and AI synthesis reports.' } },
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
type Story = StoryObj<typeof AuditPanel>;

const mockFindings: AuditFinding[] = [
  {
    analyzer: 'large_files',
    severity: 'critical',
    category: 'size',
    title: 'GraphEnrichmentPipeline.tsx exceeds 58KB — extract stage components',
    description: 'This file has grown to 1,247 lines and handles all 9 pipeline stages inline. Each stage should be a separate component.',
    file_paths: ['packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx'],
    evidence: { lines: 1247, bytes: 58301, module: 'trace' },
    suggested_action: 'Extract each pipeline stage (Structural, Catalogue, Validation, etc.) into its own component file under trace/stages/.',
    finding_id: 'SIZE-1',
    priority: 'P0',
    effort: 'large',
  },
  {
    analyzer: 'circular_deps',
    severity: 'warning',
    category: 'architecture',
    title: 'Circular dependency between search/ and trace/ modules',
    description: 'SearchPanel imports TraceGraph, and TraceExplorer imports SearchResultsList. This creates a bidirectional dependency.',
    file_paths: ['src/components/search/SearchPanel.tsx', 'src/components/trace/TraceExplorer.tsx'],
    evidence: { cycle: ['search', 'trace'], module: 'search' },
    suggested_action: 'Create a shared results/ module for SearchResultsList, breaking the cycle.',
    finding_id: 'ARCH-1',
    priority: 'P1',
    effort: 'medium',
  },
  {
    analyzer: 'naming',
    severity: 'info',
    category: 'naming',
    title: 'Inconsistent naming: "Panel" vs "Card" vs "Widget" suffixes',
    description: '15 components use "Panel", 8 use "Card", and 3 use "Widget". Adopt a consistent naming convention.',
    file_paths: ['src/components/dashboard/', 'src/components/trace/'],
    evidence: { panel_count: 15, card_count: 8, widget_count: 3, module: 'dashboard' },
    suggested_action: 'Standardize: use "Panel" for full-height panels, "Card" for compact cards, retire "Widget".',
    finding_id: 'NAME-1',
    priority: 'P2',
    effort: 'small',
  },
  {
    analyzer: 'dead_code',
    severity: 'warning',
    category: 'quality',
    title: 'GoalpostsPanel is hidden but still ships in the bundle',
    description: 'The component is marked as hidden in the panel registry but is still imported and tree-shaken into the build.',
    file_paths: ['src/components/goalposts/GoalpostsPanel.tsx'],
    evidence: { hidden: true, bundle_bytes: 22000, module: 'goalposts' },
    suggested_action: 'Use React.lazy() for sunset panels, or remove the import entirely.',
    finding_id: 'QUAL-1',
    priority: 'P1',
    effort: 'small',
  },
  {
    analyzer: 'test_coverage',
    severity: 'info',
    category: 'coverage',
    title: 'No test coverage for AgentScopePanel auto-populate flow',
    description: 'The auto-populate feature (Phase 67) has no integration tests.',
    file_paths: ['src/components/agents/AgentScopePanel.tsx'],
    evidence: { coverage_pct: 0, module: 'agents' },
    suggested_action: 'Add integration test for onAutoPopulate callback with mock data.',
    finding_id: 'COV-1',
    priority: 'P2',
    effort: 'medium',
  },
  {
    analyzer: 'large_files',
    severity: 'warning',
    category: 'size',
    title: 'EnterpriseAdminPanel.tsx is 45KB — consider splitting tabs',
    description: 'The enterprise admin panel handles 6 tabs inline. Extract each tab into its own component.',
    file_paths: ['src/components/enterprise/EnterpriseAdminPanel.tsx'],
    evidence: { lines: 1100, bytes: 45363, module: 'enterprise' },
    suggested_action: 'Split each admin tab (Providers, Models, Data, Sync, Network, Budget) into separate files.',
    finding_id: 'SIZE-2',
    priority: 'P1',
    effort: 'large',
  },
];

const mockStatus: AuditStatus = {
  running: false,
  error: null,
  has_results: true,
  finding_count: mockFindings.length,
  severity_counts: { critical: 1, warning: 3, info: 2, suggestion: 0 },
  last_run: {
    generated_at: new Date(Date.now() - 7200000).toISOString(),
    graph_node_count: 5085,
    graph_edge_count: 21767,
    finding_count: mockFindings.length,
    document_count: 3,
    analyzers_run: ['large_files', 'circular_deps', 'naming', 'dead_code', 'test_coverage'],
    documents: ['AUDIT_SUMMARY', 'ARCHITECTURE_ANALYSIS', 'TECH_DEBT_REPORT'],
  },
};

const mockReports: AuditReport[] = [
  { name: 'AUDIT_SUMMARY', filename: 'audit_summary.md', size_bytes: 4200 },
  { name: 'ARCHITECTURE_ANALYSIS', filename: 'architecture_analysis.md', size_bytes: 8500 },
  { name: 'TECH_DEBT_REPORT', filename: 'tech_debt_report.md', size_bytes: 6300 },
];

const noop = () => {};

/** Full audit with findings across all categories */
export const WithFindings: Story = {
  args: {
    status: mockStatus,
    findings: mockFindings,
    reports: mockReports,
    onRunAudit: noop,
    onViewReport: noop,
  },
};

/** Empty state — no audit has been run yet */
export const NoResults: Story = {
  args: {
    status: { running: false, error: null, has_results: false },
    findings: [],
    reports: [],
    onRunAudit: noop,
    onViewReport: noop,
  },
};

/** Running state — audit in progress */
export const Running: Story = {
  args: {
    status: { running: true, error: null, has_results: false },
    findings: [],
    reports: [],
    onRunAudit: noop,
    onViewReport: noop,
  },
};
