/**
 * Phase 142 (DR-4.6) — lightweight admin audit logging.
 *
 * Emits structured, PII-free audit events to the process console, which the
 * host (Netlify / Vercel) captures as function logs. This is the MVP audit
 * trail for the in-memory report store. A persistent, queryable audit store is
 * an open follow-up (see DEEP_RESEARCH_B_SECURITY_FINDINGS.md) — it needs the
 * same durable-storage decision as rate-limit persistence.
 *
 * NEVER pass PII (reporter email, raw tokens, report bodies) into an audit
 * entry. Actors are recorded as a non-reversible hash of the presented
 * credential via `hashActor`.
 */

import { createHash } from 'crypto';

/**
 * Non-reversible short id of a credential, for the audit `actor` field.
 * Truncated to 12 hex chars — enough to distinguish credentials in logs
 * without being usable to reconstruct the secret.
 */
export function hashActor(credential: string): string {
  return createHash('sha256').update(credential, 'utf8').digest('hex').slice(0, 12);
}

export interface AdminAuditEntry {
  /** Dotted event name, e.g. 'bug_report.patch' or 'admin.login'. */
  event: string;
  /** Hashed credential id (never the raw secret), or 'anonymous'/'unknown'. */
  actor: string;
  /** Affected report id, when applicable. */
  reportId?: string;
  /** Summary of what changed. MUST NOT contain reporter PII. */
  changes?: Record<string, unknown>;
  outcome?: 'success' | 'failure';
}

/** Write a single structured, PII-free admin audit event to the function logs. */
export function logAdminAudit(entry: AdminAuditEntry): void {
  const record = {
    kind: 'admin_audit',
    ts: new Date().toISOString(),
    ...entry,
  };
  console.log(`[audit] ${JSON.stringify(record)}`);
}
