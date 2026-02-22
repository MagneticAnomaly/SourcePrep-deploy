'use client';

import { useState, useEffect, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';

// ── Types ─────────────────────────────────────────────────────

type ReportStatus = 'new' | 'triaging' | 'investigating' | 'fixed' | 'closed';
type ReportSeverity = 'critical' | 'major' | 'minor' | 'cosmetic';

interface ReportFull {
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
  payload: Record<string, unknown>;
}

// ── Helpers ───────────────────────────────────────────────────

const SEV_EMOJI: Record<ReportSeverity, string> = {
  critical: '🔴', major: '🟠', minor: '🟡', cosmetic: '⚪',
};

const STATUS_OPTIONS: ReportStatus[] = ['new', 'triaging', 'investigating', 'fixed', 'closed'];

const STATUS_COLORS: Record<ReportStatus, string> = {
  new: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  triaging: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
  investigating: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  fixed: 'bg-green-500/20 text-green-400 border-green-500/30',
  closed: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
};

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString('en-US', {
    year: 'numeric', month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

// ── Component ─────────────────────────────────────────────────

export default function ReportDetailPage() {
  const params = useParams();
  const router = useRouter();
  const reportId = params.id as string;

  const [report, setReport] = useState<ReportFull | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updating, setUpdating] = useState(false);
  const [showPayload, setShowPayload] = useState(false);

  const fetchReport = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`/api/bug-reports/${reportId}`);
      if (res.ok) {
        setReport(await res.json());
      } else if (res.status === 404) {
        setError('Report not found');
      } else {
        setError('Failed to load report');
      }
    } catch {
      setError('Network error');
    }
    setLoading(false);
  }, [reportId]);

  useEffect(() => { fetchReport(); }, [fetchReport]);

  const updateStatus = async (newStatus: ReportStatus) => {
    if (!report || updating) return;
    setUpdating(true);
    try {
      const res = await fetch(`/api/bug-reports/${reportId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: newStatus }),
      });
      if (res.ok) {
        const updated = await res.json();
        setReport(updated);
      }
    } catch { /* silent */ }
    setUpdating(false);
  };

  const downloadPayload = () => {
    if (!report) return;
    const blob = new Blob([JSON.stringify(report.payload, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${report.id}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-950 text-white flex items-center justify-center">
        <p className="text-gray-400">Loading report...</p>
      </div>
    );
  }

  if (error || !report) {
    return (
      <div className="min-h-screen bg-gray-950 text-white flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-400 mb-4">{error ?? 'Report not found'}</p>
          <Link href="/admin/reports" className="text-blue-400 hover:underline">← Back to reports</Link>
        </div>
      </div>
    );
  }

  const issue = (report.payload?.issue as Record<string, string>) ?? {};
  const logs = (report.payload?.logs as Array<{ time: string; level: string; logger: string; message: string }>) ?? [];
  const errorLogs = logs.filter(l => l.level === 'ERROR' || l.level === 'CRITICAL');

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      {/* Header */}
      <header className="border-b border-gray-800 px-6 py-4">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link href="/admin/reports" className="text-gray-400 hover:text-white transition-colors">
              ← Reports
            </Link>
            <span className="text-gray-600">/</span>
            <span className="font-mono text-sm text-gray-300">{report.id}</span>
          </div>
          <button
            onClick={downloadPayload}
            className="px-3 py-1.5 bg-gray-800 border border-gray-700 rounded-lg text-sm hover:bg-gray-700 transition-colors"
          >
            Download JSON
          </button>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-6 space-y-6">
        {/* Summary Row */}
        <div className="flex flex-wrap items-start gap-4">
          <div className="flex-1 min-w-[300px]">
            <h1 className="text-lg font-semibold mb-2">
              {SEV_EMOJI[report.severity]} {report.description}
            </h1>
            <div className="flex flex-wrap items-center gap-3 text-sm text-gray-400">
              <span>From <strong className="text-gray-200">{report.email}</strong></span>
              <span>·</span>
              <span>{formatDate(report.created_at)}</span>
              {report.platform && <><span>·</span><span>{report.platform}</span></>}
              {report.license_tier && <><span>·</span><span>{report.license_tier}</span></>}
            </div>
          </div>

          {/* Status Workflow */}
          <div className="flex items-center gap-2">
            {STATUS_OPTIONS.map((s) => (
              <button
                key={s}
                onClick={() => updateStatus(s)}
                disabled={updating || report.status === s}
                className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${
                  report.status === s
                    ? STATUS_COLORS[s] + ' border-current'
                    : 'border-gray-700 text-gray-500 hover:text-gray-300 hover:border-gray-500'
                } ${updating ? 'opacity-50 cursor-not-allowed' : ''}`}
              >
                {s}
              </button>
            ))}
          </div>
        </div>

        {/* Info Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <InfoCard label="Severity" value={`${SEV_EMOJI[report.severity]} ${report.severity}`} />
          <InfoCard label="Log Entries" value={`${report.log_count} (${report.error_count} errors)`} />
          <InfoCard label="Project" value={report.project_id ?? 'N/A'} />
          <InfoCard label="Updated" value={formatDate(report.updated_at)} />
        </div>

        {/* Steps to Reproduce */}
        {issue.steps_to_reproduce && (
          <Section title="Steps to Reproduce">
            <pre className="whitespace-pre-wrap text-sm text-gray-300">{issue.steps_to_reproduce}</pre>
          </Section>
        )}

        {/* Expected vs Actual */}
        {(issue.expected_behavior || issue.actual_behavior) && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {issue.expected_behavior && (
              <Section title="Expected Behavior">
                <p className="text-sm text-gray-300">{issue.expected_behavior}</p>
              </Section>
            )}
            {issue.actual_behavior && (
              <Section title="Actual Behavior">
                <p className="text-sm text-gray-300">{issue.actual_behavior}</p>
              </Section>
            )}
          </div>
        )}

        {/* Error Logs */}
        {errorLogs.length > 0 && (
          <Section title={`Error Logs (${errorLogs.length})`}>
            <div className="bg-gray-900 rounded-lg p-4 max-h-[400px] overflow-auto font-mono text-xs space-y-2">
              {errorLogs.slice(-30).map((log, i) => (
                <div key={i} className="border-b border-gray-800/50 pb-2">
                  <span className="text-red-400">[{log.level}]</span>{' '}
                  <span className="text-gray-500">{log.time}</span>{' '}
                  <span className="text-gray-400">{log.logger}</span>
                  <div className="text-gray-300 mt-0.5 pl-4">{log.message}</div>
                </div>
              ))}
            </div>
          </Section>
        )}

        {/* Full Payload (collapsible) */}
        <div className="border border-gray-800 rounded-xl overflow-hidden">
          <button
            onClick={() => setShowPayload(!showPayload)}
            className="w-full flex items-center justify-between px-4 py-3 bg-gray-900/30 hover:bg-gray-900/50 transition-colors text-sm"
          >
            <span className="font-medium text-gray-300">Full Diagnostic Payload</span>
            <span className="text-gray-500">{showPayload ? '▲ Collapse' : '▼ Expand'}</span>
          </button>
          {showPayload && (
            <pre className="px-4 py-3 text-xs text-gray-400 overflow-auto max-h-[600px] bg-gray-900/20">
              {JSON.stringify(report.payload, null, 2)}
            </pre>
          )}
        </div>
      </main>
    </div>
  );
}

// ── Sub-components ────────────────────────────────────────────

function InfoCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="border border-gray-800 rounded-xl px-4 py-3 bg-gray-900/20">
      <div className="text-xs text-gray-500 mb-1">{label}</div>
      <div className="text-sm font-medium text-gray-200">{value}</div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="border border-gray-800 rounded-xl p-4 bg-gray-900/20">
      <h3 className="text-sm font-semibold text-gray-300 mb-3">{title}</h3>
      {children}
    </div>
  );
}
