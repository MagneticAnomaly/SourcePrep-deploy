import type { ApiClient } from './client';

const MOCK_PROJECT = {
  id: 'proj_mock_001',
  name: 'Demo Project',
  path: '/mock/demo-project',
  mode: 'standalone' as const,
  created_at: '2026-01-15T10:00:00Z',
  updated_at: '2026-02-10T14:30:00Z',
};

const MOCK_STATUS = {
  building: false,
  stale: false,
  index: {
    exists: true,
    total_chunks: 1234,
    embedding_dim: 768,
    embedding_model: 'nomic-embed-text',
    last_build_at: '2026-02-10T12:00:00Z',
    last_error: null,
  },
  trace: {
    enabled: true,
    exists: true,
    building: false,
    node_count: 456,
    edge_count: 789,
    last_build_at: '2026-02-10T12:05:00Z',
    last_error: null,
  },
  watch: {
    enabled: false,
    state: 'disabled',
  },
};

export class MockApiClient implements ApiClient {
  public readonly baseUrl = 'mock://local';

  async getHealth(): Promise<{ status: string; version: string }> {
    return { status: 'ok', version: '0.1.0-mock' };
  }

  async listProjects(): Promise<any> {
    return { projects: [MOCK_PROJECT], total: 1 };
  }

  async createProject(): Promise<any> {
    return { project: { ...MOCK_PROJECT, id: `proj_mock_${Date.now()}` } };
  }

  async getProject(): Promise<any> {
    return { project: MOCK_PROJECT };
  }

  async updateProject(): Promise<any> {
    return { project: MOCK_PROJECT };
  }

  async deleteProject(): Promise<any> {
    return { removed: true, purged: false };
  }

  async getProjectStatus(): Promise<any> {
    return MOCK_STATUS;
  }

  async buildProject(): Promise<any> {
    return { started: true, building: true, build_id: 'build_mock_001' };
  }

  async search(): Promise<any> {
    return {
      results: [
        {
          chunk_id: 'chunk_mock_001',
          source_path: 'src/main.py',
          span: { start_line: 10, end_line: 25 },
          preview: 'def main():\n    """Main entry point for the application."""\n    ...',
          score: 0.92,
        },
        {
          chunk_id: 'chunk_mock_002',
          source_path: 'src/utils.py',
          span: { start_line: 45, end_line: 60 },
          preview: 'def process_data(input):\n    """Process input data and return results."""\n    ...',
          score: 0.85,
        },
      ],
    };
  }

  async assembleContext(): Promise<any> {
    return {
      context: '# Context for your query\n\n## src/main.py:10-25\n```python\ndef main():\n    """Main entry point."""\n    app = create_app()\n    app.run()\n```\n\n## src/utils.py:45-60\n```python\ndef process_data(input):\n    return transform(input)\n```',
      chunks: [],
      total_chars: 256,
      estimated_tokens: 64,
    };
  }

  async getTraceStatus(): Promise<any> {
    return MOCK_STATUS.trace;
  }

  async getProjectRoots(): Promise<any> {
    return { roots: ['/mock/demo-project'] };
  }

  async getProjectFileContent(_projectId: string, path: string): Promise<{ content: string; path: string; size: number }> {
    return { content: '// Mock content', path, size: 100 };
  }

  async detectStack(_projectId: string): Promise<{ recommended_globs: string[]; detected_presets: string[]; all_presets: Record<string, string[]> }> {
    await new Promise(resolve => setTimeout(resolve, 500));
    return {
      recommended_globs: ['**/*.ts', '**/*.tsx', '**/*.js', '**/*.json'],
      detected_presets: ['Web (JS/TS)'],
      all_presets: {
        "Web (JS/TS)": ["**/*.js", "**/*.jsx", "**/*.ts", "**/*.tsx", "**/*.html", "**/*.css", "**/*.json"],
        "Python": ["**/*.py", "**/*.ipynb"],
      }
    };
  }

  async startWatch(): Promise<any> {
    return { enabled: true, status: { enabled: true, state: 'idle', debounce_ms: 5000 } };
  }

  async stopWatch(): Promise<any> {
    return { enabled: false };
  }

  async getWatchStatus(): Promise<any> {
    return { enabled: false, state: 'disabled', debounce_ms: 5000, stale: false, pending: false };
  }

  async getLLMStatus(): Promise<any> {
    return {
      ollama: { url: 'http://localhost:11434', connected: true, models: ['nomic-embed-text'] },
    };
  }

