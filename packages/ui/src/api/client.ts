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
import type { LLMStatus, LicenseStatus, Project, ProjectStatus, TraceCoverage, TraceStatus, WatchStatus, GlobalConfig, ModelStatusResult, ModelReadinessStatus, AugmentationStatus, DeepAnalysisRunStatus, LLMSlotsStatus, EpistemicStatus, ModuleStatus, DeepeningStatus, KnowledgeEmbeddingStatus, GraphEngineStatus, PipelineStatus, CrashedPipelineRun } from '../types';

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
  testLLMModel(provider: string, url: string, model: string, kind: string, apiKey?: string): Promise<{ success: boolean; message: string; model_status?: ModelReadinessStatus }>;
  getModelStatus(provider: string, url: string, model: string, ensureReady?: boolean, apiKey?: string): Promise<ModelStatusResult>;

  // LLM Slot Connectivity
  getLLMSlotsStatus(): Promise<LLMSlotsStatus>;

  // Augmentation & Deep Analysis
  getAugmentStatus(projectId: string): Promise<AugmentationStatus>;
  runAugmentation(projectId: string, maxItems?: number): Promise<{ started: boolean; task_id: string }>;
  getDeepAnalysisStatus(projectId: string): Promise<DeepAnalysisRunStatus>;
  runDeepAnalysis(projectId: string, opts?: { max_items?: number; max_tokens?: number; max_minutes?: number }): Promise<{ started: boolean; task_id: string }>;
  cancelDeepAnalysis(projectId: string): Promise<{ cancelled: boolean }>;

  // Graph & index destruction
  destroyGraph(projectId: string): Promise<{ deleted: string[]; errors: string[] }>;
  destroyIndex(projectId: string): Promise<{ deleted: string[]; errors: string[] }>;

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
  getPipelineBudget(projectId: string): Promise<{ tokens_used: number; max_tokens: number; window_minutes: number; remaining: number; window_resets_in: number }>;

  // Pipeline Crash Protection (Phase 25)
  getCrashedRuns(projectId?: string): Promise<{ crashed_runs: CrashedPipelineRun[]; count: number }>;
  resumeCrashedRun(runId: string): Promise<{ resumed: boolean; run_id: string }>;
  discardCrashedRun(runId: string): Promise<{ discarded: boolean; run_id: string }>;

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
  }): Promise<any>;
  getProjectSettings(projectId: string): Promise<Record<string, any>>;
  setProjectSetting(projectId: string, key: string, value: any): Promise<{ key: string; value: any }>;

  // Advanced Config
  getAdvancedConfig(): Promise<import('../types').AdvancedConfig>;
  updateAdvancedConfig(config: Partial<import('../types').AdvancedConfig>): Promise<import('../types').AdvancedConfig>;

  // Scope Orchestrator (Phase 24 SM-8)
  getScopeStatus(projectId: string): Promise<any>;
  addScopeFiles(projectId: string, paths: string[]): Promise<any>;
  removeScopeFiles(projectId: string, paths: string[]): Promise<any>;
  triggerScopeRebuild(projectId: string): Promise<any>;
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

  async testLLMModel(provider: string, url: string, model: string, kind: string, apiKey?: string): Promise<{ success: boolean; message: string; model_status?: ModelReadinessStatus }> {
    return this.requestEnvelope<{ success: boolean; message: string; model_status?: ModelReadinessStatus }>('/api/llm/proxy/test-model', {
      method: 'POST',
      body: { provider, url, api_key: apiKey, model, kind },
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
    opts?: { method?: string; query?: Record<string, string | number | boolean | undefined>; body?: unknown }
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

    let res: Response;
    try {
      res = await this.fetchImpl(url.toString(), {
        method: opts?.method ?? 'GET',
        headers,
        body: opts?.body !== undefined ? JSON.stringify(opts.body) : undefined,
      });
    } catch (err) {
      console.error('[ApiClient] Network Error Details:', {
        url: url.toString(),
        error: err,
        message: err instanceof Error ? err.message : String(err),
        stack: err instanceof Error ? err.stack : undefined
      });
      throw new ApiClientError('Network error contacting CoDRAG daemon', { url: url.toString() });
    }

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

  async getPipelineBudget(projectId: string): Promise<{ tokens_used: number; max_tokens: number; window_minutes: number; remaining: number; window_resets_in: number }> {
    return this.requestEnvelope<{ tokens_used: number; max_tokens: number; window_minutes: number; remaining: number; window_resets_in: number }>(`/projects/${projectId}/pipeline/budget`);
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
}

export function createCodragApiClient(config?: ApiClientConfig): ApiClient {
  return new CodragApiClient(config);
}
