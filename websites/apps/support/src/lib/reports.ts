/**
 * Phase 27.2 — Bug Report Storage Abstraction
 *
 * MVP: In-memory Map store. Works for dev and low-volume production.
 * The interface is designed for easy migration to Turso/Supabase/Postgres.
 *
 * To add persistence, implement ReportStore and set it via setStore().
 */

// ── Types ─────────────────────────────────────────────────────

export type ReportStatus = 'new' | 'triaging' | 'investigating' | 'fixed' | 'closed';
export type ReportSeverity = 'critical' | 'major' | 'minor' | 'cosmetic';

export interface ReportMetadata {
  id: string;
  status: ReportStatus;
  severity: ReportSeverity;
  email: string;
  description: string;
  project_id: string | null;
  license_tier: string | null;
  platform: string | null;
  log_count: number;
  error_count: number;
  assigned_to: string | null;
  resolution: string | null;
  created_at: string;   // ISO 8601
  updated_at: string;   // ISO 8601
}

export interface ReportFull extends ReportMetadata {
  /** Full bug report JSON payload */
  payload: Record<string, unknown>;
}

export interface ReportListOptions {
  status?: ReportStatus;
  severity?: ReportSeverity;
  search?: string;
  limit?: number;
  offset?: number;
}

export interface ReportListResult {
  reports: ReportMetadata[];
  total: number;
}

export interface ReportMetrics {
  total: number;
  by_status: Record<ReportStatus, number>;
  by_severity: Record<ReportSeverity, number>;
  recent_24h: number;
  recent_7d: number;
}

// ── Store Interface ───────────────────────────────────────────

export interface ReportStore {
  insert(report: ReportFull): Promise<void>;
  get(id: string): Promise<ReportFull | null>;
  list(opts: ReportListOptions): Promise<ReportListResult>;
  updateStatus(id: string, status: ReportStatus, fields?: { assigned_to?: string; resolution?: string }): Promise<ReportFull | null>;
  metrics(): Promise<ReportMetrics>;
}

// ── In-Memory Implementation ──────────────────────────────────

class InMemoryReportStore implements ReportStore {
  private reports = new Map<string, ReportFull>();

  async insert(report: ReportFull): Promise<void> {
    this.reports.set(report.id, { ...report });
  }

  async get(id: string): Promise<ReportFull | null> {
    return this.reports.get(id) ?? null;
  }

  async list(opts: ReportListOptions): Promise<ReportListResult> {
    let items = Array.from(this.reports.values());

    // Filter
    if (opts.status) items = items.filter(r => r.status === opts.status);
    if (opts.severity) items = items.filter(r => r.severity === opts.severity);
    if (opts.search) {
      const q = opts.search.toLowerCase();
      items = items.filter(r =>
        r.description.toLowerCase().includes(q) ||
        r.email.toLowerCase().includes(q) ||
        r.id.toLowerCase().includes(q)
      );
    }

    // Sort newest first
    items.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());

    const total = items.length;
    const offset = opts.offset ?? 0;
    const limit = opts.limit ?? 50;
    const page = items.slice(offset, offset + limit);

    // Strip payload from list results (metadata only)
    const reports: ReportMetadata[] = page.map(({ payload: _, ...meta }) => meta);

    return { reports, total };
  }

  async updateStatus(
    id: string,
    status: ReportStatus,
    fields?: { assigned_to?: string; resolution?: string },
  ): Promise<ReportFull | null> {
    const report = this.reports.get(id);
    if (!report) return null;

    report.status = status;
    report.updated_at = new Date().toISOString();
    if (fields?.assigned_to !== undefined) report.assigned_to = fields.assigned_to;
    if (fields?.resolution !== undefined) report.resolution = fields.resolution;

    return { ...report };
  }

  async metrics(): Promise<ReportMetrics> {
    const all = Array.from(this.reports.values());
    const now = Date.now();
    const day = 86400000;

    const by_status: Record<ReportStatus, number> = { new: 0, triaging: 0, investigating: 0, fixed: 0, closed: 0 };
    const by_severity: Record<ReportSeverity, number> = { critical: 0, major: 0, minor: 0, cosmetic: 0 };
    let recent_24h = 0;
    let recent_7d = 0;

    for (const r of all) {
      by_status[r.status]++;
      by_severity[r.severity]++;
      const age = now - new Date(r.created_at).getTime();
      if (age < day) recent_24h++;
      if (age < 7 * day) recent_7d++;
    }

    return { total: all.length, by_status, by_severity, recent_24h, recent_7d };
  }
}

// ── Singleton ─────────────────────────────────────────────────

let _store: ReportStore = new InMemoryReportStore();

/** Get the current report store */
export function getStore(): ReportStore {
  return _store;
}

/** Replace the store implementation (e.g., with Turso/Supabase adapter) */
export function setStore(store: ReportStore): void {
  _store = store;
}

// ── Helper: create ReportFull from API payload ────────────────

export function createReport(
  reportId: string,
  payload: Record<string, unknown>,
): ReportFull {
  const reporter = (payload.reporter as any) ?? {};
  const issue = (payload.issue as any) ?? {};
  const diagnostics = (payload.diagnostics as any) ?? {};
  const logs = (payload.logs as any[]) ?? [];
  const platform = (payload.platform as any) ?? {};

  const errorCount = logs.filter(
    (l: any) => l.level === 'ERROR' || l.level === 'CRITICAL',
  ).length;

  const now = new Date().toISOString();

  return {
    id: reportId,
    status: 'new',
    severity: issue.severity ?? 'major',
    email: reporter.email ?? '',
    description: issue.description ?? '',
    project_id: diagnostics.project?.id ?? null,
    license_tier: diagnostics.license_tier ?? null,
    platform: platform.os ?? platform.platform ?? null,
    log_count: logs.length,
    error_count: errorCount,
    assigned_to: null,
    resolution: null,
    created_at: (payload.generated_at as string) ?? now,
    updated_at: now,
    payload,
  };
}