  async testLLMConnectivity(): Promise<{ ollama: { connected: boolean } }> {
    return { ollama: { connected: true } };
  }

  async getProjectFiles(): Promise<any> {
    return {
      path: '/mock/demo-project',
      tree: [
        { name: 'src', type: 'folder', children: [{ name: 'main.py', type: 'file' }] },
        { name: 'README.md', type: 'file' },
      ],
    };
  }

  async getPathWeights(): Promise<any> {
    return { path_weights: { 'src/': 1.5, 'docs/': 0.5 } };
  }

  async updatePathWeights(): Promise<any> {
    return { path_weights: {} };
  }

  async searchTrace(): Promise<any> {
    return { nodes: [] };
  }

  async getTraceNode(): Promise<any> {
    return { node: { id: 'node_mock', kind: 'symbol', name: 'main' }, in_degree: 0, out_degree: 2 };
  }

  async getTraceNeighbors(): Promise<any> {
    return { nodes: [], edges: [] };
  }

  async buildTrace(): Promise<any> {
    return { started: true, building: true };
  }

  async getTraceCoverage(): Promise<any> {
    return {
      summary: { total_files: 10, traced_files: 8, untraced_files: 2, stale_files: 0, coverage_pct: 80 },
      untraced: [],
      stale: [],
      excluded: [],
    };
  }

  async updateTraceIgnore(): Promise<any> {
    return { success: true };
  }

  async getLicense(): Promise<any> {
    return {
      license: { tier: 'free', valid: true, email: null, expires_at: null, seats: 1, features: [] },
      features: { auto_rebuild: false, trace_index: true, mcp_tools: true },
    };
  }

  async activateLicense(_key: string): Promise<any> {
    return {
      license: { tier: 'pro', valid: true, email: 'user@example.com', expires_at: null, seats: 1, features: [] },
      features: { auto_rebuild: true, trace_index: true, mcp_tools: true },
    };
  }

  async deactivateLicense(): Promise<any> {
    return {
      license: { tier: 'free', valid: true, email: null, expires_at: null, seats: 1, features: [] },
      features: { auto_rebuild: false, trace_index: true, mcp_tools: true },
    };
  }

  async setDevTierOverride(tier: string | null): Promise<any> {
    const t = tier || 'free';
    return {
      license: { tier: t, valid: true, email: null, expires_at: null, seats: 1, features: [] },
      features: { auto_rebuild: t !== 'free', trace_index: true, mcp_tools: true },
    };
  }

  async getGlobalConfig(): Promise<any> {
    return { llm_config: { embedding: { source: 'huggingface' } } };
  }

  async updateGlobalConfig(): Promise<any> {
    return { success: true };
  }

  async getEmbeddingStatus(): Promise<any> {
    return { available: true, model: 'nomic-embed-text-v1.5', dim: 768, downloaded: true };
  }

  async downloadEmbedding(): Promise<any> {
    return { success: true };
  }

  async getCompressionStatus(): Promise<any> {
    return { lingua: { available: false, type: 'lingua' }, lod: { available: true, type: 'lod' } };
  }

  async downloadLinguaModel(): Promise<{ status: string }> {
    return { status: 'downloading' };
  }

  async getProjectActivity(): Promise<any> {
    return { days: [], totals: { embeddings: 0, trace: 0, builds: 0 } };
  }

  async getProjectCoverage(): Promise<any> {
    return { summary: { total_files: 10, indexed_files: 8, coverage_pct: 80 }, tree: [] };
  }

  async testLLMEndpoint(): Promise<any> {
    return { success: true, message: 'Connection successful' };
  }

  async fetchLLMModels(): Promise<any> {
    return { models: ['nomic-embed-text', 'llama3.2:3b', 'mistral:7b'] };
  }

  async testLLMModel(): Promise<any> {
    return { success: true, message: 'Model ready', model_status: 'ready' };
  }

  async getModelStatus(): Promise<any> {
    return { status: 'ready', loaded: true };
  }

  async getLLMSlotsStatus(): Promise<any> {
    return {
      embedding: { configured: false, status: 'not_configured' },
      small_model: { configured: false, status: 'not_configured' },
      large_model: { configured: false, status: 'not_configured' },
      code_model: { configured: false, status: 'not_configured' },
    };
  }

  async getAugmentStatus(): Promise<any> {
    return {
      enabled: false,
      total_nodes: 0,
      augmented_nodes: 0,
      validated_nodes: 0,
      avg_confidence: 0,
      low_confidence_count: 0,
    };
  }

  async runAugmentation(): Promise<any> {
    return { started: true, task_id: 'mock_augment_1' };
  }

