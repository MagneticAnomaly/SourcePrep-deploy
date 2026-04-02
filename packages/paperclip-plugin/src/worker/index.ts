/**
 * CoDRAG Plugin Worker
 *
 * Out-of-process worker that handles tool execution, events, and jobs
 * by proxying requests to the CoDRAG daemon HTTP API.
 */

// Types for the plugin SDK (will be replaced by actual SDK imports when available)
interface PluginContext {
  config: { get(): PluginConfig };
  tools: { register(name: string, declaration: any, handler: ToolHandler): void };
  events: { on(name: string, filter: any, handler: EventHandler): void };
  jobs: { register(key: string, opts: any, handler: JobHandler): void };
  state: {
    get(scope: string): Promise<any>;
    set(scope: string, value: any): Promise<void>;
  };
  data: { register(key: string, handler: DataHandler): void };
  actions: { register(key: string, handler: ActionHandler): void };
  logger: { info(msg: string, ...args: any[]): void; error(msg: string, ...args: any[]): void };
}

interface PluginConfig {
  daemon_url: string;
  project_id: string;
  auto_context: boolean;
}

type ToolHandler = (params: any, context: any) => Promise<any>;
type EventHandler = (event: any) => Promise<void>;
type JobHandler = (input: any) => Promise<void>;
type DataHandler = (input: any) => Promise<any>;
type ActionHandler = (input: any) => Promise<any>;

// ── CoDRAG Daemon Client ──────────────────────────────────────

class CodragDaemonClient {
  constructor(private baseUrl: string) {}

  async request(path: string, opts?: { method?: string; body?: any }): Promise<any> {
    const method = opts?.method ?? 'GET';
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    const init: RequestInit = { method, headers };
    if (opts?.body) {
      init.body = JSON.stringify(opts.body);
    }

    const res = await fetch(`${this.baseUrl}${path}`, init);
    if (!res.ok) {
      throw new Error(`CoDRAG daemon error: ${res.status} ${await res.text()}`);
    }

    const json = await res.json();
    // Unwrap envelope
    if (json?.success && json?.data !== undefined) {
      return json.data;
    }
    return json;
  }

  async resolveProjectId(config: PluginConfig, workspacePath?: string): Promise<string> {
    if (config.project_id) return config.project_id;

    // Auto-detect: list projects and match by workspace path
    if (workspacePath) {
      const data = await this.request('/projects');
      const projects = data?.projects ?? [];
      for (const p of projects) {
        if (p.path && workspacePath.startsWith(p.path)) {
          return p.id;
        }
      }
    }

    // Fallback: use first project
    const data = await this.request('/projects');
    const projects = data?.projects ?? [];
    if (projects.length === 1) {
      return projects[0].id;
    }

    throw new Error('Cannot auto-detect CoDRAG project. Set project_id in plugin config.');
  }
}

// ── Worker Entry Point ────────────────────────────────────────

