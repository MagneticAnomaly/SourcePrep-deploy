import { useState, useCallback, useEffect } from 'react'
import { Settings, X, ImageIcon, Key, Shield, Trash2, Palette, Activity, ClipboardCheck, Cpu, Info, ExternalLink } from 'lucide-react'
import {
  useApiClient,
  Button,
  ConfirmDialog,
  Select,
  ProjectSettingsPanel,
  DeepAnalysisSettings,
  type ProjectConfig,
  type LicenseStatus,
  type LicenseTier,
  type DeepAnalysisSchedule,
} from '@codrag/ui'
import { AdvancedSettingsPanel } from './AdvancedSettingsPanel'

// ── Constants ────────────────────────────────────────────────

const MODE_OPTIONS = [
  { value: 'light', label: 'Light' },
  { value: 'dark', label: 'Dark' },
]

const THEME_OPTIONS = [
  { value: 'none', label: 'Default' },
  { value: 'a', label: 'A: Slate Developer' },
  { value: 'b', label: 'B: Deep Focus' },
  { value: 'c', label: 'C: Signal Green' },
  { value: 'd', label: 'D: Warm Craft' },
  { value: 'e', label: 'E: Neo-Brutalist' },
  { value: 'f', label: 'F: Swiss Minimal' },
  { value: 'g', label: 'G: Glass-Morphic' },
  { value: 'h', label: 'H: Retro-Futurism' },
  { value: 'm', label: 'M: Retro Aurora' },
  { value: 'n', label: 'N: Retro Mirage' },
  { value: 'i', label: 'I: Studio Collage' },
  { value: 'j', label: 'J: Yale Grid' },
  { value: 'k', label: 'K: Inclusive Focus' },
  { value: 'l', label: 'L: Enterprise Console' },
]

const HARDWARE_PROFILE_OPTIONS = [
  { value: 'apple_silicon', label: 'Apple Silicon (Mac)' },
  { value: 'nvidia_small', label: 'NVIDIA GPU (≤24 GB)' },
  { value: 'nvidia_large', label: 'NVIDIA GPU (32 GB+)' },
  { value: 'cloud', label: 'Cloud API' },
  { value: 'custom', label: 'Custom' },
]

const LLM_CONCURRENCY_OPTIONS = [
  { value: '1', label: '1 — Sequential' },
  { value: '2', label: '2' },
  { value: '3', label: '3' },
  { value: '4', label: '4' },
  { value: '5', label: '5' },
  { value: '6', label: '6' },
  { value: '8', label: '8' },
]

/** Map hardware profile → concurrency values for fast/code/deep */
const HARDWARE_CONCURRENCY: Record<string, { fast: number; code: number; deep: number }> = {
  apple_silicon: { fast: 1, code: 1, deep: 1 },
  nvidia_small:  { fast: 2, code: 2, deep: 1 },
  nvidia_large:  { fast: 4, code: 2, deep: 2 },
  cloud:         { fast: 5, code: 3, deep: 3 },
}

/** Detect hardware profile from concurrency values (returns 'custom' if user has overridden) */
function detectProfile(fast: number, code: number, deep: number, forceCustom?: boolean): string {
  if (forceCustom) return 'custom'
  for (const [key, c] of Object.entries(HARDWARE_CONCURRENCY)) {
    if (c.fast === fast && c.code === code && c.deep === deep) return key
  }
  return 'custom'
}

const DEV_TIER_OPTIONS = [
  { value: '', label: 'Off (use real license)' },
  { value: 'free', label: 'Free' },
  { value: 'pro', label: 'Pro' },
  { value: 'team', label: 'Team' },
  { value: 'enterprise', label: 'Enterprise' },
]

// ── Settings Panel (drawer) ──────────────────────────────────
type SettingsDrawerTab = 'project' | 'global' | 'advanced' | 'developer'

