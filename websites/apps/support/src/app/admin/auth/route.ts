import { NextRequest, NextResponse } from 'next/server';
import { COOKIE_NAME, deriveSessionId, safeEqual, isConfirmedDevelopment } from '../../../lib/auth';
import { logAdminAudit, hashActor } from '../../../lib/audit';

/**
 * POST /admin/auth — Validate the admin token and set the session cookie.
 *
 * The cookie stores an opaque session id DERIVED from ADMIN_TOKEN — never the
 * raw token (DR-4.5). The token comparison is constant-time (DR-4.3).
 */
export async function POST(request: NextRequest) {
  const formData = await request.formData();
  const token = formData.get('token');
  const adminToken = process.env.ADMIN_TOKEN;

  if (typeof token !== 'string' || !adminToken || !safeEqual(token, adminToken)) {
    logAdminAudit({ event: 'admin.login', actor: 'anonymous', outcome: 'failure' });
    return NextResponse.redirect(new URL('/admin/reports?error=invalid', request.url));
  }

  const sessionId = deriveSessionId(adminToken);
  const response = NextResponse.redirect(new URL('/admin/reports', request.url));
  response.cookies.set(COOKIE_NAME, sessionId, {
    httpOnly: true,
    // Secure everywhere except a positively-confirmed local dev/test env.
    secure: !isConfirmedDevelopment(),
    sameSite: 'lax',
    maxAge: 60 * 60 * 24 * 7, // 7 days
    path: '/',
  });

  logAdminAudit({ event: 'admin.login', actor: hashActor(sessionId), outcome: 'success' });
  return response;
}
