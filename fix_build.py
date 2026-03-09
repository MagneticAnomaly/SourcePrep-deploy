import os

ams_path = "packages/ui/src/components/llm/AIModelsSettings.tsx"
with open(ams_path, 'r') as f:
    content = f.read()

content = content.replace(
    "const suggested = findRecommended('embedding', models);",
    "const suggested = findRecommended('embedding', models.map(m => m.id));"
)
content = content.replace(
    "const modelInList = (model: string | undefined, list: import('../../types').ModelInfo[]) => model && list.some(m => m.id === model);",
    "const modelInList = (model: string | undefined, list: import('../../types').ModelInfo[]) => model && list.some(m => m.id === model);"
)

with open(ams_path, 'w') as f:
    f.write(content)


ams_story_path = "packages/ui/src/stories/llm/AIModelsSettings.stories.tsx"
with open(ams_story_path, 'r') as f:
    content = f.read()

old_test = """
        onTestEndpoint={async (endpoint) => {
          await new Promise((r) => setTimeout(r, 500));
          if (endpoint.url.includes('error')) return { success: false, message: 'Connection failed' };
          return { success: true, message: 'Connected to Ollama v0.1.20', models: modelsByEndpoint[endpoint.id] || [] };
        }}
"""
new_test = """
        onTestEndpoint={async (endpoint) => {
          await new Promise((r) => setTimeout(r, 500));
          if (endpoint.url.includes('error')) return { success: false, message: 'Connection failed' };
          return { success: true, message: 'Connected to Ollama v0.1.20' };
        }}
"""
content = content.replace(old_test, new_test)

with open(ams_story_path, 'w') as f:
    f.write(content)
