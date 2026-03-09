import re

with open("/Volumes/4TB-BAD/HumanAI/CoDRAG/packages/ui/src/components/llm/AIModelsSettings.tsx", "r") as f:
    text = f.read()

# Add formHardwareProfile state
old_state = """  const [formType, setFormType] = useState<'local' | 'remote' | 'cloud'>('local');
  const [formConcurrency, setFormConcurrency] = useState(1);
  const [formGpuName, setFormGpuName] = useState('');"""

new_state = """  const [formType, setFormType] = useState<'local' | 'remote' | 'cloud'>('local');
  const [formHardwareProfile, setFormHardwareProfile] = useState<import('../../types').ComputeHardwareProfile | ''>('');
  const [formConcurrency, setFormConcurrency] = useState(1);
  const [formGpuName, setFormGpuName] = useState('');"""

# Update resetForm
old_reset = """  const resetForm = () => {
    setFormName('');
    setFormType('local');
    setFormConcurrency(1);
    setFormGpuName('');
    setAdding(false);
    setEditingId(null);
  };"""

new_reset = """  const resetForm = () => {
    setFormName('');
    setFormType('local');
    setFormHardwareProfile('');
    setFormConcurrency(1);
    setFormGpuName('');
    setAdding(false);
    setEditingId(null);
  };"""

# Update handleAdd
old_add = """    onAdd({
      name: formName.trim(),
      type: formType,
      max_concurrent: formConcurrency,
      gpu_name: formGpuName.trim() || undefined,
      endpoint_ids: [],
    });"""

new_add = """    onAdd({
      name: formName.trim(),
      type: formType,
      hardware_profile: formHardwareProfile || undefined,
      max_concurrent: formConcurrency,
      gpu_name: formGpuName.trim() || undefined,
      endpoint_ids: [],
    });"""

# Update startEdit
old_edit = """  const startEdit = (node: ComputeNode) => {
    setEditingId(node.id);
    setFormName(node.name);
    setFormType(node.type);
    setFormConcurrency(node.max_concurrent);
    setFormGpuName(node.gpu_name || '');
  };"""

new_edit = """  const startEdit = (node: ComputeNode) => {
    setEditingId(node.id);
    setFormName(node.name);
    setFormType(node.type);
    setFormHardwareProfile(node.hardware_profile || '');
    setFormConcurrency(node.max_concurrent);
    setFormGpuName(node.gpu_name || '');
  };"""

# Update handleSaveEdit
old_save = """    onUpdate(editingId, {
      name: formName.trim(),
      type: formType,
      max_concurrent: formConcurrency,
      gpu_name: formGpuName.trim() || undefined,
    });"""

new_save = """    onUpdate(editingId, {
      name: formName.trim(),
      type: formType,
      hardware_profile: formHardwareProfile || undefined,
      max_concurrent: formConcurrency,
      gpu_name: formGpuName.trim() || undefined,
    });"""

# Add hardware profile dropdown to edit form
old_edit_form_inputs = """                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block text-[10px] font-medium text-text-muted mb-1">GPU / Hardware</label>
                    <input
                      value={formGpuName}"""

new_edit_form_inputs = """                <div className="grid grid-cols-3 gap-2">
                  <div>
                    <label className="block text-[10px] font-medium text-text-muted mb-1">Hardware Profile</label>
                    <Select
                      size="sm"
                      value={formHardwareProfile}
                      onChange={(e) => setFormHardwareProfile(e.target.value as any)}
                      options={[
                        { value: '', label: 'Auto Detect' },
                        { value: 'apple_silicon', label: 'Apple Silicon (M-Series)' },
                        { value: 'nvidia', label: 'NVIDIA Discrete GPU' },
                        { value: 'amd', label: 'AMD GPU' },
                        { value: 'intel', label: 'Intel Arc' },
                        { value: 'cloud', label: 'Cloud Endpoint' },
                      ]}
                      className="w-full"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] font-medium text-text-muted mb-1">GPU Name</label>
                    <input
                      value={formGpuName}"""

# Add hardware profile dropdown to add form
old_add_form_inputs = """          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="block text-[10px] font-medium text-text-muted mb-1">GPU / Hardware</label>
              <input
                value={formGpuName}"""

new_add_form_inputs = """          <div className="grid grid-cols-3 gap-2">
            <div>
              <label className="block text-[10px] font-medium text-text-muted mb-1">Hardware Profile</label>
              <Select
                size="sm"
                value={formHardwareProfile}
                onChange={(e) => setFormHardwareProfile(e.target.value as any)}
                options={[
                  { value: '', label: 'Auto Detect' },
                  { value: 'apple_silicon', label: 'Apple Silicon (M-Series)' },
                  { value: 'nvidia', label: 'NVIDIA Discrete GPU' },
                  { value: 'amd', label: 'AMD GPU' },
                  { value: 'intel', label: 'Intel Arc' },
                  { value: 'cloud', label: 'Cloud Endpoint' },
                ]}
                className="w-full"
              />
            </div>
            <div>
              <label className="block text-[10px] font-medium text-text-muted mb-1">GPU Name</label>
              <input
                value={formGpuName}"""


text = text.replace(old_state, new_state)
text = text.replace(old_reset, new_reset)
text = text.replace(old_add, new_add)
text = text.replace(old_edit, new_edit)
text = text.replace(old_save, new_save)
text = text.replace(old_edit_form_inputs, new_edit_form_inputs)
text = text.replace(old_add_form_inputs, new_add_form_inputs)

with open("/Volumes/4TB-BAD/HumanAI/CoDRAG/packages/ui/src/components/llm/AIModelsSettings.tsx", "w") as f:
    f.write(text)
    
print("Patched AIModelsSettings.tsx with Hardware Profile dropdowns")
