import type { CliScript } from '@prep/ui';

// 1. Setup / Init Demo
export const docsInitDemo: CliScript = {
  title: 'codrag-init',
  loop: true,
  loopDelayMs: 4000,
  events: [
    { type: 'user_input', text: 'npx @codrag/cli init', typingDelayMs: 30 },
    { type: 'pause', durationMs: 500 },
    { type: 'agent_output', text: 'Initializing CoDRAG workspace locally...', typewriterDelayMs: 5 },
    { type: 'agent_output', text: '✔ Found 240 files.', typewriterDelayMs: 5 },
    { type: 'agent_output', text: '✔ Parsed AST via tree-sitter.', typewriterDelayMs: 5 },
    { type: 'agent_output', text: '✔ Computed dependency edges.', typewriterDelayMs: 5 },
    { type: 'tool_result', text: 'Ready. Index contains 1.4M graph nodes. Start the MCP server using `codrag serve`', status: 'success' },
    { type: 'pause', durationMs: 4000 }
  ]
};

// 2. Ambient Context Demo (codrag)
export const docsAmbientDemo: CliScript = {
  title: 'codrag-ambient',
  loop: true,
  loopDelayMs: 5000,
  events: [
    { type: 'user_input', text: 'codrag', typingDelayMs: 40 },
    { type: 'agent_thinking', durationMs: 600, label: 'fetching graph context' },
    { type: 'agent_output', text: 'CoDRAG Ambient Context Loaded:', typewriterDelayMs: 2 },
    { type: 'agent_output', text: ' Hub Files: src/auth.ts, src/db.ts', typewriterDelayMs: 2 },
    { type: 'agent_output', text: ' Graph Health: 98% connected components', typewriterDelayMs: 2 },
    { type: 'agent_output', text: ' Active Scope: UI Engineer (restricted to /components)', typewriterDelayMs: 2 },
    { type: 'pause', durationMs: 4000 }
  ]
};

// 3. Search Demo (codrag_search)
export const docsSearchDemo: CliScript = {
  title: 'codrag-search',
  loop: true,
  loopDelayMs: 5000,
  events: [
    { type: 'user_input', text: 'Search for "JWT decode failure"', typingDelayMs: 30 },
    { type: 'tool_call', tool: 'codrag_search', args: '{"query": "JWT decode failure"}', durationMs: 800 },
    { type: 'agent_output', text: 'Found semantic AST match in `lib/jwt.ts`:', typewriterDelayMs: 5 },
    { type: 'tool_result', text: '+ Expanded structural neighborhood to include `lib/errorHandler.ts`', status: 'info' },
    { type: 'agent_output', text: 'The decode fails because the error handler strips the signature. Let me fix that.', typewriterDelayMs: 10 },
    { type: 'pause', durationMs: 4000 }
  ]
};

// 4. Blast Radius (codrag_impact)
export const docsImpactDemo: CliScript = {
  title: 'codrag-impact',
  loop: true,
  loopDelayMs: 6000,
  events: [
    { type: 'user_input', text: 'What breaks if I change StripeCheckout?', typingDelayMs: 40 },
    { type: 'tool_call', tool: 'codrag_impact', args: '{"file_path": "components/StripeCheckout.tsx"}', durationMs: 1200 },
    { type: 'agent_output', text: 'Direct Dependents: 3 routes', typewriterDelayMs: 5 },
    { type: 'agent_output', text: 'Transitive Dependents: 12 files', typewriterDelayMs: 5 },
    { type: 'tool_result', text: 'WARNING: Modifying this will affect the `billing-api` microservice interface.', status: 'error' },
    { type: 'pause', durationMs: 4000 }
  ]
};

// 5. Audit (codrag_audit)
export const docsAuditDemo: CliScript = {
  title: 'codrag-audit',
  loop: true,
  loopDelayMs: 5000,
  events: [
    { type: 'user_input', text: 'Audit my codebase for issues', typingDelayMs: 30 },
    { type: 'tool_call', tool: 'codrag_audit', args: '{"action": "scan"}', durationMs: 2000 },
    { type: 'agent_output', text: '[ARCH-1] Circular dependency detected between `orders` and `billing`.', typewriterDelayMs: 5 },
    { type: 'agent_output', text: '[QUAL-3] `god_class.ts` exceeds 2,000 lines.', typewriterDelayMs: 5 },
    { type: 'user_input', text: 'Fix ARCH-1', typingDelayMs: 40 },
    { type: 'tool_call', tool: 'codrag_audit', args: '{"action": "refactor", "finding_ids": ["ARCH-1"]}', durationMs: 1500 },
    { type: 'tool_result', text: 'Extraction plan created. I will move the shared types to `common/types.ts`.', status: 'success' },
    { type: 'pause', durationMs: 4000 }
  ]
};
