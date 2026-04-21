import type { Meta, StoryObj } from '@storybook/react';
import { useState } from 'react';
import { AIModelsSettings } from '../../components/llm/AIModelsSettings';
import type {
  EndpointTestResult,
  LLMConfig,
  ModelSlotType,
  SavedEndpoint,
  PrepTaskId,
} from '../../types';
import { applyPreset } from '../../lib/llm-presets';

const meta: Meta<typeof AIModelsSettings> = {
  title: 'Dashboard/Widgets/Settings/AIModelsSettings',
  component: AIModelsSettings,
  tags: ['autodocs'],
  parameters: {
    layout: 'padded',
  },
};

export default meta;
type Story = StoryObj<typeof AIModelsSettings>;

const sleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

const baseEndpoints: SavedEndpoint[] = [
  {
    id: 'local-ollama',
    name: 'Local Ollama',
    provider: 'ollama',
    url: 'http://localhost:11434',
  },
  {
    id: 'gpu-ollama',
    name: 'GPU Server',
    provider: 'ollama',
    url: 'http://192.168.1.100:11434',
  },
  {
    id: 'openai',
    name: 'OpenAI',
    provider: 'openai',
    url: 'https://api.openai.com/v1',
    api_key: '********',
  },
];

const baseConfig: LLMConfig = {
  embedding: {
    source: 'endpoint',
    endpoint_id: 'local-ollama',
    model: 'nomic-embed-text',
    hf_repo_id: 'nomic-ai/nomic-embed-text-v1.5',
    hf_downloaded: false,
    hf_download_progress: undefined,
  },
  small_model: {
    enabled: true,
    endpoint_id: 'local-ollama',
    model: 'qwen3:4b-instruct',
  },
  large_model: {
    enabled: true,
    endpoint_id: 'gpu-ollama',
    model: 'qwen3:8b',
  },
  code_model: {
    enabled: false,
  },
  saved_endpoints: baseEndpoints,
};

export const Default: Story = {
  render: () => {
    const [config, setConfig] = useState<LLMConfig>(baseConfig);
    const [availableModels, setAvailableModels] = useState<Record<string, string[]>>({
      'local-ollama': ['nomic-embed-text', 'qwen3:4b', 'qwen3:1.7b', 'gemma3:4b'],
      'gpu-ollama': ['qwen3:8b', 'qwen3:14b', 'qwen3:30b', 'qwen3-coder:30b'],
      openai: ['gpt-4.1-mini', 'gpt-4.1-nano', 'gpt-4.1'],
    });
    const [loadingModels, setLoadingModels] = useState<Record<string, boolean>>({});
    const [testingSlot, setTestingSlot] = useState<ModelSlotType | null>(null);
    const [testResults, setTestResults] = useState<Record<string, EndpointTestResult>>({});

    return (
      <AIModelsSettings
        config={config}
        onConfigChange={setConfig}
        availableModels={availableModels}
        loadingModels={loadingModels}
        testingSlot={testingSlot}
        testResults={testResults}
        onAddEndpoint={(ep) =>
          setConfig((prev) => ({
            ...prev,
            saved_endpoints: [
              ...prev.saved_endpoints,
              {
                id: `ep-${prev.saved_endpoints.length + 1}`,
                ...ep,
              },
            ],
          }))
        }
        onEditEndpoint={(endpoint) =>
          setConfig((prev) => ({
            ...prev,
            saved_endpoints: prev.saved_endpoints.map((e) => (e.id === endpoint.id ? endpoint : e)),
          }))
        }
        onDeleteEndpoint={(id) =>
          setConfig((prev) => ({
            ...prev,
            saved_endpoints: prev.saved_endpoints.filter((e) => e.id !== id),
          }))
        }
        onTestEndpoint={async (endpoint) => {
          await sleep(350);
          if (endpoint.provider === 'ollama') {
            return {
              success: true,
              message: 'Connected. Models loaded.',
              models: availableModels[endpoint.id] || [],
            };
          }
          if ((endpoint.provider === 'openai' || endpoint.provider === 'anthropic') && !endpoint.api_key) {
            return { success: false, message: 'Missing API key' };
          }
          return { success: true, message: 'Connected.' };
        }}
        onFetchModels={async (endpointId) => {
          setLoadingModels((prev) => ({ ...prev, [endpointId]: true }));
          await sleep(400);

          const modelsByEndpoint: Record<string, string[]> = {
            'local-ollama': ['nomic-embed-text', 'qwen3:4b', 'qwen3:1.7b', 'gemma3:4b'],
            'gpu-ollama': ['qwen3:8b', 'qwen3:14b', 'qwen3:30b', 'qwen3-coder:30b'],
            openai: ['gpt-4.1-mini', 'gpt-4.1-nano', 'gpt-4.1'],
          };

          setAvailableModels((prev) => ({
            ...prev,
            [endpointId]: modelsByEndpoint[endpointId] || [],
          }));
          setLoadingModels((prev) => ({ ...prev, [endpointId]: false }));
          return modelsByEndpoint[endpointId] || [];
        }}
        onTestModel={async (slotType) => {
          setTestingSlot(slotType);
          await sleep(450);
          const result: EndpointTestResult = { success: true, message: 'Test succeeded.' };
          setTestResults((prev) => ({ ...prev, [slotType]: result }));
          setTestingSlot(null);
          return result;
        }}
        onHFDownload={() => {
          setConfig((prev) => ({
            ...prev,
            embedding: {
              ...prev.embedding,
              source: 'huggingface',
              hf_downloaded: false,
              hf_download_progress: 0.35,
            },
          }));
        }}
      />
    );
  },
};

