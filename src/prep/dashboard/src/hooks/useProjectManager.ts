import { useState, useCallback, useMemo, useRef, useEffect } from 'react'
import {
  useApiClient,
  type ProjectListItem,
  type ProjectConfig,
  type ProjectSummary,
  type ProjectStatus,
  type StatusState,
  type ProjectMode,
  type PriorityLevel,
} from '@prep/ui'

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
    activity_status: p.activity_status,
    is_starred: p.config?.is_starred,
    priority_level: (p.config?.priority_level as PriorityLevel | undefined)
      ?? (p.config?.is_starred ? 'boost' : 'none'),
  }
}

const DEFAULT_CONFIG: ProjectConfig = {
  include_globs: ['**/*.md', '**/*.py', '**/*.ts', '**/*.tsx', '**/*.js', '**/*.json'],
  exclude_globs: ['**/.git/**', '**/node_modules/**', '**/__pycache__/**', '**/.venv/**', '**/dist/**', '**/build/**', '**/.next/**'],
  max_file_bytes: 400_000,
  use_gitignore: true,
  trace: { enabled: false },
  auto_rebuild: { enabled: false, debounce_ms: 5000 },
  is_starred: false,
  priority_level: 'none' as PriorityLevel,
  max_branch_backups: 3,
}

// ── Dependencies ─────────────────────────────────────────────

export type ToastVariant = 'error' | 'warning' | 'info' | 'success'

