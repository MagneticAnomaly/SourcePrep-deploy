import os

path = "src/codrag/api/routers/llm.py"
with open(path, 'r') as f:
    content = f.read()

old_filter = """                        methods = m.get("supportedGenerationMethods", [])
                        if "generateContent" not in methods:
                            continue"""

new_filter = """                        methods = m.get("supportedGenerationMethods", [])
                        if "generateContent" not in methods:
                            continue
                        
                        # Filter out non-LLM models
                        lower_name = m["name"].lower()
                        if any(x in lower_name for x in ["embedding", "imagen", "veo", "audio", "vision", "aqa"]):
                            continue"""

content = content.replace(old_filter, new_filter)

with open(path, 'w') as f:
    f.write(content)
