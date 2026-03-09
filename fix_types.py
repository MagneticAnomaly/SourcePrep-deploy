import os

types_path = "packages/ui/src/types.ts"
with open(types_path, 'r') as f:
    content = f.read()

content = content.replace("models?: string[];", "models?: ModelInfo[];")
with open(types_path, 'w') as f:
    f.write(content)

