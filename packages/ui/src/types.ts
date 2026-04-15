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
  | 'paused'     // User/system paused — resumable
  | 'cancelled'  // User cancelled — terminal
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
/**
 * Project activity status (Phase 97)
 * - active: full functionality
 * - inactive: Pro explicit deactivation (manual-only)
 * - locked: archived or over Free tier limit
 */
export type ActivityStatus = 'active' | 'inactive' | 'locked';

export type PriorityLevel = 'none' | 'boost' | 'exclusive';

export interface ProjectSummary {
  id: string;
  name: string;
  path: string;
  mode: ProjectMode;
  status: StatusState;
  chunk_count?: number;
  last_build_at?: string;
  activity_status?: ActivityStatus;
  /** @deprecated Use priority_level instead */
  is_starred?: boolean;
  priority_level?: PriorityLevel;
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
  debounce_ms: number;
  stale: boolean;
  stale_since: string | null;
  pending: boolean;
  pending_paths_count: number;
  next_rebuild_at: string | null;
  last_event_at: string | null;
  last_rebuild_at: string | null;
}

/**
 * Team remote sync status from API (Phase 06)
 */
export interface SyncStatus {
  enabled: boolean;
  last_sync_at: number | null;
  last_sync_commit: string;
  remote_version: number | null;
  remote_timestamp: number | null;
  is_syncing: boolean;
  behind_minutes: number | null;
  error: string | null;
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
  slot_progress?: { message: string; current: number; total: number; baseline?: number };
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
  progress_current?: number;
  progress_total?: number;
  progress_baseline?: number;
}

/**
 * Epistemic enrichment status (Pass 2)
 */
export interface EpistemicStatus {
  enabled: boolean;
  enriched_nodes: number;
  total_file_nodes?: number;
  /** Total nodes of all kinds (files + functions + classes etc) — matches enrichment scope */
  total_nodes?: number;
  avg_confidence: number;
  running: boolean;
  /** True when ANY deep enrichment stage (5-8) is active (for DeepCoverageBar) */
  pipeline_running?: boolean;
  progress_current?: number;
  progress_total?: number;
  progress_baseline?: number;
  /** F-76: Baseline count persisted in the manifest, used for two-tone
   * progress bars across page refresh and daemon restart. */
  incremental_baseline?: number;
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
  progress_baseline?: number;
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
  /** Live slot progress fields (populated when running). Enables the
   *  two-tone incremental progress bar instead of plain "blue running". */
  progress_current?: number;
  progress_total?: number;
  progress_baseline?: number;
}

/**
 * Per-segment metadata for the sub-atlas tree (Phase 104).
 */
export interface AtlasSegmentStatus {
  segment_id: string;
  segment_name: string;
  dir_path: string;
  file_count: number;
  char_count: number;
  mode?: 'llm' | 'structural';
  generated_at?: string;
  stale?: boolean;
  /** Full rendered segment content. Sent inline on GET /atlas so the
   *  sub-atlas tree can preview a segment without a second round trip. */
  content?: string;
}

/**
 * Shape of a RoleVector for the `applied_role` field on atlas responses
 * (Phase 104). Matches RoleVector.to_dict() from role_vectors.py.
 */
export interface RoleVectorPayload {
  role_id: string;
  display_name: string;
  layer_weights: Record<string, number>;
  domain_affinity: string[];
  centrality_weight: number;
  detail_level: number;
  max_chars: number;
}

/**
 * Persistent per-role override layered on top of the built-in RoleVector
 * (Phase 104). Unset fields fall through to the built-in defaults.
 */
export interface RoleOverride {
  role_id: string;
  max_chars?: number | null;
  pinned_concept_ids: string[];
  updated_at: number;
}

