/**
 * CoDRAG Paperclip Plugin Worker
 *
 * Out-of-process worker that handles tool execution, events, and jobs
 * by proxying requests to the CoDRAG daemon HTTP API.
 */
import {
  definePlugin,
  runWorker,
  type PluginContext,
  type ToolRunContext,
  type ToolResult,
  type PluginHealthDiagnostics,
  type PluginConfigValidationResult,
} from '@paperclipai/plugin-sdk';

// ── CoDRAG Daemon Client ──────────────────────────────────────

interface CodragConfig {
  daemon_url: string;
  project_id: string;
  auto_context: boolean;
}

class CodragDaemonClient {
  constructor(private baseUrl: string) {}

  async request(path: string, opts?: { method?: string; body?: unknown }): Promise<unknown> {
    const method = opts?.method ?? 'GET';
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    };
    const init: RequestInit = { method, headers };
    if (opts?.body) {
      init.body = JSON.stringify(opts.body);
    }

    const res = await fetch(`${this.baseUrl}${path}`, init);
    if (!res.ok) {
      const text = await res.text().catch(() => '');
      throw new Error(`CoDRAG daemon ${method} ${path} returned ${res.status}: ${text.slice(0, 200)}`);
    }

    const json = await res.json();
    // Unwrap the CoDRAG API envelope {success, data, error}
    if (json?.success && json?.data !== undefined) {
      return json.data;
    }
    return json;
  }

  async health(): Promise<{ status: string; version: string }> {
    return this.request('/health') as Promise<{ status: string; version: string }>;
  }

  async resolveProjectId(config: CodragConfig): Promise<string> {
    if (config.project_id) return config.project_id;

    // Auto-detect: use the first (or only) project
    const data = (await this.request('/projects')) as { projects?: Array<{ id: string; path: string }> };
    const projects = data?.projects ?? [];
    if (projects.length === 1) {
      return projects[0].id;
    }
    if (projects.length === 0) {
      throw new Error('No CoDRAG projects found. Add a project first: codrag add <path>');
    }
    throw new Error(
      `Multiple CoDRAG projects found (${projects.length}). ` +
      'Set project_id in plugin config to disambiguate.'
    );
  }
}

// ── Plugin Definition ─────────────────────────────────────────

// Module-level state so onHealth/onValidateConfig can access the daemon URL
let activeDaemonUrl = 'http://127.0.0.1:8400';