  async getDeepAnalysisStatus(): Promise<any> {
    return {
      queue_size: 0,
      avg_confidence: 0,
      running: false,
    };
  }

  async runDeepAnalysis(): Promise<any> {
    return { started: true, task_id: 'mock_deep_1' };
  }

  async cancelDeepAnalysis(): Promise<any> {
    return { cancelled: true };
  }

  async destroyGraph(): Promise<any> {
    return { deleted: [], errors: [] };
  }

  async destroyIndex(): Promise<any> {
    return { deleted: [], errors: [] };
  }

  async getEpistemicStatus(): Promise<any> {
    return { enabled: false, enriched_nodes: 0, avg_confidence: 0, running: false };
  }

  async runEpistemic(): Promise<any> {
    return { started: true, task_id: 'mock_epistemic_1' };
  }

  async getModuleStatus(): Promise<any> {
    return { enabled: false, module_count: 0, total_files_clustered: 0, running: false };
  }

  async runModuleSynthesis(): Promise<any> {
    return { started: true, task_id: 'mock_cluster_1' };
  }

  async getDeepeningStatus(): Promise<any> {
    return { running: false, total_scored: 0, settled_count: 0, settled_ratio: 0, avg_score: 0 };
  }

  async runDeepening(): Promise<any> {
    return { started: true, task_id: 'mock_deepening_1' };
  }

  // ── Knowledge Embedding ─────────────────────────────────────

  async getKnowledgeStatus(): Promise<any> {
    return {
      enabled: false,
      running: false,
      chunks_embedded: 0,
      last_run_at: null,
    };
  }

  async runKnowledgeBuild(): Promise<any> {
    return { started: true, building: true };
  }

  // ── Pipeline Orchestrator ──────────────────────────────────

  async runPipelineFast(): Promise<any> {
    return { started: true, group: 'fast' };
  }

  async runPipelineDeep(): Promise<any> {
    return { started: true, group: 'deep' };
  }

  async runPipelineAll(): Promise<any> {
    return { started: true, group: 'all' };
  }

  async getPipelineStatus(): Promise<any> {
    return { running: false, group: null, stage: null, progress: null };
  }

  async cancelPipeline(): Promise<any> {
    return { cancelled: true, group: 'all' };
  }

  async pausePipeline(_projectId: string, _group: string): Promise<{ paused: boolean; group: string }> {
    return { paused: true, group: _group };
  }

  async resumePipeline(_projectId: string, _group: string): Promise<{ resumed: boolean; group: string }> {
    return { resumed: true, group: _group };
  }

  async getPipelineBudget(): Promise<any> {
    return { tokens_used: 0, max_tokens: 0, window_minutes: 5, remaining: -1, window_resets_in: 0 };
  }

  // ── Pipeline Crash Protection (Phase 25) ───────────────────────

  async getCrashedRuns(_projectId?: string): Promise<{ crashed_runs: any[]; count: number }> {
    return { crashed_runs: [], count: 0 };
  }

  async resumeCrashedRun(runId: string): Promise<{ resumed: boolean; run_id: string }> {
    return { resumed: true, run_id: runId };
  }

  async discardCrashedRun(runId: string): Promise<{ discarded: boolean; run_id: string }> {
    return { discarded: true, run_id: runId };
  }

  // ── Codebase Atlas (Phase 29) ──────────────────────────────────

  async getAtlas(_projectId: string): Promise<import('../types').AtlasStatus> {
    return {
      exists: true,
      content: 'Python/TypeScript monorepo. Core engine (src/codrag/core/) handles indexing, embedding, and search. API layer (src/codrag/api/) exposes FastAPI endpoints. Dashboard (packages/ui/) is a React + Tremor app. MCP server (src/codrag/mcp_server.py) bridges AI tools. Enrichment pipeline: trace → augment → validate → enrich → cluster → atlas → deepen → knowledge.',
      mode: 'structural',
      model: 'structural',
      generated_at: new Date().toISOString(),
      file_count: 547,
      module_count: 8,
      char_count: 312,
      stale: false,
    };
  }

  async regenerateAtlas(_projectId: string): Promise<import('../types').AtlasStatus> {
    return this.getAtlas(_projectId);
  }

  // ── Settings Store ────────────────────────────────────────

  async getSettings(): Promise<Record<string, any>> {
    return {};
  }

  async getSetting(_key: string): Promise<{ key: string; value: any }> {
    return { key: _key, value: null };
  }

