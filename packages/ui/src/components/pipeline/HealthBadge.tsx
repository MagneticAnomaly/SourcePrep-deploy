import { useState } from 'react';
import { CheckCircle2, AlertTriangle } from 'lucide-react';
import type { PipelineHealth } from '../../types';

export interface HealthBadgeProps {
  health: PipelineHealth;
}

export interface HealthSummary {
  ok: boolean;
  warnCount: number;
  label: string;
}

export function computeHealthSummary(health: PipelineHealth): HealthSummary {
  const warnCount = health.warnings.length;
  const ok = warnCount === 0;
  const label = ok
    ? 'Healthy'
    : `${warnCount} warning${warnCount === 1 ? '' : 's'}`;
  return { ok, warnCount, label };
}

export function HealthBadge({ health }: HealthBadgeProps) {
  const [expanded, setExpanded] = useState(false);
  const { ok, warnCount, label } = computeHealthSummary(health);

  return (
    <div className="inline-block">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className={`inline-flex items-center gap-1 rounded px-2 py-0.5 text-xs ${
          ok
            ? 'bg-success/10 text-success'
            : 'bg-warning/10 text-warning'
        }`}
        aria-expanded={expanded}
      >
        {ok ? (
          <CheckCircle2 className="h-3 w-3" aria-hidden />
        ) : (
          <AlertTriangle className="h-3 w-3" aria-hidden />
        )}
        {label}
      </button>
      {expanded && warnCount > 0 && (
        <ul className="mt-1 space-y-1 rounded border border-warning/30 bg-warning/5 p-2 text-xs">
          {health.warnings.map((w, i) => (
            <li key={i}>• {w}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
