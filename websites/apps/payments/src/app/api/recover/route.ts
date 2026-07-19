import { NextResponse } from 'next/server';

// In-memory per-IP rate limit (5 requests/hour). Resets on cold start —
// acceptable for a not-yet-available endpoint; upgrade to a persistent
// store (Netlify Blobs / Upstash) before this goes live.
const rateMap = new Map<string, { count: number; reset: number }>();
const RATE_LIMIT = 5;
const RATE_WINDOW_MS = 60 * 60 * 1000;

function getClientIp(request: Request): string {
  const xff = request.headers.get('x-forwarded-for');
  return (xff ? xff.split(',')[0] : '').trim() || 'unknown';
}

export async function POST(request: Request) {
  try {
    const ip = getClientIp(request);
    const now = Date.now();
    const entry = rateMap.get(ip);
    if (!entry || now > entry.reset) {
      rateMap.set(ip, { count: 1, reset: now + RATE_WINDOW_MS });
    } else {
      entry.count += 1;
      if (entry.count > RATE_LIMIT) {
        return NextResponse.json(
          { error: 'Too many requests. Please try again later.' },
          { status: 429 }
        );
      }
    }

    const { email } = await request.json();

    if (!email || typeof email !== 'string') {
      return NextResponse.json(
        { error: 'Email is required' },
        { status: 400 }
      );
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      return NextResponse.json(
        { error: 'A valid email address is required.' },
        { status: 400 }
      );
    }

    // License recovery is not yet implemented. Do NOT log the visitor's
    // email (PII). Direct them to the monitored mailbox.
    console.log('[Mock] Recover request received');

    return NextResponse.json(
      {
        error:
          'License recovery is not yet available. Email licenses@sourceprep.io and we will resend your key.',
      },
      { status: 501 }
    );
  } catch (error) {
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}