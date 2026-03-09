import { cn } from '../../lib/utils';
import { Select } from '../primitives/Select';
import { Button } from '../primitives/Button';
import { InfoTooltip } from '../primitives/InfoTooltip';
import { X, CheckCircle, AlertCircle, RefreshCw } from 'lucide-react';
import type { CodragTaskId, SavedEndpoint, EndpointTestResult } from '../../types';
import { ALL_TASK_IDS, TASK_LABELS, TASK_TAGS } from '../../types';

export interface LLMAssignmentBlockCardProps {
  id: string;
  endpointId: string;
  model: string;
  tasks: CodragTaskId[];
  enableReasoning?: boolean;
  alwaysOn?: boolean;
  concurrency?: number;

  /** All saved endpoints for the endpoint dropdown */
  endpoints: SavedEndpoint[];
  /** Models available on the currently selected endpoint */
  availableModels: string[];
  loadingModels?: boolean;
  /** Task IDs that are already assigned globally across all blocks */
  assignedTasks: CodragTaskId[];

  onEndpointChange: (blockId: string, endpointId: string) => void;
  onModelChange: (blockId: string, model: string) => void;
  onRefreshModels: (endpointId: string) => void;
  onAddTask: (blockId: string, taskId: CodragTaskId) => void;
  onRemoveTask: (blockId: string, taskId: CodragTaskId) => void;
  onEnableReasoningChange?: (blockId: string, enabled: boolean) => void;
  onAlwaysOnChange?: (blockId: string, alwaysOn: boolean) => void;
  onConcurrencyChange?: (blockId: string, concurrency: number) => void;
  onDelete: (blockId: string) => void;
  onTest?: (blockId: string) => void;

  testResult?: EndpointTestResult;
  testingConnection?: boolean;

  className?: string;
}

