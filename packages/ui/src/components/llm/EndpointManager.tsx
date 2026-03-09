import { useState } from 'react';
import { cn } from '../../lib/utils';
import type { SavedEndpoint, LLMProvider, EndpointTestResult, ComputeNode } from '../../types';
import { Plus, Trash2, Edit2, Play, CheckCircle, AlertCircle, Server } from 'lucide-react';
import { Button } from '../primitives/Button';
import { Select } from '../primitives/Select';
import { InfoTooltip } from '../primitives/InfoTooltip';

export interface EndpointManagerProps {
  endpoints: SavedEndpoint[];
  onAdd: (endpoint: Omit<SavedEndpoint, 'id'>) => void;
  onEdit: (endpoint: SavedEndpoint) => void;
  onDelete: (id: string) => void;
  onTest: (endpoint: SavedEndpoint) => Promise<EndpointTestResult>;
  computeNodes?: ComputeNode[];
  onEndpointNodeChange?: (endpointId: string, nodeId: string | null) => void;
  className?: string;
}

const PROVIDER_OPTIONS: { value: LLMProvider; label: string; hint?: string }[] = [
  { value: 'ollama', label: 'Ollama', hint: 'http://localhost:11434' },
  { value: 'lm-studio', label: 'LM Studio', hint: 'http://localhost:1234' },
  { value: 'openai', label: 'OpenAI', hint: 'https://api.openai.com/v1' },
  { value: 'openai-compatible', label: 'OpenAI Compatible' },
  { value: 'anthropic', label: 'Anthropic (Claude)', hint: 'https://api.anthropic.com' },
  { value: 'google', label: 'Google (Gemini)', hint: 'https://generativelanguage.googleapis.com' },
];

