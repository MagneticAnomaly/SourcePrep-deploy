import type { CliScript } from '@prep/ui';

export type DemoTool =
  | 'prep'
  | 'prep_search'
  | 'prep_impact'
  | 'prep_audit'
  | 'prep_observe'
  | 'prep_concepts'
  | 'ide';

export interface DemoVariant {
  id: string;
  tool: DemoTool;
  label: string;
  note?: string;
  script: CliScript;
}

// ----------------------------------------------------------------------------
// prep — ambient orientation when starting a real task
// ----------------------------------------------------------------------------

const prepRateLimiting: CliScript = {
  title: 'claude — my-project',
  loop: true,
  loopDelayMs: 5000,
  events: [
    {
      type: 'user_input',
      text: 'need to add rate limiting — where does that fit in here?',
      typingDelayMs: 28,
    },
    { type: 'agent_thinking', durationMs: 700 },
    {
      type: 'tool_call',
      tool: 'prep',
      args: '',
      durationMs: 800,
      statusText: 'Loading structural context…',
    },
    {
      type: 'tool_result',
      text: 'FastAPI app · 3 modules · hub: auth/middleware.py (23 dependents)',
      status: 'success',
    },
    { type: 'pause', durationMs: 300 },
    {
      type: 'agent_output',
      text: '`api/` is your request layer, and cross-cutting stuff already lives in `auth/middleware.py` — that\'s where auth + CORS get composed.\n\nRate limiting belongs there too. `middleware.py` has 23 dependents, so adding a new middleware class is safer than bolting a decorator onto every route. Want to start there?',
      typewriterDelayMs: 12,
    },
  ],
};

// ----------------------------------------------------------------------------
// prep_search — finding existing work before re-implementing it
// ----------------------------------------------------------------------------

const searchRetryReuse: CliScript = {
  title: 'claude — my-project',
  loop: true,
  loopDelayMs: 5000,
  events: [
    {
      type: 'user_input',
      text: 'do we have retry logic somewhere?',
      typingDelayMs: 30,
    },
    { type: 'agent_thinking', durationMs: 500 },
    {
      type: 'tool_call',
      tool: 'prep_search',
      args: '"retry failed jobs"',
      durationMs: 1000,
      statusText: 'Searching…',
    },
    {
      type: 'tool_result',
      text: '3 matches · services/queue/retry.ts · workers/base.ts · tests/retry.test.ts',
      status: 'success',
    },
    { type: 'pause', durationMs: 300 },
    {
      type: 'agent_output',
      text: 'Yeah — `RetryPolicy` in `services/queue/retry.ts`. Exponential backoff (1s → 30s, max 5 tries), dead-letter queue on terminal failures.\n\n`workers/base.ts` already wires it into the worker base class, so anything extending `BaseWorker` picks it up for free. Worth reusing instead of rolling your own.',
      typewriterDelayMs: 12,
    },
  ],
};

// ----------------------------------------------------------------------------
// prep_impact — blast radius before making a change
// ----------------------------------------------------------------------------

const impactRename: CliScript = {
  title: 'claude — my-project',
  loop: true,
  loopDelayMs: 5000,
  events: [
    {
      type: 'user_input',
      text: "let's rename getUserData to fetchUserProfile",
      typingDelayMs: 28,
    },
    { type: 'agent_thinking', durationMs: 600 },
    {
      type: 'tool_call',
      tool: 'prep_impact',
      args: '"getUserData"',
      durationMs: 900,
      statusText: 'Tracing callers…',
    },
    {
      type: 'tool_result',
      text: '14 callers · 6 files · 1 in public API surface',
      status: 'success',
    },
    { type: 'pause', durationMs: 300 },
    {
      type: 'agent_output',
      text: '`getUserData` has 14 callers across 6 files — including `api/public/users.ts`, which looks like part of your public surface.\n\nSafer to add `fetchUserProfile` as an alias and deprecate `getUserData` with a JSDoc notice, rather than a naked rename. Want me to do that?',
      typewriterDelayMs: 12,
    },
  ],
};

// ----------------------------------------------------------------------------
// prep_audit — enriches another tool's findings with graph context
// ----------------------------------------------------------------------------

