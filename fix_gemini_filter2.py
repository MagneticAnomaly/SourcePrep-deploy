import os

path = "src/codrag/api/routers/llm.py"
with open(path, 'r') as f:
    content = f.read()

old_filter = """                        # Filter out non-LLM models
                        lower_name = m["name"].lower()
                        if any(x in lower_name for x in ["embedding", "imagen", "veo", "audio", "vision", "aqa"]):
                            continue"""

new_filter = """                        # Filter out non-LLM models
                        lower_name = m["name"].lower()
                        exclude_terms = [
                            "embedding", "imagen", "veo", "audio", "vision", "aqa",
                            "tts", "-image", "image-generation", "computer-use"
                        ]
                        if any(x in lower_name for x in exclude_terms):
                            continue"""

content = content.replace(old_filter, new_filter)

with open(path, 'w') as f:
    f.write(content)
