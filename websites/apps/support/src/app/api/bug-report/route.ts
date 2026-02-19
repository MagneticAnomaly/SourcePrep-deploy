import { NextRequest, NextResponse } from 'next/server';

// ── Types ─────────────────────────────────────────────────────
interface BugReportPayload {
  report_version: string;
  generated_at: string;
  reporter: { email: string };
  issue: {
    severity: 'critical' | 'major' | 'minor' | 'cosmetic';
    description: string;
    steps_to_reproduce?: string;
    expected_behavior?: string;
    actual_behavior?: string;
  };
  platform: Record<string, unknown>;
  diagnostics: Record<string, unknown>;
  logs: Array<{ time: string; level: string; logger: string; message: string }>;
}

// ── Validation ────────────────────────────────────────────────
function validate(body: unknown): { ok: true; data: BugReportPayload } | { ok: false; error: string } {
  if (!body || typeof body !== 'object') return { ok: false, error: 'Request body must be a JSON object.' };
  const b = body as Record<string, unknown>;

  if (!b.reporter || typeof (b.reporter as any)?.email !== 'string' || !(b.reporter as any).email.includes('@')) {
    return { ok: false, error: 'reporter.email is required and must be a valid email.' };
  }
  if (!b.issue || typeof (b.issue as any)?.description !== 'string' || (b.issue as any).description.length < 10) {
    return { ok: false, error: 'issue.description is required (min 10 characters).' };
  }
  const validSeverities = ['critical', 'major', 'minor', 'cosmetic'];
  if (!validSeverities.includes((b.issue as any)?.severity)) {
    return { ok: false, error: `issue.severity must be one of: ${validSeverities.join(', ')}` };
  }

  return { ok: true, data: body as BugReportPayload };
}

// ── Rate limiting (in-memory, per-process — good enough for serverless MVP) ──
const rateLimitMap = new Map<string, { count: number; resetAt: number }>();
const RATE_LIMIT = 10;       // max reports
const RATE_WINDOW = 3600000; // per hour (ms)

function checkRateLimit(ip: string): boolean {
  const now = Date.now();
  const entry = rateLimitMap.get(ip);
  if (!entry || now > entry.resetAt) {
    rateLimitMap.set(ip, { count: 1, resetAt: now + RATE_WINDOW });
    return true;
  }
  if (entry.count >= RATE_LIMIT) return false;
  entry.count++;
  return true;
}

// ── Report ID ─────────────────────────────────────────────────
function generateReportId(): string {
  const ts = Date.now().toString(36);
  const rand = Math.random().toString(36).slice(2, 8);
  return `br-${ts}-${rand}`;
}

