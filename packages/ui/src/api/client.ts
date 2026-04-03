import { ApiClientError } from './errors';
import type {
  ApiEnvelope,
  AssembleContextRequest,
  AssembleContextResponse,
  CreateProjectRequest,
  CreateProjectResponse,
  UpdateProjectRequest,
  UpdateProjectResponse,
  DeleteProjectResponse,
  BuildProjectResponse,
  ListProjectsResponse,
  SearchRequest,
  SearchResponse,
  WatchActionResponse,
} from './types';
import type { LLMStatus, LicenseStatus, Project, ProjectStatus, TraceCoverage, TraceStatus, WatchStatus, GlobalConfig, ModelStatusResult, ModelReadinessStatus, AugmentationStatus, DeepAnalysisRunStatus, LLMSlotsStatus, EpistemicStatus, ModuleStatus, DeepeningStatus, KnowledgeEmbeddingStatus, GraphEngineStatus, PipelineStatus, CrashedPipelineRun, AssignmentMode, LLMAssignmentBlock } from '../types';

export interface FileTreeNode {
  name: string;
  type: 'file' | 'folder';
  children?: FileTreeNode[];
  status?: 'indexed' | 'pending' | 'pending_removal' | 'ignored' | 'error';
  chunks?: number;
  has_children?: boolean;
}

export interface ApiClient {
  // Configuration
  readonly baseUrl: string;

  // Health
  getHealth(): Promise<{ status: string; version: string }>;

  // Projects CRUD
  listProjects(): Promise<ListProjectsResponse>;
  createProject(request: CreateProjectRequest): Promise<CreateProjectResponse>;
  getProject(projectId: string): Promise<{ project: Project }>;
  updateProject(projectId: string, request: UpdateProjectRequest): Promise<UpdateProjectResponse>;
  deleteProject(projectId: string, purge?: boolean): Promise<DeleteProjectResponse>;

  // Project status & build
  getProjectStatus(projectId: string): Promise<ProjectStatus>;
  buildProject(projectId: string, full?: boolean, includedPaths?: string[]): Promise<BuildProjectResponse>;

  // Search & context
  search(projectId: string, request: SearchRequest): Promise<SearchResponse>;
  assembleContext(projectId: string, request: AssembleContextRequest): Promise<AssembleContextResponse>;

  // Trace
  getTraceStatus(projectId: string): Promise<TraceStatus>;
  searchTrace(projectId: string, query: string, kinds?: string[], limit?: number): Promise<{ nodes: any[] }>;
  getTraceNode(projectId: string, nodeId: string): Promise<{ node: any; in_degree: number; out_degree: number }>;
  getTraceNeighbors(projectId: string, nodeId: string, direction?: string): Promise<{ nodes: any[]; edges: any[] }>;
  buildTrace(projectId: string): Promise<{ started: boolean }>;
  getTraceCoverage(projectId: string): Promise<TraceCoverage>;
  updateTraceIgnore(projectId: string, action: 'add' | 'remove', patterns: string[]): Promise<{ ignore_patterns: string[] }>;

  // Roots & Files
  getProjectRoots(projectId: string): Promise<{ roots: string[] }>;
  getProjectFiles(projectId: string, path?: string, depth?: number): Promise<{ path: string; tree: FileTreeNode[] }>;
  getProjectFileContent(projectId: string, path: string): Promise<{ content: string; path: string; size: number }>;
  detectStack(projectId: string): Promise<{ recommended_globs: string[]; detected_presets: string[]; all_presets: Record<string, string[]> }>;

  // Watch
  startWatch(projectId: string): Promise<WatchActionResponse>;
  stopWatch(projectId: string): Promise<WatchActionResponse>;
  getWatchStatus(projectId: string): Promise<WatchStatus>;

  // Path Weights
  getPathWeights(projectId: string): Promise<{ path_weights: Record<string, number> }>;
  updatePathWeights(projectId: string, pathWeights: Record<string, number>): Promise<{ path_weights: Record<string, number> }>;

  // Included Paths (Knowledge Scope)
  getIncludedPaths(projectId: string): Promise<{ included_paths: string[] }>;
  updateIncludedPaths(projectId: string, includedPaths: string[]): Promise<{ included_paths: string[] }>;

  // LLM
  getLLMStatus(): Promise<LLMStatus>;

  // Embedding
  getEmbeddingStatus(): Promise<{ available: boolean; model: string; dim: number; downloaded: boolean }>;
  downloadEmbedding(): Promise<{ status: string }>;

  // Compression
  getCompressionStatus(): Promise<{ lingua: any; lod: any }>;
  downloadLinguaModel(): Promise<{ status: string }>;

  // Activity & Coverage
  getProjectActivity(projectId: string, weeks?: number): Promise<{ days: any[]; totals: { embeddings: number; trace: number; builds: number } }>;
  getProjectCoverage(projectId: string): Promise<{ tree: any[] }>;

  // License
  getLicense(): Promise<LicenseStatus>;
  activateLicense(key: string): Promise<LicenseStatus>;
  deactivateLicense(): Promise<LicenseStatus>;
  setDevTierOverride(tier: string | null): Promise<LicenseStatus>;

  // Global Config
  getGlobalConfig(): Promise<GlobalConfig>;
  updateGlobalConfig(config: GlobalConfig): Promise<GlobalConfig>;

  // LLM Proxy
  testLLMConnectivity(): Promise<{ ollama: { connected: boolean } }>;
  testLLMEndpoint(provider: string, url: string, apiKey?: string): Promise<{ success: boolean; models?: string[] }>;
  fetchLLMModels(provider: string, url: string, apiKey?: string): Promise<{ models: string[] }>;
  testLLMModel(provider: string, url: string, model: string, kind: string, apiKey?: string, slot?: string): Promise<{ success: boolean; message: string; model_status?: ModelReadinessStatus; warnings?: string[]; recommendations?: Record<string, any> }>;
  getModelStatus(provider: string, url: string, model: string, ensureReady?: boolean, apiKey?: string): Promise<ModelStatusResult>;

  // LLM Slot Connectivity
  getLLMSlotsStatus(): Promise<LLMSlotsStatus>;
  switchAssignmentMode(mode: AssignmentMode, blocks?: LLMAssignmentBlock[]): Promise<{ success: boolean; old_mode: string; new_mode: string; unloaded_models: string[]; kept_models: string[] }>;

  // Augmentation & Deep Analysis
  getAugmentStatus(projectId: string): Promise<AugmentationStatus>;
  runAugmentation(projectId: string, maxItems?: number): Promise<{ started: boolean; task_id: string }>;
  getDeepAnalysisStatus(projectId: string): Promise<DeepAnalysisRunStatus>;
  runDeepAnalysis(projectId: string, opts?: { max_items?: number; max_tokens?: number; max_minutes?: number }): Promise<{ started: boolean; task_id: string }>;
  cancelDeepAnalysis(projectId: string): Promise<{ cancelled: boolean }>;

  // Graph & index destruction
  destroyGraph(projectId: string): Promise<{ deleted: string[]; errors: string[] }>;
  destroyIndex(projectId: string): Promise<{ deleted: string[]; errors: string[] }>;
  destroyAtlas(projectId: string): Promise<{ deleted: string[]; errors: string[] }>;
  destroyGroupReasoning(projectId: string): Promise<{ deleted: string[]; errors: string[] }>;
  destroyDeepEnrichment(projectId: string): Promise<{ deleted: string[]; errors: string[] }>;

  // Epistemic Enrichment, Modules & Deepening
  getEpistemicStatus(projectId: string): Promise<EpistemicStatus>;
  runEpistemic(projectId: string, maxItems?: number): Promise<{ started: boolean; task_id: string }>;
  getModuleStatus(projectId: string): Promise<ModuleStatus>;
  runModuleSynthesis(projectId: string): Promise<{ started: boolean; task_id: string }>;
  getDeepeningStatus(projectId: string): Promise<DeepeningStatus>;
  runDeepening(projectId: string, opts?: { max_iterations?: number; batch_size?: number }): Promise<{ started: boolean; task_id: string }>;

  // Knowledge Embedding (Stage 7)
  getKnowledgeStatus(projectId: string): Promise<KnowledgeEmbeddingStatus>;
  runKnowledgeBuild(projectId: string): Promise<{ started: boolean; building: boolean }>;

  // Unified Graph Engine
  getGraphEngineStatus(projectId: string): Promise<GraphEngineStatus>;