/**
 * Codebase Atlas status (Phase 29, extended for Phase 104 sub-atlases)
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
  segments?: AtlasSegmentStatus[];
  routing?: boolean;
  running?: boolean;
  /** Phase 64A — role-filtered sub-atlas, when ?role= is supplied */
  role?: string;
  role_atlas?: string;
  role_atlas_chars?: number;
  role_atlas_error?: string;
  /** Phase 104 — effective role vector after any override is merged in */
  applied_role?: RoleVectorPayload;
  /** Phase 104 — the override that was applied, or null */
  override?: RoleOverride | null;
}

// ============================================================
// Phase 96 - Finalize Stage Status Types
// ============================================================

/** Stage 12: Rules file generation status */
export interface RulesStatus {
  generated: boolean;
  stale: boolean;
  mode?: string;
  atlas_chars?: number;
}

/** Stage 13: Concept seeding status */
export interface ConceptsStatus {
  seeded: boolean;
  count: number;
  questions?: number;
}

/** Stage 14: Structural audit status */
export interface AuditPipelineStatus {
  exists: boolean;
  finding_count: number;
  tier2?: boolean;
}

/** Stage 15: Antibody derivation status */
export interface AntibodiesStatus {
  count: number;
  firing?: number;
}

// ============================================================
// Phase 49 - Process Metadata & Data Provenance
// ============================================================

/**
 * Per-stage provenance metadata — which model produced this data, when, and how well.
 */
export interface StageProvenance {
  stage_id: string;
  model?: string;
  provider?: string;
  generated_at?: string;
  age_days?: number;
  elapsed_seconds?: number;
  codrag_version?: string;
  quality?: {
    avg_confidence?: number;
    success_rate?: number;
    total_items?: number;
  };
  /** Present when multiple models contributed to this stage (mid-stage model swap) */
  model_breakdown?: {
    model: string;
    count: number;
    percentage: number;
    avg_confidence?: number;
  }[];
}

/**
 * Full pipeline provenance response from GET /projects/{id}/pipeline/provenance
 */
