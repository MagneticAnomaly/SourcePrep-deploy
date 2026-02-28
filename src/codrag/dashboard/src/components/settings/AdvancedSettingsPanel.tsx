import { useState, useEffect, useCallback } from 'react'
import { Sliders, GitBranch, FileCode, Cpu, Save, RotateCcw, AlertTriangle } from 'lucide-react'
import { useApiClient, Button, type ProjectConfig, type AdvancedConfig } from '@codrag/ui'

// ── Types ─────────────────────────────────────────────────────

interface NumberFieldProps {
  label: string
  description: string
  value: number
  defaultValue: number
  onChange: (v: number) => void
  min: number
  max: number
  step?: number
  unit?: string
}

function NumberField({ label, description, value, defaultValue, onChange, min, max, step = 1, unit }: NumberFieldProps) {
  const isDefault = value === defaultValue
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <label className="text-xs font-medium text-text-subtle">{label}</label>
        {!isDefault && (
          <button
            onClick={() => onChange(defaultValue)}
            className="text-[10px] text-primary hover:text-primary-hover transition-colors"
            title={`Reset to default (${defaultValue.toLocaleString()})`}
          >
            reset
          </button>
        )}
      </div>
      <div className="flex items-center gap-2">
        <input
          type="number"
          value={value}
          onChange={(e) => {
            const n = parseInt(e.target.value) || min
            onChange(Math.max(min, Math.min(max, n)))
          }}
          min={min}
          max={max}
          step={step}
          className="flex-1 bg-surface-raised border border-border rounded px-2 py-1.5 text-xs text-text focus:outline-none focus:ring-1 focus:ring-primary"
        />
        {unit && <span className="text-[10px] text-text-muted w-16 shrink-0">{unit}</span>}
      </div>
      <p className="text-[10px] text-text-muted leading-relaxed">{description}</p>
    </div>
  )
}

function FloatField({ label, description, value, defaultValue, onChange, min, max, step = 0.05 }: NumberFieldProps & { step?: number }) {
  const isDefault = value === defaultValue
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <label className="text-xs font-medium text-text-subtle">{label}</label>
        {!isDefault && (
          <button
            onClick={() => onChange(defaultValue)}
            className="text-[10px] text-primary hover:text-primary-hover transition-colors"
            title={`Reset to default (${defaultValue})`}
          >
            reset
          </button>
        )}
      </div>
      <input
        type="range"
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        min={min}
        max={max}
        step={step}
        className="w-full accent-primary"
      />
      <div className="flex justify-between text-[10px] text-text-muted">
        <span>{min}</span>
        <span className="font-medium text-text">{value}</span>
        <span>{max}</span>
      </div>
      <p className="text-[10px] text-text-muted leading-relaxed">{description}</p>
    </div>
  )
}

// ── Defaults ─────────────────────────────────────────────────

const PROJECT_DEFAULTS = {
  max_files: 50_000,
  max_nodes: 100_000,
  max_edges: 500_000,
}

const GLOBAL_DEFAULTS: AdvancedConfig = {
  checkpoint_interval: 500,
  min_edge_confidence: 0.5,
  chunk_max_chars: 2000,
  chunk_overlap_chars: 200,
  md_chunk_max_chars: 1800,
  md_chunk_min_chars: 350,
}

// ── Component ────────────────────────────────────────────────

export interface AdvancedSettingsPanelProps {
  projectConfig: ProjectConfig
  onProjectConfigChange: (config: ProjectConfig) => void
  onSaveConfig: () => void
  configDirty: boolean
  hasProject: boolean
}

