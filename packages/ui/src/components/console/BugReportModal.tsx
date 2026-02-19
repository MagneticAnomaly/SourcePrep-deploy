import { useState, useCallback, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { Bug, X, Send, Download, CheckCircle, ChevronDown, ChevronRight, AlertCircle } from 'lucide-react';
import { Button } from '../primitives/Button';
import { cn } from '../../lib/utils';
import type { LogEntry } from '../../types';

/** Where reports are POSTed. Update when cloud endpoint is deployed. */
const BUG_REPORT_ENDPOINT = 'https://support.codrag.io/api/bug-report';
const SUBMIT_TIMEOUT_MS = 10_000;
const EMAIL_STORAGE_KEY = 'codrag_bug_report_email';

type Severity = 'critical' | 'major' | 'minor' | 'cosmetic';
type SubmitState = 'idle' | 'submitting' | 'success' | 'failed';

const SEVERITY_OPTIONS: { value: Severity; label: string; color: string; desc: string }[] = [
  { value: 'critical', label: 'Critical', color: 'text-error',   desc: 'App crashes or data loss' },
  { value: 'major',    label: 'Major',    color: 'text-warning', desc: 'Feature broken, no workaround' },
  { value: 'minor',    label: 'Minor',    color: 'text-primary', desc: 'Feature broken, workaround exists' },
  { value: 'cosmetic', label: 'Cosmetic', color: 'text-text-subtle', desc: 'Visual or UX issue' },
];

export interface BugReportModalProps {
  open: boolean;
  onClose: () => void;
  logs: LogEntry[];
  diagnosticData?: Record<string, unknown>;
}

export function BugReportModal({ open, onClose, logs, diagnosticData }: BugReportModalProps) {
  const [email, setEmail] = useState(() =>
    (typeof localStorage !== 'undefined' ? localStorage.getItem(EMAIL_STORAGE_KEY) : null) ?? ''
  );
  const [severity, setSeverity] = useState<Severity>('major');
  const [description, setDescription] = useState('');
  const [steps, setSteps] = useState('');
  const [expected, setExpected] = useState('');
  const [actual, setActual] = useState('');
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [showDiagnostics, setShowDiagnostics] = useState(false);
  const [submitState, setSubmitState] = useState<SubmitState>('idle');
  const [submitError, setSubmitError] = useState<string | null>(null);
  const descRef = useRef<HTMLTextAreaElement>(null);

  // Focus description on open
  useEffect(() => {
    if (open) {
      setTimeout(() => descRef.current?.focus(), 100);
    }
  }, [open]);

  // Escape to close
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [open, onClose]);

  // Persist email to localStorage
  useEffect(() => {
    if (email && typeof localStorage !== 'undefined') {
      localStorage.setItem(EMAIL_STORAGE_KEY, email);
    }
  }, [email]);

  const buildReport = useCallback(() => {
    return {
      report_version: '1',
      generated_at: new Date().toISOString(),
      reporter: { email },
      issue: {
        severity,
        description,
        steps_to_reproduce: steps || undefined,
        expected_behavior: expected || undefined,
        actual_behavior: actual || undefined,
      },
      platform: {
        user_agent: navigator.userAgent,
        os: navigator.platform,
        screen: `${screen.width}x${screen.height}`,
        language: navigator.language,
        online: navigator.onLine,
        tauri: !!(window as any).__TAURI__,
      },
      diagnostics: diagnosticData ?? {},
      logs: logs.map(l => ({
        time: new Date(l.timestamp * 1000).toISOString(),
        level: l.level,
        logger: l.logger,
        message: l.message,
      })),
    };
  }, [email, severity, description, steps, expected, actual, logs, diagnosticData]);

  const downloadReport = useCallback((report: ReturnType<typeof buildReport>) => {
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `codrag-bug-report-${new Date().toISOString().slice(0, 10)}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, []);

  const handleSubmit = useCallback(async () => {
    const report = buildReport();
    setSubmitState('submitting');
    setSubmitError(null);

    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), SUBMIT_TIMEOUT_MS);

      const res = await fetch(BUG_REPORT_ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(report),
        signal: controller.signal,
      });
      clearTimeout(timeout);

      if (res.ok) {
        setSubmitState('success');
        setTimeout(() => {
          handleReset();
          onClose();
        }, 3000);
        return;
      }
      throw new Error(`Server returned ${res.status}`);
    } catch (err) {
      // Network error or timeout — fall back to download
      setSubmitState('failed');
      setSubmitError(
        err instanceof DOMException && err.name === 'AbortError'
          ? 'Request timed out. You can download the report instead.'
          : 'Could not reach the report server. You can download the report instead.'
      );
      downloadReport(report);
    }
  }, [buildReport, downloadReport, onClose]);

  const handleDownloadOnly = useCallback(() => {
    downloadReport(buildReport());
    setSubmitState('success');
    setTimeout(() => {
      handleReset();
      onClose();
    }, 3000);
  }, [buildReport, downloadReport, onClose]);

  const handleReset = () => {
    setDescription('');
    setSteps('');
    setExpected('');
    setActual('');
    setSeverity('major');
    setShowAdvanced(false);
    setShowDiagnostics(false);
    setSubmitState('idle');
    setSubmitError(null);
  };

  const canSubmit = email.trim().length > 0 && description.trim().length >= 10;

  const logSummary = {
    total: logs.length,
    errors: logs.filter(l => l.level === 'ERROR' || l.level === 'CRITICAL').length,
    warnings: logs.filter(l => l.level === 'WARNING').length,
  };

  if (!open) return null;

  return createPortal(
    <div
      className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div
        className="relative mx-4 w-full max-w-lg max-h-[90vh] flex flex-col rounded-lg border border-border bg-surface shadow-2xl animate-in fade-in zoom-in-95 duration-150"
        role="dialog"
        aria-modal="true"
        aria-labelledby="bug-report-title"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-border shrink-0">
          <h2 id="bug-report-title" className="text-base font-semibold text-text flex items-center gap-2">
            <Bug className="w-5 h-5 text-warning" />
            Send Bug Report
          </h2>
          <Button variant="ghost" size="icon-sm" onClick={onClose} aria-label="Close">
            <X className="w-5 h-5" />
          </Button>
        </div>

        {/* Success state */}
        {submitState === 'success' ? (
          <div className="flex flex-col items-center justify-center gap-3 py-12 px-6">
            <CheckCircle className="w-12 h-12 text-emerald-500" />
            <p className="text-sm font-medium text-text">Report sent — thank you!</p>
            <p className="text-xs text-text-muted text-center">
              We'll investigate and follow up at <span className="font-mono">{email}</span> if needed.
            </p>
          </div>
        ) : (
          <>
            {/* Scrollable body */}
            <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4 min-h-0">
              <p className="text-xs text-text-muted leading-relaxed">
                Help us squash this bug! Be as detailed as possible — the more context you give,
                the faster we can track it down. Diagnostic data from your session will be included automatically.
              </p>

              {/* Email */}
              <div>
                <label className="block text-xs font-medium text-text-muted mb-1">
                  Email <span className="text-error">*</span>
                </label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  className="w-full bg-surface-raised border border-border rounded-md px-3 py-2 text-sm text-text placeholder:text-text-subtle focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
                />
                <p className="text-[10px] text-text-subtle mt-0.5">So we can follow up. Remembered for next time.</p>
              </div>

              {/* Severity */}
              <div>
                <label className="block text-xs font-medium text-text-muted mb-1.5">Severity</label>
                <div className="grid grid-cols-4 gap-1.5">
                  {SEVERITY_OPTIONS.map((opt) => (
                    <button
                      key={opt.value}
                      type="button"
                      onClick={() => setSeverity(opt.value)}
                      className={cn(
                        'flex flex-col items-center gap-0.5 p-2 rounded-md border text-center transition-all',
                        severity === opt.value
                          ? 'border-primary bg-primary/5'
                          : 'border-border bg-surface hover:bg-surface-raised'
                      )}
                    >
                      <span className={cn('text-xs font-medium', severity === opt.value ? opt.color : 'text-text-muted')}>
                        {opt.label}
                      </span>
                      <span className="text-[9px] text-text-subtle leading-tight">{opt.desc}</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* Description */}
              <div>
                <label className="block text-xs font-medium text-text-muted mb-1">
                  What happened? <span className="text-error">*</span>
                </label>
                <textarea
                  ref={descRef}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  rows={4}
                  placeholder="Describe the bug in detail. What were you doing? What did you see? Include any error messages you noticed. The more detail the better — even things that seem irrelevant can help us reproduce the issue."
                  className="w-full bg-surface-raised border border-border rounded-md px-3 py-2 text-sm text-text placeholder:text-text-subtle focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all resize-y min-h-[100px]"
                />
                {description.length > 0 && description.length < 10 && (
                  <p className="text-[10px] text-warning mt-0.5">Please provide at least 10 characters.</p>
                )}
              </div>

              {/* Steps to reproduce */}
              <div>
                <label className="block text-xs font-medium text-text-muted mb-1">
                  Steps to Reproduce <span className="text-text-subtle">(highly recommended)</span>
                </label>
                <textarea
                  value={steps}
                  onChange={(e) => setSteps(e.target.value)}
                  rows={3}
                  placeholder={"1. Opened project 'my-app'\n2. Clicked 'Rebuild Knowledge Base'\n3. Build reached 50% then froze\n4. Console showed ERROR from codrag.core.index"}
                  className="w-full bg-surface-raised border border-border rounded-md px-3 py-2 text-sm text-text placeholder:text-text-subtle focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all resize-y"
                />
              </div>

              {/* Advanced: Expected / Actual */}
              <div>
                <button
                  type="button"
                  onClick={() => setShowAdvanced(!showAdvanced)}
                  className="flex items-center gap-1 text-xs text-text-subtle hover:text-text-muted transition-colors"
                >
                  {showAdvanced ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                  <span>Expected vs. Actual behavior</span>
                </button>
                {showAdvanced && (
                  <div className="mt-2 space-y-3 animate-in fade-in slide-in-from-top-1 duration-150">
                    <div>
                      <label className="block text-[10px] font-medium text-text-subtle mb-0.5">Expected</label>
                      <input
                        type="text"
                        value={expected}
                        onChange={(e) => setExpected(e.target.value)}
                        placeholder="What did you expect to happen?"
                        className="w-full bg-surface-raised border border-border rounded-md px-3 py-1.5 text-xs text-text placeholder:text-text-subtle focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
                      />
                    </div>
                    <div>
                      <label className="block text-[10px] font-medium text-text-subtle mb-0.5">Actual</label>
                      <input
                        type="text"
                        value={actual}
                        onChange={(e) => setActual(e.target.value)}
                        placeholder="What actually happened?"
                        className="w-full bg-surface-raised border border-border rounded-md px-3 py-1.5 text-xs text-text placeholder:text-text-subtle focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
                      />
                    </div>
                  </div>
                )}
              </div>

              {/* Diagnostics preview */}
              <div className="border-t border-border/50 pt-3">
                <button
                  type="button"
                  onClick={() => setShowDiagnostics(!showDiagnostics)}
                  className="flex items-center gap-1.5 text-xs text-text-subtle hover:text-text-muted transition-colors"
                >
                  {showDiagnostics ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                  <span className="font-medium">What we'll include automatically</span>
                  <span className="text-[10px] bg-surface-raised border border-border px-1.5 py-0.5 rounded-full font-mono">
                    {logSummary.total} logs
                    {logSummary.errors > 0 && <span className="text-error ml-1">{logSummary.errors} errors</span>}
                  </span>
                </button>
                {showDiagnostics && (
                  <div className="mt-2 rounded-md border border-border bg-surface-raised/50 p-3 text-[11px] text-text-muted space-y-1 animate-in fade-in slide-in-from-top-1 duration-150 max-h-32 overflow-y-auto">
                    <div><strong>Platform:</strong> {navigator.platform}, {navigator.userAgent.slice(0, 60)}...</div>
                    <div><strong>Logs:</strong> {logSummary.total} entries ({logSummary.errors} errors, {logSummary.warnings} warnings)</div>
                    {diagnosticData?.project != null && (
                      <div><strong>Project:</strong> {String((diagnosticData.project as Record<string, unknown>)?.name ?? 'unknown')} ({String((diagnosticData.project as Record<string, unknown>)?.mode ?? '?')})</div>
                    )}
                    {diagnosticData?.license_tier != null && (
                      <div><strong>License:</strong> {String(diagnosticData.license_tier)}</div>
                    )}
                    {diagnosticData?.project_status != null && (
                      <div><strong>Status:</strong> building={String((diagnosticData.project_status as Record<string, unknown>)?.building)}, stale={String((diagnosticData.project_status as Record<string, unknown>)?.stale)}</div>
                    )}
                    <div className="text-text-subtle italic pt-1">Full project config, trace status, watch status, and enrichment state are included.</div>
                  </div>
                )}
              </div>

              {/* Submit error banner */}
              {submitState === 'failed' && submitError && (
                <div className="flex items-start gap-2 p-3 rounded-md bg-warning/10 border border-warning/20 text-warning text-xs">
                  <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                  <div className="space-y-1">
                    <p>{submitError}</p>
                    <p className="text-text-muted">
                      The report was downloaded as a file. Please attach it to an email at{' '}
                      <a href="mailto:support@codrag.io" className="underline">support@codrag.io</a>.
                    </p>
                  </div>
                </div>
              )}
            </div>

            {/* Footer actions */}
            <div className="flex items-center justify-between gap-3 px-5 py-3 border-t border-border bg-surface-raised/30 shrink-0">
              <Button
                variant="ghost"
                size="sm"
                onClick={handleDownloadOnly}
                title="Download report as file"
                className="text-text-subtle"
              >
                <Download className="w-3.5 h-3.5 mr-1.5" />
                Download
              </Button>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={onClose}>
                  Cancel
                </Button>
                <Button
                  size="sm"
                  disabled={!canSubmit || submitState === 'submitting'}
                  loading={submitState === 'submitting'}
                  onClick={handleSubmit}
                >
                  <Send className="w-3.5 h-3.5 mr-1.5" />
                  {submitState === 'submitting' ? 'Sending...' : 'Send Report'}
                </Button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>,
    document.body,
  );
}
