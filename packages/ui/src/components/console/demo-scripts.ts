import type { CliScript } from './cli-types';

// ============================================================================
// prep — ambient structural orientation
// ============================================================================

const prepRateLimitingDemo: CliScript = {
  title: 'claude — my-project',
  loop: true,
  loopDelayMs: 5000,
  events: [
    {
      type: 'user_input',
      text: 'need to add rate limiting — where does that fit?',
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

const prepTldrOverviewDemo: CliScript = {
  title: 'claude — my-project',
  loop: true,
  loopDelayMs: 5000,
  events: [
    {
      type: 'user_input',
      text: 'tldr on this codebase',
      typingDelayMs: 28,
    },
    { type: 'agent_thinking', durationMs: 500 },
    {
      type: 'tool_call',
      tool: 'prep',
      args: '',
      durationMs: 800,
      statusText: 'Loading structural context…',
    },
    {
      type: 'tool_result',
      text: 'FastAPI + React · 247 files · payment/ + auth/ + workers/ · 14k LOC',
      status: 'success',
    },
    { type: 'pause', durationMs: 300 },
    {
      type: 'agent_output',
      text: "It's a FastAPI backend with a React dashboard. Three core modules:\n\n• `payment/` — saga-based payment flow\n• `auth/` — JWT + OAuth\n• `workers/` — background jobs, already using `RetryPolicy`\n\nHub files: `auth/middleware.py` (23 dependents) and `payment/saga_runner.py` (14). Both worth treating carefully. One hard architectural rule: no direct DB transactions inside `payment/`.",
      typewriterDelayMs: 12,
    },
  ],
};

const prepBuildWebhookDemo: CliScript = {
  title: 'claude — my-project',
  loop: true,
  loopDelayMs: 5000,
  events: [
    {
      type: 'user_input',
      text: 'add a webhook endpoint for subscription.cancelled events',
      typingDelayMs: 26,
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
      text: 'api/webhooks/ · 4 existing handlers · hub: webhook_router.py',
      status: 'success',
    },
    { type: 'pause', durationMs: 300 },
    {
      type: 'agent_output',
      text: 'Webhooks live in `api/webhooks/`, all routed through `webhook_router.py`. There are already 4 handlers (invoice paid, payment failed, dispute, refund) that follow the same shape: validate signature → parse payload → enqueue a domain event → return 200.\n\nI\'ll add `subscription_cancelled.py` next to them and register it in the router so it picks up the same middleware. Ready to draft it?',
      typewriterDelayMs: 12,
    },
  ],
};

// ============================================================================
// prep_search — semantic search with structural expansion
// ============================================================================

const searchRetryReuseDemo: CliScript = {
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

const searchMaxConnectionsDemo: CliScript = {
  title: 'claude — my-project',
  loop: true,
  loopDelayMs: 5000,
  events: [
    {
      type: 'user_input',
      text: "where's 'max connections exceeded' coming from?",
      typingDelayMs: 28,
    },
    { type: 'agent_thinking', durationMs: 500 },
    {
      type: 'tool_call',
      tool: 'prep_search',
      args: '"max connections exceeded"',
      durationMs: 900,
      statusText: 'Searching…',
    },
    {
      type: 'tool_result',
      text: '2 matches · db/pool.py:142 · tests/test_pool.py',
      status: 'success',
    },
    { type: 'pause', durationMs: 300 },
    {
      type: 'agent_output',
      text: "`DatabasePool.acquire()` throws it in `db/pool.py:142` when the pool is saturated. Pool size lives in `db/config.py` — defaults to 20.\n\nIf you're hitting it in staging, either the pool is smaller there than prod, or something's leaking connections without releasing them. Rest of the codebase uses `with pool.acquire()` — worth grepping whoever you just touched for a missing `with`.",
      typewriterDelayMs: 12,
    },
  ],
};

const searchBuildWorkerDemo: CliScript = {
  title: 'claude — my-project',
  loop: true,
  loopDelayMs: 5000,
  events: [
    {
      type: 'user_input',
      text: 'build a worker that sends weekly digest emails every sunday',
      typingDelayMs: 26,
    },
    { type: 'agent_thinking', durationMs: 600 },
    {
      type: 'tool_call',
      tool: 'prep_search',
      args: '"scheduled worker base class"',
      durationMs: 900,
      statusText: 'Searching…',
    },
    {
      type: 'tool_result',
      text: 'workers/base.py · ScheduledWorker · 5 existing cron workers',
      status: 'success',
    },
    { type: 'pause', durationMs: 300 },
    {
      type: 'agent_output',
      text: '`ScheduledWorker` in `workers/base.py` is the pattern — takes a cron expression, inherits `RetryPolicy` and the shared logger automatically. 5 workers already extend it (`workers/cleanup.py`, `workers/billing_sync.py`, etc.).\n\nI\'ll add `workers/digest.py` extending `ScheduledWorker`, cron `0 9 * * 0` for 9am Sunday, and register it in `workers/__init__.py` next to the others. Ready to write it?',
      typewriterDelayMs: 12,
    },
  ],
};

// ============================================================================
// prep_impact — blast radius before making a change
// ============================================================================

const impactDeleteUnusedDemo: CliScript = {
  title: 'claude — my-project',
  loop: true,
  loopDelayMs: 5000,
  events: [
    {
      type: 'user_input',
      text: "remove the legacy email helper — it's unused",
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

const impactExtractServiceDemo: CliScript = {
  title: 'claude — my-project',
  loop: true,
  loopDelayMs: 5000,
  events: [
    {
      type: 'user_input',
      text: 'thinking about pulling ReportGenerator out into its own service',
      typingDelayMs: 26,
    },
    { type: 'agent_thinking', durationMs: 700 },
    {
      type: 'tool_call',
      tool: 'prep_impact',
      args: '"ReportGenerator"',
      durationMs: 1000,
      statusText: 'Tracing dependents…',
    },
    {
      type: 'tool_result',
      text: '12 callers · 4 files · all in dashboard/ and workers/',
      status: 'success',
    },
    { type: 'pause', durationMs: 300 },
    {
      type: 'agent_output',
      text: "`ReportGenerator` has 12 callers across 4 files — all contained to `dashboard/` and `workers/`. Good news for extraction.\n\nOne thing to watch: `workers/nightly.py` calls it synchronously inside a scheduled job. Moving it to a remote service turns that into a network hop with failure modes the worker isn't currently handling. Worth wrapping the new client in the existing `RetryPolicy` when you migrate.",
      typewriterDelayMs: 12,
    },
  ],
};

const impactAsyncMigrationDemo: CliScript = {
  title: 'claude — my-project',
  loop: true,
  loopDelayMs: 5000,
  events: [
    {
      type: 'user_input',
      text: 'make send_email async',
      typingDelayMs: 28,
    },
    { type: 'agent_thinking', durationMs: 700 },
    {
      type: 'tool_call',
      tool: 'prep_impact',
      args: '"send_email"',
      durationMs: 1000,
      statusText: 'Tracing callers…',
    },
    {
      type: 'tool_result',
      text: '19 callers · 11 files · 4 in sync request paths',
      status: 'success',
    },
    { type: 'pause', durationMs: 300 },
    {
      type: 'agent_output',
      text: "`send_email` is called from 19 places across 11 files. Most are workers or already-async routes, which are fine — but 4 callers are inside **sync FastAPI handlers** (`api/auth.py`, `api/billing.py`, `api/users.py`, `api/invites.py`) that can't just `await` it.\n\nTwo paths: (a) make those routes async too — small blast radius, clean. (b) keep a sync `send_email_now()` wrapper that schedules via the queue. I'd go with (a). Want me to draft it?",
      typewriterDelayMs: 12,
    },
  ],
};

// ============================================================================
// prep_audit — enriches another tool's findings with graph context
// ============================================================================

const auditPrSanityCheckDemo: CliScript = {
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
      text: "Found 8 things worth flagging. Graded by blast radius:\n\n• **2 critical** — your `charge()` change hits a hub file with 14 dependents. Worth a second look.\n• **1 concept violation** — direct DB call inside `payment/`, which has a \"no db.transaction\" architectural rule.\n• **5 low-risk** — style nits in leaf files, safe to batch.\n\nI'd only block on the first two. Rest can ship.",
      typewriterDelayMs: 12,
    },
  ],
};

const auditSecurityScanDemo: CliScript = {
  title: 'claude — my-project',
  loop: true,
  loopDelayMs: 5000,
  events: [
    {
      type: 'user_input',
      text: 'security scan flagged 6 things — which actually matter?',
      typingDelayMs: 26,
    },
    { type: 'agent_thinking', durationMs: 600, label: 'Reading scan…' },
    {
      type: 'tool_call',
      tool: 'bash',
      args: 'cat security-scan.json',
      durationMs: 500,
    },
    {
      type: 'tool_result',
      text: '6 findings · CVEs + SAST',
      status: 'success',
    },
    { type: 'agent_thinking', durationMs: 800, label: 'Cross-referencing graph…' },
    {
      type: 'tool_call',
      tool: 'prep_audit',
      args: 'findings=[6]',
      durationMs: 1000,
      statusText: 'Enriching with graph context…',
    },
    {
      type: 'tool_result',
      text: '6 enriched · 1 critical (hub) · 1 reachable · 4 unreachable',
      status: 'success',
    },
    { type: 'pause', durationMs: 300 },
    {
      type: 'agent_output',
      text: "Cross-referenced the 6 findings against your dependency graph:\n\n• **1 critical** — XSS in `api/users.py`'s HTML render path. That file has 23 callers and this one actually reaches user input. Fix first.\n• **1 reachable** — outdated `urllib3` in the worker image. Only matters if workers make outbound HTTP, which `workers/webhook.py` does. Bump it.\n• **4 noise** — in `tests/fixtures/` and seed data, not in the runtime path. Safe to dismiss in scanner config.",
      typewriterDelayMs: 12,
    },
  ],
};

const auditTightenTypesDemo: CliScript = {
  title: 'claude — my-project',
  loop: true,
  loopDelayMs: 5000,
  events: [
    {
      type: 'user_input',
      text: 'tighten up the types in billing/ — mypy strict',
      typingDelayMs: 26,
    },
    { type: 'agent_thinking', durationMs: 600, label: 'Running mypy…' },
    {
      type: 'tool_call',
      tool: 'bash',
      args: 'mypy --strict src/billing/',
      durationMs: 800,
    },
    {
      type: 'tool_result',
      text: '23 errors · 8 files',
      status: 'success',
    },
    { type: 'agent_thinking', durationMs: 800, label: 'Cross-referencing graph…' },
    {
      type: 'tool_call',
      tool: 'prep_audit',
      args: 'findings=[23]',
      durationMs: 1000,
      statusText: 'Enriching with graph context…',
    },
    {
      type: 'tool_result',
      text: '23 enriched · 3 in hub file · 6 on public API surface · 14 internal',
      status: 'success',
    },
    { type: 'pause', durationMs: 300 },
    {
      type: 'agent_output',
      text: "mypy flagged 23 issues across 8 files. Ranked by who touches the code:\n\n• **3 in `billing/invoice.py`** — that's a hub (17 dependents). An untyped `Dict[str, Any]` return hurts every caller. Fix first.\n• **6 on the public `BillingAPI` surface** — consumers in `api/billing.py` and the frontend client rely on these signatures. Worth tight types.\n• **14 internal** — helpers inside `billing/`, safe to batch-fix later.\n\nI'd start with the first group. Want me to draft the changes?",
      typewriterDelayMs: 12,
    },
  ],
};

// ============================================================================
// prep_observe — persistent cross-session memory
// ============================================================================

const observeCachingRecallDemo: CliScript = {
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

const observeInvestigationRecallDemo: CliScript = {
  title: 'claude — my-project',
  loop: true,
  loopDelayMs: 5000,
  events: [
    {
      type: 'user_input',
      text: 'where did we leave off on the cache invalidation investigation?',
      typingDelayMs: 26,
    },
    { type: 'agent_thinking', durationMs: 500 },
    {
      type: 'tool_call',
      tool: 'prep_observe',
      args: 'action="get", query="cache invalidation"',
      durationMs: 800,
      statusText: 'Retrieving observations…',
    },
    {
      type: 'tool_result',
      text: '3 observations · last active 2 weeks ago',
      status: 'success',
    },
    { type: 'pause', durationMs: 300 },
    {
      type: 'agent_output',
      text: "Last note was 2 weeks ago. Working theory: stale entries when keys overlap between `user:X` and `session:X` — a key-prefix collision in Redis.\n\nYou were about to force a collision in staging to reproduce. No follow-up notes, so that repro probably didn't happen. The `cache/keys.py` namespace logic is where the collision would actually manifest. Want to pick it up from there?",
      typewriterDelayMs: 12,
    },
  ],
};

const observeSaveOwnershipDemo: CliScript = {
  title: 'claude — my-project',
  loop: true,
  loopDelayMs: 5000,
  events: [
    {
      type: 'user_input',
      text: 'save a note — payments team owns retries for the stripe sync job',
      typingDelayMs: 26,
    },
    { type: 'agent_thinking', durationMs: 500 },
    {
      type: 'tool_call',
      tool: 'prep_observe',
      args: 'action="save", category="ownership"',
      durationMs: 700,
      statusText: 'Saving observation…',
    },
    {
      type: 'tool_result',
      text: 'Saved #62 · linked to workers/stripe_sync.py + payment/saga_runner.py',
      status: 'success',
    },
    { type: 'pause', durationMs: 300 },
    {
      type: 'agent_output',
      text: "Saved as an ownership note. Linked it to `workers/stripe_sync.py` (the job itself) and `payment/saga_runner.py` (where retries compose).\n\nIf anyone touches either file later, this note resurfaces — so a billing-team dev who wanders in here knows where to route questions before shipping changes.",
      typewriterDelayMs: 12,
    },
  ],
};

// ============================================================================
// prep_concepts — business rationale and architectural constraints
// ============================================================================

const conceptsTransactionRuleDemo: CliScript = {
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
      text: '`payment/` has a hard rule against direct transactions — your team recorded it as *"no db.transaction inside payment/"*.\n\nReason: payments span billing, inventory, and notifications, and a single DB transaction can\'t cover all three. Use the saga runner in `payment/saga_runner.py` — it handles compensating rollbacks for you if something downstream fails.',
      typewriterDelayMs: 12,
    },
  ],
};

const conceptsQueuePitfallsDemo: CliScript = {
  title: 'claude — my-project',
  loop: true,
  loopDelayMs: 5000,
  events: [
    {
      type: 'user_input',
      text: 'any pitfalls before I start messing with the queue?',
      typingDelayMs: 26,
    },
    { type: 'agent_thinking', durationMs: 600 },
    {
      type: 'tool_call',
      tool: 'prep_concepts',
      args: 'action="get", query="queue"',
      durationMs: 900,
      statusText: 'Querying concept store…',
    },
    {
      type: 'tool_result',
      text: '2 concepts · Queue Ordering Invariant · Idempotency Requirement',
      status: 'success',
    },
    { type: 'pause', durationMs: 300 },
    {
      type: 'agent_output',
      text: 'Two rules your team recorded:\n\n• **Queue ordering invariant** — jobs for the same `user_id` must execute in order. If you change dispatch, preserve per-user FIFO.\n• **Idempotency requirement** — handlers must be safe to run twice. Retries can deliver dupes, so `JobHandler.handle()` needs to tolerate that.\n\nBoth are enforced as immune-system antibodies — you\'ll get a polite nudge if new code breaks either one.',
      typewriterDelayMs: 12,
    },
  ],
};

const conceptsBuildRefundDemo: CliScript = {
  title: 'claude — my-project',
  loop: true,
  loopDelayMs: 5000,
  events: [
    {
      type: 'user_input',
      text: 'add a handler to refund canceled subscriptions',
      typingDelayMs: 26,
    },
    { type: 'agent_thinking', durationMs: 700 },
    {
      type: 'tool_call',
      tool: 'prep_concepts',
      args: 'action="get", query="payment refund"',
      durationMs: 900,
      statusText: 'Checking constraints…',
    },
    {
      type: 'tool_result',
      text: '2 concepts · Payment Saga · Audit Log Required',
      status: 'success',
    },
    { type: 'pause', durationMs: 300 },
    {
      type: 'agent_output',
      text: "Before writing code, two team-recorded rules apply to `payment/`:\n\n• **Payment Saga** — no direct DB transactions. Refunds have to go through `saga_runner.py` so rollback is handled if the Stripe call fails mid-flight.\n• **Audit Log Required** — every monetary write needs an entry in `audit/events.py` with `actor`, `amount`, `reason`.\n\nSo the shape is: compose a `RefundSaga`, call `saga.run()`, emit the audit event on success. Ready to draft it?",
      typewriterDelayMs: 12,
    },
  ],
};

// ============================================================================
// IDE — agentic edit demos
// ============================================================================

const ideDoubleSubmitFixDemo: CliScript = {
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

const ideLoadingSkeletonDemo: CliScript = {
  title: 'prep-ide-demo',
  loop: true,
  loopDelayMs: 5000,
  events: [
    { type: 'pause', durationMs: 600 },
    {
      type: 'user_input',
      text: 'add a loading state to the Dashboard — match how other pages handle it',
      typingDelayMs: 26,
    },
    { type: 'agent_thinking', durationMs: 900 },
    {
      type: 'tool_call',
      tool: 'prep_search',
      args: '"loading skeleton pattern"',
      durationMs: 900,
    },
    {
      type: 'tool_result',
      text: 'ReportsPage.tsx + BillingPage.tsx use <Skeleton /> from @prep/ui',
      status: 'success',
    },
    {
      type: 'agent_output',
      text: "Other pages use `<Skeleton />` from `@prep/ui` while data loads. I'll match that pattern on the Dashboard.",
      typewriterDelayMs: 16,
    },
    {
      type: 'file_open',
      filePath: 'src/pages/Dashboard.tsx',
      language: 'typescript',
      content: `import { useState, useEffect } from 'react';
import { fetchMetrics, type Metric } from '@/api/metrics';
import { MetricCard } from '@/components/MetricCard';

export function Dashboard() {
  const [metrics, setMetrics] = useState<Metric[] | null>(null);

  useEffect(() => {
    fetchMetrics().then(setMetrics);
  }, []);

  return (
    <div className="grid gap-4">
      {metrics?.map((m) => (
        <MetricCard key={m.id} metric={m} />
      ))}
    </div>
  );
}`,
      durationMs: 1000,
    },
    { type: 'agent_thinking', durationMs: 500 },
    {
      type: 'code_edit',
      filePath: 'src/pages/Dashboard.tsx',
      durationMs: 1800,
      newContent: `import { useState, useEffect } from 'react';
import { Skeleton } from '@prep/ui';
import { fetchMetrics, type Metric } from '@/api/metrics';
import { MetricCard } from '@/components/MetricCard';

export function Dashboard() {
  const [metrics, setMetrics] = useState<Metric[] | null>(null);

  useEffect(() => {
    fetchMetrics().then(setMetrics);
  }, []);

  if (!metrics) {
    return (
      <div className="grid gap-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-24 rounded-md" />
        ))}
      </div>
    );
  }

  return (
    <div className="grid gap-4">
      {metrics.map((m) => (
        <MetricCard key={m.id} metric={m} />
      ))}
    </div>
  );
}`,
    },
    {
      type: 'agent_output',
      text: "Updated `Dashboard.tsx` — same `<Skeleton />` pattern as Reports and Billing. Renders 4 placeholder rows while `metrics` is loading, swaps to the real cards once the fetch resolves.",
      typewriterDelayMs: 14,
    },
    { type: 'pause', durationMs: 3500 },
  ],
};

const ideAddCsvExportDemo: CliScript = {
  title: 'prep-ide-demo',
  loop: true,
  loopDelayMs: 5000,
  events: [
    { type: 'pause', durationMs: 600 },
    {
      type: 'user_input',
      text: 'add a csv export button to the users table',
      typingDelayMs: 26,
    },
    { type: 'agent_thinking', durationMs: 900 },
    {
      type: 'tool_call',
      tool: 'prep_search',
      args: '"csv export helper"',
      durationMs: 900,
    },
    {
      type: 'tool_result',
      text: 'ReportsTable.tsx uses exportToCsv() from @/lib/csv',
      status: 'success',
    },
    {
      type: 'agent_output',
      text: "There's already an `exportToCsv()` helper in `@/lib/csv` — the Reports table uses it. I'll reuse the same helper so the behavior matches.",
      typewriterDelayMs: 16,
    },
    {
      type: 'file_open',
      filePath: 'src/components/UsersTable.tsx',
      language: 'typescript',
      content: `import { useState, useEffect } from 'react';
import { fetchUsers, type User } from '@/api/users';

export function UsersTable() {
  const [users, setUsers] = useState<User[]>([]);

  useEffect(() => {
    fetchUsers().then(setUsers);
  }, []);

  return (
    <table className="w-full">
      <thead>
        <tr><th>Name</th><th>Email</th><th>Role</th></tr>
      </thead>
      <tbody>
        {users.map((u) => (
          <tr key={u.id}>
            <td>{u.name}</td>
            <td>{u.email}</td>
            <td>{u.role}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}`,
      durationMs: 1000,
    },
    { type: 'agent_thinking', durationMs: 500 },
    {
      type: 'code_edit',
      filePath: 'src/components/UsersTable.tsx',
      durationMs: 1800,
      newContent: `import { useState, useEffect } from 'react';
import { Button } from '@prep/ui';
import { exportToCsv } from '@/lib/csv';
import { fetchUsers, type User } from '@/api/users';

export function UsersTable() {
  const [users, setUsers] = useState<User[]>([]);

  useEffect(() => {
    fetchUsers().then(setUsers);
  }, []);

  return (
    <div>
      <div className="mb-3 flex justify-end">
        <Button
          variant="secondary"
          onClick={() => exportToCsv('users.csv', users)}
          disabled={users.length === 0}
        >
          Export CSV
        </Button>
      </div>
      <table className="w-full">
        <thead>
          <tr><th>Name</th><th>Email</th><th>Role</th></tr>
        </thead>
        <tbody>
          {users.map((u) => (
            <tr key={u.id}>
              <td>{u.name}</td>
              <td>{u.email}</td>
              <td>{u.role}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}`,
    },
    {
      type: 'agent_output',
      text: "Added the export button using `exportToCsv()` from `@/lib/csv` — same helper the Reports table uses. Disables when there's nothing to export.",
      typewriterDelayMs: 14,
    },
    { type: 'pause', durationMs: 3500 },
  ],
};

// ============================================================================
// Sequence exports — for slots that cycle back-to-back through 3 picks.
// Use these on the home page via <AnimatedCLI scripts={prepDemos} />.
// ============================================================================

export const prepDemos: CliScript[] = [
  prepRateLimitingDemo,
  prepTldrOverviewDemo,
  prepBuildWebhookDemo,
];

export const prepSearchDemos: CliScript[] = [
  searchRetryReuseDemo,
  searchMaxConnectionsDemo,
  searchBuildWorkerDemo,
];

export const prepImpactDemos: CliScript[] = [
  impactDeleteUnusedDemo,
  impactExtractServiceDemo,
  impactAsyncMigrationDemo,
];

export const prepAuditDemos: CliScript[] = [
  auditPrSanityCheckDemo,
  auditSecurityScanDemo,
  auditTightenTypesDemo,
];

export const prepObserveDemos: CliScript[] = [
  observeCachingRecallDemo,
  observeInvestigationRecallDemo,
  observeSaveOwnershipDemo,
];

export const prepConceptsDemos: CliScript[] = [
  conceptsTransactionRuleDemo,
  conceptsQueuePitfallsDemo,
  conceptsBuildRefundDemo,
];

export const ideDemos: CliScript[] = [
  ideDoubleSubmitFixDemo,
  ideLoadingSkeletonDemo,
  ideAddCsvExportDemo,
];

// ============================================================================
// Single-script aliases — for surfaces that only show one demo (sub-pages,
// Storybook stories). Each points to the first pick of its sequence.
// ============================================================================

export const prepOverviewDemo: CliScript = prepDemos[0];
export const prepSearchDemo: CliScript = prepSearchDemos[0];
export const prepImpactDemo: CliScript = prepImpactDemos[0];
export const prepAuditDemo: CliScript = prepAuditDemos[0];
export const prepObserveDemo: CliScript = prepObserveDemos[0];
export const prepConceptsDemo: CliScript = prepConceptsDemos[0];
export const ideDemoScript: CliScript = ideDemos[0];
