import type { Meta, StoryObj } from '@storybook/react';
import { useState, useMemo, useCallback, useRef } from 'react';
import { Settings, FileText } from 'lucide-react';
import { IndexStatusCard } from '../../components/dashboard/IndexStatusCard';
import { LLMStatusWidget, type LLMServiceStatus } from '../../components/dashboard/index';
import { SearchPanel } from '../../components/search/SearchPanel';
import { ContextOptionsPanel } from '../../components/search/ContextOptionsPanel';
import { SearchResultsList } from '../../components/search/SearchResultsList';
import type { SearchResult } from '../../types';
import { ChunkPreview } from '../../components/search/ChunkPreview';
import { ContextOutput } from '../../components/search/ContextOutput';
import type { TreeNode } from '../../components/project/index';
import { FolderTreePanel } from '../../components/project/FolderTreePanel';
import { FileExplorerDetail } from '../../components/project/FileExplorerDetail';
import type { PinnedTextFile } from '../../components/project/PinnedTextFilesPanel';
import { TraceGraph, SymbolSearchInput, type TraceNode } from '../../components/trace/index';
import { GraphStructurePanel } from '../../components/trace/GraphStructurePanel';
import { GraphEnrichmentPipeline } from '../../components/trace/GraphEnrichmentPipeline';
import type { TraceCoverageFile, TraceCoverageSummary } from '../../types';
import { ModularDashboard, type DashboardLayoutApi } from '../../components/layout/ModularDashboard';
import type { PanelDefinition } from '../../types/layout';
import { AppShell, Sidebar, ProjectList, SidebarAIGateway, SidebarPipelineQueue } from '../../components/navigation/index';
import type { ProjectSummary, LLMSlotsStatus } from '../../types';
import { CodeViewer } from '../../components/project/CodeViewer';
import { UsageGuidePanel } from '../../components/dashboard/UsageGuidePanel';
import { DeepAnalysisSettings, type DeepAnalysisSchedule } from '../../components/llm/DeepAnalysisSettings';
import { LogConsole } from '../../components/console/LogConsole';
import { ActivityHeatmap, generateSampleActivityData } from '../../components/viz/ActivityHeatmap';
import { AgentOpsPanel } from '../../components/agents/AgentOpsPanel';
import { AuditPanel } from '../../components/audit/AuditPanel';
import { OpportunitiesPanel } from '../../components/audit/OpportunitiesPanel';
import { RoadmapPanel } from '../../components/goalposts/RoadmapPanel';
import { ConceptsPanel } from '../../components/concepts/ConceptsPanel';
import type { ConceptItem, ConceptQuestionItem, ConceptStats } from '../../components/concepts/ConceptsPanel';
import { AtlasLensPanel } from '../../components/trace/AtlasLensPanel/AtlasLensPanel';
import type { AuditFinding, AuditReport, AtlasStatus, ScopeSummary, ScopeStatus, ScopeRecord } from '../../types';

const noop = () => {};

const meta: Meta = {
  title: 'Dashboard/Layouts/FullDashboard',
  tags: ['autodocs'],
  parameters: {
    layout: 'fullscreen',
  },
};

export default meta;

const sampleTraceNodes: TraceNode[] = [
  { id: '1', name: 'build_project', kind: 'symbol', language: 'Python', inDegree: 3, outDegree: 5 },
  { id: '2', name: 'IndexManager', kind: 'symbol', language: 'Python', inDegree: 8, outDegree: 12 },
  { id: '3', name: '/api/build', kind: 'endpoint', inDegree: 1, outDegree: 2 },
  { id: '4', name: 'server.py', kind: 'file', inDegree: 0, outDegree: 15 },
];

const sampleLLMServices: LLMServiceStatus[] = [
  { name: 'Ollama', url: 'localhost:11434', status: 'connected', type: 'ollama' },
  { name: 'Compression', status: 'connected', type: 'other' },
  { name: 'OpenAI', status: 'disconnected', type: 'openai' },
];

const mockResults: SearchResult[] = [
  {
    chunk_id: '1',
    source_path: 'src/api/client.ts',
    section: 'ApiClient.fetch',
    content: `export class ApiClient {
  private baseUrl: string;
  
  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }
  
  async fetch<T>(endpoint: string): Promise<T> {
    const res = await fetch(\`\${this.baseUrl}\${endpoint}\`);
    if (!res.ok) throw new Error(\`HTTP \${res.status}\`);
    return res.json();
  }
}`,
    preview: 'export class ApiClient { ... }',
    span: { start_line: 1, end_line: 15 },
    score: 0.892,
  },
  {
    chunk_id: '2',
    source_path: 'src/api/errors.ts',
    section: 'handleApiError',
    content: `export function handleApiError(error: unknown): never {
  if (error instanceof ApiError) {
    console.error('API Error:', error.message);
    throw error;
  }
  throw new ApiError('Unknown error', 500);
}`,
    preview: 'export function handleApiError(error: unknown): never { ... }',
    span: { start_line: 1, end_line: 10 },
    score: 0.756,
  },
];

const mockUntracedFiles: TraceCoverageFile[] = [
  { path: 'backend/workers/retry.py', language: 'python', size: 4200, modified: new Date(Date.now() - 3_600_000).toISOString(), created: new Date(Date.now() - 86_400_000).toISOString() },
  { path: 'frontend/src/lib/format.ts', language: 'typescript', size: 1800, modified: new Date(Date.now() - 86_400_000).toISOString(), created: new Date(Date.now() - 604_800_000).toISOString() },
  { path: 'backend/core/scheduler.py', language: 'python', size: 6100, modified: new Date(Date.now() - 3_600_000).toISOString(), created: new Date(Date.now() - 86_400_000).toISOString() },
];

const mockStaleFiles: TraceCoverageFile[] = [
  { path: 'backend/services/task_service.py', language: 'python', size: 18_400, modified: new Date(Date.now() - 3_600_000).toISOString(), created: new Date(Date.now() - 604_800_000).toISOString() },
];

const mockExcludedFiles: TraceCoverageFile[] = [
  { path: 'tests/backend/test_tasks.py', language: 'python', size: 3200, modified: new Date(Date.now() - 86_400_000).toISOString(), created: new Date(Date.now() - 604_800_000).toISOString() },
  { path: 'scripts/deploy.sh', language: null, size: 800, modified: new Date(Date.now() - 86_400_000).toISOString(), created: new Date(Date.now() - 604_800_000).toISOString() },
];

const mockCoverageSummary: TraceCoverageSummary = {
  total: 89,
  traced: 78,
  untraced: 3,
  stale: 1,
  excluded: 7,
  coverage_pct: 87.6,
  last_build_at: new Date(Date.now() - 7_200_000).toISOString(),
};

import { PANEL_REGISTRY } from '../../config/panelRegistry';

