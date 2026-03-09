import os
import re

def replace_in_file(path, old, new):
    if not os.path.exists(path):
        return
    with open(path, 'r') as f:
        content = f.read()
    if old in content:
        with open(path, 'w') as f:
            f.write(content.replace(old, new))

# 1. Update types.ts
types_path = "packages/ui/src/types.ts"
with open(types_path, 'r') as f:
    types_content = f.read()
if "export interface ModelInfo" not in types_content:
    with open(types_path, 'a') as f:
        f.write("\nexport interface ModelInfo {\n  id: string;\n  name: string;\n  context_length?: number;\n}\n")

# 2. client.ts
client_path = "packages/ui/src/api/client.ts"
with open(client_path, 'r') as f:
    client_content = f.read()

client_content = client_content.replace(
    "fetchLLMModels(provider: string, url: string, apiKey?: string): Promise<{ models: string[] }>;",
    "fetchLLMModels(provider: string, url: string, apiKey?: string): Promise<{ models: import('../types').ModelInfo[] }>;"
)
client_content = client_content.replace(
    "async fetchLLMModels(provider: string, url: string, apiKey?: string): Promise<{ models: string[] }> {",
    "async fetchLLMModels(provider: string, url: string, apiKey?: string): Promise<{ models: import('../types').ModelInfo[] }> {"
)
client_content = client_content.replace(
    "return this.requestEnvelope<{ models: string[] }>('/api/llm/proxy/models', {",
    "return this.requestEnvelope<{ models: import('../types').ModelInfo[] }>('/api/llm/proxy/models', {"
)
with open(client_path, 'w') as f:
    f.write(client_content)


# 3. ModelCard.tsx
mc_path = "packages/ui/src/components/llm/ModelCard.tsx"
with open(mc_path, 'r') as f:
    mc_content = f.read()

mc_content = mc_content.replace("availableModels?: string[];", "availableModels?: import('../../types').ModelInfo[];")
mc_content = mc_content.replace("options={availableModels.map((m) => ({ value: m, label: m }))}", "options={availableModels.map((m) => ({ value: m.id, label: m.context_length ? `${m.name} (${Math.round(m.context_length/1000)}k ctx)` : m.name }))}")

with open(mc_path, 'w') as f:
    f.write(mc_content)


# 4. LLMAssignmentBlockCard.tsx
abc_path = "packages/ui/src/components/llm/LLMAssignmentBlockCard.tsx"
with open(abc_path, 'r') as f:
    abc_content = f.read()

abc_content = abc_content.replace("availableModels: string[];", "availableModels: import('../../types').ModelInfo[];")
abc_content = abc_content.replace("options={availableModels.map((m) => ({ value: m, label: m }))}", "options={availableModels.map((m) => ({ value: m.id, label: m.context_length ? `${m.name} (${Math.round(m.context_length/1000)}k ctx)` : m.name }))}")

with open(abc_path, 'w') as f:
    f.write(abc_content)

# 5. AIModelsSettings.tsx
ams_path = "packages/ui/src/components/llm/AIModelsSettings.tsx"
with open(ams_path, 'r') as f:
    ams_content = f.read()

ams_content = ams_content.replace("onFetchModels: (endpointId: string) => Promise<string[]>;", "onFetchModels: (endpointId: string) => Promise<import('../../types').ModelInfo[]>;")
ams_content = ams_content.replace("availableModels?: Record<string, string[]>;", "availableModels?: Record<string, import('../../types').ModelInfo[]>;")

# Replace helper modelInList
ams_content = ams_content.replace(
    "const modelInList = (model: string | undefined, list: string[]) => model && list.includes(model);",
    "const modelInList = (model: string | undefined, list: import('../../types').ModelInfo[]) => model && list.some(m => m.id === model);"
)

# findRecommended (might need adjustment)
ams_content = ams_content.replace(
    "const findRecommended = (slotType: string, models: string[]) => {",
    "const findRecommended = (slotType: string, models: import('../../types').ModelInfo[]) => {\n    const modelIds = models.map(m => m.id);"
)
ams_content = ams_content.replace(
    "return models.find((m) => m === rec) || models.find((m) => m.startsWith(rec)) || models.find((m) => m.includes(rec));",
    "return modelIds.find((m) => m === rec) || modelIds.find((m) => m.startsWith(rec)) || modelIds.find((m) => m.includes(rec));"
)

with open(ams_path, 'w') as f:
    f.write(ams_content)

# 6. useLLMConfig.ts
ullm_path = "src/codrag/dashboard/src/hooks/useLLMConfig.ts"
with open(ullm_path, 'r') as f:
    ullm_content = f.read()

ullm_content = ullm_content.replace(
    "const [availableModels, setAvailableModels] = useState<Record<string, string[]>>({})",
    "const [availableModels, setAvailableModels] = useState<Record<string, import('@codrag/ui').ModelInfo[]>>({})"
)
ullm_content = ullm_content.replace(
    "import type { LLMConfig, SavedEndpoint, EndpointTestResult, LLMSlotsStatus } from '@codrag/ui'",
    "import type { LLMConfig, SavedEndpoint, EndpointTestResult, LLMSlotsStatus, ModelInfo } from '@codrag/ui'"
)

with open(ullm_path, 'w') as f:
    f.write(ullm_content)

print("Done")
