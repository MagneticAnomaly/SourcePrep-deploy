import type { CliScript } from './cli-types';

/**
 * Demo: prep — Ambient structural context (no query needed)
 * Shows the "instant orientation" value prop.
 */
export const prepOverviewDemo: CliScript = {
  title: 'claude — my-project',
  loop: true,
  loopDelayMs: 5000,
  events: [
    {
      type: 'user_input',
      text: 'give me an overview of this project',
      typingDelayMs: 28,
    },
    { type: 'agent_thinking', durationMs: 600 },
    {
      type: 'tool_call',
      tool: 'prep',
      args: '',
      durationMs: 900,
      statusText: 'Loading structural context…',
    },
    {
      type: 'tool_result',
      text: 'Project: my-project (247 files, 1,892 graph nodes)\n3 modules · 5 hub files · 2 focus areas',
      status: 'success',
    },
    { type: 'pause', durationMs: 300 },
    {
      type: 'agent_output',
      text: 'This is a FastAPI application with three modules:\n\n• **api/** — REST endpoints (hub: auth/middleware.py)\n• **services/** — Business logic (hub: payment.py, 23 dependents)\n• **models/** — SQLAlchemy ORM definitions\n\nThe most-connected file is `services/payment.py`. Your focus areas are `api/` and `services/`.',
      typewriterDelayMs: 12,
    },
  ],
};

/**
 * Demo: prep_impact — Blast radius before you break things
 */
export const prepImpactDemo: CliScript = {
  title: 'claude — my-project',
  loop: true,
  loopDelayMs: 5000,
  events: [
    {
      type: 'user_input',
      text: 'what breaks if I change PaymentService.charge()?',
      typingDelayMs: 25,
    },
    { type: 'agent_thinking', durationMs: 600 },
    {
      type: 'tool_call',
      tool: 'prep_impact',
      args: '"services/payment.py"',
      durationMs: 1000,
      statusText: 'Tracing dependents…',
    },
    {
      type: 'tool_result',
      text: '3 direct dependents · 7 transitive\ncheckout/handler.py · billing/subscription.py · tests/test_payment.py',
      status: 'success',
    },
    { type: 'pause', durationMs: 300 },
    {
      type: 'agent_output',
      text: 'Changing `charge()` directly affects:\n\n• `CheckoutHandler.process()` — calls charge with amount + currency\n• `SubscriptionBilling.renew()` — passes a stored payment method\n• 4 test cases in `test_payment.py`\n\nSafest approach: add the new parameter with a default value.',
      typewriterDelayMs: 12,
    },
  ],
};

/**
 * Demo: prep_audit — Enriches linter/audit findings with structural context
 */
export const prepAuditDemo: CliScript = {
  title: 'claude — my-project',
  loop: true,
  loopDelayMs: 5000,
  events: [
    {
      type: 'user_input',
      text: 'I ran ruff and semgrep — can you enrich these findings with structural context?',
      typingDelayMs: 22,
    },
    { type: 'agent_thinking', durationMs: 700 },
    {
      type: 'tool_call',
      tool: 'prep_audit',
      args: 'findings=[{file, line, message, severity}]',
      durationMs: 1200,
      statusText: 'Enriching 12 findings with graph context…',
    },
    {
      type: 'tool_result',
      text: '12 findings enriched\n3 critical (hub files, 15+ dependents)\n2 in import cycles · 7 low-risk',
      status: 'success',
    },
    { type: 'pause', durationMs: 300 },
    {
      type: 'agent_output',
      text: 'Enriched your lint results with structural context:\n\n• **3 critical** — in hub files with 15+ downstream dependents. Fix these first.\n• **2 moderate** — caught in the `auth ↔ users` import cycle (coupling: 0.87)\n• **7 low-risk** — leaf files with no dependents, safe to batch-fix\n\nI can output enriched SARIF for your CI pipeline too.',
      typewriterDelayMs: 12,
    },
  ],
};

/**
 * Demo: prep_search — Semantic code search with structural expansion
 */
export const prepSearchDemo: CliScript = {
  title: 'claude — my-project',
  loop: true,
  loopDelayMs: 5000,
  events: [
    {
      type: 'user_input',
      text: 'how does authentication handle expired tokens?',
      typingDelayMs: 30,
    },
    { type: 'agent_thinking', durationMs: 800, label: 'Thinking…' },
    {
      type: 'tool_call',
      tool: 'prep_search',
      args: '"expired token middleware"',
      durationMs: 1200,
      statusText: 'Searching with structural expansion…',
    },
    {
      type: 'tool_result',
      text: 'Found 4 chunks (1,842 tokens)\nauth/middleware.py · auth/token_service.py · tests/test_auth.py',
      status: 'success',
    },
    { type: 'pause', durationMs: 300 },
    {
      type: 'agent_output',
      text: 'Token expiration works in three stages:\n\n1. `TokenService.validate()` checks the JWT `exp` claim\n2. If expired, `AuthMiddleware` calls `refresh_pair()`\n3. A new access token is issued; the old refresh token is rotated\n\nThe refresh window is configurable via `AUTH_REFRESH_WINDOW_SECONDS`.',
      typewriterDelayMs: 12,
    },
  ],
};