// Phase 131: filter PANEL_REGISTRY for the storybook demo.
//
// 1. Always exclude the legacy "AI Gateway" summary card (`llm-status`).
//    Phase 74 sunsetted this panel — manually-constructed state drifted from
//    real pipeline status; the sidebar AI Gateway widget is now the canonical
//    live view. Keeping it out of the demo means it never appears in either
//    private or public storybook.
//
// 2. In public mode (STORYBOOK_PUBLIC=true), additionally drop every panel
//    flagged `devOnly: true` in the registry — Spaghetti Finder, Goalposts,
//    Health Scanner, Advisor, Roadmap, Opportunities. The local developer
//    storybook keeps showing them so internal work isn't blocked.
const IS_PUBLIC = typeof process !== 'undefined' && process.env.STORYBOOK_PUBLIC === 'true';

const STORY_PANELS: PanelDefinition[] = PANEL_REGISTRY.filter((p) => {
  if (p.id === 'llm-status') return false; // deprecated
  if (IS_PUBLIC && p.devOnly) return false;
  return true;
});

/** Prefix for dynamically-pinned file panel IDs */
const PINNED_PREFIX = 'pinned:';

// ────────────────────────────────────────────────────────────────────────────
// Demo dummy data — kept generic ("Acme Search") so the showcase doesn't
// expose internal project names. The audit/atlas/concepts panels render
// healthy steady-state content (no critical findings, atlas exists, concepts
// curated).
// ────────────────────────────────────────────────────────────────────────────

const mockAuditFindings: AuditFinding[] = [
  // ── Warnings ──
  {
    finding_id: 'a1',
    analyzer: 'oversized-files',
    severity: 'warning',
    category: 'size',
    title: 'task_service.py is 18KB',
    description: 'Approaching the 20KB soft ceiling. Status-transition logic plus side-effect orchestration in one module.',
    file_paths: ['backend/services/task_service.py'],
    evidence: { size_bytes: 18_400 },
    suggested_action: 'Extract status-transition state machine into its own module.',
    priority: 'P2',
    effort: 'medium',
  },
  {
    finding_id: 'a2',
    analyzer: 'import-cycles',
    severity: 'warning',
    category: 'architecture',
    title: 'Import cycle: api.tasks ↔ services.task_service',
    description: 'tasks.py imports task_service for the create flow; task_service imports tasks for the route URL helpers.',
    file_paths: ['backend/api/tasks.py', 'backend/services/task_service.py'],
    evidence: { cycle_length: 2 },
    suggested_action: 'Move shared TaskRef types to backend/models/task.py and import from there in both.',
    priority: 'P2',
    effort: 'medium',
  },
  // ── Info ──
  {
    finding_id: 'a3',
    analyzer: 'todo-scanner',
    severity: 'info',
    category: 'quality',
    title: '4 TODOs in backend/workers/',
    description: 'Outstanding TODO comments tracked for the next sprint — retry backoff tuning + dead-letter wiring.',
    file_paths: ['backend/workers/queue.py', 'backend/workers/retry.py'],
    evidence: { todo_count: 4 },
    suggested_action: 'Triage and convert to issues or close.',
    priority: 'P3',
    effort: 'small',
  },
  {
    finding_id: 'a4',
    analyzer: 'stale-docs',
    severity: 'info',
    category: 'coverage',
    title: 'ROADMAP.md last touched 3 weeks ago',
    description: 'No entries since the v0.4 release; v0.5 milestones are not reflected.',
    file_paths: ['docs/ROADMAP.md'],
    evidence: {},
    suggested_action: 'Backfill v0.5 milestones from the closed PR list.',
    priority: 'P3',
    effort: 'small',
  },
  {
    finding_id: 'a5',
    analyzer: 'doc-coverage',
    severity: 'info',
    category: 'coverage',
    title: 'README missing "Local development" section',
    description: 'README documents production deploy but not the docker-compose dev loop.',
    file_paths: ['docs/README.md'],
    evidence: {},
    suggested_action: 'Add a "Local development" section pointing at docker-compose.yml.',
    priority: 'P3',
    effort: 'small',
  },
  {
    finding_id: 'a6',
    analyzer: 'test-coverage',
    severity: 'info',
    category: 'testing',
    title: 'lib/date.ts has no tests',
    description: 'date.ts is referenced by the "frontend never trusts client-side timestamps" concept — load-bearing but untested.',
    file_paths: ['frontend/src/lib/date.ts'],
    evidence: { test_files: 0 },
    suggested_action: 'Add a test file covering tz normalization + drift handling.',
    priority: 'P2',
    effort: 'small',
  },
  // ── Suggestions ──
  {
    finding_id: 'a7',
    analyzer: 'concept-coverage',
    severity: 'suggestion',
    category: 'coverage',
    title: 'Concept "Tasks soft-delete with deleted_at" is a seed',
    description: 'Auto-detected pattern from backend/models/task.py is still in seed status — promote or archive.',
    file_paths: ['backend/models/task.py'],
    evidence: {},
    suggested_action: 'Review the concept and promote to active if it reflects intent.',
    priority: 'P3',
    effort: 'small',
  },
  {
    finding_id: 'a8',
    analyzer: 'coupling',
    severity: 'suggestion',
    category: 'architecture',
    title: 'email.py fans out to 12 imports',
    description: 'Possible god-module — email composition, SMTP transport, and template rendering all in one file.',
    file_paths: ['backend/services/email.py'],
    evidence: { import_count: 12 },
    suggested_action: 'Split into transport + template + composer.',
    priority: 'P3',
    effort: 'medium',
  },
  {
    finding_id: 'a9',
    analyzer: 'react-patterns',
    severity: 'suggestion',
    category: 'quality',
    title: 'Settings.tsx has 8 useState calls',
    description: 'High useState count suggests reducer-shaped state. Consider extracting useReducer.',
    file_paths: ['frontend/src/pages/Settings.tsx'],
    evidence: { useState_count: 8 },
    suggested_action: 'Refactor to useReducer with a Settings action type.',
    priority: 'P3',
    effort: 'medium',
  },
  {
    finding_id: 'a10',
    analyzer: 'atlas-coverage',
    severity: 'suggestion',
    category: 'coverage',
    title: '3 directories without sub-atlases',
    description: 'scripts/, tests/backend/, tests/frontend/ have no curated atlas — agent answers about these areas fall back to raw retrieval.',
    file_paths: ['scripts/', 'tests/backend/', 'tests/frontend/'],
    evidence: { uncovered_dirs: 3 },
    suggested_action: 'Either add sub-atlases or explicitly tag these dirs as "no-atlas".',
    priority: 'P3',
    effort: 'small',
  },
];

const mockAuditReports: AuditReport[] = [
  { name: 'Audit · 2026-04-29', filename: 'audit_20260429.md', size_bytes: 18_240 },
  { name: 'Audit · 2026-04-15', filename: 'audit_20260415.md', size_bytes: 17_760 },
];

