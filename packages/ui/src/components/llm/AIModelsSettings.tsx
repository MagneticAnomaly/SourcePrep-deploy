import { cn } from '../../lib/utils';
import { ModelCard } from './ModelCard';
import { EndpointManager } from './EndpointManager';
import { Select } from '../primitives/Select';
import { Button } from '../primitives/Button';
import { InfoTooltip } from '../primitives/InfoTooltip';
import type { 
  LLMConfig,
  SavedEndpoint,
  EndpointTestResult,
  ModelSource,
  BatchMode,
} from '../../types';
import { Cpu, Info, Download, CheckCircle, Shrink, Cloud } from 'lucide-react';

export interface AIModelsSettingsProps {
  config: LLMConfig;
  onConfigChange: (config: LLMConfig) => void;
  
  // Endpoint operations
  onAddEndpoint: (endpoint: Omit<SavedEndpoint, 'id'>) => void;
  onEditEndpoint: (endpoint: SavedEndpoint) => void;
  onDeleteEndpoint: (id: string) => void;
  onTestEndpoint: (endpoint: SavedEndpoint) => Promise<EndpointTestResult>;
  
  // Model operations
  onFetchModels: (endpointId: string) => Promise<string[]>;
  onTestModel: (slotType: 'embedding' | 'small' | 'large' | 'code') => Promise<EndpointTestResult>;
  onClearTestResult?: (slot: string) => void;
  
  // HuggingFace operations
  onHFDownload: (slotType: 'embedding' | 'lingua') => void;
  
  // UI state
  availableModels?: Record<string, string[]>; // endpointId -> models
  loadingModels?: Record<string, boolean>;
  testingSlot?: 'embedding' | 'small' | 'large' | 'code' | null;
  testResults?: Record<string, EndpointTestResult>;
  
  className?: string;
}

// Recommended models per slot.
// nomic-embed-text-v1.5 (built-in via ONNX) is the primary recommendation.
// nomic-embed-text is the fallback for Ollama users.
const RECOMMENDED_MODELS: Record<string, string[]> = {
  embedding: ['nomic-embed-text', 'nomic-embed-code'],
  small: ['qwen3:4b', 'qwen3:1.7b', 'gemma3:4b'],
  large: ['qwen3:8b', 'qwen3:14b', 'qwen3:30b', 'gemma3:12b'],
  code: ['qwen3-coder:30b', 'qwen2.5-coder:7b', 'qwen3:4b'],
};

/** Check if a model name matches an entry in the available list (handles ':latest' suffix) */
function modelInList(model: string, list: string[]): boolean {
  return list.some(
    (m) => m === model || m === `${model}:latest` || model === `${m}:latest`
      || m.replace(/:latest$/, '') === model.replace(/:latest$/, '')
  );
}

/** Find the first recommended model present in the available list */
function findRecommended(slot: string, list: string[]): string | undefined {
  const recs = RECOMMENDED_MODELS[slot] ?? [];
  for (const rec of recs) {
    const match = list.find(
      (m) => m === rec || m === `${rec}:latest` || m.replace(/:latest$/, '') === rec.replace(/:latest$/, '')
    );
    if (match) return match;
  }
  return undefined;
}

