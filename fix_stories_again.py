import os

ams_path = "packages/ui/src/stories/llm/AIModelsSettings.stories.tsx"
with open(ams_path, 'r') as f:
    content = f.read()

# Fix the dummy models definitions in the story
content = content.replace("Record<string, string[]>", "Record<string, import('../../types').ModelInfo[]>")

models_by_ep_old = """
  const modelsByEndpoint: Record<string, string[]> = {
    'local-ollama': ['nomic-embed-text', 'qwen3:4b', 'qwen3:1.7b', 'gemma3:4b'],
    'gpu-ollama': ['qwen3:8b', 'qwen3:14b', 'qwen3:30b', 'qwen3-coder:30b'],
    openai: ['gpt-4.1-mini', 'gpt-4.1-nano', 'gpt-4.1'],
  };
"""
models_by_ep_new = """
  const modelsByEndpoint: Record<string, import('../../types').ModelInfo[]> = {
    'local-ollama': [{id:'nomic-embed-text', name:'nomic-embed-text'}, {id:'qwen3:4b', name:'qwen3:4b'}, {id:'qwen3:1.7b', name:'qwen3:1.7b'}, {id:'gemma3:4b', name:'gemma3:4b'}],
    'gpu-ollama': [{id:'qwen3:8b', name:'qwen3:8b'}, {id:'qwen3:14b', name:'qwen3:14b'}, {id:'qwen3:30b', name:'qwen3:30b'}, {id:'qwen3-coder:30b', name:'qwen3-coder:30b'}],
    openai: [{id:'gpt-4.1-mini', name:'gpt-4.1-mini'}, {id:'gpt-4.1-nano', name:'gpt-4.1-nano'}, {id:'gpt-4.1', name:'gpt-4.1'}],
  };
"""
content = content.replace(models_by_ep_old, models_by_ep_new)

models_old2 = """
        const models: Record<string, string[]> = {
          'local-ollama': [{id:'nomic-embed-text', name:'nomic-embed-text'}, {id:'qwen3:4b', name:'qwen3:4b'}, {id:'qwen3:1.7b', name:'qwen3:1.7b'}, {id:'gemma3:4b', name:'gemma3:4b'}],
          'gpu-ollama': [{id:'qwen3:8b', name:'qwen3:8b'}, {id:'qwen3:14b', name:'qwen3:14b'}, {id:'qwen3:30b', name:'qwen3:30b'}, {id:'qwen3-coder:30b', name:'qwen3-coder:30b'}],
          openai: [{id:'gpt-4.1-mini', name:'gpt-4.1-mini'}, {id:'gpt-4.1-nano', name:'gpt-4.1-nano'}, {id:'gpt-4.1', name:'gpt-4.1'}],
        };
"""
models_new2 = """
        const models: Record<string, import('../../types').ModelInfo[]> = {
          'local-ollama': [{id:'nomic-embed-text', name:'nomic-embed-text'}, {id:'qwen3:4b', name:'qwen3:4b'}, {id:'qwen3:1.7b', name:'qwen3:1.7b'}, {id:'gemma3:4b', name:'gemma3:4b'}],
          'gpu-ollama': [{id:'qwen3:8b', name:'qwen3:8b'}, {id:'qwen3:14b', name:'qwen3:14b'}, {id:'qwen3:30b', name:'qwen3:30b'}, {id:'qwen3-coder:30b', name:'qwen3-coder:30b'}],
          openai: [{id:'gpt-4.1-mini', name:'gpt-4.1-mini'}, {id:'gpt-4.1-nano', name:'gpt-4.1-nano'}, {id:'gpt-4.1', name:'gpt-4.1'}],
        };
"""
content = content.replace(models_old2, models_new2)

with open(ams_path, 'w') as f:
    f.write(content)

