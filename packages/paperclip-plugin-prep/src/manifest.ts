/**
 * SourcePrep Paperclip Plugin Manifest
 */
import type { PaperclipPluginManifestV1 } from '@paperclipai/plugin-sdk';

const manifest: PaperclipPluginManifestV1 = {
  id: 'prep',
  apiVersion: 1,
  version: '0.1.0',
  displayName: 'SourcePrep Codebase Intelligence',
  description:
    'Gives every Paperclip agent structural codebase knowledge — module maps, ' +
    'dependency graphs, semantic search, and health analysis powered by SourcePrep.',
  author: 'SourcePrep <hello@sourceprep.io>',
  categories: ['connector'],

  capabilities: [
    'agent.tools.register',
    'projects.read',
    'issues.read',
    'agents.read',
    'events.subscribe',
    'jobs.schedule',
    'http.outbound',
    'plugin.state.read',
    'plugin.state.write',
    'ui.dashboardWidget.register',
    'ui.detailTab.register',
    'ui.page.register',
  ],

  entrypoints: {
    worker: 'dist/worker.js',
    ui: 'dist/ui/',
  },

  instanceConfigSchema: {
    type: 'object',
    properties: {
      daemon_url: {
        type: 'string',
        description: 'SourcePrep daemon base URL',
        default: 'http://127.0.0.1:8400',
      },
      project_id: {
        type: 'string',
        description: 'Default SourcePrep project ID (auto-detected if empty)',
        default: '',
      },
      auto_context: {
        type: 'boolean',
        description: 'Automatically attach SourcePrep context to new issues',
        default: true,
      },
    },
    required: ['daemon_url'],
  },

  tools: [
    {
      name: 'context',
      displayName: 'Codebase Context',
      description: 'Structural overview: modules, hub files, atlas. Call at the start of every task.',
      parametersSchema: {
        type: 'object',
        properties: {
          role: { type: 'string', description: 'Optional role slug for scoped context' },
        },
      },
    },
    {
      name: 'search',
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
    {
      name: 'impact',
      displayName: 'Impact Analysis',
      description: 'Analyze dependencies and dependents of a file. Use before modifying files.',
      parametersSchema: {
        type: 'object',
        properties: {
          file: { type: 'string', description: 'File path to analyze' },
        },
        required: ['file'],
      },
    },
    {
      name: 'audit',
      displayName: 'Codebase Audit',
      description: 'Get codebase health findings — tech debt, architecture issues, opportunities.',
      parametersSchema: {
        type: 'object',
        properties: {
          categories: { type: 'array', items: { type: 'string' }, description: 'Filter by categories' },
        },
      },
    },
    {
      name: 'observe',
      displayName: 'Save Observation',
      description: 'Save a cross-session observation for future reference.',
      parametersSchema: {
        type: 'object',
        properties: {
          content: { type: 'string', description: 'Observation text' },
          file_path: { type: 'string', description: 'Related file path' },
          category: { type: 'string', description: 'note, decision, bug, pattern, assumption' },
        },
        required: ['content'],
      },
    },
  ],

  ui: {
    slots: [
      {
        type: 'dashboardWidget',
        id: 'codebase-health',
        displayName: 'Codebase Health',
        exportName: 'CodebaseHealthWidget',
      },
      {
        type: 'detailTab',
        id: 'knowledge-scope',
        displayName: 'Knowledge Scope',
        exportName: 'KnowledgeScopeTab',
        entityTypes: ['agent'],
      },
      {
        type: 'detailTab',
        id: 'codebase-context',
        displayName: 'Codebase Context',
        exportName: 'IssueContextTab',
        entityTypes: ['issue'],
      },
      {
        type: 'page',
        id: 'prep-settings',
        displayName: 'SourcePrep Settings',
        exportName: 'SettingsPage',
      },
    ],
  },

  jobs: [
    {
      jobKey: 'reindex-check',
      displayName: 'SourcePrep Reindex Check',
      description: 'Check if SourcePrep index is stale and needs rebuild',
      schedule: '0 */6 * * *',
    },
  ],
};

export default manifest;
