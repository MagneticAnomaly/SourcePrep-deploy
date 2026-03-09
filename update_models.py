import os
files = [
    "packages/ui/src/types.ts",
    "packages/ui/src/api/client.ts",
    "packages/ui/src/components/llm/AIModelsSettings.tsx",
    "packages/ui/src/components/llm/ModelCard.tsx",
    "packages/ui/src/components/llm/LLMAssignmentBlockCard.tsx",
    "src/codrag/dashboard/src/hooks/useLLMConfig.ts",
]

# We need to change `availableModels: string[]` to `availableModels: {id: string, label: string}[]`
# But let's check `types.ts` first