const mockConcepts: ConceptItem[] = [
  // ── Architecture (3, all active) ──
  {
    id: 'c1',
    title: 'Single source of truth for task state',
    content: 'task_service owns every status transition; routes and workers call into it rather than mutating the model directly. Prevents partial-update races where the API thinks a task is `done` while a worker still has it `running`.',
    category: 'architecture',
    status: 'active',
    confidence: 0.94,
    anchors: ['backend/services/task_service.py'],
    tags: ['state-machine', 'consistency'],
    created_at: Date.now() / 1000 - 86_400 * 21,
  },
  {
    id: 'c2',
    title: 'Auth lives at the dependency layer, not in routes',
    content: 'FastAPI Depends(current_user) wraps every protected route. Routes never call get_user() directly so tests can swap the dependency.',
    category: 'architecture',
    status: 'active',
    confidence: 0.96,
    anchors: ['backend/api/deps.py', 'backend/api/auth.py'],
    tags: ['auth', 'testability'],
    created_at: Date.now() / 1000 - 86_400 * 18,
  },
  {
    id: 'c3',
    title: 'Optimistic UI reconciles on next fetch',
    content: 'useTasks applies edits to local state immediately, then refetches to verify. If the server rejects, the next refetch rolls back. Keeps the UI snappy without phantom state.',
    category: 'architecture',
    status: 'active',
    confidence: 0.88,
    anchors: ['frontend/src/hooks/useTasks.ts'],
    tags: ['ux', 'frontend'],
    created_at: Date.now() / 1000 - 86_400 * 9,
  },
  // ── Constraints (4, all active — these auto-derive antibodies) ──
  {
    id: 'c4',
    title: 'All cloud LLM calls are budget-capped',
    content: 'Every notification template render and every job-summary call passes through a per-call token budget. No unbounded prompt ever ships to a cloud provider.',
    category: 'constraint',
    status: 'active',
    confidence: 0.97,
    anchors: ['backend/services/notification_service.py', 'backend/workers/jobs.py'],
    tags: ['cost', 'safety'],
    created_at: Date.now() / 1000 - 86_400 * 14,
  },
  {
    id: 'c5',
    title: 'Background jobs are idempotent',
    content: 'Every job carries an idempotency key; the queue dedupes on retry. Required because retry.py uses at-least-once delivery and the SMTP transport can succeed before ack.',
    category: 'constraint',
    status: 'active',
    confidence: 0.93,
    anchors: ['backend/workers/queue.py', 'backend/workers/retry.py'],
    tags: ['reliability', 'workers'],
    created_at: Date.now() / 1000 - 86_400 * 11,
  },
  {
    id: 'c6',
    title: 'DB sessions never cross request boundaries',
    content: 'get_session() is request-scoped via FastAPI dependency. Closing late once exhausted the connection pool — fixed in v0.4, antibody monitors for stale session leaks.',
    category: 'constraint',
    status: 'active',
    confidence: 0.95,
    anchors: ['backend/core/db.py'],
    tags: ['db', 'lifecycle'],
    created_at: Date.now() / 1000 - 86_400 * 5,
  },
  {
    id: 'c7',
    title: 'Frontend never trusts client-side timestamps',
    content: 'All timestamps render through lib/date.ts which normalizes against server time. Clock drift on user devices used to produce "task scheduled in the past" bugs.',
    category: 'constraint',
    status: 'active',
    confidence: 0.90,
    anchors: ['frontend/src/lib/date.ts'],
    tags: ['frontend', 'reliability'],
    created_at: Date.now() / 1000 - 86_400 * 3,
  },
  // ── Pattern (1, active) ──
  {
    id: 'c8',
    title: 'Notification side-effects are batched, not per-event',
    content: 'Task changes accumulate in a per-user buffer; notification_service flushes the buffer on a 60s tick or when the user comes online. Avoids hitting provider rate limits during bulk edits.',
    category: 'pattern',
    status: 'active',
    confidence: 0.87,
    anchors: ['backend/services/notification_service.py'],
    tags: ['notifications', 'rate-limits'],
    created_at: Date.now() / 1000 - 86_400 * 6,
  },
  // ── Seeds (2, awaiting promotion) ──
  {
    id: 'c9',
    title: 'Tasks soft-delete with a deleted_at column',
    content: 'task.py has deleted_at + a partial index on deleted_at IS NULL. Inferred from the model; intent looks deliberate. Promote if confirmed.',
    category: 'constraint',
    status: 'seed',
    confidence: 0.72,
    anchors: ['backend/models/task.py'],
    tags: ['db', 'undo'],
    created_at: Date.now() / 1000 - 86_400 * 2,
  },
  {
    id: 'c10',
    title: 'Email templates live in code, not the database',
    content: 'email.py loads Jinja templates from disk at boot. Inferred from the import structure; might want to confirm intent vs. accident.',
    category: 'pattern',
    status: 'seed',
    confidence: 0.68,
    anchors: ['backend/services/email.py'],
    tags: ['email', 'review-ability'],
    created_at: Date.now() / 1000 - 3_600 * 6,
  },
];

const mockConceptQuestions: ConceptQuestionItem[] = [
  {
    id: 'q1',
    question: 'Should we expose a task-history audit log to end users?',
    context: 'task_service emits status_changed events, but they only land in the worker logs. Users have asked for an in-product timeline view.',
    suggested_category: 'pattern',
    target_module: 'backend/services/task_service.py',
    answered: false,
  },
  {
    id: 'q2',
    question: 'Is the reducer in Dashboard.tsx supposed to be shared with TaskList?',
    context: 'Both files reimplement nearly identical filter state. Likely accidental duplication.',
    suggested_category: 'architecture',
    target_module: 'frontend/src/pages/Dashboard.tsx',
    answered: false,
  },
];

const mockConceptStats: ConceptStats = {
  total: 10,
  active: 8,
  seeds: 2,
  archived: 0,
  stale: 0,
  pending_questions: 2,
  by_category: { architecture: 3, constraint: 4, pattern: 2, seed: 1 },
  coverage_pct: 82,
  total_modules: 12,
  covered_modules: 10,
  concepts_count: 10,
};

// Mirror of useDashboardPanels DEFAULT_ALWAYS_IGNORED_GLOBS so the demo
// Scope panel renders agent-rule files as strikethrough/always-ignored.
const ALWAYS_IGNORED_GLOBS: string[] = [
  '**/AGENTS.md',
  '**/CLAUDE.md',
  '**/.cursor/rules/*.mdc',
  '**/.cursorrules',
  '**/.windsurfrules',
  '**/GEMINI.md',
];

// ────────────────────────────────────────────────────────────────────────────
// demo-repo file tree — a notional task-management web app (FastAPI backend +
// React frontend). Designed so the audit findings, concepts, and sub-atlases
// all anchor to real paths that visitors can trace through the demo.
// ────────────────────────────────────────────────────────────────────────────

const f = (name: string, status?: TreeNode['status'], chunks?: number): TreeNode => ({
  name, type: 'file', ...(status ? { status } : {}), ...(chunks != null ? { chunks } : {}),
});
const d = (name: string, children: TreeNode[]): TreeNode => ({ name, type: 'folder', children });

