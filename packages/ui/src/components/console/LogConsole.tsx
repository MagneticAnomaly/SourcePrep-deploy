import { useState, useRef, useEffect, useMemo } from 'react';
import { Terminal, XCircle, ChevronDown, ChevronRight, Bug } from 'lucide-react';
import { cn } from '../../lib/utils';
import { Button } from '../primitives/Button';
import { BugReportModal } from './BugReportModal';
import type { LogEntry } from '../../types';

export interface LogConsoleProps {
  logs: LogEntry[];
  onClear: () => void;
  className?: string;
  defaultExpanded?: boolean;
  /** Extra diagnostic data to bundle into bug reports (project status, config, tier, etc.) */
  diagnosticData?: Record<string, unknown>;
}

type LogLevel = 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL';

export function LogConsole({
  logs,
  onClear,
  className,
  defaultExpanded = false,
  diagnosticData,
}: LogConsoleProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const [autoScroll, setAutoScroll] = useState(true);
  const [filterLevel, setFilterLevel] = useState<LogLevel | 'ALL'>('ALL');
  const [bugReportOpen, setBugReportOpen] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll effect
  useEffect(() => {
    if (autoScroll && scrollRef.current && expanded) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs, autoScroll, expanded]);

  // Handle scroll events to toggle auto-scroll
  const handleScroll = () => {
    if (!scrollRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
    const isAtBottom = Math.abs(scrollHeight - scrollTop - clientHeight) < 20;
    setAutoScroll(isAtBottom);
  };

  const filteredLogs = useMemo(() => {
    if (filterLevel === 'ALL') return logs;
    // Simple severity check: ERROR includes CRITICAL, WARNING includes ERROR+, INFO includes all but DEBUG
    if (filterLevel === 'ERROR') {
      return logs.filter(l => ['ERROR', 'CRITICAL'].includes(l.level));
    }
    if (filterLevel === 'WARNING') {
      return logs.filter(l => ['WARNING', 'ERROR', 'CRITICAL'].includes(l.level));
    }
    if (filterLevel === 'INFO') {
      return logs.filter(l => l.level !== 'DEBUG');
    }
    return logs; // DEBUG matches everything passed to frontend (usually INFO+)
  }, [logs, filterLevel]);

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
    <div className={cn('flex flex-col border-t border-border bg-surface-raised', className)}>
      {/* Toolbar */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-border/50 bg-surface">
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-2 text-xs font-semibold text-text hover:text-primary transition-colors"
        >
          {expanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
          <div className="flex items-center gap-2">
            <Terminal className="w-3.5 h-3.5" />
            <span>Console</span>
            <span className="bg-surface-raised border border-border px-1.5 py-0.5 rounded-full text-[10px] text-text-subtle font-mono">
              {logs.length}
            </span>
          </div>
        </button>

        {expanded && (
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1 bg-surface border border-border rounded-md p-0.5">
              {(['ALL', 'INFO', 'WARNING', 'ERROR'] as const).map((lvl) => (
                <button
                  key={lvl}
                  onClick={() => setFilterLevel(lvl)}
                  className={cn(
                    "px-2 py-0.5 text-[10px] rounded hover:bg-surface-raised transition-colors",
                    filterLevel === lvl ? "bg-primary/10 text-primary font-medium" : "text-text-subtle"
                  )}
                >
                  {lvl === 'ALL' ? 'All' : lvl}
                </button>
              ))}
            </div>
            <div className="w-px h-4 bg-border mx-1" />
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
        )}
      </div>

      {/* Bug Report Modal */}
      <BugReportModal
        open={bugReportOpen}
        onClose={() => setBugReportOpen(false)}
        logs={logs}
        diagnosticData={diagnosticData}
      />

      {/* Log Output */}
      {expanded && (
        <div
          ref={scrollRef}
          onScroll={handleScroll}
          className="flex-1 overflow-y-auto min-h-0 p-2 font-mono text-xs space-y-0.5 bg-[#0d1117]"
          style={{ height: '200px' }} // Fixed height when expanded
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
      )}
    </div>
  );
}
