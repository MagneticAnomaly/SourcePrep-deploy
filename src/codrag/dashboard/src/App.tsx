import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import { RefreshCw, FileText, Settings, X, ImageIcon, AlertCircle } from 'lucide-react'
import {
  // API
  useApiClient,
  type ProjectListItem,
  // Navigation
  AppShell,
  Sidebar,
  ProjectList,
  // Dashboard
  IndexStatusCard,
  SearchPanel,
  UsageGuidePanel,
  ContextOptionsPanel,
  SearchResultsList,
  ChunkPreview,
  ContextOutput,
  ProjectSettingsPanel,
  ModularDashboard,
  LLMStatusWidget,
  AIModelsSettings,
  DeepAnalysisSettings,
  type DeepAnalysisSchedule,
  type DeepAnalysisRunStatus,
  CopyButton,
  // Project
  AddProjectModal,
  FolderTreePanel,
  FileExplorerDetail,
  // Trace
  TraceExplorer,
  TraceCoveragePanel,
  TracePipelineStatus,
  type AugmentationStatus,
  type LLMSlotsStatus,
  type PinnedTextFile,
  // Watch
  WatchControlPanel,
  // Patterns
  LoadingState,
  EmptyState,
  // Primitives
  Button,
  Select,
  // Types
  type SearchResult,
  type ContextMeta,
  type ProjectConfig,
  type ProjectSummary,
  type ProjectStatus,
  type StatusState,
  type TreeNode,
  type LLMConfig,
  type SavedEndpoint,
  type EndpointTestResult,
  type WatchStatus,
  type ProjectMode,
  type DashboardLayoutApi,
  type DashboardLayout,
  type PanelDefinition,
  // Layout
  PanelPicker,
  LogConsole,
  useEventStream,
  PANEL_REGISTRY,
} from '@codrag/ui'
import { StartupScreen } from './components/StartupScreen'
import 'react-grid-layout/css/styles.css'
import 'react-resizable/css/styles.css'

// ── Constants ────────────────────────────────────────────────

const PINNED_PREFIX = 'pinned:'

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

// ── Helpers ──────────────────────────────────────────────────

function deriveStatus(ps: ProjectStatus | null, building: boolean): StatusState {
  if (building) return 'building'
  if (!ps) return 'pending'
  if (ps.building) return 'building'
  if (ps.stale) return 'stale'
  if (ps.index.exists) return 'fresh'
  return 'pending'
}

/** Recursively collect paths of files that are indexed or pending in the tree. */
function collectIndexedPaths(nodes: TreeNode[], prefix = ''): string[] {
  const result: string[] = []
  for (const node of nodes) {
    const p = prefix ? `${prefix}/${node.name}` : node.name
    if (node.type === 'file' && (node.status === 'indexed' || node.status === 'pending')) {
      result.push(p)
    }
    if (node.children) result.push(...collectIndexedPaths(node.children, p))
  }
  return result
}

function toProjectSummary(p: ProjectListItem, ps: ProjectStatus | null, building: boolean): ProjectSummary {
  return {
    id: p.id,
    name: p.name,
    path: p.path,
    mode: p.mode ?? 'standalone',
    status: deriveStatus(ps, building),
    chunk_count: ps?.index.total_chunks,
    last_build_at: ps?.index.last_build_at ?? undefined,
  }
}

// ── Settings Panel (drawer) ──────────────────────────────────
type SettingsDrawerTab = 'project' | 'global'

interface SettingsDrawerProps {
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
  // Global tab
  uiMode: 'light' | 'dark'
  onModeChange: (mode: 'light' | 'dark') => void
  uiTheme: string
  onThemeChange: (theme: string) => void
  bgImage: string | null
  onBgImageChange: (url: string | null) => void
}

