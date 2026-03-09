import os

files_to_update = [
    "packages/ui/src/components/llm/ModelCard.tsx",
    "packages/ui/src/components/llm/LLMAssignmentBlockCard.tsx"
]

old_map = """options={availableModels.map((m) => {
                        let label = m.name;
                        if (m.context_length) label += ` (${Math.round(m.context_length / 1000)}k ctx)`;
                        if (m.tags?.length) label += ` [${m.tags.join(', ')}]`;
                        return { value: m.id, label };
                      })}"""
# Standard HTML select options can't be richly formatted with flexbox to align things to the right. 
# They can only take text. To pseudo-align, we could pad with spaces, but it's not monospaced.
# Or we can just format it cleanly: "Gemini 2.5 Flash   |   1049k ctx   |   Free Tier Available"

new_map = """options={availableModels.map((m) => {
                        let parts = [m.name];
                        if (m.context_length) parts.push(`(${Math.round(m.context_length / 1000)}k ctx)`);
                        if (m.tags?.length) parts.push(`[${m.tags.join(', ')}]`);
                        return { value: m.id, label: parts.join('  •  ') };
                      })}"""

for fpath in files_to_update:
    if not os.path.exists(fpath): continue
    with open(fpath, 'r') as f:
        content = f.read()
    if old_map in content:
        content = content.replace(old_map, new_map)
        with open(fpath, 'w') as f:
            f.write(content)