export function EndpointManager({
  endpoints,
  onAdd,
  onEdit,
  onDelete,
  onTest,
  computeNodes,
  onEndpointNodeChange,
  className,
}: EndpointManagerProps) {
  const [showAddForm, setShowAddForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [testingId, setTestingId] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<Record<string, EndpointTestResult>>({});
  
  // Form state
  const [formName, setFormName] = useState('');
  const [formProvider, setFormProvider] = useState<LLMProvider>('ollama');
  const [formUrl, setFormUrl] = useState('');
  const [formApiKey, setFormApiKey] = useState('');

  const resetForm = () => {
    setFormName('');
    setFormProvider('ollama');
    setFormUrl('');
    setFormApiKey('');
    setShowAddForm(false);
    setEditingId(null);
  };

  const handleAdd = () => {
    if (!formName.trim() || !formUrl.trim()) return;
    onAdd({
      name: formName.trim(),
      provider: formProvider,
      url: formUrl.trim(),
      api_key: formApiKey.trim() || undefined,
    });
    resetForm();
  };

  const handleEdit = (ep: SavedEndpoint) => {
    setEditingId(ep.id);
    setFormName(ep.name);
    setFormProvider(ep.provider);
    setFormUrl(ep.url);
    setFormApiKey(ep.api_key || '');
    setShowAddForm(false);
  };

  const handleSaveEdit = () => {
    if (!editingId || !formName.trim() || !formUrl.trim()) return;
    onEdit({
      id: editingId,
      name: formName.trim(),
      provider: formProvider,
      url: formUrl.trim(),
      api_key: formApiKey.trim() || undefined,
    });
    resetForm();
  };

  const handleTest = async (ep: SavedEndpoint) => {
    setTestingId(ep.id);
    try {
      const result = await onTest(ep);
      setTestResults((prev) => ({ ...prev, [ep.id]: result }));
    } catch (err) {
      setTestResults((prev) => ({
        ...prev,
        [ep.id]: { success: false, message: 'Test failed' },
      }));
    }
    setTestingId(null);
  };

  const providerNeedsApiKey = (provider: LLMProvider) =>
    provider === 'openai' || provider === 'anthropic' || provider === 'openai-compatible' || provider === 'google';

  const providerDefaultUrl = (provider: LLMProvider) =>
    PROVIDER_OPTIONS.find((o) => o.value === provider)?.hint ?? '';

  return (
    <div className={cn('codrag-card rounded-lg border border-border bg-surface p-6', className)}>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-lg font-semibold text-text flex items-center gap-2">
            <Server className="w-5 h-5 text-primary" />
            <InfoTooltip 
              content="Learn about supported LLM providers." 
              href="https://docs.codrag.io/guides/models" 
            />
            Saved Endpoints
          </h3>
          <p className="text-sm text-text-muted mt-1">Manage local and remote LLM server connections</p>
        </div>
      </div>

      {/* Endpoint List */}
      <div className="space-y-3 mb-6">
        {endpoints.length === 0 ? (
          <div className="text-sm text-text-muted py-8 text-center bg-surface-raised rounded-lg border border-dashed border-border">
            No saved endpoints found
          </div>
        ) : (
          endpoints.map((ep) => (
            <div
              key={ep.id}
              className={cn(
                "p-4 border rounded-lg transition-colors",
                editingId === ep.id 
                  ? "bg-surface-raised border-primary/50" 
                  : "border-border hover:border-border-subtle bg-surface"
              )}
            >
              {editingId === ep.id ? (
                // Edit form inline
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-medium text-text-muted mb-1">Display Name</label>
                      <input
                        placeholder="Display Name"
                        value={formName}
                        onChange={(e) => setFormName(e.target.value)}
                        className="w-full bg-surface border border-border rounded px-3 py-2 text-sm text-text focus:outline-none focus:ring-2 focus:ring-primary"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-text-muted mb-1">Provider</label>
                      <Select
                        value={formProvider}
                        onChange={(e) => setFormProvider(e.target.value as LLMProvider)}
                        options={PROVIDER_OPTIONS.map((o) => ({ value: o.value, label: o.label }))}
                        className="w-full"
                      />
                    </div>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-text-muted mb-1">Endpoint URL</label>
                    <input
                      placeholder={providerDefaultUrl(formProvider) || 'Endpoint URL'}
                      value={formUrl}
                      onChange={(e) => setFormUrl(e.target.value)}
                      className="w-full bg-surface border border-border rounded px-3 py-2 text-sm text-text focus:outline-none focus:ring-2 focus:ring-primary"
                    />
                  </div>
                  {providerNeedsApiKey(formProvider) && (
                    <div>
                      <label className="block text-xs font-medium text-text-muted mb-1">API Key</label>
                      <input
                        placeholder="API Key"
                        type="password"
                        value={formApiKey}
                        onChange={(e) => setFormApiKey(e.target.value)}
                        className="w-full bg-surface border border-border rounded px-3 py-2 text-sm text-text focus:outline-none focus:ring-2 focus:ring-primary"
                      />
                    </div>
                  )}
                  <div className="flex gap-2 pt-2 justify-end">
                    <Button 
                      onClick={resetForm}
                      variant="outline"
                      size="sm"
                    >
                      Cancel
                    </Button>
                    <Button 
                      onClick={handleSaveEdit}
                      size="sm"
                    >
                      Save Changes
                    </Button>
                  </div>
                </div>
              ) : (
                // Display mode
                <div className="flex items-center justify-between">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-medium text-sm text-text">{ep.name}</span>
                      <span className="text-xs px-2 py-0.5 rounded-full bg-surface-raised text-text-muted border border-border">
                        {ep.provider}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <code className="text-xs text-text-subtle font-mono truncate max-w-[200px]">
                        {ep.url}
                      </code>
                      {computeNodes && computeNodes.length > 0 && onEndpointNodeChange && (
                        <Select
                          size="sm"
                          value={ep.compute_node_id || ''}
                          onChange={(e) => onEndpointNodeChange(ep.id, e.target.value || null)}
                          options={[
                            { value: '', label: 'Auto (default node)' },
                            ...computeNodes.map((n) => ({
                              value: n.id,
                              label: `${n.name}${n.gpu_name ? ` · ${n.gpu_name}` : ''}`
                            }))
                          ]}
                          className="max-w-[180px]"
                        />
                      )}
                    </div>
                    {testResults[ep.id] && (
                      <div className={cn(
                        'text-xs mt-2 flex items-center gap-1.5',
                        testResults[ep.id].success ? 'text-success' : 'text-error'
                      )}>
                        {testResults[ep.id].success ? (
                          <CheckCircle className="w-3.5 h-3.5" />
                        ) : (
                          <AlertCircle className="w-3.5 h-3.5" />
                        )}
                        {testResults[ep.id].message}
                      </div>
                    )}
                  </div>
                  <div className="flex gap-2 ml-4">
                    <Button
                      onClick={() => handleTest(ep)}
                      disabled={testingId === ep.id}
                      variant="ghost"
                      size="icon-sm"
                      className={cn(testingId === ep.id && "opacity-70")}
                      aria-label="Test Connection"
                    >
                      <Play className={cn("w-4 h-4", testingId === ep.id && "animate-pulse")} />
                    </Button>
                    <Button
                      onClick={() => handleEdit(ep)}
                      variant="ghost"
                      size="icon-sm"
                      aria-label="Edit"
                    >
                      <Edit2 className="w-4 h-4" />
                    </Button>
                    <Button
                      onClick={() => onDelete(ep.id)}
                      variant="ghost"
                      size="icon-sm"
                      className="hover:bg-error-muted/10 hover:text-error"
                      aria-label="Delete"
                    >
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
              )}
            </div>
          ))
        )}
      </div>

      {/* Add New Endpoint */}
      {showAddForm ? (
        <div className="p-4 border border-border rounded-lg bg-surface-raised/50 space-y-4 animate-in fade-in slide-in-from-top-2">
          <h4 className="text-sm font-semibold font-mono text-text">Add New Endpoint</h4>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-text-muted mb-1">Display Name</label>
              <input
                placeholder="e.g. Local Ollama"
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                className="w-full bg-surface border border-border rounded px-3 py-2 text-sm text-text focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-text-muted mb-1">Provider</label>
              <Select
                value={formProvider}
                onChange={(e) => setFormProvider(e.target.value as LLMProvider)}
                options={PROVIDER_OPTIONS.map((o) => ({ value: o.value, label: o.label }))}
                className="w-full"
              />
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium text-text-muted mb-1">Endpoint URL</label>
            <input
              placeholder={providerDefaultUrl(formProvider) || 'e.g., http://localhost:11434'}
              value={formUrl}
              onChange={(e) => setFormUrl(e.target.value)}
              className="w-full bg-surface border border-border rounded px-3 py-2 text-sm text-text focus:outline-none focus:ring-2 focus:ring-primary"
            />
          </div>
          {providerNeedsApiKey(formProvider) && (
            <div>
              <label className="block text-xs font-medium text-text-muted mb-1">API Key</label>
              <input
                placeholder="sk-..."
                type="password"
                value={formApiKey}
                onChange={(e) => setFormApiKey(e.target.value)}
                className="w-full bg-surface border border-border rounded px-3 py-2 text-sm text-text focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>
          )}
          <div className="flex gap-2 pt-2">
            <Button 
              onClick={handleAdd}
              size="sm"
            >
              Add Endpoint
            </Button>
            <Button 
              onClick={resetForm}
              variant="outline"
              size="sm"
            >
              Cancel
            </Button>
          </div>
        </div>
      ) : (
        <button
          onClick={() => setShowAddForm(true)}
          className="w-full py-3 border border-dashed border-border rounded-lg text-sm text-text-muted hover:text-text hover:border-primary/50 hover:bg-surface-raised transition-all flex items-center justify-center gap-2 group"
        >
          <Plus className="w-4 h-4 group-hover:scale-110 transition-transform" />
          Add New Endpoint
        </button>
      )}
    </div>
  );
}
