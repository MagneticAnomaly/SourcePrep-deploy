import type { CliScript } from './cli-types';

/**
 * Demo: CoDRAG semantic search from Claude Code
 */
export const codragSearchDemo: CliScript = {
  title: 'claude — codrag-project',
  loop: true,
  loopDelayMs: 4000,
  events: [
    {
      type: 'user_input',
      text: 'how does authentication handle expired tokens?',
      typingDelayMs: 30,
    },
    { type: 'agent_thinking', durationMs: 800, label: 'Thinking…' },
    {
      type: 'tool_call',
      tool: 'codrag_search',
      args: '"expired token middleware"',
      durationMs: 1200,
      statusText: 'Searching codebase with structural expansion…',
    },
    {
      type: 'tool_result',
      text: 'Found 4 relevant chunks (1,842 tokens)\nauth/middleware.py · auth/token_service.py · tests/test_auth.py',
      status: 'success',
    },
    { type: 'pause', durationMs: 300 },
    {
      type: 'agent_output',
      text: 'The token expiration flow works in three stages:\n\n1. `TokenService.validate()` checks the JWT `exp` claim\n2. If expired, `AuthMiddleware` calls `refresh_pair()`\n3. A new access token is issued; the old refresh token is rotated\n\nThe refresh window is configurable via `AUTH_REFRESH_WINDOW_SECONDS` in your environment.',
      typewriterDelayMs: 12,
    },
  ],
};

/**
 * Demo: CoDRAG impact analysis
 */
export const codragImpactDemo: CliScript = {
  title: 'claude — codrag-project',
  loop: true,
  loopDelayMs: 4000,
  events: [
    {
      type: 'user_input',
      text: 'what would break if I change the signature of PaymentService.charge()?',
      typingDelayMs: 25,
    },
    { type: 'agent_thinking', durationMs: 600 },
    {
      type: 'tool_call',
      tool: 'codrag_impact',
      args: 'file_path="services/payment.py", direction="dependents"',
      durationMs: 900,
      statusText: 'Tracing dependents (2 hops)…',
    },
    {
      type: 'tool_result',
      text: '3 direct dependents, 7 transitive\nDirect: checkout/handler.py · billing/subscription.py · tests/test_payment.py',
      status: 'success',
    },
    { type: 'pause', durationMs: 400 },
    {
      type: 'agent_output',
      text: 'Changing `PaymentService.charge()` would directly affect:\n\n• `CheckoutHandler.process()` — calls charge() with amount + currency\n• `SubscriptionBilling.renew()` — passes a stored payment method\n• 4 test cases in `test_payment.py`\n\nThe safest approach: add the new parameter with a default value to avoid breaking existing callers.',
      typewriterDelayMs: 12,
    },
  ],
};

/**
 * Demo: CoDRAG structural overview
 */
export const codragOverviewDemo: CliScript = {
  title: 'claude — my-project',
  loop: true,
  loopDelayMs: 4000,
  events: [
    {
      type: 'user_input',
      text: 'give me an overview of this project',
      typingDelayMs: 28,
    },
    { type: 'agent_thinking', durationMs: 500 },
    {
      type: 'tool_call',
      tool: 'codrag',
      args: '',
      durationMs: 800,
      statusText: 'Loading structural context…',
    },
    {
      type: 'tool_result',
      text: 'Project: my-project (247 files, 1,892 graph nodes)\n3 modules detected · 5 hub files · 2 focus areas',
      status: 'success',
    },
    { type: 'pause', durationMs: 300 },
    {
      type: 'agent_output',
      text: 'This is a FastAPI application with three main modules:\n\n• **api/** — REST endpoints and middleware (hub: auth/middleware.py)\n• **services/** — Business logic layer (hub: payment.py, 23 dependents)\n• **models/** — SQLAlchemy ORM definitions\n\nThe most-connected file is `services/payment.py` with 23 downstream dependents. Your focus areas are `api/` and `services/`.',
      typewriterDelayMs: 10,
    },
  ],
};

/**
 * Demo: Agent IDE operations
 */
export const ideDemoScript: CliScript = {
  title: 'codrag-ide-demo',
  events: [
    { type: 'pause', durationMs: 1000 },
    { type: 'user_input', text: 'Can you wire up the pipeline status page to listen to Redis updates?', typingDelayMs: 30 },
    { type: 'agent_thinking', durationMs: 1500 },
    { type: 'tool_call', tool: 'codrag', args: '{ "project_id": "auto" }', durationMs: 800 },
    { type: 'tool_result', text: 'Loaded 412 files across 4 focus areas.', status: 'success' },
    { type: 'tool_call', tool: 'codrag_search', args: '{ "query": "pipeline status page" }', durationMs: 1500 },
    { type: 'tool_result', text: 'Found PipelineDashboard.tsx', status: 'success' },
    { type: 'agent_output', text: 'I found the `PipelineDashboard.tsx` component. I am going to open it and add the Redis subscription listener to update the state.', typewriterDelayMs: 20 },
    { type: 'file_open', filePath: 'src/components/PipelineDashboard.tsx', language: 'typescript', content: `import { useState, useEffect } from 'react';

export function PipelineDashboard() {
  const [status, setStatus] = useState('idle');

  return (
    <div className="p-4">
      <h2>Pipeline Status: {status}</h2>
    </div>
  );
}`, durationMs: 1500 },
    { type: 'agent_thinking', durationMs: 800 },
    { type: 'code_edit', filePath: 'src/components/PipelineDashboard.tsx', durationMs: 2000, newContent: `import { useState, useEffect } from 'react';
import { pubsub } from '@/lib/redis';

export function PipelineDashboard() {
  const [status, setStatus] = useState('idle');

  useEffect(() => {
    return pubsub.subscribe('pipeline_updates', (msg) => {
      setStatus(msg.status);
    });
  }, []);

  return (
    <div className="p-4 bg-gray-900 border border-gray-800 rounded">
      <h2 className="text-white">Pipeline Status: <span className="text-blue-400">{status}</span></h2>
    </div>
  );
}` },
    { type: 'agent_output', text: 'I updated `PipelineDashboard.tsx`:\n- Imported the Redis `pubsub` client.\n- Added a `useEffect` hook to subscribe to the `pipeline_updates` channel.\n- Added some basic styling to the container so it meshes with the dashboard theme.', typewriterDelayMs: 15 },
    { type: 'pause', durationMs: 4000 }
  ]
};
