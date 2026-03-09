import re

# Update types.ts
with open('packages/ui/src/types.ts', 'r') as f:
    content = f.read()

if 'export interface ModelInfo' not in content:
    content += """
export interface ModelInfo {
  id: string;
  name: string;
  context_length?: number;
}
"""
    with open('packages/ui/src/types.ts', 'w') as f:
        f.write(content)