export function LLMAssignmentBlockCard({
  id,
  endpointId,
  model,
  tasks,
  enableReasoning = false,
  alwaysOn = false,
  concurrency = 1,
  endpoints,
  availableModels,
  loadingModels = false,
  assignedTasks,
  onEndpointChange,
  onModelChange,
  onRefreshModels,
  onAddTask,
  onRemoveTask,
  onEnableReasoningChange,
  onAlwaysOnChange,
  onConcurrencyChange,
  onDelete,
  onTest,
  testResult,
  testingConnection = false,
  className,
}: LLMAssignmentBlockCardProps) {
  const hasEndpoint = !!endpointId;
  const hasModel = !!model;
  const isConfigured = hasEndpoint && hasModel;

  return (
    <div
      className={cn(
        'codrag-card rounded-lg border bg-surface p-5 transition-colors',
        isConfigured
          ? 'border-success/50 shadow-[0_0_12px_rgba(var(--success),0.08)]'
          : 'border-border',
        className,
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h4 className="text-sm font-semibold font-mono text-text">LLM Assignment</h4>
        <button
          onClick={() => onDelete(id)}
          className="p-1 rounded text-text-muted hover:text-error hover:bg-error-muted/10 transition-colors"
          title="Remove assignment block"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Tasks */}
      <div className="mb-5">
        <label className="block text-xs font-medium text-text-muted mb-1.5">Tasks</label>
        <div className="space-y-1.5">
          {tasks.map((taskId) => (
            <div
              key={taskId}
              className="flex items-center justify-between px-3 py-1.5 rounded-md bg-surface-raised border border-border text-xs"
            >
              <div className="flex items-center gap-2">
                <span className="text-text">{TASK_LABELS[taskId]}</span>
                {TASK_TAGS[taskId] && (
                  <span className="text-[10px] text-text-muted px-1.5 py-0.5 rounded bg-surface border border-border">
                    {TASK_TAGS[taskId]}
                  </span>
                )}
              </div>
              {tasks.length > 1 && (
                <button
                  onClick={() => onRemoveTask(id, taskId)}
                  className="p-0.5 rounded text-text-muted hover:text-error transition-colors"
                  title="Remove task from this block"
                >
                  <X className="w-3 h-3" />
                </button>
              )}
            </div>
          ))}

          {/* Add Task dropdown */}
          <Select
            value=""
            onChange={(e) => {
              if (e.target.value) {
                onAddTask(id, e.target.value as CodragTaskId);
              }
            }}
            placeholder="+ Add Task"
            options={ALL_TASK_IDS.map((t) => {
              const isAssigned = assignedTasks.includes(t);
              const tagStr = TASK_TAGS[t] ? ` [${TASK_TAGS[t]}]` : '';
              return {
                value: t,
                label: isAssigned ? `✓ ${TASK_LABELS[t]}${tagStr}` : `${TASK_LABELS[t]}${tagStr}`,
                disabled: isAssigned,
              };
            })}
            className="w-full text-xs"
          />
        </div>
      </div>

      {/* Endpoint + Model */}
      <div className="space-y-3 mb-4">
        <div>
          <label className="block text-xs font-medium text-text-muted mb-1">Endpoint</label>
          <Select
            value={endpointId}
            onChange={(e) => onEndpointChange(id, e.target.value)}
            placeholder="Select endpoint..."
            options={endpoints.map((ep) => ({
              value: ep.id,
              label: `${ep.name} (${ep.provider})`,
            }))}
            className="w-full"
          />
        </div>

        {hasEndpoint && (
          <div>
            <label className="block text-xs font-medium text-text-muted mb-1">Model</label>
            <div className="flex gap-2">
              <Select
                value={model}
                onChange={(e) => onModelChange(id, e.target.value)}
                placeholder="Select model..."
                options={availableModels.map((m) => ({ value: m, label: m }))}
                className="w-full flex-1"
              />
              <Button
                onClick={() => onRefreshModels(endpointId)}
                disabled={loadingModels}
                variant="outline"
                className="bg-surface-raised hover:bg-border border-border aspect-square p-0 w-[36px]"
                title="Refresh Models"
              >
                <RefreshCw className={cn('w-3.5 h-3.5', loadingModels && 'animate-spin')} />
              </Button>
            </div>
          </div>
        )}

        {/* Checkboxes: Reasoning & Always On */}
        {hasEndpoint && hasModel && (
          <div className="pt-2 flex flex-col gap-2">
            {onEnableReasoningChange && (
              <label className="flex items-center gap-2 cursor-pointer group w-max">
                <div className="relative flex items-center justify-center">
                  <input
                    type="checkbox"
                    checked={enableReasoning}
                    onChange={(e) => onEnableReasoningChange(id, e.target.checked)}
                    className="peer appearance-none w-4 h-4 border border-border rounded bg-surface checked:bg-primary checked:border-primary transition-colors cursor-pointer"
                  />
                  <CheckCircle className="absolute w-3 h-3 text-surface opacity-0 peer-checked:opacity-100 pointer-events-none transition-opacity" />
                </div>
                <span className="text-xs text-text-muted group-hover:text-text transition-colors select-none">
                  Enable Reasoning <span className="text-[10px] opacity-70">(parse {"<think>"} tags)</span>
                </span>
              </label>
            )}

            {onAlwaysOnChange !== undefined && (
              <label className="flex items-center gap-2 cursor-pointer group w-max">
                <div className="relative flex items-center justify-center">
                  <input
                    type="checkbox"
                    checked={alwaysOn}
                    onChange={(e) => onAlwaysOnChange(id, e.target.checked)}
                    className="peer appearance-none w-4 h-4 border border-border rounded bg-surface checked:bg-primary checked:border-primary transition-colors cursor-pointer"
                  />
                  <CheckCircle className="absolute w-3 h-3 text-surface opacity-0 peer-checked:opacity-100 pointer-events-none transition-opacity" />
                </div>
                <span className="text-xs text-text-muted group-hover:text-text transition-colors select-none">
                  Always available (Keep loaded)
                </span>
              </label>
            )}

            {/* Per-model Concurrency (advanced, local only) */}
            {onConcurrencyChange && (
              <div className="flex items-center gap-2">
                <label className="text-xs text-text-muted whitespace-nowrap">Concurrency</label>
                <Select
                  size="sm"
                  value={String(concurrency)}
                  onChange={(e) => onConcurrencyChange(id, parseInt(e.target.value))}
                  options={[
                    { value: '1', label: '1 (Standard)' },
                    { value: '2', label: '2 (High VRAM)' },
                  ]}
                  className="w-[140px]"
                />
                <InfoTooltip
                  content="How many simultaneous requests this model handles. 1 is recommended for all setups. Only set to 2 if your GPU has 8+ GB free VRAM after loading the model. Apple Silicon: always use 1. Embeddings are unaffected (run via ONNX)."
                />
              </div>
            )}
          </div>
        )}
      </div>

      {/* Test Connection */}
      {onTest && isConfigured && (
        <div className="pt-3 border-t border-border">
          {testResult && (
            <div
              className={cn(
                'mb-2 p-2 rounded-md text-xs border flex items-start gap-2',
                testResult.success
                  ? 'bg-success-muted/10 text-success border-success-muted/20'
                  : 'bg-error-muted/10 text-error border-error-muted/20',
              )}
            >
              {testResult.success ? (
                <CheckCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
              ) : (
                <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
              )}
              <span>{testResult.message}</span>
            </div>
          )}
          <Button
            size="sm"
            variant="secondary"
            onClick={() => onTest(id)}
            loading={testingConnection}
            className="w-full bg-surface-raised hover:bg-border border-border text-text text-xs"
          >
            Test Connection
          </Button>
        </div>
      )}
    </div>
  );
}
