import re

with open("/Volumes/4TB-BAD/HumanAI/CoDRAG/packages/ui/src/components/llm/AIModelsSettings.tsx", "r") as f:
    text = f.read()

# Update the Max Concurrent dropdown label and guidance text in the add/edit form
old_edit_form_inputs = """                  <div>
                    <label className="block text-[10px] font-medium text-text-muted mb-1">Max Concurrent</label>
                    <Select
                      size="sm"
                      value={String(formConcurrency)}
                      onChange={(e) => setFormConcurrency(parseInt(e.target.value))}
                      options={[1, 2, 3, 4, 6, 8].map((n) => ({ value: String(n), label: String(n) }))}
                      className="w-full"
                    />
                  </div>"""

new_edit_form_inputs = """                  <div>
                    <label className="block text-[10px] font-medium text-text-muted mb-1">LLM Concurrency</label>
                    <Select
                      size="sm"
                      value={String(formConcurrency)}
                      onChange={(e) => setFormConcurrency(parseInt(e.target.value))}
                      options={[1, 2, 3, 4, 6, 8].map((n) => ({ value: String(n), label: String(n) }))}
                      className="w-full"
                    />
                  </div>"""

old_add_form_inputs = """            <div>
              <label className="block text-[10px] font-medium text-text-muted mb-1">Max Concurrent</label>
              <Select
                size="sm"
                value={String(formConcurrency)}
                onChange={(e) => setFormConcurrency(parseInt(e.target.value))}
                options={[1, 2, 3, 4, 6, 8].map((n) => ({ value: String(n), label: String(n) }))}
                className="w-full"
              />
            </div>"""

new_add_form_inputs = """            <div>
              <label className="block text-[10px] font-medium text-text-muted mb-1">LLM Concurrency</label>
              <Select
                size="sm"
                value={String(formConcurrency)}
                onChange={(e) => setFormConcurrency(parseInt(e.target.value))}
                options={[1, 2, 3, 4, 6, 8].map((n) => ({ value: String(n), label: String(n) }))}
                className="w-full"
              />
            </div>"""

text = text.replace(old_edit_form_inputs, new_edit_form_inputs)
text = text.replace(old_add_form_inputs, new_add_form_inputs)

# Update the guidance text at the bottom of the ComputeNodePanel
old_guidance = """      <p className="text-[9px] text-text-muted opacity-70">
        Assign endpoints to compute nodes to control which hardware runs each model. Concurrency slots are managed per node.
      </p>"""

new_guidance = """      <p className="text-[9px] text-text-muted opacity-70">
        Assign endpoints to compute nodes to control which hardware runs each model. Concurrency slots are managed per node.<br/>
        <strong>Concurrency Guidance:</strong> 1: Single GPU, 8-16GB VRAM (Mac M1/M2, RTX 3060) | 2: 16-32GB VRAM (Mac M3/M4, RTX 3070/4060) | 4: 32-48GB VRAM (Mac Pro/Ultra, RTX 4090)
      </p>"""

text = text.replace(old_guidance, new_guidance)

with open("/Volumes/4TB-BAD/HumanAI/CoDRAG/packages/ui/src/components/llm/AIModelsSettings.tsx", "w") as f:
    f.write(text)
    
print("Patched AIModelsSettings.tsx with abstract concurrency profiles")