  // Pipeline Orchestrator (Phase 24 SM-6)
  runPipelineFast(projectId: string): Promise<{ started: boolean; group: string }>;
  runPipelineDeep(projectId: string): Promise<{ started: boolean; group: string }>;
  runPipelineAll(projectId: string): Promise<{ started: boolean; group: string }>;
  getPipelineStatus(projectId: string): Promise<PipelineStatus>;
  cancelPipeline(projectId: string, group: string): Promise<{ cancelled: boolean; group: string }>;
  pausePipeline(projectId: string, group: string): Promise<{ paused: boolean; group: string }>;
  resumePipeline(projectId: string, group: string): Promise<{ resumed: boolean; group: string }>;
  swapPipelineModel(projectId: string, group: string): Promise<{ swapped: boolean; paused_at_stage: string; resumed: boolean }>;
  getPipelineBudget(projectId: string): Promise<{ tokens_used: number; max_tokens: number; window_minutes: number; remaining: number; window_resets_in: number }>;

  // Pipeline Crash Protection (Phase 25)
  getCrashedRuns(projectId?: string): Promise<{ crashed_runs: CrashedPipelineRun[]; count: number }>;
  resumeCrashedRun(runId: string): Promise<{ resumed: boolean; run_id: string }>;
  discardCrashedRun(runId: string): Promise<{ discarded: boolean; run_id: string }>;

  // Pipeline Provenance (Phase 49)
  getPipelineProvenance(projectId: string): Promise<import('../types').PipelineProvenance>;

  // Codebase Atlas (Phase 29)
  getAtlas(projectId: string): Promise<import('../types').AtlasStatus>;
  regenerateAtlas(projectId: string): Promise<import('../types').AtlasStatus>;

  // Settings Store (Phase 24)
  getSettings(): Promise<Record<string, any>>;
  getSetting(key: string): Promise<{ key: string; value: any }>;
  setSetting(key: string, value: any): Promise<{ key: string; value: any }>;
  deleteSetting(key: string): Promise<{ key: string; deleted: boolean }>;
  getPipelineConfig(): Promise<any>;
  updatePipelineConfig(config: {
    fast_sync_auto?: boolean;
    deep_enrichment_mode?: string;
    schedule_frequency?: string;
    schedule_day_of_week?: number;
    schedule_hour?: number;
    schedule_threshold_enabled?: boolean;
    schedule_time_enabled?: boolean;
    threshold_percent?: number;
    budget_max_tokens?: number;
    budget_max_minutes?: number;
    budget_max_items?: number;
    llm_concurrency?: number;
    llm_concurrency_fast?: number;
    llm_concurrency_code?: number;
    llm_concurrency_deep?: number;
  }): Promise<any>;
  getProjectSettings(projectId: string): Promise<Record<string, any>>;
  setProjectSetting(projectId: string, key: string, value: any): Promise<{ key: string; value: any }>;

  // Advanced Config
  getAdvancedConfig(): Promise<import('../types').AdvancedConfig>;
  updateAdvancedConfig(config: Partial<import('../types').AdvancedConfig>): Promise<import('../types').AdvancedConfig>;

  // Compute Nodes (Phase 45D)
  getComputeNodes(): Promise<{ nodes: import('../types').ComputeNode[]; count: number }>;
  createComputeNode(node: Omit<import('../types').ComputeNode, 'id'>): Promise<import('../types').ComputeNode>;
  updateComputeNode(nodeId: string, updates: Partial<import('../types').ComputeNode>): Promise<import('../types').ComputeNode>;
  deleteComputeNode(nodeId: string): Promise<{ deleted: string }>;
  getComputeNodeStatus(nodeId: string): Promise<import('../types').SchedulerNodeStatus & { node_id: string; name: string }>;
  getSchedulerStatus(): Promise<import('../types').SchedulerStatus>;

  // Admin Policy (EA-C3)
  getAdminPolicy(): Promise<import('../types').AdminPolicy>;

  // Admin Security (EA-I)
  getSecurityHealth(): Promise<import('../components/enterprise/EnterpriseAdminPanel').SecurityHealthResult>;
  getSecurityEvents(limit?: number): Promise<Array<{ timestamp: number; event_type: string; severity: string; message: string }>>;
  exportSecurityReport(): Promise<any>;
  exportAuditLog(format?: 'json' | 'csv'): Promise<any>;

  // Batch Estimate
  getBatchEstimate(): Promise<any>;

  // License validation (LS-2)
  validateLicense(): Promise<any>;
  getSeatStatus(): Promise<any>;
  provisionSeat(email: string): Promise<any>;

  // Scope Orchestrator (Phase 24 SM-8)
  getScopeStatus(projectId: string): Promise<any>;
  addScopeFiles(projectId: string, paths: string[]): Promise<any>;
  removeScopeFiles(projectId: string, paths: string[]): Promise<any>;
  triggerScopeRebuild(projectId: string): Promise<any>;

  // AutoAudit (Phase 43)
  triggerAudit(projectId: string, opts?: { synthesize?: boolean; categories?: string[] }): Promise<{ status: string; synthesize: boolean }>;
  getAuditStatus(projectId: string): Promise<import('../types').AuditStatus>;
  getAuditFindings(projectId: string, opts?: { severity?: string; category?: string; limit?: number }): Promise<{ finding_count: number; total_finding_count: number; severity_counts: Record<string, number>; findings: import('../types').AuditFinding[] }>;
  getAuditReports(projectId: string): Promise<{ reports: import('../types').AuditReport[] }>;
  getAuditReport(projectId: string, reportName: string): Promise<{ name: string; content: string; size_bytes: number }>;

  // Spaghetti Finder (Phase 52)
  getSpaghettiScores(projectId: string, opts?: { tab?: string; limit?: number; refresh?: boolean }): Promise<import('../types').SpaghettiResult>;

  // Token Telemetry (Phase 56)
  getTokenUsage(projectId: string, since?: number): Promise<{ usage: Record<string, { prompt_tokens: number; completion_tokens: number; total_tokens: number }> }>;

  // Goalposts (Phase 57)
  getGoalposts(projectId: string): Promise<import('../types').GoalpostsResponse>;
  triggerGoalpostsGenerate(projectId: string): Promise<{ status: string; message: string }>;
  updateGoalpostsIntent(projectId: string, intent: string): Promise<{ product_intent: string }>;
  updateGoalpostProposal(projectId: string, proposalId: string, state: 'approved' | 'dismissed'): Promise<{ id: string; state: string }>;
  answerGoalpostQuestion(projectId: string, questionId: string, answer: string): Promise<{ id: string; answered: boolean }>;

  // Roadmap (Phase 59)
  getRoadmap(projectId: string): Promise<import('../types').RoadmapResponse>;
  createRoadmapNode(projectId: string, node: { title: string; description?: string; tier?: string; category?: string; priority?: string }): Promise<{ id: string; tier: string; position: number }>;
  updateRoadmapNode(projectId: string, nodeId: string, updates: Partial<import('../types').RoadmapNode>): Promise<{ id: string; tier: string; state: string }>;
  deleteRoadmapNode(projectId: string, nodeId: string): Promise<{ deleted: string }>;
  generateRoadmapProposals(projectId: string): Promise<{ status: string; message: string }>;
  updateRoadmapEthos(projectId: string, ethos: string): Promise<{ app_ethos: string }>;
  reorderRoadmapNodes(projectId: string, tier: string, nodeIds: string[]): Promise<{ tier: string; count: number }>;
  scanRoadmapTodos(projectId: string): Promise<{ status: string; message: string }>;
  answerRoadmapQuestion(projectId: string, questionId: string, answer: string): Promise<{ id: string; answered: boolean }>;

  // Roadmap GitHub + Mining (Phase 59D)
  syncGitHub(projectId: string): Promise<{ status: string; message: string }>;
  getGitHubStatus(projectId: string): Promise<import('../types').GitHubStatus>;
  mineRoadmap(projectId: string): Promise<{ status: string; message: string }>;

  // Roadmap Webhook + Push + Sprint (Phase 59D-2/3/4)
  pushToGitHub(projectId: string, nodeIds: string[]): Promise<import('../types').PushGitHubResult>;
  getVelocity(projectId: string): Promise<import('../types').VelocityResponse>;
  suggestSprint(projectId: string): Promise<import('../types').SprintSuggestion>;

  // Roadmap Node Execution (Phase 59E)
  executeNode(projectId: string, nodeId: string): Promise<{ node_id: string; guidance: string; tokens_used: number; model: string }>;