const demoFileTree: TreeNode[] = [
  d('backend', [
    d('api', [
      f('routes.py'), f('auth.py'), f('users.py'), f('tasks.py'), f('deps.py'),
    ]),
    d('core', [
      f('config.py'), f('security.py'), f('db.py'), f('scheduler.py'),
    ]),
    d('models', [
      f('base.py'), f('user.py'), f('task.py'), f('project.py'),
    ]),
    d('services', [
      f('task_service.py'), f('notification_service.py'), f('email.py'),
    ]),
    d('workers', [
      f('queue.py'), f('jobs.py'), f('retry.py'),
    ]),
  ]),
  d('frontend', [
    d('src', [
      d('components', [
        f('TaskList.tsx'), f('TaskCard.tsx'), f('Sidebar.tsx'),
      ]),
      d('pages', [
        f('Dashboard.tsx'), f('Login.tsx'), f('Settings.tsx'),
      ]),
      d('hooks', [
        f('useAuth.ts'), f('useTasks.ts'), f('useTheme.ts'),
      ]),
      d('api', [
        f('client.ts'), f('types.ts'),
      ]),
      d('lib', [
        f('date.ts'), f('format.ts'),
      ]),
    ]),
  ]),
  d('tests', [
    d('backend', [
      f('test_auth.py'), f('test_tasks.py'),
    ]),
    d('frontend', [
      f('tasks.test.ts'),
    ]),
  ]),
  d('docs', [
    f('README.md'),
    // Pre-selected in the demo's includedPaths Set — rendered with
    // status='indexed' so it reads as "already in the knowledge base"
    // while every other file lights up as `pending` when toggled on.
    f('ROADMAP.md', 'indexed', 12),
    f('ARCHITECTURE.md'),
  ]),
  d('scripts', [
    f('deploy.sh'),
  ]),
  { name: 'node_modules', type: 'folder', status: 'ignored', children: [] },
  { name: '.venv', type: 'folder', status: 'ignored', children: [] },
];

// Single mock project used by the demo sidebar's ProjectList. The name +
// path match the IndexStatusCard's `index_dir` below so the whole demo
// reads as one coherent "/volumes/filepath/demo-repo" project.
const DEMO_PROJECT_PATH = '/volumes/filepath/demo-repo';

// SidebarAIGateway needs a slots-status payload. Mock "all connected to
// local Ollama" — matches the most common dev state and keeps the
// labels generic (no real org / cloud provider names leak into the
// public storybook build).
const mockLLMSlots: LLMSlotsStatus = {
  running_tasks: [],
  embedding:    { configured: true, status: 'connected', model: 'nomic-embed-text',     provider: 'ollama' },
  small_model:  { configured: true, status: 'connected', model: 'qwen2.5:3b',           provider: 'ollama' },
  large_model:  { configured: true, status: 'connected', model: 'qwen2.5:14b',          provider: 'ollama' },
  code_model:   { configured: true, status: 'connected', model: 'qwen2.5-coder:7b',     provider: 'ollama' },
};

// SidebarPipelineQueue fetches from baseUrl/system/pipeline-queue. We
// point it at an unreachable host (the `.invalid` TLD is reserved by
// RFC 6761) so the fetch silently fails, the queue stays empty, and
// the visitor sees the collapsed "Pipeline Queue" header without any
// fake data. Real daemon at :8400 on the dev machine is bypassed.
const DEMO_DAEMON_URL = 'http://demo.invalid';
const initialMockProject: ProjectSummary = {
  id: 'demo-project',
  name: 'demo-repo',
  path: DEMO_PROJECT_PATH,
  mode: 'standalone',
  status: 'fresh',
  chunk_count: 1245,
  last_build_at: new Date(Date.now() - 7_200_000).toISOString(),
  activity_status: 'active',
  priority_level: 'none',
};

const mockScopes: ScopeSummary[] = [
  { id: 'global', display_name: 'Global', path_count: 18, assigned_to_role: null },
  { id: 'scope-backend', display_name: 'Backend', path_count: 9, assigned_to_role: null },
  { id: 'scope-docs', display_name: 'Docs only', path_count: 4, assigned_to_role: null },
];

const mockScopeStatus: ScopeStatus = {
  state: 'idle',
  pending_adds: 0,
  pending_removes: 0,
  pending_changes: 0,
  total_pending: 0,
  auto_rebuild: true,
  debounce_ms: 1500,
  error: null,
  last_rebuild_at: Date.now() / 1000 - 3600,
  stale_since: null,
  is_stale: false,
};

// Sub-atlases for the AtlasLensPanel. Each segment is a curated paragraph
// summarizing what the module does. Visitors can click into each segment in
// the demo to preview the body text — same affordance as the live app.
const ATLAS_NOW = new Date(Date.now() - 7_200_000).toISOString();
const mockAtlasSegments: NonNullable<AtlasStatus['segments']> = [
  {
    segment_id: 'seg-api',
    segment_name: 'API surface',
    dir_path: 'backend/api',
    file_count: 5,
    char_count: 3200,
    mode: 'llm',
    generated_at: ATLAS_NOW,
    stale: false,
    content:
`The HTTP entry point. routes.py mounts the FastAPI app and pulls every
protected route through deps.current_user. tasks.py is the largest router
and handles list/create/update/delete; auth.py owns the login + token
exchange flow and users.py is the smaller account-management surface.

The notable design choice here is that no route reaches into a model
directly — every write goes through services/task_service so the
"single source of truth for task state" concept holds at the API edge.`,
  },
  {
    segment_id: 'seg-models',
    segment_name: 'Persistence models',
    dir_path: 'backend/models',
    file_count: 4,
    char_count: 2100,
    mode: 'llm',
    generated_at: ATLAS_NOW,
    stale: false,
    content:
`SQLAlchemy ORM. base.py defines the declarative Base + a shared
mixin (created_at, updated_at). task.py is the central model and
includes a deleted_at column for soft-delete; project.py and user.py
are smaller.

Tasks belong to a Project; both Task and Project belong to a User.
The deleted_at pattern is consistent across all three but only Task
has a partial index — flagged as a seed concept awaiting promotion.`,
  },
  {
    segment_id: 'seg-services',
    segment_name: 'Business logic',
    dir_path: 'backend/services',
    file_count: 3,
    char_count: 2600,
    mode: 'llm',
    generated_at: ATLAS_NOW,
    stale: false,
    content:
`Service layer between the API and the models. task_service owns the
status-transition state machine for tasks; notification_service buffers
per-user events and flushes them on a 60s tick or login; email.py is
the SMTP transport plus a small Jinja template loader.

task_service is the biggest file in the backend at 18KB — audit has
flagged it as approaching the 20KB ceiling. The "single source of truth"
concept treats this as deliberate centralization; the audit treats it
as a refactor signal. Both can be right.`,
  },
  {
    segment_id: 'seg-workers',
    segment_name: 'Async workers',
    dir_path: 'backend/workers',
    file_count: 3,
    char_count: 1800,
    mode: 'llm',
    generated_at: ATLAS_NOW,
    stale: false,
    content:
`Background job runner. queue.py wraps the broker (Redis), jobs.py
declares the job handlers, retry.py owns the backoff policy.

Delivery is at-least-once — every job carries an idempotency key and
the queue dedupes on retry. This is the source of the "background jobs
are idempotent" constraint concept; the corresponding antibody fires
when a new job handler ships without an idempotency_key parameter.`,
  },
  {
    segment_id: 'seg-frontend',
    segment_name: 'React frontend',
    dir_path: 'frontend/src',
    file_count: 14,
    char_count: 6100,
    mode: 'llm',
    generated_at: ATLAS_NOW,
    stale: false,
    content:
`Single-page React app. pages/ hosts the route components (Dashboard,
Login, Settings); components/ are the leaf widgets (TaskList, TaskCard,
Sidebar). hooks/ wraps API access — useTasks is where optimistic-update
reconciliation lives, useAuth proxies token storage.

lib/date.ts is small but load-bearing: every rendered timestamp passes
through it for tz normalization. The "frontend never trusts client-side
timestamps" concept anchors here. Audit currently flags it as untested
even though it's a constraint-grade dependency.`,
  },
];

