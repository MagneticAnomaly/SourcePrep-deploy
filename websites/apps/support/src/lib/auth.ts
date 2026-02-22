/**
 * Phase 27.3 — Simple admin auth for MVP.
 *
 * Uses ADMIN_TOKEN env var. Token is passed via:
 * - Authorization: Bearer <token> header (API routes)
 * - ?token=<token> query param (admin pages — stored in cookie after first visit)
 * - admin_token cookie (set by admin layout)
 *
 * For production, replace with a proper auth provider (NextAuth, Clerk, etc.).
 */

import { NextRequest } from 'next/server';
import { cookies } from 'next/headers';

const COOKIE_NAME = 'codrag_admin_token';

/** Check if a request has valid admin auth */
export function isAuthorized(request: NextRequest): boolean {
  const token = getAdminToken();
  if (!token) {
    // No ADMIN_TOKEN configured — allow access in dev, deny in prod
    return process.env.NODE_ENV !== 'production';
  }

  // Check Authorization header
  const authHeader = request.headers.get('authorization');
  if (authHeader === `Bearer ${token}`) return true;

  // Check query param
  const url = new URL(request.url);
  if (url.searchParams.get('token') === token) return true;

  // Check cookie
  const cookieToken = request.cookies.get(COOKIE_NAME)?.value;
  if (cookieToken === token) return true;

  return false;
}

/** Check admin auth from server components (cookies only) */
export async function isAuthorizedServer(): Promise<boolean> {
  const token = getAdminToken();
  if (!token) return process.env.NODE_ENV !== 'production';

  const cookieStore = await cookies();
  const cookieToken = cookieStore.get(COOKIE_NAME)?.value;
  return cookieToken === token;
}

/** Get the configured admin token */
function getAdminToken(): string | undefined {
  return process.env.ADMIN_TOKEN;
}

export { COOKIE_NAME };
