import os

ams_path = "packages/ui/src/components/llm/AIModelsSettings.tsx"
with open(ams_path, 'r') as f:
    content = f.read()

old_model_in_list = """function modelInList(model: string, list: string[]): boolean {
  return list.some(
    (m) => m === model || m === `${model}:latest` || model === `${m}:latest`
      || m.replace(/:latest$/, '') === model.replace(/:latest$/, '')
  );
}"""
new_model_in_list = """function modelInList(model: string, list: import('../../types').ModelInfo[]): boolean {
  return list.some(
    (m) => m.id === model || m.id === `${model}:latest` || model === `${m.id}:latest`
      || m.id.replace(/:latest$/, '') === model.replace(/:latest$/, '')
  );
}"""

content = content.replace(old_model_in_list, new_model_in_list)

with open(ams_path, 'w') as f:
    f.write(content)
