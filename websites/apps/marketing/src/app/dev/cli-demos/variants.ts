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

// ============================================================================
// prep — ambient structural orientation
// ============================================================================

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

const prepPaymentsOnboard: CliScript = {
  title: 'claude — my-project',
  loop: true,
  loopDelayMs: 5000,
  events: [
    {
      type: 'user_input',
      text: 'jumping into the payments module for the first time',
      typingDelayMs: 28,
    },
    { type: 'agent_thinking', durationMs: 700 },
    {
      type: 'tool_call',
      tool: 'prep',
      args: '',
      durationMs: 900,
      statusText: 'Loading structural context…',
    },
    {
      type: 'tool_result',
      text: 'payment/ · 12 files · hub: saga_runner.py · Stripe + billing/ + inventory/',
      status: 'success',
    },
    { type: 'pause', durationMs: 300 },
    {
      type: 'agent_output',
      text: '`payment/` is 12 files, all coordinated by `saga_runner.py`. It talks to Stripe, `billing/`, and `inventory/`.\n\nHeads up before you touch anything: there\'s a hard architectural rule — no direct DB transactions inside `payment/`. The saga runner handles rollbacks when something fails downstream. Worth keeping in mind.',
      typewriterDelayMs: 12,
    },
  ],
};

// ============================================================================
// prep_search — semantic search with structural expansion
// ============================================================================

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

const searchOauthCallback: CliScript = {
  title: 'claude — my-project',
  loop: true,
  loopDelayMs: 5000,
  events: [
    {
      type: 'user_input',
      text: 'show me how we handle oauth callbacks',
      typingDelayMs: 28,
    },
    { type: 'agent_thinking', durationMs: 500 },
    {
      type: 'tool_call',
      tool: 'prep_search',
      args: '"oauth callback handler"',
      durationMs: 900,
      statusText: 'Searching…',
    },
    {
      type: 'tool_result',
      text: '2 matches · auth/oauth.py · tests/test_oauth.py',
      status: 'success',
    },
    { type: 'pause', durationMs: 300 },
    {
      type: 'agent_output',
      text: 'Callback lives in `auth/oauth.py` — `AuthOAuth.handle_callback()`. Flow:\n\n1. Validates the `state` param against Redis (CSRF defense)\n2. Exchanges the code for a token with the provider\n3. Creates or updates the `User` record\n4. Issues a new session\n\nErrors route to `/auth/error?reason=…`. Token refresh is separate — it lives in `token_service.py`.',
      typewriterDelayMs: 12,
    },
  ],
};

// ============================================================================
// prep_impact — blast radius before making a change
// ============================================================================

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

const impactDeleteUnused: CliScript = {
  title: 'claude — my-project',
  loop: true,
  loopDelayMs: 5000,
  events: [
    {
      type: 'user_input',
      text: "removing the legacy email helper — it's unused",
      typingDelayMs: 28,
    },
    { type: 'agent_thinking', durationMs: 600 },
    {
      type: 'tool_call',
      tool: 'prep_impact',
      args: '"send_email_legacy"',
      durationMs: 900,
      statusText: 'Tracing callers…',
    },
    {
      type: 'tool_result',
      text: '7 callers · 4 files · notifications/, workers/digest.py',
      status: 'success',
    },
    { type: 'pause', durationMs: 300 },
    {
      type: 'agent_output',
      text: "Actually, `send_email_legacy` still has 7 callers across 4 files — mostly in `notifications/` and one in `workers/digest.py`. Looks like the migration to the new mailer stopped halfway.\n\nWant me to finish the migration first, then delete the legacy helper? I can flag which call sites are straightforward swaps and which need a closer look.",
      typewriterDelayMs: 12,
    },
  ],
};

// ============================================================================
// prep_audit — enriches another tool's findings with graph context
// ============================================================================

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

const auditBranchReview: CliScript = {
  title: 'claude — my-project',
  loop: true,
  loopDelayMs: 5000,
  events: [
    {
      type: 'user_input',
      text: 'review this branch before I push',
      typingDelayMs: 26,
    },
    { type: 'agent_thinking', durationMs: 600, label: 'Reading diff…' },
    {
      type: 'tool_call',
      tool: 'bash',
      args: 'git diff main -- src/',
      durationMs: 600,
    },
    {
      type: 'tool_result',
      text: '6 files · +204 / -56',
      status: 'success',
    },
    { type: 'agent_thinking', durationMs: 900, label: 'Forming findings…' },
    {
      type: 'tool_call',
      tool: 'prep_audit',
      args: 'findings=[11]',
      durationMs: 1100,
      statusText: 'Enriching with graph context…',
    },
    {
      type: 'tool_result',
      text: '11 findings · 1 critical · 2 concept violations · 8 low-risk',
      status: 'success',
    },
    { type: 'pause', durationMs: 300 },
    {
      type: 'agent_output',
      text: "Went through the diff and flagged 11 things. Ranked by blast radius:\n\n• **1 critical** — new unhandled `await` in `payment/charge.ts`, and that file has 14 downstream callers.\n• **2 concept violations** — direct DB writes inside `payment/` (your \"no db.transaction\" rule).\n• **8 low-risk** — naming, minor typing gaps.\n\nI'd fix the critical + concept ones before pushing. Low-risk can follow up.",
      typewriterDelayMs: 12,
    },
  ],
};