  // Opportunities (Phase 63)
  getOpportunities(projectId: string, opts?: { category?: string; min_priority?: string; source?: string; include_dismissed?: boolean; limit?: number }): Promise<{ item_count: number; items: any[] }>;
  refreshOpportunities(projectId: string): Promise<{ item_count: number; summary: any; items: any[] }>;
  getOpportunitiesSummary(projectId: string): Promise<{ total: number; dismissed: number; critical: number; warning: number; info: number; last_refresh: string | null; by_priority: Record<string, number>; by_category: Record<string, number>; by_source: Record<string, number> }>;
  dismissOpportunity(projectId: string, itemId: string): Promise<{ dismissed: string }>;
  restoreOpportunity(projectId: string, itemId: string): Promise<{ restored: string }>;
  exportOpportunities(projectId: string, format: string, opts?: { category?: string; min_priority?: string; source?: string }): Promise<string>;

  // Agent Operations (Phase 67)
  getAgentsStatus(projectId: string): Promise<{ hr: { role_count: number; roles: string[] }; researcher: { run_count: number; latest_run: string | null }; custodian: { archive_count: number } }>;
  getHRReadiness(projectId: string): Promise<{ score: number; ready_for_list: boolean; ready_for_auto: boolean; dimensions: Record<string, number>; missing: string[] }>;
  getHRRoster(projectId: string): Promise<{ roles: Array<{ slug: string; display_name: string; has_agents_md: boolean; has_soul_md: boolean; has_knowledge_md: boolean }> }>;
  generateHRRoles(projectId: string, mode: string, roleNames: string[]): Promise<{ roles_generated: number; slugs: string[] }>;
  auditHRRoles(projectId: string): Promise<{ role_fitness: Array<{ slug: string; display_name: string; fitness_score: number; recommendation: string }>; coverage_gaps: string[] }>;
  runResearcher(projectId: string, maxTopics: number): Promise<{ plans: any[]; count: number }>;
  getResearchHistory(projectId: string): Promise<{ runs: Array<{ run_id: string; timestamp: string; topic_count: number; plan_count: number }> }>;
  runCustodian(projectId: string, dryRun: boolean, maxFiles: number): Promise<{ dry_run: boolean; branch_name: string; candidate_count: number; candidates: any[] }>;
  getCustodianManifest(projectId: string): Promise<{ entries: any[] }>;
}

export interface ApiClientConfig {
  baseUrl?: string;
  apiKey?: string;
  fetchImpl?: typeof fetch;
}

export class CodragApiClient implements ApiClient {
  public readonly baseUrl: string;
  private readonly apiKey?: string;
  private readonly fetchImpl: typeof fetch;

  constructor(config?: ApiClientConfig) {
    this.baseUrl = config?.baseUrl ?? 'http://127.0.0.1:8400';
    this.apiKey = config?.apiKey;
    this.fetchImpl = config?.fetchImpl ?? fetch.bind(globalThis);
  }

  // ── Health ──────────────────────────────────────────────────

  async getHealth(): Promise<{ status: string; version: string }> {
    // /health returns raw JSON, not an envelope
    const res = await this.fetchImpl(new URL('/health', this.baseUrl).toString(), {
      headers: { Accept: 'application/json' },
    });
    if (!res.ok) throw new ApiClientError(`Health check failed: HTTP ${res.status}`);
    return res.json();
  }

  // ── Projects CRUD ──────────────────────────────────────────

  async listProjects(): Promise<ListProjectsResponse> {
    return this.requestEnvelope<ListProjectsResponse>('/projects');
  }

  async createProject(request: CreateProjectRequest): Promise<CreateProjectResponse> {
    return this.requestEnvelope<CreateProjectResponse>('/projects', {
      method: 'POST',
      body: request,
    });
  }

  async getProject(projectId: string): Promise<{ project: Project }> {
    return this.requestEnvelope<{ project: Project }>(`/projects/${encodeURIComponent(projectId)}`);
  }

  async updateProject(projectId: string, request: UpdateProjectRequest): Promise<UpdateProjectResponse> {
    return this.requestEnvelope<UpdateProjectResponse>(`/projects/${encodeURIComponent(projectId)}`, {
      method: 'PUT',
      body: request,
    });
  }

  async deleteProject(projectId: string, purge = false): Promise<DeleteProjectResponse> {
    return this.requestEnvelope<DeleteProjectResponse>(`/projects/${encodeURIComponent(projectId)}`, {
      method: 'DELETE',
      query: { purge },
    });
  }

  // ── Status & Build ─────────────────────────────────────────

  async getProjectStatus(projectId: string): Promise<ProjectStatus> {
    return this.requestEnvelope<ProjectStatus>(`/projects/${encodeURIComponent(projectId)}/status`);
  }

  async buildProject(projectId: string, full = false, includedPaths?: string[]): Promise<BuildProjectResponse> {
    return this.requestEnvelope<BuildProjectResponse>(`/projects/${encodeURIComponent(projectId)}/build`, {
      method: 'POST',
      query: { full },
      body: includedPaths?.length ? { included_paths: includedPaths } : undefined,
    });
  }

  // ── Search & Context ───────────────────────────────────────

  async search(projectId: string, request: SearchRequest): Promise<SearchResponse> {
    return this.requestEnvelope<SearchResponse>(`/projects/${encodeURIComponent(projectId)}/search`, {
      method: 'POST',
      body: request,
    });
  }

  async assembleContext(projectId: string, request: AssembleContextRequest): Promise<AssembleContextResponse> {
    return this.requestEnvelope<AssembleContextResponse>(`/projects/${encodeURIComponent(projectId)}/context`, {
      method: 'POST',
      body: request,
    });
  }

  // ── Trace ──────────────────────────────────────────────────

  async getTraceStatus(projectId: string): Promise<TraceStatus> {
    return this.requestEnvelope<TraceStatus>(`/projects/${encodeURIComponent(projectId)}/trace/status`);
  }

  async searchTrace(projectId: string, query: string, kinds?: string[], limit: number = 20): Promise<{ nodes: any[] }> {
    return this.requestEnvelope<{ nodes: any[] }>(`/projects/${encodeURIComponent(projectId)}/trace/search`, {
      method: 'POST',
      body: { query, kinds, limit },
    });
  }

  async getTraceNode(projectId: string, nodeId: string): Promise<{ node: any; in_degree: number; out_degree: number }> {
    return this.requestEnvelope<{ node: any; in_degree: number; out_degree: number }>(
      `/projects/${encodeURIComponent(projectId)}/trace/nodes/${encodeURI(nodeId)}`
    );
  }

  async getTraceNeighbors(projectId: string, nodeId: string, direction: string = 'both'): Promise<{ nodes: any[]; edges: any[] }> {
    return this.requestEnvelope<{ nodes: any[]; edges: any[] }>(
      `/projects/${encodeURIComponent(projectId)}/trace/neighbors/${encodeURI(nodeId)}`,
      { query: { direction } }
    );
  }

  async buildTrace(projectId: string): Promise<{ started: boolean }> {
    return this.requestEnvelope<{ started: boolean }>(`/projects/${encodeURIComponent(projectId)}/trace/build`, {
      method: 'POST',
    });
  }

  async getTraceCoverage(projectId: string): Promise<TraceCoverage> {
    return this.requestEnvelope<TraceCoverage>(`/projects/${encodeURIComponent(projectId)}/trace/coverage`);
  }

  async updateTraceIgnore(projectId: string, action: 'add' | 'remove', patterns: string[]): Promise<{ ignore_patterns: string[] }> {
    return this.requestEnvelope<{ ignore_patterns: string[] }>(`/projects/${encodeURIComponent(projectId)}/trace/ignore`, {
      method: 'POST',
      body: { action, patterns },
    });
  }

  // ── Roots ──────────────────────────────────────────────────

  async getProjectRoots(projectId: string): Promise<{ roots: string[] }> {
    return this.requestEnvelope<{ roots: string[] }>(`/projects/${encodeURIComponent(projectId)}/roots`);
  }

  async getProjectFiles(projectId: string, path: string = '', depth: number = 3): Promise<{ path: string; tree: FileTreeNode[] }> {
    const params = new URLSearchParams();
    if (path) params.set('path', path);
    if (depth !== 3) params.set('depth', String(depth));
    const qs = params.toString();
    return this.requestEnvelope<{ path: string; tree: FileTreeNode[] }>(
      `/projects/${encodeURIComponent(projectId)}/files${qs ? `?${qs}` : ''}`
    );
  }

  async getProjectFileContent(projectId: string, path: string): Promise<{ content: string; path: string; size: number }> {
    const data = await this.requestEnvelope<{ file: { content: string; path: string; bytes: number } }>(
      `/projects/${encodeURIComponent(projectId)}/file?path=${encodeURIComponent(path)}`
    );
    return { content: data.file.content, path: data.file.path, size: data.file.bytes };
  }

