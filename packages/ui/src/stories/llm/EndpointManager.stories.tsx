import type { Meta, StoryObj } from '@storybook/react';
import { useState } from 'react';
import { EndpointManager } from '../../components/llm/EndpointManager';
import type { SavedEndpoint, EndpointTestResult } from '../../types';

const meta: Meta<typeof EndpointManager> = {
  title: 'Dashboard/LLM/EndpointManager',
  component: EndpointManager,
  tags: ['autodocs'],
  parameters: {
    layout: 'padded',
  },
};

export default meta;
type Story = StoryObj<typeof EndpointManager>;

export const Empty: Story = {
  args: {
    endpoints: [],
    onAdd: () => {},
    onEdit: () => {},
    onDelete: () => {},
    onTest: async (): Promise<EndpointTestResult> => ({
      success: false,
      message: 'No endpoint to test',
    }),
  },
};

export const Interactive: Story = {
  render: () => {
    const [endpoints, setEndpoints] = useState<SavedEndpoint[]>([
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
    ]);

    const sleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

    return (
      <EndpointManager
        endpoints={endpoints}
        onAdd={(ep) =>
          setEndpoints((prev) => [
            ...prev,
            {
              id: `ep-${prev.length + 1}`,
              ...ep,
            },
          ])
        }
        onEdit={(ep) => setEndpoints((prev) => prev.map((p) => (p.id === ep.id ? ep : p)))}
        onDelete={(id) => setEndpoints((prev) => prev.filter((p) => p.id !== id))}
        onTest={async (ep) => {
          await sleep(350);
          if (ep.provider === 'ollama' && ep.url.includes('localhost')) {
            return { success: true, message: 'Connected. Models: nomic-embed-text, mistral' };
          }
          if (ep.provider === 'openai' && !ep.api_key) {
            return { success: false, message: 'Missing API key' };
          }
          return { success: true, message: 'Connected.' };
        }}
      />
    );
  },
};