// ============================================================================
// prep_observe — persistent cross-session memory
// ============================================================================

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

const observeZodStandard: CliScript = {
  title: 'claude — my-project',
  loop: true,
  loopDelayMs: 5000,
  events: [
    {
      type: 'user_input',
      text: "note: we're standardizing on zod for new validation",
      typingDelayMs: 26,
    },
    { type: 'agent_thinking', durationMs: 500 },
    {
      type: 'tool_call',
      tool: 'prep_observe',
      args: 'action="save", category="decision"',
      durationMs: 700,
      statusText: 'Saving observation…',
    },
    {
      type: 'tool_result',
      text: 'Saved #51 · linked to 4 validation sites',
      status: 'success',
    },
    { type: 'pause', durationMs: 300 },
    {
      type: 'agent_output',
      text: "Saved. Linked it to the 4 files currently using ad-hoc validation — `api/users.py`, `api/billing.py`, `api/webhooks.py`, `workers/ingest.py`.\n\nIf any of those get touched later, this note resurfaces automatically so you (or whoever picks the work up) knows to weigh a migration to zod.",
      typewriterDelayMs: 12,
    },
  ],
};

// ============================================================================
// prep_concepts — business rationale and architectural constraints
// ============================================================================

const conceptsTransactionRule: CliScript = {
  title: 'claude — my-project',
  loop: true,
  loopDelayMs: 5000,
  events: [
    {
      type: 'user_input',
      text: "why can't I just wrap this in a transaction?",
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

const conceptsDocumentRule: CliScript = {
  title: 'claude — my-project',
  loop: true,
  loopDelayMs: 5000,
  events: [
    {
      type: 'user_input',
      text: "let's document the no-direct-transactions rule for payment/",
      typingDelayMs: 26,
    },
    { type: 'agent_thinking', durationMs: 600 },
    {
      type: 'tool_call',
      tool: 'prep_concepts',
      args: 'action="save", category="constraint"',
      durationMs: 900,
      statusText: 'Recording concept…',
    },
    {
      type: 'tool_result',
      text: 'Saved "Payment Saga Rule" · assertion: no db.transaction inside payment/ · 2 anchors',
      status: 'success',
    },
    { type: 'pause', durationMs: 300 },
    {
      type: 'agent_output',
      text: 'Recorded as *"Payment Saga Rule"* — assertion `no db.transaction inside payment/`, anchored on `saga_runner.py` and `payment/charge.py`.\n\nFrom now on, any new `db.transaction` import inside `payment/` gets flagged by the immune system when I (or anyone else using the graph) looks at that area. Future-you gets a polite alarm instead of a surprise.',
      typewriterDelayMs: 12,
    },
  ],
};

// ============================================================================
// IDE — agentic edit, prep + search for orientation
// ============================================================================

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
      text: "Found `PipelineDashboard.tsx`. There's already a `useWebSocket` hook in the codebase — I'll wire it into the dashboard instead of rolling new polling logic.",
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

const ideDoubleSubmitFix: CliScript = {
  title: 'prep-ide-demo',
  loop: true,
  loopDelayMs: 5000,
  events: [
    { type: 'pause', durationMs: 600 },
    {
      type: 'user_input',
      text: 'fix the double-submit on PaymentForm — only happens on mobile',
      typingDelayMs: 26,
    },
    { type: 'agent_thinking', durationMs: 900 },
    { type: 'tool_call', tool: 'prep_search', args: '"PaymentForm submit handler"', durationMs: 900 },
    {
      type: 'tool_result',
      text: 'PaymentForm.tsx · handleSubmit · no pending-state guard',
      status: 'success',
    },
    {
      type: 'agent_output',
      text: "Found it. `handleSubmit` doesn't guard against re-entry while the request is pending — mobile users are probably double-tapping before the spinner renders. I'll add an `isSubmitting` flag and disable the button while it's in flight.",
      typewriterDelayMs: 16,
    },
    {
      type: 'file_open',
      filePath: 'src/components/PaymentForm.tsx',
      language: 'typescript',
      content: `import { useState } from 'react';

export function PaymentForm({ onSubmit }: { onSubmit: (data: FormData) => Promise<void> }) {
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    try {
      await onSubmit(new FormData(e.currentTarget));
    } catch (err) {
      setError('Payment failed');
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      {error && <p className="text-red-500">{error}</p>}
      <button type="submit" className="btn-primary">Pay</button>
    </form>
  );
}`,
      durationMs: 1000,
    },
    { type: 'agent_thinking', durationMs: 500 },
    {
      type: 'code_edit',
      filePath: 'src/components/PaymentForm.tsx',
      durationMs: 1800,
      newContent: `import { useState } from 'react';

export function PaymentForm({ onSubmit }: { onSubmit: (data: FormData) => Promise<void> }) {
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (isSubmitting) return;
    setIsSubmitting(true);
    try {
      await onSubmit(new FormData(e.currentTarget));
    } catch (err) {
      setError('Payment failed');
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      {error && <p className="text-red-500">{error}</p>}
      <button type="submit" disabled={isSubmitting} className="btn-primary">
        {isSubmitting ? 'Processing…' : 'Pay'}
      </button>
    </form>
  );
}`,
    },
    {
      type: 'agent_output',
      text: 'Added the `isSubmitting` guard — early-return on re-entry, button disables on submit, re-enables in `finally`. Mobile double-tap stops causing a second charge.',
      typewriterDelayMs: 14,
    },
    { type: 'pause', durationMs: 3500 },
  ],
};

// ============================================================================
// Export — ordered so that filter-by-tool groups cleanly in the UI
// ============================================================================

export const variants: DemoVariant[] = [
  // prep
  {
    id: 'prep-rate-limiting',
    tool: 'prep',
    label: 'Adding a feature — "where does this fit?"',
    note: 'Casual task-start. prep fires as orientation, not as a query. Value = agent points to the right seam instead of guessing.',
    script: prepRateLimiting,
  },
  {
    id: 'prep-payments-onboard',
    tool: 'prep',
    label: 'Jumping into an unfamiliar module',
    note: 'Declarative (not a question). Dev signals they\'re onboarding; prep returns structure + surfaces the hard architectural rule before they trip over it.',
    script: prepPaymentsOnboard,
  },

  // prep_search
  {
    id: 'search-retry-reuse',
    tool: 'prep_search',
    label: '"Do we already have X?"',
    note: 'Ultimate casual prompt devs mutter to themselves. Catches near-duplicate implementations before they happen.',
    script: searchRetryReuse,
  },
  {
    id: 'search-oauth-callback',
    tool: 'prep_search',
    label: 'Imperative "show me how X works"',
    note: 'Imperative form — not a question. Returns the actual flow steps rather than a file list, thanks to structural expansion.',
    script: searchOauthCallback,
  },

  // prep_impact
  {
    id: 'impact-rename',
    tool: 'prep_impact',
    label: 'Rename with public API surface',
    note: 'Ordinary rename request — impact fires because renames have blast radius. Value shows up in the recommendation (alias vs. naked rename).',
    script: impactRename,
  },
  {
    id: 'impact-delete-unused',
    tool: 'prep_impact',
    label: 'Declarative "it\'s unused" (spoiler: it\'s not)',
    note: 'Dev is confidently wrong. Impact catches 7 real callers before the delete happens. Classic graph-wins-over-grep scenario.',
    script: impactDeleteUnused,
  },

  // prep_audit
  {
    id: 'audit-pr-sanity-check',
    tool: 'prep_audit',
    label: 'Pre-PR review (SourcePrep enriches)',
    note: 'Agent does the review. prep_audit enriches findings with graph context (hub files, concept violations). SourcePrep is NOT the auditor — it makes the auditor smarter.',
    script: auditPrSanityCheck,
  },
  {
    id: 'audit-branch-review',
    tool: 'prep_audit',
    label: 'Imperative "review this branch"',
    note: 'Variant of the PR-check with a more direct, imperative prompt. Same enrichment pattern — agent\'s own review + graph context.',
    script: auditBranchReview,
  },

  // prep_observe
  {
    id: 'observe-caching-recall',
    tool: 'prep_observe',
    label: 'Recalling past decisions',
    note: 'Dev half-remembers a prior discussion. Recall surfaces both the active decision and a stale one that needs re-evaluation.',
    script: observeCachingRecall,
  },
  {
    id: 'observe-zod-standard',
    tool: 'prep_observe',
    label: 'Saving a decision ("note: ...")',
    note: 'Declarative save. Shows the write side of observations — plus the auto-linking to affected files, so the note resurfaces when relevant later.',
    script: observeZodStandard,
  },

  // prep_concepts
  {
    id: 'concepts-transaction-rule',
    tool: 'prep_concepts',
    label: 'Hitting an architectural constraint',
    note: 'Dev about to violate a hard rule. Concepts surfaces the team-recorded rationale + the sanctioned alternative.',
    script: conceptsTransactionRule,
  },
  {
    id: 'concepts-document-rule',
    tool: 'prep_concepts',
    label: 'Declarative "let\'s document this rule"',
    note: 'Save side of concepts. Creates a constraint that the immune system will enforce going forward. Future agents get the alarm automatically.',
    script: conceptsDocumentRule,
  },

  // ide
  {
    id: 'ide-live-pipeline-updates',
    tool: 'ide',
    label: 'Live updates — reusing an existing hook',
    note: 'Casual bug-style prompt. Agent uses prep + search to discover the existing useWebSocket hook instead of rolling new polling logic.',
    script: ideLivePipelineUpdates,
  },
  {
    id: 'ide-double-submit-fix',
    tool: 'ide',
    label: 'Imperative bug fix — mobile double-submit',
    note: 'Imperative bug report ("fix the X"). Search orients to the handler; edit adds the isSubmitting guard. No question, no explanation asked for.',
    script: ideDoubleSubmitFix,
  },
];