  async detectStack(projectId: string): Promise<{ recommended_globs: string[]; detected_presets: string[]; all_presets: Record<string, string[]> }> {
    return this.requestEnvelope<{ recommended_globs: string[]; detected_presets: string[]; all_presets: Record<string, string[]> }>(
      `/projects/${encodeURIComponent(projectId)}/detect-stack`
    );
  }

  // ── Watch ──────────────────────────────────────────────────

  async startWatch(projectId: string): Promise<WatchActionResponse> {
    return this.requestEnvelope<WatchActionResponse>(`/projects/${encodeURIComponent(projectId)}/watch/start`, {
      method: 'POST',
    });
  }

  async stopWatch(projectId: string): Promise<WatchActionResponse> {
    return this.requestEnvelope<WatchActionResponse>(`/projects/${encodeURIComponent(projectId)}/watch/stop`, {
      method: 'POST',
    });
  }

  async getWatchStatus(projectId: string): Promise<WatchStatus> {
    return this.requestEnvelope<WatchStatus>(`/projects/${encodeURIComponent(projectId)}/watch/status`);
  }

  // ── Path Weights ──────────────────────────────────────────

  async getPathWeights(projectId: string): Promise<{ path_weights: Record<string, number> }> {
    return this.requestEnvelope<{ path_weights: Record<string, number> }>(
      `/projects/${encodeURIComponent(projectId)}/path_weights`
    );
  }

  async updatePathWeights(projectId: string, pathWeights: Record<string, number>): Promise<{ path_weights: Record<string, number> }> {
    return this.requestEnvelope<{ path_weights: Record<string, number> }>(
      `/projects/${encodeURIComponent(projectId)}/path_weights`,
      { method: 'PUT', body: { path_weights: pathWeights } }
    );
  }

  // ── Included Paths (Knowledge Scope) ──────────────────────

  async getIncludedPaths(projectId: string): Promise<{ included_paths: string[] }> {
    return this.requestEnvelope<{ included_paths: string[] }>(
      `/projects/${encodeURIComponent(projectId)}/included_paths`
    );
  }

  async updateIncludedPaths(projectId: string, includedPaths: string[]): Promise<{ included_paths: string[] }> {
    return this.requestEnvelope<{ included_paths: string[] }>(
      `/projects/${encodeURIComponent(projectId)}/included_paths`,
      { method: 'PUT', body: { included_paths: includedPaths } }
    );
  }

  // ── LLM ────────────────────────────────────────────────────

  async getSeatStatus(): Promise<any> {
    return this.requestEnvelope<any>('/license/seats');
  }

  async provisionSeat(email: string): Promise<any> {
    return this.requestEnvelope<any>('/license/provision-seat', {
      method: 'POST',
      body: { email },
    });
  }

  async getLLMStatus(): Promise<LLMStatus> {
    return this.requestEnvelope<LLMStatus>('/llm/status');
  }

  // ── License ────────────────────────────────────────────────

  async getLicense(): Promise<LicenseStatus> {
    return this.requestEnvelope<LicenseStatus>('/license');
  }

  async activateLicense(key: string): Promise<LicenseStatus> {
    return this.requestEnvelope<LicenseStatus>('/license/activate', {
      method: 'POST',
      body: { key },
    });
  }

  async deactivateLicense(): Promise<LicenseStatus> {
    return this.requestEnvelope<LicenseStatus>('/license/deactivate', {
      method: 'POST',
      body: {},
    });
  }

  async setDevTierOverride(tier: string | null): Promise<LicenseStatus> {
    return this.requestEnvelope<LicenseStatus>('/license/dev-override', {
      method: 'POST',
      body: { tier: tier || '' },
    });
  }

  // ── Embedding ────────────────────────────────────────────

  async getEmbeddingStatus(): Promise<{ available: boolean; model: string; dim: number; downloaded: boolean }> {
    return this.requestEnvelope<{ available: boolean; model: string; dim: number; downloaded: boolean }>('/embedding/status');
  }

  async downloadEmbedding(): Promise<{ status: string }> {
    return this.requestEnvelope<{ status: string }>('/embedding/download', { method: 'POST' });
  }

  // ── Compression ───────────────────────────────────────────

  async getCompressionStatus(): Promise<{ lingua: any; lod: any }> {
    return this.requestEnvelope<{ lingua: any; lod: any }>('/compression/status');
  }

  async downloadLinguaModel(): Promise<{ status: string; model_path: string; hf_repo_id: string }> {
    return this.requestEnvelope<{ status: string; model_path: string; hf_repo_id: string }>('/compression/download', { method: 'POST' });
  }

  // ── Activity & Coverage ──────────────────────────────────

  async getProjectActivity(projectId: string, weeks = 12): Promise<{ days: any[]; totals: { embeddings: number; trace: number; builds: number } }> {
    return this.requestEnvelope<{ days: any[]; totals: { embeddings: number; trace: number; builds: number } }>(
      `/projects/${encodeURIComponent(projectId)}/activity`,
      { query: { weeks } }
    );
  }

  async getProjectCoverage(projectId: string): Promise<{ tree: any[] }> {
    return this.requestEnvelope<{ tree: any[] }>(`/projects/${encodeURIComponent(projectId)}/coverage`);
  }

  // ── LLM Proxy ─────────────────────────────────────────────

  async testLLMConnectivity(): Promise<{ ollama: { connected: boolean } }> {
    return this.requestEnvelope<{ ollama: { connected: boolean } }>('/llm/test', {
      method: 'POST',
    });
  }

  async testLLMEndpoint(provider: string, url: string, apiKey?: string): Promise<{ success: boolean; models?: string[] }> {
    return this.requestEnvelope<{ success: boolean; models?: string[] }>('/api/llm/proxy/test', {
      method: 'POST',
      body: { provider, url, api_key: apiKey },
    });
  }

  async fetchLLMModels(provider: string, url: string, apiKey?: string): Promise<{ models: string[] }> {
    return this.requestEnvelope<{ models: string[] }>('/api/llm/proxy/models', {
      method: 'POST',
      body: { provider, url, api_key: apiKey },
    });
  }

  async testLLMModel(provider: string, url: string, model: string, kind: string, apiKey?: string, slot?: string): Promise<{ success: boolean; message: string; model_status?: ModelReadinessStatus; warnings?: string[]; recommendations?: Record<string, any> }> {
    return this.requestEnvelope<{ success: boolean; message: string; model_status?: ModelReadinessStatus; warnings?: string[]; recommendations?: Record<string, any> }>('/api/llm/proxy/test-model', {
      method: 'POST',
      body: { provider, url, api_key: apiKey, model, kind, slot },
    });
  }

  async getModelStatus(provider: string, url: string, model: string, ensureReady = false, apiKey?: string): Promise<ModelStatusResult> {
    return this.requestEnvelope<ModelStatusResult>('/api/llm/model-status', {
      method: 'POST',
      body: { provider, url, model, api_key: apiKey, ensure_ready: ensureReady },
    });
  }

  // ── Global Config ──────────────────────────────────────────

  async getGlobalConfig(): Promise<GlobalConfig> {
    return this.requestEnvelope<GlobalConfig>('/global/config');
  }

  async updateGlobalConfig(config: GlobalConfig): Promise<GlobalConfig> {
    return this.requestEnvelope<GlobalConfig>('/global/config', {
      method: 'PUT',
      body: config,
    });
  }

