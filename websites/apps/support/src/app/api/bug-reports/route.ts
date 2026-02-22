import { NextRequest, NextResponse } from 'next/server';
import { isAuthorized } from '../../../lib/auth';
import { getStore, type ReportStatus, type ReportSeverity } from '../../../lib/reports';

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, Authorization',
};

export async function OPTIONS() {
  return new NextResponse(null, { status: 204, headers: corsHeaders });
}

/**
 * GET /api/bug-reports — List reports (paginated, filtered, auth-gated)
 *
 * Query params:
 *   status   — filter by status (new, triaging, investigating, fixed, closed)
 *   severity — filter by severity (critical, major, minor, cosmetic)
 *   search   — text search in description/email/id
 *   limit    — page size (default 50, max 200)
 *   offset   — pagination offset (default 0)
 */
export async function GET(request: NextRequest) {
  const headers = { ...corsHeaders, 'Content-Type': 'application/json' };

  if (!isAuthorized(request)) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401, headers });
  }

  const url = new URL(request.url);
  const status = url.searchParams.get('status') as ReportStatus | null;
  const severity = url.searchParams.get('severity') as ReportSeverity | null;
  const search = url.searchParams.get('search') ?? undefined;
  const limit = Math.min(parseInt(url.searchParams.get('limit') ?? '50', 10) || 50, 200);
  const offset = parseInt(url.searchParams.get('offset') ?? '0', 10) || 0;

  const result = await getStore().list({
    status: status ?? undefined,
    severity: severity ?? undefined,
    search,
    limit,
    offset,
  });

  return NextResponse.json(result, { status: 200, headers });
}
