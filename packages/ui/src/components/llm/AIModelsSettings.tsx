import { cn } from '../../lib/utils';
import { ModelCard } from './ModelCard';
import { EndpointManager } from './EndpointManager';
import { InfoTooltip } from '../primitives/InfoTooltip';
import type { 
  LLMConfig,
  SavedEndpoint,
  EndpointTestResult,
  ModelSource 
} from '../../types';
import { Cpu, Info } from 'lucide-react';

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
  onTestModel: (slotType: 'embedding' | 'small' | 'large' | 'clara') => Promise<EndpointTestResult>;
  onClearTestResult?: (slot: string) => void;
  
  // HuggingFace operations
  onHFDownload: (slotType: 'embedding' | 'clara') => void;
  
  // UI state
  availableModels?: Record<string, string[]>; // endpointId -> models
  loadingModels?: Record<string, boolean>;
  testingSlot?: 'embedding' | 'small' | 'large' | 'clara' | null;
  testResults?: Record<string, EndpointTestResult>;
  
  className?: string;
}

// Recommended models per slot
const RECOMMENDED_MODELS: Record<string, string[]> = {
  embedding: ['nomic-embed-text'],
  small: ['ministral-3:3b', 'qwen2.5:3b', 'phi3:mini'],
  large: ['ministral-3:8b', 'ministral-3:14b', 'mistral-nemo', 'qwen2.5:14b', 'deepseek-coder-v2'],
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
  
  const handleClaraSourceChange = (source: ModelSource) => {
    onClearTestResult?.('clara');
    onConfigChange({
      ...config,
      clara: { ...config.clara, source },
    });
  };

  const handleClaraEndpointChange = (endpointId: string) => {
    onClearTestResult?.('clara');
    if (!endpointId || endpointId === '__disconnect__') {
      onConfigChange({
        ...config,
        clara: { ...config.clara, endpoint_id: undefined, remote_url: undefined },
      });
      return;
    }
    const ep = config.saved_endpoints.find(e => e.id === endpointId);
    onConfigChange({
      ...config,
      clara: { 
        ...config.clara, 
        endpoint_id: endpointId,
        remote_url: ep?.url,
        enabled: true
      },
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
  
  const getClaraStatus = () => {
    // A successful test result always means connected
    if (testResults['clara']?.success) return 'connected';
    if (!config.clara.enabled) return 'not-configured';
    if (config.clara.source === 'huggingface') {
      if (config.clara.hf_download_progress !== undefined && config.clara.hf_download_progress < 1) {
        return 'downloading';
      }
      return config.clara.hf_downloaded ? 'connected' : 'not-configured';
    }
    // For endpoint source, check if we have a URL
    return config.clara.remote_url ? 'connected' : 'not-configured';
  };

  return (
    <div className={cn('codrag-ai-models-settings space-y-8', className)}>
      {/* Header */}
      <div>
        <h2 className="text-xl font-semibold flex items-center gap-2 text-text">
          <Cpu className="w-6 h-6 text-primary" />
          AI Models
          <InfoTooltip 
            content="Learn how to choose and configure models." 
            href="https://docs.codrag.io/guides/models" 
          />
        </h2>
        <p className="text-sm text-text-muted mt-1">Configure LLMs for embedding, analysis, and compression</p>
      </div>

      {/* Model Cards Grid */}
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

        {/* CLaRa Model (Bottom Left) */}
        <ModelCard
          title="CLaRa (Compression)"
          description="16x context compression (optional)"
          icon={
            <svg className="w-5 h-5 text-success" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
            </svg>
          }
          source={config.clara.source}
          endpoint={config.clara.endpoint_id}
          endpoints={config.saved_endpoints}
          onEndpointChange={handleClaraEndpointChange}
          hideModelSelector={true}
          hfEnabled={true}
          hfRepoId="apple/CLaRa-7B-Instruct"
          hfDownloaded={config.clara.hf_downloaded}
          hfDownloadProgress={config.clara.hf_download_progress}
          onHFDownload={() => onHFDownload('clara')}
          onSourceChange={handleClaraSourceChange}
          status={getClaraStatus()}
          onTest={() => onTestModel('clara')}
          testResult={testResults['clara']}
          testingConnection={testingSlot === 'clara'}
        />

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
          <h4 className="text-sm font-semibold mb-2 text-text">Model Recommendations</h4>
          <ul className="text-xs text-text-muted space-y-1.5 list-disc pl-4">
            <li><strong>Embedding:</strong> nomic-embed-text (via Ollama or HuggingFace download)</li>
            <li>
              <strong>Small:</strong> <a href="https://ollama.com/library/ministral-3" target="_blank" rel="noreferrer" className="text-primary hover:underline">ministral-3:3b</a>, qwen2.5:3b for fast parsing
            </li>
            <li>
              <strong>Large:</strong> <a href="https://ollama.com/library/ministral-3" target="_blank" rel="noreferrer" className="text-primary hover:underline">ministral-3:8b</a>, mistral-nemo, deepseek-coder-v2 for complex analysis
            </li>
            <li><strong>CLaRa:</strong> Optional - enables 16x context compression for large codebases</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
