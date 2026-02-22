/**
 * CoDRAG UI Type Definitions
 */

/**
 * Status states for index/build indicators
 * These are the core states that appear throughout the UI
 */
export type StatusState = 
  | 'fresh'      // Index is up-to-date
  | 'stale'      // Changes detected, rebuild needed
  | 'building'   // Build in progress
  | 'pending'    // Build queued
  | 'error'      // Build failed or error state
  | 'disabled';  // Feature disabled

/**
 * Search result from the CoDRAG API
 */
export interface SearchResult {
  chunk_id: string;
  source_path: string;
  span: {
    start_line: number;
    end_line: number;
  };
  preview: string;
  score: number;
  // Optional extras for different contexts
  section?: string;
  content?: string;
}

/**
 * Code chunk for display
 */
export interface CodeChunk {
  id: string;
  source_path: string;
  span: {
    start_line: number;
    end_line: number;
  };
  content: string;
  language?: string;
}

/**
 * Project summary for list display
 */
export interface ProjectSummary {
  id: string;
  name: string;
  path: string;
  mode: ProjectMode;
  status: StatusState;
  chunk_count?: number;
  last_build_at?: string;
}

// ============================================================
// Phase 03 - Auto-Rebuild Types
// ============================================================

/**
 * Watch state for file watcher
 */
export type WatchState = 'disabled' | 'idle' | 'debouncing' | 'building' | 'throttled';

/**
 * Build phase for progress reporting
 */
export type BuildPhase = 
  | 'scanning' 
  | 'chunking' 
  | 'embedding' 
  | 'writing' 
  | 'complete'
  | 'trace_scan'
  | 'trace_parse'
  | 'trace_write';

/**
 * Watch status from API
 */
export interface WatchStatus {
  enabled: boolean;
  state: WatchState;
  debounce_ms?: number;
  stale?: boolean;
  pending?: boolean;
  pending_paths_count?: number;
  next_rebuild_at?: string | null;
  last_event_at?: string | null;
  last_rebuild_at?: string | null;
}

/**
 * Build history entry
 */
export interface BuildHistoryEntry {
  id: string;
  project_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  started_at: string;
  completed_at?: string;
  stats?: {
    files_scanned: number;
    chunks_created: number;
    chunks_embedded: number;
    duration_ms: number;
  };
  error?: string;
}

// ============================================================
// Phase 04 - Trace Index Types
// ============================================================

/**
 * Node kind in code graph
 */
export type NodeKind = 'file' | 'symbol' | 'external_module';

/**
 * Edge kind in code graph
 */
export type EdgeKind = 'contains' | 'imports' | 'calls' | 'implements' | 'documented_by';

/**
 * Trace node from API
 */
export interface TraceNode {
  id: string;
  kind: NodeKind;
  name: string;
  file_path: string;
  span: { start_line: number; end_line: number };
  language: string | null;
  metadata: {
    symbol_type?: string;
    qualname?: string;
    docstring?: string;
    decorators?: string[];
    is_async?: boolean;
    is_public?: boolean;
    [key: string]: unknown;
  };
}

/**
 * Trace edge from API
 */
export interface TraceEdge {
  id: string;
  kind: EdgeKind;
  source: string;
  target: string;
  metadata: {
    confidence: number;
    import?: string;
    [key: string]: unknown;
  };
}

/**
 * Code Graph status from API
 */
export interface TraceStatus {
  enabled: boolean;
  exists: boolean;
  building: boolean;
  counts: { nodes: number; edges: number };
  last_build_at: string | null;
  last_error: string | null;
  /** Which engine is active: 'rust' or 'python' */
  engine?: string;
  /** Languages the engine can parse (e.g. python, typescript, go, rust, java, c, cpp) */
  supported_languages?: string[];
  /** True when graph has nodes but 0 edges (degenerate graph) */
  degraded?: boolean;
  /** Human-readable reason for degradation */
  degraded_reason?: string | null;
}

/**
 * File entry in trace coverage report
 */
export interface TraceCoverageFile {
  path: string;
  language: string | null;
  size: number;
  modified: string;
  created: string;
}

/**
 * Code Graph coverage summary
 */
export interface TraceCoverageSummary {
  total: number;
  traced: number;
  pending_embedding?: number;
  untraced: number;
  stale: number;
  excluded: number;
  coverage_pct: number;
  last_build_at: string | null;
}

/**
 * Full trace coverage report from API
 */
