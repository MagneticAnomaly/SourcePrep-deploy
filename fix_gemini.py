import os

path = "src/codrag/api/routers/llm.py"
with open(path, 'r') as f:
    content = f.read()

# Only keep models that support generateContent
old_google_loop = """                for m in data.get("models", []):
                    if isinstance(m, dict) and "name" in m:"""
new_google_loop = """                for m in data.get("models", []):
                    if isinstance(m, dict) and "name" in m:
                        methods = m.get("supportedGenerationMethods", [])
                        if "generateContent" not in methods:
                            continue"""

content = content.replace(old_google_loop, new_google_loop)

with open(path, 'w') as f:
    f.write(content)