const auditPrSanityCheck: CliScript = {
  title: 'claude — my-project',
  loop: true,
  loopDelayMs: 5000,
  events: [
    {
      type: 'user_input',
      text: 'quick sanity check before I open the PR?',
      typingDelayMs: 26,
    },
    { type: 'agent_thinking', durationMs: 700, label: 'Reviewing diff…' },
    {
      type: 'tool_call',
      tool: 'bash',
      args: 'git diff main -- src/',
      durationMs: 600,
    },
    {
      type: 'tool_result',
      text: '4 files · +128 / -42',
      status: 'success',
    },
    { type: 'agent_thinking', durationMs: 800, label: 'Forming findings…' },
    {
      type: 'tool_call',
      tool: 'prep_audit',
      args: 'findings=[8]',
      durationMs: 1000,
      statusText: 'Enriching with graph context…',
    },
    {
      type: 'tool_result',
      text: '8 findings · 2 critical (hub file) · 1 concept violation · 5 low-risk',
      status: 'success',
    },
    { type: 'pause', durationMs: 300 },
    {
      type: 'agent_output',
      text: "Found 8 things worth flagging. Graded by blast radius:\n\n• **2 critical** — your `charge()` change hits a hub file with 14 dependents. Second look worth it.\n• **1 concept violation** — direct DB call inside `payment/`, which has a \"no db.transaction\" architectural rule.\n• **5 low-risk** — style nits in leaf files, safe to batch.\n\nI'd only block on the first two. Rest can ship.",
      typewriterDelayMs: 12,
    },
  ],
};

// ----------------------------------------------------------------------------
// prep_observe — recall of past decisions, with staleness tracking
// ----------------------------------------------------------------------------

const observeCachingRecall: CliScript = {
  title: 'claude — my-project',
  loop: true,
  loopDelayMs: 5000,
  events: [
    {
      type: 'user_input',
      text: 'wait — did we ever settle on anything for caching?',
      typingDelayMs: 28,
    },
    { type: 'agent_thinking', durationMs: 500 },
    {
      type: 'tool_call',
      tool: 'prep_observe',
      args: 'action="get", query="caching"',
      durationMs: 700,
      statusText: 'Retrieving observations…',
    },
    {
      type: 'tool_result',
      text: '2 observations · 1 active · 1 [stale]',
      status: 'success',
    },
    { type: 'pause', durationMs: 300 },
    {
      type: 'agent_output',
      text: 'Two notes on file:\n\n• **Redis, 5-min TTL for session data** — decided 3 months ago (active)\n• **In-memory LRU for hot reads** — proposed last month, but the linked file (`cache/memory.ts`) has changed since, so it\'s flagged [stale]\n\nSo: Redis session cache is still the plan. The LRU idea is worth re-evaluating before you build on it.',
      typewriterDelayMs: 12,
    },
  ],
};

// ----------------------------------------------------------------------------
// prep_concepts — surfaces architectural constraints / business rules
// ----------------------------------------------------------------------------

const conceptsTransactionRule: CliScript = {
  title: 'claude — my-project',
  loop: true,
  loopDelayMs: 5000,
  events: [
    {
      type: 'user_input',
      text: 'why can\'t I just wrap this in a transaction?',
      typingDelayMs: 26,
    },
    { type: 'agent_thinking', durationMs: 600 },
    {
      type: 'tool_call',
      tool: 'prep_concepts',
      args: 'action="get", query="payment transaction"',
      durationMs: 800,
      statusText: 'Querying concept store…',
    },
    {
      type: 'tool_result',
      text: 'Concept: "Payment Saga" · constraint · 2 anchors',
      status: 'success',
    },
    { type: 'pause', durationMs: 300 },
    {
      type: 'agent_output',
      text: 'Payment has a hard rule against direct transactions — your team recorded it as *"no db.transaction inside payment/"*.\n\nReason: payments span billing, inventory, and notifications, and a single DB transaction can\'t cover all three. Use the saga runner in `services/saga_runner.py` — it handles compensating rollbacks for you if something downstream fails.',
      typewriterDelayMs: 12,
    },
  ],
};

// ----------------------------------------------------------------------------
// IDE — agentic edit using prep + prep_search for orientation
// ----------------------------------------------------------------------------

