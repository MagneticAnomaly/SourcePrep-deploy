/**
 * Architecture diagram types — Phase 71A
 *
 * These types define the data model for the interactive architecture diagram.
 * Backend returns ArchGraphResponse; frontend maps to React Flow nodes/edges.
 */

// ── API Response Types ─────────────────────────────────────────────

/** A module in the architecture graph (from module synthesis + trace) */
export interface ArchModule {
  id: string;
  name: string;
  description: string;
  file_count: number;
  member_files: string[];
  hub_files?: string[];
  domain_tags: string[];
  architecture_layers: string[];
  component_status: string;
  avg_confidence: number;
  dependencies: string[];
}

/** A file node in the architecture graph */
export interface ArchFile {
  id: string;
  path: string;
  module_id: string;
  language: string;
  hub_score: number;
  confidence: number;
  summary: string;
  line_count: number;
}

/** An edge between modules or files */
export interface ArchEdge {
  source: string;
  target: string;
  kind: 'imports' | 'calls' | 'inferred';
  count: number;
}

/** Stats about the architecture graph */
export interface ArchStats {
  total_modules: number;
  total_files: number;
  total_edges: number;
  generated_at: string;
}

/** Full response from GET /projects/{id}/architecture/graph */
export interface ArchGraphResponse {
  exists: boolean;
  modules: ArchModule[];
  files: ArchFile[];
  edges: ArchEdge[];
  external_refs: ArchFile[];
  stats: ArchStats;
}

/** Summary response from GET /projects/{id}/architecture/summary */
export interface ArchSummaryResponse {
  exists: boolean;
  module_count: number;
  file_count: number;
  edge_count: number;
  note_count: number;
  last_edited: string | null;
}

// ── Notes ──────────────────────────────────────────────────────────

export type ArchNoteType = 'adr' | 'comment' | 'agent_note';

/** A user or agent annotation attached to a node */
export interface ArchNote {
  id: string;
  node_id: string;
  content: string;
  note_type: ArchNoteType;
  author: string;
  color: string;
  created_at: string;
  updated_at: string;
}

/** Request body for creating a note */
export interface ArchNoteCreate {
  node_id: string;
  content: string;
  note_type: ArchNoteType;
  author?: string;
  color?: string;
}

/** Request body for updating a note */
export interface ArchNoteUpdate {
  content?: string;
  color?: string;
}

// ── Layout Persistence ─────────────────────────────────────────────

/** Saved node position for a specific layer */
export interface ArchNodePosition {
  id: string;
  x: number;
  y: number;
}

/** Saved layout for one drill-down layer */
export interface ArchLayerLayout {
  layer_path: string;
  positions: ArchNodePosition[];
  viewport: { x: number; y: number; zoom: number };
}

/** Full persisted architecture state */
export interface ArchState {
  layouts: Record<string, ArchLayerLayout>;
  module_overrides: Record<string, { name?: string; description?: string }>;
}

// ── Frontend-only types ────────────────────────────────────────────

/** Breadcrumb segment for layer navigation */
export interface ArchBreadcrumb {
  label: string;
  layerPath: string[];
}

/** Node data passed to React Flow custom nodes */
export interface ModuleNodeData {
  label: string;
  description: string;
  fileCount: number;
  hubFiles: string[];
  domainTags: string[];
  componentStatus: string;
  confidence: number;
  noteCount: number;
  isHub: boolean;
}

export interface FileNodeData {
  label: string;
  path: string;
  language: string;
  hubScore: number;
  confidence: number;
  summary: string;
  lineCount: number;
  noteCount: number;
  isHub: boolean;
}

export interface ExternalRefNodeData {
  label: string;
  moduleId: string;
  description: string;
}

export interface AnnotationNodeData {
  noteId: string;
  content: string;
  noteType: ArchNoteType;
  author: string;
  color: string;
  onEdit?: (noteId: string, content: string) => void;
  onDelete?: (noteId: string) => void;
}

// ── ACRs (Phase B) ────────────────────────────────────────────────

export type ACRStatus = 'proposed' | 'approved' | 'in_progress' | 'completed' | 'rejected';

/** Architecture Change Request */
export interface ACR {
  id: string;
  title: string;
  description: string;
  status: ACRStatus;
  source_type: 'agent' | 'user' | 'audit';
  source_agent: string;
  affected_nodes: string[];
  paperclip_issue_id?: string;
  created_at: string;
  approved_at?: string;
}

/** Request body for creating an ACR */
export interface ACRCreate {
  title: string;
  description: string;
  source_type: 'agent' | 'user' | 'audit';
  source_agent: string;
  affected_nodes: string[];
}

// ── Issue Linking (Phase B) ───────────────────────────────────────

export type IssuePriority = 'P0' | 'P1' | 'P2' | 'P3';
export type IssueStatus = 'open' | 'in_progress' | 'closed';

/** A Paperclip issue linked to a diagram node */
export interface LinkedIssue {
  paperclip_issue_id: string;
  title: string;
  priority: IssuePriority;
  status: IssueStatus;
  node_id: string;
}

/** Request body for linking an issue to a node */
export interface LinkIssueRequest {
  paperclip_issue_id: string;
  title: string;
  priority: IssuePriority;
  status: IssueStatus;
}

// ── Entry Point Node (Phase B) ────────────────────────────────────

export interface EntryPointNodeData {
  label: string;
  path: string;
  entryType: 'api_route' | 'cli_command' | 'main' | 'webhook';
  noteCount: number;
}
