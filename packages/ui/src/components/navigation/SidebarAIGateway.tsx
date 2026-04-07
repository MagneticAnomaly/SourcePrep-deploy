import { useState, useCallback } from 'react';
import { cn } from '../../lib/utils';
import {
  ChevronDown,
  ChevronRight,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  Loader2,
  Maximize2,
  Cpu,
} from 'lucide-react';
import { Button } from '../primitives/Button';
import type { LLMSlotsStatus, RunningTask, LLMSlotStatus } from '../../types';
import { TASK_LABELS } from '../../types';

export interface SidebarAIGatewayProps {
  slotsStatus: LLMSlotsStatus | null;
  collapsed?: boolean;
  onOpenDetails?: () => void;
  className?: string;
}

interface SlotInfo {
  key: string;
  label: string;
  shortLabel: string;
  status: LLMSlotStatus | undefined;
  modelSlotKey: 'embedding' | 'small' | 'large' | 'code';
}

function getSlots(slotsStatus: LLMSlotsStatus | null): SlotInfo[] {
  if (!slotsStatus) return [];
  return [
    { key: 'embedding', label: 'Embedding', shortLabel: 'Emb', status: slotsStatus.embedding, modelSlotKey: 'embedding' },
    { key: 'small_model', label: 'Fast Model', shortLabel: 'Fast', status: slotsStatus.small_model, modelSlotKey: 'small' },
    { key: 'large_model', label: 'Thinking', shortLabel: 'Think', status: slotsStatus.large_model, modelSlotKey: 'large' },
    { key: 'code_model', label: 'Code Model', shortLabel: 'Code', status: slotsStatus.code_model, modelSlotKey: 'code' },
  ];
}

function slotColor(status: LLMSlotStatus | undefined, isRunning: boolean): string {
  if (isRunning) return 'bg-blue-500';
  if (!status) return 'bg-text-muted/30';
  if (status.status === 'connected' || status.status === 'local') return 'bg-success';
  if (status.status === 'unreachable') return 'bg-error';
  if (status.configured) return 'bg-warning';
  return 'bg-text-muted/30';
}

function runningCountForSlot(
  slotKey: 'embedding' | 'small' | 'large' | 'code',
  runningTasks: RunningTask[],
): number {
  return runningTasks.filter(t => t.model_slot === slotKey).length;
}

/** Sum concurrent_workers across all tasks for a given slot. */
function concurrentWorkersForSlot(
  slotKey: 'embedding' | 'small' | 'large' | 'code',
  runningTasks: RunningTask[],
): number {
  return runningTasks
    .filter(t => t.model_slot === slotKey)
    .reduce((sum, t) => sum + (t.concurrent_workers || 1), 0);
}

/** Total concurrent workers across all slots. */
function totalConcurrentWorkers(runningTasks: RunningTask[]): number {
  return runningTasks.reduce((sum, t) => sum + (t.concurrent_workers || 1), 0);
}

/**
 * Collapsed sidebar view: vertical stack of colored dots per model slot
 * with running-count badges.
 */
function CollapsedView({
  slotsStatus,
  runningTasks,
  onOpenDetails,
}: {
  slotsStatus: LLMSlotsStatus | null;
  runningTasks: RunningTask[];
  onOpenDetails?: () => void;
}) {
  const slots = getSlots(slotsStatus);
  const totalRunning = totalConcurrentWorkers(runningTasks);

  return (
    <div className="flex flex-col items-center gap-1.5 py-3 px-2">
      <button
        onClick={onOpenDetails}
        className="flex flex-col items-center gap-1.5 group cursor-pointer"
        title="AI Gateway — click for details"
      >
        <Cpu className={cn(
          "w-4 h-4 mb-0.5",
          totalRunning > 0 ? "text-blue-500" : "text-text-muted"
        )} />
        {slots.map(slot => {
          const running = runningCountForSlot(slot.modelSlotKey, runningTasks);
          const workers = concurrentWorkersForSlot(slot.modelSlotKey, runningTasks);
          const isRunning = running > 0;
          return (
            <div key={slot.key} className="relative" title={`${slot.label}${isRunning ? ` (${workers} concurrent call${workers !== 1 ? 's' : ''})` : ''}`}>
              <div className={cn(
                "w-2.5 h-2.5 rounded-full transition-colors",
                slotColor(slot.status, isRunning),
                isRunning && "animate-pulse"
              )} />
              {workers > 1 && (
                <span className="absolute -top-1 -right-2 text-[8px] font-bold text-blue-500 leading-none">
                  {workers}×
                </span>
              )}
            </div>
          );
        })}
      </button>
    </div>
  );
}

/**
 * Expanded sidebar view: collapsible section with model slots and running task details.
 */