const mockAtlas: AtlasStatus = {
  exists: true,
  content: null,
  mode: 'llm',
  module_count: 12,
  file_count: 1100,
  char_count: 15_800,
  generated_at: ATLAS_NOW,
  routing: true,
  stale: false,
  segmented: true,
  segments: mockAtlasSegments,
};

// Finalize-group stage statuses (stages 11-15). All complete + healthy.
const mockRulesStatus: import('../../types').RulesStatus = {
  generated: true,
  stale: false,
  mode: 'llm',
  atlas_chars: 15_800,
};

const mockConceptsStatus: import('../../types').ConceptsStatus = {
  seeded: true,
  count: 10,
  questions: 2,
};

const mockAuditPipelineStatus: import('../../types').AuditPipelineStatus = {
  exists: true,
  finding_count: 10,
  tier2: true,
};

const mockAntibodiesStatus: import('../../types').AntibodiesStatus = {
  count: 6,
  firing: 0,
};

/**
 * Pipeline panel for the storybook demo. Renders the GraphEnrichmentPipeline
 * in a "healthy / fully-built" state with all 10 stages complete, and wires
 * local React state for the three group-collapse toggles AND the
 * fast/deep/finalize Manual/Auto switches. The component itself is purely
 * controlled — without a state-bearing wrapper its chevrons and switches
 * are no-ops.
 */
function PipelinePanelDemo() {
  const [fastCollapsed, setFastCollapsed] = useState(false);
  const [deepCollapsed, setDeepCollapsed] = useState(false);
  const [finalizeCollapsed, setFinalizeCollapsed] = useState(false);
  const [autoConfig, setAutoConfig] = useState<{
    fastSync: boolean;
    deepEnrichment: 'manual' | 'auto' | 'scheduled' | 'threshold';
    finalize: 'manual' | 'auto';
  }>({ fastSync: true, deepEnrichment: 'auto', finalize: 'manual' });

  const TOTAL = 1245;
  const built = new Date(Date.now() - 7_200_000).toISOString(); // 2h ago

  return (
    <div className="h-full overflow-y-auto">
      <GraphEnrichmentPipeline
        trace={{
          enabled: true,
          exists: true,
          building: false,
          counts: { nodes: TOTAL, edges: 3890 },
          last_build_at: built,
        }}
        inferredEdges={{ enabled: true, exists: true, edge_count: 42 }}
        augmentation={{
          enabled: true,
          total_nodes: TOTAL,
          augmented_nodes: TOTAL,
          validated_nodes: TOTAL,
          avg_confidence: 0.88,
          low_confidence_count: 0,
          last_augment_at: built,
          model: 'qwen2.5:3b',
        }}
        epistemic={{
          enabled: true,
          enriched_nodes: TOTAL,
          progress_current: TOTAL,
          progress_total: TOTAL,
          avg_confidence: 0.92,
          running: false,
        }}
        modules={{
          enabled: true,
          module_count: 12,
          total_files_clustered: 1100,
          running: false,
        }}
        atlas={mockAtlas}
        rulesStatus={mockRulesStatus}
        conceptsStatus={mockConceptsStatus}
        auditPipelineStatus={mockAuditPipelineStatus}
        antibodiesStatus={mockAntibodiesStatus}
        deepening={{
          running: false,
          total_scored: TOTAL,
          settled_count: TOTAL,
          settled_ratio: 1.0,
          avg_score: 0.91,
        }}
        knowledge={{
          enabled: true,
          running: false,
          chunks_embedded: 3200,
          deep_chunks_embedded: 3200,
          last_run_at: built,
        }}
        autoConfig={autoConfig}
        onAutoConfigChange={setAutoConfig}
        fastCollapsed={fastCollapsed}
        deepCollapsed={deepCollapsed}
        finalizeCollapsed={finalizeCollapsed}
        onToggleFastCollapsed={() => setFastCollapsed((c) => !c)}
        onToggleDeepCollapsed={() => setDeepCollapsed((c) => !c)}
        onToggleFinalizeCollapsed={() => setFinalizeCollapsed((c) => !c)}
        isPro={true}
        onRebuild={(scope) => console.log('[Story] onRebuild', scope)}
        onStopRebuild={() => console.log('[Story] onStopRebuild')}
        onRunFastSync={() => console.log('[Story] onRunFastSync')}
        onRunDeepEnrichment={() => console.log('[Story] onRunDeepEnrichment')}
        onRunFinalize={() => console.log('[Story] onRunFinalize')}
      />
    </div>
  );
}

/**
 * Stateful demo wrapper for DeepAnalysisSettings — without it the mode/
 * frequency/hour selects feel stuck when clicked.
 */
function DeepAnalysisDemo() {
  const [schedule, setSchedule] = useState<DeepAnalysisSchedule>({
    mode: 'scheduled',
    frequency: 'daily',
    hour: 0,
    budget_enabled: true,
    budget_max_tokens: 100000,
    budget_max_minutes: 60,
    budget_max_items: 500,
    priority: 'lowest_confidence',
  });
  return (
    <div className="h-full overflow-y-auto p-4">
      <DeepAnalysisSettings
        schedule={schedule}
        onScheduleChange={setSchedule}
        largeModelConfigured={true}
        fastModelConfigured={true}
      />
    </div>
  );
}

/** Stateful demo wrapper for AtlasLensPanel role picker. */
function AtlasPanelDemo() {
  const [role, setRole] = useState<string | null>(null);
  return (
    <AtlasLensPanel
      atlas={mockAtlas}
      role={role}
      onRoleChange={setRole}
      regenerating={false}
      onRegenerate={() => console.log('[Story] onRegenerate atlas')}
    />
  );
}

/** Stateful demo wrapper for OpportunitiesPanel filter dropdowns + show-dismissed toggle. */
function OpportunitiesPanelDemo() {
  const [categoryFilter, setCategoryFilter] = useState<string | null>(null);
  const [priorityFilter, setPriorityFilter] = useState<string | null>(null);
  const [sourceFilter, setSourceFilter] = useState<string | null>(null);
  const [showDismissed, setShowDismissed] = useState(false);
  return (
    <OpportunitiesPanel
      items={[]}
      summary={null}
      loading={false}
      refreshing={false}
      error={null}
      onRefresh={() => console.log('[Story] onRefresh opportunities')}
      onDismiss={noop}
      onRestore={noop}
      onExport={noop}
      categoryFilter={categoryFilter}
      onCategoryFilterChange={setCategoryFilter}
      priorityFilter={priorityFilter}
      onPriorityFilterChange={setPriorityFilter}
      sourceFilter={sourceFilter}
      onSourceFilterChange={setSourceFilter}
      showDismissed={showDismissed}
      onShowDismissedChange={setShowDismissed}
    />
  );
}