export interface PipelineProvenance {
  current_data: Record<string, StageProvenance>;
  last_run?: Record<string, unknown>;
  oldest_data_age_days?: number;
  staleness_warning?: boolean;
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

export type UserRole = 'user' | 'admin';


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
// Phase 44 - LLM Mapping Types
// ============================================================

/**
 * Canonical task IDs for LLM assignment (Phase 44).
 * Each represents an atomic execution point that requires an LLM.
 */
export type CodragTaskId =
  | 'catalogue'
  | 'inferred_edges'
  | 'enrichment'
  | 'group_reasoning'
  | 'clustering'
  | 'atlas'
  | 'deepening'
  | 'search_intent'
  | 'audit'
  | 'augmentation';

export const ALL_TASK_IDS: CodragTaskId[] = [
  'inferred_edges', 'catalogue', 'enrichment', 'group_reasoning', 'clustering',
  'atlas', 'deepening', 'search_intent', 'audit', 'augmentation',
];

export const TASK_LABELS: Record<CodragTaskId, string> = {
  catalogue: 'Catalogue Summarization',
  inferred_edges: 'Inferred Edge Discovery',
  enrichment: 'Deep Reasoning',
  group_reasoning: 'Group Reasoning',
  clustering: 'Module Synthesis',
  atlas: 'Atlas Generation',
  deepening: 'Deepening Loop',
  search_intent: 'Search Preprocessing',
  audit: 'Automated Audits',
  augmentation: 'Trace Augmentation',
};

export const TASK_TAGS: Record<CodragTaskId, string> = {
  inferred_edges: 'Code',
  catalogue: 'Fast',
  search_intent: 'Fast',
  augmentation: 'Fast',
  enrichment: 'Reasoning (optional)',
  group_reasoning: 'Reasoning (recommended)',
  clustering: 'Reasoning (optional)',
  atlas: 'Reasoning (optional)',
  deepening: 'Reasoning (optional)',
  audit: 'Reasoning (optional)',
};

export type CloudPreference = 'local-preferred' | 'cloud-preferred' | 'neutral';

export const TASK_CLOUD_PREF: Record<CodragTaskId, CloudPreference> = {
  catalogue: 'local-preferred',
  search_intent: 'local-preferred',
  augmentation: 'local-preferred',
  inferred_edges: 'neutral',
  enrichment: 'neutral',
  group_reasoning: 'cloud-preferred',
  clustering: 'neutral',
  atlas: 'cloud-preferred',
  deepening: 'cloud-preferred',
  audit: 'cloud-preferred',
};

/**
 * LLM assignment mode (Phase 44)
 */
export type AssignmentMode = 'structured' | 'mapped';

/**
 * A single LLM assignment block in Mapped mode (Phase 44).
 * Groups one model with one or more tasks.
 */
export interface LLMAssignmentBlock {
  id: string;
  endpoint_id: string;
  model: string;
  tasks: CodragTaskId[];
  enable_reasoning?: boolean;
  always_on?: boolean;
  /** Per-model LLM concurrency (1 or 2). Default: 1. Only for local endpoints. */
  concurrency?: number;
}

// ============================================================
// LLM Configuration Types (AI Models Settings)
// ============================================================

/**
 * Provider types for LLM endpoints
 */
export type LLMProvider = 'ollama' | 'openai' | 'openai-compatible' | 'lm-studio' | 'anthropic' | 'google';

/**
 * Model source for embedding
 */
export type ModelSource = 'endpoint' | 'huggingface';

/**
 * Saved endpoint configuration
 */

export type ComputeHardwareProfile = 'apple_silicon' | 'nvidia' | 'amd' | 'intel' | 'cloud';

export interface ComputeNode {
  id: string;
  name: string;
  type: 'local' | 'remote' | 'cloud';
  hardware_profile?: ComputeHardwareProfile;
  max_concurrent: number;
  gpu_name?: string;
  gpu_vram_gb?: number;
  endpoint_ids: string[];
}

export interface SavedEndpoint {
  id: string;
  name: string;
  provider: LLMProvider;
  url: string;
  api_key?: string;
  compute_node_id?: string | null;
  /** Max concurrent local model requests (VRAM-bound). Default: 1. */
  local_concurrency?: number;
  /** Max concurrent cloud-proxied model requests (rate-limit-bound). Default: 1. */
  cloud_concurrency?: number;
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
  always_on?: boolean;
  /** Per-model LLM concurrency (1 or 2). Default: 1. Only for local endpoints. */
  concurrency?: number;
}

/**
 * Full LLM configuration
 */
export interface LLMConfig {
  assignment_mode?: AssignmentMode;
  embedding: EmbeddingConfig;
  small_model: LLMSlotConfig;
  large_model: LLMSlotConfig;
  code_model: LLMSlotConfig;
  /**
   * Optional Swarm Coordinator model. When unset (or `inherit_from_large`),
   * the swarm orchestrator falls back to `large_model` for planning/synthesis.
   */
  coordinator_model?: LLMSlotConfig & { inherit_from_large?: boolean };
  saved_endpoints: SavedEndpoint[];
  compute_nodes?: ComputeNode[];
  assignment_blocks?: LLMAssignmentBlock[];
  /** Cached context window sizes keyed by model name, auto-populated when models are fetched. */
  model_context_cache?: Record<string, number>;
}

/**
 * Model slot type for UI
 */
export type ModelSlotType = 'embedding' | 'small' | 'large' | 'code' | 'coordinator';

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
  warnings?: string[];
  recommendations?: Record<string, any>;
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
  activation_method?: string;
}

/**
 * Project configuration
 */
