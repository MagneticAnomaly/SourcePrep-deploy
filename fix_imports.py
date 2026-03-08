import re

with open('packages/ui/src/components/llm/AIModelsSettings.tsx', 'r') as f:
    content = f.read()

# Add Server icon import
content = re.sub(
    r'(import \{ (.*?)Cpu)',
    r'import { \2Cpu, Server',
    content
)

with open('packages/ui/src/components/llm/AIModelsSettings.tsx', 'w') as f:
    f.write(content)
