import os

ams_path = "packages/ui/src/components/llm/AIModelsSettings.tsx"
with open(ams_path, 'r') as f:
    content = f.read()

content = content.replace(
    "models: availableModels[endpoint.id] || [],",
    "models: (availableModels[endpoint.id] || []).map(m => m.id),"
)

with open(ams_path, 'w') as f:
    f.write(content)