export interface ProjectConfig {
  include_globs: string[];
  exclude_globs: string[];
  max_file_bytes: number;
  active?: boolean;  // Pro tier: explicit active/inactive toggle (default true)
  /** @deprecated Use priority_level instead */
  is_starred?: boolean;
  priority_level?: PriorityLevel;
  hard_limit_bytes?: number;
  use_gitignore: boolean;
  trace: { enabled: boolean; paused?: boolean; ignore_patterns?: string[] };
  auto_rebuild: { enabled: boolean; debounce_ms?: number };
  graph_engine?: GraphEngineConfig;
  advanced?: ProjectAdvancedConfig;
  max_branch_backups?: number; // Phase 60B
  /** F-65: Per-project Auto/Manual/Sched state for pipeline groups */
  auto_config?: { fastSync?: boolean; deepEnrichment?: string; finalize?: string };
  /** F-56: Per-project deep analysis schedule */
  deep_analysis_schedule?: Record<string, unknown>;
}

/**
 * Per-project advanced trace limits
 */
export interface ProjectAdvancedConfig {
  max_files?: number;
  max_nodes?: number;
  max_edges?: number;
}

/**
 * Global advanced configuration (pipeline + chunking)
 */
export interface AdvancedConfig {
  checkpoint_interval: number;
  min_edge_confidence: number;
  chunk_max_chars: number;
  chunk_overlap_chars: number;
  md_chunk_max_chars: number;
  md_chunk_min_chars: number;
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
  progress_baseline?: number;
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
  activity_status?: ActivityStatus;
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
  sync?: SyncStatus;
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
  phase: 'idle' | 'queued' | 'running' | 'pausing' | 'paused' | 'cancelling' | 'cancelled' | 'completed' | 'failed' | 'recovering';
  current_stage: string | null;
  current_stage_index: number;
  total_stages: number;
  started_at: number | null;
  finished_at: number | null;
  error: string | null;
  stage_results: Record<string, string>;
  is_queued?: boolean;
}

/**
 * Full pipeline status (11-stage, two-group model)
 * Matches the backend `PipelineOrchestrator.status()` shape.
 *
 * Stage order:
 *   Fast Sync:       structural → inferred_edges → catalogue → validation → knowledge
 *   Deep Enrichment: enrichment → group_reasoning → clustering → atlas → deepening → deep_knowledge
 */
/**
 * Phase 66: Pi Agent gate status
 */
export interface AgentGateStatus {
  agent_active: boolean;
  active_task: string | null;
  held_for_s: number | null;
}

/**
 * Phase 66: Pi Agent status from pipeline status API
 */
export interface AgentStatus {
  enabled: boolean;
  auto_scan?: boolean;
  cooldown_seconds?: number;
  running_task: string | null;
  last_scan_at: string | null;
  last_scan_delta?: {
    new_findings: Array<{ title: string; severity: string }>;
    resolved_findings: Array<{ title: string; severity: string }>;
    unchanged_count: number;
    is_first_scan?: boolean;
  } | null;
  gate?: AgentGateStatus;
}

export interface PipelineStatus {
  fast_sync: PipelineGroupRun | null;
  deep_enrichment: PipelineGroupRun | null;
  finalize: PipelineGroupRun | null;
  stages: {
    structural: any;
    inferred_edges: any;
    catalogue: any;
    validation: any;
    knowledge: any;
    enrichment: any;
    group_reasoning: any;
    clustering: any;
    deepening: any;
    deep_knowledge: any;
    atlas: any;
    rules: RulesStatus;
    concepts: ConceptsStatus;
    audit: AuditPipelineStatus;
    antibodies: AntibodiesStatus;
  };
  any_running: boolean;
  /** Phase 25: crashed pipeline runs awaiting user action */
  crashed_runs?: CrashedPipelineRun[];
  /** Phase 45D: scheduler status — compute node loads and queues */
  scheduler?: SchedulerStatus | null;
  /** Phase 66: Pi agent status and gate state */
  agent?: AgentStatus | null;
  /** Phase 60B: Branch-aware backups */
  branch?: string | null;
  branch_snapshots?: any[];
  branch_state?: any | null;
}

