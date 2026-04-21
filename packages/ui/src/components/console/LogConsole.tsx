import { useState, useRef, useEffect, useMemo } from 'react';
import { XCircle, Bug } from 'lucide-react';
import { cn } from '../../lib/utils';
import { Button } from '../primitives/Button';
import { BugReportModal } from './BugReportModal';
import type { LogEntry } from '../../types';

export interface LogConsoleProps {
  logs: LogEntry[];
  onClear: () => void;
  className?: string;
  /** @deprecated no longer used — console is always expanded */
  defaultExpanded?: boolean;
  /** Extra diagnostic data to bundle into bug reports (project status, config, tier, etc.) */
  diagnosticData?: Record<string, unknown>;
}

type FilterTag = 'PIPELINE' | 'INFO' | 'WARNING' | 'ERROR' | 'HTTP';

const _isHttpLog = (log: LogEntry) =>
  log.logger === 'uvicorn.access' ||
  log.message.includes('/health') ||
  log.message.includes('/trace/coverage') ||
  log.message.includes('/augment/status') ||
  log.message.includes('/pipeline/status') ||
  log.message.includes('/knowledge/status');

const _isPipelineLog = (log: LogEntry) =>
  log.logger.startsWith('prep.services.pipeline') ||
  log.logger.startsWith('prep.core.augmenter') ||
  log.logger.startsWith('prep.core.inferred_edges') ||
  log.logger.startsWith('prep.core.epistemic') ||
  log.logger.startsWith('prep.core.cluster') ||
  log.logger.startsWith('prep.core.atlas') ||
  log.logger.startsWith('prep.core.deepening') ||
  log.logger.startsWith('prep.core.group_reasoning');

export function LogConsole({
  logs,
  onClear,
  className,
  diagnosticData,
}: LogConsoleProps) {
  const [autoScroll, setAutoScroll] = useState(true);
  // Multi-select: set of active filter tags. Empty set = show ALL.
  const [activeFilters, setActiveFilters] = useState<Set<FilterTag>>(new Set());
  const [bugReportOpen, setBugReportOpen] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const toggleFilter = (tag: FilterTag) => {
    setActiveFilters(prev => {
      const next = new Set(prev);
      if (next.has(tag)) next.delete(tag); else next.add(tag);
      return next;
    });
  };
  const clearFilters = () => setActiveFilters(new Set());
  const isAllActive = activeFilters.size === 0;

  // Auto-scroll effect
  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs, autoScroll]);

  // Handle scroll events to toggle auto-scroll
  const handleScroll = () => {
    if (!scrollRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
    const isAtBottom = Math.abs(scrollHeight - scrollTop - clientHeight) < 20;
    setAutoScroll(isAtBottom);
  };

  const filteredLogs = useMemo(() => {
    if (isAllActive) {
      // Default: show everything EXCEPT HTTP polling noise
      return logs.filter(l => !_isHttpLog(l));
    }
    return logs.filter(l => {
      // Each active tag is an OR filter — log matches if ANY tag matches
      for (const tag of activeFilters) {
        if (tag === 'HTTP' && _isHttpLog(l)) return true;
        if (tag === 'PIPELINE' && _isPipelineLog(l)) return true;
        if (tag === 'ERROR' && ['ERROR', 'CRITICAL'].includes(l.level)) return true;
        if (tag === 'WARNING' && l.level === 'WARNING') return true;
        if (tag === 'INFO' && l.level === 'INFO' && !_isHttpLog(l)) return true;
      }
      return false;
    });
  }, [logs, activeFilters, isAllActive]);

  const levelColor = (level: string) => {
    switch (level) {
      case 'ERROR':
      case 'CRITICAL':
        return 'text-error';
      case 'WARNING':
        return 'text-warning';
      case 'DEBUG':
        return 'text-text-subtle';
      default:
        return 'text-text-muted';
    }
  };

  return (
    <div className={cn('flex flex-col', className)}>
      {/* Toolbar */}
      <div className="flex items-center justify-between px-2 py-1 border-b border-border/50 bg-surface shrink-0">
        {/* Left: multi-select filter buttons */}
        <div className="flex items-center gap-0.5">
          <button
            onClick={clearFilters}
            className={cn(
              "px-2 py-0.5 text-[10px] rounded hover:bg-surface-raised transition-colors",
              isAllActive ? "bg-primary/10 text-primary font-medium" : "text-text-subtle"
            )}
          >
            All
          </button>
          {(['PIPELINE', 'INFO', 'WARNING', 'ERROR', 'HTTP'] as FilterTag[]).map((tag) => (
            <button
              key={tag}
              onClick={() => toggleFilter(tag)}
              className={cn(
                "px-2 py-0.5 text-[10px] rounded hover:bg-surface-raised transition-colors",
                activeFilters.has(tag) ? (
                  tag === 'ERROR' ? "bg-error/15 text-error font-medium" :
                  tag === 'WARNING' ? "bg-warning/15 text-warning font-medium" :
                  tag === 'PIPELINE' ? "bg-blue-500/15 text-blue-400 font-medium" :
                  tag === 'HTTP' ? "bg-text-subtle/15 text-text-muted font-medium" :
                  "bg-primary/10 text-primary font-medium"
                ) : "text-text-subtle"
              )}
            >
              {tag}
            </button>
          ))}
        </div>
        {/* Right: action buttons */}
        <div className="flex items-center gap-0.5">
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={() => setBugReportOpen(true)}
            title="Send Bug Report"
            className="h-6 w-6 text-text-subtle hover:text-warning"
          >
            <Bug className="w-3.5 h-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={onClear}
            title="Clear Console"
            className="h-6 w-6"
          >
            <XCircle className="w-3.5 h-3.5" />
          </Button>
        </div>
      </div>

      {/* Bug Report Modal */}
      <BugReportModal
        open={bugReportOpen}
        onClose={() => setBugReportOpen(false)}
        logs={logs}
        diagnosticData={diagnosticData}
      />

      {/* Log Output */}
      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto min-h-0 font-mono text-xs bg-[#0d1117]"
      >
        {filteredLogs.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-text-subtle/50 italic select-none">
            <span>No logs captured</span>
          </div>
        ) : (
          filteredLogs.map((log, i) => (
            <div key={i} className="flex gap-2 leading-relaxed hover:bg-white/5 px-1 rounded-sm group">
              <span className="text-text-subtle/40 select-none shrink-0 w-[70px]">
                {new Date(log.timestamp * 1000).toLocaleTimeString([], { hour12: false, hour: '2-digit', minute:'2-digit', second:'2-digit' })}
              </span>
              <span className={cn("shrink-0 w-[60px] font-bold", levelColor(log.level))}>
                {log.level}
              </span>
              <span className="text-text-subtle/70 shrink-0 w-[120px] truncate" title={log.logger}>
                [{log.logger}]
              </span>
              <span className="text-text-muted break-all whitespace-pre-wrap flex-1">
                {log.message}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