/**
 * Stateful demo wrapper for FolderTreePanel — the Scope panel in the
 * dashboard. Mirrors the prop set the live useDashboardPanels hook
 * passes (scope dropdown + exclude UI + always-ignored patterns +
 * scopeStatus), so the storybook demo shows the same surface area as
 * the running app. Previously the demo passed a stripped-down prop
 * set and the conditional features (scope picker, exclude toggle)
 * were silently hidden.
 */
function ScopePanelDemo({
  data,
  includedPaths,
  onToggleInclude,
  pathWeights,
  onWeightChange,
}: {
  data: TreeNode[];
  includedPaths: Set<string>;
  onToggleInclude: (paths: string[], action: 'add' | 'remove') => void;
  pathWeights: Record<string, number>;
  onWeightChange: (path: string, weight: number | null) => void;
}) {
  const [activeScopeId, setActiveScopeId] = useState<string>('global');
  const [scopes, setScopes] = useState<ScopeSummary[]>(mockScopes);
  const [excludedPaths, setExcludedPaths] = useState<Set<string>>(
    new Set(['tests', 'scripts/deploy.sh'])
  );

  const handleToggleExclude = (paths: string[], action: 'add' | 'remove') => {
    setExcludedPaths((prev) => {
      const next = new Set(prev);
      for (const p of paths) action === 'add' ? next.add(p) : next.delete(p);
      return next;
    });
  };

  const handleCreateScope = async (display_name: string): Promise<ScopeRecord | null> => {
    const id = `scope-${Date.now()}`;
    setScopes((s) => [...s, { id, display_name, path_count: 0, assigned_to_role: null }]);
    return { id, display_name, paths: [], assigned_to_role: null };
  };
  const handleRenameScope = async (id: string, display_name: string) => {
    setScopes((s) => s.map((sc) => (sc.id === id ? { ...sc, display_name } : sc)));
  };
  const handleDeleteScope = async (id: string) => {
    setScopes((s) => s.filter((sc) => sc.id !== id));
    if (activeScopeId === id) setActiveScopeId('global');
  };

  return (
    <FolderTreePanel
      data={data}
      includedPaths={includedPaths}
      scopeStatus={mockScopeStatus}
      onToggleInclude={onToggleInclude}
      pathWeights={pathWeights}
      onWeightChange={onWeightChange}
      excludedPaths={excludedPaths}
      onToggleExclude={handleToggleExclude}
      alwaysIgnoredPatterns={ALWAYS_IGNORED_GLOBS}
      scopes={scopes}
      activeScopeId={activeScopeId}
      onSetActiveScope={setActiveScopeId}
      onCreateScope={handleCreateScope}
      onRenameScope={handleRenameScope}
      onDeleteScope={handleDeleteScope}
      className="h-full border-0 shadow-none"
      title="Knowledge Scope"
      bare
    />
  );
}

/** Stateful demo wrapper for ConceptsPanel — approve/archive/delete remove rows visually. */
function ConceptsPanelDemo() {
  const [concepts, setConcepts] = useState<ConceptItem[]>(mockConcepts);
  const [questions, setQuestions] = useState<ConceptQuestionItem[]>(mockConceptQuestions);
  const handleApprove = (id: string) =>
    setConcepts((cs) => cs.map((c) => (c.id === id ? { ...c, status: 'active' } : c)));
  const handleArchive = (id: string) =>
    setConcepts((cs) => cs.map((c) => (c.id === id ? { ...c, status: 'archived' } : c)));
  const handleDelete = (id: string) =>
    setConcepts((cs) => cs.filter((c) => c.id !== id));
  const handleAnswer = (questionId: string) =>
    setQuestions((qs) => qs.map((q) => (q.id === questionId ? { ...q, answered: true } : q)));
  return (
    <ConceptsPanel
      concepts={concepts}
      questions={questions}
      stats={mockConceptStats}
      loading={false}
      initializing={false}
      error={null}
      onInitialize={noop}
      onApprove={handleApprove}
      onArchive={handleArchive}
      onDelete={handleDelete}
      onAnswerQuestion={handleAnswer}
    />
  );
}

/** Generate mock file content for Storybook */
function mockFileContent(path: string): string {
  const name = path.split('/').pop() ?? path;
  if (name.endsWith('.md')) {
    return `# ${name}\n\nThis is the content of \`${path}\`.\n\n## Overview\n\nLorem ipsum dolor sit amet, consectetur adipiscing elit.\nSed do eiusmod tempor incididunt ut labore et dolore magna aliqua.\n`;
  }
  return `# ${path}\n# Auto-generated mock content\n\ndef example():\n    """Example function from ${name}."""\n    print("Hello from ${name}")\n    return True\n`;
}

