import os

ams_path = "packages/ui/src/stories/llm/AIModelsSettings.stories.tsx"
with open(ams_path, 'r') as f:
    content = f.read()

# Replace any lingering string arrays in mock objects with ModelInfo objects
content = content.replace("['gpt-4.1-mini', 'gpt-4.1-nano', 'gpt-4.1']", "[{id:'gpt-4.1-mini', name:'gpt-4.1-mini'}, {id:'gpt-4.1-nano', name:'gpt-4.1-nano'}, {id:'gpt-4.1', name:'gpt-4.1'}]")
content = content.replace("['nomic-embed-text', 'qwen3:4b', 'qwen3:1.7b', 'gemma3:4b']", "[{id:'nomic-embed-text', name:'nomic-embed-text'}, {id:'qwen3:4b', name:'qwen3:4b'}, {id:'qwen3:1.7b', name:'qwen3:1.7b'}, {id:'gemma3:4b', name:'gemma3:4b'}]")
content = content.replace("['qwen3:8b', 'qwen3:14b', 'qwen3:30b', 'qwen3-coder:30b']", "[{id:'qwen3:8b', name:'qwen3:8b'}, {id:'qwen3:14b', name:'qwen3:14b'}, {id:'qwen3:30b', name:'qwen3:30b'}, {id:'qwen3-coder:30b', name:'qwen3-coder:30b'}]")

with open(ams_path, 'w') as f:
    f.write(content)