  private async requestEnvelope<T>(
    path: string,
    opts?: { method?: string; query?: Record<string, string | number | boolean | undefined>; body?: unknown; timeoutMs?: number; signal?: AbortSignal }
  ): Promise<T> {
    const baseUrl = this.baseUrl.endsWith('/') ? this.baseUrl : `${this.baseUrl}/`;
    const relativePath = path.startsWith('/') ? path.slice(1) : path;
    const url = new URL(relativePath, baseUrl);

    if (opts?.query) {
      for (const [k, v] of Object.entries(opts.query)) {
        if (v === undefined) continue;
        url.searchParams.set(k, String(v));
      }
    }

    const headers: Record<string, string> = {
      Accept: 'application/json',
      'Cache-Control': 'no-store, no-cache, must-revalidate',
      'Pragma': 'no-cache',
    };

    if (opts?.body !== undefined) {
      headers['Content-Type'] = 'application/json';
    }

    if (this.apiKey) {
      headers.Authorization = `Bearer ${this.apiKey}`;
    }

    console.log(`[ApiClient] Requesting: ${url.toString()}`, {
      method: opts?.method ?? 'GET',
      headers,
      body: opts?.body
    });

    // Request timeout: abort if daemon doesn't respond within the limit.
    // Uses AbortSignal.any() to combine caller-provided signal with timeout.
    const timeoutMs = opts?.timeoutMs ?? 10_000
    const timeoutController = new AbortController()
    const timeoutId = setTimeout(() => timeoutController.abort(), timeoutMs)
    const signals = [timeoutController.signal]
    if (opts?.signal) signals.push(opts.signal)
    // AbortSignal.any() is available in all modern browsers and Node 20+
    const combinedSignal = typeof AbortSignal.any === 'function'
      ? AbortSignal.any(signals)
      : timeoutController.signal

    let res: Response;
    try {
      res = await this.fetchImpl(url.toString(), {
        method: opts?.method ?? 'GET',
        headers,
        body: opts?.body !== undefined ? JSON.stringify(opts.body) : undefined,
        signal: combinedSignal,
      });
    } catch (err) {
      clearTimeout(timeoutId)
      if (timeoutController.signal.aborted) {
        throw new ApiClientError(`Request timed out after ${timeoutMs}ms`, { url: url.toString() });
      }
      if (opts?.signal?.aborted) {
        throw new ApiClientError('Request aborted', { url: url.toString() });
      }
      console.error('[ApiClient] Network Error Details:', {
        url: url.toString(),
        error: err,
        message: err instanceof Error ? err.message : String(err),
        stack: err instanceof Error ? err.stack : undefined
      });
      throw new ApiClientError('Network error contacting CoDRAG daemon', { url: url.toString() });
    }
    clearTimeout(timeoutId)

    let json: unknown;
    try {
      json = await res.json();
    } catch {
      console.error(`[ApiClient] Invalid JSON from ${url.toString()}:`, res.status);
      throw new ApiClientError('Invalid JSON response from CoDRAG daemon', {
        status: res.status,
        url: url.toString(),
      });
    }

    console.log(`[ApiClient] Response from ${url.toString()}:`, json);

    const envelope = json as ApiEnvelope<T>;
    if (typeof envelope !== 'object' || envelope === null || typeof envelope.success !== 'boolean') {
      throw new ApiClientError(`Unexpected response shape from CoDRAG daemon: ${url.pathname} (HTTP ${res.status})`, {
        status: res.status,
        url: url.toString(),
      });
    }

    if (!envelope.success) {
      const message = envelope.error?.message ?? 'Request failed';
      throw new ApiClientError(message, {
        status: res.status,
        code: envelope.error?.code,
        apiError: envelope.error ?? undefined,
        url: url.toString(),
      });
    }

    if (envelope.data === null || envelope.data === undefined) {
      throw new ApiClientError('Envelope success=true but data was null', {
        status: res.status,
        url: url.toString(),
      });
    }

    return envelope.data;
  }

  // ── LLM Slot Connectivity ─────────────────────────────────

  async getLLMSlotsStatus(): Promise<LLMSlotsStatus> {
    return this.requestEnvelope<LLMSlotsStatus>('/llm/slots/status');
  }

  async switchAssignmentMode(mode: AssignmentMode, blocks?: LLMAssignmentBlock[]): Promise<{ success: boolean; old_mode: string; new_mode: string; unloaded_models: string[]; kept_models: string[] }> {
    return this.requestEnvelope('/api/llm/mode-switch', {
      method: 'POST',
      body: { mode, assignment_blocks: blocks ?? null },
    });
  }

  // ── Augmentation & Deep Analysis ──────────────────────────

  async getAugmentStatus(projectId: string): Promise<AugmentationStatus> {
    return this.requestEnvelope<AugmentationStatus>(`/projects/${projectId}/augment/status`);
  }

  async runAugmentation(projectId: string, maxItems?: number): Promise<{ started: boolean; task_id: string }> {
    return this.requestEnvelope<{ started: boolean; task_id: string }>(`/projects/${projectId}/augment/run`, {
      method: 'POST',
      body: maxItems != null ? { max_items: maxItems } : {},
    });
  }

  async getDeepAnalysisStatus(projectId: string): Promise<DeepAnalysisRunStatus> {
    return this.requestEnvelope<DeepAnalysisRunStatus>(`/projects/${projectId}/deep-analysis/status`);
  }

  async runDeepAnalysis(projectId: string, opts?: { max_items?: number; max_tokens?: number; max_minutes?: number }): Promise<{ started: boolean; task_id: string }> {
    return this.requestEnvelope<{ started: boolean; task_id: string }>(`/projects/${projectId}/deep-analysis/run`, {
      method: 'POST',
      body: opts ?? {},
    });
  }

  async cancelDeepAnalysis(projectId: string): Promise<{ cancelled: boolean }> {
    return this.requestEnvelope<{ cancelled: boolean }>(`/projects/${projectId}/deep-analysis/cancel`, {
      method: 'POST',
      body: {},
    });
  }

  // ── Graph Destruction ─────────────────────────────────────

  async destroyGraph(projectId: string): Promise<{ deleted: string[]; errors: string[] }> {
    return this.requestEnvelope<{ deleted: string[]; errors: string[] }>(`/projects/${projectId}/trace/destroy`, {
      method: 'DELETE',
    });
  }

  async destroyIndex(projectId: string): Promise<{ deleted: string[]; errors: string[] }> {
    return this.requestEnvelope<{ deleted: string[]; errors: string[] }>(`/projects/${projectId}/index/destroy`, {
      method: 'DELETE',
    });
  }

  async destroyAtlas(projectId: string): Promise<{ deleted: string[]; errors: string[] }> {
    return this.requestEnvelope<{ deleted: string[]; errors: string[] }>(`/projects/${projectId}/atlas/destroy`, {
      method: 'DELETE',
    });
  }

  async destroyGroupReasoning(projectId: string): Promise<{ deleted: string[]; errors: string[] }> {
    return this.requestEnvelope<{ deleted: string[]; errors: string[] }>(`/projects/${projectId}/group-reasoning/destroy`, {
      method: 'DELETE',
    });
  }

  async destroyDeepEnrichment(projectId: string): Promise<{ deleted: string[]; errors: string[] }> {
    return this.requestEnvelope<{ deleted: string[]; errors: string[] }>(`/projects/${projectId}/deep-enrichment/destroy`, {
      method: 'DELETE',
    });
  }

  // ── Epistemic Enrichment ────────────────────────────────────

  async getEpistemicStatus(projectId: string): Promise<EpistemicStatus> {
    return this.requestEnvelope<EpistemicStatus>(`/projects/${projectId}/epistemic/status`);
  }

  async runEpistemic(projectId: string, maxItems?: number): Promise<{ started: boolean; task_id: string }> {
    return this.requestEnvelope<{ started: boolean; task_id: string }>(`/projects/${projectId}/epistemic/run`, {
      method: 'POST',
      body: maxItems != null ? { max_items: maxItems } : {},
    });
  }

  // ── Module Synthesis ────────────────────────────────────────

  async getModuleStatus(projectId: string): Promise<ModuleStatus> {
    return this.requestEnvelope<ModuleStatus>(`/projects/${projectId}/modules/status`);
  }

  async runModuleSynthesis(projectId: string): Promise<{ started: boolean; task_id: string }> {
    return this.requestEnvelope<{ started: boolean; task_id: string }>(`/projects/${projectId}/modules/run`, {
      method: 'POST',
      body: {},
    });
  }

  // ── Deepening Loop ─────────────────────────────────────────

  async getDeepeningStatus(projectId: string): Promise<DeepeningStatus> {
    return this.requestEnvelope<DeepeningStatus>(`/projects/${projectId}/deepening/status`);
  }

  async runDeepening(projectId: string, opts?: { max_iterations?: number; batch_size?: number }): Promise<{ started: boolean; task_id: string }> {
    return this.requestEnvelope<{ started: boolean; task_id: string }>(`/projects/${projectId}/deepening/run`, {
      method: 'POST',
      body: opts ?? {},
    });
  }

  // ── Knowledge Embedding ─────────────────────────────────────

  async getKnowledgeStatus(projectId: string): Promise<KnowledgeEmbeddingStatus> {
    return this.requestEnvelope<KnowledgeEmbeddingStatus>(`/projects/${projectId}/knowledge/status`);
  }

  async runKnowledgeBuild(projectId: string): Promise<{ started: boolean; building: boolean }> {
    return this.requestEnvelope<{ started: boolean; building: boolean }>(`/projects/${projectId}/knowledge/build`, {
      method: 'POST',
    });
  }

