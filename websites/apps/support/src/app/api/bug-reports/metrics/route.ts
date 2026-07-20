import { NextRequest, NextResponse } from 'next/server';
import { isAuthorized } from '../../../../lib/auth';
import { corsHeaders } from '../../../../lib/cors';
import { getStore } from '../../../../lib/reports';

const CORS_METHODS = 'GET, OPTIONS';

export async function OPTIONS(request: NextRequest) {
  return new NextResponse(null, { status: 204, headers: corsHeaders(request, CORS_METHODS) });
}

/**
 * GET /api/bug-reports/metrics — Report metrics (auth-gated)
 *
 * Returns: { total, by_status, by_severity, recent_24h, recent_7d }
 */
export async function GET(request: NextRequest) {
  const headers = { ...corsHeaders(request, CORS_METHODS), 'Content-Type': 'application/json' };

  if (!isAuthorized(request)) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401, headers });
  }

  const metrics = await getStore().metrics();
  return NextResponse.json(metrics, { status: 200, headers });
}