export interface SettingsDrawerProps {
  open: boolean
  onClose: () => void
  /** When provided, forces this tab to be active whenever the drawer opens */
  openToTab?: SettingsDrawerTab
  /** When true, scrolls to the Deep Enrichment section after opening */
  scrollToDeepAnalysis?: boolean
  // Project tab
  projectConfig: ProjectConfig
  onProjectConfigChange: (config: ProjectConfig) => void
  onSaveConfig: () => void
  configDirty: boolean
  hasProject: boolean
  onDetectStack?: () => Promise<{
    recommended_globs: string[];
    detected_presets: string[];
    all_presets: Record<string, string[]>;
  }>
  // Deep Analysis (Project tab)
  deepAnalysisSchedule: DeepAnalysisSchedule
  onDeepAnalysisScheduleChange: (schedule: DeepAnalysisSchedule) => void
  largeModelConfigured: boolean
  fastModelConfigured: boolean
  // Global tab
  maxActiveProjects: number | 'infinite'
  onMaxActiveProjectsChange: (val: number | 'infinite') => void
  uiMode: 'light' | 'dark'
  onModeChange: (mode: 'light' | 'dark') => void
  uiTheme: string
  onThemeChange: (theme: string) => void
  bgImage: string | null
  onBgImageChange: (url: string | null) => void
  // License (Global tab)
  licenseStatus: LicenseStatus | null
  licenseKeyInput: string
  onLicenseKeyInputChange: (key: string) => void
  onActivateLicense: () => void
  onDeactivateLicense: () => void
  licenseLoading: boolean
  licenseError: string | null
  // Project tab – danger zone
  onDestroyGraph: () => void
  onDestroyIndex: () => void
  // Developer tab
  devTierOverride: LicenseTier | null
  onDevTierOverrideChange: (tier: LicenseTier | null) => void
}

