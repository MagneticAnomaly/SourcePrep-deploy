import { cn } from '../../lib/utils';
import { Select } from '../primitives/Select';
import { StepperNumberInput } from '../primitives/StepperNumberInput';
import { Checkbox } from '../primitives/Checkbox';
import { Calendar, Gauge, Info, Zap } from 'lucide-react';

export interface DeepAnalysisSchedule {
  mode: 'manual' | 'auto' | 'scheduled';
  /** Whether the threshold trigger is active (scheduled mode) */
  schedule_threshold_enabled?: boolean;
  threshold_percent?: number;
  /** Whether the time-based trigger is active (scheduled mode) */
  schedule_time_enabled?: boolean;
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
  largeModelConfigured?: boolean;
  fastModelConfigured?: boolean;
  className?: string;
}

const MODE_OPTIONS = [
  { value: 'manual', label: 'Manual — run from dashboard' },
  { value: 'auto', label: 'Auto — continuous after Fast Sync' },
  { value: 'scheduled', label: 'Scheduled — time or threshold' },
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

export function DeepAnalysisSettings({
  schedule,
  onScheduleChange,
  largeModelConfigured = false,
  fastModelConfigured = false,
  className,
}: DeepAnalysisSettingsProps) {
  const update = (patch: Partial<DeepAnalysisSchedule>) =>
    onScheduleChange({ ...schedule, ...patch });

  return (
    <div className={cn('space-y-6', className)}>
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

      {/* Mode selector */}
      <section className="space-y-3">
        <h4 className="text-xs font-medium font-mono text-text-muted uppercase tracking-wide flex items-center gap-1.5">
          <Calendar className="w-3.5 h-3.5" /> Trigger Mode
        </h4>
        <Select
          value={schedule.mode}
          onChange={(e) => update({ mode: e.target.value as DeepAnalysisSchedule['mode'] })}
          options={MODE_OPTIONS}
          size="sm"
          disabled={!largeModelConfigured && !fastModelConfigured}
        />

        {/* Auto: brief hint */}
        {schedule.mode === 'auto' && (
          <div className="flex gap-2 p-2 rounded-md bg-purple-500/10 border border-purple-500/20 text-purple-400">
            <Zap className="w-3.5 h-3.5 shrink-0 mt-0.5" />
            <span className="text-xs">Runs automatically after every Fast Sync. Ideal for Ollama / local models.</span>
          </div>
        )}

        {/* Scheduled: threshold first, then time-based — checkboxes prevent both off */}
        {schedule.mode === 'scheduled' && (() => {
          const threshEnabled = schedule.schedule_threshold_enabled !== false;
          const timeEnabled = schedule.schedule_time_enabled !== false;
          const disabled = !largeModelConfigured && !fastModelConfigured;
          const toggleThresh = () => {
            if (threshEnabled && !timeEnabled) return;
            update({ schedule_threshold_enabled: !threshEnabled });
          };
          const toggleTime = () => {
            if (timeEnabled && !threshEnabled) return;
            update({ schedule_time_enabled: !timeEnabled });
          };
          return (
            <div className="space-y-3 pt-1">
              {/* Threshold trigger */}
              <div className="rounded border border-border p-3 space-y-2">
                <label className="flex items-center gap-2 cursor-pointer">
                  <Checkbox
                    checked={threshEnabled}
                    onCheckedChange={toggleThresh}
                    disabled={disabled}
                    size="sm"
                  />
                  <span className="text-xs font-medium text-text">Threshold — when files change</span>
                </label>
                <div className={cn('space-y-1 pl-5', !threshEnabled && 'opacity-50 pointer-events-none')}>
                  <label className="text-xs text-text-muted">
                    Trigger when &gt; <strong>{schedule.threshold_percent ?? 20}%</strong> of files changed
                  </label>
                  <StepperNumberInput
                    value={schedule.threshold_percent ?? 20}
                    onValueChange={(v) => update({ threshold_percent: v })}
                    min={5}
                    max={80}
                    step={5}
                    disabled={!threshEnabled || disabled}
                  />
                </div>
              </div>

              {/* Time-based trigger */}
              <div className="rounded border border-border p-3 space-y-2">
                <label className="flex items-center gap-2 cursor-pointer">
                  <Checkbox
                    checked={timeEnabled}
                    onCheckedChange={toggleTime}
                    disabled={disabled}
                    size="sm"
                  />
                  <span className="text-xs font-medium text-text">Schedule — time-based</span>
                </label>
                <div className={cn('space-y-2 pl-5', !timeEnabled && 'opacity-50 pointer-events-none')}>
                    <div className="grid grid-cols-2 gap-2">
                      <div className="space-y-1">
                        <label className="text-xs text-text-muted">Frequency</label>
                        <Select
                          value={schedule.frequency ?? 'weekly'}
                          onChange={(e) => update({ frequency: e.target.value as DeepAnalysisSchedule['frequency'] })}
                          options={FREQUENCY_OPTIONS}
                          size="sm"
                          disabled={!timeEnabled || disabled}
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
                            disabled={!timeEnabled || disabled}
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
                        disabled={!timeEnabled || disabled}
                      />
                    </div>
                  </div>
              </div>
            </div>
          );
        })()}
      </section>

      {/* Budget controls */}
      <section className="space-y-3">
        <h4 className="text-xs font-medium font-mono text-text-muted uppercase tracking-wide flex items-center gap-1.5">
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
        <h4 className="text-xs font-medium font-mono text-text-muted uppercase tracking-wide">Priority</h4>
        <Select
          value={schedule.priority}
          onChange={(e) => update({ priority: e.target.value as DeepAnalysisSchedule['priority'] })}
          options={PRIORITY_OPTIONS}
          size="sm"
          disabled={!largeModelConfigured && !fastModelConfigured}
        />
      </section>
    </div>
  );
}
