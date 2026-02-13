import { useState } from 'react'
import { Settings, X, ImageIcon, Key, Shield, Trash2 } from 'lucide-react'
import {
  useApiClient,
  Button,
  Select,
  ProjectSettingsPanel,
  DeepAnalysisSettings,
  type ProjectConfig,
  type LicenseStatus,
  type LicenseTier,
  type DeepAnalysisSchedule,
  type DeepAnalysisRunStatus,
} from '@codrag/ui'

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
  { value: 'starter', label: 'Starter' },
  { value: 'pro', label: 'Pro' },
  { value: 'team', label: 'Team' },
  { value: 'enterprise', label: 'Enterprise' },
]

// ── Settings Panel (drawer) ──────────────────────────────────
type SettingsDrawerTab = 'project' | 'global' | 'developer'

export interface SettingsDrawerProps {
  open: boolean
  onClose: () => void
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
  deepAnalysisStatus: DeepAnalysisRunStatus
  deepAnalysisRunning: boolean
  onRunDeepAnalysis: () => void
  onCancelDeepAnalysis: () => void
  largeModelConfigured: boolean
  fastModelConfigured: boolean
  // Global tab
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
  projectConfig,
  onProjectConfigChange,
  onSaveConfig,
  configDirty,
  hasProject,
  onDetectStack,
  deepAnalysisSchedule,
  onDeepAnalysisScheduleChange,
  deepAnalysisStatus,
  deepAnalysisRunning,
  onRunDeepAnalysis,
  onCancelDeepAnalysis,
  largeModelConfigured,
  fastModelConfigured,
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
}: SettingsDrawerProps) {
  const api = useApiClient()
  const [activeTab, setActiveTab] = useState<SettingsDrawerTab>('project')
  const [healthResult, setHealthResult] = useState<string>('No test run yet')

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
    { key: 'developer', label: 'Developer' },
  ]

  return (
    <div className="fixed inset-y-0 right-0 z-50 w-96 bg-surface border-l border-border shadow-lg flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <h2 className="text-sm font-semibold text-text flex items-center gap-2">
          <Settings className="w-4 h-4" />
          Settings
        </h2>
        <Button variant="ghost" size="icon-sm" onClick={onClose} aria-label="Close">
          <X className="w-4 h-4" />
        </Button>
      </div>

      {/* Tab bar */}
      <div className="flex border-b border-border shrink-0 px-4">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setActiveTab(t.key)}
            className={`px-3 py-2 text-xs font-medium border-b-2 -mb-px transition-colors ${
              activeTab === t.key
                ? 'border-primary text-text'
                : 'border-transparent text-text-muted hover:text-text'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-6">
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
            <div className="border-t border-border pt-4">
              <DeepAnalysisSettings
                schedule={deepAnalysisSchedule}
                onScheduleChange={onDeepAnalysisScheduleChange}
                largeModelConfigured={largeModelConfigured}
                fastModelConfigured={fastModelConfigured}
                status={deepAnalysisStatus}
                running={deepAnalysisRunning}
                onRunNow={onRunDeepAnalysis}
                onCancel={onCancelDeepAnalysis}
              />
            </div>
            <div className="border-t border-border pt-4">
              <section>
                <h3 className="text-xs font-medium text-error uppercase tracking-wide mb-2 flex items-center gap-1.5">
                  <Trash2 className="w-3.5 h-3.5" />
                  Danger Zone
                </h3>
                <p className="text-xs text-text-muted mb-3">
                  These actions permanently delete project data and cannot be undone.
                </p>
                <div className="space-y-2">
                  <div className="p-2 rounded border border-border bg-surface-raised">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-xs font-medium text-text">Reset Graph</p>
                        <p className="text-xs text-text-muted">Deletes trace graph and all enrichment data. Embeddings and search remain intact.</p>
                      </div>
                      <Button variant="destructive" size="sm" onClick={onDestroyGraph}>
                        Reset
                      </Button>
                    </div>
                  </div>
                  <div className="p-2 rounded border border-error/30 bg-error/5">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-xs font-medium text-text">Full Reset</p>
                        <p className="text-xs text-text-muted">Deletes everything: embeddings, search index, graph, and all enrichment. You will need to rebuild from scratch.</p>
                      </div>
                      <Button variant="destructive" size="sm" onClick={onDestroyIndex}>
                        Reset All
                      </Button>
                    </div>
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
              <h3 className="text-xs font-medium text-text-muted uppercase tracking-wide mb-2 flex items-center gap-1.5">
                Appearance
              </h3>
              <div className="space-y-2">
                <Select
                  value={uiMode}
                  onChange={(e) => onModeChange(e.target.value as 'light' | 'dark')}
                  aria-label="Color Mode"
                  size="sm"
                  options={MODE_OPTIONS}
                />
                <Select
                  value={uiTheme}
                  onChange={(e) => onThemeChange(e.target.value)}
                  aria-label="Visual Theme"
                  size="sm"
                  options={THEME_OPTIONS}
                />
              </div>
            </section>

            {/* Background Image */}
            <section>
              <h3 className="text-xs font-medium text-text-muted uppercase tracking-wide mb-2">Background Image</h3>
              <div className="space-y-2">
                <label className="flex items-center gap-2 px-3 py-2 border border-dashed border-border rounded cursor-pointer hover:bg-surface-raised transition-colors text-sm text-text-muted">
                  <ImageIcon className="w-4 h-4" />
                  {bgImage ? 'Change image...' : 'Upload image...'}
                  <input type="file" accept="image/*" onChange={handleBgUpload} className="hidden" />
                </label>
                {bgImage && (
                  <Button variant="ghost" size="sm" onClick={() => onBgImageChange(null)} className="w-full text-text-muted">
                    Remove background
                  </Button>
                )}
              </div>
            </section>

            {/* License Key */}
            <section>
              <h3 className="text-xs font-medium text-text-muted uppercase tracking-wide mb-2">License</h3>
              <div className="space-y-2">
                {licenseStatus && (
                  <div className="flex items-center gap-2 text-xs">
                    <Shield className="w-3.5 h-3.5 text-primary" />
                    <span className="font-medium text-text capitalize">{licenseStatus.license.tier}</span>
                    {licenseStatus.license.valid && (
                      <span className="text-success text-[10px] bg-success/10 px-1.5 py-0.5 rounded">Active</span>
                    )}
                    {licenseStatus.license.email && (
                      <span className="text-text-muted ml-auto truncate">{licenseStatus.license.email}</span>
                    )}
                  </div>
                )}
                {devTierOverride && (
                  <div className="text-xs text-warning bg-warning/10 px-2 py-1 rounded">
                    Dev override active: <strong className="capitalize">{devTierOverride}</strong> tier
                  </div>
                )}
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={licenseKeyInput}
                    onChange={(e) => onLicenseKeyInputChange(e.target.value)}
                    placeholder="Enter license key..."
                    className="flex-1 text-xs px-2 py-1.5 rounded border border-border bg-background text-text placeholder:text-text-muted focus:outline-none focus:ring-1 focus:ring-primary"
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
                    className="w-full text-text-muted"
                  >
                    Deactivate License
                  </Button>
                )}
                {licenseError && (
                  <p className="text-xs text-error">{licenseError}</p>
                )}
                <p className="text-xs text-text-muted">
                  Purchase a license at <a href="https://codrag.io/pricing" target="_blank" rel="noreferrer" className="text-primary underline">codrag.io/pricing</a>.
                  Keys are validated via Lemon Squeezy.
                </p>
              </div>
            </section>

          </>
        )}

        {/* ── Developer tab ── */}
        {activeTab === 'developer' && (
          <>
            <section>
              <h3 className="text-xs font-medium text-text-muted uppercase tracking-wide mb-2 flex items-center gap-1.5">
                <Key className="w-3.5 h-3.5" />
                Tier Override
              </h3>
              <p className="text-xs text-text-muted mb-3">
                Override the license tier for local development and testing.
                This bypasses real license validation.
              </p>
              <Select
                value={devTierOverride ?? ''}
                onChange={(e) => {
                  const val = e.target.value
                  onDevTierOverrideChange(val ? val as LicenseTier : null)
                }}
                aria-label="Dev Tier Override"
                size="sm"
                options={DEV_TIER_OPTIONS}
              />
              {devTierOverride && (
                <div className="mt-3 p-2 rounded border border-warning/30 bg-warning/5">
                  <p className="text-xs text-warning font-medium">⚠ Development Mode</p>
                  <p className="text-xs text-text-muted mt-1">
                    The app is simulating <strong className="capitalize text-text">{devTierOverride}</strong> tier.
                    Feature gates, project limits, and UI will behave as if this tier is active.
                    This does not affect the backend license file.
                  </p>
                </div>
              )}
            </section>

            <section>
              <h3 className="text-xs font-medium text-text-muted uppercase tracking-wide mb-2">Current License State</h3>
              <div className="text-xs font-mono bg-background p-2 rounded border border-border space-y-1">
                <p><strong className="text-text">Tier:</strong> <span className="text-text-muted capitalize">{licenseStatus?.license.tier ?? 'unknown'}</span></p>
                <p><strong className="text-text">Valid:</strong> <span className="text-text-muted">{licenseStatus?.license.valid ? 'Yes' : 'No'}</span></p>
                <p><strong className="text-text">Override:</strong> <span className="text-text-muted">{devTierOverride ?? 'None'}</span></p>
                <p><strong className="text-text">Effective:</strong> <span className="text-primary capitalize">{devTierOverride ?? licenseStatus?.license.tier ?? 'free'}</span></p>
                {licenseStatus?.license.email && (
                  <p><strong className="text-text">Email:</strong> <span className="text-text-muted">{licenseStatus.license.email}</span></p>
                )}
                {licenseStatus?.license.expires_at && (
                  <p><strong className="text-text">Expires:</strong> <span className="text-text-muted">{licenseStatus.license.expires_at}</span></p>
                )}
              </div>
            </section>

            {/* Connection Debugger */}
            <section>
              <h3 className="text-xs font-medium text-text-muted uppercase tracking-wide mb-2">Connection Debugger</h3>
              <div className="space-y-2 text-xs font-mono">
                <Button variant="outline" size="sm" onClick={runHealthTest} className="w-full">
                  Test /health
                </Button>
                <div className="bg-background p-2 rounded border border-border">
                  <pre className="whitespace-pre-wrap break-all text-text">{healthResult}</pre>
                </div>
                <div className="space-y-1 text-text-muted">
                  <p><strong className="text-text">Origin:</strong> {window.location.origin}</p>
                  {/* @ts-ignore */}
                  <p><strong className="text-text">API URL:</strong> {api.baseUrl || '(hidden)'}</p>
                  <p><strong className="text-text">UA:</strong> {navigator.userAgent.slice(0, 60)}...</p>
                </div>
              </div>
            </section>
          </>
        )}
      </div>
    </div>
  )
}
