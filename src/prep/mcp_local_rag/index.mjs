import { McpServer, StdioServerTransport } from '@modelcontextprotocol/server';
import * as z from 'zod/v4';

const apiBase = (process.env.RAG_API_BASE || 'http://localhost:5000/api/self-rag').replace(/\/+$/, '');
const timeoutMs = Number.parseInt(process.env.RAG_TIMEOUT_MS || '30000', 10);

async function httpJson(path, { method = 'GET', body } = {}) {
  const url = `${apiBase}${path}`;
  const controller = new AbortController();
  const t = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const res = await fetch(url, {
      method,
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });

    const text = await res.text();
    let data;
    try {
      data = text ? JSON.parse(text) : null;
    } catch {
      data = { raw: text };
    }

    if (!res.ok) {
      const msg = typeof data === 'object' && data && data.error ? String(data.error) : `HTTP ${res.status}`;
      throw new Error(`${method} ${url} failed: ${msg}`);
    }

    return data;
  } finally {
    clearTimeout(t);
  }
}

const server = new McpServer({
  name: 'local-rag',
  version: '0.1.0',
});

server.registerTool(
  'local_rag_status',
  {
    title: 'Local RAG Status',
    description: 'Check status of the local RAG index server.',
    inputSchema: {},
  },
  async () => {
    const data = await httpJson('/status', { method: 'GET' });
    return {
      content: [{ type: 'text', text: JSON.stringify(data, null, 2) }],
      structuredContent: data,
    };
  },
);

server.registerTool(
  'local_rag_build',
  {
    title: 'Local RAG Build',
    description: 'Trigger an async build of the local RAG index. For Halley Self-RAG, pass project_root and optional roots.',
    inputSchema: {
      project_root: z.string().optional(),
      roots: z.array(z.string()).optional(),
      repo_root: z.string().optional(),
      include_globs: z.array(z.string()).optional(),
      exclude_globs: z.array(z.string()).optional(),
      max_file_bytes: z.number().int().optional(),
    },
  },
  async (input) => {
    const data = await httpJson('/build', { method: 'POST', body: input || {} });
    return {
      content: [{ type: 'text', text: JSON.stringify(data, null, 2) }],
      structuredContent: data,
    };
  },
);

server.registerTool(
  'local_rag_search',
  {
    title: 'Local RAG Search',
    description: 'Search the local RAG index and return scored chunks with metadata.',
    inputSchema: {
      query: z.string(),
      k: z.number().int().optional(),
      min_score: z.number().optional(),
    },
  },
  async ({ query, k, min_score }) => {
    const data = await httpJson('/search', {
      method: 'POST',
      body: {
        query,
        k,
        min_score,
      },
    });

    return {
      content: [{ type: 'text', text: JSON.stringify(data, null, 2) }],
      structuredContent: data,
    };
  },
);

server.registerTool(
  'local_rag_context',
  {
    title: 'Local RAG Context',
    description: 'Return an assembled context string (best chunks) for LLM injection.',
    inputSchema: {
      query: z.string(),
      k: z.number().int().optional(),
      max_chars: z.number().int().optional(),
      include_sources: z.boolean().optional(),
      include_scores: z.boolean().optional(),
      min_score: z.number().optional(),
      structured: z.boolean().optional(),
    },
  },
  async ({ query, k, max_chars, include_sources, include_scores, min_score, structured }) => {
    const data = await httpJson('/context', {
      method: 'POST',
      body: {
        query,
        k,
        max_chars,
        include_sources,
        include_scores,
        min_score,
        structured,
      },
    });

    if (structured) {
      return {
        content: [{ type: 'text', text: JSON.stringify(data, null, 2) }],
        structuredContent: data,
      };
    }

    const ctx = (data && typeof data === 'object' && 'context' in data) ? String(data.context || '') : '';

    return {
      content: [{ type: 'text', text: ctx }],
      structuredContent: data,
    };
  },
);

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

try {
  await main();
} catch (err) {
  console.error(err);
  process.exit(1);
}
