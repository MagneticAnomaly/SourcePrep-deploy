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

const prepTldrOverview: CliScript = {
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

const prepBuildWebhook: CliScript = {
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

const searchMaxConnections: CliScript = {
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

const searchBuildWorker: CliScript = {
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

const impactExtractService: CliScript = {
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

const impactAsyncMigration: CliScript = {
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
      text: "Found 8 things worth flagging. Graded by blast radius:\n\n• **2 critical** — your `charge()` change hits a hub file with 14 dependents. Worth a second look.\n• **1 concept violation** — direct DB call inside `payment/`, which has a \"no db.transaction\" architectural rule.\n• **5 low-risk** — style nits in leaf files, safe to batch.\n\nI'd only block on the first two. Rest can ship.",
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
      text: "Went through the diff and flagged 11 things. Ranked by blast radius:\n\n• **1 critical** — missing `await` in `payment/charge.py`, and that file has 14 downstream callers.\n• **2 concept violations** — direct DB writes inside `payment/` (your \"no db.transaction\" rule).\n• **8 low-risk** — naming, minor typing gaps.\n\nI'd fix the critical + concept ones before pushing. Low-risk can follow up.",
      typewriterDelayMs: 12,
    },
  ],
};

const auditSecurityScan: CliScript = {
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

const auditTightenTypes: CliScript = {
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
      text: "Saved. Linked it to the 4 files currently using ad-hoc validation — `api/users.py`, `api/billing.py`, `api/webhooks.py`, `workers/ingest.py`.\n\nIf any of those get touched later, this note resurfaces automatically, so whoever picks the work up has the context to weigh a migration to zod.",
      typewriterDelayMs: 12,
    },
  ],
};

const observeInvestigationRecall: CliScript = {
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

const observeSaveOwnership: CliScript = {
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
      text: '`payment/` has a hard rule against direct transactions — your team recorded it as *"no db.transaction inside payment/"*.\n\nReason: payments span billing, inventory, and notifications, and a single DB transaction can\'t cover all three. Use the saga runner in `payment/saga_runner.py` — it handles compensating rollbacks for you if something downstream fails.',
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
      text: 'Recorded as *"Payment Saga Rule"* — assertion `no db.transaction inside payment/`, anchored on `payment/saga_runner.py` and `payment/charge.py`.\n\nFrom now on, any new `db.transaction` import inside `payment/` gets flagged by the immune system when anyone using the graph looks at that area. Future-you gets a polite alarm instead of a surprise.',
      typewriterDelayMs: 12,
    },
  ],
};

const conceptsQueueGotchas: CliScript = {
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

const conceptsBuildRefund: CliScript = {
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

const ideLoadingSkeleton: CliScript = {
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

const ideAddCsvExport: CliScript = {
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

const ideButtonGradientVariant: CliScript = {
  title: 'prep-ide-demo',
  loop: true,
  loopDelayMs: 5000,
  events: [
    { type: 'pause', durationMs: 600 },
    {
      type: 'user_input',
      text: 'match the figma — primary CTA should have the gradient + glow',
      typingDelayMs: 26,
    },
    { type: 'agent_thinking', durationMs: 900 },
    {
      type: 'tool_call',
      tool: 'prep_impact',
      args: '"Button"',
      durationMs: 1000,
      statusText: 'Tracing callers…',
    },
    {
      type: 'tool_result',
      text: '47 callers · 18 files · used in every CTA across the app',
      status: 'success',
    },
    {
      type: 'agent_output',
      text: "`Button` has 47 callers — swapping the default style would affect every CTA, including form inputs and settings buttons that probably shouldn't glow. Safer: add a new `variant='glow'` and opt the hero CTAs in.",
      typewriterDelayMs: 16,
    },
    {
      type: 'file_open',
      filePath: 'src/components/ui/Button.tsx',
      language: 'typescript',
      content: `import { cva } from 'class-variance-authority';

const button = cva(
  'inline-flex items-center justify-center rounded-md font-medium transition',
  {
    variants: {
      variant: {
        primary: 'bg-primary text-primary-foreground hover:bg-primary/90',
        secondary: 'bg-secondary text-secondary-foreground hover:bg-secondary/80',
      },
      size: {
        sm: 'h-8 px-3 text-sm',
        md: 'h-10 px-4',
        lg: 'h-12 px-6 text-lg',
      },
    },
    defaultVariants: { variant: 'primary', size: 'md' },
  },
);

export function Button({ className, variant, size, ...props }) {
  return <button className={button({ variant, size, className })} {...props} />;
}`,
      durationMs: 1000,
    },
    { type: 'agent_thinking', durationMs: 500 },
    {
      type: 'code_edit',
      filePath: 'src/components/ui/Button.tsx',
      durationMs: 1800,
      newContent: `import { cva } from 'class-variance-authority';

const button = cva(
  'inline-flex items-center justify-center rounded-md font-medium transition',
  {
    variants: {
      variant: {
        primary: 'bg-primary text-primary-foreground hover:bg-primary/90',
        secondary: 'bg-secondary text-secondary-foreground hover:bg-secondary/80',
        glow: 'bg-gradient-to-br from-violet-500 to-fuchsia-500 text-white shadow-lg shadow-violet-500/30 hover:shadow-violet-500/50 hover:brightness-110',
      },
      size: {
        sm: 'h-8 px-3 text-sm',
        md: 'h-10 px-4',
        lg: 'h-12 px-6 text-lg',
      },
    },
    defaultVariants: { variant: 'primary', size: 'md' },
  },
);

export function Button({ className, variant, size, ...props }) {
  return <button className={button({ variant, size, className })} {...props} />;
}`,
    },
    {
      type: 'agent_output',
      text: "Added `variant='glow'` — violet→fuchsia gradient with a soft shadow that lifts on hover. Default button stays untouched, so the 47 existing callers don't move. Use it on the hero CTAs and the figma matches.",
      typewriterDelayMs: 14,
    },
    { type: 'pause', durationMs: 3500 },
  ],
};

const ideColorTokensRule: CliScript = {
  title: 'prep-ide-demo',
  loop: true,
  loopDelayMs: 5000,
  events: [
    { type: 'pause', durationMs: 600 },
    {
      type: 'user_input',
      text: 'this stat card looks ad-hoc — make it on-brand',
      typingDelayMs: 26,
    },
    { type: 'agent_thinking', durationMs: 900 },
    {
      type: 'tool_call',
      tool: 'prep_concepts',
      args: 'action="get", query="design tokens"',
      durationMs: 1000,
      statusText: 'Querying concept store…',
    },
    {
      type: 'tool_result',
      text: 'Concept: "Token-Only Colors" · constraint · 12 anchors',
      status: 'success',
    },
    {
      type: 'agent_output',
      text: "Your team has a constraint on file — *Token-Only Colors*: no raw hex, only semantic tokens. We've got `bg-surface`, `text-primary`, `text-muted`, `border-subtle`, `text-success` — all of which match what's in this card. Swapping them in.",
      typewriterDelayMs: 16,
    },
    {
      type: 'file_open',
      filePath: 'src/components/dashboard/StatCard.tsx',
      language: 'typescript',
      content: `interface StatCardProps {
  label: string;
  value: string | number;
  delta?: string;
}

export function StatCard({ label, value, delta }: StatCardProps) {
  return (
    <div className="rounded-xl bg-[#fafafa] border border-[#e5e7eb] p-5">
      <p className="text-xs text-[#6b7280] uppercase tracking-wide">{label}</p>
      <p className="mt-2 text-3xl font-semibold text-[#111827]">{value}</p>
      {delta && (
        <p className="mt-1 text-sm text-[#10b981]">{delta}</p>
      )}
    </div>
  );
}`,
      durationMs: 1000,
    },
    { type: 'agent_thinking', durationMs: 500 },
    {
      type: 'code_edit',
      filePath: 'src/components/dashboard/StatCard.tsx',
      durationMs: 1800,
      newContent: `interface StatCardProps {
  label: string;
  value: string | number;
  delta?: string;
}

export function StatCard({ label, value, delta }: StatCardProps) {
  return (
    <div className="rounded-xl bg-surface border border-subtle p-5">
      <p className="text-xs text-muted uppercase tracking-wide">{label}</p>
      <p className="mt-2 text-3xl font-semibold text-primary">{value}</p>
      {delta && (
        <p className="mt-1 text-sm text-success">{delta}</p>
      )}
    </div>
  );
}`,
    },
    {
      type: 'agent_output',
      text: 'Same look, every color now a semantic token. Dark mode works automatically and the next palette tweak rolls through every card without touching this file. The constraint stays clean — no new raw hex.',
      typewriterDelayMs: 14,
    },
    { type: 'pause', durationMs: 3500 },
  ],
};

const ideEmptyStateRecall: CliScript = {
  title: 'prep-ide-demo',
  loop: true,
  loopDelayMs: 5000,
  events: [
    { type: 'pause', durationMs: 600 },
    {
      type: 'user_input',
      text: 'projects list needs an empty state — what did we land on for those?',
      typingDelayMs: 26,
    },
    { type: 'agent_thinking', durationMs: 800 },
    {
      type: 'tool_call',
      tool: 'prep_observe',
      args: 'action="get", query="empty state pattern"',
      durationMs: 900,
      statusText: 'Retrieving observations…',
    },
    {
      type: 'tool_result',
      text: '1 observation · last active 6 weeks ago · 2 anchors',
      status: 'success',
    },
    {
      type: 'agent_output',
      text: "Found the note from when you and Maya were working through these. The pattern: small icon on top, big heading, supporting line, single primary CTA. Reports and Billing already use it — I'll match it here.",
      typewriterDelayMs: 16,
    },
    {
      type: 'file_open',
      filePath: 'src/pages/Projects.tsx',
      language: 'typescript',
      content: `import { useProjects } from '@/hooks/useProjects';
import { ProjectCard } from '@/components/ProjectCard';

export function Projects() {
  const { projects } = useProjects();

  if (projects.length === 0) {
    return null;
  }

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
      {projects.map((p) => (
        <ProjectCard key={p.id} project={p} />
      ))}
    </div>
  );
}`,
      durationMs: 1000,
    },
    { type: 'agent_thinking', durationMs: 500 },
    {
      type: 'code_edit',
      filePath: 'src/pages/Projects.tsx',
      durationMs: 1800,
      newContent: `import { EmptyState } from '@prep/ui';
import { FolderOpenIcon } from 'lucide-react';
import { useProjects } from '@/hooks/useProjects';
import { ProjectCard } from '@/components/ProjectCard';
import { useNewProjectModal } from '@/state/modals';

export function Projects() {
  const { projects } = useProjects();
  const newProject = useNewProjectModal();

  if (projects.length === 0) {
    return (
      <EmptyState
        icon={<FolderOpenIcon className="h-10 w-10 text-muted" />}
        title="No projects yet"
        description="Spin up your first project to start indexing repos and sharing context with your team."
        action={{ label: 'Create your first project', onClick: newProject.open }}
      />
    );
  }

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
      {projects.map((p) => (
        <ProjectCard key={p.id} project={p} />
      ))}
    </div>
  );
}`,
    },
    {
      type: 'agent_output',
      text: "Added the empty state — same shape as Reports and Billing. Folder icon, 'No projects yet', helper line, primary CTA wired into the existing new-project modal. Visual rhythm matches the rest of the app.",
      typewriterDelayMs: 14,
    },
    { type: 'pause', durationMs: 3500 },
  ],
};

const ideFormA11yAudit: CliScript = {
  title: 'prep-ide-demo',
  loop: true,
  loopDelayMs: 5000,
  events: [
    { type: 'pause', durationMs: 600 },
    {
      type: 'user_input',
      text: 'quick a11y pass on the signup form before we ship?',
      typingDelayMs: 26,
    },
    { type: 'agent_thinking', durationMs: 800, label: 'Running axe…' },
    {
      type: 'tool_call',
      tool: 'bash',
      args: 'npx axe src/components/SignupForm.tsx',
      durationMs: 700,
    },
    {
      type: 'tool_result',
      text: '4 issues · 1 critical · 3 minor',
      status: 'success',
    },
    { type: 'agent_thinking', durationMs: 600, label: 'Cross-referencing graph…' },
    {
      type: 'tool_call',
      tool: 'prep_audit',
      args: 'findings=[4]',
      durationMs: 1000,
      statusText: 'Enriching with graph context…',
    },
    {
      type: 'tool_result',
      text: '4 enriched · 1 in shared form primitive (high blast) · 3 local',
      status: 'success',
    },
    {
      type: 'agent_output',
      text: "axe flagged 4. Ranked by what they touch:\n\n• **Critical** — `<TextField />` is missing the label↔input association. That's a shared primitive used in 8 forms, so fixing it once lifts a11y across all of them.\n• **3 minor** — local to this form (helper-text contrast, missing `aria-describedby`, focus ring). Quick batch.\n\nStarting with the shared one.",
      typewriterDelayMs: 14,
    },
    {
      type: 'file_open',
      filePath: 'src/components/ui/TextField.tsx',
      language: 'typescript',
      content: `interface TextFieldProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: string;
  error?: string;
}

export function TextField({ label, value, onChange, type = 'text', error }: TextFieldProps) {
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-sm font-medium text-primary">{label}</span>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="rounded-md border border-subtle px-3 py-2"
      />
      {error && <span className="text-xs text-danger">{error}</span>}
    </div>
  );
}`,
      durationMs: 1000,
    },
    { type: 'agent_thinking', durationMs: 500 },
    {
      type: 'code_edit',
      filePath: 'src/components/ui/TextField.tsx',
      durationMs: 1800,
      newContent: `import { useId } from 'react';

interface TextFieldProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: string;
  error?: string;
}

export function TextField({ label, value, onChange, type = 'text', error }: TextFieldProps) {
  const id = useId();
  const errorId = error ? \`\${id}-error\` : undefined;
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-sm font-medium text-primary">{label}</label>
      <input
        id={id}
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-invalid={Boolean(error)}
        aria-describedby={errorId}
        className="rounded-md border border-subtle px-3 py-2"
      />
      {error && <span id={errorId} className="text-xs text-danger">{error}</span>}
    </div>
  );
}`,
    },
    {
      type: 'agent_output',
      text: "Wrapped the label as a real `<label htmlFor>`, gave the input a stable id via `useId()`, and wired `aria-describedby` to the error. One change, but it lifts a11y across all 8 forms using `<TextField />`.",
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
  {
    id: 'prep-tldr-overview',
    tool: 'prep',
    label: 'tldr request — high-level orientation',
    note: 'Extremely common real-world prompt. "tldr" signals the dev wants the shape, not a tour. prep gives back the one-screen map.',
    script: prepTldrOverview,
  },
  {
    id: 'prep-build-webhook',
    tool: 'prep',
    label: 'Build instruction — "add a new webhook"',
    note: 'Imperative build prompt. prep fires for orientation first — agent finds the existing handler pattern so the new code matches instead of inventing a one-off.',
    script: prepBuildWebhook,
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
  {
    id: 'search-max-connections',
    tool: 'prep_search',
    label: 'Error message → source',
    note: 'Pasting an error string is the most common real AI-assistant prompt. Search jumps straight to the raise site without the dev grepping log files.',
    script: searchMaxConnections,
  },
  {
    id: 'search-build-worker',
    tool: 'prep_search',
    label: 'Build instruction — "build a new X like the existing ones"',
    note: 'Imperative "build a worker". Search finds the ScheduledWorker base class + the five workers that already extend it, so the new one inherits RetryPolicy for free.',
    script: searchBuildWorker,
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
  {
    id: 'impact-extract-service',
    tool: 'prep_impact',
    label: 'Feasibility check for extraction',
    note: '"Thinking about X" — pre-commitment prompt. Impact returns the blast radius *before* the dev starts, so they can scope the work (or back out) with real data.',
    script: impactExtractService,
  },
  {
    id: 'impact-async-migration',
    tool: 'prep_impact',
    label: 'Build instruction — change across callers',
    note: 'Imperative "make X async". Impact surfaces the 4 sync callers that can\'t just await — scopes the real work (upgrade the routes) before any code gets written.',
    script: impactAsyncMigration,
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
  {
    id: 'audit-security-scan',
    tool: 'prep_audit',
    label: 'Triaging scanner output (reachability)',
    note: 'External scanner findings are the native input for prep_audit. Enrichment adds reachability + hub status so the dev knows which of 6 findings actually matter.',
    script: auditSecurityScan,
  },
  {
    id: 'audit-tighten-types',
    tool: 'prep_audit',
    label: 'Build instruction — tighten types across a module',
    note: 'Imperative cleanup task. Agent runs mypy --strict, prep_audit ranks the 23 errors by hub status + public-surface exposure so the work starts where it matters most.',
    script: auditTightenTypes,
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
  {
    id: 'observe-investigation-recall',
    tool: 'prep_observe',
    label: '"Where did we leave off?"',
    note: 'Mid-task context recovery. Observe returns the prior investigation trail — hypotheses tried, what was ruled out — so work resumes instead of restarts.',
    script: observeInvestigationRecall,
  },
  {
    id: 'observe-save-ownership',
    tool: 'prep_observe',
    label: 'Build instruction — "save an ownership note"',
    note: 'Imperative save with an explicit "save a note —" prefix. Observe auto-links to both files involved, so the note surfaces for anyone touching either side later.',
    script: observeSaveOwnership,
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
  {
    id: 'concepts-queue-gotchas',
    tool: 'prep_concepts',
    label: '"Any pitfalls before I touch X?"',
    note: 'Risk-probing prompt devs actually say. Concepts returns the pile of team-recorded rules for the queue module before the dev has to learn them the hard way.',
    script: conceptsQueueGotchas,
  },
  {
    id: 'concepts-build-refund',
    tool: 'prep_concepts',
    label: 'Build instruction — preflight before writing new code',
    note: 'Imperative "add a handler for X" inside a constrained module. Concepts fires preflight so the agent shapes the new code around the saga + audit-log rules instead of violating them.',
    script: conceptsBuildRefund,
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
  {
    id: 'ide-loading-skeleton',
    tool: 'ide',
    label: 'UI pattern matching across pages',
    note: '"Match how other pages do it" is a common consistency prompt. Search surfaces the shared skeleton component so the edit follows existing convention instead of inventing one.',
    script: ideLoadingSkeleton,
  },
  {
    id: 'ide-add-csv-export',
    tool: 'ide',
    label: 'Build instruction — add a new feature',
    note: 'Imperative "add a CSV export button". Search finds the existing `exportToCsv()` helper so the new button reuses it instead of rolling a parallel implementation.',
    script: ideAddCsvExport,
  },
  {
    id: 'ide-button-gradient-variant',
    tool: 'ide',
    label: 'Vibe — figma-matched gradient CTA (impact-aware)',
    note: 'Designer prompt referencing figma. prep_impact catches that Button is a hub (47 callers) and steers the agent toward adding a `variant=\'glow\'` instead of mutating the default — figma matches without breaking 47 unrelated buttons.',
    script: ideButtonGradientVariant,
  },
  {
    id: 'ide-color-tokens-rule',
    tool: 'ide',
    label: 'Vibe — on-brand colors via design-token constraint',
    note: 'Casual "make this on-brand" prompt. prep_concepts surfaces the team\'s "Token-Only Colors" rule, agent swaps raw hex for semantic tokens. Demonstrates concept-driven design enforcement.',
    script: ideColorTokensRule,
  },
  {
    id: 'ide-empty-state-recall',
    tool: 'ide',
    label: 'Vibe — recalling a prior design decision',
    note: '"What did we land on for empty states?" — design-memory prompt. prep_observe returns the prior design pattern, agent applies it. Shows observe in a non-engineering frame.',
    script: ideEmptyStateRecall,
  },
  {
    id: 'ide-form-a11y-audit',
    tool: 'ide',
    label: 'Vibe — a11y pass with hub-aware ranking',
    note: '"Quick a11y pass before we ship?" — designer/PM-flavored prompt. axe finds 4 issues; prep_audit ranks by hub-component status, so the one fix in `<TextField />` lifts a11y across 8 forms.',
    script: ideFormA11yAudit,
  },
];