  async setSetting(_key: string, _value: any): Promise<{ key: string; value: any }> {
    return { key: _key, value: _value };
  }

  async deleteSetting(_key: string): Promise<{ key: string; deleted: boolean }> {
    return { key: _key, deleted: true };
  }

  async getPipelineConfig(): Promise<any> {
    return { llm_concurrency: 1, fast_sync: { auto: true }, deep_enrichment: { mode: 'manual' }, budgets: {} };
  }

  async updatePipelineConfig(): Promise<any> {
    return { success: true };
  }

  async getProjectSettings(): Promise<Record<string, any>> {
    return {};
  }

  async setProjectSetting(_projectId: string, _key: string, _value: any): Promise<{ key: string; value: any }> {
    return { key: _key, value: _value };
  }

  // ── Advanced Config ──────────────────────────────────────

  async getAdvancedConfig(): Promise<import('../types').AdvancedConfig> {
    return {
      checkpoint_interval: 500,
      min_edge_confidence: 0.5,
      chunk_max_chars: 2000,
      chunk_overlap_chars: 200,
      md_chunk_max_chars: 1800,
      md_chunk_min_chars: 350,
    };
  }

  async updateAdvancedConfig(config: Partial<import('../types').AdvancedConfig>): Promise<import('../types').AdvancedConfig> {
    return { checkpoint_interval: 500, min_edge_confidence: 0.5, chunk_max_chars: 2000, chunk_overlap_chars: 200, md_chunk_max_chars: 1800, md_chunk_min_chars: 350, ...config };
  }

  // ── Scope Orchestrator ────────────────────────────────────

  async getScopeStatus(): Promise<any> {
    return { state: 'idle', files: [], pending: 0 };
  }

  async addScopeFiles(): Promise<any> {
    return { added: 0 };
  }

  async removeScopeFiles(): Promise<any> {
    return { removed: 0 };
  }

  async triggerScopeRebuild(): Promise<any> {
    return { started: true };
  }

  // ── Unified Graph Engine ──────────────────────────────────

  async getGraphEngineStatus(): Promise<any> {
    return {
      stages: {
        trace: { ...MOCK_STATUS.trace, stats: 456 },
        vector: { ...MOCK_STATUS.index, building: false },
        catalogue: {
          enabled: false,
          total_nodes: 0,
          augmented_nodes: 0,
          validated_nodes: 0,
          avg_confidence: 0,
          low_confidence_count: 0,
        },
        validation: {
          enabled: true,
          inferred_edges: 120,
          validated_edges: 100,
        },
        epistemic: {
          enabled: false,
          enriched_nodes: 0,
          avg_confidence: 0,
          running: false,
        },
        clustering: {
          enabled: false,
          module_count: 0,
          total_files_clustered: 0,
          running: false,
        },
        knowledge: {
          enabled: false,
          running: false,
          chunks_embedded: 0,
          last_run_at: null,
          building: false,
        },
      },
      deepening: {
        running: false,
        total_scored: 0,
        settled_count: 0,
        settled_ratio: 0,
        avg_score: 0,
      },
      global_running: false,
    };
  }
  async getIncludedPaths(_projectId: string): Promise<{ included_paths: string[] }> {
    return { included_paths: [] };
  }

  async updateIncludedPaths(_projectId: string, includedPaths: string[]): Promise<{ included_paths: string[] }> {
    return { included_paths: includedPaths };
  }

  // AutoAudit (Phase 43)
  async triggerAudit(_projectId: string, _opts?: { synthesize?: boolean; categories?: string[] }): Promise<{ status: string; synthesize: boolean }> {
    return { status: 'started', synthesize: _opts?.synthesize ?? false };
  }
  async getAuditStatus(_projectId: string): Promise<import('../types').AuditStatus> {
    return { running: false, error: null, has_results: false };
  }
  async getAuditFindings(_projectId: string, _opts?: { severity?: string; category?: string; limit?: number }): Promise<{ finding_count: number; total_finding_count: number; severity_counts: Record<string, number>; findings: import('../types').AuditFinding[] }> {
    return { finding_count: 0, total_finding_count: 0, severity_counts: {}, findings: [] };
  }
  async getAuditReports(_projectId: string): Promise<{ reports: import('../types').AuditReport[] }> {
    return { reports: [] };
  }
  async getAuditReport(_projectId: string, _reportName: string): Promise<{ name: string; content: string; size_bytes: number }> {
    return { name: _reportName, content: '# No report generated yet', size_bytes: 0 };
  }
}

export const createMockApiClient = (): ApiClient => new MockApiClient();
