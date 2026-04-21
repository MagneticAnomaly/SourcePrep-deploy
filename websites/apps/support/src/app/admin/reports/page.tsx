'use client';

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';

// ── Types ─────────────────────────────────────────────────────

type ReportStatus = 'new' | 'triaging' | 'investigating' | 'fixed' | 'closed';
type ReportSeverity = 'critical' | 'major' | 'minor' | 'cosmetic';

interface ReportMetadata {
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
  created_at: string;
  updated_at: string;
}

interface Metrics {
  total: number;
  by_status: Record<ReportStatus, number>;
  by_severity: Record<ReportSeverity, number>;
  recent_24h: number;
  recent_7d: number;
}

// ── Helpers ───────────────────────────────────────────────────

const SEV_COLORS: Record<ReportSeverity, string> = {
  critical: 'bg-red-500/20 text-red-400 border-red-500/30',
  major: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
  minor: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  cosmetic: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
};

const STATUS_COLORS: Record<ReportStatus, string> = {
  new: 'bg-blue-500/20 text-blue-400',
  triaging: 'bg-purple-500/20 text-purple-400',
  investigating: 'bg-amber-500/20 text-amber-400',
  fixed: 'bg-green-500/20 text-green-400',
  closed: 'bg-gray-500/20 text-gray-400',
};

const SEV_EMOJI: Record<ReportSeverity, string> = {
  critical: '🔴', major: '🟠', minor: '🟡', cosmetic: '⚪',
};

function timeAgo(iso: string): string {
  const seconds = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return 'just now';
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

// ── Component ─────────────────────────────────────────────────

export default function AdminReportsPage() {
  const [reports, setReports] = useState<ReportMetadata[]>([]);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  // Filters
  const [statusFilter, setStatusFilter] = useState<ReportStatus | ''>('');
  const [severityFilter, setSeverityFilter] = useState<ReportSeverity | ''>('');
  const [search, setSearch] = useState('');

  const fetchReports = useCallback(async () => {
    setLoading(true);
    const params = new URLSearchParams();
    if (statusFilter) params.set('status', statusFilter);
    if (severityFilter) params.set('severity', severityFilter);
    if (search) params.set('search', search);
    params.set('limit', '50');

    try {
      const res = await fetch(`/api/bug-reports?${params}`);
      if (res.ok) {
        const data = await res.json();
        setReports(data.reports);
        setTotal(data.total);
      }
    } catch { /* silent */ }
    setLoading(false);
  }, [statusFilter, severityFilter, search]);

  const fetchMetrics = useCallback(async () => {
    try {
      const res = await fetch('/api/bug-reports/metrics');
      if (res.ok) setMetrics(await res.json());
    } catch { /* silent */ }
  }, []);

  useEffect(() => { fetchReports(); }, [fetchReports]);
  useEffect(() => { fetchMetrics(); }, [fetchMetrics]);

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      {/* Header */}
      <header className="border-b border-gray-800 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold">Bug Reports</h1>
            <p className="text-sm text-gray-400">Prep Support Admin</p>
          </div>
          <Link href="/" className="text-sm text-gray-400 hover:text-white transition-colors">
            ← Back to Support
          </Link>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-6 space-y-6">
        {/* Metrics Cards */}
        {metrics && (
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3">
            <MetricCard label="Total" value={metrics.total} />
            <MetricCard label="Last 24h" value={metrics.recent_24h} accent="blue" />
            <MetricCard label="Last 7d" value={metrics.recent_7d} accent="purple" />
            <MetricCard label="Open" value={metrics.by_status.new + metrics.by_status.triaging + metrics.by_status.investigating} accent="amber" />
            <MetricCard label="Critical" value={metrics.by_severity.critical} accent="red" />
            <MetricCard label="Fixed" value={metrics.by_status.fixed + metrics.by_status.closed} accent="green" />
          </div>
        )}

        {/* Filters */}
        <div className="flex flex-wrap gap-3">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as ReportStatus | '')}
            className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">All Statuses</option>
            <option value="new">New</option>
            <option value="triaging">Triaging</option>
            <option value="investigating">Investigating</option>
            <option value="fixed">Fixed</option>
            <option value="closed">Closed</option>
          </select>

          <select
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value as ReportSeverity | '')}
            className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">All Severities</option>
            <option value="critical">🔴 Critical</option>
            <option value="major">🟠 Major</option>
            <option value="minor">🟡 Minor</option>
            <option value="cosmetic">⚪ Cosmetic</option>
          </select>

          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search reports..."
            className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm flex-1 min-w-[200px] focus:outline-none focus:ring-2 focus:ring-blue-500"
          />

          <button
            onClick={() => { fetchReports(); fetchMetrics(); }}
            className="px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm hover:bg-gray-700 transition-colors"
          >
            Refresh
          </button>
        </div>

        {/* Reports Table */}
        <div className="border border-gray-800 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-900/50">
              <tr className="border-b border-gray-800">
                <th className="text-left px-4 py-3 font-medium text-gray-400">Severity</th>
                <th className="text-left px-4 py-3 font-medium text-gray-400">Status</th>
                <th className="text-left px-4 py-3 font-medium text-gray-400">Description</th>
                <th className="text-left px-4 py-3 font-medium text-gray-400">Reporter</th>
                <th className="text-left px-4 py-3 font-medium text-gray-400">Logs</th>
                <th className="text-left px-4 py-3 font-medium text-gray-400">When</th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-gray-500">Loading...</td>
                </tr>
              )}
              {!loading && reports.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-gray-500">
                    {total === 0 ? 'No bug reports yet.' : 'No reports match your filters.'}
                  </td>
                </tr>
              )}
              {reports.map((r) => (
                <tr key={r.id} className="border-b border-gray-800/50 hover:bg-gray-900/30 transition-colors">
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border ${SEV_COLORS[r.severity]}`}>
                      {SEV_EMOJI[r.severity]} {r.severity}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_COLORS[r.status]}`}>
                      {r.status}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <Link
                      href={`/admin/reports/${r.id}`}
                      className="text-blue-400 hover:text-blue-300 hover:underline"
                    >
                      {r.description.length > 80 ? r.description.slice(0, 80) + '...' : r.description}
                    </Link>
                    <div className="text-xs text-gray-500 mt-0.5">{r.id}</div>
                  </td>
                  <td className="px-4 py-3 text-gray-300">{r.email}</td>
                  <td className="px-4 py-3 text-gray-400">
                    {r.log_count}
                    {r.error_count > 0 && (
                      <span className="text-red-400 ml-1">({r.error_count} err)</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-gray-400 whitespace-nowrap">{timeAgo(r.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Pagination info */}
        {total > 0 && (
          <div className="text-sm text-gray-500 text-center">
            Showing {reports.length} of {total} reports
          </div>
        )}
      </main>
    </div>
  );
}

// ── Metric Card ───────────────────────────────────────────────

function MetricCard({ label, value, accent }: { label: string; value: number; accent?: string }) {
  const accentClass = accent
    ? `border-${accent}-500/30 bg-${accent}-500/5`
    : 'border-gray-800 bg-gray-900/30';

  return (
    <div className={`border rounded-xl px-4 py-3 ${accentClass}`}>
      <div className="text-2xl font-bold">{value}</div>
      <div className="text-xs text-gray-400">{label}</div>
    </div>
  );
}
