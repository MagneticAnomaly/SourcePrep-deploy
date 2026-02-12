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
import type { LLMStatus, LicenseStatus, Project, ProjectStatus, TraceCoverage, TraceStatus, WatchStatus, GlobalConfig, ModelStatusResult, ModelReadinessStatus, AugmentationStatus, DeepAnalysisRunStatus, LLMSlotsStatus } from '../types';

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
  buildProject(projectId: string, full?: boolean): Promise<BuildProjectResponse>;

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

  // LLM
  getLLMStatus(): Promise<LLMStatus>;

  // Embedding
  getEmbeddingStatus(): Promise<{ available: boolean; model: string; dim: number; downloaded: boolean }>;
  downloadEmbedding(): Promise<{ status: string }>;

  // CLaRa
  getClaraStatus(): Promise<{ enabled: boolean; url: string; connected: boolean; model?: string }>;
  getClaraHealth(): Promise<{ healthy: boolean }>;

  // Activity & Coverage
  getProjectActivity(projectId: string, weeks?: number): Promise<{ weeks: any[]; total_builds: number }>;
  getProjectCoverage(projectId: string): Promise<{ tree: any[] }>;

  // License
  getLicense(): Promise<LicenseStatus>;

  // Global Config
  getGlobalConfig(): Promise<GlobalConfig>;
  updateGlobalConfig(config: GlobalConfig): Promise<GlobalConfig>;

  // LLM Proxy
  testLLMConnectivity(): Promise<{ ollama: { connected: boolean }; clara: { connected: boolean } }>;
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

  async buildProject(projectId: string, full = false): Promise<BuildProjectResponse> {
    return this.requestEnvelope<BuildProjectResponse>(`/projects/${encodeURIComponent(projectId)}/build`, {
      method: 'POST',
      query: { full },
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

  // ── LLM ────────────────────────────────────────────────────

  async getLLMStatus(): Promise<LLMStatus> {
    return this.requestEnvelope<LLMStatus>('/llm/status');
  }

  // ── License ────────────────────────────────────────────────

  async getLicense(): Promise<LicenseStatus> {
    return this.requestEnvelope<LicenseStatus>('/license');
  }

  // ── Embedding ────────────────────────────────────────────

  async getEmbeddingStatus(): Promise<{ available: boolean; model: string; dim: number; downloaded: boolean }> {
    return this.requestEnvelope<{ available: boolean; model: string; dim: number; downloaded: boolean }>('/embedding/status');
  }

  async downloadEmbedding(): Promise<{ status: string }> {
    return this.requestEnvelope<{ status: string }>('/embedding/download', { method: 'POST' });
  }

  // ── CLaRa ─────────────────────────────────────────────────

  async getClaraStatus(): Promise<{ enabled: boolean; url: string; connected: boolean; model?: string }> {
    return this.requestEnvelope<{ enabled: boolean; url: string; connected: boolean; model?: string }>('/clara/status');
  }

  async getClaraHealth(): Promise<{ healthy: boolean }> {
    return this.requestEnvelope<{ healthy: boolean }>('/clara/health');
  }

  // ── Activity & Coverage ──────────────────────────────────

  async getProjectActivity(projectId: string, weeks = 12): Promise<{ weeks: any[]; total_builds: number }> {
    return this.requestEnvelope<{ weeks: any[]; total_builds: number }>(
      `/projects/${encodeURIComponent(projectId)}/activity`,
      { query: { weeks } }
    );
  }

  async getProjectCoverage(projectId: string): Promise<{ tree: any[] }> {
    return this.requestEnvelope<{ tree: any[] }>(`/projects/${encodeURIComponent(projectId)}/coverage`);
  }

  // ── LLM Proxy ─────────────────────────────────────────────

  async testLLMConnectivity(): Promise<{ ollama: { connected: boolean }; clara: { connected: boolean } }> {
    return this.requestEnvelope<{ ollama: { connected: boolean }; clara: { connected: boolean } }>('/llm/test', {
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
}

export function createCodragApiClient(config?: ApiClientConfig): ApiClient {
  return new CodragApiClient(config);
}