export function AdvancedSettingsPanel({
  projectConfig,
  onProjectConfigChange,
  onSaveConfig,
  configDirty,
  hasProject,
}: AdvancedSettingsPanelProps) {
  const api = useApiClient()
  const [globalConfig, setGlobalConfig] = useState<AdvancedConfig>(GLOBAL_DEFAULTS)
  const [globalDirty, setGlobalDirty] = useState(false)
  const [saving, setSaving] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)

  // Load global advanced config
  useEffect(() => {
    api.getAdvancedConfig()
      .then(setGlobalConfig)
      .catch((e) => setLoadError(e instanceof Error ? e.message : String(e)))
  }, [api])

  const adv = projectConfig.advanced ?? {}

  const updateProjectAdvanced = useCallback((key: string, value: number) => {
    onProjectConfigChange({
      ...projectConfig,
      advanced: { ...adv, [key]: value },
    })
  }, [projectConfig, adv, onProjectConfigChange])

  const updateGlobal = useCallback((key: keyof AdvancedConfig, value: number) => {
    setGlobalConfig((prev: AdvancedConfig) => ({ ...prev, [key]: value }))
    setGlobalDirty(true)
  }, [])

  const handleSaveGlobal = useCallback(async () => {
    setSaving(true)
    try {
      const result = await api.updateAdvancedConfig(globalConfig)
      setGlobalConfig(result)
      setGlobalDirty(false)
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : String(e))
    } finally {
      setSaving(false)
    }
  }, [api, globalConfig])

  const handleResetAll = useCallback(() => {
    setGlobalConfig(GLOBAL_DEFAULTS)
    setGlobalDirty(true)
    if (hasProject) {
      onProjectConfigChange({
        ...projectConfig,
        advanced: { ...PROJECT_DEFAULTS },
      })
    }
  }, [hasProject, projectConfig, onProjectConfigChange])

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sliders className="w-4 h-4 text-primary" />
          <h3 className="text-sm font-semibold text-text">Advanced Settings</h3>
        </div>
        <button
          onClick={handleResetAll}
          className="flex items-center gap-1 text-[10px] text-text-muted hover:text-text transition-colors"
          title="Reset all to defaults"
        >
          <RotateCcw className="w-3 h-3" />
          Reset All
        </button>
      </div>

      <div className="p-3 rounded-md border border-warning/30 bg-warning/5 flex items-start gap-2">
        <AlertTriangle className="w-4 h-4 text-warning mt-0.5 shrink-0" />
        <p className="text-xs text-text-muted leading-relaxed">
          These settings are for power users managing large or unusual codebases.
          Changes take effect on the next pipeline run. Incorrect values may cause slower builds or excessive resource usage.
        </p>
      </div>

      {loadError && (
        <p className="text-xs text-error">{loadError}</p>
      )}

      {/* Per-Project: Trace Limits */}
      {hasProject && (
        <section>
          <div className="flex items-center gap-2 mb-4">
            <GitBranch className="w-4 h-4 text-primary" />
            <h4 className="text-sm font-semibold text-text">Trace Limits</h4>
            <span className="text-[10px] text-text-muted bg-surface-raised px-1.5 py-0.5 rounded">per-project</span>
          </div>
          <p className="text-xs text-text-muted mb-4">
            Controls how many files and graph elements are processed during structural analysis.
            Raise these for large monorepos; lower for faster iteration on smaller projects.
          </p>

          <div className="grid grid-cols-1 gap-4">
            <NumberField
              label="Max Files"
              description="Maximum number of source files to trace. Files beyond this are silently skipped."
              value={adv.max_files ?? PROJECT_DEFAULTS.max_files}
              defaultValue={PROJECT_DEFAULTS.max_files}
              onChange={(v) => updateProjectAdvanced('max_files', v)}
              min={1000}
              max={200_000}
              step={5000}
              unit={`${((adv.max_files ?? PROJECT_DEFAULTS.max_files) / 1000).toFixed(0)}K files`}
            />
            <NumberField
              label="Max Nodes"
              description="Maximum AST nodes (functions, classes, files) in the code graph."
              value={adv.max_nodes ?? PROJECT_DEFAULTS.max_nodes}
              defaultValue={PROJECT_DEFAULTS.max_nodes}
              onChange={(v) => updateProjectAdvanced('max_nodes', v)}
              min={10_000}
              max={1_000_000}
              step={50000}
              unit={`${((adv.max_nodes ?? PROJECT_DEFAULTS.max_nodes) / 1000).toFixed(0)}K nodes`}
            />
            <NumberField
              label="Max Edges"
              description="Maximum relationships (imports, calls, references) in the code graph."
              value={adv.max_edges ?? PROJECT_DEFAULTS.max_edges}
              defaultValue={PROJECT_DEFAULTS.max_edges}
              onChange={(v) => updateProjectAdvanced('max_edges', v)}
              min={50_000}
              max={5_000_000}
              step={100000}
              unit={`${((adv.max_edges ?? PROJECT_DEFAULTS.max_edges) / 1000).toFixed(0)}K edges`}
            />
          </div>
        </section>
      )}

      {hasProject && <div className="h-px bg-border" />}

      {/* Global: Chunking */}
      <section>
        <div className="flex items-center gap-2 mb-4">
          <FileCode className="w-4 h-4 text-primary" />
          <h4 className="text-sm font-semibold text-text">Chunking</h4>
          <span className="text-[10px] text-text-muted bg-surface-raised px-1.5 py-0.5 rounded">global</span>
        </div>
        <p className="text-xs text-text-muted mb-4">
          Controls how source files are split into chunks for embedding and search.
          Larger chunks capture more context but reduce precision; smaller chunks are more precise but may miss broader patterns.
        </p>

        <div className="grid grid-cols-2 gap-4">
          <NumberField
            label="Code Chunk Size"
            description="Max characters per code chunk."
            value={globalConfig.chunk_max_chars}
            defaultValue={GLOBAL_DEFAULTS.chunk_max_chars}
            onChange={(v) => updateGlobal('chunk_max_chars', v)}
            min={500}
            max={10000}
            step={100}
            unit={`${globalConfig.chunk_max_chars} chars`}
          />
          <NumberField
            label="Code Overlap"
            description="Overlap between adjacent chunks."
            value={globalConfig.chunk_overlap_chars}
            defaultValue={GLOBAL_DEFAULTS.chunk_overlap_chars}
            onChange={(v) => updateGlobal('chunk_overlap_chars', v)}
            min={0}
            max={2000}
            step={50}
            unit={`${globalConfig.chunk_overlap_chars} chars`}
          />
          <NumberField
            label="Markdown Chunk Size"
            description="Max characters per documentation chunk."
            value={globalConfig.md_chunk_max_chars}
            defaultValue={GLOBAL_DEFAULTS.md_chunk_max_chars}
            onChange={(v) => updateGlobal('md_chunk_max_chars', v)}
            min={500}
            max={10000}
            step={100}
            unit={`${globalConfig.md_chunk_max_chars} chars`}
          />
          <NumberField
            label="Markdown Min Size"
            description="Sections smaller than this are merged."
            value={globalConfig.md_chunk_min_chars}
            defaultValue={GLOBAL_DEFAULTS.md_chunk_min_chars}
            onChange={(v) => updateGlobal('md_chunk_min_chars', v)}
            min={50}
            max={2000}
            step={50}
            unit={`${globalConfig.md_chunk_min_chars} chars`}
          />
        </div>
      </section>

      <div className="h-px bg-border" />

      {/* Global: Pipeline */}
      <section>
        <div className="flex items-center gap-2 mb-4">
          <Cpu className="w-4 h-4 text-primary" />
          <h4 className="text-sm font-semibold text-text">Pipeline</h4>
          <span className="text-[10px] text-text-muted bg-surface-raised px-1.5 py-0.5 rounded">global</span>
        </div>
        <p className="text-xs text-text-muted mb-4">
          Controls pipeline behavior during graph enrichment. Checkpoints save progress periodically
          so crashes don't lose work. Edge confidence filters out low-quality inferred relationships.
        </p>

        <div className="grid grid-cols-1 gap-4">
          <NumberField
            label="Checkpoint Interval"
            description="Save augmentation progress every N items. Lower = more frequent saves (slower but safer)."
            value={globalConfig.checkpoint_interval}
            defaultValue={GLOBAL_DEFAULTS.checkpoint_interval}
            onChange={(v) => updateGlobal('checkpoint_interval', v)}
            min={50}
            max={5000}
            step={50}
            unit={`every ${globalConfig.checkpoint_interval} items`}
          />
          <FloatField
            label="Min Edge Confidence"
            description="Inferred edges below this confidence threshold are discarded. Higher = fewer but more reliable edges."
            value={globalConfig.min_edge_confidence}
            defaultValue={GLOBAL_DEFAULTS.min_edge_confidence}
            onChange={(v) => updateGlobal('min_edge_confidence', v)}
            min={0.1}
            max={0.9}
            step={0.05}
          />
        </div>
      </section>

      {/* Save Buttons */}
      {(configDirty || globalDirty) && (
        <div className="pt-6 border-t border-border sticky bottom-0 bg-surface -mb-6 pb-6 space-y-2">
          {configDirty && hasProject && (
            <Button onClick={onSaveConfig} className="w-full shadow-sm" icon={Save}>
              Save Project Settings
            </Button>
          )}
          {globalDirty && (
            <Button
              onClick={handleSaveGlobal}
              variant={configDirty ? 'outline' : 'default'}
              className="w-full shadow-sm"
              icon={Save}
              disabled={saving}
            >
              {saving ? 'Saving...' : 'Save Global Settings'}
            </Button>
          )}
        </div>
      )}
    </div>
  )
}