/**
 * Phase 44: Mapped mode with pre-populated assignment blocks.
 * Demonstrates the Local Standard preset applied from the baseConfig.
 */
export const MappedMode: Story = {
  render: () => {
    const initialBlocks = applyPreset('local-standard', baseConfig);
    const [config, setConfig] = useState<LLMConfig>({
      ...baseConfig,
      assignment_mode: 'mapped',
      assignment_blocks: initialBlocks,
    });
    const [availableModels, setAvailableModels] = useState<Record<string, string[]>>({
      'local-ollama': ['nomic-embed-text', 'qwen3:4b', 'qwen3:1.7b', 'gemma3:4b'],
      'gpu-ollama': ['qwen3:8b', 'qwen3:14b', 'qwen3:30b', 'qwen3-coder:30b'],
      openai: ['gpt-4.1-mini', 'gpt-4.1-nano', 'gpt-4.1'],
    });
    const [loadingModels, setLoadingModels] = useState<Record<string, boolean>>({});
    const [blockTestResults, setBlockTestResults] = useState<Record<string, EndpointTestResult>>({});
    const [blockTesting, setBlockTesting] = useState<string | null>(null);

    let blockCounter = 100;

    return (
      <AIModelsSettings
        config={config}
        onConfigChange={setConfig}
        availableModels={availableModels}
        loadingModels={loadingModels}
        onAddEndpoint={() => {}}
        onEditEndpoint={() => {}}
        onDeleteEndpoint={() => {}}
        onTestEndpoint={async () => ({ success: true, message: 'Connected.' })}
        onFetchModels={async (endpointId) => {
          setLoadingModels((prev) => ({ ...prev, [endpointId]: true }));
          await sleep(300);
          const models: Record<string, string[]> = {
            'local-ollama': ['nomic-embed-text', 'qwen3:4b', 'qwen3:1.7b', 'gemma3:4b'],
            'gpu-ollama': ['qwen3:8b', 'qwen3:14b', 'qwen3:30b', 'qwen3-coder:30b'],
            openai: ['gpt-4.1-mini', 'gpt-4.1-nano', 'gpt-4.1'],
          };
          setAvailableModels((prev) => ({ ...prev, [endpointId]: models[endpointId] || [] }));
          setLoadingModels((prev) => ({ ...prev, [endpointId]: false }));
          return models[endpointId] || [];
        }}
        onTestModel={async () => ({ success: true, message: 'Test succeeded.' })}
        onHFDownload={() => {}}
        // Phase 44: Mapped mode handlers
        onAssignmentBlockAdd={() => {
          setConfig((prev) => ({
            ...prev,
            assignment_blocks: [
              ...(prev.assignment_blocks || []),
              { id: `block-${++blockCounter}`, endpoint_id: '', model: '', tasks: [] as PrepTaskId[] },
            ],
          }));
        }}
        onAssignmentBlockDelete={(blockId) => {
          setConfig((prev) => ({
            ...prev,
            assignment_blocks: (prev.assignment_blocks || []).filter((b) => b.id !== blockId),
          }));
        }}
        onAssignmentBlockEndpointChange={(blockId, endpointId) => {
          setConfig((prev) => ({
            ...prev,
            assignment_blocks: (prev.assignment_blocks || []).map((b) =>
              b.id === blockId ? { ...b, endpoint_id: endpointId, model: '' } : b
            ),
          }));
        }}
        onAssignmentBlockModelChange={(blockId, model) => {
          setConfig((prev) => ({
            ...prev,
            assignment_blocks: (prev.assignment_blocks || []).map((b) =>
              b.id === blockId ? { ...b, model } : b
            ),
          }));
        }}
        onAssignmentBlockAddTask={(blockId, taskId) => {
          setConfig((prev) => ({
            ...prev,
            assignment_blocks: (prev.assignment_blocks || []).map((b) =>
              b.id === blockId ? { ...b, tasks: [...b.tasks, taskId] } : b
            ),
          }));
        }}
        onAssignmentBlockRemoveTask={(blockId, taskId) => {
          setConfig((prev) => ({
            ...prev,
            assignment_blocks: (prev.assignment_blocks || []).map((b) =>
              b.id === blockId ? { ...b, tasks: b.tasks.filter((t) => t !== taskId) } : b
            ),
          }));
        }}
        onAssignmentBlockTest={async (blockId) => {
          setBlockTesting(blockId);
          await sleep(400);
          const result: EndpointTestResult = { success: true, message: 'Model responded successfully' };
          setBlockTestResults((prev) => ({ ...prev, [blockId]: result }));
          setBlockTesting(null);
          return result;
        }}
        assignmentBlockTestResults={blockTestResults}
        assignmentBlockTesting={blockTesting}
      />
    );
  },
};
