/**
 * CoDRAG Paperclip Plugin Manifest
 *
 * Declares plugin identity, capabilities, tools, config schema, and UI slots.
 */

export default {
  id: 'codrag',
  name: 'CoDRAG Codebase Intelligence',
  version: '0.1.0',
  description:
    'Gives every Paperclip agent structural codebase knowledge — module maps, ' +
    'dependency graphs, semantic search, and health analysis powered by CoDRAG.',
  author: 'CoDRAG',
  homepage: 'https://codrag.dev',
  apiVersion: 1,

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
    'ui.settingsPage.register',
  ],

  config: {
    schema: {
      type: 'object',
      properties: {
        daemon_url: {
          type: 'string',
          description: 'CoDRAG daemon base URL',
          default: 'http://127.0.0.1:8400',
        },
        project_id: {
          type: 'string',
          description: 'Default CoDRAG project ID (auto-detected from workspace path if empty)',
          default: '',
        },
        auto_context: {
          type: 'boolean',
          description: 'Automatically attach CoDRAG context to new issues',
          default: true,
        },
      },
      required: ['daemon_url'],
    },
  },

  tools: [
    {
      name: 'context',
      displayName: 'Codebase Context',
      description:
        'Get structural overview of the codebase: modules, hub files, atlas. ' +
        'Call at the start of every task.',
      parametersSchema: {
        type: 'object',
        properties: {
          role: {
            type: 'string',
            description: 'Optional role slug for scoped context',
          },
        },
      },
    },
    {
      name: 'search',
      displayName: 'Code Search',
      description:
        'Semantic code search with structural trace expansion. ' +
        'Returns relevant code chunks ranked by relevance.',
      parametersSchema: {
        type: 'object',
        properties: {
          query: { type: 'string', description: 'Search query' },
          role: { type: 'string', description: 'Optional role for scoped results' },
          k: { type: 'number', description: 'Max results (default 5)', default: 5 },
        },
        required: ['query'],
      },
    },
    {
      name: 'impact',
      displayName: 'Impact Analysis',
      description:
        'Analyze what depends on a file — dependencies, dependents, blast radius. ' +
        'Use before modifying files.',
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
          categories: {
            type: 'array',
            items: { type: 'string' },
            description: 'Filter by categories',
          },
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
          category: {
            type: 'string',
            enum: ['note', 'decision', 'bug', 'pattern', 'assumption'],
            default: 'note',
          },
        },
        required: ['content'],
      },
    },
  ],

  ui: {
    slots: [
      {
        type: 'dashboardWidget',
        key: 'codebase-health',
        title: 'Codebase Health',
        description: 'Module count, hub files, readiness score',
      },
      {
        type: 'detailTab',
        entityType: 'agent',
        key: 'knowledge-scope',
        title: 'Knowledge Scope',
        description: 'CoDRAG-powered file scope for this agent',
      },
      {
        type: 'detailTab',
        entityType: 'issue',
        key: 'codebase-context',
        title: 'Codebase Context',
        description: 'Structural context for this issue from CoDRAG',
      },
      {
        type: 'settingsPage',
        key: 'codrag-config',
        title: 'CoDRAG Configuration',
        description: 'Daemon URL, project mapping, index status',
      },
    ],
  },

  jobs: [
    {
      key: 'reindex-check',
      description: 'Check if CoDRAG index is stale and needs rebuild',
      defaultCron: '0 */6 * * *', // every 6 hours
    },
  ],
};
