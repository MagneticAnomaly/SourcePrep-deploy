export { ApiClientError } from './errors';
export { PrepApiClient, createPrepApiClient } from './client';
export type { ApiClient, ApiClientConfig, FileTreeNode } from './client';
export { MockApiClient } from './mock';
export { ApiClientProvider, useApiClient } from './react';
export type {
  ApiEnvelope,
  AssembleContextRequest,
  AssembleContextResponse,
  AssembleContextResponseStructured,
  AssembleContextResponseText,
  BuildProjectResponse,
  CreateProjectRequest,
  CreateProjectResponse,
  DeleteProjectResponse,
  ListProjectsResponse,
  ProjectListItem,
  SearchRequest,
  SearchResponse,
  StructuredContextChunk,
  UpdateProjectRequest,
  UpdateProjectResponse,
  WatchActionResponse,
} from './types';