/**
 * Scheduler status for a single compute node (Phase 45D)
 */
export interface SchedulerNodeStatus {
  max_concurrent: number;
  current_load: number;
  active: Record<string, string>;  // project_id -> stage_id
  queued: Array<{
    project_id: string;
    stage: string;
    waiting_seconds: number;
  }>;
}

/**
 * Full pipeline scheduler status (Phase 45D)
 */
export interface SchedulerStatus {
  nodes: Record<string, SchedulerNodeStatus>;
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
  max_active_projects?: number | 'infinite';
  llm_config?: LLMConfig;
  deep_analysis?: DeepEnrichmentConfig;
  ui_preferences?: {
    mode?: 'light' | 'dark';
    theme?: string;
    bg_image?: string | null;
  };
  /** Phase 98: per-group collapse state for GraphEnrichmentPipeline.
   *  All three default to `true` (collapsed) when absent. */
  pipeline_ui?: {
    fast_collapsed?: boolean;
    deep_collapsed?: boolean;
    finalize_collapsed?: boolean;
  };
  module_layout?: import('./types/layout').DashboardLayout;
  developer_debug_mode?: boolean;
  developer_show_dev_panels?: boolean;
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
  /** @deprecated LOD compression is always-on */
  context_compression?: boolean;
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
    activation_method?: string;
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
 * Per-block connectivity status for mapped mode from /llm/slots/status
 */
export interface LLMBlockStatus {
  id: string;
  configured: boolean;
  status: 'not_configured' | 'endpoint_missing' | 'unreachable' | 'connected' | 'connected_no_model';
  model?: string;
  endpoint_id?: string;
  endpoint_url?: string;
  provider?: string;
  endpoint_name?: string;
  tasks: CodragTaskId[];
  model_available?: boolean;
  error?: string;
}

/**
 * A currently-running pipeline task with project context
 */
export interface RunningTask {
  task_id: CodragTaskId;
  project_id: string;
  project_name: string;
  group: string;
  stage: string;
  model_slot?: 'small' | 'large' | 'code' | 'coordinator' | null;
  /** How many parallel LLM calls this stage makes (from scheduler budget) */
  concurrent_workers?: number;
  /** Which compute node this project is running on (e.g. "cloud:default_ollama") */
  compute_node?: string | null;
  /** Whether this stage is running in swarm mode (coordinator → fan-out → synthesis) */
  is_swarm?: boolean;
}

/**
 * All LLM slot statuses from /llm/slots/status
 */
export interface LLMSlotsStatus {
  assignment_mode?: AssignmentMode;
  running_task_id?: CodragTaskId | null;
  running_tasks?: RunningTask[];
  embedding: LLMSlotStatus;
  small_model: LLMSlotStatus;
  large_model: LLMSlotStatus;
  code_model: LLMSlotStatus;
  coordinator_model?: LLMSlotStatus;
  assignment_blocks?: LLMBlockStatus[];
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

// ============================================================
// Phase 43 - AutoAudit Types
// ============================================================

export type AuditSeverity = 'critical' | 'warning' | 'info' | 'suggestion';
export type AuditCategory = 'size' | 'architecture' | 'quality' | 'coverage' | 'naming' | 'testing';

export interface AuditConfig {
  auto_run_after_deep: boolean;
  auto_synthesize: boolean;
  large_file_threshold_bytes: number;
  large_file_warning_bytes: number;
  hub_z_threshold: number;
  similarity_threshold: number;
}

export type AuditPriority = 'P0' | 'P1' | 'P2' | 'P3' | 'P4';
export type AuditEffort = 'small' | 'medium' | 'large';

export interface AuditFinding {
  analyzer: string;
  severity: AuditSeverity;
  category: AuditCategory;
  title: string;
  description: string;
  file_paths: string[];
  evidence: Record<string, unknown>;
  suggested_action: string;
  finding_id: string;
  priority: AuditPriority;
  effort: AuditEffort;
}

export interface AuditStatus {
  running: boolean;
  error: string | null;
  has_results: boolean;
  finding_count?: number;
  severity_counts?: Record<AuditSeverity, number>;
  last_run?: {
    generated_at: string;
    graph_node_count: number;
    graph_edge_count: number;
    finding_count: number;
    document_count: number;
    analyzers_run: string[];
    documents: string[];
  };
}

export interface AuditReport {
  name: string;
  filename: string;
  size_bytes: number;
}

// ── Phase 52: Spaghetti Finder Types ─────────────────────────────────

export interface SpaghettiFileScore {
  file_path: string;
  score: number;
  severity: 'critical' | 'warning' | 'info';
  estimated_lines: number;
  fan_in: number;
  fan_out: number;
  symbol_count: number;
  tech_debt_count: number;
  tech_debt_items?: string[];
  epistemic_confidence?: number;
  in_circular?: boolean;
  language: string;
  role: string;
  module_name: string;
  summary?: string;
  signals?: Record<string, number>;
}

export interface SpaghettiResult {
  file_count: number;
  scored_count: number;
  severity_counts: Record<string, number>;
  duration_ms: number;
  tab: string;
  files: SpaghettiFileScore[];
}

export type SpaghettiTab = 'worst' | 'long' | 'coupling' | 'debt';

// ── EA-C1: Admin Policy Types ────────────────────────────────────────

export interface ProviderPolicy {
  allowed_providers: string[];
  blocked_providers: string[];
  allow_local_providers: boolean;
  allow_user_endpoints: boolean;
  allow_user_api_keys: boolean;
  locked_endpoints: Array<Record<string, any>>;
}

export interface ModelPolicy {
  allowed_models: string[];
  blocked_models: string[];
  require_approved_models: boolean;
  allow_any_local_model: boolean;
  slot_overrides?: Record<string, {
    allowed_models?: string[];
    blocked_models?: string[];
    require_approved_models?: boolean;
  }>;
}

export interface DataPolicy {
  never_send_globs: string[];
  redact_patterns: string[];
  block_unapproved_cloud: boolean;
  allowed_destinations: string[];
}

export interface SyncPolicy {
  require_s3_https: boolean;
  allowed_s3_endpoints: string[];
}

export interface NetworkPolicy {
  block_metadata_endpoints: boolean;
  allowed_ports: number[];
}

export interface BudgetPolicy {
  monthly_token_limit: number;
  monthly_cost_limit_usd: number;
  alert_threshold_percent: number;
}

export interface AdminPolicy {
  provider: ProviderPolicy;
  model: ModelPolicy;
  data: DataPolicy;
  sync: SyncPolicy;
  network: NetworkPolicy;
  budgets: BudgetPolicy;
  enforcement_mode: 'suggest' | 'enforce';
}

// ── Phase 57: Goalposts Types ────────────────────────────────────────

export type GoalpostCategory = 'architecture' | 'security' | 'feature' | 'tech_debt' | 'research';
export type GoalpostState = 'proposed' | 'approved' | 'dismissed' | 'refined';

export interface GoalpostTask {
  description: string;
  file_paths: string[];
  effort: 'small' | 'medium' | 'large';
}

export interface GoalpostProposal {
  id: string;
  title: string;
  rationale: string;
  category: GoalpostCategory;
  state: GoalpostState;
  tasks: GoalpostTask[];
  priority: string;
  created_at: string;
  decided_at: string;
}

export interface GoalpostQuestion {
  id: string;
  question: string;
  context: string;
  category: GoalpostCategory;
  answered: boolean;
  answer: string;
  created_at: string;
}

export interface GoalpostsResponse {
  generating: boolean;
  error: string | null;
  ready: boolean;
  has_atlas: boolean;
  has_audit: boolean;
  has_intent: boolean;
  missing: string[];
  product_intent: string;
  proposals: GoalpostProposal[];
  questions: GoalpostQuestion[];
  last_generated_at: string;
  model_used: string;
  generation_tokens: number;
  generation_duration_ms: number;
  version: number;
}

// ── Phase 59: Roadmap Types ──────────────────────────────────────

export type RoadmapTier = 'completed' | 'active' | 'planned' | 'proposed';
export type RoadmapNodeSource = 'manual' | 'ai_proposed' | 'todo_scan' | 'github';
export type RoadmapNodeState = 'proposed' | 'accepted' | 'active' | 'completed' | 'dismissed';

export interface RoadmapTask {
  description: string;
  file_paths: string[];
  effort: 'small' | 'medium' | 'large';
}

export interface RoadmapNode {
  id: string;
  title: string;
  description: string;
  tier: RoadmapTier;
  position: number;
  source: RoadmapNodeSource;
  source_ref: string | null;
  category: string;
  priority: string;
  tasks: RoadmapTask[];
  state: RoadmapNodeState;
  parent_id: string | null;
  fork_label: string | null;
  created_at: string;
  decided_at: string | null;
  completed_at: string | null;
  ethos_alignment: string;
  business_impact: string;
}

export interface RoadmapNorthStar {
  id: string;
  title: string;
  priority: string;
}

export interface RoadmapResponse {
  generating: boolean;
  scanning: boolean;
  error: string | null;
  north_star: RoadmapNorthStar | null;
  version: number;
  app_ethos: string;
  nodes: RoadmapNode[];
  questions: GoalpostQuestion[];
  last_generated_at: string;
  model_used: string;
  generation_tokens: number;
  generation_duration_ms: number;
  github_sync: GitHubSyncState | null;
  last_mined_at?: string;
  mining_stats?: Record<string, number> | null;
}

/** GitHub sync metadata (Phase 59D) */
export interface GitHubSyncState {
  last_synced_at: string;
  issues_imported: number;
  owner: string;
  repo: string;
  project_id: string;
  error: string;
}

/** GitHub connection status response */
export interface GitHubStatus {
  configured: boolean;
  owner: string;
  repo: string;
  has_project_id: boolean;
  syncing: boolean;
  error: string | null;
  last_sync: GitHubSyncState | null;
}

/** Velocity snapshot for a sprint window (Phase 59D-4) */
export interface VelocitySnapshot {
  window_start: string;
  window_end: string;
  window_label: string;
  duration_days: number;
  completed_count: number;
  completed_nodes: string[];
  added_count: number;
  p0_completed: number;
  p1_completed: number;
  categories: Record<string, number>;
}

/** Burndown data point (Phase 59D-4) */
export interface BurndownPoint {
  date: string;
  remaining: number;
  completed: number;
}

/** Velocity response from GET /roadmap/velocity */
export interface VelocityResponse {
  average_velocity: number;
  snapshots: VelocitySnapshot[];
  burndown: BurndownPoint[];
  total_completed: number;
  total_active: number;
  total_planned: number;
  total_proposed: number;
}

/** Sprint suggestion from POST /roadmap/suggest-sprint */
export interface SprintSuggestion {
  sprint_label: string;
  capacity: number;
  suggested_nodes: string[];
  rationale: string;
  confidence: number;
  node_details: Array<{
    id: string;
    title: string;
    priority: string;
    category: string;
    tier: string;
  }>;
}

/** Push to GitHub result */
export interface PushGitHubResult {
  pushed: number;
  errors: number;
  results: Array<{
    node_id: string;
    issue_number?: number;
    url?: string;
    html_url?: string;
    error?: string;
  }>;
}

/** Webhook event result */
export interface WebhookResult {
  action: string;
  node_id: string;
  old_tier: string;
  new_tier: string;
  created: boolean;
}
