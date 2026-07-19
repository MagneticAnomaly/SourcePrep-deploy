import { NextRequest, NextResponse } from 'next/server';
import { corsHeaders } from '../../../lib/cors';
import { getStore, createReport } from '../../../lib/reports';

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
// Size bounds keep an unauthenticated public endpoint from being used to flood
// logs / email / storage with oversized payloads (DR-5.4).
const MAX_EMAIL_LEN = 254;
const MAX_DESCRIPTION_LEN = 20_000;
const MAX_TEXT_FIELD_LEN = 5_000; // steps / expected / actual
const MAX_LOGS = 1_000;
// Single-line, one-@ email. `\s` excludes CR/LF, blocking header injection into
// the Resend `reply_to` field; the explicit CR/LF check is belt-and-suspenders.
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function validate(body: unknown): { ok: true; data: BugReportPayload } | { ok: false; error: string } {
  if (!body || typeof body !== 'object') return { ok: false, error: 'Request body must be a JSON object.' };
  const b = body as Record<string, unknown>;

  const email = (b.reporter as any)?.email;
  if (typeof email !== 'string' || email.length > MAX_EMAIL_LEN || /[\r\n]/.test(email) || !EMAIL_RE.test(email)) {
    return { ok: false, error: 'reporter.email is required and must be a valid email.' };
  }

  const description = (b.issue as any)?.description;
  if (typeof description !== 'string' || description.length < 10) {
    return { ok: false, error: 'issue.description is required (min 10 characters).' };
  }
  if (description.length > MAX_DESCRIPTION_LEN) {
    return { ok: false, error: `issue.description must be under ${MAX_DESCRIPTION_LEN} characters.` };
  }

  const validSeverities = ['critical', 'major', 'minor', 'cosmetic'];
  if (!validSeverities.includes((b.issue as any)?.severity)) {
    return { ok: false, error: `issue.severity must be one of: ${validSeverities.join(', ')}` };
  }

  // Optional free-text fields — bound each to prevent oversized payloads.
  for (const f of ['steps_to_reproduce', 'expected_behavior', 'actual_behavior'] as const) {
    const v = (b.issue as any)?.[f];
    if (v !== undefined && (typeof v !== 'string' || v.length > MAX_TEXT_FIELD_LEN)) {
      return { ok: false, error: `issue.${f} must be a string under ${MAX_TEXT_FIELD_LEN} characters.` };
    }
  }

  // Normalize + bound the logs array (prevents log-flood DoS and a latent crash
  // when `logs` is omitted).
  const logs = (b as any).logs;
  if (logs === undefined) {
    (b as any).logs = [];
  } else if (!Array.isArray(logs) || logs.length > MAX_LOGS) {
    return { ok: false, error: `logs must be an array of at most ${MAX_LOGS} entries.` };
  } else if (!logs.every((l: unknown) => l !== null && typeof l === 'object')) {
    // Each entry must be a non-null object; otherwise `l.level` access below
    // throws a TypeError and 500s the request.
    return { ok: false, error: 'each log entry must be an object.' };
  }

  return { ok: true, data: body as BugReportPayload };
}

// ── Rate limiting ─────────────────────────────────────────────
// TODO(DR-5.2): this in-memory map is per-instance and resets on serverless
// cold start, so it is NOT a hard limit across the fleet. Before relying on it,
// migrate to a shared, atomic store (recommended: Netlify Blobs with strong
// consistency + an ETag compare-and-swap loop — no new subprocessor; or Upstash
// Redis + @upstash/ratelimit). See DEEP_RESEARCH_B_SECURITY_FINDINGS.md.
const rateLimitMap = new Map<string, { count: number; resetAt: number }>();
const RATE_LIMIT = 10;          // max reports
const RATE_WINDOW = 3600000;    // per hour (ms)
const MAX_TRACKED_IPS = 10_000; // bound memory before growing past this

function pruneExpired(now: number): void {
  for (const [key, entry] of rateLimitMap) {
    if (now > entry.resetAt) rateLimitMap.delete(key);
  }
}