function ExpandedView({
  slotsStatus,
  runningTasks,
  sectionOpen,
  onToggleSection,
  onOpenDetails,
}: {
  slotsStatus: LLMSlotsStatus | null;
  runningTasks: RunningTask[];
  sectionOpen: boolean;
  onToggleSection: () => void;
  onOpenDetails?: () => void;
}) {
  const slots = getSlots(slotsStatus);
  const totalRunning = totalConcurrentWorkers(runningTasks);

  return (
    <div className="px-3 py-2">
      {/* Header row */}
      <div className="flex items-center justify-between">
        <button
          onClick={onToggleSection}
          className="flex items-center gap-1.5 text-xs font-semibold text-text-muted hover:text-text transition-colors cursor-pointer"
        >
          {sectionOpen ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
          <span>AI Gateway</span>
          {totalRunning > 0 && (
            <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-blue-500/10 text-blue-500 animate-pulse">
              {totalRunning} active
            </span>
          )}
        </button>
        {onOpenDetails && (
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={onOpenDetails}
            className="text-text-muted hover:text-text w-5 h-5"
            title="Open AI Gateway details"
          >
            <Maximize2 className="w-3 h-3" />
          </Button>
        )}
      </div>

      {/* Collapsible body */}
      {sectionOpen && (
        <div className="mt-2 space-y-1.5">
          {slots.map(slot => {
            const slotRunning = runningTasks.filter(
              t => t.model_slot === slot.modelSlotKey
            );
            const isRunning = slotRunning.length > 0;
            const workers = concurrentWorkersForSlot(slot.modelSlotKey, runningTasks);
            const isConnected = slot.status?.status === 'connected' || slot.status?.status === 'local';
            const isConfigured = slot.status?.configured ?? false;

            return (
              <div key={slot.key} className="min-h-[36px]">
                <div className="flex items-center gap-2 h-[36px]">
                  {/* Status indicator */}
                  <div className={cn(
                    "shrink-0 w-5 h-5 rounded-full flex items-center justify-center",
                    isRunning ? "text-blue-500" :
                    isConnected ? "text-success" :
                    slot.status?.status === 'unreachable' ? "text-error" :
                    "text-text-muted/50"
                  )}>
                    {isRunning ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> :
                     isConnected ? <CheckCircle2 className="w-3.5 h-3.5" /> :
                     slot.status?.status === 'unreachable' ? <AlertCircle className="w-3.5 h-3.5" /> :
                     <HelpCircle className="w-3.5 h-3.5" />}
                  </div>

                  {/* Label + model name */}
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1.5">
                      <span className={cn(
                        "text-xs font-medium truncate",
                        isConnected || isRunning ? "text-text" : "text-text-muted"
                      )}>
                        {slot.label}
                      </span>
                      {isRunning && workers > 1 && (
                        <span className="inline-flex items-center px-1 py-0 rounded text-[10px] font-semibold bg-blue-500/15 text-blue-400">
                          {workers}×
                        </span>
                      )}
                    </div>
                    <div className="text-[10px] text-text-muted truncate h-[14px]">
                      {isConfigured && slot.status?.model ? slot.status.model : '\u00A0'}
                    </div>
                  </div>
                </div>

                {/* Running task details */}
                {slotRunning.map(rt => (
                  <div
                    key={`${rt.project_id}-${rt.task_id}`}
                    className="ml-7 mt-0.5 flex items-center gap-1.5 text-[10px] text-blue-400"
                  >
                    <Loader2 className="w-2.5 h-2.5 animate-spin shrink-0" />
                    <span className="truncate">
                      {TASK_LABELS[rt.task_id] ?? rt.task_id}
                    </span>
                    {(rt.concurrent_workers ?? 1) > 1 && (
                      <span className="inline-flex items-center px-1 rounded text-[9px] font-bold bg-blue-500/20 text-blue-300 shrink-0">
                        {rt.concurrent_workers}×
                      </span>
                    )}
                    <span className="text-text-muted/60 shrink-0">on</span>
                    <span className="text-blue-300 font-medium truncate">
                      {rt.project_name}
                    </span>
                  </div>
                ))}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export function SidebarAIGateway({
  slotsStatus,
  collapsed = false,
  onOpenDetails,
  className,
}: SidebarAIGatewayProps) {
  const storageKey = 'codrag_sidebar_ai_gateway_open';
  const [sectionOpen, setSectionOpen] = useState(() => {
    const saved = typeof window !== 'undefined' ? localStorage.getItem(storageKey) : null;
    return saved !== null ? saved === 'true' : true;
  });

  const handleToggle = useCallback(() => {
    setSectionOpen(prev => {
      const next = !prev;
      localStorage.setItem(storageKey, String(next));
      return next;
    });
  }, []);

  const runningTasks = slotsStatus?.running_tasks ?? [];

  return (
    <div className={cn(className)}>
      {collapsed ? (
        <CollapsedView
          slotsStatus={slotsStatus}
          runningTasks={runningTasks}
          onOpenDetails={onOpenDetails}
        />
      ) : (
        <ExpandedView
          slotsStatus={slotsStatus}
          runningTasks={runningTasks}
          sectionOpen={sectionOpen}
          onToggleSection={handleToggle}
          onOpenDetails={onOpenDetails}
        />
      )}
    </div>
  );
}
