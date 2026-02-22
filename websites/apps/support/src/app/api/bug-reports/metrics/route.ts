import { NextRequest, NextResponse } from 'next/server';
import { isAuthorized } from '../../../../lib/auth';
import { getStore } from '../../../../lib/reports';

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, Authorization',
};

export async function OPTIONS() {
  return new NextResponse(null, { status: 204, headers: corsHeaders });
}

/**
 * GET /api/bug-reports/metrics — Report metrics (auth-gated)
 *
 * Returns: { total, by_status, by_severity, recent_24h, recent_7d }
 */
export async function GET(request: NextRequest) {
  const headers = { ...corsHeaders, 'Content-Type': 'application/json' };

  if (!isAuthorized(request)) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401, headers });
  }

  const metrics = await getStore().metrics();
  return NextResponse.json(metrics, { status: 200, headers });
}
