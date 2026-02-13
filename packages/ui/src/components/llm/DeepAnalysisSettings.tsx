import { cn } from '../../lib/utils';
import { Button } from '../primitives/Button';
import { Select } from '../primitives/Select';
import { StepperNumberInput } from '../primitives/StepperNumberInput';
import { Brain, Calendar, Clock, Gauge, Play, Info, AlertTriangle, CheckCircle, Square, Loader2 } from 'lucide-react';

export interface DeepAnalysisSchedule {
  mode: 'manual' | 'threshold' | 'scheduled';
  threshold_percent?: number;
  frequency?: 'daily' | 'weekly' | 'biweekly' | 'monthly';
  day_of_week?: number;
  hour?: number;
  budget_enabled: boolean;
  budget_max_tokens: number;
  budget_max_minutes: number;
  budget_max_items: number;
  priority: 'lowest_confidence' | 'highest_connectivity';
}

export interface DeepAnalysisStatus {
  last_run_at?: string;
  last_run_items?: number;
  last_run_tokens?: number;
  next_run_at?: string;
  queue_size?: number;
  avg_confidence?: number;
  stop_reason?: string;
  budget_exhausted?: boolean;
  queue_remaining?: number;
  progress_pct?: number;
  progress_current?: number;
  progress_total?: number;
}

export interface DeepAnalysisSettingsProps {
  schedule: DeepAnalysisSchedule;
  onScheduleChange: (schedule: DeepAnalysisSchedule) => void;
  status?: DeepAnalysisStatus;
  largeModelConfigured?: boolean;
  fastModelConfigured?: boolean;
  onRunNow?: () => void;
  onCancel?: () => void;
  running?: boolean;
  className?: string;
}

const MODE_OPTIONS = [
  { value: 'manual', label: 'Manual only (run from dashboard)' },
  { value: 'threshold', label: 'After major changes' },
  { value: 'scheduled', label: 'Scheduled' },
];

const FREQUENCY_OPTIONS = [
  { value: 'daily', label: 'Daily' },
  { value: 'weekly', label: 'Weekly' },
  { value: 'biweekly', label: 'Every 2 weeks' },
  { value: 'monthly', label: 'Monthly' },
];

const DAY_OPTIONS = [
  { value: '0', label: 'Sunday' },
  { value: '1', label: 'Monday' },
  { value: '2', label: 'Tuesday' },
  { value: '3', label: 'Wednesday' },
  { value: '4', label: 'Thursday' },
  { value: '5', label: 'Friday' },
  { value: '6', label: 'Saturday' },
];

const HOUR_OPTIONS = Array.from({ length: 24 }, (_, i) => ({
  value: String(i),
  label: `${i === 0 ? '12' : i > 12 ? String(i - 12) : String(i)}:00 ${i < 12 ? 'AM' : 'PM'}`,
}));

const PRIORITY_OPTIONS = [
  { value: 'lowest_confidence', label: 'Lowest confidence first' },
  { value: 'highest_connectivity', label: 'Most-connected first' },
];

function formatDate(iso?: string): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

function formatNumber(n?: number): string {
  if (n == null) return '—';
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return String(n);
}

const STOP_REASON_MAP: Record<string, { label: string; color: string; Icon: typeof CheckCircle }> = {
  complete: { label: 'Session complete', color: 'text-emerald-400', Icon: CheckCircle },
  empty_queue: { label: 'Queue empty', color: 'text-emerald-400', Icon: CheckCircle },
  budget_tokens: { label: 'Token budget reached', color: 'text-amber-400', Icon: AlertTriangle },
  budget_time: { label: 'Time budget reached', color: 'text-amber-400', Icon: AlertTriangle },
  budget_items: { label: 'Item limit reached', color: 'text-amber-400', Icon: AlertTriangle },
  cancelled: { label: 'Cancelled by user', color: 'text-text-muted', Icon: Square },
};