  // ── Unified Graph Engine ────────────────────────────────────

  async getGraphEngineStatus(projectId: string): Promise<GraphEngineStatus> {
    return this.requestEnvelope<GraphEngineStatus>(`/projects/${projectId}/engine/status`);
  }

  // ── Pipeline Orchestrator (Phase 24 SM-6) ───────────────────

  async runPipelineFast(projectId: string): Promise<{ started: boolean; group: string }> {
    return this.requestEnvelope<{ started: boolean; group: string }>(`/projects/${projectId}/pipeline/fast`, {
      method: 'POST',
    });
  }

  async runPipelineDeep(projectId: string): Promise<{ started: boolean; group: string }> {
    return this.requestEnvelope<{ started: boolean; group: string }>(`/projects/${projectId}/pipeline/deep`, {
      method: 'POST',
    });
  }

  async runPipelineAll(projectId: string): Promise<{ started: boolean; group: string }> {
    return this.requestEnvelope<{ started: boolean; group: string }>(`/projects/${projectId}/pipeline/all`, {
      method: 'POST',
    });
  }

  async getPipelineStatus(projectId: string): Promise<PipelineStatus> {
    return this.requestEnvelope<PipelineStatus>(`/projects/${projectId}/pipeline/status`);
  }

  async cancelPipeline(projectId: string, group: string): Promise<{ cancelled: boolean; group: string }> {
    return this.requestEnvelope<{ cancelled: boolean; group: string }>(`/projects/${projectId}/pipeline/cancel`, {
      method: 'POST',
      body: { group },
    });
  }

  async pausePipeline(projectId: string, group: string): Promise<{ paused: boolean; group: string }> {
    return this.requestEnvelope<{ paused: boolean; group: string }>(`/projects/${projectId}/pipeline/pause`, {
      method: 'POST',
      body: { group },
    });
  }

  async resumePipeline(projectId: string, group: string): Promise<{ resumed: boolean; group: string }> {
    return this.requestEnvelope<{ resumed: boolean; group: string }>(`/projects/${projectId}/pipeline/resume`, {
      method: 'POST',
      body: { group },
    });
  }

  async swapPipelineModel(projectId: string, group: string): Promise<{ swapped: boolean; paused_at_stage: string; resumed: boolean }> {
    return this.requestEnvelope<{ swapped: boolean; paused_at_stage: string; resumed: boolean }>(`/projects/${projectId}/pipeline/swap-model`, {
      method: 'POST',
      body: { group },
    });
  }

  async getPipelineBudget(projectId: string): Promise<{ tokens_used: number; max_tokens: number; window_minutes: number; remaining: number; window_resets_in: number }> {
    return this.requestEnvelope<{ tokens_used: number; max_tokens: number; window_minutes: number; remaining: number; window_resets_in: number }>(`/projects/${projectId}/pipeline/budget`);
  }

  async getTokenUsage(projectId: string, since?: number): Promise<{ usage: Record<string, { prompt_tokens: number; completion_tokens: number; total_tokens: number }> }> {
    return this.requestEnvelope<{ usage: Record<string, { prompt_tokens: number; completion_tokens: number; total_tokens: number }> }>(
      `/projects/${projectId}/token-usage`,
      { query: since !== undefined ? { since } : undefined }
    );
  }

  // ── Pipeline Crash Protection (Phase 25) ───────────────────────

  async getCrashedRuns(projectId?: string): Promise<{ crashed_runs: CrashedPipelineRun[]; count: number }> {
    const query = projectId ? `?project_id=${projectId}` : '';
    return this.requestEnvelope<{ crashed_runs: CrashedPipelineRun[]; count: number }>(`/pipeline/crashed${query}`);
  }

  async resumeCrashedRun(runId: string): Promise<{ resumed: boolean; run_id: string }> {
    return this.requestEnvelope<{ resumed: boolean; run_id: string }>('/pipeline/resume', {
      method: 'POST',
      body: { run_id: runId },
    });
  }

  async discardCrashedRun(runId: string): Promise<{ discarded: boolean; run_id: string }> {
    return this.requestEnvelope<{ discarded: boolean; run_id: string }>('/pipeline/discard', {
      method: 'POST',
      body: { run_id: runId },
    });
  }

  // ── Pipeline Provenance (Phase 49) ─────────────────────────────

  async getPipelineProvenance(projectId: string): Promise<import('../types').PipelineProvenance> {
    return this.requestEnvelope<import('../types').PipelineProvenance>(`/projects/${encodeURIComponent(projectId)}/pipeline/provenance`);
  }

  // ── Codebase Atlas (Phase 29) ──────────────────────────────────

  async getAtlas(projectId: string): Promise<import('../types').AtlasStatus> {
    return this.requestEnvelope<import('../types').AtlasStatus>(`/projects/${encodeURIComponent(projectId)}/atlas`);
  }

  async regenerateAtlas(projectId: string): Promise<import('../types').AtlasStatus> {
    return this.requestEnvelope<import('../types').AtlasStatus>(`/projects/${encodeURIComponent(projectId)}/atlas/regenerate`, {
      method: 'POST',
    });
  }

  // ── Settings Store (Phase 24) ─────────────────────────────────

  async getSettings(): Promise<Record<string, any>> {
    return this.requestEnvelope<Record<string, any>>('/settings');
  }

  async getSetting(key: string): Promise<{ key: string; value: any }> {
    return this.requestEnvelope<{ key: string; value: any }>(`/settings/${key}`);
  }

  async setSetting(key: string, value: any): Promise<{ key: string; value: any }> {
    return this.requestEnvelope<{ key: string; value: any }>(`/settings/${key}`, {
      method: 'PUT',
      body: { value },
    });
  }

  async deleteSetting(key: string): Promise<{ key: string; deleted: boolean }> {
    return this.requestEnvelope<{ key: string; deleted: boolean }>(`/settings/${key}`, {
      method: 'DELETE',
    });
  }

  async getPipelineConfig(): Promise<any> {
    return this.requestEnvelope<any>('/settings/pipeline-config');
  }

  async updatePipelineConfig(config: {
    fast_sync_auto?: boolean;
    deep_enrichment_mode?: string;
    schedule_frequency?: string;
    schedule_day_of_week?: number;
    schedule_hour?: number;
    schedule_threshold_enabled?: boolean;
    schedule_time_enabled?: boolean;
    threshold_percent?: number;
    budget_max_tokens?: number;
    budget_max_minutes?: number;
    budget_max_items?: number;
    llm_concurrency?: number;
    llm_concurrency_fast?: number;
    llm_concurrency_code?: number;
    llm_concurrency_deep?: number;
  }): Promise<any> {
    return this.requestEnvelope<any>('/settings/pipeline-config', {
      method: 'POST',
      body: config,
    });
  }

  async getProjectSettings(projectId: string): Promise<Record<string, any>> {
    return this.requestEnvelope<Record<string, any>>(`/projects/${projectId}/settings`);
  }

  async setProjectSetting(projectId: string, key: string, value: any): Promise<{ key: string; value: any }> {
    return this.requestEnvelope<{ key: string; value: any }>(`/projects/${projectId}/settings/${key}`, {
      method: 'PUT',
      body: { value },
    });
  }

  // ── Advanced Config ────────────────────────────────────────────

  async getAdvancedConfig(): Promise<import('../types').AdvancedConfig> {
    return this.requestEnvelope<import('../types').AdvancedConfig>('/settings/advanced-config');
  }

  async updateAdvancedConfig(config: Partial<import('../types').AdvancedConfig>): Promise<import('../types').AdvancedConfig> {
    return this.requestEnvelope<import('../types').AdvancedConfig>('/settings/advanced-config', {
      method: 'POST',
      body: config,
    });
  }

  // ── Scope Orchestrator (Phase 24 SM-8) ────────────────────────

  async getScopeStatus(projectId: string): Promise<any> {
    return this.requestEnvelope<any>(`/projects/${projectId}/scope/status`);
  }

  async addScopeFiles(projectId: string, paths: string[]): Promise<any> {
    return this.requestEnvelope<any>(`/projects/${projectId}/scope/add`, {
      method: 'POST',
      body: { paths },
    });
  }

  async removeScopeFiles(projectId: string, paths: string[]): Promise<any> {
    return this.requestEnvelope<any>(`/projects/${projectId}/scope/remove`, {
      method: 'POST',
      body: { paths },
    });
  }