export interface UseProjectManagerDeps {
  onError: (msg: string, variant?: ToastVariant) => void
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
  /** AbortSignal from hydration controller — aborted on project switch */
  signal?: AbortSignal
  /** True while hydration is in progress — suppress polls */
  isHydrating?: boolean
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
  const signalRef = useRef(deps.signal)
  signalRef.current = deps.signal
  const isHydratingRef = useRef(deps.isHydrating)
  isHydratingRef.current = deps.isHydrating

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
      onErrorRef.current(e instanceof Error ? e.message : 'Couldn\u2019t load projects. Check your connection.', 'warning')
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
    setProjectConfig(DEFAULT_CONFIG)
    // Hydrate project status with retry — the daemon may be busy with pipeline
    // work and time out on the first attempt. refreshStatus swallows errors
    // (correct for polling), so we call the API directly for hydration.
    const signal = signalRef.current
    const hydrateStatus = async (pid: string) => {
      const delays = [2000, 4000] // retry after 2s, then 4s
      for (let attempt = 0; attempt <= delays.length; attempt++) {
        if (signal?.aborted) return
        try {
          const status = await api.getProjectStatus(pid)
          if (signal?.aborted) return
          setProjectStatuses((prev) => ({ ...prev, [pid]: status }))
          if (!status.building) {
            setBuildingProjects((prev) => { const next = new Set(prev); next.delete(pid); return next })
          }
          return // success
        } catch {
          if (attempt < delays.length) {
            await new Promise(r => setTimeout(r, delays[attempt]))
          }
        }
      }
    }
    void hydrateStatus(selectedProjectId)
    // Load project config
    api.getProject(selectedProjectId).then((data) => {
      if (signal?.aborted) return
      const cfg = data.project.config
      if (cfg) {
        setProjectConfig((prev) => ({
          include_globs: cfg.include_globs ?? prev.include_globs,
          exclude_globs: cfg.exclude_globs ?? prev.exclude_globs,
          max_file_bytes: cfg.max_file_bytes ?? prev.max_file_bytes,
          use_gitignore: cfg.use_gitignore ?? prev.use_gitignore,
          trace: cfg.trace ?? prev.trace,
          auto_rebuild: cfg.auto_rebuild ?? prev.auto_rebuild,
          // F-65: pass through server-managed fields so per-project
          // Auto/Manual config and deep analysis schedule are available
          // to useTraceSystem and useDeepAnalysis hooks.
          auto_config: cfg.auto_config,
          deep_analysis_schedule: cfg.deep_analysis_schedule,
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

  // ── Auto-poll while building (catches scope-triggered & other auto-builds) ──
  useEffect(() => {
    if (!selectedProjectId) return
    if (isHydratingRef.current) return
    const ps = projectStatuses[selectedProjectId]
    // Only start polling if the backend reports building but we didn't
    // initiate it ourselves (handleBuild already has its own poll loop).
    if (!ps?.building || buildingProjects.has(selectedProjectId)) return

    // F-11: bumped 2s -> 5s, added document.hidden pause + in-flight guard.
    let inFlight = false
    const tick = async () => {
      if (document.hidden || inFlight) return
      inFlight = true
      try {
        const status = await api.getProjectStatus(selectedProjectId)
        setProjectStatuses((prev) => ({ ...prev, [selectedProjectId]: status }))
        if (!status.building) {
          clearInterval(poll)
          setTransientCompleteProjects((prev) => new Set(prev).add(selectedProjectId))
          setTimeout(() => {
            setTransientCompleteProjects((prev) => {
              const next = new Set(prev)
              next.delete(selectedProjectId)
              return next
            })
          }, 5000)
          void fetchFileTreeRef.current?.(selectedProjectId)
        }
      } catch {
        // Silently ignore poll errors
      } finally {
        inFlight = false
      }
    }
    const poll = setInterval(tick, 5000)

    return () => clearInterval(poll)
  }, [api, selectedProjectId, projectStatuses, buildingProjects])

  // ── Actions ──────────────────────────────────────────────────

  const handleAddProject = useCallback(async (path: string, name: string, mode: ProjectMode, indexPath?: string) => {
    try {
      const data = await api.createProject({ path, name, mode, ...(indexPath ? { index_path: indexPath } : {}) })
      setProjects((prev) => [...prev, data.project])
      setSelectedProjectId(data.project.id)
      if (data.warning) {
        onErrorRef.current(data.warning, 'warning')
      }
      return data.project
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Couldn\u2019t add project.'
      onErrorRef.current(msg, 'error')
      throw e
    }
  }, [api])

  const handleArchiveProject = useCallback(async (projectId: string) => {
    try {
      const { project } = await api.archiveProject(projectId)
      setSelectedProjectId((prev) => prev === projectId ? null : prev)
      await refreshProjects()
      return project
    } catch (e) {
      onErrorRef.current(e instanceof Error ? e.message : 'Couldn\u2019t archive project.', 'error')
      throw e
    }
  }, [api, refreshProjects])

  const handleUnarchiveProject = useCallback(async (projectId: string) => {
    try {
      const { project } = await api.unarchiveProject(projectId)
      await refreshProjects()
      return project
    } catch (e) {
      onErrorRef.current(e instanceof Error ? e.message : 'Couldn\u2019t unarchive project.', 'error')
      throw e
    }
  }, [api, refreshProjects])

  const handleDeleteProject = useCallback(async (projectId: string, purge: boolean = false) => {
    try {
      await api.deleteProject(projectId, purge)
      setProjects((prev) => prev.filter((p) => p.id !== projectId))
      setSelectedProjectId((prev) => prev === projectId ? null : prev)
      // Re-fetch to ensure list is synchronized with backend
      await refreshProjects()
    } catch (e) {
      onErrorRef.current(e instanceof Error ? e.message : 'Couldn\u2019t delete project.', 'error')
    }
  }, [api, refreshProjects])

  const handleBuild = useCallback(async () => {
    if (!selectedProjectId) return
    const paths = [...(includedPathsRef.current ?? [])]
    // If the frontend has explicit selections, send them.
    // Otherwise, pass undefined so the backend falls back to the
    // project config's stored included_paths (which may have been
    // set in a previous session or by the watcher).
    const sendPaths = paths.length > 0 ? paths : undefined
    try {
      setBuildingProjects((prev) => new Set(prev).add(selectedProjectId))
      await api.buildProject(selectedProjectId, false, sendPaths)
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
      onErrorRef.current(e instanceof Error ? e.message : 'Build failed — check logs for details.', 'error')
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
          hard_limit_bytes: projectConfig.hard_limit_bytes,
          active: projectConfig.active,
          use_gitignore: projectConfig.use_gitignore,
          trace: projectConfig.trace,
          auto_rebuild: projectConfig.auto_rebuild,
          graph_engine: projectConfig.graph_engine,
          advanced: projectConfig.advanced,
        },
      })
      setConfigDirty(false)
    } catch (e) {
      onErrorRef.current(e instanceof Error ? e.message : 'Couldn\u2019t save settings. Please try again.', 'warning')
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

  const handleToggleActive = useCallback(async (projectId: string, active: boolean, touch: boolean = false) => {
    // Optimistic UI update: immediately update the project summary activity_status so the toggle is responsive
    setProjects(prev => prev.map(p => {
      if (p.id === projectId) {
        return {
          ...p,
          // If we are making it active, just say active. If we are turning it off, it's inactive.
          // Note: free tier projects can't be toggled, so this only runs on Pro tier projects anyway.
          activity_status: active ? 'active' : 'inactive',
          config: { ...(p.config || {}), active } as ProjectConfig
        };
      }
      return p;
    }));

    if (projectId === selectedProject?.id) {
      setProjectConfig(prev => ({ ...prev, active }));
    }

    try {
      // F-69: When deactivating, cancel running pipelines FIRST (fire-and-forget).
      // The pipeline cancel is async — the UI toggle is already optimistic.
      if (!active) {
        api.cancelPipeline(projectId, 'fast_sync').catch(() => {});
        api.cancelPipeline(projectId, 'deep_enrichment').catch(() => {});
        api.cancelPipeline(projectId, 'finalize').catch(() => {});
      }
      // Send the active flag directly — F-63 merge preserves other config fields
      const res = await api.updateProject(projectId, {
        config: { active },
        touch, // If true, bumps updated_at (needed for Free tier slot stealing)
      });
      // Refresh to ensure we have the authoritative state
      refreshProjects();
      
      // If the backend sent a warning (e.g. for performance limit), show it as a toast
      if (res.warning) {
        onErrorRef.current(res.warning, 'warning');
      }
    } catch (e) {
      // Revert on error
      refreshProjects();
      onErrorRef.current(e instanceof Error ? e.message : 'Couldn\u2019t update project status. Please try again.', 'warning');
    }
  }, [api, refreshProjects]);

  const handleToggleStar = useCallback(async (projectId: string, isStarred: boolean) => {
    setProjects(prev => prev.map(p => {
      if (p.id === projectId) {
        return {
          ...p,
          config: { ...p.config, is_starred: isStarred } as ProjectConfig
        };
      }
      return p;
    }));

    if (projectId === selectedProject?.id) {
      setProjectConfig(prev => ({ ...prev, is_starred: isStarred }));
    }

    try {
      const { project } = await api.getProject(projectId);
      await api.updateProject(projectId, {
        config: {
          ...(project.config || {}),
          is_starred: isStarred,
        },
        touch: false, // Don't bump updated_at just for starring
      });
      refreshProjects();
    } catch (e) {
      refreshProjects();
      onErrorRef.current(e instanceof Error ? e.message : 'Couldn\u2019t update starred status. Please try again.', 'warning');
    }
  }, [api, refreshProjects]);

  /** Cycle priority: none → boost → exclusive → none. */
  const handleCyclePriority = useCallback(async (projectId: string) => {
    // Read current level from local state
    const currentProject = projects.find((p: ProjectListItem) => p.id === projectId);
    const currentConfig = currentProject?.config;
    const currentLevel: PriorityLevel = (currentConfig?.priority_level as PriorityLevel | undefined)
      ?? (currentConfig?.is_starred ? 'boost' : 'none');
    const next: PriorityLevel = currentLevel === 'none' ? 'boost'
      : currentLevel === 'boost' ? 'exclusive'
      : 'none';

    // Optimistic: update local state immediately
    setProjects(prev => prev.map(p => {
      if (p.id === projectId) {
        return {
          ...p,
          config: {
            ...p.config,
            is_starred: next !== 'none',
            priority_level: next,
          } as ProjectConfig
        };
      }
      // If setting exclusive, clear any other project's exclusive status
      if (next === 'exclusive' && (p.config?.priority_level as PriorityLevel) === 'exclusive') {
        return {
          ...p,
          config: {
            ...p.config,
            is_starred: false,
            priority_level: 'none' as PriorityLevel,
          } as ProjectConfig
        };
      }
      return p;
    }));

    if (projectId === selectedProject?.id) {
      setProjectConfig(prev => ({ ...prev, is_starred: next !== 'none', priority_level: next }));
    } else if (next === 'exclusive' && selectedProject?.config?.priority_level === 'exclusive') {
      // We just took exclusive lock from the currently selected project
      setProjectConfig(prev => ({ ...prev, is_starred: false, priority_level: 'none' }));
    }

    try {
      const { project } = await api.getProject(projectId);
      await api.updateProject(projectId, {
        config: {
          ...(project.config || {}),
          is_starred: next !== 'none',
          priority_level: next,
        },
        touch: false,
      });
      refreshProjects();
    } catch (e) {
      refreshProjects();
      onErrorRef.current(e instanceof Error ? e.message : 'Couldn\u2019t update priority. Please try again.', 'warning');
    }
  }, [api, projects, refreshProjects]);

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
    handleArchiveProject,
    handleUnarchiveProject,
    handleDeleteProject,
    handleBuild,
    handleSaveConfig,
    handleProjectConfigChange,
    handleDetectStack,
    handleToggleActive,
    handleToggleStar,
    handleCyclePriority,
    // Internal setters needed by other hooks (e.g. useTraceSystem needs setProjectConfig)
    setProjectConfig,
    setConfigDirty,
  }
}