const plugin = definePlugin({
  async setup(ctx: PluginContext) {
    const rawConfig = await ctx.config.get();
    const config: CodragConfig = {
      daemon_url: (rawConfig as Record<string, unknown>).daemon_url as string ?? 'http://127.0.0.1:8400',
      project_id: (rawConfig as Record<string, unknown>).project_id as string ?? '',
      auto_context: (rawConfig as Record<string, unknown>).auto_context as boolean ?? true,
    };
    activeDaemonUrl = config.daemon_url;
    const client = new CodragDaemonClient(config.daemon_url);

    ctx.logger.info('CoDRAG plugin initializing', { daemon: config.daemon_url });

    // ── Tool: codrag:context ────────────────────────────────

    ctx.tools.register(
      'context',
      {
        displayName: 'Codebase Context',
        description: 'Structural overview of the codebase: modules, hubs, atlas. Call at the start of every task.',
        parametersSchema: {
          type: 'object',
          properties: {
            role: { type: 'string', description: 'Optional role slug for scoped context' },
          },
        },
      },
      async (params: unknown, _runCtx: ToolRunContext): Promise<ToolResult> => {
        try {
          const pid = await client.resolveProjectId(config);
          const p = params as Record<string, unknown> | null;
          const role = p?.role as string | undefined;
          const qs = role ? `?role=${encodeURIComponent(role)}` : '';
          const data = await client.request(`/projects/${pid}/context${qs}`);
          return { content: typeof data === 'string' ? data : JSON.stringify(data, null, 2) };
        } catch (err) {
          return { error: String(err) };
        }
      },
    );

    // ── Tool: codrag:search ─────────────────────────────────

    ctx.tools.register(
      'search',
      {
        displayName: 'Code Search',
        description: 'Semantic code search with structural trace expansion.',
        parametersSchema: {
          type: 'object',
          properties: {
            query: { type: 'string', description: 'Search query' },
            role: { type: 'string', description: 'Optional role for scoped results' },
            k: { type: 'number', description: 'Max results (default 5)' },
          },
          required: ['query'],
        },
      },
      async (params: unknown, _runCtx: ToolRunContext): Promise<ToolResult> => {
        try {
          const pid = await client.resolveProjectId(config);
          const p = params as Record<string, unknown>;
          const data = await client.request(`/projects/${pid}/search`, {
            method: 'POST',
            body: { query: p.query, k: p.k ?? 5, role: p.role },
          });
          return { content: typeof data === 'string' ? data : JSON.stringify(data, null, 2) };
        } catch (err) {
          return { error: String(err) };
        }
      },
    );

    // ── Tool: codrag:impact ─────────────────────────────────

    ctx.tools.register(
      'impact',
      {
        displayName: 'Impact Analysis',
        description: 'Analyze what depends on a file — dependencies, dependents, blast radius.',
        parametersSchema: {
          type: 'object',
          properties: {
            file: { type: 'string', description: 'File path to analyze' },
          },
          required: ['file'],
        },
      },
      async (params: unknown, _runCtx: ToolRunContext): Promise<ToolResult> => {
        try {
          const pid = await client.resolveProjectId(config);
          const p = params as Record<string, unknown>;
          const data = await client.request(`/projects/${pid}/trace/impact`, {
            method: 'POST',
            body: { file: p.file },
          });
          return { content: typeof data === 'string' ? data : JSON.stringify(data, null, 2) };
        } catch (err) {
          return { error: String(err) };
        }
      },
    );

    // ── Tool: codrag:audit ──────────────────────────────────

    ctx.tools.register(
      'audit',
      {
        displayName: 'Codebase Audit',
        description: 'Get codebase health findings — tech debt, architecture issues, opportunities.',
        parametersSchema: {
          type: 'object',
          properties: {
            categories: { type: 'array', items: { type: 'string' }, description: 'Filter by categories' },
          },
        },
      },
      async (params: unknown, _runCtx: ToolRunContext): Promise<ToolResult> => {
        try {
          const pid = await client.resolveProjectId(config);
          const p = params as Record<string, unknown> | null;
          const cats = (p?.categories as string[] | undefined)?.join(',');
          const qs = cats ? `?categories=${cats}` : '';
          const data = await client.request(`/projects/${pid}/opportunities${qs}`);
          return { content: typeof data === 'string' ? data : JSON.stringify(data, null, 2) };
        } catch (err) {
          return { error: String(err) };
        }
      },
    );

    // ── Tool: codrag:observe ────────────────────────────────

    ctx.tools.register(
      'observe',
      {
        displayName: 'Save Observation',
        description: 'Save a cross-session observation for future reference.',
        parametersSchema: {
          type: 'object',
          properties: {
            content: { type: 'string', description: 'Observation text' },
            file_path: { type: 'string', description: 'Related file path' },
            category: { type: 'string', description: 'Category: note, decision, bug, pattern, assumption' },
          },
          required: ['content'],
        },
      },
      async (params: unknown, _runCtx: ToolRunContext): Promise<ToolResult> => {
        try {
          const pid = await client.resolveProjectId(config);
          const p = params as Record<string, unknown>;
          const data = await client.request(`/projects/${pid}/observations`, {
            method: 'POST',
            body: {
              content: p.content,
              file_path: p.file_path,
              category: p.category ?? 'note',
              created_by: 'paperclip-agent',
            },
          });
          return { content: JSON.stringify(data) };
        } catch (err) {
          return { error: String(err) };
        }
      },
    );

    // ── Data Providers (for UI) ─────────────────────────────

    ctx.data.register('codebase-health', async () => {
      try {
        const pid = await client.resolveProjectId(config);
        const [status, readiness, pushSummary, consensus, delta] = await Promise.all([
          client.request(`/projects/${pid}/agents/status`),
          client.request(`/projects/${pid}/agents/hr/readiness`),
          client.request(`/projects/${pid}/collaboration/push-summary`).catch(() => null),
          client.request(`/projects/${pid}/collaboration/consensus`).catch(() => ({ scores: [] })),
          client.request(`/projects/${pid}/collaboration/delta`).catch(() => null),
        ]);
        return {
          status,
          readiness,
          push_summary: pushSummary,
          consensus: (consensus as any)?.scores ?? [],
          delta,
        };
      } catch {
        return { status: null, readiness: null, push_summary: null, consensus: [], delta: null, error: 'CoDRAG daemon unavailable' };
      }
    });

    ctx.data.register('agent-knowledge-scope', async (input) => {
      try {
        const pid = await client.resolveProjectId(config);
        const agentId = (input as Record<string, unknown>)?.entityId as string;
        if (!agentId) return { files: [], role: null, error: 'No agent selected' };

        // Try reading role from agent's adapter config first, fall back to state
        let roleSlug: string | null = null;
        try {
          const agent = await (ctx as any).agents?.get?.(agentId);
          roleSlug = (agent as any)?.adapterConfig?.codrag_role ?? null;
        } catch {
          // agents API may not be available
        }

        if (!roleSlug) {
          roleSlug = await ctx.state.get({
            scopeKind: 'agent',
            scopeId: agentId,
            stateKey: 'role_slug',
          }) as string | null;
        }

        if (!roleSlug) return { files: [], role: null, error: 'No CoDRAG role mapped for this agent' };

        const data = await client.request(`/projects/${pid}/agent-scope/${roleSlug}`);
        return { ...(data as object), role: roleSlug };
      } catch (err) {
        return { files: [], role: null, error: String(err) };
      }
    });

    // ── Phase 73.5: Collaboration Data Providers ───────────

    ctx.data.register('structural-delta', async () => {
      try {
        const pid = await client.resolveProjectId(config);
        const data = await client.request(`/projects/${pid}/collaboration/delta`);
        return data;
      } catch (err) {
        return { is_empty: true, error: String(err) };
      }
    });

    ctx.data.register('agent-claims', async () => {
      try {
        const pid = await client.resolveProjectId(config);
        const data = await client.request(`/projects/${pid}/collaboration/claims`);
        return data;
      } catch (err) {
        return { claims: [], error: String(err) };
      }
    });

    ctx.data.register('consensus-hotspots', async () => {
      try {
        const pid = await client.resolveProjectId(config);
        const data = await client.request(`/projects/${pid}/collaboration/consensus`);
        return data;
      } catch (err) {
        return { scores: [], error: String(err) };
      }
    });

    ctx.data.register('push-summary', async () => {
      try {
        const pid = await client.resolveProjectId(config);
        const data = await client.request(`/projects/${pid}/collaboration/push-summary`);
        return data;
      } catch (err) {
        return { total_pushes: 0, latest_push_at: null, error: String(err) };
      }
    });

    // ── Actions ─────────────────────────────────────────────

    ctx.actions.register('run-researcher', async (input) => {
      const pid = await client.resolveProjectId(config);
      const p = input as Record<string, unknown> | null;
      return client.request(`/projects/${pid}/agents/researcher/run`, {
        method: 'POST',
        body: { max_topics: (p?.maxTopics as number) ?? 3 },
      });
    });

    ctx.actions.register('run-custodian', async (input) => {
      const pid = await client.resolveProjectId(config);
      const p = input as Record<string, unknown> | null;
      return client.request(`/projects/${pid}/agents/custodian/run`, {
        method: 'POST',
        body: { dry_run: (p?.dryRun as boolean) ?? true, max_files: (p?.maxFiles as number) ?? 20 },
      });
    });

    ctx.actions.register('enrich-issue', async (input) => {
      const pid = await client.resolveProjectId(config);
      const p = input as Record<string, unknown>;
      const issueId = p?.issueId as string;
      if (!issueId) return { error: 'No issue ID provided' };

      // Get the issue to extract file paths from description
      let desc = '';
      try {
        const issue = await (ctx as any).issues?.get?.(issueId);
        desc = (issue as any)?.description ?? '';
      } catch {
        return { error: 'Could not fetch issue' };
      }

      // Extract file paths (simple heuristic: paths with extensions)
      const filePaths = desc.match(/[\w/.-]+\.\w{1,10}/g) ?? [];
      const uniquePaths = [...new Set(filePaths)].slice(0, 5);

      if (uniquePaths.length === 0) {
        return { error: 'No file paths found in issue description' };
      }

      const results = await Promise.all(
        uniquePaths.map((file: string) =>
          client.request(`/projects/${pid}/trace/impact`, {
            method: 'POST',
            body: { file },
          }).catch(() => null),
        ),
      );

      return {
        files_analyzed: uniquePaths,
        impact: results.filter(Boolean),
      };
    });

    // ── Event Handlers ──────────────────────────────────────

    if (config.auto_context) {
      ctx.events.on('issue.created', async (event) => {
        ctx.logger.info('Issue created — checking for CoDRAG context', {
          entityId: event.entityId,
        });
      });
    }

    ctx.events.on('agent.created', async (event) => {
      ctx.logger.info('Agent created — ready for Knowledge Scope mapping', {
        entityId: event.entityId,
      });
    });

    // ── Jobs ────────────────────────────────────────────────

    ctx.jobs.register('reindex-check', async (job) => {
      try {
        const health = await client.health();
        ctx.logger.info('CoDRAG reindex check passed', {
          daemon: health.status,
          runId: job.runId,
        });
      } catch {
        ctx.logger.error('CoDRAG daemon unreachable during reindex check');
      }
    });

    ctx.logger.info('CoDRAG plugin initialized — 5 tools, 6 data providers, 3 actions, 1 job');
  },

  async onHealth(): Promise<PluginHealthDiagnostics> {
    try {
      const res = await fetch(`${activeDaemonUrl}/health`, { signal: AbortSignal.timeout(3000) });
      if (res.ok) {
        return { status: 'ok', message: `CoDRAG daemon reachable at ${activeDaemonUrl}` };
      }
      return { status: 'degraded', message: `CoDRAG daemon returned ${res.status}` };
    } catch {
      return { status: 'error', message: `Cannot reach CoDRAG daemon at ${activeDaemonUrl}` };
    }
  },

  async onValidateConfig(config: Record<string, unknown>): Promise<PluginConfigValidationResult> {
    const url = config.daemon_url as string;
    if (!url) {
      return { ok: false, errors: ['daemon_url is required'] };
    }
    try {
      const res = await fetch(`${url}/health`, { signal: AbortSignal.timeout(5000) });
      if (res.ok) {
        return { ok: true };
      }
      return { ok: false, errors: [`CoDRAG daemon at ${url} returned ${res.status}`] };
    } catch {
      return {
        ok: false,
        errors: [`Cannot connect to CoDRAG daemon at ${url}. Is the desktop app running?`],
      };
    }
  },
});

export default plugin;

// Start the JSON-RPC worker when executed as a process
runWorker(plugin, import.meta.url);