export interface TraceCoverage {
  traced: TraceCoverageFile[];
  pending_embedding?: TraceCoverageFile[];
  untraced: TraceCoverageFile[];
  stale: TraceCoverageFile[];
  excluded: TraceCoverageFile[];
  summary: TraceCoverageSummary;
  building: boolean;
}

/**
 * Trace expand options for context assembly
 */
export interface TraceExpandOptions {
  enabled: boolean;
  hops: number;
  direction: 'in' | 'out' | 'both';
  edge_kinds: EdgeKind[];
  max_nodes: number;
  max_additional_chunks: number;
  max_additional_chars: number;
}

// ============================================================
// Phase 04B - Deep Analysis / LLM Augmentation Types
// ============================================================

/**
 * Evidence tier for retrieval scoping.
 * Tier 0 = ground truth only (no LLM content), used by validation.
 * Tier 1 = ground truth + verified high-confidence augmentations.
 * Tier 2 = everything including unverified augmentations (default search).
 */
export type EvidenceTier = 0 | 1 | 2;

/**
 * Deep enrichment mode (Phase 26: standardized terminology)
 */
export type DeepEnrichmentMode = 'manual' | 'threshold' | 'scheduled' | 'auto';
/** @deprecated Use DeepEnrichmentMode */
export type DeepAnalysisMode = DeepEnrichmentMode;

/**
 * Deep enrichment priority ordering
 */
export type DeepEnrichmentPriority = 'lowest_confidence' | 'highest_connectivity';
/** @deprecated Use DeepEnrichmentPriority */
export type DeepAnalysisPriority = DeepEnrichmentPriority;

/**
 * Schedule frequency
 */
export type ScheduleFrequency = 'daily' | 'weekly' | 'biweekly' | 'monthly';

/**
 * Deep enrichment configuration (persisted in global config)
 */
export interface DeepEnrichmentConfig {
  mode: DeepEnrichmentMode;
  threshold_percent?: number;
  frequency?: ScheduleFrequency;
  day_of_week?: number;
  hour?: number;
  budget_enabled: boolean;
  budget_max_tokens: number;
  budget_max_minutes: number;
  budget_max_items: number;
  priority: DeepEnrichmentPriority;
}
/** @deprecated Use DeepEnrichmentConfig */
export type DeepAnalysisScheduleConfig = DeepEnrichmentConfig;
/** @deprecated Use DeepEnrichmentConfig */
export type DeepAnalysisSchedule = DeepEnrichmentConfig;

/**
 * Deep enrichment run status from API
 */
export interface DeepEnrichmentRunStatus {
  last_run_at?: string;
  last_run_items?: number;
  last_run_tokens?: number;
  next_run_at?: string;
  queue_size?: number;
  avg_confidence?: number;
  running?: boolean;
  current_item?: string;
  progress_pct?: number;
  progress_current?: number;
  progress_total?: number;
  stop_reason?: string;
  budget_exhausted?: boolean;
  queue_remaining?: number;
}
/** @deprecated Use DeepEnrichmentRunStatus */
export type DeepAnalysisRunStatus = DeepEnrichmentRunStatus;

/**
 * Trace augmentation entry (per-node overlay)
 */
export interface TraceAugmentation {
  node_id: string;
  summary: string;
  role: string;
  confidence: number;
  augmented_at: string;
  model: string;
  version: number;
  validated?: boolean;
  validated_at?: string;
  validated_by?: string;
}

/**
 * Inferred edges status (Stage 2 — code model edge discovery)
 */
export interface InferredEdgesStatus {
  enabled: boolean;
  exists: boolean;
  edge_count: number;
  running?: boolean;
  slot_progress?: { message: string; current: number; total: number };
  slot_phase?: string;
}

/**
 * Augmentation status summary
 */
export interface AugmentationStatus {
  enabled: boolean;
  total_nodes: number;
  augmented_nodes: number;
  validated_nodes: number;
  avg_confidence: number;
  low_confidence_count: number;
  last_augment_at?: string;
  last_validate_at?: string;
  model?: string;
}

/**
 * Epistemic enrichment status (Pass 2)
 */
export interface EpistemicStatus {
  enabled: boolean;
  enriched_nodes: number;
  total_file_nodes?: number;
  avg_confidence: number;
  running: boolean;
  /** True when ANY deep enrichment stage (5-8) is active (for DeepCoverageBar) */
  pipeline_running?: boolean;
  progress_current?: number;
  progress_total?: number;
}

/**
 * Module/cluster synthesis status (Pass 3)
 */
export interface ModuleStatus {
  enabled: boolean;
  module_count: number;
  total_files_clustered: number;
  running: boolean;
  last_run_at?: string | null;
  progress_current?: number;
  progress_total?: number;
}