function SettingsDrawer({
  open,
  onClose,
  projectConfig,
  onProjectConfigChange,
  onSaveConfig,
  configDirty,
  hasProject,
  onDetectStack,
  uiMode,
  onModeChange,
  uiTheme,
  onThemeChange,
  bgImage,
  onBgImageChange,
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
          <ProjectSettingsPanel
            config={projectConfig}
            onChange={onProjectConfigChange}
            onSave={onSaveConfig}
            onDetectStack={onDetectStack}
            isDirty={configDirty}
            bare
          />
        )}
        {activeTab === 'project' && !hasProject && (
          <p className="text-sm text-text-muted">Select a project to configure settings.</p>
        )}

        {/* ── Global tab ── */}
        {activeTab === 'global' && (
          <>
            {/* Appearance */}
            <section>
              <h3 className="text-xs font-medium text-text-muted uppercase tracking-wide mb-2">Appearance</h3>
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

// ── App ──────────────────────────────────────────────────────

function App() {
  const api = useApiClient()

  // ── Connection state ───────────────────────────────────────
  const [isConnected, setIsConnected] = useState(false)
  const [isDaemonUnhealthy, setIsDaemonUnhealthy] = useState(false)

  // Initial connection & health polling
  useEffect(() => {
    let interval: NodeJS.Timeout

    const checkHealth = async () => {
      try {
        await api.getHealth()
        if (!isConnected) setIsConnected(true)
        setIsDaemonUnhealthy(false)
      } catch {
        if (isConnected) setIsDaemonUnhealthy(true)
      }
    }

    // Start polling once connected (StartupScreen handles the initial wait)
    if (isConnected) {
      interval = setInterval(checkHealth, 2000)
      checkHealth()
    }

    return () => clearInterval(interval)
  }, [api, isConnected])

  // ── Global state ───────────────────────────────────────────
  const [loading, setLoading] = useState(true)
  const [_error, setError] = useState<string | null>(null) // TODO: wire to error toast

  // ── Project list ───────────────────────────────────────────
  const [projects, setProjects] = useState<ProjectListItem[]>([])
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null)
  const [projectStatuses, setProjectStatuses] = useState<Record<string, ProjectStatus>>({})
  const [buildingProjects, setBuildingProjects] = useState<Set<string>>(new Set())
  const [addModalOpen, setAddModalOpen] = useState(false)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)

  // ── UI preferences ─────────────────────────────────────────
  const [uiMode, setUiMode] = useState<'light' | 'dark'>(() =>
    (localStorage.getItem('codrag_ui_mode') as 'light' | 'dark') ?? 'light'
  )
  const [uiTheme, setUiTheme] = useState<string>(() =>
    localStorage.getItem('codrag_ui_theme') ?? 'none'
  )
  const [devSettingsOpen, setDevSettingsOpen] = useState(false)
  const [bgImage, setBgImage] = useState<string | null>(() =>
    localStorage.getItem('codrag_bg_image') ?? null
  )
  const [dashboardLayout, setDashboardLayout] = useState<DashboardLayout | null>(null)

  // ── Search state ───────────────────────────────────────────
  const [query, setQuery] = useState<string>('')
  const [searchK, setSearchK] = useState<number>(8)
  const [minScore, setMinScore] = useState<number>(0.15)
  const [searchLoading, setSearchLoading] = useState(false)
  const [searchResults, setSearchResults] = useState<SearchResult[]>([])
  const [selectedChunk, setSelectedChunk] = useState<SearchResult | null>(null)

  // ── Context state ──────────────────────────────────────────
  const [contextK, setContextK] = useState<number>(5)
  const [contextMaxChars, setContextMaxChars] = useState<number>(6000)
  const [contextIncludeSources, setContextIncludeSources] = useState(true)
  const [contextIncludeScores, setContextIncludeScores] = useState(false)
  const [contextStructured, setContextStructured] = useState(false)
  const [context, setContext] = useState<string>('')
  const [contextMeta, setContextMeta] = useState<ContextMeta | null>(null)

  // ── File tree state ──────────────────────────────────────
  const [fileTree, setFileTree] = useState<TreeNode[]>([])

  // ── Index inclusion state (which files are included in the knowledge scope) ──
  const [includedPaths, setIncludedPaths] = useState<Set<string>>(() => {
    try {
      const stored = localStorage.getItem('codrag_included_paths')
      return stored ? new Set(JSON.parse(stored)) : new Set()
    } catch { return new Set() }
  })

  // ── Path weights state ────────────────────────────────────
  const [pathWeights, setPathWeights] = useState<Record<string, number>>({})

  // ── Pinned files state ──────────────────────────────────────
  const [pinnedPaths, setPinnedPaths] = useState<Set<string>>(() => {
    try {
      const stored = localStorage.getItem('codrag_pinned_files')
      return stored ? new Set(JSON.parse(stored)) : new Set()
    } catch { return new Set() }
  })
  const [pinnedFiles, setPinnedFiles] = useState<PinnedTextFile[]>([])
  const layoutApiRef = useRef<DashboardLayoutApi | null>(null)

  // ── Watch state ─────────────────────────────────────────────
  const [watchStatus, setWatchStatus] = useState<WatchStatus>({
    enabled: false,
    state: 'disabled',
    stale: false,
    pending: false,
  })
  const [watchLoading, setWatchLoading] = useState(false)

  // ── Settings state ─────────────────────────────────────────
  const [projectConfig, setProjectConfig] = useState<ProjectConfig>({
    include_globs: ['**/*.md', '**/*.py', '**/*.ts', '**/*.tsx', '**/*.js', '**/*.json'],
    exclude_globs: ['**/.git/**', '**/node_modules/**', '**/__pycache__/**', '**/.venv/**', '**/dist/**', '**/build/**', '**/.next/**'],
    max_file_bytes: 400_000,
    use_gitignore: true,
    trace: { enabled: false },
    auto_rebuild: { enabled: false, debounce_ms: 5000 },
  })
  const [configDirty, setConfigDirty] = useState(false)
  const [deepAnalysisSchedule, setDeepAnalysisSchedule] = useState<DeepAnalysisSchedule>({
    mode: 'manual',
    threshold_percent: 20,
    frequency: 'weekly',
    day_of_week: 0,
    hour: 2,
    budget_max_tokens: 50_000,
    budget_max_minutes: 30,
    budget_max_items: 100,
    priority: 'lowest_confidence',
  })
  const [deepAnalysisStatus, setDeepAnalysisStatus] = useState<DeepAnalysisRunStatus>({})
  const [deepAnalysisRunning, setDeepAnalysisRunning] = useState(false)
  const [augmentationStatus, setAugmentationStatus] = useState<AugmentationStatus>({
    enabled: false, total_nodes: 0, augmented_nodes: 0, validated_nodes: 0,
    avg_confidence: 0, low_confidence_count: 0,
  })
  const [augmenting, setAugmenting] = useState(false)
  const [llmSlotsStatus, setLlmSlotsStatus] = useState<LLMSlotsStatus | null>(null)

  // ── Trace state ───────────────────────────────────────────
  const [traceStatus, setTraceStatus] = useState<{ enabled: boolean; exists: boolean; building: boolean; counts: { nodes: number; edges: number } }>({
    enabled: false, exists: false, building: false, counts: { nodes: 0, edges: 0 },
  })

  // ── Trace coverage state ────────────────────────────────────
  const [traceCoverage, setTraceCoverage] = useState<{
    summary: { total: number; traced: number; untraced: number; stale: number; excluded: number; coverage_pct: number; last_build_at: string | null } | null;
    untraced: Array<{ path: string; language: string | null; size: number; modified: string; created: string }>;
    stale: Array<{ path: string; language: string | null; size: number; modified: string; created: string }>;
    excluded: Array<{ path: string; language: string | null; size: number; modified: string; created: string }>;
    building: boolean;
    loading: boolean;
  }>({ summary: null, untraced: [], stale: [], excluded: [], building: false, loading: false })

  // ── LLM config state ───────────────────────────────────────
  const [llmConfig, setLLMConfig] = useState<LLMConfig>({
    saved_endpoints: [
      { id: 'default_ollama', name: 'Default Ollama', provider: 'ollama', url: 'http://localhost:11434' },
    ],
    embedding: { source: 'endpoint', endpoint_id: 'default_ollama', model: 'nomic-embed-text' },
    small_model: { enabled: false },
    large_model: { enabled: false },
    clara: { enabled: false, source: 'huggingface', remote_url: undefined },
  })
  const [availableModels, setAvailableModels] = useState<Record<string, string[]>>({})
  const [loadingModels, setLoadingModels] = useState<Record<string, boolean>>({})
  const [testingSlot, setTestingSlot] = useState<'embedding' | 'small' | 'large' | 'clara' | null>(null)
  const [testResults, setTestResults] = useState<Record<string, EndpointTestResult>>({})

  // ── Event Stream ───────────────────────────────────────────
  // In dev mode, bypass Vite proxy (which buffers SSE) and connect directly to daemon
  const eventsUrl = import.meta.env.DEV
    ? `http://${window.location.hostname}:8400/events`
    : `${api.baseUrl}/events`;
  const { logs, tasks, clearLogs } = useEventStream(eventsUrl, 1000);

  // Helper to find relevant task for current project
  const findActiveTask = useCallback((type: 'index_build' | 'trace_build') => {
    if (!selectedProjectId) return undefined;
    const entry = Object.values(tasks).find(t => 
      t.task_id.startsWith(`${type}:${selectedProjectId}`) && 
      (t.status === 'running' || t.status === 'completed')
    );
    return entry;
  }, [tasks, selectedProjectId]);

  // ── Derived ────────────────────────────────────────────────
  const selectedProject = useMemo(
    () => projects.find((p) => p.id === selectedProjectId) ?? null,
    [projects, selectedProjectId],
  )
  const projectStatus = selectedProjectId ? projectStatuses[selectedProjectId] ?? null : null
  const isBuilding = selectedProjectId ? buildingProjects.has(selectedProjectId) : false

  const projectSummaries = useMemo(
    () => projects.map((p) => toProjectSummary(p, projectStatuses[p.id] ?? null, buildingProjects.has(p.id))),
    [projects, projectStatuses, buildingProjects],
  )

  // ── Data fetching ──────────────────────────────────────────

  const refreshProjects = useCallback(async () => {
    try {
      const data = await api.listProjects()
      setProjects(data.projects)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to list projects')
    }
  }, [api])

  const refreshStatus = useCallback(async (projectId: string) => {
    try {
      const status = await api.getProjectStatus(projectId)
      setProjectStatuses((prev) => ({ ...prev, [projectId]: status }))
      if (!status.building) {
        setBuildingProjects((prev) => {
          const next = new Set(prev)
          next.delete(projectId)
          return next
        })
      }
    } catch {
      // Silently ignore status errors for background polling
    }
  }, [api])

  // ── Actions ────────────────────────────────────────────────

  const handleAddProject = useCallback(async (path: string, name: string, mode: ProjectMode, indexPath?: string) => {
    try {
      const data = await api.createProject({ path, name, mode, ...(indexPath ? { index_path: indexPath } : {}) })
      setProjects((prev) => [...prev, data.project])
      setSelectedProjectId(data.project.id)
      setAddModalOpen(false)
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Failed to add project'
      setError(msg)
      throw e // Re-throw so modal can handle state
    }
  }, [api])

  const handleBuild = useCallback(async () => {
    if (!selectedProjectId) return
    try {
      setBuildingProjects((prev) => new Set(prev).add(selectedProjectId))
      await api.buildProject(selectedProjectId)
      // Poll status until build completes
      const poll = setInterval(async () => {
        const status = await api.getProjectStatus(selectedProjectId)
        setProjectStatuses((prev) => ({ ...prev, [selectedProjectId]: status }))
        if (!status.building) {
          clearInterval(poll)
          setBuildingProjects((prev) => {
            const next = new Set(prev)
            next.delete(selectedProjectId)
            return next
          })
          // Refresh file tree so Pending → Indexed
          api.getProjectFiles(selectedProjectId, '', 4).then((data) => {
            setFileTree(data.tree ?? [])
          }).catch(() => {})
        }
      }, 2000)
    } catch (e) {
      setBuildingProjects((prev) => {
        const next = new Set(prev)
        next.delete(selectedProjectId)
        return next
      })
      setError(e instanceof Error ? e.message : 'Build failed')
    }
  }, [api, selectedProjectId])

  const handleSearch = useCallback(async () => {
    if (!query.trim() || !selectedProjectId) return
    setSearchLoading(true)
    try {
      const data = await api.search(selectedProjectId, {
        query: query.trim(),
        k: searchK,
        min_score: minScore,
      })
      const results: SearchResult[] = data.results.map((r) => ({
        chunk_id: r.chunk_id,
        source_path: r.source_path,
        span: r.span,
        preview: r.preview,
        score: r.score,
        section: r.section,
        content: r.content,
      }))
      setSearchResults(results)
      setSelectedChunk(results[0] ?? null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Search failed')
    } finally {
      setSearchLoading(false)
    }
  }, [api, minScore, query, searchK, selectedProjectId])

  const handleGetContext = useCallback(async () => {
    if (!query.trim() || !selectedProjectId) return
    try {
      const data = await api.assembleContext(selectedProjectId, {
        query: query.trim(),
        k: contextK,
        max_chars: contextMaxChars,
        include_sources: contextIncludeSources,
        include_scores: contextIncludeScores,
        min_score: minScore,
        structured: contextStructured,
      })
      setContext(String(data.context || ''))
      if ('chunks' in data && data.chunks) {
        setContextMeta({
          chunks: data.chunks.map((c) => ({
            source_path: c.source_path,
            section: '',
            score: c.score ?? 0,
            truncated: false,
          })),
          total_chars: data.total_chars ?? 0,
          estimated_tokens: data.estimated_tokens ?? 0,
        })
      } else {
        setContextMeta(null)
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to get context')
    }
  }, [api, contextIncludeScores, contextIncludeSources, contextK, contextMaxChars, contextStructured, minScore, query, selectedProjectId])

  const handleCopyContext = useCallback(async () => {
    if (!context) return
    try {
      await navigator.clipboard.writeText(context)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Copy failed')
    }
  }, [context])

  // ── LLM config handlers ─────────────────────────────────────

  const handleLLMConfigChange = useCallback((cfg: LLMConfig) => {
    setLLMConfig(cfg)
    setConfigDirty(true)
  }, [])

  const handleAddEndpoint = useCallback((endpoint: Omit<SavedEndpoint, 'id'>) => {
    const id = `ep_${Date.now()}_${Math.random().toString(16).slice(2)}`
    setLLMConfig((prev) => ({
      ...prev,
      saved_endpoints: [...prev.saved_endpoints, { ...endpoint, id }],
    }))
    setConfigDirty(true)
  }, [])

  const handleEditEndpoint = useCallback((endpoint: SavedEndpoint) => {
    setLLMConfig((prev) => ({
      ...prev,
      saved_endpoints: prev.saved_endpoints.map((e) => (e.id === endpoint.id ? endpoint : e)),
    }))
    setConfigDirty(true)
  }, [])

  const handleDeleteEndpoint = useCallback((id: string) => {
    setLLMConfig((prev) => ({
      ...prev,
      saved_endpoints: prev.saved_endpoints.filter((e) => e.id !== id),
    }))
    setConfigDirty(true)
  }, [])

  const handleTestEndpoint = useCallback(async (endpoint: SavedEndpoint) => {
    const r = await fetch('/api/llm/proxy/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ provider: endpoint.provider, url: endpoint.url, api_key: endpoint.api_key }),
    })
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    const json = await r.json()
    const data = json?.data ?? json
    if (Array.isArray(data.models)) {
      setAvailableModels((prev) => ({ ...prev, [endpoint.id]: data.models }))
    }
    return data as EndpointTestResult
  }, [])

  const handleFetchModels = useCallback(async (endpointId: string) => {
    const ep = llmConfig.saved_endpoints.find((e) => e.id === endpointId)
    if (!ep) return []
    setLoadingModels((prev) => ({ ...prev, [endpointId]: true }))
    try {
      const r = await fetch('/api/llm/proxy/models', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider: ep.provider, url: ep.url, api_key: ep.api_key }),
      })
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      const json = await r.json()
      const data = json?.data ?? json
      const models = Array.isArray(data.models) ? data.models : []
      setAvailableModels((prev) => ({ ...prev, [endpointId]: models }))
      return models
    } finally {
      setLoadingModels((prev) => ({ ...prev, [endpointId]: false }))
    }
  }, [llmConfig.saved_endpoints])

  const handleTestModel = useCallback(async (slotType: 'embedding' | 'small' | 'large' | 'clara') => {
    if (slotType === 'clara') {
      // Resolve CLaRa URL: saved endpoint, remote_url, or default
      let claraUrl = 'http://localhost:8765'
      if (llmConfig.clara.endpoint_id) {
        const ep = llmConfig.saved_endpoints.find((e) => e.id === llmConfig.clara.endpoint_id)
        if (ep) claraUrl = ep.url
      } else if (llmConfig.clara.remote_url) {
        claraUrl = llmConfig.clara.remote_url
      }
      setTestingSlot('clara')
      try {
        const r = await fetch('/api/llm/proxy/test-model', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ provider: 'clara', url: claraUrl, model: 'clara', kind: 'completion' }),
        })
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        const json = await r.json()
        const data = (json?.data ?? json) as EndpointTestResult
        setTestResults((prev) => ({ ...prev, clara: data }))
        return data
      } finally {
        setTestingSlot(null)
      }
    }
    let endpointId: string | undefined
    let model: string | undefined
    let kind = 'completion'
    if (slotType === 'embedding') {
      endpointId = llmConfig.embedding.endpoint_id; model = llmConfig.embedding.model; kind = 'embedding'
    } else if (slotType === 'small') {
      endpointId = llmConfig.small_model.endpoint_id; model = llmConfig.small_model.model
    } else {
      endpointId = llmConfig.large_model.endpoint_id; model = llmConfig.large_model.model
    }
    const ep = llmConfig.saved_endpoints.find((e) => e.id === endpointId)
    if (!ep || !model) {
      const res: EndpointTestResult = { success: false, message: 'Model not configured.' }
      setTestResults((prev) => ({ ...prev, [slotType]: res }))
      return res
    }
    setTestingSlot(slotType)
    try {
      const r = await fetch('/api/llm/proxy/test-model', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider: ep.provider, url: ep.url, api_key: ep.api_key, model, kind }),
      })
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      const json = await r.json()
      const data = (json?.data ?? json) as EndpointTestResult
      setTestResults((prev) => ({ ...prev, [slotType]: data }))
      return data
    } finally {
      setTestingSlot(null)
    }
  }, [llmConfig])

  const handleSaveConfig = useCallback(async () => {
    if (!selectedProjectId) return
    try {
      await api.updateProject(selectedProjectId, {
        config: {
          include_globs: projectConfig.include_globs,
          exclude_globs: projectConfig.exclude_globs,
          max_file_bytes: projectConfig.max_file_bytes,
          trace: projectConfig.trace,
          auto_rebuild: projectConfig.auto_rebuild,
        },
      })
      setConfigDirty(false)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to save config')
    }
  }, [api, projectConfig, selectedProjectId])

  const handleProjectConfigChange = useCallback((cfg: ProjectConfig) => {
    setProjectConfig(cfg)
    setConfigDirty(true)
  }, [])

  const handleDetectStack = useCallback(async () => {
    if (!selectedProjectId) throw new Error("No project selected")
    return await api.detectStack(selectedProjectId)
  }, [api, selectedProjectId])

  // ── LLM slots connectivity check ────────────────────────────

  const fetchLLMSlotsStatus = useCallback(async () => {
    try {
      const status = await api.getLLMSlotsStatus()
      setLlmSlotsStatus(status)
    } catch {
      // Silent — not critical
    }
  }, [api])

  // ── Augmentation handlers ──────────────────────────────────

  const fetchAugmentationStatus = useCallback(async () => {
    if (!selectedProjectId) return
    try {
      const status = await api.getAugmentStatus(selectedProjectId)
      setAugmentationStatus(status)
    } catch {
      // Silent — status not critical
    }
  }, [api, selectedProjectId])

  const handleRunAugmentation = useCallback(async () => {
    if (!selectedProjectId) return
    setAugmenting(true)
    try {
      await api.runAugmentation(selectedProjectId)
      const poll = setInterval(async () => {
        try {
          const status = await api.getAugmentStatus(selectedProjectId)
          setAugmentationStatus(status)
          // Stop polling once augmented_nodes stabilizes (no running indicator from status)
          // We'll just poll a few times then stop
        } catch { /* ignore */ }
      }, 3000)
      // Stop after 5 minutes max
      setTimeout(() => {
        clearInterval(poll)
        setAugmenting(false)
        void fetchAugmentationStatus()
      }, 300_000)
    } catch (e) {
      setAugmenting(false)
      setError(e instanceof Error ? e.message : 'Augmentation failed')
    }
  }, [api, selectedProjectId, fetchAugmentationStatus])

  // ── Deep analysis handlers ─────────────────────────────────

  const fetchDeepAnalysisStatus = useCallback(async () => {
    if (!selectedProjectId) return
    try {
      const status = await api.getDeepAnalysisStatus(selectedProjectId)
      setDeepAnalysisStatus(status)
    } catch {
      // Silent — status not critical
    }
  }, [api, selectedProjectId])

  const handleRunDeepAnalysis = useCallback(async () => {
    if (!selectedProjectId) return
    setDeepAnalysisRunning(true)
    try {
      await api.runDeepAnalysis(selectedProjectId)
      // Poll for completion
      const poll = setInterval(async () => {
        try {
          const status = await api.getDeepAnalysisStatus(selectedProjectId)
          setDeepAnalysisStatus(status)
          if (!status.running) {
            clearInterval(poll)
            setDeepAnalysisRunning(false)
          }
        } catch {
          clearInterval(poll)
          setDeepAnalysisRunning(false)
        }
      }, 3000)
    } catch (e) {
      setDeepAnalysisRunning(false)
      setError(e instanceof Error ? e.message : 'Deep analysis failed')
    }
  }, [api, selectedProjectId])

  // ── Watch handlers ──────────────────────────────────────────

  const refreshWatchStatus = useCallback(async (projId: string) => {
    try {
      const ws = await api.getWatchStatus(projId)
      setWatchStatus(ws)
    } catch {
      setWatchStatus({ enabled: false, state: 'disabled', stale: false, pending: false })
    }
  }, [api])

  const handleStartWatch = useCallback(async () => {
    if (!selectedProjectId) return
    setWatchLoading(true)
    try {
      await api.startWatch(selectedProjectId)
      await refreshWatchStatus(selectedProjectId)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to start watch')
    } finally {
      setWatchLoading(false)
    }
  }, [api, selectedProjectId, refreshWatchStatus])

  const handleStopWatch = useCallback(async () => {
    if (!selectedProjectId) return
    setWatchLoading(true)
    try {
      await api.stopWatch(selectedProjectId)
      await refreshWatchStatus(selectedProjectId)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to stop watch')
    } finally {
      setWatchLoading(false)
    }
  }, [api, selectedProjectId, refreshWatchStatus])

  // ── Index inclusion handlers (knowledge scope — unrelated to dashboard pins) ──

  const handleToggleInclude = useCallback((paths: string[], action: 'add' | 'remove') => {
    setIncludedPaths((prev) => {
      const next = new Set(prev)
      if (action === 'add') {
        paths.forEach((p) => next.add(p))
      } else {
        paths.forEach((p) => next.delete(p))
      }
      localStorage.setItem('codrag_included_paths', JSON.stringify([...next]))
      return next
    })
  }, [])

  // ── Pinned files handlers ──────────────────────────────────

  const handlePinFile = useCallback((path: string) => {
    console.log('[App] handlePinFile called for:', path)
    setPinnedPaths((prev) => {
      const next = new Set(prev)
      next.add(path)
      localStorage.setItem('codrag_pinned_files', JSON.stringify([...next]))
      return next
    })
  }, [])

  // Sync pinned paths to dashboard layout (ensure panels exist and are visible)
  useEffect(() => {
    console.log('[App] Syncing pinned paths to layout. Paths:', Array.from(pinnedPaths))
    if (!layoutApiRef.current) {
      console.warn('[App] layoutApiRef.current is missing, cannot sync layout')
      return
    }
    
    // We only need to ensure pinned paths are in the layout.
    // Unpinning is handled explicitly by handleUnpinFile.
    for (const path of pinnedPaths) {
      const panelId = `${PINNED_PREFIX}${path}`
      console.log('[App] Ensuring panel in layout:', panelId)
      // addPanel will make it visible if it already exists
      layoutApiRef.current.addPanel(panelId, { height: 8, w: 6 })
    }
  }, [pinnedPaths])

  const handleUnpinFile = useCallback((pathOrPanelId: string) => {
    console.log('[App] handleUnpinFile:', pathOrPanelId)
    const path = pathOrPanelId.startsWith(PINNED_PREFIX)
      ? pathOrPanelId.slice(PINNED_PREFIX.length)
      : pathOrPanelId
    const panelId = `${PINNED_PREFIX}${path}`

    setPinnedPaths((prev) => {
      const next = new Set(prev)
      const deleted = next.delete(path)
      console.log('[App] Unpinning path:', path, 'Deleted:', deleted, 'New size:', next.size)
      localStorage.setItem('codrag_pinned_files', JSON.stringify([...next]))
      return next
    })
    setPinnedFiles((prev) => prev.filter((f) => f.id !== path))
    console.log('[App] Removing panel from layout:', panelId)
    layoutApiRef.current?.removePanel(panelId)
  }, [])

  const handlePanelClose = useCallback((panelId: string) => {
    if (panelId.startsWith(PINNED_PREFIX)) {
      handleUnpinFile(panelId)
    }
  }, [handleUnpinFile])

  const handlePathWeightChange = useCallback((path: string, weight: number | null) => {
    if (!selectedProjectId) return
    setPathWeights((prev) => {
      const next = { ...prev }
      if (weight === null) {
        delete next[path]
      } else {
        next[path] = weight
      }
      // Persist to backend (fire-and-forget)
      api.updatePathWeights(selectedProjectId, next).catch(() => {})
      return next
    })
  }, [api, selectedProjectId])

  const handleSearchTrace = useCallback(async (query: string, kinds?: string[], limit?: number) => {
    if (!selectedProjectId) return { nodes: [] }
    return api.searchTrace(selectedProjectId, query, kinds, limit)
  }, [api, selectedProjectId])

  const handleGetTraceNode = useCallback(async (nodeId: string) => {
    if (!selectedProjectId) throw new Error('No project selected')
    return api.getTraceNode(selectedProjectId, nodeId)
  }, [api, selectedProjectId])

  const handleGetTraceNeighbors = useCallback(async (nodeId: string, direction?: string) => {
    if (!selectedProjectId) throw new Error('No project selected')
    return api.getTraceNeighbors(selectedProjectId, nodeId, direction)
  }, [api, selectedProjectId])

  const handleBuildTrace = useCallback(() => {
    if (!selectedProjectId) return
    api.buildTrace(selectedProjectId).then(() => {
      setTraceStatus(prev => ({ ...prev, building: true }))
    }).catch(() => {})
  }, [api, selectedProjectId])

  const handleEnableTrace = useCallback(() => {
    if (!selectedProjectId) return
    const newConfig = { ...projectConfig, trace: { ...projectConfig.trace, enabled: true } }
    setProjectConfig(newConfig)
    setConfigDirty(true)
    api.updateProject(selectedProjectId, { config: newConfig }).catch(() => {})
    setTraceStatus(prev => ({ ...prev, enabled: true }))
  }, [api, selectedProjectId, projectConfig])

  const fetchTraceCoverage = useCallback(() => {
    if (!selectedProjectId || !traceStatus.enabled) return
    setTraceCoverage(prev => ({ ...prev, loading: true }))
    api.getTraceCoverage(selectedProjectId).then((data) => {
      setTraceCoverage({
        summary: data.summary,
        untraced: data.untraced,
        stale: data.stale,
        excluded: data.excluded ?? (data as any).ignored ?? [],
        building: data.building,
        loading: false,
      })
    }).catch(() => {
      setTraceCoverage(prev => ({ ...prev, loading: false }))
    })
  }, [api, selectedProjectId, traceStatus.enabled])

  const handleTraceAll = useCallback(() => {
    if (!selectedProjectId) return
    api.buildTrace(selectedProjectId).then(() => {
      setTraceStatus(prev => ({ ...prev, building: true }))
      setTraceCoverage(prev => ({ ...prev, building: true }))
    }).catch(() => {})
  }, [api, selectedProjectId])

  const handleRetraceStale = useCallback(() => {
    // Re-trace triggers a full trace rebuild (same as trace all)
    handleTraceAll()
  }, [handleTraceAll])

  const handleAddExcludePattern = useCallback((pattern: string) => {
    if (!selectedProjectId) return
    api.updateTraceIgnore(selectedProjectId, 'add', [pattern]).then(() => {
      fetchTraceCoverage()
    }).catch(() => {})
  }, [api, selectedProjectId, fetchTraceCoverage])

  const handleRemoveExcludePattern = useCallback((pattern: string) => {
    if (!selectedProjectId) return
    api.updateTraceIgnore(selectedProjectId, 'remove', [pattern]).then(() => {
      fetchTraceCoverage()
    }).catch(() => {})
  }, [api, selectedProjectId, fetchTraceCoverage])

  const handleLoadChildren = useCallback(async (path: string): Promise<TreeNode[]> => {
    if (!selectedProjectId) return []
    const data = await api.getProjectFiles(selectedProjectId, path, 4)
    return (data.tree ?? []) as TreeNode[]
  }, [api, selectedProjectId])

  const handleLoadFileContent = useCallback(async (path: string): Promise<string> => {
    if (!selectedProjectId) throw new Error('No project selected')
    const data = await api.getProjectFileContent(selectedProjectId, path)
    return data.content
  }, [api, selectedProjectId])

  // Fetch content for pinned files when paths or project change
  useEffect(() => {
    if (!selectedProjectId || pinnedPaths.size === 0) {
      setPinnedFiles([])
      return
    }
    let cancelled = false
    const fetchAll = async () => {
      const results: PinnedTextFile[] = []
      for (const path of pinnedPaths) {
        try {
          const data = await api.getProjectFileContent(selectedProjectId, path)
          if (cancelled) return
          const name = path.split('/').pop() ?? path
          results.push({ id: path, path, name, content: data.content })
        } catch {
          // skip files that fail to load
        }
      }
      if (!cancelled) setPinnedFiles(results)
    }
    void fetchAll()
    return () => { cancelled = true }
  }, [api, selectedProjectId, pinnedPaths])

  // ── Auto-refresh coverage when trace build completes via SSE ──
  const prevTraceBuildStatusRef = useRef<string | undefined>(undefined)
  useEffect(() => {
    const traceTask = findActiveTask('trace_build')
    const prevStatus = prevTraceBuildStatusRef.current
    prevTraceBuildStatusRef.current = traceTask?.status

    // Detect transition to completed/failed
    if (traceTask && prevStatus === 'running' && (traceTask.status === 'completed' || traceTask.status === 'failed')) {
      // Reset building flags and refresh coverage data
      setTraceStatus(prev => ({ ...prev, building: false }))
      setTraceCoverage(prev => ({ ...prev, building: false }))
      if (traceTask.status === 'completed') {
        // Short delay to let the backend finish flushing the manifest
        setTimeout(() => fetchTraceCoverage(), 500)
      }
    }
  }, [findActiveTask, fetchTraceCoverage])

  // ── Theme effect ───────────────────────────────────────────
  useEffect(() => {
    const root = document.documentElement
    if (uiMode === 'dark') root.classList.add('dark')
    else root.classList.remove('dark')
    root.setAttribute('data-codrag-theme', uiTheme === 'none' ? 'a' : uiTheme)
    localStorage.setItem('codrag_ui_mode', uiMode)
    localStorage.setItem('codrag_ui_theme', uiTheme)
    if (bgImage) localStorage.setItem('codrag_bg_image', bgImage)
    else localStorage.removeItem('codrag_bg_image')
  }, [uiMode, uiTheme, bgImage])

  // ── Persist UI preferences to backend ─────────────────────
  const uiPrefsSkipRef = useRef(0)
  useEffect(() => {
    if (uiPrefsSkipRef.current < 2) { uiPrefsSkipRef.current++; return }
    const timeout = setTimeout(() => {
      api.updateGlobalConfig({
        ui_preferences: { mode: uiMode, theme: uiTheme, bg_image: bgImage },
      }).catch(() => {})
    }, 500)
    return () => clearTimeout(timeout)
  }, [api, uiMode, uiTheme, bgImage])

  // ── Init: load projects + global config ─────────────────────
  useEffect(() => {
    const init = async () => {
      try {
        await refreshProjects()
        // Load global config (LLM endpoints, models, etc.)
        try {
          const globalCfg = await api.getGlobalConfig()
          if (globalCfg.llm_config) {
            setLLMConfig(globalCfg.llm_config)
          }
          if (globalCfg.deep_analysis) {
            setDeepAnalysisSchedule((prev) => ({ ...prev, ...globalCfg.deep_analysis }))
          }
          if (globalCfg.ui_preferences) {
            const prefs = globalCfg.ui_preferences
            if (prefs.mode) setUiMode(prefs.mode)
            if (prefs.theme) setUiTheme(prefs.theme)
            if (prefs.bg_image !== undefined) setBgImage(prefs.bg_image)
          }
          if (globalCfg.module_layout && globalCfg.module_layout.version) {
            // Persist to localStorage so useLayoutPersistence picks it up
            try {
              localStorage.setItem('codrag_dashboard_layout', JSON.stringify(globalCfg.module_layout))
            } catch { /* storage full */ }
          }
        } catch {
          // Global config not available — use defaults
        }
        // Check LLM connectivity
        void fetchLLMSlotsStatus()
      } catch {
        // Error already set
      } finally {
        setLoading(false)
      }
    }
    void init()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshProjects])

  // ── Auto-save LLM config to backend ─────────────────────────
  const llmConfigSkipRef = useRef(0) // skip initial + loaded-from-backend
  useEffect(() => {
    if (llmConfigSkipRef.current < 2) {
      llmConfigSkipRef.current++
      return
    }
    const timeout = setTimeout(() => {
      api.updateGlobalConfig({ llm_config: llmConfig }).catch(() => {
        // Silent fail — config will be retried on next change
      })
    }, 500)
    return () => clearTimeout(timeout)
  }, [api, llmConfig])

  // ── Auto-save deep analysis schedule to backend ─────────────
  const deepAnalysisSkipRef = useRef(0)
  useEffect(() => {
    if (deepAnalysisSkipRef.current < 2) {
      deepAnalysisSkipRef.current++
      return
    }
    const timeout = setTimeout(() => {
      api.updateGlobalConfig({ deep_analysis: deepAnalysisSchedule }).catch(() => {})
    }, 500)
    return () => clearTimeout(timeout)
  }, [api, deepAnalysisSchedule])

  // ── Auto-save dashboard layout to backend ───────────────────
  const layoutSkipRef = useRef(0)
  useEffect(() => {
    if (!dashboardLayout) return
    if (layoutSkipRef.current < 2) { layoutSkipRef.current++; return }
    const timeout = setTimeout(() => {
      api.updateGlobalConfig({ module_layout: dashboardLayout }).catch(() => {})
    }, 1000)
    return () => clearTimeout(timeout)
  }, [api, dashboardLayout])

  // ── Auto-fetch models for pre-configured endpoints ──────────
  useEffect(() => {
    const endpointIds = new Set<string>()
    if (llmConfig.embedding.source === 'endpoint' && llmConfig.embedding.endpoint_id) {
      endpointIds.add(llmConfig.embedding.endpoint_id)
    }
    if (llmConfig.small_model.endpoint_id) endpointIds.add(llmConfig.small_model.endpoint_id)
    if (llmConfig.large_model.endpoint_id) endpointIds.add(llmConfig.large_model.endpoint_id)

    for (const epId of endpointIds) {
      if (!availableModels[epId]?.length) {
        void handleFetchModels(epId)
      }
    }
  // Run once on mount — intentionally omitting deps to avoid re-fetching on every config change
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ── Refresh status + watch when project changes ─────────────
  useEffect(() => {
    if (!selectedProjectId) return
    void refreshStatus(selectedProjectId)
    void refreshWatchStatus(selectedProjectId)
    void fetchAugmentationStatus()
    void fetchDeepAnalysisStatus()
    // Fetch file tree
    api.getProjectFiles(selectedProjectId, '', 15).then((data) => {
      const tree = data.tree ?? []
      setFileTree(tree)
      // Merge server-reported indexed/pending paths into includedPaths
      // so already-indexed files aren't shown as "Removing" after restart
      const serverPaths = collectIndexedPaths(tree)
      if (serverPaths.length > 0) {
        setIncludedPaths((prev) => {
          const next = new Set(prev)
          let changed = false
          for (const p of serverPaths) {
            if (!next.has(p)) { next.add(p); changed = true }
          }
          if (changed) {
            localStorage.setItem('codrag_included_paths', JSON.stringify([...next]))
          }
          return changed ? next : prev
        })
      }
    }).catch(() => { setFileTree([]) })
    // Fetch path weights
    api.getPathWeights(selectedProjectId).then((data) => {
      setPathWeights(data.path_weights ?? {})
    }).catch(() => { setPathWeights({}) })
    // Fetch trace status, then coverage if trace is enabled
    api.getTraceStatus(selectedProjectId).then((data) => {
      const enabled = data.enabled ?? false
      setTraceStatus({
        enabled,
        exists: data.exists ?? false,
        building: data.building ?? false,
        counts: data.counts ?? { nodes: 0, edges: 0 },
      })
      // Fetch coverage directly — can't rely on fetchTraceCoverage() here
      // because setTraceStatus hasn't applied yet (stale closure)
      if (enabled && selectedProjectId) {
        setTraceCoverage(prev => ({ ...prev, loading: true }))
        api.getTraceCoverage(selectedProjectId).then((cov) => {
          setTraceCoverage({
            summary: cov.summary,
            untraced: cov.untraced,
            stale: cov.stale,
            excluded: cov.excluded ?? (cov as any).ignored ?? [],
            building: cov.building,
            loading: false,
          })
        }).catch(() => {
          setTraceCoverage(prev => ({ ...prev, loading: false }))
        })
      }
    }).catch(() => { setTraceStatus({ enabled: false, exists: false, building: false, counts: { nodes: 0, edges: 0 } }) })
    // Load project config
    api.getProject(selectedProjectId).then((data) => {
      const cfg = data.project.config
      if (cfg) {
        setProjectConfig({
          include_globs: cfg.include_globs ?? projectConfig.include_globs,
          exclude_globs: cfg.exclude_globs ?? projectConfig.exclude_globs,
          max_file_bytes: cfg.max_file_bytes ?? projectConfig.max_file_bytes,
          use_gitignore: cfg.use_gitignore ?? projectConfig.use_gitignore,
          trace: cfg.trace ?? projectConfig.trace,
          auto_rebuild: cfg.auto_rebuild ?? projectConfig.auto_rebuild,
        })
        setConfigDirty(false)
      }
    }).catch(() => {})
    // Auto-select first project if none selected
  }, [selectedProjectId]) // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-select first project
  useEffect(() => {
    if (!selectedProjectId && projects.length > 0) {
      setSelectedProjectId(projects[0].id)
    }
  }, [projects, selectedProjectId])

  // ── Panel content (Storybook components only) ──────────────

  const panelContent = useMemo(() => ({
    'log-console': (
      <LogConsole
        logs={logs}
        onClear={clearLogs}
        className="h-full border-none shadow-none bg-transparent"
        defaultExpanded={true}
      />
    ),
    'usage-guide': (
      <UsageGuidePanel bare />
    ),
    status: (
      <IndexStatusCard
        stats={projectStatus ? {
          loaded: projectStatus.index.exists,
          index_dir: selectedProject?.path,
          total_documents: projectStatus.index.total_chunks,
          model: projectStatus.index.embedding_model,
          built_at: projectStatus.index.last_build_at ?? undefined,
          embedding_dim: projectStatus.index.embedding_dim,
          build: projectStatus.index.build,
        } : {
          loaded: false,
          total_documents: 0,
          embedding_dim: 0,
          model: 'Unknown',
          built_at: undefined,
          build: undefined,
        }}
        building={projectStatus?.building ?? false}
        stale={projectStatus?.stale ?? false}
        progress={findActiveTask('index_build')}
        lastError={projectStatus?.index.last_error?.message}
        onBuild={selectedProjectId ? handleBuild : undefined}
        traceChunks={traceStatus.counts?.nodes ?? 0}
        className="h-full border-none shadow-none bg-transparent"
        bare
      />
    ),
    'llm-status': (
      <div className="h-full overflow-y-auto p-4">
        <LLMStatusWidget
          services={(() => {
            const hasEmbedding = !!(llmConfig.embedding.model && (llmConfig.embedding.source === 'endpoint' || llmConfig.embedding.source === 'huggingface'));
            const hasFast = !!(llmConfig.small_model.enabled && llmConfig.small_model.model);
            const hasThinking = !!(llmConfig.large_model.enabled && llmConfig.large_model.model);
            const hasCLaRa = !!(llmConfig.clara.enabled && (llmConfig.clara.remote_url || llmConfig.clara.endpoint_id || llmConfig.clara.source === 'huggingface'));
            const fastName = hasThinking ? 'Fast Model' : 'Single LLM';
            type Svc = { name: string; status: 'connected' | 'disconnected' | 'disabled' | 'not-configured'; type: 'ollama' | 'clara' | 'openai' | 'other'; model?: string };
            const items: Svc[] = [];
            if (hasEmbedding) {
              items.push({
                name: 'Embedding',
                status: llmSlotsStatus?.embedding
                  ? (llmSlotsStatus.embedding.status === 'connected' || llmSlotsStatus.embedding.status === 'local' ? 'connected'
                    : llmSlotsStatus.embedding.status === 'unreachable' ? 'disconnected'
                    : llmSlotsStatus.embedding.configured ? 'disconnected' : 'not-configured')
                  : 'connected',
                type: 'other',
                model: llmConfig.embedding.model,
              });
            }
            if (hasFast) {
              items.push({
                name: fastName,
                status: llmSlotsStatus?.small_model
                  ? (llmSlotsStatus.small_model.status === 'connected' ? 'connected'
                    : llmSlotsStatus.small_model.status === 'unreachable' ? 'disconnected'
                    : llmSlotsStatus.small_model.configured ? 'disconnected' : 'not-configured')
                  : 'connected',
                type: 'ollama',
                model: llmConfig.small_model.model,
              });
            }
            if (hasThinking) {
              items.push({
                name: 'Thinking Model',
                status: llmSlotsStatus?.large_model
                  ? (llmSlotsStatus.large_model.status === 'connected' ? 'connected'
                    : llmSlotsStatus.large_model.status === 'unreachable' ? 'disconnected'
                    : llmSlotsStatus.large_model.configured ? 'disconnected' : 'not-configured')
                  : 'connected',
                type: 'openai',
                model: llmConfig.large_model.model,
              });
            }
            if (hasCLaRa) {
              items.push({
                name: 'CLaRa',
                status: llmConfig.clara.remote_url || llmConfig.clara.endpoint_id ? 'connected' : 'not-configured',
                type: 'clara',
                model: 'Context Compression',
              });
            }
            if (items.length === 0) {
              items.push({ name: 'No models configured', status: 'not-configured', type: 'other' });
            }
            return items;
          })()}
          bare
        />
      </div>
    ),
    search: (
      <SearchPanel
        query={query}
        onQueryChange={setQuery}
        k={searchK}
        onKChange={setSearchK}
        minScore={minScore}
        onMinScoreChange={setMinScore}
        onSearch={handleSearch}
        loading={searchLoading}
        bare
      />
    ),
    'context-options': (
      <ContextOptionsPanel
        k={contextK}
        onKChange={setContextK}
        maxChars={contextMaxChars}
        onMaxCharsChange={setContextMaxChars}
        includeSources={contextIncludeSources}
        onIncludeSourcesChange={setContextIncludeSources}
        includeScores={contextIncludeScores}
        onIncludeScoresChange={setContextIncludeScores}
        structured={contextStructured}
        onStructuredChange={setContextStructured}
        onGetContext={handleGetContext}
        onCopyContext={handleCopyContext}
        hasContext={!!context}
        disabled={!query.trim()}
        bare
      />
    ),
    results: (
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 h-full overflow-hidden">
        <div className="h-full overflow-y-auto min-h-0">
          <SearchResultsList
            results={searchResults}
            selectedId={selectedChunk?.chunk_id}
            onSelect={setSelectedChunk}
          />
        </div>
        <div className="h-full overflow-y-auto min-h-0 border-l border-border pl-4">
          <ChunkPreview
            content={selectedChunk?.content}
            sourcePath={selectedChunk?.source_path}
            section={selectedChunk?.section}
            bare
          />
        </div>
      </div>
    ),
    'context-output': (
      <ContextOutput
        context={context}
        meta={contextMeta}
        bare
      />
    ),
    roots: (
      <FolderTreePanel
        data={fileTree}
        includedPaths={includedPaths}
        onToggleInclude={handleToggleInclude}
        pathWeights={pathWeights}
        onWeightChange={handlePathWeightChange}
        onLoadChildren={handleLoadChildren}
        bare
      />
    ),
    ...Object.fromEntries(
      [...pinnedPaths].map((p) => {
        const file = pinnedFiles.find((f) => f.path === p)
        return [
          `${PINNED_PREFIX}${p}`,
          file ? (
            <div key={p} className="h-full flex flex-col overflow-hidden">
              <div className="flex items-center justify-between gap-2 px-1 py-1 border-b border-border shrink-0">
                <span className="text-xs font-mono text-text-muted truncate flex-1">{file.path}</span>
                <CopyButton text={file.content} label="Copy" />
              </div>
              <pre className="flex-1 min-h-0 p-3 text-xs whitespace-pre-wrap font-mono text-text overflow-y-auto custom-scrollbar">
                {file.content}
              </pre>
            </div>
          ) : (
            <div key={p} className="h-full flex items-center justify-center text-sm text-text-muted">
              Loading {p.split('/').pop()}…
            </div>
          ),
        ]
      })
    ),
    watch: (
      <WatchControlPanel
        status={watchStatus}
        onStartWatch={handleStartWatch}
        onStopWatch={handleStopWatch}
        onRebuildNow={() => selectedProjectId && void handleBuild()}
        loading={watchLoading}
        bare
      />
    ),
    trace: (
      <TraceExplorer
        traceEnabled={traceStatus.enabled}
        traceExists={traceStatus.exists}
        traceBuilding={traceStatus.building}
        traceCounts={traceStatus.counts}
        onSearchTrace={handleSearchTrace}
        onGetNode={handleGetTraceNode}
        onGetNeighbors={handleGetTraceNeighbors}
        onBuildTrace={handleBuildTrace}
        onEnableTrace={handleEnableTrace}
        progress={findActiveTask('trace_build')}
      />
    ),
    'trace-coverage': (
      <TraceCoveragePanel
        summary={traceCoverage.summary}
        untracedFiles={traceCoverage.untraced}
        staleFiles={traceCoverage.stale}
        excludedFiles={traceCoverage.excluded}
        building={traceCoverage.building}
        loading={traceCoverage.loading}
        onTraceAll={handleTraceAll}
        onRetraceStale={handleRetraceStale}
        onAddExcludePattern={handleAddExcludePattern}
        onRemoveExcludePattern={handleRemoveExcludePattern}
        onRefresh={fetchTraceCoverage}
        progress={findActiveTask('trace_build')}
        bare
      />
    ),
    'trace-pipeline': (
      <div className="h-full overflow-y-auto p-4">
        <TracePipelineStatus
          trace={{
            enabled: traceStatus.enabled,
            exists: traceStatus.exists,
            building: traceStatus.building,
            counts: traceStatus.counts,
            last_build_at: null,
          }}
          augmentation={augmentationStatus}
          deepAnalysis={deepAnalysisStatus}
          smallModelConfigured={!!(llmConfig.small_model?.endpoint_id && llmConfig.small_model?.model)}
          largeModelConfigured={!!(llmConfig.large_model?.endpoint_id && llmConfig.large_model?.model)}
          onBuildTrace={handleBuildTrace}
          onRunAugmentation={handleRunAugmentation}
          onRunDeepAnalysis={handleRunDeepAnalysis}
          augmenting={augmenting}
          deepAnalyzing={deepAnalysisRunning}
        />
      </div>
    ),
    'deep-analysis': (
      <div className="h-full overflow-y-auto p-4">
        <DeepAnalysisSettings
          schedule={deepAnalysisSchedule}
          onScheduleChange={setDeepAnalysisSchedule}
          largeModelConfigured={!!(llmConfig.large_model?.endpoint_id && llmConfig.large_model?.model)}
          fastModelConfigured={!!(llmConfig.small_model?.endpoint_id && llmConfig.small_model?.model)}
          status={deepAnalysisStatus}
          running={deepAnalysisRunning}
          onRunNow={handleRunDeepAnalysis}
        />
      </div>
    ),
    settings: (
      <ProjectSettingsPanel
        config={projectConfig}
        onChange={handleProjectConfigChange}
        onSave={() => void handleSaveConfig()}
        onDetectStack={handleDetectStack}
        isDirty={configDirty}
        bare
      />
    ),
  }), [
    projectStatus, isBuilding, selectedProject, selectedProjectId, fileTree, includedPaths, pinnedPaths, pinnedFiles,
    watchStatus, watchLoading, handleStartWatch, handleStopWatch,
    query, searchK, minScore, searchLoading, searchResults, selectedChunk,
    contextK, contextMaxChars, contextIncludeSources, contextIncludeScores, contextStructured, context, contextMeta,
    projectConfig, configDirty, traceStatus, traceCoverage,
    handleBuild, handleSearch, handleGetContext, handleCopyContext, handleSaveConfig, handleProjectConfigChange,
    handleToggleInclude, handlePinFile, handleUnpinFile, pathWeights, handlePathWeightChange, handleLoadChildren,
    handleSearchTrace, handleGetTraceNode, handleGetTraceNeighbors, handleBuildTrace, handleEnableTrace,
    handleTraceAll, handleRetraceStale, handleAddExcludePattern, handleRemoveExcludePattern, fetchTraceCoverage,
    findActiveTask, logs, clearLogs, tasks, llmConfig,
    handleLLMConfigChange, handleAddEndpoint, handleEditEndpoint, handleDeleteEndpoint,
    handleTestEndpoint, handleFetchModels, handleTestModel, availableModels, loadingModels, testingSlot, testResults,
    handleDetectStack, augmentationStatus, deepAnalysisStatus, augmenting, deepAnalysisRunning,
    handleRunAugmentation, handleRunDeepAnalysis, handleBuildTrace, llmSlotsStatus,
  ])

  // ── Dynamic panel definitions for pinned files ──────────────
  const dynamicPanelDefs = useMemo<PanelDefinition[]>(() =>
    [...pinnedPaths].map((p) => ({
      id: `${PINNED_PREFIX}${p}`,
      title: p.split('/').pop() ?? p,
      icon: FileText,
      minHeight: 4,
      defaultHeight: 8,
      category: 'projects' as const,
      closeable: true,
      resizable: true,
    })),
    [pinnedPaths]
  )

  const allPanelDefs = useMemo(
    () => [...PANEL_REGISTRY, ...dynamicPanelDefs],
    [dynamicPanelDefs]
  )

  const panelDetails = useMemo(() => ({
    'llm-status': (
      <div className="max-w-6xl mx-auto w-full p-6 space-y-8">
        <AIModelsSettings
          config={llmConfig}
          onConfigChange={handleLLMConfigChange}
          onAddEndpoint={handleAddEndpoint}
          onEditEndpoint={handleEditEndpoint}
          onDeleteEndpoint={handleDeleteEndpoint}
          onTestEndpoint={handleTestEndpoint}
          onFetchModels={handleFetchModels}
          onTestModel={handleTestModel}
          onHFDownload={() => {}}
          availableModels={availableModels}
          loadingModels={loadingModels}
          testingSlot={testingSlot}
          testResults={testResults}
        />
      </div>
    ),
    'deep-analysis': (
      <div className="h-full overflow-y-auto p-4">
        <DeepAnalysisSettings
          schedule={deepAnalysisSchedule}
          onScheduleChange={setDeepAnalysisSchedule}
          largeModelConfigured={!!(llmConfig.large_model?.endpoint_id && llmConfig.large_model?.model)}
          fastModelConfigured={!!(llmConfig.small_model?.endpoint_id && llmConfig.small_model?.model)}
          status={deepAnalysisStatus}
          running={deepAnalysisRunning}
          onRunNow={handleRunDeepAnalysis}
          className="max-w-xl mx-auto"
        />
      </div>
    ),
    roots: (
      <FileExplorerDetail
        treeData={fileTree}
        pinnedPaths={pinnedPaths}
        onPinFile={handlePinFile}
        onUnpinFile={handleUnpinFile}
        onLoadFileContent={handleLoadFileContent}
        includedPaths={includedPaths}
        onToggleInclude={handleToggleInclude}
        pathWeights={pathWeights}
        onWeightChange={handlePathWeightChange}
        onLoadChildren={handleLoadChildren}
      />
    ),
    settings: (
      <div className="max-w-4xl mx-auto w-full p-6">
        <ProjectSettingsPanel
          config={projectConfig}
          onChange={handleProjectConfigChange}
          onSave={() => void handleSaveConfig()}
          onDetectStack={handleDetectStack}
          isDirty={configDirty}
        />
      </div>
    ),
  }), [
    llmConfig, handleLLMConfigChange, handleAddEndpoint, handleEditEndpoint, handleDeleteEndpoint,
    handleTestEndpoint, handleFetchModels, handleTestModel, availableModels, loadingModels, testingSlot, testResults,
    fileTree, includedPaths, handleToggleInclude, pinnedPaths, handlePinFile, handleUnpinFile, handleLoadFileContent, handleLoadChildren, pathWeights, handlePathWeightChange,
    projectConfig, handleProjectConfigChange, handleSaveConfig, configDirty, handleDetectStack,
    deepAnalysisSchedule, deepAnalysisStatus, deepAnalysisRunning, handleRunDeepAnalysis,
  ])

  // ── Loading state ──────────────────────────────────────────
  if (loading) {
    return <LoadingState message="Connecting to CoDRAG daemon..." />
  }

  // ── Render ─────────────────────────────────────────────────
  return (
    <>
      <ConnectivityStatus />
      <SettingsDrawer
        open={devSettingsOpen}
        onClose={() => setDevSettingsOpen(false)}
        projectConfig={projectConfig}
        onProjectConfigChange={handleProjectConfigChange}
        onSaveConfig={() => void handleSaveConfig()}
        configDirty={configDirty}
        hasProject={!!selectedProject}
        onDetectStack={handleDetectStack}
        uiMode={uiMode}
        onModeChange={setUiMode}
        uiTheme={uiTheme}
        onThemeChange={setUiTheme}
        bgImage={bgImage}
        onBgImageChange={setBgImage}
      />
      {/* Floating Dev Settings trigger — always visible */}
      {!devSettingsOpen && (
        <Button
          variant="outline"
          size="icon"
          onClick={() => setDevSettingsOpen(true)}
          title="Dev Settings"
          className="fixed bottom-4 right-4 z-40 shadow-lg bg-surface hover:bg-surface-raised"
        >
          <Settings className="w-5 h-5" />
        </Button>
      )}
      {/* Background image overlay */}
      {bgImage && (
        <div
          className="fixed inset-0 z-[-1] bg-cover bg-center opacity-10 pointer-events-none"
          style={{ backgroundImage: `url(${bgImage})` }}
        />
      )}
      <AppShell
        sidebar={
          <Sidebar
            collapsed={sidebarCollapsed}
            onCollapseToggle={() => setSidebarCollapsed((c) => !c)}
          >
            {!sidebarCollapsed && (
              <ProjectList
                projects={projectSummaries}
                selectedProjectId={selectedProjectId ?? undefined}
                onProjectSelect={setSelectedProjectId}
                onAddProject={() => setAddModalOpen(true)}
                extraActions={
                  dashboardLayout && layoutApiRef.current ? (
                    <PanelPicker
                      layout={dashboardLayout}
                      panelDefinitions={allPanelDefs}
                      onTogglePanel={layoutApiRef.current.togglePanelVisibility}
                      onResetLayout={layoutApiRef.current.resetLayout}
                      onRefitLayout={layoutApiRef.current.reflowLayout}
                      onCopyLayout={layoutApiRef.current.copyLayout}
                      onPasteLayout={layoutApiRef.current.pasteLayout}
                    />
                  ) : undefined
                }
              />
            )}
          </Sidebar>
        }
      >
        {selectedProject ? (
          <div className="w-full space-y-6">
            <ModularDashboard
              panelDefinitions={allPanelDefs}
              panelContent={panelContent}
              panelDetails={panelDetails}
              onPanelClose={handlePanelClose}
              onLayoutReady={(api) => { layoutApiRef.current = api }}
              onLayoutChange={setDashboardLayout}
              hidePanelPicker
              headerLeft={
                <h1 className="text-2xl font-bold flex items-center gap-2 text-text">
                  {selectedProject.name}
                </h1>
              }
              headerRight={
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => selectedProjectId && void refreshStatus(selectedProjectId)}
                  title="Refresh"
                >
                  <RefreshCw className="w-5 h-5" />
                </Button>
              }
            />
          </div>
        ) : (
          <EmptyState
            icon={<FileText />}
            title="No Project Selected"
            description="Select a project from the sidebar or create a new one to get started."
            action={{ label: 'Add Project', onClick: () => setAddModalOpen(true) }}
          />
        )}
      </AppShell>

      <AddProjectModal
        isOpen={addModalOpen}
        onClose={() => setAddModalOpen(false)}
        onAdd={handleAddProject}
      />
    </>
  )
}

export default App