const ideLivePipelineUpdates: CliScript = {
  title: 'prep-ide-demo',
  loop: true,
  loopDelayMs: 5000,
  events: [
    { type: 'pause', durationMs: 600 },
    {
      type: 'user_input',
      text: 'make the pipeline status live — right now you have to refresh to see updates',
      typingDelayMs: 26,
    },
    { type: 'agent_thinking', durationMs: 1000 },
    { type: 'tool_call', tool: 'prep', args: '', durationMs: 700 },
    {
      type: 'tool_result',
      text: '412 files · React dashboard · hub: PipelineService.ts',
      status: 'success',
    },
    {
      type: 'tool_call',
      tool: 'prep_search',
      args: '"pipeline dashboard status"',
      durationMs: 900,
    },
    {
      type: 'tool_result',
      text: 'PipelineDashboard.tsx (4 dependents) · useWebSocket hook already exists',
      status: 'success',
    },
    {
      type: 'agent_output',
      text: 'Found `PipelineDashboard.tsx`. There\'s already a `useWebSocket` hook in the codebase — I\'ll wire it into the dashboard instead of rolling new polling logic.',
      typewriterDelayMs: 16,
    },
    {
      type: 'file_open',
      filePath: 'src/components/PipelineDashboard.tsx',
      language: 'typescript',
      content: `import { useState } from 'react';

export function PipelineDashboard() {
  const [status, setStatus] = useState('idle');

  return (
    <div className="p-4">
      <h2>Pipeline: {status}</h2>
    </div>
  );
}`,
      durationMs: 1000,
    },
    { type: 'agent_thinking', durationMs: 500 },
    {
      type: 'code_edit',
      filePath: 'src/components/PipelineDashboard.tsx',
      durationMs: 1800,
      newContent: `import { useState, useEffect } from 'react';
import { useWebSocket } from '@/hooks/useWebSocket';

export function PipelineDashboard() {
  const [status, setStatus] = useState('idle');
  const ws = useWebSocket('/api/pipeline/status');

  useEffect(() => {
    ws.onMessage((msg) => setStatus(msg.status));
    return () => ws.close();
  }, [ws]);

  return (
    <div className="p-4 rounded border border-border">
      <h2>Pipeline: <span className="text-primary">{status}</span></h2>
    </div>
  );
}`,
    },
    {
      type: 'agent_output',
      text: 'Updated `PipelineDashboard.tsx` — subscribes to `/api/pipeline/status` via the existing hook, updates live, cleans up on unmount. No more refresh needed.',
      typewriterDelayMs: 14,
    },
    { type: 'pause', durationMs: 3500 },
  ],
};

// ----------------------------------------------------------------------------
// Export
// ----------------------------------------------------------------------------

export const variants: DemoVariant[] = [
  {
    id: 'prep-rate-limiting',
    tool: 'prep',
    label: 'Adding a feature — "where does this fit?"',
    note: 'Dev starts a real task. prep fires as orientation, not as a query. Value = agent points to the right seam instead of guessing.',
    script: prepRateLimiting,
  },
  {
    id: 'search-retry-reuse',
    tool: 'prep_search',
    label: '"Do we already have X?"',
    note: 'The ultimate casual prompt devs mutter to themselves. Catches near-duplicate implementations before they happen.',
    script: searchRetryReuse,
  },
  {
    id: 'impact-rename',
    tool: 'prep_impact',
    label: 'Rename with public API surface',
    note: 'Ordinary rename request — impact fires because the agent knows renames have blast radius. Value shows up in the recommendation (alias vs. naked rename).',
    script: impactRename,
  },
  {
    id: 'audit-pr-sanity-check',
    tool: 'prep_audit',
    label: 'Pre-PR review (SourcePrep enriches)',
    note: 'Agent does the review. prep_audit enriches findings with graph context (hub files, concept violations). SourcePrep is NOT the auditor — it makes the auditor smarter.',
    script: auditPrSanityCheck,
  },
  {
    id: 'observe-caching-recall',
    tool: 'prep_observe',
    label: 'Recalling past decisions',
    note: 'Dev half-remembers a prior discussion. Recall surfaces both the active decision and a stale one that needs re-evaluation.',
    script: observeCachingRecall,
  },
  {
    id: 'concepts-transaction-rule',
    tool: 'prep_concepts',
    label: 'Hitting an architectural constraint',
    note: 'Dev about to violate a hard rule. concepts surfaces the team-recorded rationale + the sanctioned alternative.',
    script: conceptsTransactionRule,
  },
  {
    id: 'ide-live-pipeline-updates',
    tool: 'ide',
    label: 'Live updates — reusing an existing hook',
    note: 'Casual bug-style prompt. Agent uses prep + search to discover the existing useWebSocket hook instead of rolling new polling logic.',
    script: ideLivePipelineUpdates,
  },
];