function checkRateLimit(ip: string): boolean {
  const now = Date.now();
  // Prevent unbounded growth from many distinct IPs (memory-exhaustion DoS).
  if (rateLimitMap.size >= MAX_TRACKED_IPS) pruneExpired(now);
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

  const toAddress = process.env.BUG_REPORT_EMAIL ?? 'bugs@sourceprep.io';
  const sevEmoji: Record<string, string> = { critical: '🔴', major: '🟠', minor: '🟡', cosmetic: '⚪' };
  const emoji = sevEmoji[report.issue.severity] ?? '⚪';
  const logErrorCount = report.logs.filter(l => l?.level === 'ERROR' || l?.level === 'CRITICAL').length;

  const subject = `${emoji} [Bug ${report.issue.severity.toUpperCase()}] ${report.issue.description.slice(0, 80)}`;

  // Every value below is attacker-controllable (email, diagnostics, platform,
  // log fields) and MUST be HTML-escaped before interpolation to prevent
  // stored/blind XSS in the recipient's email client (DR-5.4).
  const projectName = String((report.diagnostics as any)?.project?.name ?? 'N/A');
  const licenseTier = String((report.diagnostics as any)?.license_tier ?? 'unknown');
  const platform = String((report.platform as any)?.os ?? (report.platform as any)?.platform ?? 'unknown');

  const htmlBody = `
<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 700px;">
  <h2 style="margin: 0 0 16px;">${emoji} Bug Report: ${reportId}</h2>

  <table style="border-collapse: collapse; width: 100%; font-size: 14px;">
    <tr><td style="padding: 6px 12px; font-weight: bold; width: 140px;">Reporter</td><td style="padding: 6px 12px;">${escapeHtml(report.reporter.email)}</td></tr>
    <tr><td style="padding: 6px 12px; font-weight: bold;">Severity</td><td style="padding: 6px 12px;">${emoji} ${report.issue.severity}</td></tr>
    <tr><td style="padding: 6px 12px; font-weight: bold;">Platform</td><td style="padding: 6px 12px;">${escapeHtml(platform)}</td></tr>
    <tr><td style="padding: 6px 12px; font-weight: bold;">Project</td><td style="padding: 6px 12px;">${escapeHtml(projectName)}</td></tr>
    <tr><td style="padding: 6px 12px; font-weight: bold;">License</td><td style="padding: 6px 12px;">${escapeHtml(licenseTier)}</td></tr>
    <tr><td style="padding: 6px 12px; font-weight: bold;">Logs</td><td style="padding: 6px 12px;">${report.logs.length} entries (${logErrorCount} errors)</td></tr>
    <tr><td style="padding: 6px 12px; font-weight: bold;">Submitted</td><td style="padding: 6px 12px;">${escapeHtml(String(report.generated_at))}</td></tr>
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
      .filter(l => l?.level === 'ERROR' || l?.level === 'CRITICAL')
      .slice(-20)
      .map(l => `<span style="color: #ff6b6b;">[${escapeHtml(String(l.level))}]</span> ${escapeHtml(String(l.time))} <span style="color: #888;">${escapeHtml(String(l.logger))}</span>\n  ${escapeHtml(String(l.message))}`)
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
        from: 'SourcePrep Bug Reports <bugs@sourceprep.io>',
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

// ── CORS (origin allowlist — see lib/cors.ts) ─────────────────
const CORS_METHODS = 'POST, OPTIONS';

// ── OPTIONS (CORS preflight) ──────────────────────────────────
export async function OPTIONS(request: NextRequest) {
  return new NextResponse(null, { status: 204, headers: corsHeaders(request, CORS_METHODS) });
}

// ── POST /api/bug-report ──────────────────────────────────────
export async function POST(request: NextRequest) {
  // CORS (reflected allowlist; native clients send no Origin and are unaffected)
  const headers = { ...corsHeaders(request, CORS_METHODS), 'Content-Type': 'application/json' };

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

  // Log for function logs (always available even without Resend). No PII: the
  // reporter email is deliberately NOT logged (DR-4.7).
  console.log(`[bug-report] ${reportId} severity=${report.issue.severity} logs=${report.logs.length}`);

  // Send notification email (best-effort — a render or delivery failure must
  // not 500 the request; the response already reports email_sent).
  let emailSent = false;
  try {
    emailSent = await sendNotification(reportId, report);
  } catch (emailErr) {
    console.error('[bug-report] notification failed to render/send:', emailErr);
  }

  // Phase 27.2: Persist report for ticket tracking
  try {
    const reportRecord = createReport(reportId, report as unknown as Record<string, unknown>);
    await getStore().insert(reportRecord);
  } catch (storeErr) {
    console.error('[bug-report] Failed to store report:', storeErr);
    // Non-fatal — email notification is the primary delivery
  }

  return NextResponse.json(
    {
      success: true,
      report_id: reportId,
      email_sent: emailSent,
      message: 'Bug report received. Thank you for helping improve SourcePrep!',
    },
    { status: 200, headers },
  );
}