// ── Email via Resend ──────────────────────────────────────────
async function sendNotification(reportId: string, report: BugReportPayload): Promise<boolean> {
  const apiKey = process.env.RESEND_API_KEY;
  if (!apiKey) {
    console.warn('[bug-report] RESEND_API_KEY not set — skipping email notification');
    return false;
  }

  const toAddress = process.env.BUG_REPORT_EMAIL ?? 'bugs@codrag.io';
  const sevEmoji: Record<string, string> = { critical: '🔴', major: '🟠', minor: '🟡', cosmetic: '⚪' };
  const emoji = sevEmoji[report.issue.severity] ?? '⚪';
  const logErrorCount = report.logs.filter(l => l.level === 'ERROR' || l.level === 'CRITICAL').length;

  const subject = `${emoji} [Bug ${report.issue.severity.toUpperCase()}] ${report.issue.description.slice(0, 80)}`;

  const projectName = (report.diagnostics as any)?.project?.name ?? 'N/A';
  const licenseTier = String((report.diagnostics as any)?.license_tier ?? 'unknown');
  const platform = String((report.platform as any)?.os ?? (report.platform as any)?.platform ?? 'unknown');

  const htmlBody = `
<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 700px;">
  <h2 style="margin: 0 0 16px;">${emoji} Bug Report: ${reportId}</h2>
  
  <table style="border-collapse: collapse; width: 100%; font-size: 14px;">
    <tr><td style="padding: 6px 12px; font-weight: bold; width: 140px;">Reporter</td><td style="padding: 6px 12px;">${report.reporter.email}</td></tr>
    <tr><td style="padding: 6px 12px; font-weight: bold;">Severity</td><td style="padding: 6px 12px;">${emoji} ${report.issue.severity}</td></tr>
    <tr><td style="padding: 6px 12px; font-weight: bold;">Platform</td><td style="padding: 6px 12px;">${platform}</td></tr>
    <tr><td style="padding: 6px 12px; font-weight: bold;">Project</td><td style="padding: 6px 12px;">${projectName}</td></tr>
    <tr><td style="padding: 6px 12px; font-weight: bold;">License</td><td style="padding: 6px 12px;">${licenseTier}</td></tr>
    <tr><td style="padding: 6px 12px; font-weight: bold;">Logs</td><td style="padding: 6px 12px;">${report.logs.length} entries (${logErrorCount} errors)</td></tr>
    <tr><td style="padding: 6px 12px; font-weight: bold;">Submitted</td><td style="padding: 6px 12px;">${report.generated_at}</td></tr>
  </table>

  <h3 style="margin: 24px 0 8px;">Description</h3>
  <div style="background: #f6f8fa; border: 1px solid #d0d7de; border-radius: 6px; padding: 12px; white-space: pre-wrap; font-size: 13px;">${escapeHtml(report.issue.description)}</div>

  ${report.issue.steps_to_reproduce ? `
  <h3 style="margin: 24px 0 8px;">Steps to Reproduce</h3>
  <div style="background: #f6f8fa; border: 1px solid #d0d7de; border-radius: 6px; padding: 12px; white-space: pre-wrap; font-size: 13px;">${escapeHtml(report.issue.steps_to_reproduce)}</div>
  ` : ''}

  ${report.issue.expected_behavior ? `
  <h3 style="margin: 24px 0 8px;">Expected</h3>
  <p style="font-size: 13px;">${escapeHtml(report.issue.expected_behavior)}</p>
  ` : ''}

  ${report.issue.actual_behavior ? `
  <h3 style="margin: 24px 0 8px;">Actual</h3>
  <p style="font-size: 13px;">${escapeHtml(report.issue.actual_behavior)}</p>
  ` : ''}

  ${logErrorCount > 0 ? `
  <h3 style="margin: 24px 0 8px;">Recent Errors (last 20)</h3>
  <div style="background: #1a1a2e; color: #e0e0e0; border-radius: 6px; padding: 12px; font-family: monospace; font-size: 11px; white-space: pre-wrap; max-height: 400px; overflow: auto;">${
    report.logs
      .filter(l => l.level === 'ERROR' || l.level === 'CRITICAL')
      .slice(-20)
      .map(l => `<span style="color: #ff6b6b;">[${l.level}]</span> ${l.time} <span style="color: #888;">${l.logger}</span>\n  ${escapeHtml(l.message)}`)
      .join('\n\n')
  }</div>
  ` : ''}

  <p style="margin-top: 32px; font-size: 11px; color: #888;">
    Full diagnostics JSON attached. Report ID: ${reportId}
  </p>
</div>`;

  try {
    const res = await fetch('https://api.resend.com/emails', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${apiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        from: 'CoDRAG Bug Reports <bugs@codrag.io>',
        to: [toAddress],
        reply_to: report.reporter.email,
        subject,
        html: htmlBody,
        attachments: [{
          filename: `${reportId}.json`,
          content: Buffer.from(JSON.stringify(report, null, 2)).toString('base64'),
          content_type: 'application/json',
        }],
        tags: [
          { name: 'category', value: 'bug-report' },
          { name: 'severity', value: report.issue.severity },
          { name: 'report_id', value: reportId },
        ],
      }),
    });

    if (!res.ok) {
      const errText = await res.text();
      console.error(`[bug-report] Resend error ${res.status}: ${errText}`);
      return false;
    }
    return true;
  } catch (err) {
    console.error('[bug-report] Failed to send notification:', err);
    return false;
  }
}

function escapeHtml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ── CORS headers ──────────────────────────────────────────────
const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
};

// ── OPTIONS (CORS preflight) ──────────────────────────────────
export async function OPTIONS() {
  return new NextResponse(null, { status: 204, headers: corsHeaders });
}

// ── POST /api/bug-report ──────────────────────────────────────
export async function POST(request: NextRequest) {
  // CORS
  const headers = { ...corsHeaders, 'Content-Type': 'application/json' };

  // Rate limit
  const ip = request.headers.get('x-forwarded-for')?.split(',')[0]?.trim()
    ?? request.headers.get('x-real-ip')
    ?? 'unknown';
  if (!checkRateLimit(ip)) {
    return NextResponse.json(
      { error: 'Rate limit exceeded. Max 10 reports per hour.' },
      { status: 429, headers },
    );
  }

  // Parse body
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json(
      { error: 'Invalid JSON body.' },
      { status: 400, headers },
    );
  }

  // Validate
  const result = validate(body);
  if (!result.ok) {
    return NextResponse.json(
      { error: result.error },
      { status: 400, headers },
    );
  }

  const report = result.data;
  const reportId = generateReportId();

  // Log for Vercel function logs (always available even without Resend)
  console.log(`[bug-report] ${reportId} severity=${report.issue.severity} email=${report.reporter.email} logs=${report.logs.length}`);

  // Send notification email
  const emailSent = await sendNotification(reportId, report);

  // TODO (Phase 27.3): Store in database for ticket tracking
  // await db.insert('reports', { id: reportId, status: 'new', ... });

  return NextResponse.json(
    {
      success: true,
      report_id: reportId,
      email_sent: emailSent,
      message: 'Bug report received. Thank you for helping improve CoDRAG!',
    },
    { status: 200, headers },
  );
}
