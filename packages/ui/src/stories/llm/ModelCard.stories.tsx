import type { Meta, StoryObj } from '@storybook/react';
import { ModelCard } from '../../components/llm/ModelCard';
import type { SavedEndpoint } from '../../types';

const meta: Meta<typeof ModelCard> = {
  title: 'Dashboard/LLM/ModelCard',
  component: ModelCard,
  tags: ['autodocs'],
  parameters: {
    layout: 'padded',
  },
};

export default meta;
type Story = StoryObj<typeof ModelCard>;

const endpoints: SavedEndpoint[] = [
  {
    id: 'local-ollama',
    name: 'Local Ollama',
    provider: 'ollama',
    url: 'http://localhost:11434',
  },
  {
    id: 'openai',
    name: 'OpenAI',
    provider: 'openai',
    url: 'https://api.openai.com/v1',
    api_key: '********',
  },
];

const defaultIcon = (
  <svg className="w-4 h-4 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={2}
      d="M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485M7 17h.01"
    />
  </svg>
);

export const NotConfigured: Story = {
  args: {
    title: 'Embedding Model',
    description: 'Vector encoding for semantic search',
    icon: defaultIcon,
    endpoints,
    status: 'not-configured',
  },
};

export const EndpointSelected: Story = {
  args: {
    title: 'Small Model',
    description: 'Fast analysis & parsing',
    icon: defaultIcon,
    endpoints,
    endpoint: 'local-ollama',
    availableModels: ['qwen3:4b-instruct', 'phi-3-mini', 'llama3.1'],
    status: 'connected',
    onTest: () => {},
  },
};

export const ConnectedWithModelAndTestResult: Story = {
  args: {
    title: 'Large Model',
    description: 'Complex reasoning & summaries',
    icon: defaultIcon,
    endpoints,
    endpoint: 'local-ollama',
    model: 'mistral',
    availableModels: ['mistral', 'qwen3:30b-instruct', 'deepseek-coder-v2'],
    status: 'connected',
    onTest: () => {},
    testResult: { success: true, message: 'Connected. 3 models available.' },
  },
};

export const TestingConnection: Story = {
  args: {
    title: 'Large Model',
    description: 'Complex reasoning & summaries',
    icon: defaultIcon,
    endpoints,
    endpoint: 'local-ollama',
    model: 'mistral',
    availableModels: ['mistral', 'qwen3:30b-instruct', 'deepseek-coder-v2'],
    status: 'connected',
    onTest: () => {},
    testingConnection: true,
  },
};

export const HFNotDownloaded: Story = {
  args: {
    title: 'Embedding Model',
    description: 'Vector encoding for semantic search',
    icon: defaultIcon,
    hfEnabled: true,
    source: 'huggingface',
    hfRepoId: 'nomic-ai/nomic-embed-text-v1.5',
    hfDownloaded: false,
    endpoints,
    status: 'not-configured',
    onSourceChange: () => {},
    onHFDownload: () => {},
  },
};

export const HFDownloading: Story = {
  args: {
    title: 'Embedding Model',
    description: 'Vector encoding for semantic search',
    icon: defaultIcon,
    hfEnabled: true,
    source: 'huggingface',
    hfRepoId: 'nomic-ai/nomic-embed-text-v1.5',
    hfDownloaded: false,
    hfDownloadProgress: 0.42,
    endpoints,
    status: 'downloading',
    onSourceChange: () => {},
    onHFDownload: () => {},
  },
};

export const HFDownloaded: Story = {
  args: {
    title: 'Embedding Model',
    description: 'Vector encoding for semantic search',
    icon: defaultIcon,
    hfEnabled: true,
    source: 'huggingface',
    hfRepoId: 'nomic-ai/nomic-embed-text-v1.5',
    hfDownloaded: true,
    endpoints,
    status: 'connected',
    onSourceChange: () => {},
  },
};
