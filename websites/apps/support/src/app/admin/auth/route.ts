import { NextRequest, NextResponse } from 'next/server';
import { COOKIE_NAME } from '../../../lib/auth';

/**
 * POST /admin/auth — Set admin cookie and redirect to reports page.
 */
export async function POST(request: NextRequest) {
  const formData = await request.formData();
  const token = formData.get('token') as string | null;
  const adminToken = process.env.ADMIN_TOKEN;

  if (!adminToken || token !== adminToken) {
    return NextResponse.redirect(new URL('/admin/reports?error=invalid', request.url));
  }

  const response = NextResponse.redirect(new URL('/admin/reports', request.url));
  response.cookies.set(COOKIE_NAME, token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'lax',
    maxAge: 60 * 60 * 24 * 7, // 7 days
    path: '/',
  });

  return response;
}
