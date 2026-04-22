import { cn } from '../../lib/utils';
import { CheckCircle2, AlertCircle, CircleOff, HelpCircle, Loader2, Cloud } from 'lucide-react';
import { InfoTooltip } from '../primitives/InfoTooltip';
import type { PrepTaskId, LLMAssignmentBlock, SavedEndpoint } from '../../types';
import { TASK_LABELS } from '../../types';
import { getTaskTokenDescription, getTaskTokenVolume } from '../../lib/token-estimates';

export interface LLMServiceStatus {
  name: string;
  url?: string; // This effectively holds the Provider Name (e.g., "Ollama", "OpenAI")
  model?: string; // The specific model name
  status: 'connected' | 'disconnected' | 'disabled' | 'not-configured';
  type: 'ollama' | 'openai' | 'other';
  running?: boolean;
}

export interface LLMStatusWidgetProps {
  services: LLMServiceStatus[];
  assignedBlocks?: LLMAssignmentBlock[];
  assignedEndpoints?: SavedEndpoint[];
  assignmentMode?: 'structured' | 'mapped';
  runningTaskId?: PrepTaskId | null;
  fileCount?: number;
  tokenUsageData?: Record<string, { prompt_tokens: number; completion_tokens: number; total_tokens: number }>;
  className?: string;
  bare?: boolean;
}

const CLOUD_PROVIDERS = new Set(['openai', 'anthropic', 'openai-compatible']);

function isCloudEndpoint(endpointId: string, endpoints: SavedEndpoint[]): boolean {
  const ep = endpoints.find(e => e.id === endpointId);
  return ep ? CLOUD_PROVIDERS.has(ep.provider) : false;
}