  async triggerScopeRebuild(projectId: string): Promise<any> {
    return this.requestEnvelope<any>(`/projects/${projectId}/scope/rebuild`, {
      method: 'POST',
    });
  }

  // AutoAudit (Phase 43)

  async triggerAudit(projectId: string, opts?: { synthesize?: boolean; categories?: string[] }): Promise<{ status: string; synthesize: boolean }> {
    return this.requestEnvelope<{ status: string; synthesize: boolean }>(`/projects/${projectId}/audit`, {
      method: 'POST',
      body: { synthesize: opts?.synthesize ?? false, categories: opts?.categories },
    });
  }

  async getAuditStatus(projectId: string): Promise<import('../types').AuditStatus> {
    return this.requestEnvelope<import('../types').AuditStatus>(`/projects/${projectId}/audit/status`);
  }

  async getAuditFindings(projectId: string, opts?: { severity?: string; category?: string; limit?: number }): Promise<{ finding_count: number; total_finding_count: number; severity_counts: Record<string, number>; findings: import('../types').AuditFinding[] }> {
    const params = new URLSearchParams();
    if (opts?.severity) params.set('severity', opts.severity);
    if (opts?.category) params.set('category', opts.category);
    if (opts?.limit) params.set('limit', String(opts.limit));
    const qs = params.toString();
    return this.requestEnvelope(`/projects/${projectId}/audit/findings${qs ? `?${qs}` : ''}`);
  }

  async getAuditReports(projectId: string): Promise<{ reports: import('../types').AuditReport[] }> {
    return this.requestEnvelope(`/projects/${projectId}/audit/reports`);
  }

  async getAuditReport(projectId: string, reportName: string): Promise<{ name: string; content: string; size_bytes: number }> {
    return this.requestEnvelope(`/projects/${projectId}/audit/report/${encodeURIComponent(reportName)}`);
  }

  // ── Spaghetti Finder (Phase 52) ──────────────────────────────

  async getSpaghettiScores(projectId: string, opts?: { tab?: string; limit?: number; refresh?: boolean }): Promise<import('../types').SpaghettiResult> {
    const params = new URLSearchParams();
    if (opts?.tab) params.set('tab', opts.tab);
    if (opts?.limit) params.set('limit', String(opts.limit));
    if (opts?.refresh) params.set('refresh', 'true');
    const qs = params.toString();
    return this.requestEnvelope(`/projects/${projectId}/audit/spaghetti${qs ? `?${qs}` : ''}`);
  }

  // ── Compute Nodes (Phase 45D) ─────────────────────────────────

  async getComputeNodes(): Promise<{ nodes: import('../types').ComputeNode[]; count: number }> {
    return this.requestEnvelope<{ nodes: import('../types').ComputeNode[]; count: number }>('/compute/nodes');
  }

  async createComputeNode(node: Omit<import('../types').ComputeNode, 'id'>): Promise<import('../types').ComputeNode> {
    return this.requestEnvelope<import('../types').ComputeNode>('/compute/nodes', {
      method: 'POST',
      body: node,
    });
  }

  async updateComputeNode(nodeId: string, updates: Partial<import('../types').ComputeNode>): Promise<import('../types').ComputeNode> {
    return this.requestEnvelope<import('../types').ComputeNode>(`/compute/nodes/${encodeURIComponent(nodeId)}`, {
      method: 'PUT',
      body: updates,
    });
  }

  async deleteComputeNode(nodeId: string): Promise<{ deleted: string }> {
    return this.requestEnvelope<{ deleted: string }>(`/compute/nodes/${encodeURIComponent(nodeId)}`, {
      method: 'DELETE',
    });
  }

  async getComputeNodeStatus(nodeId: string): Promise<import('../types').SchedulerNodeStatus & { node_id: string; name: string }> {
    return this.requestEnvelope(`/compute/nodes/${encodeURIComponent(nodeId)}/status`);
  }

  async getSchedulerStatus(): Promise<import('../types').SchedulerStatus> {
    return this.requestEnvelope<import('../types').SchedulerStatus>('/compute/scheduler');
  }

  async getAdminPolicy(): Promise<import('../types').AdminPolicy> {
    return this.requestEnvelope<import('../types').AdminPolicy>('/settings/admin-policy');
  }

  async getBatchEstimate(): Promise<any> {
    return this.requestEnvelope<any>('/settings/batch-estimate');
  }

  async validateLicense(): Promise<any> {
    return this.requestEnvelope<any>('/license/validate', { method: 'POST' });
  }

  // ── Admin Security (EA-I) ──────────────────────────────────

  async getSecurityHealth(): Promise<import('../components/enterprise/EnterpriseAdminPanel').SecurityHealthResult> {
    return this.requestEnvelope<import('../components/enterprise/EnterpriseAdminPanel').SecurityHealthResult>('/admin/security-health');
  }

  async getSecurityEvents(limit: number = 50): Promise<Array<{ timestamp: number; event_type: string; severity: string; message: string }>> {
    const data = await this.requestEnvelope<{ events: any[]; count: number }>('/admin/audit-log', {
      method: 'POST',
      body: { severity: null, event_type: null, limit },
    });
    return (data.events || []).map((e: any) => ({
      timestamp: e.timestamp,
      event_type: e.event_type,
      severity: e.severity,
      message: e.message || e.event_type,
    }));
  }

  async exportSecurityReport(): Promise<any> {
    return this.requestEnvelope<any>('/admin/security-report');
  }

  async exportAuditLog(format: 'json' | 'csv' = 'json'): Promise<any> {
    return this.requestEnvelope<any>(`/admin/audit-log/export?format=${format}`);
  }

  // ── Goalposts (Phase 57) ──────────────────────────────────────

  async getGoalposts(projectId: string): Promise<import('../types').GoalpostsResponse> {
    return this.requestEnvelope<import('../types').GoalpostsResponse>(`/projects/${projectId}/goalposts`);
  }

  async triggerGoalpostsGenerate(projectId: string): Promise<{ status: string; message: string }> {
    return this.requestEnvelope<{ status: string; message: string }>(`/projects/${projectId}/goalposts/generate`, {
      method: 'POST',
    });
  }

  async updateGoalpostsIntent(projectId: string, intent: string): Promise<{ product_intent: string }> {
    return this.requestEnvelope<{ product_intent: string }>(`/projects/${projectId}/goalposts/intent`, {
      method: 'PUT',
      body: { product_intent: intent },
    });
  }

  async updateGoalpostProposal(projectId: string, proposalId: string, state: 'approved' | 'dismissed'): Promise<{ id: string; state: string }> {
    return this.requestEnvelope<{ id: string; state: string }>(`/projects/${projectId}/goalposts/proposals/${encodeURIComponent(proposalId)}`, {
      method: 'PATCH',
      body: { state },
    });
  }

  async answerGoalpostQuestion(projectId: string, questionId: string, answer: string): Promise<{ id: string; answered: boolean }> {
    return this.requestEnvelope<{ id: string; answered: boolean }>(`/projects/${projectId}/goalposts/questions/${encodeURIComponent(questionId)}/answer`, {
      method: 'POST',
      body: { answer },
    });
  }

  // ── Roadmap (Phase 59) ──────────────────────────────────────────

  async getRoadmap(projectId: string): Promise<import('../types').RoadmapResponse> {
    return this.requestEnvelope<import('../types').RoadmapResponse>(`/projects/${projectId}/roadmap`);
  }

  async createRoadmapNode(projectId: string, node: { title: string; description?: string; tier?: string; category?: string; priority?: string }): Promise<{ id: string; tier: string; position: number }> {
    return this.requestEnvelope<{ id: string; tier: string; position: number }>(`/projects/${projectId}/roadmap/nodes`, {
      method: 'POST',
      body: node,
    });
  }

  async updateRoadmapNode(projectId: string, nodeId: string, updates: Partial<import('../types').RoadmapNode>): Promise<{ id: string; tier: string; state: string }> {
    return this.requestEnvelope<{ id: string; tier: string; state: string }>(`/projects/${projectId}/roadmap/nodes/${encodeURIComponent(nodeId)}`, {
      method: 'PATCH',
      body: updates,
    });
  }

  async deleteRoadmapNode(projectId: string, nodeId: string): Promise<{ deleted: string }> {
    return this.requestEnvelope<{ deleted: string }>(`/projects/${projectId}/roadmap/nodes/${encodeURIComponent(nodeId)}`, {
      method: 'DELETE',
    });
  }

  async generateRoadmapProposals(projectId: string): Promise<{ status: string; message: string }> {
    return this.requestEnvelope<{ status: string; message: string }>(`/projects/${projectId}/roadmap/generate`, {
      method: 'POST',
    });
  }