export function AIModelsSettings({
  config,
  onConfigChange,
  onAddEndpoint,
  onEditEndpoint,
  onDeleteEndpoint,
  onTestEndpoint,
  onFetchModels,
  onTestModel,
  onClearTestResult,
  onHFDownload,
  availableModels = {},
  loadingModels = {},
  testingSlot,
  testResults = {},
  className,
}: AIModelsSettingsProps) {
  
  const handleEmbeddingSourceChange = (source: ModelSource) => {
    onClearTestResult?.('embedding');
    onConfigChange({
      ...config,
      embedding: { ...config.embedding, source },
    });
  };
  
  const handleEmbeddingEndpointChange = async (endpointId: string) => {
    onClearTestResult?.('embedding');
    if (!endpointId || endpointId === '__disconnect__') {
      onConfigChange({
        ...config,
        embedding: { ...config.embedding, endpoint_id: undefined, model: undefined },
      });
      return;
    }
    onConfigChange({
      ...config,
      embedding: { ...config.embedding, endpoint_id: endpointId, model: undefined },
    });
    const models = await onFetchModels(endpointId);
    const suggested = findRecommended('embedding', models);
    if (suggested) {
      onConfigChange({
        ...config,
        embedding: { ...config.embedding, endpoint_id: endpointId, model: suggested },
      });
    }
  };
  
  const handleEmbeddingModelChange = (model: string) => {
    onClearTestResult?.('embedding');
    onConfigChange({
      ...config,
      embedding: { ...config.embedding, model },
    });
  };
  
  const handleSmallModelEndpointChange = async (endpointId: string) => {
    onClearTestResult?.('small');
    if (!endpointId || endpointId === '__disconnect__') {
      onConfigChange({
        ...config,
        small_model: { ...config.small_model, endpoint_id: undefined, model: undefined, enabled: false },
      });
      return;
    }
    onConfigChange({
      ...config,
      small_model: { ...config.small_model, endpoint_id: endpointId, model: undefined, enabled: true },
    });
    // Fetch models for the dropdown but don't auto-select — user must choose
    void onFetchModels(endpointId);
  };
  
  const handleSmallModelChange = (model: string) => {
    onClearTestResult?.('small');
    onConfigChange({
      ...config,
      small_model: { ...config.small_model, model, enabled: true },
    });
  };
  
  const handleLargeModelEndpointChange = async (endpointId: string) => {
    onClearTestResult?.('large');
    if (!endpointId || endpointId === '__disconnect__') {
      onConfigChange({
        ...config,
        large_model: { ...config.large_model, endpoint_id: undefined, model: undefined, enabled: false },
      });
      return;
    }
    onConfigChange({
      ...config,
      large_model: { ...config.large_model, endpoint_id: endpointId, model: undefined, enabled: true },
    });
    // Fetch models for the dropdown but don't auto-select — user must choose
    void onFetchModels(endpointId);
  };
  
  const handleLargeModelChange = (model: string) => {
    onClearTestResult?.('large');
    onConfigChange({
      ...config,
      large_model: { ...config.large_model, model, enabled: true },
    });
  };
  
  const handleCodeModelEndpointChange = async (endpointId: string) => {
    onClearTestResult?.('code');
    if (!endpointId || endpointId === '__disconnect__') {
      onConfigChange({
        ...config,
        code_model: { ...config.code_model, endpoint_id: undefined, model: undefined, enabled: false },
      });
      return;
    }
    onConfigChange({
      ...config,
      code_model: { ...config.code_model, endpoint_id: endpointId, model: undefined, enabled: true },
    });
    // Fetch models for the dropdown but don't auto-select — user must choose
    void onFetchModels(endpointId);
  };
  
  const handleCodeModelChange = (model: string) => {
    onClearTestResult?.('code');
    onConfigChange({
      ...config,
      code_model: { ...config.code_model, model, enabled: true },
    });
  };
  

  // Determine status for each slot
  const getEmbeddingStatus = () => {
    // A successful test result always means connected
    if (testResults['embedding']?.success) return 'connected';
    if (config.embedding.source === 'huggingface') {
      if (config.embedding.hf_download_progress !== undefined && config.embedding.hf_download_progress < 1) {
        return 'downloading';
      }
      return config.embedding.hf_downloaded ? 'connected' : 'not-configured';
    }
    if (!config.embedding.endpoint_id || !config.embedding.model) return 'not-configured';
    const epModels = availableModels[config.embedding.endpoint_id] || [];
    if (epModels.length === 0) return 'loading';
    return modelInList(config.embedding.model, epModels) ? 'connected' : 'disconnected';
  };
  
  const getSlotStatus = (slot: { enabled: boolean; endpoint_id?: string; model?: string }, slotKey: string) => {
    // A successful test result always means connected
    if (testResults[slotKey]?.success) return 'connected';
    if (!slot.endpoint_id || !slot.model) return 'not-configured';
    const epModels = availableModels[slot.endpoint_id] || [];
    if (epModels.length === 0) return 'loading';
    return modelInList(slot.model, epModels) ? 'connected' : 'disconnected';
  };
  

  return (
    <div className={cn('codrag-ai-models-settings space-y-8', className)}>
      {/* Header */}
      <div>
        <h2 className="text-xl font-semibold font-mono flex items-center gap-2 text-text">
          <Cpu className="w-6 h-6 text-primary" />
          AI Models
          <InfoTooltip 
            content="Learn how to choose and configure models." 
            href="https://docs.codrag.io/guides/models" 
          />
        </h2>
        <p className="text-sm text-text-muted mt-1">Configure LLMs for embedding, analysis, and compression</p>
      </div>

      {/* Model Cards Grid: Left (Embed, Compression, Cloud) + Right (Fast, Code, Thinking) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Embedding Model (Top Left) */}
        <ModelCard
          title="Embedding Model"
          description="Vector encoding for semantic search"
          icon={
            <svg className="w-5 h-5 text-info" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485M7 17h.01" />
            </svg>
          }
          info="Recommended: Built-in ONNX (nomic-embed-text-v1.5) — works offline, no Ollama needed. Alternatively, use nomic-embed-text via Ollama or an OpenAI-compatible cloud provider."
          source={config.embedding.source}
          endpoint={config.embedding.endpoint_id}
          model={config.embedding.model}
          endpoints={config.saved_endpoints}
          onEndpointChange={handleEmbeddingEndpointChange}
          availableModels={availableModels[config.embedding.endpoint_id || ''] || []}
          onModelChange={handleEmbeddingModelChange}
          onRefreshModels={() => config.embedding.endpoint_id && onFetchModels(config.embedding.endpoint_id)}
          loadingModels={loadingModels[config.embedding.endpoint_id || '']}
          hfEnabled={true}
          hfRepoId="nomic-ai/nomic-embed-text-v1.5"
          hfDownloaded={config.embedding.hf_downloaded}
          hfDownloadProgress={config.embedding.hf_download_progress}
          onHFDownload={() => onHFDownload('embedding')}
          onSourceChange={handleEmbeddingSourceChange}
          status={getEmbeddingStatus()}
          onTest={() => onTestModel('embedding')}
          testResult={testResults['embedding']}
          testingConnection={testingSlot === 'embedding'}
        />

        {/* Fast Model (Top Right) */}
        <div className="flex flex-col h-full">
           <ModelCard
            title="Single / Fast Model"
            description="Fast analysis & parsing"
            icon={
              <svg className="w-5 h-5 text-warning" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            }
            info="Use a single powerful model here (like Claude/GPT) to handle both Fast and Thinking tasks, or combine a smaller local model with a larger one below."
            infoLink="https://docs.codrag.io/guides/models"
            endpoint={config.small_model.endpoint_id}
            model={config.small_model.model}
            endpoints={config.saved_endpoints}
            onEndpointChange={handleSmallModelEndpointChange}
            availableModels={availableModels[config.small_model.endpoint_id || ''] || []}
            onModelChange={handleSmallModelChange}
            onRefreshModels={() => config.small_model.endpoint_id && onFetchModels(config.small_model.endpoint_id)}
            loadingModels={loadingModels[config.small_model.endpoint_id || '']}
            status={getSlotStatus(config.small_model, 'small')}
            onTest={() => onTestModel('small')}
            testResult={testResults['small']}
            testingConnection={testingSlot === 'small'}
            className="flex-grow"
          />
        </div>

        {/* Context Compression — identical structure to ModelCard */}
        <div className={cn(
          'codrag-card rounded-lg border bg-surface p-6 transition-colors flex flex-col h-full',
          config.compression?.enabled && config.compression?.lingua_downloaded
            ? 'border-success/50 shadow-[0_0_15px_rgba(var(--success),0.1)]'
            : 'border-border',
        )}>
          {/* Header */}
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-surface-raised text-primary">
                <Shrink className="w-5 h-5" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-lg font-semibold font-mono text-text">Context Compression</h3>
                  <InfoTooltip
                    content="LLMLingua-2 prunes docs/markdown tokens; LOD extracts code at configurable detail levels. Download the model to enable compression."
                    href="https://docs.codrag.io/guides/models"
                  />
                </div>
                <p className="text-sm text-text-muted">LLMLingua-2 (docs) + LOD (code)</p>
              </div>
            </div>
            <span className={cn(
              "text-xs px-2 py-1 rounded-full font-medium border flex items-center gap-1.5",
              config.compression?.enabled && config.compression?.lingua_downloaded
                ? "bg-success-muted text-success border-success/20"
                : config.compression?.enabled
                  ? "bg-surface-raised text-text-muted border-border"
                  : "bg-surface-raised text-text-muted border-border"
            )}>
              {config.compression?.enabled && config.compression?.lingua_downloaded
                ? 'Connected'
                : config.compression?.enabled
                  ? 'Not Configured'
                  : 'Disabled'}
            </span>
          </div>

          <div className="flex-grow space-y-6">
            {/* Source Toggle — identical to ModelCard toggle */}
            <div className="p-1 bg-surface-raised rounded-lg flex gap-1 border border-border">
              <button
                onClick={() => onConfigChange({
                  ...config,
                  compression: { ...config.compression, enabled: false },
                })}
                className={cn(
                  'flex-1 px-3 py-2 text-xs rounded-md transition-all font-medium flex items-center justify-center gap-2',
                  !(config.compression?.enabled ?? false)
                    ? 'bg-surface text-text shadow-sm'
                    : 'text-text-muted hover:text-text hover:bg-surface/50'
                )}
              >
                Compression Disabled
              </button>
              <button
                onClick={() => onConfigChange({
                  ...config,
                  compression: { ...config.compression, enabled: true },
                })}
                className={cn(
                  'flex-1 px-3 py-2 text-xs rounded-md transition-all font-medium flex items-center justify-center gap-2',
                  config.compression?.enabled ?? false
                    ? 'bg-surface text-text shadow-sm'
                    : 'text-text-muted hover:text-text hover:bg-surface/50'
                )}
              >
                <Cloud className="w-3 h-3" />
                Download from HF
              </button>
            </div>

            {/* HuggingFace Download — identical to ModelCard HF mode */}
            {config.compression?.enabled && (
              <div className="space-y-4">
                <div className="p-4 bg-surface-raised rounded-lg border border-border">
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-xs font-medium text-text-muted">Model Repository</span>
                    <code className="text-xs text-primary bg-primary-muted/20 px-1.5 py-0.5 rounded">microsoft/llmlingua-2-bert-base</code>
                  </div>

                  {config.compression?.lingua_downloaded ? (
                    <div className="flex items-center gap-2 text-sm text-success font-medium bg-success-muted/10 p-3 rounded border border-success-muted/20">
                      <CheckCircle className="w-4 h-4" />
                      Downloaded & Ready
                    </div>
                  ) : config.compression?.lingua_download_progress != null && config.compression.lingua_download_progress > 0 ? (
                    <div className="space-y-2">
                      <div className="flex items-center justify-between text-xs text-text-muted">
                        <span>Downloading model files...</span>
                        <span>{Math.round(config.compression.lingua_download_progress * 100)}%</span>
                      </div>
                      <div className="h-2 bg-border rounded-full overflow-hidden">
                        <div
                          className="h-full bg-info transition-all duration-300"
                          style={{ width: `${config.compression.lingua_download_progress * 100}%` }}
                        />
                      </div>
                    </div>
                  ) : (
                    <Button
                      onClick={() => onHFDownload('lingua')}
                      className="w-full"
                      icon={Download}
                    >
                      Download Model
                    </Button>
                  )}
                </div>

                {/* Mode and Level selectors — side by side */}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-text-muted mb-1.5">Mode</label>
                    <Select
                      value={config.compression?.mode ?? 'auto'}
                      onChange={(e) => onConfigChange({
                        ...config,
                        compression: { ...config.compression, mode: e.target.value as any },
                      })}
                      options={[
                        { value: 'auto', label: 'Auto (dual-channel)' },
                        { value: 'lingua', label: 'Lingua only (docs/markdown)' },
                        { value: 'none', label: 'LOD only (code)' },
                      ]}
                      className="w-full"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-text-muted mb-1.5">Level</label>
                    <Select
                      value={config.compression?.level ?? 'standard'}
                      onChange={(e) => onConfigChange({
                        ...config,
                        compression: { ...config.compression, level: e.target.value as any },
                      })}
                      options={[
                        { value: 'light', label: 'Light (keep 60%)' },
                        { value: 'standard', label: 'Standard (keep 40%)' },
                        { value: 'aggressive', label: 'Aggressive (keep 25%)' },
                      ]}
                      className="w-full"
                    />
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Code Model (new slot for inferred edges) */}
        <ModelCard
          title="Code Model"
          description="Code-aware edge discovery (Optional)"
          icon={
            <svg className="w-5 h-5 text-success" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
            </svg>
          }
          info="Optional code-specialized model for inferring cross-file relationships. Falls back to the Fast model if not configured. Best with code-tuned models like qwen2.5-coder or deepseek-coder."
          infoLink="https://docs.codrag.io/guides/models"
          endpoint={config.code_model?.endpoint_id}
          model={config.code_model?.model}
          endpoints={config.saved_endpoints}
          onEndpointChange={handleCodeModelEndpointChange}
          availableModels={availableModels[config.code_model?.endpoint_id || ''] || []}
          onModelChange={handleCodeModelChange}
          onRefreshModels={() => config.code_model?.endpoint_id && onFetchModels(config.code_model.endpoint_id)}
          loadingModels={loadingModels[config.code_model?.endpoint_id || '']}
          status={getSlotStatus(config.code_model ?? { enabled: false }, 'code')}
          onTest={() => onTestModel('code')}
          testResult={testResults['code']}
          testingConnection={testingSlot === 'code'}
        />

        {/* Cloud Batch Processing (Bottom Left) */}
        <div className="codrag-card rounded-lg border bg-surface border-border p-6 flex flex-col h-full">
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-surface-raised text-primary">
                <Cloud className="w-5 h-5" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-lg font-semibold font-mono text-text">Cloud Processing</h3>
                  <InfoTooltip
                    content="When using a cloud model (BYOK), CoDRAG batches multiple files per API call for speed and cost savings."
                    href="https://docs.codrag.io/guides/byok-batching"
                  />
                </div>
                <p className="text-sm text-text-muted">Batch size for cloud API calls</p>
              </div>
            </div>
          </div>

          <div className="flex-grow space-y-4">
            <div>
              <label className="block text-xs font-medium text-text-muted mb-1.5">Batch mode</label>
              <Select
                value={config.batch_mode ?? 'standard'}
                onChange={(e) =>
                  onConfigChange({
                    ...config,
                    batch_mode: e.target.value as BatchMode,
                  })
                }
                options={[
                  { value: 'large', label: 'Large — 50–100 items/call' },
                  { value: 'standard', label: 'Standard — 25–50 items/call' },
                  { value: 'compact', label: 'Compact — 10–20 items/call' },
                  { value: 'off', label: 'Off — one item per call' },
                ]}
                className="w-full"
              />
            </div>
            <div className="text-xs text-text-muted space-y-1.5">
              <p className="font-medium text-text">Recommended models</p>
              <ul className="list-disc pl-4 space-y-1">
                <li><strong>Budget:</strong> <code className="text-primary bg-primary-muted/20 px-1 rounded">gpt-4.1-nano</code> — $0.10/$0.40 per 1M tokens (use <em>Standard</em>)</li>
                <li><strong>Best value:</strong> <code className="text-primary bg-primary-muted/20 px-1 rounded">gpt-4.1-mini</code> — $0.40/$1.60, 1M context (use <em>Standard</em>)</li>
                <li><strong>Cheapest:</strong> <code className="text-primary bg-primary-muted/20 px-1 rounded">gemini-2.5-flash</code> — $0.15/$0.60 (use <em>Compact</em>)</li>
                <li><strong>Premium:</strong> <code className="text-primary bg-primary-muted/20 px-1 rounded">claude-sonnet-4.5</code> — $3/$15, 64K output (use <em>Large</em>)</li>
              </ul>
            </div>
          </div>
        </div>

        {/* Thinking Model (Bottom Right) */}
        <ModelCard
          title="Thinking Model"
          description="Complex reasoning & summaries (Optional)"
          disabled={!config.small_model.model}
          icon={
            <svg className="w-5 h-5 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
          }
          endpoint={config.large_model.endpoint_id}
          model={config.large_model.model}
          endpoints={config.saved_endpoints}
          onEndpointChange={handleLargeModelEndpointChange}
          availableModels={availableModels[config.large_model.endpoint_id || ''] || []}
          onModelChange={handleLargeModelChange}
          onRefreshModels={() => config.large_model.endpoint_id && onFetchModels(config.large_model.endpoint_id)}
          loadingModels={loadingModels[config.large_model.endpoint_id || '']}
          status={getSlotStatus(config.large_model, 'large')}
          onTest={() => onTestModel('large')}
          testResult={testResults['large']}
          testingConnection={testingSlot === 'large'}
        />
      </div>

      {/* Endpoint Manager */}
      <EndpointManager
        endpoints={config.saved_endpoints}
        onAdd={onAddEndpoint}
        onEdit={onEditEndpoint}
        onDelete={onDeleteEndpoint}
        onTest={onTestEndpoint}
      />

      {/* Info Card */}
      <div className="rounded-lg bg-surface-raised border border-border p-4 flex gap-3">
        <Info className="w-5 h-5 text-info shrink-0 mt-0.5" />
        <div>
          <div className="flex items-center justify-between mb-2">
            <h4 className="text-sm font-semibold font-mono text-text">Model Recommendations (Ollama)</h4>
            <a href="https://docs.codrag.io/guides/model-advisor" target="_blank" rel="noreferrer" className="text-xs text-primary hover:underline">Setup Advisor →</a>
          </div>
          <ul className="text-xs text-text-muted space-y-1.5 list-disc pl-4">
            <li><strong>Embedding:</strong> nomic-embed-text-v1.5 (Built-in ONNX — no Ollama needed)</li>
            <li>
              <strong>Fast:</strong> <a href="https://ollama.com/library/qwen3" target="_blank" rel="noreferrer" className="text-primary hover:underline">qwen3:4b</a> (2.5GB) — rivals 72B models at this size. Alt: qwen3:1.7b for low VRAM
            </li>
            <li>
              <strong>Thinking:</strong> <a href="https://ollama.com/library/qwen3" target="_blank" rel="noreferrer" className="text-primary hover:underline">qwen3:8b</a> (5.2GB) — strong reasoning. Alt: qwen3:14b (9.3GB) or qwen3:30b MoE (19GB) for better quality
            </li>
            <li><strong>Code:</strong> <a href="https://ollama.com/library/qwen3-coder" target="_blank" rel="noreferrer" className="text-primary hover:underline">qwen3-coder:30b</a> MoE (19GB, 3.3B active) — best code model. Alt: qwen2.5-coder:7b (optional — falls back to Fast model)</li>
            <li><strong>Compression:</strong> LLMLingua-2 prunes docs/markdown tokens; LOD extracts code at configurable detail levels</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
