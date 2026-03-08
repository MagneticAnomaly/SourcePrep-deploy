import re

with open('packages/ui/src/types.ts', 'r') as f:
    content = f.read()

# Add ComputeNode interfaces right before SavedEndpoint
compute_node_str = """
export type ComputeHardwareProfile = 'apple_silicon' | 'nvidia' | 'amd' | 'intel' | 'cloud';

export interface ComputeNode {
  id: string;
  name: string;
  type: 'local' | 'remote' | 'cloud';
  hardware_profile?: ComputeHardwareProfile;
  max_concurrent: number;
  gpu_name?: string;
  gpu_vram_gb?: number;
  endpoint_ids: string[];
}
"""

content = re.sub(
    r'(export interface SavedEndpoint \{)',
    compute_node_str + r'\n\1',
    content,
    count=1
)

# Add compute_node_id to SavedEndpoint
content = re.sub(
    r'(  api_key\?: string;)',
    r'\1\n  compute_node_id?: string | null;',
    content,
    count=1
)

# Add compute_nodes to LLMConfig
content = re.sub(
    r'(  saved_endpoints: SavedEndpoint\[\];)',
    r'\1\n  compute_nodes?: ComputeNode[];',
    content,
    count=1
)

with open('packages/ui/src/types.ts', 'w') as f:
    f.write(content)
