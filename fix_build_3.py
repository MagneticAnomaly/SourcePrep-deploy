import os

ams_path = "packages/ui/src/components/llm/AIModelsSettings.tsx"
with open(ams_path, 'r') as f:
    content = f.read()

# Let's see the current modelInList definition
import re
match = re.search(r'const modelInList = .*?\n', content)
if match:
    old_def = match.group(0)
    new_def = "const modelInList = (model: string | undefined, list: import('../../types').ModelInfo[]) => model && list.some(m => m.id === model);\n"
    content = content.replace(old_def, new_def)
else:
    print("modelInList not found")

with open(ams_path, 'w') as f:
    f.write(content)
