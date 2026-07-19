/**
 * Phase 142 (DR-5.1) — CORS origin allowlist for the support API.
 *
 * Replaces the previous wildcard `Access-Control-Allow-Origin: *`. Credentials
 * are never allowed cross-origin (`Access-Control-Allow-Credentials` is not
 * set), so allowlisting an origin only permits that origin's browser JS to call
 * the endpoint — it never exposes cookies.
 *
 * IMPORTANT: CORS is enforced by browsers only. Native clients (the desktop
 * app's native HTTP layer, CLIs) send no `Origin` header and are unaffected by
 * this allowlist — the server still processes their requests. The desktop app's
 * *webview* origin (`tauri://localhost` / `https://tauri.localhost`) is
 * allowlisted so an in-webview `fetch` keeps working once the Tauri CSP is
 * updated to permit the support host (see DEEP_RESEARCH_B_SECURITY_FINDINGS.md).
 */

import { NextRequest } from 'next/server';

/** Trusted browser origins allowed to call the support API cross-origin. */
const ALLOWED_ORIGINS: ReadonlySet<string> = new Set([
  // Production web family
  'https://sourceprep.io',
  'https://www.sourceprep.io',
  'https://support.sourceprep.io',
  'https://docs.sourceprep.io',
  'https://marketing.sourceprep.io',
  'https://payments.sourceprep.io',
  'https://storybook.sourceprep.io',
  // Desktop app (Tauri) webview origins — platform dependent
  'tauri://localhost',
  'https://tauri.localhost',
  'http://tauri.localhost',
  // Local development
  'http://localhost:3000',
  'http://localhost:3002',
  'http://localhost:5174',
  'http://localhost:6006',
]);

export function isAllowedOrigin(origin: string | null | undefined): origin is string {
  return !!origin && ALLOWED_ORIGINS.has(origin);
}

/**
 * Build CORS headers for a request, reflecting the request's Origin only when
 * it is on the allowlist. `methods` is the `Access-Control-Allow-Methods` value
 * for the route (e.g. 'POST, OPTIONS').
 */
export function corsHeaders(request: NextRequest, methods: string): Record<string, string> {
  const origin = request.headers.get('origin');
  const headers: Record<string, string> = {
    Vary: 'Origin',
    'Access-Control-Allow-Methods': methods,
    'Access-Control-Allow-Headers': 'Content-Type, Authorization',
  };
  if (isAllowedOrigin(origin)) {
    headers['Access-Control-Allow-Origin'] = origin;
  }
  return headers;
}