/**
 * Deepening loop status (Pass 4+)
 */
export interface DeepeningStatus {
  running: boolean;
  total_scored: number;
  settled_count: number;
  settled_ratio: number;
  avg_score: number;
  min_score?: number;
  max_score?: number;
  iteration?: number;
  max_iterations?: number;
}

/**
 * Codebase Atlas status (Phase 29)
 */
export interface AtlasStatus {
  exists: boolean;
  content: string | null;
  mode?: 'llm' | 'structural';
  model?: string;
  generated_at?: string;
  file_count?: number;
  module_count?: number;
  char_count?: number;
  stale?: boolean;
  segmented?: boolean;
  routing?: boolean;
  running?: boolean;
}

// ============================================================
// Phase 05 - MCP Types
// ============================================================

/**
 * MCP tool definition
 */
export interface MCPTool {
  name: string;
  description: string;
  inputs: MCPToolInput[];
  example?: string;
}

export interface MCPToolInput {
  name: string;
  type: string;
  required: boolean;
  description: string;
  default?: unknown;
}

// ============================================================
// Phase 06 - Team & Enterprise Types
// ============================================================

/**
 * Project mode
 */
export type ProjectMode = 'standalone' | 'embedded' | 'custom';

/**
 * Server mode for network access
 */
export type ServerMode = 'local' | 'remote';

/**
 * License tier
 */
export type LicenseTier = 'free' | 'pro' | 'team' | 'enterprise';

/**
 * Team config status
 */
export type TeamConfigStatus = 'none' | 'applied' | 'overridden' | 'conflict';

/**
 * LLM service status (basic)
 */
export interface LLMStatus {
  ollama: {
    url: string;
    connected: boolean;
    models: string[];
  };
}

// ============================================================
// LLM Configuration Types (AI Models Settings)
// ============================================================

/**
 * Provider types for LLM endpoints
 */
export type LLMProvider = 'ollama' | 'openai' | 'openai-compatible' | 'anthropic';

/**
 * Model source for embedding
 */
export type ModelSource = 'endpoint' | 'huggingface';

/**
 * Saved endpoint configuration
 */
export interface SavedEndpoint {
  id: string;
  name: string;
  provider: LLMProvider;
  url: string;
  api_key?: string;
}

/**
 * Embedding model configuration
 */
export interface EmbeddingConfig {
  source: ModelSource;
  // Endpoint mode
  endpoint_id?: string;
  model?: string;
  // HuggingFace mode
  hf_repo_id?: string;
  hf_downloaded?: boolean;
  hf_model_path?: string;
  hf_download_progress?: number;
}

/**
 * Generic LLM slot configuration (small/large/code models)
 */
export interface LLMSlotConfig {
  enabled: boolean;
  endpoint_id?: string;
  model?: string;
}

/**
 * Compression configuration (LLMLingua-2 + LOD)
 */
export interface CompressionConfig {
  enabled: boolean;
  mode: 'none' | 'lingua' | 'auto';
  level: 'light' | 'standard' | 'aggressive';
  lingua_downloaded?: boolean;
  lingua_download_progress?: number;
}

/**
 * Full LLM configuration
 */
/**
 * Batch processing mode for BYOK cloud models.
 * 'auto' detects the model and picks the best profile.
 */
export type BatchMode = 'auto' | 'large' | 'standard' | 'compact' | 'off';

export interface LLMConfig {
  embedding: EmbeddingConfig;
  small_model: LLMSlotConfig;
  large_model: LLMSlotConfig;
  code_model: LLMSlotConfig;
  compression: CompressionConfig;
  saved_endpoints: SavedEndpoint[];
  batch_mode?: BatchMode;
}

/**
 * Model slot type for UI
 */
export type ModelSlotType = 'embedding' | 'small' | 'large' | 'code';

/**
 * HuggingFace download status
 */
export interface HFDownloadStatus {
  model_type: ModelSlotType;
  status: 'idle' | 'downloading' | 'complete' | 'error';
  progress?: number;
  bytes_downloaded?: string;
  error?: string;
}

/**
 * Model readiness status from the backend.
 * Ollama models can be: not_found (not downloaded), downloaded (on disk
 * but not in VRAM), loading (being loaded into memory), ready (serving),
 * or error (provider unreachable).
 */
export type ModelReadinessStatus = 'not_found' | 'downloaded' | 'loading' | 'ready' | 'error' | 'unknown';

/**
 * Result from the /api/llm/model-status endpoint
 */
