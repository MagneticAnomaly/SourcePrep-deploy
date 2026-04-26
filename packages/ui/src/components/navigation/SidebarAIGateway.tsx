import { useState, useCallback, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
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
  Wrench,
} from 'lucide-react';
import { Button } from '../primitives/Button';
import { ConcurrencyResetPanel } from '../concurrency/ConcurrencyResetPanel';
import type { LLMSlotsStatus, RunningTask, LLMSlotStatus } from '../../types';
import { TASK_LABELS } from '../../types';

export interface SidebarAIGatewayProps {
  slotsStatus: LLMSlotsStatus | null;
  collapsed?: boolean;
  onOpenDetails?: () => void;
  className?: string;
  /** Phase 119 Task 16: when set, the AI Gateway header surfaces a small
   *  developer-mode wrench that opens the cloud-concurrency reset panel.
   *  The same affordance lives in Settings → AI Models → Pipeline Activity;
   *  the sidebar entry point makes the action one click away from the
   *  badge that triggered the user's investigation. */
  baseUrl?: string;
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

/** Check if any task for a given slot is running in swarm mode. */
function isSwarmForSlot(
  slotKey: 'embedding' | 'small' | 'large' | 'code',
  runningTasks: RunningTask[],
): boolean {
  return runningTasks.some(t => t.model_slot === slotKey && t.is_swarm);
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
          const swarming = isSwarmForSlot(slot.modelSlotKey, runningTasks);
          const isRunning = running > 0;
          return (
            <div key={slot.key} className="relative" title={`${slot.label}${isRunning ? ` (${workers}${swarming ? ' swarm' : ' concurrent'} call${workers !== 1 ? 's' : ''})` : ''}`}>
              <div className={cn(
                "w-2.5 h-2.5 rounded-full transition-colors",
                slotColor(slot.status, isRunning),
                isRunning && "animate-pulse"
              )} />
              {workers > 1 && (
                <span className="absolute -top-1 -right-2 text-[8px] font-bold text-blue-500 leading-none">
                  {workers}×{swarming ? 'S' : ''}
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
 * Phase 119 Task 16: small inline menu next to the AI Gateway header.
 * One action — "Reset cloud concurrency discovery" — surfaced under a
 * subtle wrench icon. Hidden unless `baseUrl` is provided AND at least
 * one `cloud:*` node is registered with the scheduler (queried lazily).
 */
function DevModeMenu({ baseUrl }: { baseUrl: string }) {
  const [open, setOpen] = useState(false);
  const [cloudNodeIds, setCloudNodeIds] = useState<string[] | null>(null);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const [anchor, setAnchor] = useState<{ left: number; top: number } | null>(null);

  // Recompute anchor coordinates when the popover opens. Using a portal
  // (rendered into document.body) sidesteps the sidebar's overflow clip
  // and any z-index stacking inside ProjectList; using fixed-pixel
  // coordinates from getBoundingClientRect avoids re-implementing
  // floating-ui-style positioning for a one-shot dev affordance.
  useEffect(() => {
    if (!open) return;
    const rect = triggerRef.current?.getBoundingClientRect();
    if (rect) {
      setAnchor({ left: rect.right + 8, top: rect.top });
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    const root = baseUrl.replace(/\/$/, '');
    (async () => {
      try {
        const res = await fetch(`${root}/compute/scheduler`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const body = await res.json();
        const nodes = body?.data?.nodes ?? body?.nodes ?? {};
        const ids = Object.keys(nodes).filter((nid) => nid.startsWith('cloud:'));
        if (!cancelled) setCloudNodeIds(ids);
      } catch {
        if (!cancelled) setCloudNodeIds([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [open, baseUrl]);

  const portalTarget = typeof document !== 'undefined' ? document.body : null;

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          setOpen((v) => !v);
        }}
        className={cn(
          // Phase 119 amendment: bumped visual weight (text-amber-400, w-6
          // h-6, w-3.5 h-3.5 icon) so the developer affordance is
          // discoverable from a quick scan of the AI Gateway header.
          // Previously the muted color blended into the sidebar and users
          // missed it entirely.
          'inline-flex items-center justify-center w-6 h-6 rounded transition-colors',
          'text-amber-400 hover:text-amber-300 hover:bg-surface-raised',
          open && 'text-amber-300 bg-surface-raised',
        )}
        title="Developer tools — reset cloud concurrency discovery"
        aria-label="Developer tools — reset cloud concurrency discovery"
        aria-expanded={open}
        data-testid="ai-gateway-devmode-toggle"
      >
        <Wrench className="w-3.5 h-3.5" />
      </button>
      {open && portalTarget && anchor &&
        createPortal(
          <>
            {/* Click-outside backdrop */}
            <div
              className="fixed inset-0 z-[9998]"
              onClick={() => setOpen(false)}
              aria-hidden
            />
            <div
              className="fixed z-[9999] w-72 rounded-md border border-border bg-surface shadow-xl p-3 space-y-2"
              style={{ left: anchor.left, top: anchor.top }}
              data-testid="ai-gateway-devmode-popover"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center gap-1.5 text-[11px] font-semibold text-text">
                <Wrench className="w-3 h-3 text-text-muted" />
                Developer mode
              </div>
              <ConcurrencyResetPanel
                cloudNodeIds={cloudNodeIds ?? []}
                baseUrl={baseUrl}
              />
              {cloudNodeIds === null && (
                <div className="text-[10px] text-text-muted">Loading nodes…</div>
              )}
            </div>
          </>,
          portalTarget,
        )}
    </>
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
  baseUrl,
}: {
  slotsStatus: LLMSlotsStatus | null;
  runningTasks: RunningTask[];
  sectionOpen: boolean;
  onToggleSection: () => void;
  onOpenDetails?: () => void;
  baseUrl?: string;
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
        <div className="flex items-center gap-0.5">
          {baseUrl && <DevModeMenu baseUrl={baseUrl} />}
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
                      <span className={cn(
                        "inline-flex items-center px-1 rounded text-[9px] font-bold shrink-0",
                        rt.is_swarm ? "bg-purple-500/20 text-purple-300" : "bg-blue-500/20 text-blue-300",
                      )}>
                        {rt.concurrent_workers}×{rt.is_swarm ? 'Swarm' : ''}
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
  baseUrl,
}: SidebarAIGatewayProps) {
  const storageKey = 'prep_sidebar_ai_gateway_open';
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
          baseUrl={baseUrl}
        />
      )}
    </div>
  );
}