function ServiceCard({ service }: { service: LLMServiceStatus }) {
  const isConnected = service.status === 'connected';
  const isConfigured = service.status !== 'not-configured' && service.status !== 'disabled';
  const isRunning = service.running && isConnected;

  return (
    <div
      className={cn(
        "group flex items-center justify-between p-3 rounded-lg transition-colors border",
        isConnected
          ? "bg-surface-raised border-border hover:border-success/30"
          : "bg-surface/50 border-transparent hover:bg-surface-raised/50"
      )}
    >
      <div className="flex items-center gap-3 overflow-hidden">
        <div className={cn(
          "shrink-0 w-8 h-8 rounded-full flex items-center justify-center border",
          isRunning ? "bg-blue-500/10 border-blue-500/20 text-blue-500" :
          isConnected ? "bg-success-muted/10 border-success-muted/20 text-success" :
          service.status === 'disconnected' ? "bg-error-muted/10 border-error-muted/20 text-error" :
          "bg-surface-raised border-border text-text-muted"
        )}>
          {isRunning ? <Loader2 className="w-4 h-4 animate-spin" /> :
           isConnected ? <CheckCircle2 className="w-4 h-4" /> :
           service.status === 'disconnected' ? <AlertCircle className="w-4 h-4" /> :
           service.status === 'not-configured' ? <HelpCircle className="w-4 h-4" /> :
           <CircleOff className="w-4 h-4" />}
        </div>

        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className={cn(
              "text-sm font-medium truncate",
              isConnected ? "text-text" : "text-text-muted"
            )}>
              {service.name}
            </span>
            {isRunning ? (
              <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-blue-500/10 text-blue-500 animate-pulse">
                Running
              </span>
            ) : isConnected && (
              <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-success-muted/10 text-success">
                Active
              </span>
            )}
          </div>

          {isConfigured ? (
            <div className="text-xs text-text-muted truncate flex items-center gap-1.5 mt-0.5">
              <span className="font-medium text-text-subtle">{service.url}</span>
              {service.model && (
                <>
                  <span className="text-border">•</span>
                  <span className="opacity-75 truncate">{service.model}</span>
                </>
              )}
            </div>
          ) : (
            <div className="text-xs text-text-muted/50 italic mt-0.5">
              {service.status === 'not-configured' ? 'Not configured' : 'Disabled'}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function AssignedBlockCard({
  block,
  endpoints,
  runningTaskId,
  fileCount,
  tokenUsageData,
}: {
  block: LLMAssignmentBlock;
  endpoints: SavedEndpoint[];
  runningTaskId?: PrepTaskId | null;
  fileCount: number;
  tokenUsageData?: Record<string, { prompt_tokens: number; completion_tokens: number; total_tokens: number }>;
}) {
  const ep = endpoints.find(e => e.id === block.endpoint_id);
  const isConfigured = !!block.endpoint_id && !!block.model;
  const isCloud = block.endpoint_id ? isCloudEndpoint(block.endpoint_id, endpoints) : false;
  const blockHasRunningTask = block.tasks.some(t => t === runningTaskId);

  return (
    <div
      className={cn(
        "group p-3 rounded-lg transition-colors border",
        isConfigured
          ? "bg-surface-raised border-border hover:border-success/30"
          : "bg-surface/50 border-transparent hover:bg-surface-raised/50"
      )}
    >
      <div className="flex items-center gap-3 mb-2">
        <div className={cn(
          "shrink-0 w-8 h-8 rounded-full flex items-center justify-center border",
          blockHasRunningTask ? "bg-blue-500/10 border-blue-500/20 text-blue-500" :
          isConfigured ? "bg-success-muted/10 border-success-muted/20 text-success" :
          "bg-surface-raised border-border text-text-muted"
        )}>
          {blockHasRunningTask ? <Loader2 className="w-4 h-4 animate-spin" /> :
           isConfigured ? <CheckCircle2 className="w-4 h-4" /> :
           <HelpCircle className="w-4 h-4" />}
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className={cn(
              "text-sm font-medium truncate",
              isConfigured ? "text-text" : "text-text-muted"
            )}>
              {block.model || 'Not configured'}
            </span>
            {blockHasRunningTask ? (
              <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-blue-500/10 text-blue-500 animate-pulse">
                Running
              </span>
            ) : isConfigured && (
              <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-success-muted/10 text-success">
                Active
              </span>
            )}
            {isCloud && (
              <Cloud className="w-3.5 h-3.5 text-info opacity-70" />
            )}
          </div>
          {ep && (
            <div className="text-xs text-text-muted truncate mt-0.5">
              {ep.name} ({ep.provider})
            </div>
          )}
        </div>
      </div>

      {block.tasks.length > 0 && (
        <div className="ml-11 space-y-1">
          {block.tasks.map(taskId => {
            const isTaskRunning = taskId === runningTaskId;
            const actualUsage = tokenUsageData?.[taskId];
            const volume = getTaskTokenVolume(taskId);
            const tokenDesc = fileCount > 0 ? getTaskTokenDescription(taskId, fileCount) : null;

            return (
              <div key={taskId} className="flex items-center gap-2 text-xs">
                {isTaskRunning && (
                  <Loader2 className="w-3 h-3 text-blue-500 animate-spin shrink-0" />
                )}
                <span className={cn(
                  "truncate",
                  isTaskRunning ? "text-blue-500 font-medium" : "text-text-muted"
                )}>
                  {TASK_LABELS[taskId]}
                </span>
                {isCloud && (
                  <span
                    className={cn(
                      "text-[10px] px-1 py-0.5 rounded border shrink-0",
                      actualUsage
                        ? "text-success/80 bg-success/5 border-success/10 font-medium cursor-help"
                        : "text-info/70 bg-info/5 border-info/10"
                    )}
                    title={
                      actualUsage
                        ? `Physical tokens used:\nPrompt: ${actualUsage.prompt_tokens.toLocaleString()}\nCompletion: ${actualUsage.completion_tokens.toLocaleString()}\nTotal: ${actualUsage.total_tokens.toLocaleString()}`
                        : tokenDesc ?? `${volume} volume estimation`
                    }
                  >
                    {actualUsage
                      ? `${actualUsage.total_tokens >= 1000 ? (actualUsage.total_tokens / 1000).toFixed(1) + 'k' : actualUsage.total_tokens} tokens`
                      : volume}
                  </span>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
export function LLMStatusWidget({
  services,
  assignedBlocks,
  assignedEndpoints = [],
  assignmentMode = 'structured',
  runningTaskId,
  fileCount = 0,
  tokenUsageData,
  className,
  bare = false,
}: LLMStatusWidgetProps) {
  const useAssigned = assignmentMode === 'mapped' && assignedBlocks && assignedBlocks.length > 0;

  return (
    <div className={cn(
      !bare && 'border border-border bg-surface shadow-sm rounded-lg p-4',
      className
    )}>
      {!bare && (
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-text">AI Gateway</h3>
            <InfoTooltip 
              content="Configure your LLM providers." 
              href="https://docs.sourceprep.io/guides/models" 
            />
          </div>
        </div>
      )}
      
      <div className="space-y-2">
        {useAssigned ? (
          <>
            {/* Embedding & Compression from services (universal) */}
            {services.filter(s => s.name === 'Embedding' || s.name === 'Compression').map(s => (
              <ServiceCard key={s.name} service={s} />
            ))}
            {/* Assignment Blocks */}
            {assignedBlocks!.map(block => (
              <AssignedBlockCard
                key={block.id}
                block={block}
                endpoints={assignedEndpoints}
                runningTaskId={runningTaskId}
                fileCount={fileCount}
                tokenUsageData={tokenUsageData}
              />
            ))}
          </>
        ) : (
          services.map((service) => (
            <ServiceCard key={service.name} service={service} />
          ))
        )}
      </div>
    </div>
  );
}