export function SettingsDrawer({
  open,
  onClose,
  openToTab,
  projectConfig,
  onProjectConfigChange,
  onSaveConfig,
  configDirty,
  hasProject,
  onDetectStack,
  deepAnalysisSchedule,
  onDeepAnalysisScheduleChange,
  largeModelConfigured,
  fastModelConfigured,
  maxActiveProjects,
  onMaxActiveProjectsChange,
  uiMode,
  onModeChange,
  uiTheme,
  onThemeChange,
  bgImage,
  onBgImageChange,
  licenseStatus,
  licenseKeyInput,
  onLicenseKeyInputChange,
  onActivateLicense,
  onDeactivateLicense,
  licenseLoading,
  licenseError,
  onDestroyGraph,
  onDestroyIndex,
  devTierOverride,
  onDevTierOverrideChange,
  scrollToDeepAnalysis,
}: SettingsDrawerProps) {
  const api = useApiClient()
  const [activeTab, setActiveTab] = useState<SettingsDrawerTab>('project')
  const [healthResult, setHealthResult] = useState<string>('No test run yet')
  const [concurrencyFast, setConcurrencyFast] = useState<number>(1)
  const [concurrencyCode, setConcurrencyCode] = useState<number>(1)
  const [concurrencyDeep, setConcurrencyDeep] = useState<number>(1)
  const [concurrencySaving, setConcurrencySaving] = useState(false)
  const [forceCustomProfile, setForceCustomProfile] = useState(false)

  useEffect(() => {
    if (open && openToTab) setActiveTab(openToTab)
  }, [open, openToTab])

  // Load pipeline config when Global tab is shown
  useEffect(() => {
    if (open && activeTab === 'global') {
      api.getPipelineConfig()
        .then((config: any) => {
          if (config?.llm_concurrency_fast) setConcurrencyFast(config.llm_concurrency_fast)
          else if (config?.llm_concurrency) setConcurrencyFast(config.llm_concurrency)
          if (config?.llm_concurrency_code) setConcurrencyCode(config.llm_concurrency_code)
          else if (config?.llm_concurrency_fast) setConcurrencyCode(config.llm_concurrency_fast)
          else if (config?.llm_concurrency) setConcurrencyCode(config.llm_concurrency)
          if (config?.llm_concurrency_deep) setConcurrencyDeep(config.llm_concurrency_deep)
          else if (config?.llm_concurrency) setConcurrencyDeep(config.llm_concurrency)
        })
        .catch(() => {})
    }
  }, [open, activeTab, api])

  const handleConcurrencyFastChange = useCallback(async (value: number) => {
    setConcurrencyFast(value)
    setConcurrencySaving(true)
    try {
      await api.updatePipelineConfig({ llm_concurrency_fast: value })
    } catch {
      setConcurrencyFast((prev) => prev)
    } finally {
      setConcurrencySaving(false)
    }
  }, [api])

  const handleConcurrencyCodeChange = useCallback(async (value: number) => {
    setConcurrencyCode(value)
    setConcurrencySaving(true)
    try {
      await api.updatePipelineConfig({ llm_concurrency_code: value })
    } catch {
      setConcurrencyCode((prev) => prev)
    } finally {
      setConcurrencySaving(false)
    }
  }, [api])

  const handleConcurrencyDeepChange = useCallback(async (value: number) => {
    setConcurrencyDeep(value)
    setConcurrencySaving(true)
    try {
      await api.updatePipelineConfig({ llm_concurrency_deep: value })
    } catch {
      setConcurrencyDeep((prev) => prev)
    } finally {
      setConcurrencySaving(false)
    }
  }, [api])

  useEffect(() => {
    if (open && scrollToDeepAnalysis) {
      setTimeout(() => {
        document.getElementById('settings-deep-analysis')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }, 100)
    }
  }, [open, scrollToDeepAnalysis])
  const [confirmAction, setConfirmAction] = useState<'graph' | 'index' | null>(null)

  const handleConfirmedAction = useCallback(() => {
    if (confirmAction === 'graph') onDestroyGraph()
    if (confirmAction === 'index') onDestroyIndex()
    setConfirmAction(null)
  }, [confirmAction, onDestroyGraph, onDestroyIndex])

  const runHealthTest = async () => {
    setHealthResult('Testing...')
    try {
      const health = await api.getHealth()
      setHealthResult(`OK: ${JSON.stringify(health)}`)
    } catch (err) {
      setHealthResult(`Error: ${err instanceof Error ? err.message : String(err)}`)
    }
  }

  const handleBgUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = () => onBgImageChange(reader.result as string)
    reader.readAsDataURL(file)
  }

  if (!open) return null

  const tabs: { key: SettingsDrawerTab; label: string }[] = [
    { key: 'project', label: 'Project' },
    { key: 'global', label: 'Global' },
    { key: 'advanced', label: 'Advanced' },
    { key: 'developer', label: 'Developer' },
  ]

  return (
    <div className="fixed inset-y-0 right-0 z-50 w-[500px] bg-surface border-l border-border shadow-lg flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-border">
        <h2 className="text-base font-semibold text-text flex items-center gap-2">
          <Settings className="w-4 h-4" />
          Settings
        </h2>
        <Button variant="ghost" size="icon-sm" onClick={onClose} aria-label="Close">
          <X className="w-4 h-4" />
        </Button>
      </div>

      {/* Tab bar */}
      <div className="flex border-b border-border shrink-0 px-6">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setActiveTab(t.key)}
            className={`px-4 py-3 text-sm font-medium border-b-2 -mb-px transition-colors ${
              activeTab === t.key
                ? 'border-primary text-text'
                : 'border-transparent text-text-muted hover:text-text'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto p-6 space-y-8">
        {/* ── Project tab ── */}
        {activeTab === 'project' && hasProject && (
          <>
            <ProjectSettingsPanel
              config={projectConfig}
              onChange={onProjectConfigChange}
              onSave={onSaveConfig}
              onDetectStack={onDetectStack}
              isDirty={configDirty}
              bare
            />
            <div id="settings-deep-analysis" className="border-t border-border pt-6">
              <DeepAnalysisSettings
                schedule={deepAnalysisSchedule}
                onScheduleChange={onDeepAnalysisScheduleChange}
                largeModelConfigured={largeModelConfigured}
                fastModelConfigured={fastModelConfigured}
              />
            </div>
            <div className="border-t border-border pt-6">
              <section>
                <div className="flex items-center gap-2 mb-4">
                  <Trash2 className="w-4 h-4 text-error" />
                  <h3 className="text-sm font-semibold text-text">Danger Zone</h3>
                </div>
                <p className="text-xs text-text-muted mb-4">
                  These actions permanently delete project data and cannot be undone.
                </p>
                <div className="grid grid-cols-2 gap-4">
                  <div className="p-3 rounded border border-border bg-surface-raised flex flex-col justify-between gap-3">
                    <div>
                      <p className="text-sm font-medium text-text">Reset Graph</p>
                      <p className="text-xs text-text-muted mt-1">Deletes trace graph and all enrichment data.</p>
                    </div>
                    <Button variant="destructive" size="sm" onClick={() => setConfirmAction('graph')} className="w-full">
                      Reset
                    </Button>
                  </div>
                  <div className="p-3 rounded border border-error/30 bg-error/5 flex flex-col justify-between gap-3">
                    <div>
                      <p className="text-sm font-medium text-text">Full Reset</p>
                      <p className="text-xs text-text-muted mt-1">Deletes everything including search index.</p>
                    </div>
                    <Button variant="destructive" size="sm" onClick={() => setConfirmAction('index')} className="w-full">
                      Reset All
                    </Button>
                  </div>
                </div>
              </section>
            </div>
          </>
        )}
        {activeTab === 'project' && !hasProject && (
          <p className="text-sm text-text-muted">Select a project to configure settings.</p>
        )}

        {/* ── Global tab ── */}
        {activeTab === 'global' && (
          <>
            {/* Appearance */}
            <section>
              <div className="flex items-center gap-2 mb-4">
                <Palette className="w-4 h-4 text-primary" />
                <h3 className="text-sm font-semibold text-text">Appearance</h3>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-text-subtle">Color Mode</label>
                  <Select
                    value={uiMode}
                    onChange={(e) => onModeChange(e.target.value as 'light' | 'dark')}
                    aria-label="Color Mode"
                    size="sm"
                    options={MODE_OPTIONS}
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-text-subtle">Theme</label>
                  <Select
                    value={uiTheme}
                    onChange={(e) => onThemeChange(e.target.value)}
                    aria-label="Visual Theme"
                    size="sm"
                    options={THEME_OPTIONS}
                  />
                </div>
              </div>
            </section>

            {/* Background Image */}
            <section>
              <div className="flex items-center gap-2 mb-4">
                <ImageIcon className="w-4 h-4 text-primary" />
                <h3 className="text-sm font-semibold text-text">Background Image</h3>
              </div>
              <div className="flex items-center gap-2">
                <label className="flex-1 flex items-center justify-center gap-2 px-3 py-2 border border-dashed border-border rounded cursor-pointer hover:bg-surface-raised transition-colors text-sm text-text-muted">
                  <ImageIcon className="w-4 h-4" />
                  {bgImage ? 'Change image...' : 'Upload image...'}
                  <input type="file" accept="image/*" onChange={handleBgUpload} className="hidden" />
                </label>
                {bgImage && (
                  <Button variant="ghost" size="sm" onClick={() => onBgImageChange(null)} className="text-text-muted">
                    Remove
                  </Button>
                )}
              </div>
            </section>

            {/* Hardware Profile */}
            <section>
              <div className="flex items-center gap-2 mb-4">
                <Cpu className="w-4 h-4 text-primary" />
                <h3 className="text-sm font-semibold text-text">Resource Limits</h3>
              </div>
              <div className="space-y-4">
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-text-subtle">Max Active Projects</label>
                  <Select
                    value={String(maxActiveProjects)}
                    onChange={(e) => {
                      const val = e.target.value
                      onMaxActiveProjectsChange(val === 'infinite' ? 'infinite' : parseInt(val))
                    }}
                    aria-label="Max Active Projects"
                    size="sm"
                    options={[
                      { value: '1', label: '1 (Conservative)' },
                      { value: '2', label: '2' },
                      { value: '3', label: '3 (Standard)' },
                      { value: '4', label: '4' },
                      { value: '5', label: '5' },
                      { value: 'infinite', label: 'Infinite (Uncapped)' },
                    ]}
                  />
                  <p className="text-[10px] text-text-muted leading-relaxed">
                    Limit how many projects can be active simultaneously. Applies to Pro+ tiers. Inactive projects can be browsed but will not auto-sync or run background LLM pipelines.
                  </p>
                </div>
              </div>
            </section>

            <section>
              <div className="flex items-center gap-2 mb-4">
                <Cpu className="w-4 h-4 text-primary" />
                <h3 className="text-sm font-semibold text-text">Hardware Profile</h3>
                <a
                  href="https://docs.codrag.io/guides/hardware-profiles"
                  target="_blank"
                  rel="noreferrer"
                  className="ml-auto flex items-center gap-1 text-[10px] text-primary hover:underline"
                  title="Learn more about hardware profiles and concurrency"
                >
                  <Info className="w-3 h-3" />
                  Learn more <ExternalLink className="w-2.5 h-2.5" />
                </a>
              </div>
              <p className="text-[10px] text-text-muted leading-relaxed mb-3">
                Select your inference hardware. CoDRAG auto-tunes pipeline concurrency based on your hardware type.
              </p>
              <div className="space-y-3">
                <Select
                  value={detectProfile(concurrencyFast, concurrencyCode, concurrencyDeep, forceCustomProfile)}
                  onChange={(e) => {
                    const profile = e.target.value
                    if (profile === 'custom') {
                      setForceCustomProfile(true)
                      return
                    }
                    setForceCustomProfile(false)
                    const c = HARDWARE_CONCURRENCY[profile] ?? HARDWARE_CONCURRENCY.apple_silicon
                    handleConcurrencyFastChange(c.fast)
                    handleConcurrencyCodeChange(c.code)
                    handleConcurrencyDeepChange(c.deep)
                  }}
                  aria-label="Hardware Profile"
                  size="sm"
                  options={HARDWARE_PROFILE_OPTIONS}
                />
                {concurrencySaving && (
                  <span className="text-[10px] text-text-muted animate-pulse block">Saving...</span>
                )}

                {/* Custom concurrency controls */}
                {detectProfile(concurrencyFast, concurrencyCode, concurrencyDeep, forceCustomProfile) === 'custom' && (
                  <div className="space-y-2 p-3 rounded border border-border bg-surface-raised">
                    <p className="text-[10px] font-medium text-text">Custom Concurrency</p>
                    <div className="grid grid-cols-3 gap-3">
                      <div className="space-y-1">
                        <label className="text-[10px] font-medium text-text-muted">Fast Model</label>
                        <Select
                          value={String(concurrencyFast)}
                          onChange={(e) => handleConcurrencyFastChange(parseInt(e.target.value))}
                          aria-label="Fast Model Concurrency"
                          size="sm"
                          options={LLM_CONCURRENCY_OPTIONS}
                        />
                        <p className="text-[9px] text-text-muted">Stage 3: catalogue</p>
                      </div>
                      <div className="space-y-1">
                        <label className="text-[10px] font-medium text-text-muted">Coder Model</label>
                        <Select
                          value={String(concurrencyCode)}
                          onChange={(e) => handleConcurrencyCodeChange(parseInt(e.target.value))}
                          aria-label="Coder Model Concurrency"
                          size="sm"
                          options={LLM_CONCURRENCY_OPTIONS}
                        />
                        <p className="text-[9px] text-text-muted">Stage 2: edges</p>
                      </div>
                      <div className="space-y-1">
                        <label className="text-[10px] font-medium text-text-muted">Deep Model</label>
                        <Select
                          value={String(concurrencyDeep)}
                          onChange={(e) => handleConcurrencyDeepChange(parseInt(e.target.value))}
                          aria-label="Deep Model Concurrency"
                          size="sm"
                          options={LLM_CONCURRENCY_OPTIONS}
                        />
                        <p className="text-[9px] text-text-muted">Stages 6-9: deep</p>
                      </div>
                    </div>
                    <div className="text-[9px] text-text-muted leading-relaxed mt-1">
                      Set <code className="text-primary">OLLAMA_NUM_PARALLEL</code> in Ollama to at least the highest value above.
                      Each parallel slot uses additional VRAM for KV cache.
                    </div>
                  </div>
                )}

                {/* Info box for preset profiles */}
                {detectProfile(concurrencyFast, concurrencyCode, concurrencyDeep, forceCustomProfile) !== 'custom' && (
                  <div className="text-[10px] text-text-muted bg-surface-raised p-2 rounded border border-border leading-relaxed">
                    {detectProfile(concurrencyFast, concurrencyCode, concurrencyDeep, forceCustomProfile) === 'apple_silicon' ? (
                      <><strong className="text-text">Apple Silicon:</strong> Concurrency locked to 1. Unified memory means parallel requests compete for the same bandwidth — sequential is fastest.</>
                    ) : detectProfile(concurrencyFast, concurrencyCode, concurrencyDeep, forceCustomProfile) === 'cloud' ? (
                      <><strong className="text-text">Cloud API:</strong> High concurrency (3-5) for network-bound requests. Ensure your API rate limits support this.</>
                    ) : (
                      <><strong className="text-text">NVIDIA GPU:</strong> Concurrency scaled to VRAM. Set <code className="text-primary">OLLAMA_NUM_PARALLEL</code> in Ollama to at least the same value.</>
                    )}
                  </div>
                )}
              </div>
            </section>

            {/* License Key */}
            <section>
              <div className="flex items-center gap-2 mb-4">
                <Shield className="w-4 h-4 text-primary" />
                <h3 className="text-sm font-semibold text-text">License</h3>
              </div>
              <div className="space-y-3">
                {licenseStatus && (
                  <div className="flex items-center gap-2 text-xs p-2 rounded bg-surface-raised border border-border">
                    <Shield className="w-3.5 h-3.5 text-primary" />
                    <span className="font-medium text-text capitalize">{licenseStatus.license.tier} Plan</span>
                    {licenseStatus.license.valid && (
                      <span className="text-success text-[10px] bg-success/10 px-1.5 py-0.5 rounded ml-auto">Active</span>
                    )}
                  </div>
                )}
                
                {devTierOverride && (
                  <div className="text-xs text-warning bg-warning/10 px-2 py-1 rounded border border-warning/20">
                    Dev override active: <strong className="capitalize">{devTierOverride}</strong> tier
                  </div>
                )}

                <div className="flex gap-2">
                  <input
                    type="text"
                    value={licenseKeyInput}
                    onChange={(e) => onLicenseKeyInputChange(e.target.value)}
                    placeholder="Enter license key..."
                    className="flex-1 text-xs px-3 py-1.5 rounded border border-border bg-background text-text placeholder:text-text-muted focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                  <Button
                    variant="default"
                    size="sm"
                    onClick={onActivateLicense}
                    disabled={!licenseKeyInput.trim() || licenseLoading}
                  >
                    {licenseLoading ? 'Activating...' : 'Activate'}
                  </Button>
                </div>

                {licenseStatus?.license.tier !== 'free' && !devTierOverride && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={onDeactivateLicense}
                    disabled={licenseLoading}
                    className="w-full text-text-muted hover:text-error hover:bg-error/10"
                  >
                    Deactivate License
                  </Button>
                )}

                {licenseError && (
                  <p className="text-xs text-error">{licenseError}</p>
                )}
                
                <p className="text-xs text-text-muted">
                  Purchase a license at <a href="https://codrag.io/pricing" target="_blank" rel="noreferrer" className="text-primary underline">codrag.io/pricing</a>.
                </p>
              </div>
            </section>
          </>
        )}

        {/* ── Advanced tab ── */}
        {activeTab === 'advanced' && (
          <AdvancedSettingsPanel
            projectConfig={projectConfig}
            onProjectConfigChange={onProjectConfigChange}
            onSaveConfig={onSaveConfig}
            configDirty={configDirty}
            hasProject={hasProject}
          />
        )}

        {/* ── Developer tab ── */}
        {activeTab === 'developer' && (
          <>
            <section>
              <div className="flex items-center gap-2 mb-4">
                <Key className="w-4 h-4 text-primary" />
                <h3 className="text-sm font-semibold text-text">Tier Override</h3>
              </div>
              <div className="grid grid-cols-1 gap-3">
                <p className="text-xs text-text-muted">
                  Override the license tier for local development and testing.
                </p>
                <div className="flex items-center gap-2">
                  <Select
                    value={devTierOverride ?? ''}
                    onChange={(e) => {
                      const val = e.target.value
                      onDevTierOverrideChange(val ? val as LicenseTier : null)
                    }}
                    aria-label="Dev Tier Override"
                    size="sm"
                    options={DEV_TIER_OPTIONS}
                    className="flex-1"
                  />
                </div>
                {devTierOverride && (
                  <div className="p-3 rounded border border-warning/30 bg-warning/5">
                    <p className="text-xs text-warning font-medium">⚠ Development Mode Active</p>
                    <p className="text-xs text-text-muted mt-1">
                      Simulating <strong className="capitalize text-text">{devTierOverride}</strong> tier.
                    </p>
                  </div>
                )}
              </div>
            </section>

            <section>
              <div className="flex items-center gap-2 mb-4">
                <ClipboardCheck className="w-4 h-4 text-primary" />
                <h3 className="text-sm font-semibold text-text">License Details</h3>
              </div>
              <div className="text-xs font-mono bg-background p-3 rounded border border-border space-y-1.5">
                <div className="grid grid-cols-[80px_1fr] gap-x-2">
                  <strong className="text-text">Tier:</strong> 
                  <span className="text-text-muted capitalize">{licenseStatus?.license.tier ?? 'unknown'}</span>
                  
                  <strong className="text-text">Valid:</strong> 
                  <span className="text-text-muted">{licenseStatus?.license.valid ? 'Yes' : 'No'}</span>
                  
                  <strong className="text-text">Override:</strong> 
                  <span className="text-text-muted">{devTierOverride ?? 'None'}</span>
                  
                  <strong className="text-text">Effective:</strong> 
                  <span className="text-primary capitalize">{devTierOverride ?? licenseStatus?.license.tier ?? 'free'}</span>
                  
                  {licenseStatus?.license.email && (
                    <>
                      <strong className="text-text">Email:</strong> 
                      <span className="text-text-muted truncate">{licenseStatus.license.email}</span>
                    </>
                  )}
                </div>
              </div>
            </section>

            {/* Connection Debugger */}
            <section>
              <div className="flex items-center gap-2 mb-4">
                <Activity className="w-4 h-4 text-primary" />
                <h3 className="text-sm font-semibold text-text">Connection Debugger</h3>
              </div>
              <div className="space-y-3">
                <Button variant="outline" size="sm" onClick={runHealthTest} className="w-full">
                  Test /health Endpoint
                </Button>
                <div className="bg-background p-3 rounded border border-border font-mono text-xs">
                  <pre className="whitespace-pre-wrap break-all text-text">{healthResult}</pre>
                </div>
                <div className="grid grid-cols-[60px_1fr] gap-x-2 text-xs text-text-muted">
                  <strong className="text-text">Origin:</strong> {window.location.origin}
                  {/* @ts-ignore */}
                  <strong className="text-text">API:</strong> {api.baseUrl || '(hidden)'}
                </div>
              </div>
            </section>
          </>
        )}
      </div>

      {/* ── Confirmation Dialog (portals to body) ── */}
      <ConfirmDialog
        open={confirmAction !== null}
        onConfirm={handleConfirmedAction}
        onCancel={() => setConfirmAction(null)}
        title={confirmAction === 'graph' ? 'Reset Graph?' : 'Full Reset?'}
        description={
          confirmAction === 'graph'
            ? 'This will permanently delete the trace graph, all augmentation, epistemic enrichment, and cluster data. Embeddings and search will remain intact.'
            : 'This will permanently delete ALL project data: embeddings, search index, trace graph, and all enrichment. You will need to rebuild everything from scratch.'
        }
        confirmLabel={confirmAction === 'graph' ? 'Reset Graph' : 'Reset Everything'}
      />
    </div>
  )
}