export function initialize(ctx: PluginContext): void {
  const config = ctx.config.get();
  const client = new CodragDaemonClient(config.daemon_url);

  ctx.logger.info('CoDRAG plugin initializing', { daemon: config.daemon_url });

  // ── Register Tools ────────────────────────────────────────

  ctx.tools.register('context', {}, async (params, runCtx) => {
    const pid = await client.resolveProjectId(config, runCtx?.workspacePath);
    const role = params?.role ?? '';
    const query = role ? `role=${encodeURIComponent(role)}` : '';
    const path = query
      ? `/projects/${pid}/context?${query}`
      : `/projects/${pid}/context`;
    return await client.request(path);
  });

  ctx.tools.register('search', {}, async (params, runCtx) => {
    const pid = await client.resolveProjectId(config, runCtx?.workspacePath);
    return await client.request(`/projects/${pid}/search`, {
      method: 'POST',
      body: {
        query: params.query,
        k: params.k ?? 5,
        role: params.role,
      },
    });
  });

  ctx.tools.register('impact', {}, async (params, runCtx) => {
    const pid = await client.resolveProjectId(config, runCtx?.workspacePath);
    return await client.request(`/projects/${pid}/trace/impact`, {
      method: 'POST',
      body: { file: params.file },
    });
  });

  ctx.tools.register('audit', {}, async (params, runCtx) => {
    const pid = await client.resolveProjectId(config, runCtx?.workspacePath);
    const qs = params?.categories
      ? `?categories=${params.categories.join(',')}`
      : '';
    return await client.request(`/projects/${pid}/opportunities${qs}`);
  });

  ctx.tools.register('observe', {}, async (params, runCtx) => {
    const pid = await client.resolveProjectId(config, runCtx?.workspacePath);
    return await client.request(`/projects/${pid}/observations`, {
      method: 'POST',
      body: {
        content: params.content,
        file_path: params.file_path,
        category: params.category ?? 'note',
      },
    });
  });

  // ── Register Data Providers (for UI) ──────────────────────

  ctx.data.register('codebase-health', async (input) => {
    const pid = await client.resolveProjectId(config);
    const status = await client.request(`/projects/${pid}/agents/status`);
    const readiness = await client.request(`/projects/${pid}/agents/hr/readiness`);
    return { status, readiness };
  });

  ctx.data.register('agent-knowledge-scope', async (input) => {
    const pid = await client.resolveProjectId(config);
    const agentId = input?.context?.entityId;
    if (!agentId) return { files: [], error: 'No agent selected' };

    // Look up agent role in state
    const roleSlug = await ctx.state.get(`agent:${agentId}:role_slug`);
    if (!roleSlug) return { files: [], error: 'No role mapped for this agent' };

    return await client.request(`/projects/${pid}/scope/${roleSlug}`);
  });

  ctx.data.register('issue-context', async (input) => {
    const pid = await client.resolveProjectId(config);
    // Try to extract CoDRAG address from issue
    return { project_id: pid, available: true };
  });

  // ── Register Actions ──────────────────────────────────────

  ctx.actions.register('run-researcher', async (input) => {
    const pid = await client.resolveProjectId(config);
    return await client.request(`/projects/${pid}/agents/researcher/run`, {
      method: 'POST',
      body: { max_topics: input?.maxTopics ?? 3 },
    });
  });

  ctx.actions.register('run-custodian', async (input) => {
    const pid = await client.resolveProjectId(config);
    return await client.request(`/projects/${pid}/agents/custodian/run`, {
      method: 'POST',
      body: { dry_run: input?.dryRun ?? true, max_files: input?.maxFiles ?? 20 },
    });
  });

  // ── Register Event Handlers ───────────────────────────────

  if (config.auto_context) {
    ctx.events.on('issue.created', {}, async (event) => {
      // When an issue is created, check if it has a CoDRAG address
      // and auto-attach context if so
      ctx.logger.info('Issue created, checking for CoDRAG context', {
        issueId: event?.entityId,
      });
    });
  }

  ctx.events.on('agent.created', {}, async (event) => {
    ctx.logger.info('Agent created, ready for Knowledge Scope mapping', {
      agentId: event?.entityId,
    });
  });

  // ── Register Jobs ─────────────────────────────────────────

  ctx.jobs.register('reindex-check', { cron: '0 */6 * * *' }, async () => {
    try {
      const pid = await client.resolveProjectId(config);
      const health = await client.request('/health');
      ctx.logger.info('CoDRAG reindex check', {
        daemon: health?.status,
        project: pid,
      });
    } catch (err) {
      ctx.logger.error('CoDRAG daemon unreachable during reindex check');
    }
  });

  ctx.logger.info('CoDRAG plugin initialized — 5 tools, 3 data providers, 2 actions');
}

export function health(): { status: string; error?: string } {
  return { status: 'ok' };
}

export function shutdown(): void {
  // No cleanup needed — HTTP client is stateless
}