export interface ModelStatusResult {
  status: ModelReadinessStatus;
  message: string;
  model: string;
  provider: string;
  details?: Record<string, unknown>;
}

/**
 * Endpoint test result
 */
export interface EndpointTestResult {
  success: boolean;
  message: string;
  models?: string[];
  model_status?: ModelReadinessStatus;
}

/**
 * Server status (team/enterprise mode)
 */
export interface ServerStatus {
  mode: ServerMode;
  requires_auth: boolean;
  bind_address?: string;
}

/**
 * Team configuration
 */
export interface TeamConfig {
  include_globs: string[];
  exclude_globs: string[];
  trace_enabled: boolean;
  embedding_model: string;
}

/**
 * License information
 */
export interface LicenseInfo {
  tier: LicenseTier;
  valid: boolean;
  expires_at?: string;
  seats_used?: number;
  seats_total?: number;
  features: string[];
}

/**
 * Project configuration
 */
export interface ProjectConfig {
  include_globs: string[];
  exclude_globs: string[];
  max_file_bytes: number;
  hard_limit_bytes?: number;
  use_gitignore: boolean;
  trace: { enabled: boolean; paused?: boolean };
  auto_rebuild: { enabled: boolean; debounce_ms?: number };
  graph_engine?: GraphEngineConfig;
}

/**
 * Graph Engine Configuration (Auto-run toggles)
 */
export interface GraphEngineConfig {
  stages: {
    trace: { auto: boolean };
    vector: { auto: boolean };
    catalogue: { auto: boolean };
    validation: { auto: boolean };
    epistemic: { auto: boolean };
    clustering: { auto: boolean };
    knowledge: { auto: boolean };
  };
}

/**
 * Knowledge Embedding Status (Stage 7)
 */
export interface KnowledgeEmbeddingStatus {
  enabled: boolean;
  running: boolean;
  chunks_embedded: number;
  deep_chunks_embedded?: number;
  last_run_at: string | null;
  progress_current?: number;
  progress_total?: number;
}

/**
 * Full project details
 */
export interface Project {
  id: string;
  name: string;
  path: string;
  mode: ProjectMode;
  config: ProjectConfig;
  created_at: string;
  updated_at: string;
}

/**
 * Build statistics from the last index operation
 */
export interface IndexBuildStats {
  mode: string;
  files_total: number;
  files_reused: number;
  files_embedded: number;
  files_deleted: number;
  chunks_total: number;
  chunks_reused: number;
  chunks_embedded: number;
  lines_scanned?: number;
  lines_indexed?: number;
  files_docs?: number;
  files_code?: number;
  lines_docs?: number;
  lines_code?: number;
}

/**
 * Index status from API
 */
export interface IndexStatus {
  exists: boolean;
  total_chunks: number;
  embedding_dim?: number;
  embedding_model?: string;
  last_build_at: string | null;
  last_error: ApiError | null;
  build?: IndexBuildStats;
}

/**
 * Full project status from API
 */
export interface ProjectStatus {
  building: boolean;
  stale: boolean;
  stale_since?: string | null;
  stale_count?: number;
  index: IndexStatus;
  trace: TraceStatus;
  watch: WatchStatus;
  // Deep Analysis / Graph Engine extensions
  augmentation?: AugmentationStatus; // Stage 3
  epistemic?: EpistemicStatus;       // Stage 5
  modules?: ModuleStatus;            // Stage 6
  deepening?: DeepeningStatus;       // Stage 4+ loop
  knowledge?: KnowledgeEmbeddingStatus; // Stage 7
}

/**
 * Pipeline group run status (Phase 24 SM-6)
 */
export interface PipelineGroupRun {
  project_id: string;
  group: string;
  phase: 'idle' | 'running' | 'completed' | 'failed';
  current_stage: string | null;
  current_stage_index: number;
  total_stages: number;
  started_at: number | null;
  finished_at: number | null;
  error: string | null;
  stage_results: Record<string, string>;
}

/**
 * Full pipeline status (10-stage, two-group model)
 * Matches the backend `PipelineOrchestrator.status()` shape.
 */
export interface PipelineStatus {
  fast_sync: PipelineGroupRun | null;
  deep_enrichment: PipelineGroupRun | null;
  stages: {
    structural: any;
    inferred_edges: any;
    catalogue: any;
    validation: any;
    knowledge: any;
    enrichment: any;
    clustering: any;
    atlas: any;
    deepening: any;
    deep_knowledge: any;
  };
  any_running: boolean;
  /** Phase 25: crashed pipeline runs awaiting user action */
  crashed_runs?: CrashedPipelineRun[];
}

