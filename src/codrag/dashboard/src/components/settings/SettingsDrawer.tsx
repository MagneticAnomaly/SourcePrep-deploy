import { useState, useCallback, useEffect } from 'react'
import { Settings, X, ImageIcon, Key, Shield, Trash2, Palette, Activity, ClipboardCheck, Cpu } from 'lucide-react'
import {
  useApiClient,
  Button,
  ConfirmDialog,
  Select,
  Toggle,
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
  projectName?: string
  onDestroyGraph: () => void
  onDestroyIndex: () => void
  // Developer tab – selective resets
  onDestroyAtlas?: () => void
  onDestroyGroupReasoning?: () => void
  onDestroyDeepEnrichment?: () => void
  // Global config for debug mode
  globalConfig?: { developer_debug_mode?: boolean }
  onGlobalConfigChange?: (config: Partial<{ developer_debug_mode?: boolean }>) => void
  // Developer tab
  devTierOverride: LicenseTier | null
  onDevTierOverrideChange: (tier: LicenseTier | null) => void
  devRoleOverride: import('@codrag/ui').UserRole | null
  onDevRoleOverrideChange: (role: import('@codrag/ui').UserRole | null) => void
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
  maxActiveProjects: _maxActiveProjects,
  onMaxActiveProjectsChange: _onMaxActiveProjectsChange,
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
  projectName,
  onDestroyGraph,
  onDestroyIndex,
  onDestroyAtlas,
  onDestroyGroupReasoning,
  onDestroyDeepEnrichment,
  globalConfig,
  onGlobalConfigChange,
  devTierOverride,
  onDevTierOverrideChange,
  devRoleOverride,
  onDevRoleOverrideChange,
  scrollToDeepAnalysis,
}: SettingsDrawerProps) {
  const api = useApiClient()
  const [activeTab, setActiveTab] = useState<SettingsDrawerTab>('project')
  const [healthResult, setHealthResult] = useState<string>('No test run yet')

  useEffect(() => {
    if (open && openToTab) setActiveTab(openToTab)
  }, [open, openToTab])

  // Pipeline config (concurrency) now lives in AI Gateway, not here


  useEffect(() => {
    if (open && scrollToDeepAnalysis) {
      setTimeout(() => {
        document.getElementById('settings-deep-analysis')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }, 100)
    }
  }, [open, scrollToDeepAnalysis])
  const [confirmAction, setConfirmAction] = useState<'graph' | 'index' | 'atlas' | 'group_reasoning' | 'deep_enrichment' | null>(null)

  const handleConfirmedAction = useCallback(() => {
    if (confirmAction === 'graph') onDestroyGraph()
    if (confirmAction === 'index') onDestroyIndex()
    if (confirmAction === 'atlas') onDestroyAtlas?.()
    if (confirmAction === 'group_reasoning') onDestroyGroupReasoning?.()
    if (confirmAction === 'deep_enrichment') onDestroyDeepEnrichment?.()
    setConfirmAction(null)
  }, [confirmAction, onDestroyGraph, onDestroyIndex, onDestroyAtlas, onDestroyGroupReasoning, onDestroyDeepEnrichment])

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

            {/* AI Gateway shortcut — resource limits + hardware profile live in AI Gateway now */}
            <section>
              <div className="flex items-center gap-2 mb-4">
                <Cpu className="w-4 h-4 text-primary" />
                <h3 className="text-sm font-semibold text-text">AI Gateway</h3>
              </div>
              <p className="text-[10px] text-text-muted leading-relaxed mb-3">
                Manage AI models, endpoints, compute resources, and concurrency settings.
              </p>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => {
                  onClose()
                  // Open the AI Models panel — the parent component handles this
                  window.dispatchEvent(new CustomEvent('codrag:open-ai-gateway'))
                }}
                className="w-full"
              >
                <Cpu className="w-3.5 h-3.5 mr-1.5" />
                Open AI Gateway
              </Button>
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
                <div className="w-4 h-4 text-primary"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m8 2 1.88 1.88"/><path d="M14.12 3.88 16 2"/><path d="M9 7.13v-1a3.003 3.003 0 1 1 6 0v1"/><path d="M12 20c-3.3 0-6-2.7-6-6v-3a4 4 0 0 1 4-4h4a4 4 0 0 1 4 4v3c0 3.3-2.7 6-6 6"/><path d="M12 20v-9"/><path d="M6.53 9C4.6 8.8 3 7.1 3 5"/><path d="M17.47 9c1.93-.2 3.53-1.9 3.53-4"/></svg></div>
                <h3 className="text-sm font-semibold text-text">Debug Tools</h3>
              </div>
              
              <div className="grid grid-cols-1 gap-3">
                <div className="flex items-center justify-between p-3 rounded bg-bg-surface border border-border">
                  <div>
                    <h4 className="text-sm font-medium text-text">Verbose Telemetry</h4>
                    <p className="text-xs text-text-muted mt-1">
                      Log deep LLM analytics, raw prompts, and response timings to stdout for local testing.
                    </p>
                  </div>
                  <Toggle
                    checked={globalConfig?.developer_debug_mode ?? false}
                    onChange={(val: boolean) => {
                      onGlobalConfigChange?.({ developer_debug_mode: val })
                    }}
                  />
                </div>
              </div>
            </section>

            <section>
              <div className="flex items-center gap-2 mb-4 mt-6">
                <Key className="w-4 h-4 text-primary" />
                <h3 className="text-sm font-semibold text-text">Tier Override</h3>
              </div>
              <div className="grid grid-cols-1 gap-3">
                <p className="text-xs text-text-muted">
                  Override the license tier and role for local development and testing.
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
                <label className="text-xs font-medium text-text-subtle mt-2">Role Override</label>
                <div className="flex items-center gap-2">
                  <Select
                    value={devRoleOverride ?? ''}
                    onChange={(e) => {
                      const val = e.target.value
                      onDevRoleOverrideChange(val ? val as any : null)
                    }}
                    aria-label="Dev Role Override"
                    size="sm"
                    options={[
                      { value: '', label: 'Default (user)' },
                      { value: 'user', label: 'User' },
                      { value: 'admin', label: 'IT Admin' },
                    ]}
                    className="flex-1"
                  />
                </div>
                {(devTierOverride || devRoleOverride) && (
                  <div className="p-3 rounded border border-warning/30 bg-warning/5">
                    <p className="text-xs text-warning font-medium">⚠ Development Mode Active</p>
                    <p className="text-xs text-text-muted mt-1">
                      Simulating <strong className="capitalize text-text">{devTierOverride || 'Free'}</strong> tier with <strong className="capitalize text-text">{devRoleOverride || 'User'}</strong> role.
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

            {/* Selective Reset — Developer Danger Zone */}
            <section>
              <div className="flex items-center gap-2 mb-4">
                <Trash2 className="w-4 h-4 text-error" />
                <h3 className="text-sm font-semibold text-error">Selective Reset</h3>
              </div>
              <p className="text-xs text-text-muted mb-3">
                Reset specific pipeline stages for the current project. Fast Sync stages are preserved.
              </p>
              <div className="grid grid-cols-3 gap-3">
                <div className="p-3 rounded border border-border bg-bg-surface text-center">
                  <h4 className="text-xs font-semibold text-text mb-1">Reset Atlas</h4>
                  <p className="text-[10px] text-text-muted mb-2">Deletes atlas and routing data only.</p>
                  <Button variant="outline" size="sm" onClick={() => setConfirmAction('atlas')} className="w-full text-xs">
                    Reset
                  </Button>
                </div>
                <div className="p-3 rounded border border-border bg-bg-surface text-center">
                  <h4 className="text-xs font-semibold text-text mb-1">Reset Group Reasoning</h4>
                  <p className="text-[10px] text-text-muted mb-2">Deletes group reasoning data only.</p>
                  <Button variant="outline" size="sm" onClick={() => setConfirmAction('group_reasoning')} className="w-full text-xs">
                    Reset
                  </Button>
                </div>
                <div className="p-3 rounded border border-error/40 bg-error/5 text-center">
                  <h4 className="text-xs font-semibold text-error mb-1">Reset Deep Enrichment</h4>
                  <p className="text-[10px] text-text-muted mb-2">Deletes all 6 deep stages.</p>
                  <Button variant="outline" size="sm" onClick={() => setConfirmAction('deep_enrichment')} className="w-full text-xs border-error/40 text-error hover:bg-error/10">
                    Reset All
                  </Button>
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
        title={
          confirmAction === 'graph' ? `Reset Graph for ${projectName || 'Project'}?`
          : confirmAction === 'atlas' ? `Reset Atlas for ${projectName || 'Project'}?`
          : confirmAction === 'group_reasoning' ? `Reset Group Reasoning for ${projectName || 'Project'}?`
          : confirmAction === 'deep_enrichment' ? `Reset Deep Enrichment for ${projectName || 'Project'}?`
          : `Full Reset for ${projectName || 'Project'}?`
        }
        description={
          confirmAction === 'graph'
            ? 'This will permanently delete the trace graph, all augmentation, epistemic enrichment, and cluster data. Embeddings and search will remain intact.'
            : confirmAction === 'atlas'
            ? 'This will permanently delete the atlas and routing data for this project. Other enrichment stages will remain intact.'
            : confirmAction === 'group_reasoning'
            ? 'This will permanently delete the group reasoning data for this project. Other enrichment stages will remain intact.'
            : confirmAction === 'deep_enrichment'
            ? 'This will permanently delete ALL deep enrichment data (epistemic, group reasoning, modules, atlas, deepening, knowledge embeddings). Fast Sync stages (graph, augmentation, inferred edges) will remain intact.'
            : 'This will permanently delete ALL project data: embeddings, search index, trace graph, and all enrichment. You will need to rebuild everything from scratch.'
        }
        confirmLabel={
          confirmAction === 'graph' ? 'Reset Graph'
          : confirmAction === 'atlas' ? 'Reset Atlas'
          : confirmAction === 'group_reasoning' ? 'Reset Group Reasoning'
          : confirmAction === 'deep_enrichment' ? 'Reset Deep Enrichment'
          : 'Reset Everything'
        }
      />
    </div>
  )
}