  async updateRoadmapEthos(projectId: string, ethos: string): Promise<{ app_ethos: string }> {
    return this.requestEnvelope<{ app_ethos: string }>(`/projects/${projectId}/roadmap/ethos`, {
      method: 'PUT',
      body: { app_ethos: ethos },
    });
  }

  async reorderRoadmapNodes(projectId: string, tier: string, nodeIds: string[]): Promise<{ tier: string; count: number }> {
    return this.requestEnvelope<{ tier: string; count: number }>(`/projects/${projectId}/roadmap/reorder`, {
      method: 'POST',
      body: { tier, node_ids: nodeIds },
    });
  }

  async scanRoadmapTodos(projectId: string): Promise<{ status: string; message: string }> {
    return this.requestEnvelope<{ status: string; message: string }>(`/projects/${projectId}/roadmap/scan-todos`, {
      method: 'POST',
    });
  }

  async answerRoadmapQuestion(projectId: string, questionId: string, answer: string): Promise<{ id: string; answered: boolean }> {
    return this.requestEnvelope<{ id: string; answered: boolean }>(`/projects/${projectId}/roadmap/questions/${encodeURIComponent(questionId)}/answer`, {
      method: 'POST',
      body: { answer },
    });
  }

  // ── Roadmap GitHub + Mining (Phase 59D) ────────────────────────

  async syncGitHub(projectId: string): Promise<{ status: string; message: string }> {
    return this.requestEnvelope<{ status: string; message: string }>(`/projects/${projectId}/roadmap/sync-github`, {
      method: 'POST',
    });
  }

  async getGitHubStatus(projectId: string): Promise<import('../types').GitHubStatus> {
    return this.requestEnvelope<import('../types').GitHubStatus>(`/projects/${projectId}/roadmap/github-status`);
  }

  async mineRoadmap(projectId: string): Promise<{ status: string; message: string }> {
    return this.requestEnvelope<{ status: string; message: string }>(`/projects/${projectId}/roadmap/mine`, {
      method: 'POST',
    });
  }

  // ── Roadmap Push + Sprint (Phase 59D-2/3/4) ───────────────────

  async pushToGitHub(projectId: string, nodeIds: string[]): Promise<import('../types').PushGitHubResult> {
    return this.requestEnvelope<import('../types').PushGitHubResult>(`/projects/${projectId}/roadmap/push-github`, {
      method: 'POST',
      body: JSON.stringify({ node_ids: nodeIds }),
    });
  }

  async getVelocity(projectId: string): Promise<import('../types').VelocityResponse> {
    return this.requestEnvelope<import('../types').VelocityResponse>(`/projects/${projectId}/roadmap/velocity`);
  }

  async suggestSprint(projectId: string): Promise<import('../types').SprintSuggestion> {
    return this.requestEnvelope<import('../types').SprintSuggestion>(`/projects/${projectId}/roadmap/suggest-sprint`, {
      method: 'POST',
    });
  }
  async executeNode(projectId: string, nodeId: string): Promise<{ node_id: string; guidance: string; tokens_used: number; model: string }> {
    return this.requestEnvelope<{ node_id: string; guidance: string; tokens_used: number; model: string }>(`/projects/${projectId}/roadmap/nodes/${encodeURIComponent(nodeId)}/execute`, {
      method: 'POST',
    });
  }

  // ── Opportunities (Phase 63) ─────────────────────────────────

  async getOpportunities(projectId: string, opts?: { category?: string; min_priority?: string; source?: string; include_dismissed?: boolean; limit?: number }): Promise<{ item_count: number; items: any[] }> {
    const query: Record<string, string | number | boolean | undefined> = {};
    if (opts?.category) query.category = opts.category;
    if (opts?.min_priority) query.min_priority = opts.min_priority;
    if (opts?.source) query.source = opts.source;
    if (opts?.include_dismissed) query.include_dismissed = true;
    if (opts?.limit) query.limit = opts.limit;
    return this.requestEnvelope<{ item_count: number; items: any[] }>(`/projects/${projectId}/opportunities`, { query });
  }

  async refreshOpportunities(projectId: string): Promise<{ item_count: number; summary: any; items: any[] }> {
    return this.requestEnvelope<{ item_count: number; summary: any; items: any[] }>(`/projects/${projectId}/opportunities/refresh`, {
      method: 'POST',
    });
  }

  async getOpportunitiesSummary(projectId: string): Promise<{ total: number; dismissed: number; critical: number; warning: number; info: number; last_refresh: string | null; by_priority: Record<string, number>; by_category: Record<string, number>; by_source: Record<string, number> }> {
    return this.requestEnvelope(`/projects/${projectId}/opportunities/summary`);
  }

  async dismissOpportunity(projectId: string, itemId: string): Promise<{ dismissed: string }> {
    return this.requestEnvelope<{ dismissed: string }>(`/projects/${projectId}/opportunities/${encodeURIComponent(itemId)}/dismiss`, {
      method: 'POST',
    });
  }

  async restoreOpportunity(projectId: string, itemId: string): Promise<{ restored: string }> {
    return this.requestEnvelope<{ restored: string }>(`/projects/${projectId}/opportunities/${encodeURIComponent(itemId)}/restore`, {
      method: 'POST',
    });
  }

  async exportOpportunities(projectId: string, format: string, opts?: { category?: string; min_priority?: string; source?: string }): Promise<string> {
    const params = new URLSearchParams({ format });
    if (opts?.category) params.set('category', opts.category);
    if (opts?.min_priority) params.set('min_priority', opts.min_priority);
    if (opts?.source) params.set('source', opts.source);
    const res = await this.fetchImpl(`${this.baseUrl}/projects/${projectId}/opportunities/export?${params}`, {
      headers: this.apiKey ? { Authorization: `Bearer ${this.apiKey}` } : {},
    });
    return res.text();
  }

  // ── Agent Operations (Phase 67) ────────────────────────────

  async getAgentsStatus(projectId: string) {
    return this.requestEnvelope<{ hr: { role_count: number; roles: string[] }; researcher: { run_count: number; latest_run: string | null }; custodian: { archive_count: number } }>(`/projects/${projectId}/agents/status`);
  }

  async getHRReadiness(projectId: string) {
    return this.requestEnvelope<{ score: number; ready_for_list: boolean; ready_for_auto: boolean; dimensions: Record<string, number>; missing: string[] }>(`/projects/${projectId}/agents/hr/readiness`);
  }

  async getHRRoster(projectId: string) {
    return this.requestEnvelope<{ roles: Array<{ slug: string; display_name: string; has_agents_md: boolean; has_soul_md: boolean; has_knowledge_md: boolean }> }>(`/projects/${projectId}/agents/hr/roster`);
  }

  async generateHRRoles(projectId: string, mode: string, roleNames: string[]) {
    return this.requestEnvelope<{ roles_generated: number; slugs: string[] }>(`/projects/${projectId}/agents/hr/generate`, {
      method: 'POST',
      body: JSON.stringify({ mode, role_names: roleNames }),
    });
  }

  async auditHRRoles(projectId: string) {
    return this.requestEnvelope<{ role_fitness: Array<{ slug: string; display_name: string; fitness_score: number; recommendation: string }>; coverage_gaps: string[] }>(`/projects/${projectId}/agents/hr/audit`, {
      method: 'POST',
    });
  }

  async runResearcher(projectId: string, maxTopics: number) {
    return this.requestEnvelope<{ plans: any[]; count: number }>(`/projects/${projectId}/agents/researcher/run`, {
      method: 'POST',
      body: JSON.stringify({ max_topics: maxTopics }),
    });
  }

  async getResearchHistory(projectId: string) {
    return this.requestEnvelope<{ runs: Array<{ run_id: string; timestamp: string; topic_count: number; plan_count: number }> }>(`/projects/${projectId}/agents/researcher/history`);
  }

  async runCustodian(projectId: string, dryRun: boolean, maxFiles: number) {
    return this.requestEnvelope<{ dry_run: boolean; branch_name: string; candidate_count: number; candidates: any[] }>(`/projects/${projectId}/agents/custodian/run`, {
      method: 'POST',
      body: JSON.stringify({ dry_run: dryRun, max_files: maxFiles }),
    });
  }

  async getCustodianManifest(projectId: string) {
    return this.requestEnvelope<{ entries: any[] }>(`/projects/${projectId}/agents/custodian/manifest`);
  }
}

export function createCodragApiClient(config?: ApiClientConfig): ApiClient {
  return new CodragApiClient(config);
}