/**
 * Demo: prep_observe — Persistent cross-session memory
 */
export const prepObserveDemo: CliScript = {
  title: 'claude — my-project',
  loop: true,
  loopDelayMs: 5000,
  events: [
    {
      type: 'user_input',
      text: 'remember that we chose JWT over session cookies for the mobile API',
      typingDelayMs: 25,
    },
    { type: 'agent_thinking', durationMs: 500 },
    {
      type: 'tool_call',
      tool: 'prep_observe',
      args: 'action="save", category="decision"',
      durationMs: 600,
      statusText: 'Saving observation…',
    },
    {
      type: 'tool_result',
      text: 'Saved observation #42\nLinked to: auth/token_service.py, api/mobile.py\nCategory: decision',
      status: 'success',
    },
    { type: 'pause', durationMs: 800 },
    {
      type: 'user_input',
      text: 'what decisions did we make about auth?',
      typingDelayMs: 28,
    },
    { type: 'agent_thinking', durationMs: 400 },
    {
      type: 'tool_call',
      tool: 'prep_observe',
      args: 'action="get", query="auth"',
      durationMs: 500,
      statusText: 'Retrieving observations…',
    },
    {
      type: 'tool_result',
      text: '2 observations\n#42 JWT over session cookies for mobile API (active)\n#38 Rate limiting on /auth endpoints after incident (active)',
      status: 'success',
    },
    { type: 'pause', durationMs: 200 },
    {
      type: 'agent_output',
      text: 'Two auth decisions on record:\n\n• **JWT over session cookies** — chosen for the mobile API (linked to `token_service.py`)\n• **Rate limiting on /auth** — added after an incident (linked to `auth/middleware.py`)\n\nBoth are still active. If the linked files change, these get flagged [STALE] so you know to re-evaluate.',
      typewriterDelayMs: 12,
    },
  ],
};

/**
 * Demo: prep_concepts — Business rationale and design decisions
 */
export const prepConceptsDemo: CliScript = {
  title: 'claude — my-project',
  loop: true,
  loopDelayMs: 5000,
  events: [
    {
      type: 'user_input',
      text: 'why does the payment module use a saga pattern instead of direct DB transactions?',
      typingDelayMs: 22,
    },
    { type: 'agent_thinking', durationMs: 600 },
    {
      type: 'tool_call',
      tool: 'prep_concepts',
      args: 'action="get", query="payment saga"',
      durationMs: 800,
      statusText: 'Querying concept store…',
    },
    {
      type: 'tool_result',
      text: 'Concept: "Payment Saga Architecture"\nCategory: architecture\nAssertion: payment/ must not import db.transaction directly\nAnchors: services/payment.py, services/saga_runner.py',
      status: 'success',
    },
    { type: 'pause', durationMs: 300 },
    {
      type: 'agent_output',
      text: 'The payment module uses a saga pattern because:\n\n• **Cross-service coordination** — payments span billing, inventory, and notifications. A single DB transaction can\'t cover all three.\n• **Compensating actions** — if inventory reservation fails after charge, the saga auto-refunds.\n• **Constraint:** `payment/` must never import `db.transaction` directly — RunPrep will flag violations via the immune system.\n\nThis concept was recorded by your team and linked to `saga_runner.py`.',
      typewriterDelayMs: 12,
    },
  ],
};

/**
 * Demo: Agent IDE operations — shows RunPrep powering an agentic edit
 */
export const ideDemoScript: CliScript = {
  title: 'prep-ide-demo',
  loop: true,
  loopDelayMs: 5000,
  events: [
    { type: 'pause', durationMs: 800 },
    { type: 'user_input', text: 'Add real-time status updates to the pipeline dashboard', typingDelayMs: 28 },
    { type: 'agent_thinking', durationMs: 1200 },
    { type: 'tool_call', tool: 'prep', args: '', durationMs: 700 },
    { type: 'tool_result', text: '412 files · 3 modules · hub: PipelineService.ts', status: 'success' },
    { type: 'tool_call', tool: 'prep_search', args: '"pipeline dashboard component"', durationMs: 1000 },
    { type: 'tool_result', text: 'Found PipelineDashboard.tsx (4 dependents)', status: 'success' },
    { type: 'agent_output', text: 'Found `PipelineDashboard.tsx`. I\'ll add a WebSocket subscription for live status updates.', typewriterDelayMs: 18 },
    { type: 'file_open', filePath: 'src/components/PipelineDashboard.tsx', language: 'typescript', content: `import { useState } from 'react';

export function PipelineDashboard() {
  const [status, setStatus] = useState('idle');

  return (
    <div className="p-4">
      <h2>Pipeline: {status}</h2>
    </div>
  );
}`, durationMs: 1200 },
    { type: 'agent_thinking', durationMs: 600 },
    { type: 'code_edit', filePath: 'src/components/PipelineDashboard.tsx', durationMs: 1800, newContent: `import { useState, useEffect } from 'react';
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
}` },
    { type: 'agent_output', text: 'Updated `PipelineDashboard.tsx`:\n- Added WebSocket hook for live pipeline status\n- Status updates in real-time without polling\n- Cleanup on unmount to prevent leaks', typewriterDelayMs: 14 },
    { type: 'pause', durationMs: 4000 }
  ]
};
