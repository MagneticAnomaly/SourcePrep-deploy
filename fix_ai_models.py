import os

ams_path = "packages/ui/src/components/llm/AIModelsSettings.tsx"
with open(ams_path, 'r') as f:
    content = f.read()

# fix findRecommended call
content = content.replace("const suggested = findRecommended('embedding', models);", "const suggested = findRecommended('embedding', models);")
# Let's verify what models actually is
old_findRecommended = """
  const findRecommended = (slotType: string, models: import('../../types').ModelInfo[]) => {
    const modelIds = models.map(m => m.id);
    const recs = RECOMMENDED_MODELS[slotType] || [];
    for (const rec of recs) {
      const match = modelIds.find((m) => m === rec) || modelIds.find((m) => m.startsWith(rec)) || modelIds.find((m) => m.includes(rec));
      if (match) return match;
    }
    return null;
  };
"""

with open(ams_path, 'w') as f:
    f.write(content)
