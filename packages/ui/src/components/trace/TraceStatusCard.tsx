import { Card, Badge } from '@tremor/react';
import { Zap } from 'lucide-react';
import { Button } from '../primitives/Button';
import { cn } from '../../lib/utils';
import { ProgressIndicator } from '../status/ProgressIndicator';
import type { TraceStatus, TaskProgress } from '../../types';

const LANG_LABELS: Record<string, string> = {
  python: 'Python',
  typescript: 'TS',
  javascript: 'JS',
  go: 'Go',
  rust: 'Rust',
  java: 'Java',
  c: 'C',
  cpp: 'C++',
};

export interface TraceStatusCardProps {
  status: TraceStatus;
  progress?: TaskProgress;
  onEnableTrace?: () => void;
  onBuildTrace?: () => void;
  className?: string;
}

export function TraceStatusCard({
  status,
  progress,
  onEnableTrace,
  onBuildTrace,
  className,
}: TraceStatusCardProps) {
  // Construct effective progress for display
  // If building but no progress object yet, show indeterminate
  const effectiveProgress = progress || (status.building ? {
    task_id: 'pending_trace',
    message: 'Building graph...',
    current: 0,
    total: 100,
    percent: 0,
    status: 'running'
  } as TaskProgress : undefined);

  return (
    <Card className={cn('prep-trace-status-card', className)}>
      <div className="space-y-6">
        <div className="flex items-start justify-between">
          <div>
            <h3 className="text-sm font-semibold">Code Graph</h3>
            <p className="text-xs text-gray-500 mt-1">
              Structural index for symbols and imports
            </p>
          </div>
          
          <div className="flex items-center gap-2">
            {status.engine && (
              <Badge color={status.engine === 'rust' ? 'orange' : 'gray'}>
                {status.engine === 'rust' && <Zap className="w-3 h-3 mr-1 inline" />}
                {status.engine === 'rust' ? 'Rust Engine' : 'Python'}
              </Badge>
            )}
            {!status.enabled && (
              <Badge color="gray">Disabled</Badge>
            )}
            {status.enabled && !status.exists && (
              <Badge color="yellow">Not Built</Badge>
            )}
            {status.enabled && status.exists && !status.building && (
              <Badge color="green">Ready</Badge>
            )}
            {status.building && (
              <Badge color="blue">Building</Badge>
            )}
          </div>
        </div>

        {effectiveProgress && (
          <div>
            <ProgressIndicator progress={effectiveProgress} />
          </div>
        )}

        {status.enabled && status.exists && (
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-2xl font-bold">{status.counts.nodes.toLocaleString()}</p>
              <p className="text-xs text-gray-500">Nodes</p>
            </div>
            <div>
              <p className="text-2xl font-bold">{status.counts.edges.toLocaleString()}</p>
              <p className="text-xs text-gray-500">Edges</p>
            </div>
          </div>
        )}

        {status.supported_languages && status.supported_languages.length > 0 && status.enabled && (
          <div className="flex flex-wrap gap-1">
            {status.supported_languages.map((lang) => (
              <span
                key={lang}
                className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-surface-raised text-text-muted border border-border"
              >
                {LANG_LABELS[lang] || lang}
              </span>
            ))}
          </div>
        )}

        {(status.last_build_at || status.last_error) && (
          <div className="space-y-3">
            {status.last_build_at && (
              <p className="text-xs text-gray-500">
                Last built: {status.last_build_at}
              </p>
            )}

            {status.last_error && (
              <div className="rounded bg-red-50 p-2 text-xs text-red-700 dark:bg-red-900/20 dark:text-red-400">
                {status.last_error}
              </div>
            )}
          </div>
        )}

        <div className="flex gap-2">
          {!status.enabled && onEnableTrace && (
            <Button size="sm" onClick={onEnableTrace}>
              Enable Code Graph
            </Button>
          )}
          {status.enabled && !status.building && onBuildTrace && (
            <Button size="sm" variant="secondary" onClick={onBuildTrace}>
              {status.exists ? 'Rebuild Graph' : 'Build Graph'}
            </Button>
          )}
        </div>
      </div>
    </Card>
  );
}
