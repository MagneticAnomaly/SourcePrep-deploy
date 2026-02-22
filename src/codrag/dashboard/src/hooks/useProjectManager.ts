import { useState, useCallback, useMemo, useRef, useEffect } from 'react'
import {
  useApiClient,
  type ProjectListItem,
  type ProjectConfig,
  type ProjectSummary,
  type ProjectStatus,
  type StatusState,
  type ProjectMode,
} from '@codrag/ui'

// ── Helpers ──────────────────────────────────────────────────

function deriveStatus(ps: ProjectStatus | null, building: boolean): StatusState {
  if (building) return 'building'
  if (!ps) return 'pending'
  if (ps.building) return 'building'
  if (ps.stale) return 'stale'
  if (ps.index.exists) return 'fresh'
  return 'pending'
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

const DEFAULT_CONFIG: ProjectConfig = {
  include_globs: ['**/*.md', '**/*.py', '**/*.ts', '**/*.tsx', '**/*.js', '**/*.json'],
  exclude_globs: ['**/.git/**', '**/node_modules/**', '**/__pycache__/**', '**/.venv/**', '**/dist/**', '**/build/**', '**/.next/**'],
  max_file_bytes: 400_000,
  use_gitignore: true,
  trace: { enabled: false },
  auto_rebuild: { enabled: false, debounce_ms: 5000 },
}

// ── Dependencies ─────────────────────────────────────────────

export interface UseProjectManagerDeps {
  onError: (msg: string) => void
  /** Start the file watcher (for auto-rebuild after build) */
  handleStartWatch?: () => Promise<void>
  /** Refresh watch status after watcher state change */
  refreshWatchStatus?: (projectId: string) => Promise<void>
  /** Refresh file tree after build completes */
  fetchFileTree?: (projectId: string) => Promise<void>
  /** Currently included paths in file tree (for selective build) */
  includedPaths?: Set<string>
  /** Whether auto-rebuild is enabled */
  indexAutoRebuild?: boolean
}

// ── Hook ─────────────────────────────────────────────────────

/**
 * Manages project list, selection, config, and build operations.
 * Self-hydrates project config on project change.
 * Extracted from App.tsx as part of SM-1 Phase C1.
 */
export function useProjectManager(deps: UseProjectManagerDeps) {
  const api = useApiClient()

  // Stable refs for callback deps that shouldn't trigger re-renders
  const onErrorRef = useRef(deps.onError)
  onErrorRef.current = deps.onError
  const startWatchRef = useRef(deps.handleStartWatch)
  startWatchRef.current = deps.handleStartWatch
  const refreshWatchRef = useRef(deps.refreshWatchStatus)
  refreshWatchRef.current = deps.refreshWatchStatus
  const fetchFileTreeRef = useRef(deps.fetchFileTree)
  fetchFileTreeRef.current = deps.fetchFileTree
  const includedPathsRef = useRef(deps.includedPaths)
  includedPathsRef.current = deps.includedPaths
  const indexAutoRebuildRef = useRef(deps.indexAutoRebuild)
  indexAutoRebuildRef.current = deps.indexAutoRebuild

  // ── State ────────────────────────────────────────────────────

  const [projects, setProjects] = useState<ProjectListItem[]>([])
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null)
  const [projectStatuses, setProjectStatuses] = useState<Record<string, ProjectStatus>>({})
  const [buildingProjects, setBuildingProjects] = useState<Set<string>>(new Set())
  const [transientCompleteProjects, setTransientCompleteProjects] = useState<Set<string>>(new Set())
  const [projectConfig, setProjectConfig] = useState<ProjectConfig>(DEFAULT_CONFIG)
  const [configDirty, setConfigDirty] = useState(false)

  // ── Fetch ────────────────────────────────────────────────────

  const refreshProjects = useCallback(async () => {
    try {
      const data = await api.listProjects()
      setProjects(data.projects)
    } catch (e) {
      onErrorRef.current(e instanceof Error ? e.message : 'Failed to list projects')
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

  // ── Self-hydrate on project change ───────────────────────────

  useEffect(() => {
    if (!selectedProjectId) return
    void refreshStatus(selectedProjectId)
    // Load project config
    api.getProject(selectedProjectId).then((data) => {
      const cfg = data.project.config
      if (cfg) {
        setProjectConfig((prev) => ({
          include_globs: cfg.include_globs ?? prev.include_globs,
          exclude_globs: cfg.exclude_globs ?? prev.exclude_globs,
          max_file_bytes: cfg.max_file_bytes ?? prev.max_file_bytes,
          use_gitignore: cfg.use_gitignore ?? prev.use_gitignore,
          trace: cfg.trace ?? prev.trace,
          auto_rebuild: cfg.auto_rebuild ?? prev.auto_rebuild,
        }))
        setConfigDirty(false)
      }
    }).catch(() => {})
  }, [api, selectedProjectId, refreshStatus])

  // Auto-select first project
  useEffect(() => {
    if (!selectedProjectId && projects.length > 0) {
      setSelectedProjectId(projects[0].id)
    }
  }, [projects, selectedProjectId])

  // ── Actions ──────────────────────────────────────────────────

  const handleAddProject = useCallback(async (path: string, name: string, mode: ProjectMode, indexPath?: string) => {
    try {
      const data = await api.createProject({ path, name, mode, ...(indexPath ? { index_path: indexPath } : {}) })
      setProjects((prev) => [...prev, data.project])
      setSelectedProjectId(data.project.id)
      return data.project
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Failed to add project'
      onErrorRef.current(msg)
      throw e
    }
  }, [api])

  const handleDeleteProject = useCallback(async (projectId: string) => {
    try {
      await api.deleteProject(projectId)
      setProjects((prev) => prev.filter((p) => p.id !== projectId))
      setSelectedProjectId((prev) => prev === projectId ? null : prev)
    } catch (e) {
      onErrorRef.current(e instanceof Error ? e.message : 'Failed to delete project')
    }
  }, [api])

  const handleBuild = useCallback(async () => {
    if (!selectedProjectId) return
    try {
      setBuildingProjects((prev) => new Set(prev).add(selectedProjectId))
      const paths = [...(includedPathsRef.current ?? [])]
      await api.buildProject(selectedProjectId, false, paths.length > 0 ? paths : undefined)
      // Poll status until build completes
      const poll = setInterval(async () => {
        try {
          const status = await api.getProjectStatus(selectedProjectId)
          setProjectStatuses((prev) => ({ ...prev, [selectedProjectId]: status }))
          if (!status.building) {
            clearInterval(poll)
            setBuildingProjects((prev) => {
              const next = new Set(prev)
              next.delete(selectedProjectId)
              return next
            })
            // Transient complete state for 5s
            setTransientCompleteProjects((prev) => new Set(prev).add(selectedProjectId))
            setTimeout(() => {
              setTransientCompleteProjects((prev) => {
                const next = new Set(prev)
                next.delete(selectedProjectId)
                return next
              })
            }, 5000)
            void refreshStatus(selectedProjectId)
            void fetchFileTreeRef.current?.(selectedProjectId)
            if (indexAutoRebuildRef.current) {
              startWatchRef.current?.().then(() => refreshWatchRef.current?.(selectedProjectId)).catch(() => {})
            }
          }
        } catch (e) {
          console.warn('Poll failed', e)
        }
      }, 2000)
    } catch (e) {
      setBuildingProjects((prev) => {
        const next = new Set(prev)
        next.delete(selectedProjectId)
        return next
      })
      onErrorRef.current(e instanceof Error ? e.message : 'Build failed')
    }
  }, [api, selectedProjectId, refreshStatus])

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
      onErrorRef.current(e instanceof Error ? e.message : 'Failed to save config')
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

  // ── Derived ──────────────────────────────────────────────────

  const selectedProject = useMemo(
    () => projects.find((p) => p.id === selectedProjectId) ?? null,
    [projects, selectedProjectId],
  )

  const projectStatus = selectedProjectId ? projectStatuses[selectedProjectId] ?? null : null

  const projectSummaries = useMemo(
    () => projects.map((p) => toProjectSummary(p, projectStatuses[p.id] ?? null, buildingProjects.has(p.id))),
    [projects, projectStatuses, buildingProjects],
  )

  // ── Return ───────────────────────────────────────────────────

  return {
    // State (read-only)
    projects,
    selectedProjectId,
    selectedProject,
    projectStatus,
    projectSummaries,
    projectConfig,
    configDirty,
    buildingProjects,
    transientCompleteProjects,
    // Selection
    setSelectedProjectId,
    // Fetch
    refreshProjects,
    refreshStatus,
    // Actions
    handleAddProject,
    handleDeleteProject,
    handleBuild,
    handleSaveConfig,
    handleProjectConfigChange,
    handleDetectStack,
    // Internal setters needed by other hooks (e.g. useTraceSystem needs setProjectConfig)
    setProjectConfig,
    setConfigDirty,
  }
}
