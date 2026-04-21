import type {
  ApiEnvelope,
  HealthResponse,
  ProjectListItem,
  ProjectStatus,
  SearchResult,
  FileTreeNode,
  LicenseStatus,
  WatchStatus,
} from './types';

export class PrepClientError extends Error {
  readonly status?: number;
  readonly code?: string;

  constructor(message: string, opts?: { status?: number; code?: string }) {
    super(message);
    this.name = 'PrepClientError';
    this.status = opts?.status;
    this.code = opts?.code;
  }
}

/**
 * Lightweight HTTP client for the Prep daemon.
 * No React or browser dependencies — pure Node.js fetch.
 */
export class PrepDaemonClient {
  public readonly baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl.replace(/\/$/, '');
  }

  // ── Health ──────────────────────────────────────────────────

  async getHealth(): Promise<HealthResponse> {
    const res = await this.rawFetch('/health');
    if (!res.ok) {
      throw new PrepClientError(`Health check failed: HTTP ${res.status}`, { status: res.status });
    }
    return res.json() as Promise<HealthResponse>;
  }

  async isReachable(): Promise<boolean> {
    try {
      await this.getHealth();
      return true;
    } catch {
      return false;
    }
  }

  // ── Projects ────────────────────────────────────────────────

  async listProjects(): Promise<{ projects: ProjectListItem[]; total: number }> {
    return this.envelope<{ projects: ProjectListItem[]; total: number }>('/projects');
  }

  async createProject(path: string, name?: string, mode?: string): Promise<{ project: ProjectListItem }> {
    return this.envelope<{ project: ProjectListItem }>('/projects', {
      method: 'POST',
      body: { path, name, mode },
    });
  }

  async deleteProject(projectId: string, purge = false): Promise<{ removed: boolean; purged: boolean }> {
    return this.envelope<{ removed: boolean; purged: boolean }>(
      `/projects/${enc(projectId)}`,
      { method: 'DELETE', query: { purge: String(purge) } },
    );
  }

  // ── Status & Build ──────────────────────────────────────────

  async getProjectStatus(projectId: string): Promise<ProjectStatus> {
    return this.envelope<ProjectStatus>(`/projects/${enc(projectId)}/status`);
  }

  async buildProject(projectId: string, full = false): Promise<{ started: boolean; building: boolean }> {
    return this.envelope<{ started: boolean; building: boolean }>(
      `/projects/${enc(projectId)}/build`,
      { method: 'POST', query: { full: String(full) } },
    );
  }

  // ── Search & Context ────────────────────────────────────────

  async search(projectId: string, query: string, k = 10, minScore = 0.15): Promise<{ results: SearchResult[] }> {
    return this.envelope<{ results: SearchResult[] }>(
      `/projects/${enc(projectId)}/search`,
      { method: 'POST', body: { query, k, min_score: minScore } },
    );
  }

  async assembleContext(
    projectId: string,
    query: string,
    opts?: { k?: number; max_chars?: number; structured?: boolean },
  ): Promise<{ context: string; chunks?: unknown[]; total_chars?: number; estimated_tokens?: number }> {
    return this.envelope<{ context: string; chunks?: unknown[]; total_chars?: number; estimated_tokens?: number }>(
      `/projects/${enc(projectId)}/context`,
      { method: 'POST', body: { query, structured: true, ...opts } },
    );
  }

  // ── Files ───────────────────────────────────────────────────

  async getProjectFiles(projectId: string, path = '', depth = 3): Promise<{ path: string; tree: FileTreeNode[] }> {
    const query: Record<string, string> = {};
    if (path) { query.path = path; }
    if (depth !== 3) { query.depth = String(depth); }
    return this.envelope<{ path: string; tree: FileTreeNode[] }>(
      `/projects/${enc(projectId)}/files`,
      { query },
    );
  }

  async getProjectRoots(projectId: string): Promise<{ roots: string[] }> {
    return this.envelope<{ roots: string[] }>(`/projects/${enc(projectId)}/roots`);
  }

  // ── Watch ───────────────────────────────────────────────────

  async getWatchStatus(projectId: string): Promise<WatchStatus> {
    return this.envelope<WatchStatus>(`/projects/${enc(projectId)}/watch/status`);
  }

  async startWatch(projectId: string): Promise<{ enabled: boolean; state: string }> {
    return this.envelope<{ enabled: boolean; state: string }>(
      `/projects/${enc(projectId)}/watch/start`,
      { method: 'POST' },
    );
  }

  async stopWatch(projectId: string): Promise<{ enabled: boolean; state: string }> {
    return this.envelope<{ enabled: boolean; state: string }>(
      `/projects/${enc(projectId)}/watch/stop`,
      { method: 'POST' },
    );
  }

  // ── License ─────────────────────────────────────────────────

  async getLicense(): Promise<LicenseStatus> {
    return this.envelope<LicenseStatus>('/license');
  }

  async activateLicense(key: string): Promise<LicenseStatus> {
    return this.envelope<LicenseStatus>('/license/activate', {
      method: 'POST',
      body: { key },
    });
  }

  async deactivateLicense(): Promise<void> {
    return this.envelope<void>('/license/deactivate', { method: 'POST' });
  }

  // ── Trace ───────────────────────────────────────────────────

  async searchTrace(projectId: string, query: string, limit = 20): Promise<{ nodes: unknown[] }> {
    return this.envelope<{ nodes: unknown[] }>(
      `/projects/${enc(projectId)}/trace/search`,
      { method: 'POST', body: { query, limit } },
    );
  }

  // ── MCP Config ──────────────────────────────────────────────

  async getMCPConfig(projectId?: string): Promise<Record<string, unknown>> {
    const query: Record<string, string> = {};
    if (projectId) { query.project = projectId; }
    return this.envelope<Record<string, unknown>>('/mcp/config', { query });
  }

  // ── Internals ───────────────────────────────────────────────

  private async rawFetch(path: string, init?: RequestInit): Promise<Response> {
    const url = `${this.baseUrl}${path}`;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 5000);
    try {
      return await fetch(url, { ...init, signal: controller.signal });
    } finally {
      clearTimeout(timeout);
    }
  }

  private async envelope<T>(
    path: string,
    opts?: {
      method?: string;
      query?: Record<string, string>;
      body?: unknown;
    },
  ): Promise<T> {
    let url = `${this.baseUrl}${path}`;
    if (opts?.query) {
      const params = new URLSearchParams(opts.query);
      const qs = params.toString();
      if (qs) { url += `?${qs}`; }
    }

    const headers: Record<string, string> = { Accept: 'application/json' };
    let bodyStr: string | undefined;
    if (opts?.body !== undefined) {
      headers['Content-Type'] = 'application/json';
      bodyStr = JSON.stringify(opts.body);
    }

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 30_000);
    let res: Response;
    try {
      res = await fetch(url, {
        method: opts?.method ?? 'GET',
        headers,
        body: bodyStr,
        signal: controller.signal,
      });
    } catch (err) {
      throw new PrepClientError(
        `Network error contacting Prep daemon at ${this.baseUrl}: ${err instanceof Error ? err.message : String(err)}`,
      );
    } finally {
      clearTimeout(timeout);
    }

    let json: unknown;
    try {
      json = await res.json();
    } catch {
      throw new PrepClientError(`Invalid JSON from daemon (HTTP ${res.status})`, { status: res.status });
    }

    const envelope = json as ApiEnvelope<T>;
    if (typeof envelope !== 'object' || envelope === null || typeof envelope.success !== 'boolean') {
      throw new PrepClientError('Unexpected response shape from daemon', { status: res.status });
    }

    if (!envelope.success) {
      const msg = envelope.error?.message ?? `Request failed (HTTP ${res.status})`;
      throw new PrepClientError(msg, { status: res.status, code: envelope.error?.code });
    }

    if (envelope.data === null || envelope.data === undefined) {
      throw new PrepClientError('Envelope success=true but data was null', { status: res.status });
    }

    return envelope.data;
  }
}

function enc(s: string): string {
  return encodeURIComponent(s);
}
