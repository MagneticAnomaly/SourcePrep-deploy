import os

ams_path = "packages/ui/src/components/llm/AIModelsSettings.tsx"
with open(ams_path, 'r') as f:
    content = f.read()

# Replace modelInList definition
old_model_in_list = "const modelInList = (model: string | undefined, list: string[]) => model && list.includes(model);"
new_model_in_list = "const modelInList = (model: string | undefined, list: import('../../types').ModelInfo[]) => model && list.some(m => m.id === model);"
if old_model_in_list in content:
    content = content.replace(old_model_in_list, new_model_in_list)

with open(ams_path, 'w') as f:
    f.write(content)

story_path = "packages/ui/src/stories/llm/AIModelsSettings.stories.tsx"
with open(story_path, 'r') as f:
    s_content = f.read()

old_test = """
        onTestEndpoint={async (endpoint) => {
          await new Promise((r) => setTimeout(r, 500));
          if (endpoint.url.includes('error')) return { success: false, message: 'Connection failed' };
          return { success: true, message: 'Connected to Ollama v0.1.20', models: models[endpoint.id] || [] };
        }}
"""
new_test = """
        onTestEndpoint={async (endpoint) => {
          await new Promise((r) => setTimeout(r, 500));
          if (endpoint.url.includes('error')) return { success: false, message: 'Connection failed' };
          return { success: true, message: 'Connected to Ollama v0.1.20' };
        }}
"""
s_content = s_content.replace(old_test, new_test)

with open(story_path, 'w') as f:
    f.write(s_content)

