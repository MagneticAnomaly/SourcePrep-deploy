import type {
  ApiError,
  LLMStatus,
  Project,
  ProjectStatus,
  SearchResult,
  TraceExpandOptions,
  TraceStatus,
} from '../types';

export interface ApiEnvelope<T> {
  success: boolean;
  data: T | null;
  error: ApiError | null;
}

export type ProjectListItem = Pick<
  Project,
  'id' | 'name' | 'path' | 'mode' | 'created_at' | 'updated_at' | 'activity_status'
> & {
  config?: Project['config'];
};

export interface ListProjectsResponse {
  projects: ProjectListItem[];
  total: number;
}

export interface SearchRequest {
  query: string;
  k?: number;
  min_score?: number;
}

export interface SearchResponse {
  results: SearchResult[];
}

export interface AssembleContextRequest {
  query: string;
  k?: number;
  max_chars?: number;
  min_score?: number;
  include_sources?: boolean;
  include_scores?: boolean;
  structured?: boolean;
  include_atlas?: boolean;
  trace_expand?: TraceExpandOptions;
  compression?: 'none' | 'lod' | 'lingua' | 'auto';
}

export interface StructuredContextChunk {
  chunk_id?: string;
  source_path: string;
  span?: { start_line: number; end_line: number };
  score?: number;
  text?: string;
  lod?: number;
  compression_ratio?: number;
  truncated?: boolean;
}

export interface AssembleContextResponseText {
  context: string;
}

export interface AssembleContextResponseStructured {
  context: string;
  chunks: StructuredContextChunk[];
  total_chars?: number;
  estimated_tokens?: number;
}

export type AssembleContextResponse =
  | AssembleContextResponseText
  | AssembleContextResponseStructured;

// ── Project CRUD ──────────────────────────────────────────

export interface CreateProjectRequest {
  path: string;
  name?: string;
  mode?: 'standalone' | 'embedded' | 'custom';
  index_path?: string;
}

export interface CreateProjectResponse {
  project: ProjectListItem;
}

export interface UpdateProjectRequest {
  name?: string;
  config?: Partial<{
    include_globs: string[];
    exclude_globs: string[];
    max_file_bytes: number;
    hard_limit_bytes?: number;
    use_gitignore?: boolean;
    active?: boolean;
    trace: { enabled: boolean; paused?: boolean };
    auto_rebuild: { enabled: boolean; debounce_ms?: number };
    graph_engine?: any;
    advanced?: any;
  }>;
  touch?: boolean;
}

export interface UpdateProjectResponse {
  project: ProjectListItem;
}

export interface DeleteProjectResponse {
  removed: boolean;
  purged: boolean;
}

// ── Build ─────────────────────────────────────────────────

export interface BuildProjectResponse {
  started: boolean;
  building: boolean;
  build_id?: string;
}

// ── Watch ─────────────────────────────────────────────────

export interface WatchActionResponse {
  enabled: boolean;
  state: string;
}

export type { ProjectStatus, TraceStatus, LLMStatus };
