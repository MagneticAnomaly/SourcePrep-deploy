import os

ams_path = "packages/ui/src/components/llm/AIModelsSettings.tsx"
with open(ams_path, 'r') as f:
    content = f.read()

content = content.replace(
    "const suggested = findRecommended('embedding', models);",
    "const suggested = findRecommended('embedding', models);"
)
# Re-apply modelInList fix
content = content.replace(
    "const modelInList = (model: string | undefined, list: import('../../types').ModelInfo[]) => model && list.some(m => m.id === model);",
    "const modelInList = (model: string | undefined, list: import('../../types').ModelInfo[]) => model && list.some(m => m.id === model);"
)

with open(ams_path, 'w') as f:
    f.write(content)

story1_path = "packages/ui/src/stories/llm/AIModelsSettings.stories.tsx"
with open(story1_path, 'r') as f:
    s1_content = f.read()

s1_content = s1_content.replace(
    "const [availableModels, setAvailableModels] = useState<Record<string, string[]>>({",
    "const [availableModels, setAvailableModels] = useState<Record<string, import('../../types').ModelInfo[]>>({"
)
s1_content = s1_content.replace(
    "models: ['llama3', 'mistral', 'qwen2']",
    "models: [{id: 'llama3', name: 'llama3'}, {id: 'mistral', name: 'mistral'}, {id: 'qwen2', name: 'qwen2'}]"
)
s1_content = s1_content.replace(
    "onFetchModels={async (endpointId) => {",
    "onFetchModels={async (endpointId): Promise<import('../../types').ModelInfo[]> => {"
)
with open(story1_path, 'w') as f:
    f.write(s1_content)

story2_path = "packages/ui/src/stories/llm/ModelCard.stories.tsx"
with open(story2_path, 'r') as f:
    s2_content = f.read()

s2_content = s2_content.replace(
    "availableModels: ['qwen3:4b-instruct', 'phi-3-mini', 'llama3.1'],",
    "availableModels: [{id: 'qwen3:4b-instruct', name: 'qwen3:4b-instruct'}, {id: 'phi-3-mini', name: 'phi-3-mini'}, {id: 'llama3.1', name: 'llama3.1'}],"
)
s2_content = s2_content.replace(
    "availableModels: ['mistral', 'qwen3:30b-instruct', 'deepseek-coder-v2'],",
    "availableModels: [{id: 'mistral', name: 'mistral'}, {id: 'qwen3:30b-instruct', name: 'qwen3:30b-instruct'}, {id: 'deepseek-coder-v2', name: 'deepseek-coder-v2'}],"
)
with open(story2_path, 'w') as f:
    f.write(s2_content)

