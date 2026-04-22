import type { Meta, StoryObj } from '@storybook/react';
import { RoadmapPanel } from '../../components/goalposts/RoadmapPanel';
import type { RoadmapNode, GoalpostQuestion, VelocityResponse, SprintSuggestion } from '../../types';

const meta: Meta<typeof RoadmapPanel> = {
  title: 'Goalposts/RoadmapPanel',
  component: RoadmapPanel,
  parameters: {
    layout: 'fullscreen',
    docs: { description: { component: 'AI-powered project roadmap with vertical timeline, tier filters (Completed → Proposed), App Ethos editor, Sprint Intelligence, and GitHub sync. Nodes can be AI-proposed, mined from TODOs, or manually created.' } },
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
type Story = StoryObj<typeof RoadmapPanel>;

const now = new Date().toISOString();
const weekAgo = new Date(Date.now() - 7 * 86400000).toISOString();
const twoWeeksAgo = new Date(Date.now() - 14 * 86400000).toISOString();

const mockNodes: RoadmapNode[] = [
  {
    id: 'rm-1', title: 'Implement MCP streaming responses', description: 'Add Server-Sent Events streaming for prep_search to reduce TTFB for large context assemblies.',
    tier: 'active', position: 0, source: 'ai_proposed', source_ref: null, category: 'feature', priority: 'P0',
    tasks: [
      { description: 'Add SSE endpoint to MCP server', file_paths: ['src/prep/mcp/routes.py'], effort: 'medium' },
      { description: 'Update client to consume streaming', file_paths: ['packages/ui/src/api/client.ts'], effort: 'small' },
    ],
    state: 'active', parent_id: null, fork_label: null, created_at: weekAgo, decided_at: weekAgo, completed_at: null,
    ethos_alignment: 'Performance-first approach for real-time developer workflows', business_impact: 'Reduces perceived latency by 60%, improving competitive positioning vs Greptile',
  },
  {
    id: 'rm-2', title: 'Extract pipeline stages into individual components', description: 'GraphEnrichmentPipeline.tsx is 58KB. Split into 9 individual stage components.',
    tier: 'planned', position: 1, source: 'ai_proposed', source_ref: null, category: 'architecture', priority: 'P1',
    tasks: [
      { description: 'Create trace/stages/ directory', file_paths: ['packages/ui/src/components/trace/'], effort: 'small' },
      { description: 'Extract each stage into its own component', file_paths: ['packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx'], effort: 'large' },
    ],
    state: 'accepted', parent_id: null, fork_label: null, created_at: weekAgo, decided_at: null, completed_at: null,
    ethos_alignment: 'Maintainability-first architecture', business_impact: 'Reduces onboarding cost for new contributors',
  },
  {
    id: 'rm-3', title: 'Add retry logic for embedding failures', description: 'Missing exponential backoff in the embedding pipeline.',
    tier: 'planned', position: 2, source: 'todo_scan', source_ref: 'src/prep/core/embeddings.py:142', category: 'tech_debt', priority: 'P2',
    tasks: [{ description: 'Add exponential backoff with max 3 attempts', file_paths: ['src/prep/core/embeddings.py'], effort: 'small' }],
    state: 'accepted', parent_id: null, fork_label: null, created_at: twoWeeksAgo, decided_at: null, completed_at: null,
    ethos_alignment: 'Reliability-first design', business_impact: 'Eliminates silent indexing failures for enterprise deployments',
  },
  {
    id: 'rm-4', title: 'Multi-project search federation', description: 'Allow searching across all active projects in a single MCP call.',
    tier: 'proposed', position: 3, source: 'ai_proposed', source_ref: null, category: 'feature', priority: 'P1',
    tasks: [
      { description: 'Add federated search endpoint', file_paths: ['src/prep/mcp/routes.py'], effort: 'large' },
      { description: 'Merge and re-rank results across projects', file_paths: ['src/prep/core/search.py'], effort: 'large' },
    ],
    state: 'proposed', parent_id: null, fork_label: null, created_at: now, decided_at: null, completed_at: null,
    ethos_alignment: 'Sovereign multi-repo architecture', business_impact: 'Unlocks Enterprise tier monorepo use case',
  },
  {
    id: 'rm-5', title: 'Ship VS Code extension v2.0', description: 'Updated extension with embedded dashboard, inline search results, and code lens annotations.',
    tier: 'completed', position: 4, source: 'manual', source_ref: null, category: 'feature', priority: 'P0',
    tasks: [], state: 'completed', parent_id: null, fork_label: null,
    created_at: twoWeeksAgo, decided_at: twoWeeksAgo, completed_at: weekAgo,
    ethos_alignment: 'Meet developers where they are', business_impact: 'Primary distribution channel',
  },
];

const mockQuestions: GoalpostQuestion[] = [
  {
    id: 'q-1', question: 'Should federated search merge results by relevance score or by project priority?',
    context: 'Federated search across multiple projects requires a merge strategy. Relevance-first gives the best individual results; project-priority-first lets users weight their active project higher.',
    category: 'feature', answered: false, answer: '', created_at: now,
  },
  {
    id: 'q-2', question: 'What is the maximum acceptable latency for MCP streaming first-byte?',
    context: 'Current TTFB is ~400ms for cached queries. Streaming could reduce this but adds complexity.',
    category: 'architecture', answered: true, answer: 'Target under 200ms TTFB for cached, under 1s for cold queries.',
    created_at: weekAgo,
  },
];

const mockVelocity: VelocityResponse = {
  average_velocity: 3.2,
  total_completed: 12, total_active: 3, total_planned: 5, total_proposed: 2,
  snapshots: [
    { window_start: twoWeeksAgo, window_end: weekAgo, window_label: 'Sprint 4', duration_days: 7,
      completed_count: 4, completed_nodes: ['rm-5'], added_count: 2, p0_completed: 1, p1_completed: 2,
      categories: { feature: 2, architecture: 1, tech_debt: 1 } },
    { window_start: weekAgo, window_end: now, window_label: 'Sprint 5', duration_days: 7,
      completed_count: 2, completed_nodes: [], added_count: 3, p0_completed: 0, p1_completed: 1,
      categories: { feature: 1, tech_debt: 1 } },
  ],
  burndown: [
    { date: twoWeeksAgo, remaining: 18, completed: 10 },
    { date: weekAgo, remaining: 14, completed: 14 },
    { date: now, remaining: 12, completed: 16 },
  ],
};

const mockSprint: SprintSuggestion = {
  sprint_label: 'Sprint 6', capacity: 3, confidence: 0.82,
  rationale: 'Based on your average velocity of 3.2 nodes/sprint, prioritizing the active P0 streaming feature and two planned P1 items.',
  suggested_nodes: ['rm-1', 'rm-2', 'rm-3'],
  node_details: [
    { id: 'rm-1', title: 'Implement MCP streaming responses', priority: 'P0', category: 'feature', tier: 'active' },
    { id: 'rm-2', title: 'Extract pipeline stage components', priority: 'P1', category: 'architecture', tier: 'planned' },
    { id: 'rm-3', title: 'Add retry logic for embedding failures', priority: 'P2', category: 'tech_debt', tier: 'planned' },
  ],
};

const noop = () => {};

/** Full roadmap with nodes, questions, velocity, and sprint suggestion */
export const WithContent: Story = {
  args: {
    nodes: mockNodes, questions: mockQuestions,
    northStar: { id: 'rm-1', title: 'Implement MCP streaming responses', priority: 'P0' },
    appEthos: 'SourcePrep is an epistemic intelligence engine for autonomous agents. We prioritize structural understanding over token volume, private-by-design architecture, and zero-configuration developer experience.',
    generating: false, scanning: false, error: null, ready: true,
    lastGeneratedAt: weekAgo, modelUsed: 'claude-sonnet-4-20250514',
    velocityData: mockVelocity, sprintSuggestion: mockSprint, loadingSprint: false,
    onGenerate: noop, onScanTodos: noop, onUpdateEthos: noop,
    onPromoteNode: noop, onDismissNode: noop, onDeleteNode: noop,
    onCreateNode: noop, onAnswerQuestion: noop,
    onSuggestSprint: noop, onMineRoadmap: noop,
  },
};

/** Empty state — no roadmap generated yet */
export const Empty: Story = {
  args: {
    nodes: [], questions: [],
    northStar: null, appEthos: '',
    generating: false, scanning: false, error: null, ready: true,
    lastGeneratedAt: '', modelUsed: '',
    onGenerate: noop, onScanTodos: noop, onUpdateEthos: noop,
    onPromoteNode: noop, onDismissNode: noop, onDeleteNode: noop,
    onCreateNode: noop, onAnswerQuestion: noop,
  },
};

/** Generating state */
export const Generating: Story = {
  args: {
    nodes: [], questions: [],
    northStar: null, appEthos: 'SourcePrep is an epistemic intelligence engine.',
    generating: true, scanning: false, error: null, ready: true,
    lastGeneratedAt: '', modelUsed: '',
    onGenerate: noop, onScanTodos: noop, onUpdateEthos: noop,
    onPromoteNode: noop, onDismissNode: noop, onDeleteNode: noop,
    onCreateNode: noop, onAnswerQuestion: noop,
  },
};
