// ── Types for the VS Code extension ──
// Lightweight subset of @prep/ui types, avoiding React dependency.

export type LicenseTier = 'free' | 'starter' | 'pro' | 'team' | 'enterprise';

export interface FeatureAvailability {
  auto_rebuild: boolean;
  auto_trace: boolean;
  trace_index: boolean;
  trace_search: boolean;
  mcp_tools: boolean;
  mcp_trace_expand: boolean;
  path_weights: boolean;
  prep-compress_compression: boolean;
  multi_repo_agent: boolean;
  team_config: boolean;
  audit_log: boolean;
  projects_max: number;
}

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

export interface ProjectListItem {
  id: string;
  name: string;
  path: string;
  mode: 'standalone' | 'embedded' | 'custom';
  created_at: string;
  updated_at: string;
  config?: ProjectConfig;
}

export interface ProjectConfig {
  include_globs: string[];
  exclude_globs: string[];
  max_file_bytes: number;
  trace: { enabled: boolean };
  auto_rebuild: { enabled: boolean; debounce_ms?: number };
}

export interface IndexStatus {
  exists: boolean;
  total_chunks: number;
  embedding_dim?: number;
  embedding_model?: string;
  last_build_at: string | null;
  last_error: ApiError | null;
}

export interface TraceStatus {
  enabled: boolean;
  exists: boolean;
  building: boolean;
  counts: { nodes: number; edges: number };
  last_build_at: string | null;
  last_error: string | null;
  engine?: string;
}

export type WatchState = 'disabled' | 'idle' | 'debouncing' | 'building' | 'throttled';

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

export interface ProjectStatus {
  building: boolean;
  stale: boolean;
  index: IndexStatus;
  trace: TraceStatus;
  watch: WatchStatus;
}

export interface SearchResult {
  chunk_id: string;
  source_path: string;
  span: { start_line: number; end_line: number };
  preview: string;
  score: number;
  content?: string;
}

export interface FileTreeNode {
  name: string;
  type: 'file' | 'folder';
  children?: FileTreeNode[];
}

export interface ApiEnvelope<T> {
  success: boolean;
  data: T | null;
  error: ApiError | null;
}

export interface ApiError {
  code: string;
  message: string;
  hint?: string;
  details?: Record<string, unknown>;
}

export interface HealthResponse {
  status: string;
  version: string;
}
