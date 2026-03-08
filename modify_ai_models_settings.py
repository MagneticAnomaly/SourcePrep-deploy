import re

with open('packages/ui/src/components/llm/AIModelsSettings.tsx', 'r') as f:
    content = f.read()

# Add ComputeNode to imports
content = re.sub(
    r'  SavedEndpoint,',
    r'  SavedEndpoint,\n  ComputeNode,',
    content
)

# Add Multi-GPU tab state
state_logic = """
  // Compute Profile Tabs
  const [computeTab, setComputeTab] = useState<'single' | 'multi'>('single');
"""
content = re.sub(
    r'  const \[draftMode, setDraftMode\] = useState<AssignmentMode>',
    state_logic + r'\n  const [draftMode, setDraftMode] = useState<AssignmentMode>',
    content
)

# Replace the existing "Compute Profile" section
old_compute_profile = r'      \{\/\* Compute Profile \*\/\}.*?      \{/\* Cloud Processing \*\/\}'

new_compute_profile = """      {/* Compute Profile (Phase 45) */}
      <div className="rounded-lg border border-border bg-surface p-4 space-y-4">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-semibold text-text flex items-center gap-2">
            <Cpu className="w-4 h-4 text-primary" />
            Compute Profile
          </h3>
          <div className="flex bg-surface-raised rounded-md p-1 border border-border">
            <button
              onClick={() => setComputeTab('single')}
              className={cn(
                "px-3 py-1 text-xs font-medium rounded-sm transition-colors",
                computeTab === 'single' ? "bg-surface shadow-sm text-text" : "text-text-muted hover:text-text"
              )}
            >
              Single Compute
            </button>
            <button
              onClick={() => setComputeTab('multi')}
              className={cn(
                "px-3 py-1 text-xs font-medium rounded-sm transition-colors flex items-center gap-1",
                computeTab === 'multi' ? "bg-surface shadow-sm text-text" : "text-text-muted hover:text-text"
              )}
            >
              Multi-GPU
              <div className="px-1.5 py-0.5 rounded-full bg-primary/20 text-primary text-[10px] leading-none ml-1">New</div>
            </button>
          </div>
        </div>

        {computeTab === 'single' ? (
          <div className="space-y-4 pt-2">
            {onMaxActiveProjectsChange && (
              <div>
                <label className="text-xs font-medium text-text mb-1 block">
                  Max Active Projects
                  <InfoTooltip text="How many projects can be running background tasks simultaneously." />
                </label>
                <Select
                  value={maxActiveProjects?.toString() ?? 'infinite'}
                  onChange={(val) => onMaxActiveProjectsChange(val === 'infinite' ? 'infinite' : parseInt(val))}
                  options={[
                    { value: '1', label: '1 (Conservative)' },
                    { value: '2', label: '2' },
                    { value: '3', label: '3 (Standard)' },
                    { value: '4', label: '4' },
                    { value: '5', label: '5' },
                    { value: 'infinite', label: 'Infinite (Uncapped)' },
                  ]}
                />
              </div>
            )}
            
            {onConcurrencyChange && (
              <div>
                <label className="text-xs font-medium text-text mb-1 block">
                  Hardware Concurrency Profile
                  <InfoTooltip text="How many parallel LLM requests to allow on your local machine. Cloud endpoints auto-scale based on batch limits." />
                </label>
                <Select
                  value={concurrencyFast?.toString() ?? '1'}
                  onChange={(val) => {
                    const c = parseInt(val);
                    onConcurrencyChange('fast', c);
                    onConcurrencyChange('code', c);
                    onConcurrencyChange('deep', c);
                  }}
                  options={[
                    { value: '1', label: '1 (Single GPU, 8-16GB VRAM, Mac M1/M2)' },
                    { value: '2', label: '2 (16-32GB VRAM, Mac M3/M4)' },
                    { value: '3', label: '3' },
                    { value: '4', label: '4 (32-48GB VRAM, Mac Pro, RTX 4090)' },
                    { value: '6', label: '6' },
                    { value: '8', label: '8 (64GB+ VRAM or multi-GPU)' },
                  ]}
                />
                <p className="text-xs text-text-muted mt-2">
                  When using NativeEmbedder, knowledge embedding runs on a completely separate ONNX queue and does not block LLM concurrency.
                </p>
              </div>
            )}
          </div>
        ) : (
          <div className="space-y-4 pt-2">
            <div className="p-4 border border-primary/20 bg-primary/5 rounded-lg flex flex-col items-center text-center">
              <Server className="w-8 h-8 text-primary mb-2 opacity-80" />
              <h4 className="text-sm font-semibold text-text">Multi-Node Orchestration</h4>
              <p className="text-xs text-text-muted mt-1 max-w-md">
                Map specific endpoints to remote GPU servers or local hardware. CoDRAG will schedule pipeline tasks across multiple nodes concurrently.
              </p>
              
              <div className="mt-4 w-full flex flex-col gap-2 text-left">
                {config.compute_nodes?.map(node => (
                  <div key={node.id} className="p-3 border border-border bg-surface-raised rounded-md flex justify-between items-center">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-text">{node.name}</span>
                        <span className="text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded bg-surface border border-border text-text-muted">
                          {node.type}
                        </span>
                      </div>
                      <div className="text-xs text-text-muted mt-1">
                        Concurrency: {node.max_concurrent} &bull; {node.endpoint_ids.length} endpoints
                      </div>
                    </div>
                    <Button variant="ghost" size="sm">Edit Node</Button>
                  </div>
                ))}
              </div>
              
              <Button variant="outline" size="sm" className="mt-4 w-full">
                <Plus className="w-4 h-4 mr-2" />
                Add Compute Node
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* Cloud Processing */}"""

content = re.sub(
    old_compute_profile,
    new_compute_profile,
    content,
    flags=re.DOTALL
)

with open('packages/ui/src/components/llm/AIModelsSettings.tsx', 'w') as f:
    f.write(content)