export const FullDashboard: StoryObj = {
  render: () => {
    // Phase 131: every visit to the storybook demo should boot from the
    // canonical DEFAULT_LAYOUT in packages/ui/src/types/layout.ts (the same
    // config the dashboard app ships with). Clear any saved customisation
    // BEFORE useLayoutPersistence reads from localStorage on mount.
    useState(() => {
      try {
        window.localStorage.removeItem('storybook_fulldashboard_layout');
      } catch {
        // localStorage may be blocked in some sandboxed iframes; that's fine.
      }
      return null;
    });

    const [building, setBuilding] = useState(false);
    const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

    // Single demo project, lifted to state so the active/inactive toggle
    // and the star priority cycle actually work in the demo.
    const [projects, setProjects] = useState<ProjectSummary[]>([initialMockProject]);
    const handleToggleActive = useCallback((projectId: string, active: boolean) => {
      setProjects((prev) => prev.map((p) =>
        p.id === projectId ? { ...p, activity_status: active ? 'active' : 'inactive' } : p
      ));
    }, []);
    const handleCyclePriority = useCallback((projectId: string) => {
      setProjects((prev) => prev.map((p) => {
        if (p.id !== projectId) return p;
        const next: ProjectSummary['priority_level'] =
          p.priority_level === 'none' ? 'boost' :
          p.priority_level === 'boost' ? 'exclusive' :
          'none';
        return { ...p, priority_level: next };
      }));
    }, []);

    const [query, setQuery] = useState('');
    const [searchK, setSearchK] = useState(8);
    const [minScore, setMinScore] = useState(0.15);
    const [searchLoading, setSearchLoading] = useState(false);
    const [results, setResults] = useState<SearchResult[]>([]);
    const [selectedChunk, setSelectedChunk] = useState<SearchResult | null>(null);
    const [selectedTraceNode, setSelectedTraceNode] = useState<string>('1');
    const [symbolQuery, setSymbolQuery] = useState('');
    
    const [contextK, setContextK] = useState(5);
    const [maxChars, setMaxChars] = useState(6000);
    const [includeSources, setIncludeSources] = useState(true);
    const [includeScores, setIncludeScores] = useState(false);
    const [structured, setStructured] = useState(false);
    const [context, setContext] = useState('');

    // RAG inclusion state (primary functionality).
    //
    // Initial state: ONLY `docs/ROADMAP.md`. Critically, do NOT pre-include
    // the parent folder (`docs`) here — FolderTree's `isPathOrAncestorIncluded`
    // returns true if any ancestor is in the Set, so seeding both a folder
    // AND its children would make the file appear checked even after the
    // user un-checks it (its parent is still in the Set → ancestor inclusion
    // wins). Seed only the leaf so toggles round-trip cleanly.
    const [includedPaths, setIncludedPaths] = useState<Set<string>>(
      new Set(['docs/ROADMAP.md'])
    );

    const handleToggleInclude = useCallback((paths: string[], action: 'add' | 'remove') => {
      setIncludedPaths((prev) => {
        const next = new Set(prev);
        for (const path of paths) {
          if (action === 'remove') {
            next.delete(path);
          } else {
            next.add(path);
          }
        }
        return next;
      });
    }, []);

    // Path weights state
    const [pathWeights, setPathWeights] = useState<Record<string, number>>({});

    const handleWeightChange = useCallback((path: string, weight: number | null) => {
      setPathWeights((prev) => {
        const next = { ...prev };
        if (weight === null) {
          delete next[path];
        } else {
          next[path] = weight;
        }
        return next;
      });
    }, []);

    // Pinned files state — each pinned file becomes its own dashboard panel
    const [pinnedFiles, setPinnedFiles] = useState<PinnedTextFile[]>([]);
    const layoutApiRef = useRef<DashboardLayoutApi | null>(null);

    const handlePinFile = useCallback((path: string) => {
      const name = path.split('/').pop() || 'unknown';
      const content = mockFileContent(path);
      const panelId = `${PINNED_PREFIX}${path}`;

      setPinnedFiles((prev) => {
        if (prev.some((f) => f.id === path)) return prev;
        return [...prev, { id: path, path, name, content }];
      });

      // Add a visible panel to the grid
      layoutApiRef.current?.addPanel(panelId, { height: 8, w: 6 });
    }, []);

    const handleUnpinFile = useCallback((pathOrPanelId: string) => {
      // Accept either a raw path or a "pinned:path" panel ID
      const path = pathOrPanelId.startsWith(PINNED_PREFIX)
        ? pathOrPanelId.slice(PINNED_PREFIX.length)
        : pathOrPanelId;
      const panelId = `${PINNED_PREFIX}${path}`;

      setPinnedFiles((prev) => prev.filter((f) => f.id !== path));
      layoutApiRef.current?.removePanel(panelId);
    }, []);

    const handlePanelClose = useCallback((panelId: string) => {
      if (panelId.startsWith(PINNED_PREFIX)) {
        handleUnpinFile(panelId);
      }
    }, [handleUnpinFile]);

    const pinnedPathsSet = useMemo(() => new Set(pinnedFiles.map((f) => f.id)), [pinnedFiles]);

    const handleBuild = () => {
      setBuilding(true);
      setTimeout(() => setBuilding(false), 2000);
    };

    const handleSearch = () => {
      setSearchLoading(true);
      setTimeout(() => {
        setResults(mockResults);
        setSearchLoading(false);
      }, 800);
    };

    const handleGetContext = () => {
      setContext('# Source: src/api/client.ts ...');
    };

    const panelContent = useMemo(() => ({
      'usage-guide': (
        <UsageGuidePanel bare />
      ),
      status: (
        <IndexStatusCard
          stats={{
            loaded: true,
            total_documents: 1234,
            model: 'nomic-embed-text',
            built_at: new Date().toISOString(),
            index_dir: DEMO_PROJECT_PATH,
          }}
          building={building}
          onBuild={handleBuild}
          bare
        />
      ),
      'llm-status': (
        <LLMStatusWidget services={sampleLLMServices} bare />
      ),
      search: (
        <SearchPanel
          query={query}
          onQueryChange={setQuery}
          k={searchK}
          onKChange={setSearchK}
          minScore={minScore}
          onMinScoreChange={setMinScore}
          onSearch={handleSearch}
          loading={searchLoading}
          bare
        />
      ),
      'context-options': (
        <ContextOptionsPanel
          k={contextK}
          onKChange={setContextK}
          maxChars={maxChars}
          onMaxCharsChange={setMaxChars}
          includeSources={includeSources}
          onIncludeSourcesChange={setIncludeSources}
          includeScores={includeScores}
          onIncludeScoresChange={setIncludeScores}
          structured={structured}
          onStructuredChange={setStructured}
          onGetContext={handleGetContext}
          onCopyContext={() => navigator.clipboard.writeText(context)}
          hasContext={!!context}
          disabled={!query.trim()}
          bare
        />
      ),
      results: (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 h-full overflow-hidden">
          <div className="h-full overflow-y-auto min-h-0">
            <SearchResultsList
              results={results}
              selectedId={selectedChunk?.chunk_id}
              onSelect={setSelectedChunk}
            />
          </div>
          <div className="h-full overflow-y-auto min-h-0 border-l border-border pl-4">
            <ChunkPreview
              content={selectedChunk?.content}
              sourcePath={selectedChunk?.source_path}
              section={selectedChunk?.section}
              bare
            />
          </div>
        </div>
      ),
      'context-output': (
        <ContextOutput
          context={context}
          meta={context ? { chunks: [], total_chars: context.length, estimated_tokens: 100 } : null}
          bare
        />
      ),
      'file-tree': (
        <ScopePanelDemo
          data={demoFileTree}
          includedPaths={includedPaths}
          onToggleInclude={handleToggleInclude}
          pathWeights={pathWeights}
          onWeightChange={handleWeightChange}
        />
      ),
      // Dynamic per-file pinned panels
      ...Object.fromEntries(
        pinnedFiles.map((f) => [
          `${PINNED_PREFIX}${f.path}`,
          <div key={f.path} className="h-full flex flex-col overflow-hidden">
            <CodeViewer 
              content={f.content} 
              path={f.path}
              className="h-full border-0 rounded-none"
            />
          </div>,
        ])
      ),
      trace: (
        <div className="h-full flex flex-col">
          <div className="mb-4">
            <SymbolSearchInput 
              value={symbolQuery}
              onChange={setSymbolQuery}
            />
          </div>
          <div className="flex-1 min-h-0">
            <TraceGraph 
              nodes={sampleTraceNodes} 
              edges={[]} 
              selectedNode={selectedTraceNode}
              onSelectNode={setSelectedTraceNode}
            />
          </div>
        </div>
      ),
      'graph-structure': (
        <GraphStructurePanel
          summary={mockCoverageSummary}
          epistemic={{ enabled: true, enriched_nodes: 569, avg_confidence: 0.9, running: false }}
          augmentation={{ enabled: true, total_nodes: 670, augmented_nodes: 670, validated_nodes: 600, avg_confidence: 0.95, low_confidence_count: 0 }}
          untracedFiles={mockUntracedFiles}
          staleFiles={mockStaleFiles}
          excludedFiles={mockExcludedFiles}
          building={false}
          loading={false}
          onTraceAll={() => console.log('[Story] Trace All')}
          onRetraceStale={() => console.log('[Story] Re-trace Stale')}
          onAddExcludePattern={(p: string) => console.log('[Story] Add exclude:', p)}
          onRemoveExcludePattern={(p: string) => console.log('[Story] Remove exclude:', p)}
          onRefresh={() => console.log('[Story] Refresh')}
          traceExists={true}
        />
      ),
      'trace-pipeline': <PipelinePanelDemo />,
      'deep-analysis': <DeepAnalysisDemo />,
      'log-console': (
        <LogConsole
          logs={[
            { timestamp: Date.now() / 1000, level: 'INFO', logger: 'daemon', message: 'Daemon started', created: Date.now() / 1000 },
            { timestamp: Date.now() / 1000, level: 'INFO', logger: 'project', message: 'Project loaded', created: Date.now() / 1000 },
          ]}
          onClear={() => {}}
          defaultExpanded={true}
          className="h-full border-none shadow-none bg-transparent"
        />
      ),
      'activity-heatmap': (
        <ActivityHeatmap
          data={generateSampleActivityData(12)}
          weeks={12}
          showLegend={true}
          showLabels={true}
          className="h-full border-none shadow-none bg-transparent"
        />
      ),
      'agent-ops': (
        <AgentOpsPanel 
          data={{ hr: { last_run: '2h ago', push_count: 5 }, researcher: { last_run: null, push_count: 0 }, custodian: { last_run: '1d ago', push_count: 0 } }}
          loading={false} 
        />
      ),
      'audit': (
        <AuditPanel
          status={{
            running: false,
            error: null,
            has_results: true,
            finding_count: mockAuditFindings.length,
            severity_counts: { critical: 0, warning: 1, info: 2, suggestion: 1 },
            last_run: {
              generated_at: new Date(Date.now() - 1_800_000).toISOString(),
              graph_node_count: 1245,
              graph_edge_count: 3890,
              finding_count: mockAuditFindings.length,
              document_count: 0,
              analyzers_run: ['stale-docs', 'todo-scanner', 'oversized-files', 'doc-coverage'],
              documents: [],
            },
          }}
          findings={mockAuditFindings}
          reports={mockAuditReports}
          onRunAudit={noop}
          onViewReport={noop}
        />
      ),
      'concepts': <ConceptsPanelDemo />,
      'atlas': <AtlasPanelDemo />,
      'opportunities': <OpportunitiesPanelDemo />,
      'roadmap': (
        <RoadmapPanel 
          nodes={[]} 
          questions={[]} 
          northStar={null} 
          appEthos="SourcePrep Ethos" 
          generating={false} 
          scanning={false} 
          error={null} 
          ready={true} 
          lastGeneratedAt="" 
          modelUsed=""
          onGenerate={noop}
          onScanTodos={noop}
          onUpdateEthos={noop}
          onPromoteNode={noop}
          onDismissNode={noop}
          onDeleteNode={noop}
          onCreateNode={noop}
          onAnswerQuestion={noop}
          onSuggestSprint={noop}
          onMineRoadmap={noop}
        />
      ),
    }), [building, query, searchK, minScore, searchLoading, results, selectedChunk, contextK, maxChars, includeSources, includeScores, structured, context, symbolQuery, selectedTraceNode, includedPaths, pinnedFiles, handleToggleInclude, pathWeights, handleWeightChange]);

    // Dynamic panel definitions for pinned files
    const dynamicPanelDefs = useMemo<PanelDefinition[]>(() =>
      pinnedFiles.map((f) => ({
        id: `${PINNED_PREFIX}${f.path}`,
        title: f.name,
        icon: FileText,
        minHeight: 4,
        defaultHeight: 8,
        category: 'projects' as const,
        closeable: true,
        resizable: true,
      })),
      [pinnedFiles]
    );

    const allPanelDefs = useMemo(
      () => [...STORY_PANELS, ...dynamicPanelDefs],
      [dynamicPanelDefs]
    );

    const panelDetails = useMemo(() => ({
      'llm-status': (
        <div className="p-6">
          <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
            <Settings className="w-6 h-6" />
            LLM Settings
          </h2>
          <div className="p-4 bg-surface-raised rounded-lg border border-border">
            Mock AIModelsSettings content would go here.
          </div>
        </div>
      ),
      'file-tree': (
        <FileExplorerDetail
          treeData={demoFileTree}
          pinnedPaths={pinnedPathsSet}
          onPinFile={handlePinFile}
          onUnpinFile={handleUnpinFile}
          includedPaths={includedPaths}
          onToggleInclude={handleToggleInclude}
          pathWeights={pathWeights}
          onWeightChange={handleWeightChange}
        />
      ),
    }), [includedPaths, pinnedPathsSet, handleToggleInclude, handlePinFile, handleUnpinFile, pathWeights, handleWeightChange]);

    return (
      <AppShell
        sidebar={
          <Sidebar
            collapsed={sidebarCollapsed}
            onCollapseToggle={() => setSidebarCollapsed((c) => !c)}
            footer={sidebarCollapsed ? (
              <SidebarAIGateway slotsStatus={mockLLMSlots} collapsed onOpenDetails={noop} />
            ) : undefined}
          >
            {!sidebarCollapsed && (
              <ProjectList
                projects={projects}
                selectedProjectId="demo-project"
                onProjectSelect={noop}
                onAddProject={noop}
                onDeleteProject={noop}
                onArchiveProject={noop}
                onUnarchiveProject={noop}
                onToggleActive={handleToggleActive}
                onCyclePriority={handleCyclePriority}
                isPro={true}
                beforeActions={
                  <>
                    <SidebarPipelineQueue baseUrl={DEMO_DAEMON_URL} />
                    <SidebarAIGateway slotsStatus={mockLLMSlots} onOpenDetails={noop} />
                  </>
                }
              />
            )}
          </Sidebar>
        }
      >
        <div className="h-full bg-background p-6 overflow-auto">
          <ModularDashboard
            panelDefinitions={allPanelDefs}
            panelContent={panelContent}
            panelDetails={panelDetails}
            storageKey="storybook_fulldashboard_layout"
            onPanelClose={handlePanelClose}
            onLayoutReady={(api) => { layoutApiRef.current = api; }}
            hidePanelPicker
          />
        </div>
      </AppShell>
    );
  },
};

export const EmptyState: StoryObj = {
  render: () => {
    const panelContent = {
      status: (
        <div className="p-4">
          <IndexStatusCard stats={{ loaded: false }} bare />
        </div>
      ),
      search: (
        <div className="p-4">
          <SearchPanel
            query=""
            onQueryChange={() => {}}
            k={8}
            onKChange={() => {}}
            minScore={0.15}
            onMinScoreChange={() => {}}
            onSearch={() => {}}
            disabled
            bare
          />
        </div>
      ),
    };

    return (
      <div className="min-h-screen bg-background p-6">
        <ModularDashboard
          panelDefinitions={STORY_PANELS}
          panelContent={panelContent}
          storageKey="storybook_emptystate_layout"
        />
      </div>
    );
  },
};
