import { NextRequest, NextResponse } from 'next/server';
import { isAuthorized } from '../../../../lib/auth';
import { getStore, type ReportStatus } from '../../../../lib/reports';

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, PATCH, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, Authorization',
};

export async function OPTIONS() {
  return new NextResponse(null, { status: 204, headers: corsHeaders });
}

/**
 * GET /api/bug-reports/:id — Get full report detail (auth-gated)
 */
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const headers = { ...corsHeaders, 'Content-Type': 'application/json' };

  if (!isAuthorized(request)) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401, headers });
  }

  const { id } = await params;
  const report = await getStore().get(id);

  if (!report) {
    return NextResponse.json({ error: 'Report not found' }, { status: 404, headers });
  }

  return NextResponse.json(report, { status: 200, headers });
}

/**
 * PATCH /api/bug-reports/:id — Update report status/assignment (auth-gated)
 *
 * Body: { status?, assigned_to?, resolution? }
 */
export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const headers = { ...corsHeaders, 'Content-Type': 'application/json' };

  if (!isAuthorized(request)) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401, headers });
  }

  let body: Record<string, unknown>;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400, headers });
  }

  const validStatuses: ReportStatus[] = ['new', 'triaging', 'investigating', 'fixed', 'closed'];
  const status = body.status as ReportStatus | undefined;
  if (status && !validStatuses.includes(status)) {
    return NextResponse.json(
      { error: `status must be one of: ${validStatuses.join(', ')}` },
      { status: 400, headers },
    );
  }

  const { id } = await params;

  if (!status) {
    return NextResponse.json({ error: 'At least status is required' }, { status: 400, headers });
  }

  const updated = await getStore().updateStatus(id, status, {
    assigned_to: body.assigned_to as string | undefined,
    resolution: body.resolution as string | undefined,
  });

  if (!updated) {
    return NextResponse.json({ error: 'Report not found' }, { status: 404, headers });
  }

  return NextResponse.json(updated, { status: 200, headers });
}
