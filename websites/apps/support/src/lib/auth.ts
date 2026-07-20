/**
 * Admin auth for the support portal.
 *
 * Hardened in Phase 142 (DR-4). Auth is proven by presenting the ADMIN_TOKEN
 * secret through one of:
 * - `Authorization: Bearer <ADMIN_TOKEN>` header (programmatic API clients)
 * - an opaque session cookie whose value is DERIVED from ADMIN_TOKEN
 *   (`deriveSessionId`) — the raw token is NEVER stored in the cookie.
 *
 * All secret comparisons are constant-time (`safeEqual`). The legacy `?token=`
 * query-param path was removed (a token in a URL leaks via Referer and logs).
 * When ADMIN_TOKEN is unset, access HARD-DENIES unless a dev/test env is
 * positively confirmed (`isConfirmedDevelopment`) — an unset or unexpected
 * NODE_ENV no longer auto-authorizes.
 *
 * A single shared secret is the MVP. Migrating to a real provider (NextAuth /
 * Clerk) is a design decision documented in DEEP_RESEARCH_B_SECURITY_FINDINGS.md.
 */

import { createHmac, createHash, timingSafeEqual } from 'crypto';
import { NextRequest } from 'next/server';
import { cookies } from 'next/headers';
import { hashActor } from './audit';

const COOKIE_NAME = 'prep_admin_token';
const SESSION_DERIVATION_VERSION = 'v1';

/**
 * Constant-time string comparison. Both inputs are SHA-256 hashed to a fixed
 * 32-byte length first, so the comparison never throws on unequal lengths and
 * does not leak the length of the secret through timing.
 */
export function safeEqual(a: string, b: string): boolean {
  const ha = createHash('sha256').update(a, 'utf8').digest();
  const hb = createHash('sha256').update(b, 'utf8').digest();
  return timingSafeEqual(ha, hb);
}

/**
 * Derive the opaque admin session id stored in the auth cookie. This is an
 * HMAC of a fixed label keyed by ADMIN_TOKEN: it is not the raw token, cannot
 * be reversed to it, and cannot be replayed as the `Bearer` API token. Rotating
 * ADMIN_TOKEN invalidates every existing session automatically.
 */
export function deriveSessionId(token: string): string {
  return createHmac('sha256', token)
    .update(`prep-admin-session:${SESSION_DERIVATION_VERSION}`)
    .digest('hex');
}

/**
 * True ONLY when a local development or test environment is positively
 * confirmed. Any ambiguous value (unset, 'production', or unrecognized) returns
 * false, so the no-token path hard-denies rather than auto-authorizing.
 */
export function isConfirmedDevelopment(): boolean {
  const env = process.env.NODE_ENV;
  return env === 'development' || env === 'test';
}

/** Check if a request carries valid admin auth. */
export function isAuthorized(request: NextRequest): boolean {
  const token = getAdminToken();
  if (!token) {
    // No ADMIN_TOKEN configured — only allow in a confirmed dev/test env.
    return isConfirmedDevelopment();
  }

  // 1) Authorization: Bearer <ADMIN_TOKEN> — programmatic clients (constant-time).
  const authHeader = request.headers.get('authorization');
  if (authHeader?.startsWith('Bearer ')) {
    const presented = authHeader.slice('Bearer '.length);
    if (presented && safeEqual(presented, token)) return true;
  }

  // 2) Opaque session cookie (derived from ADMIN_TOKEN; never the raw token).
  const cookieToken = request.cookies.get(COOKIE_NAME)?.value;
  if (cookieToken && safeEqual(cookieToken, deriveSessionId(token))) return true;

  // NOTE: the legacy `?token=` query-param path was removed on purpose — a
  // secret in a URL leaks via the Referer header (to third-party assets) and
  // via server / proxy / CDN access logs.
  return false;
}

/** Check admin auth from server components (session cookie only). */
export async function isAuthorizedServer(): Promise<boolean> {
  const token = getAdminToken();
  if (!token) return isConfirmedDevelopment();

  const cookieStore = await cookies();
  const cookieToken = cookieStore.get(COOKIE_NAME)?.value;
  return !!cookieToken && safeEqual(cookieToken, deriveSessionId(token));
}

/**
 * Non-reversible short identifier for the credential presented on a request,
 * for audit logs. Never returns (or logs) the raw credential.
 */
export function getRequestActor(request: NextRequest): string {
  const authHeader = request.headers.get('authorization');
  if (authHeader?.startsWith('Bearer ')) {
    return hashActor(authHeader.slice('Bearer '.length));
  }
  const cookieToken = request.cookies.get(COOKIE_NAME)?.value;
  if (cookieToken) return hashActor(cookieToken);
  return 'unknown';
}

/** Get the configured admin token. */
function getAdminToken(): string | undefined {
  return process.env.ADMIN_TOKEN;
}

export { COOKIE_NAME };
