import os
import re

# 1. Update types.ts
types_path = "packages/ui/src/types.ts"
with open(types_path, 'r') as f:
    content = f.read()

if "tags?: string[]" not in content:
    content = content.replace(
        "context_length?: number;",
        "context_length?: number;\n  tags?: string[];"
    )
    with open(types_path, 'w') as f:
        f.write(content)

# 2. Update ModelCard.tsx
mc_path = "packages/ui/src/components/llm/ModelCard.tsx"
with open(mc_path, 'r') as f:
    content = f.read()

old_options = "options={availableModels.map((m) => ({ value: m.id, label: m.context_length ? `${m.name} (${Math.round(m.context_length/1000)}k ctx)` : m.name }))}"
new_options = """options={availableModels.map((m) => {
                        let label = m.name;
                        if (m.context_length) label += ` (${Math.round(m.context_length / 1000)}k ctx)`;
                        if (m.tags?.length) label += ` [${m.tags.join(', ')}]`;
                        return { value: m.id, label };
                      })}"""
if old_options in content:
    content = content.replace(old_options, new_options)
with open(mc_path, 'w') as f:
    f.write(content)

# 3. Update LLMAssignmentBlockCard.tsx
abc_path = "packages/ui/src/components/llm/LLMAssignmentBlockCard.tsx"
with open(abc_path, 'r') as f:
    content = f.read()

if old_options in content:
    content = content.replace(old_options, new_options)
with open(abc_path, 'w') as f:
    f.write(content)

# 4. Update llm.py
llm_path = "src/codrag/api/routers/llm.py"
with open(llm_path, 'r') as f:
    content = f.read()

ollama_old = """
                        models.append({
                            "id": m["name"],
                            "name": m["name"],
                        })
"""
ollama_new = """
                        models.append({
                            "id": m["name"],
                            "name": m["name"],
                            "tags": ["Local", "Free"]
                        })
"""
content = content.replace(ollama_old, ollama_new)

openai_old = """
                        models.append({
                            "id": m["id"],
                            "name": m["id"],
                            "context_length": m.get("context_length") # LM studio sometimes provides this
                        })
"""
openai_new = """
                        is_local = req.provider == "lm-studio"
                        models.append({
                            "id": m["id"],
                            "name": m["id"],
                            "context_length": m.get("context_length"),
                            "tags": ["Local", "Free"] if is_local else ["Paid"]
                        })
"""
content = content.replace(openai_old, openai_new)

google_old = """
                        models.append({
                            "id": name,
                            "name": m.get("displayName", name),
                            "context_length": m.get("inputTokenLimit")
                        })
"""
google_new = """
                        tags = []
                        if "flash" in name.lower() or "pro" in name.lower():
                            tags.append("Free Tier")
                        else:
                            tags.append("Paid/Quota")
                        
                        models.append({
                            "id": name,
                            "name": m.get("displayName", name),
                            "context_length": m.get("inputTokenLimit"),
                            "tags": tags
                        })
"""
content = content.replace(google_old, google_new)

with open(llm_path, 'w') as f:
    f.write(content)

print("Done enhancing models")
