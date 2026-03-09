import os

path = "src/codrag/api/routers/llm.py"
with open(path, 'r') as f:
    content = f.read()

# Update the google tags logic
old_google = """                        tags = []
                        if "flash" in name.lower() or "pro" in name.lower():
                            tags.append("Free Tier")
                        else:
                            tags.append("Paid/Quota")"""

new_google = """                        tags = []
                        if "flash" in name.lower() or "pro" in name.lower() or "gemma" in name.lower():
                            tags.append("Free Tier Available")
                        else:
                            tags.append("Paid/Quota")"""

if old_google in content:
    content = content.replace(old_google, new_google)
    with open(path, 'w') as f:
        f.write(content)