function StopReasonBadge({ reason }: { reason: string }) {
  const info = STOP_REASON_MAP[reason];
  if (!info) return <span className="text-text-muted text-xs">{reason}</span>;
  const { label, color, Icon } = info;
  return (
    <span className={`inline-flex items-center gap-1 text-xs font-medium ${color}`}>
      <Icon className="w-3 h-3" />
      {label}
    </span>
  );
}

export function DeepAnalysisSettings({
  schedule,
  onScheduleChange,
  status,
  largeModelConfigured = false,
  fastModelConfigured = false,
  onRunNow,
  onCancel,
  running = false,
  className,
}: DeepAnalysisSettingsProps) {
  const update = (patch: Partial<DeepAnalysisSchedule>) =>
    onScheduleChange({ ...schedule, ...patch });

  return (
    <div className={cn('space-y-6', className)}>
      {/* Header */}
      <div className="flex items-start gap-3">
        <Brain className="w-5 h-5 text-purple-400 mt-0.5 shrink-0" />
        <div>
          <h3 className="text-sm font-semibold text-text">Deep Analysis</h3>
          <p className="text-xs text-text-muted mt-0.5">
            Reasoning model validates augmentations and builds codebase ontology.
            Uses <strong>Tier 0 (ground truth)</strong> evidence only — no hallucination risk.
          </p>
        </div>
      </div>

      {/* Model requirement warning */}
      {!largeModelConfigured && !fastModelConfigured && (
        <div className="flex gap-2 p-3 rounded-md bg-amber-500/10 border border-amber-500/20 text-amber-500">
          <Info className="w-4 h-4 shrink-0 mt-0.5" />
          <span className="text-xs">
            Configure a model in <strong>AI Models</strong> settings to enable deep analysis.
          </span>
        </div>
      )}
      {!largeModelConfigured && fastModelConfigured && (
        <div className="flex gap-2 p-3 rounded-md bg-blue-500/10 border border-blue-500/20 text-blue-400">
          <Info className="w-4 h-4 shrink-0 mt-0.5" />
          <span className="text-xs">
            Using <strong>Fast Model</strong> for deep analysis. For best results, configure a <strong>Thinking Model</strong> (reasoning-capable).
          </span>
        </div>
      )}

      {/* Schedule mode */}
      <section className="space-y-3">
        <h4 className="text-xs font-medium text-text-muted uppercase tracking-wide flex items-center gap-1.5">
          <Calendar className="w-3.5 h-3.5" /> Schedule
        </h4>
        <Select
          value={schedule.mode}
          onChange={(e) => update({ mode: e.target.value as DeepAnalysisSchedule['mode'] })}
          options={MODE_OPTIONS}
          size="sm"
          disabled={!largeModelConfigured && !fastModelConfigured}
        />

        {schedule.mode === 'threshold' && (
          <div className="space-y-1.5 pl-1">
            <label className="text-xs text-text-muted">
              Trigger when &gt; <strong>{schedule.threshold_percent ?? 20}%</strong> of files changed
            </label>
            <StepperNumberInput
              value={schedule.threshold_percent ?? 20}
              onValueChange={(v) => update({ threshold_percent: v })}
              min={5}
              max={80}
              step={5}
              disabled={!largeModelConfigured && !fastModelConfigured}
            />
          </div>
        )}

        {schedule.mode === 'scheduled' && (
          <div className="space-y-3 pl-1">
            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1">
                <label className="text-xs text-text-muted">Frequency</label>
                <Select
                  value={schedule.frequency ?? 'weekly'}
                  onChange={(e) => update({ frequency: e.target.value as DeepAnalysisSchedule['frequency'] })}
                  options={FREQUENCY_OPTIONS}
                  size="sm"
                  disabled={!largeModelConfigured && !fastModelConfigured}
                />
              </div>
              {(schedule.frequency ?? 'weekly') !== 'daily' && (
                <div className="space-y-1">
                  <label className="text-xs text-text-muted">Day</label>
                  <Select
                    value={String(schedule.day_of_week ?? 0)}
                    onChange={(e) => update({ day_of_week: Number(e.target.value) })}
                    options={DAY_OPTIONS}
                    size="sm"
                    disabled={!largeModelConfigured && !fastModelConfigured}
                  />
                </div>
              )}
            </div>
            <div className="space-y-1">
              <label className="text-xs text-text-muted">Time</label>
              <Select
                value={String(schedule.hour ?? 2)}
                onChange={(e) => update({ hour: Number(e.target.value) })}
                options={HOUR_OPTIONS}
                size="sm"
                disabled={!largeModelConfigured && !fastModelConfigured}
              />
            </div>
          </div>
        )}
      </section>

      {/* Budget controls */}
      <section className="space-y-3">
        <h4 className="text-xs font-medium text-text-muted uppercase tracking-wide flex items-center gap-1.5">
          <Gauge className="w-3.5 h-3.5" /> Budget Per Session
        </h4>

        {/* Budget toggle */}
        <label className="flex items-center gap-2 cursor-pointer group">
          <button
            type="button"
            role="switch"
            aria-checked={schedule.budget_enabled}
            onClick={() => update({ budget_enabled: !schedule.budget_enabled })}
            disabled={!largeModelConfigured && !fastModelConfigured}
            className={cn(
              'relative inline-flex h-5 w-9 shrink-0 rounded-full border-2 border-transparent transition-colors',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-purple-500/50',
              'disabled:cursor-not-allowed disabled:opacity-50',
              schedule.budget_enabled ? 'bg-purple-500' : 'bg-surface-raised border-border',
            )}
          >
            <span
              className={cn(
                'pointer-events-none block h-4 w-4 rounded-full bg-white shadow-sm transition-transform',
                schedule.budget_enabled ? 'translate-x-4' : 'translate-x-0',
              )}
            />
          </button>
          <span className="text-xs text-text-muted group-hover:text-text transition-colors">
            {schedule.budget_enabled ? 'Budget limits enabled (recommended for BYOK / cloud)' : 'No limits (recommended for Ollama / local)'}
          </span>
        </label>

        {!schedule.budget_enabled && (
          <div className="flex gap-2 p-2.5 rounded-md bg-blue-500/10 border border-blue-500/20 text-blue-400">
            <Info className="w-3.5 h-3.5 shrink-0 mt-0.5" />
            <span className="text-xs">
              Budget limits are <strong>disabled</strong>. Analysis will run until the queue is empty or manually stopped.
              Recommended when running local models via Ollama — no cost per token.
            </span>
          </div>
        )}

        {schedule.budget_enabled && (
          <div className="space-y-3">
            <div className="space-y-1">
              <label className="text-xs text-text-muted">Max tokens</label>
              <StepperNumberInput
                value={schedule.budget_max_tokens}
                onValueChange={(v) => update({ budget_max_tokens: v })}
                min={1000}
                max={500000}
                step={5000}
                disabled={!largeModelConfigured && !fastModelConfigured}
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-text-muted">Max time (minutes)</label>
              <StepperNumberInput
                value={schedule.budget_max_minutes}
                onValueChange={(v) => update({ budget_max_minutes: v })}
                min={5}
                max={480}
                step={5}
                disabled={!largeModelConfigured && !fastModelConfigured}
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-text-muted">Max items per session</label>
              <StepperNumberInput
                value={schedule.budget_max_items}
                onValueChange={(v) => update({ budget_max_items: v })}
                min={10}
                max={1000}
                step={10}
                disabled={!largeModelConfigured && !fastModelConfigured}
              />
            </div>
          </div>
        )}
      </section>

      {/* Priority */}
      <section className="space-y-2">
        <h4 className="text-xs font-medium text-text-muted uppercase tracking-wide">Priority</h4>
        <Select
          value={schedule.priority}
          onChange={(e) => update({ priority: e.target.value as DeepAnalysisSchedule['priority'] })}
          options={PRIORITY_OPTIONS}
          size="sm"
          disabled={!largeModelConfigured && !fastModelConfigured}
        />
      </section>

      {/* Status */}
      {status && (
        <section className="space-y-2">
          <h4 className="text-xs font-medium text-text-muted uppercase tracking-wide flex items-center gap-1.5">
            <Clock className="w-3.5 h-3.5" /> Status
          </h4>
          <div className="rounded-md border border-border bg-surface-raised p-3 space-y-1.5 text-xs">
            <div className="flex justify-between">
              <span className="text-text-muted">Last run</span>
              <span className="text-text font-medium">
                {formatDate(status.last_run_at)}
                {status.last_run_items != null && ` — ${status.last_run_items} items`}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-muted">Tokens used</span>
              <span className="text-text font-medium">{formatNumber(status.last_run_tokens)}</span>
            </div>
            {status.stop_reason && (
              <div className="flex justify-between items-center">
                <span className="text-text-muted">Stopped because</span>
                <StopReasonBadge reason={status.stop_reason} />
              </div>
            )}
            {schedule.mode !== 'manual' && (
              <div className="flex justify-between">
                <span className="text-text-muted">Next run</span>
                <span className="text-text font-medium">{formatDate(status.next_run_at)}</span>
              </div>
            )}
            <div className="flex justify-between">
              <span className="text-text-muted">Validation queue</span>
              <span className="text-text font-medium">
                {formatNumber(status.queue_size)} items
                {status.avg_confidence != null && status.avg_confidence > 0 && (
                  <span className="text-text-subtle ml-1">(avg conf: {(status.avg_confidence * 100).toFixed(0)}%)</span>
                )}
              </span>
            </div>
          </div>

          {/* Actionable hint when budget was exhausted */}
          {status.budget_exhausted && (status.queue_remaining ?? 0) > 0 && (
            <div className="flex gap-2 p-2.5 rounded-md bg-amber-500/10 border border-amber-500/20 text-amber-400">
              <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
              <span className="text-xs">
                {formatNumber(status.queue_remaining)} items remain. Run again or increase the budget to continue.
              </span>
            </div>
          )}
        </section>
      )}

      {/* Running progress */}
      {running && status && (
        <section className="space-y-2">
          <h4 className="text-xs font-medium text-text-muted uppercase tracking-wide flex items-center gap-1.5">
            <Loader2 className="w-3.5 h-3.5 animate-spin text-purple-400" /> Running
          </h4>
          <div className="rounded-md border border-purple-500/30 bg-purple-500/5 p-3 space-y-2">
            <div className="flex justify-between text-xs">
              <span className="text-text-muted">Progress</span>
              <span className="text-text font-medium">
                {status.progress_current ?? 0} / {status.progress_total ?? '?'} items
              </span>
            </div>
            <div className="h-1.5 rounded-full bg-surface overflow-hidden">
              <div
                className="h-full rounded-full bg-purple-500 transition-all duration-500 ease-out"
                style={{ width: `${Math.min(status.progress_pct ?? 0, 100)}%` }}
              />
            </div>
            <div className="text-right text-[10px] text-text-subtle">
              {(status.progress_pct ?? 0).toFixed(0)}%
            </div>
          </div>
        </section>
      )}

      {/* Run / Stop buttons */}
      {onRunNow && (
        <div className="flex gap-2">
          {running ? (
            <Button
              variant="destructive"
              size="sm"
              onClick={onCancel}
              disabled={!onCancel}
              className="w-full"
            >
              <Square className="w-3.5 h-3.5 mr-1.5" />
              Stop Deep Analysis
            </Button>
          ) : (
            <Button
              variant="outline"
              size="sm"
              onClick={onRunNow}
              disabled={!largeModelConfigured && !fastModelConfigured}
              className="w-full"
            >
              <Play className="w-3.5 h-3.5 mr-1.5" />
              Run Deep Analysis Now
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