/**
 * A crashed pipeline run detected on daemon startup (Phase 25).
 * The UI should display a banner offering Resume / Discard.
 */
export interface CrashedPipelineRun {
  run_id: string;
  project_id: string;
  group: string;
  status: string;
  stages: string[];
  current_stage: string | null;
  current_stage_index: number;
  started_at: number | null;
  last_heartbeat: number | null;
  error: string | null;
  stage_results: Record<string, string>;
  checkpoint_path: string | null;
  chain_deep: boolean;
}

/**
 * Scope Orchestrator status (Phase 24 SM-8: Knowledge Scope Pipeline)
 * Matches the backend `ScopeOrchestrator.status()` shape.
 */
export interface ScopeStatus {
  project_id?: string;
  state: 'idle' | 'debouncing' | 'building' | 'failed' | 'stale';
  pending_adds: number;
  pending_removes: number;
  pending_changes: number;
  total_pending: number;
  auto_rebuild: boolean;
  debounce_ms: number;
  error: string | null;
  last_rebuild_at: number | null;
  stale_since: number | null;
  is_stale: boolean;
}

/**
 * Unified Graph Engine Status (for the Engine Panel)
 */
export interface GraphEngineStatus {
  stages: {
    trace: TraceStatus & { stats: number };
    vector: IndexStatus & { building: boolean };
    catalogue: AugmentationStatus;
    validation: { enabled: boolean; inferred_edges: number; validated_edges: number };
    epistemic: EpistemicStatus;
    clustering: ModuleStatus;
    knowledge: KnowledgeEmbeddingStatus & { building: boolean; count?: number; last_build_at?: string; model?: string; exists?: boolean };
  };
  deepening: DeepeningStatus;
  global_running: boolean;
}

/**
 * Global UI configuration
 */
export interface GlobalConfig {
  repo_root?: string;
  core_roots?: string[];
  working_roots?: string[];
  include_globs?: string[];
  exclude_globs?: string[];
  max_file_bytes?: number;
  hard_limit_bytes?: number;
  use_gitignore?: boolean;
  trace?: { enabled: boolean };
  auto_rebuild?: { enabled: boolean; debounce_ms?: number };
  llm_config?: LLMConfig;
  deep_analysis?: DeepEnrichmentConfig;
  ui_preferences?: {
    mode?: 'light' | 'dark';
    theme?: string;
    bg_image?: string | null;
  };
  module_layout?: import('./types/layout').DashboardLayout;
}

/**
 * Feature availability from /license endpoint
 */
export interface FeatureAvailability {
  auto_rebuild: boolean;
  auto_trace: boolean;
  trace_index: boolean;
  trace_search: boolean;
  mcp_tools: boolean;
  mcp_trace_expand: boolean;
  path_weights: boolean;
  context_compression: boolean;
  multi_repo_agent: boolean;
  team_config: boolean;
  audit_log: boolean;
  projects_max: number;
}

/**
 * License status from /license endpoint
 */
export interface LicenseStatus {
  license: {
    tier: string;
    valid: boolean;
    email?: string;
    expires_at?: string;
    seats: number;
    features: string[];
  };
  features: FeatureAvailability;
}

/**
 * Per-slot LLM connectivity status from /llm/slots/status
 */
export interface LLMSlotStatus {
  configured: boolean;
  enabled?: boolean;
  model?: string;
  endpoint_id?: string;
  endpoint_url?: string;
  provider?: string;
  source?: string;
  status: 'not_configured' | 'endpoint_missing' | 'unreachable' | 'connected' | 'connected_no_model' | 'local';
  model_available?: boolean;
  error?: string;
}

/**
 * All LLM slot statuses from /llm/slots/status
 */
export interface LLMSlotsStatus {
  embedding: LLMSlotStatus;
  small_model: LLMSlotStatus;
  large_model: LLMSlotStatus;
  code_model: LLMSlotStatus;
}

/**
 * API error structure
 */
export interface ApiError {
  code: string;
  message: string;
  hint?: string;
  details?: Record<string, unknown>;
}

// ============================================================
// Phase 13 - Operational Visibility Types
// ============================================================

/**
 * Log entry from backend event stream
 */
export interface LogEntry {
  timestamp: number;
  level: string;
  logger: string;
  message: string;
  created: number;
}

/**
 * Task progress update from backend event stream
 */
export interface TaskProgress {
  task_id: string;
  message: string;
  current: number;
  total: number;
  percent: number;
  status: 'running' | 'completed' | 'failed';
}
