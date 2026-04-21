import { useState, useCallback, useEffect, useRef } from 'react'
import {
  useApiClient,
  type DeepAnalysisSchedule,
  type DeepAnalysisRunStatus,
  type TokenBudgetData,
} from '@codrag/ui'

interface UseDeepAnalysisOptions {
  onError?: (msg: string, variant?: 'error' | 'warning' | 'info' | 'success') => void
  /** F-56: per-project config so the schedule is scoped to the selected project. */
  projectConfig?: any
  setProjectConfig?: (config: any) => void
  setConfigDirty?: (dirty: boolean) => void
}

/** Manages deep analysis schedule, run/cancel actions, status polling, and auto-save to backend. */
export function useDeepAnalysis(selectedProjectId: string | null, { onError, projectConfig, setProjectConfig, setConfigDirty }: UseDeepAnalysisOptions = {}) {
  const api = useApiClient()
  const onErrorRef = useRef(onError)
  onErrorRef.current = onError
  const projectConfigRef = useRef(projectConfig)
  projectConfigRef.current = projectConfig
  const setProjectConfigRef = useRef(setProjectConfig)
  setProjectConfigRef.current = setProjectConfig
  const setConfigDirtyRef = useRef(setConfigDirty)
  setConfigDirtyRef.current = setConfigDirty

  // ── State ───────────────────────────────────────────────────
  const DEFAULT_SCHEDULE: DeepAnalysisSchedule = {
    mode: 'manual',
    threshold_percent: 20,
    frequency: 'weekly',
    day_of_week: 0,
    hour: 2,
    budget_enabled: false,
    budget_max_tokens: 50_000,
    budget_max_minutes: 30,
    budget_max_items: 100,
    priority: 'lowest_confidence',
  }
  const [deepAnalysisSchedule, setDeepAnalysisSchedule] = useState<DeepAnalysisSchedule>(DEFAULT_SCHEDULE)
  const [deepAnalysisStatus, setDeepAnalysisStatus] = useState<DeepAnalysisRunStatus>({})
  const [deepAnalysisRunning, setDeepAnalysisRunning] = useState(false)
  const [budgetUsage, setBudgetUsage] = useState<TokenBudgetData | null>(null)
  const [tokenUsageData, setTokenUsageData] = useState<Record<string, { prompt_tokens: number; completion_tokens: number; total_tokens: number }> | null>(null)

  // ── Load saved settings (per-project, fall back to global) ───
  //
  // F-56: deep_analysis_schedule is now scoped per-project, same pattern
  // as enrichmentAutoConfig in useTraceSystem.ts. The previous load only
  // ran on mount and read from the GLOBAL pipeline_config, so switching
  // projects carried over the previous project's schedule. The auto-save
  // effect below also wrote only to the global setting, so changing
  // schedule on project A also changed it on project B.
  //
  // New behavior:
  //   - Read from project.config.deep_analysis_schedule first
  //   - Fall back to global ui_config.deep_analysis + pipeline_config.deep_enrichment.mode
  //     for migration of projects that have never had a per-project schedule
  //   - Persist to project.config.deep_analysis_schedule on every change
  //     (the global write below in the auto-save effect is kept as a default
  //     for new projects + so the daemon-side auto-trigger logic in
  //     api/routers/settings.py:308/332 still has a sane fallback).
  useEffect(() => {
    const projSched = (projectConfig as any)?.deep_analysis_schedule
    if (projSched && typeof projSched === 'object') {
      setDeepAnalysisSchedule({ ...DEFAULT_SCHEDULE, ...projSched })
      return
    }
    // No per-project schedule yet — load global default once
    let cancelled = false
    Promise.all([
      api.getGlobalConfig().catch(() => null),
      api.getSetting('pipeline_config').catch(() => null),
    ]).then(([cfg, pcResult]: [any, any]) => {
      if (cancelled) return
      const saved = cfg?.deep_analysis
      if (saved && typeof saved === 'object') {
        setDeepAnalysisSchedule((prev) => ({ ...prev, ...saved }))
      }
      const pcMode = (pcResult?.value?.deep_enrichment || {}).mode
      if (pcMode === 'manual' || pcMode === 'auto' || pcMode === 'scheduled') {
        setDeepAnalysisSchedule((prev) => prev.mode !== pcMode ? { ...prev, mode: pcMode } : prev)
      }
    }).catch(() => { /* silent — use defaults */ })
    return () => { cancelled = true }
  }, [api, selectedProjectId, projectConfig])

  // ── Reset per-project state on project switch ───────────────
  useEffect(() => {
    setDeepAnalysisStatus({})
    setDeepAnalysisRunning(false)
    setBudgetUsage(null)
    setTokenUsageData(null)
    setDeepAnalysisSchedule(DEFAULT_SCHEDULE)
  }, [selectedProjectId])

  // ── Handlers ────────────────────────────────────────────────

  const fetchDeepAnalysisStatus = useCallback(async () => {
    if (!selectedProjectId) return
    try {
      const status = await api.getDeepAnalysisStatus(selectedProjectId)
      setDeepAnalysisStatus(status)
    } catch {
      // Silent — status not critical
    }
    // Also fetch budget usage
    try {
      const usage = await api.getPipelineBudget(selectedProjectId)
      setBudgetUsage(usage)
    } catch {
      // Silent — budget endpoint may not exist yet
    }
    // Fetch physical token telemetry
    try {
      const res = await api.getTokenUsage(selectedProjectId)
      if (res && res.usage) {
        setTokenUsageData(res.usage)
      }
    } catch {
      // Silent
    }
  }, [api, selectedProjectId])

  const handleRunDeepAnalysis = useCallback(async () => {
    if (!selectedProjectId) return
    setDeepAnalysisRunning(true)
    try {
      await api.runDeepAnalysis(selectedProjectId)
      // Poll for progress updates (every 2s for responsive UI)
      let daInFlight = false
      const poll = setInterval(async () => {
        if (document.hidden || daInFlight) return
        daInFlight = true
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
        } finally {
          daInFlight = false
        }
      }, 2000)
    } catch (e) {
      setDeepAnalysisRunning(false)
      onErrorRef.current?.(e instanceof Error ? e.message : 'Deep analysis failed')
    }
  }, [api, selectedProjectId])

  const handleCancelDeepAnalysis = useCallback(async () => {
    if (!selectedProjectId) return
    try {
      await api.cancelDeepAnalysis(selectedProjectId)
    } catch (e) {
      onErrorRef.current?.(e instanceof Error ? e.message : 'Failed to cancel deep analysis')
    }
  }, [api, selectedProjectId])

  // ── Auto-save schedule to backend ───────────────────────────
  const deepAnalysisInitialMount = useRef(true)
  useEffect(() => {
    if (deepAnalysisInitialMount.current) {
      deepAnalysisInitialMount.current = false
      return
    }
    const timeout = setTimeout(() => {
      // F-56: persist schedule to the SELECTED PROJECT'S config first.
      // Was previously only saved to the global ui_config + pipeline_config
      // which all projects shared.
      const pid = selectedProjectId
      const pCfg = projectConfigRef.current
      if (pid && pCfg) {
        const newProjectConfig: any = {
          ...pCfg,
          deep_analysis_schedule: deepAnalysisSchedule,
        }
        setProjectConfigRef.current?.(newProjectConfig)
        setConfigDirtyRef.current?.(true)
        api.updateProject(pid, { config: newProjectConfig }).catch(() => { /* silent */ })
      }
      // Save full schedule to global config (ui_config) — kept as a default
      // for new projects.
      api.updateGlobalConfig({ deep_analysis: deepAnalysisSchedule }).catch(() => {})
      // Sync to pipeline_config so the daemon-side auto-trigger paths
      // (api/routers/settings.py:308/332) still see a sane default for
      // any project that lacks its own deep_analysis_schedule.
      api.updatePipelineConfig({
        deep_enrichment_mode: deepAnalysisSchedule.mode,
        schedule_frequency: deepAnalysisSchedule.frequency,
        schedule_day_of_week: deepAnalysisSchedule.day_of_week,
        schedule_hour: deepAnalysisSchedule.hour,
        schedule_threshold_enabled: deepAnalysisSchedule.schedule_threshold_enabled,
        schedule_time_enabled: deepAnalysisSchedule.schedule_time_enabled,
        threshold_percent: deepAnalysisSchedule.threshold_percent,
        budget_enabled: deepAnalysisSchedule.budget_enabled,
        budget_max_tokens: deepAnalysisSchedule.budget_max_tokens,
        budget_max_minutes: deepAnalysisSchedule.budget_max_minutes,
        budget_max_items: deepAnalysisSchedule.budget_max_items,
        priority: deepAnalysisSchedule.priority,
      }).catch(() => {})
    }, 500)
    return () => clearTimeout(timeout)
  }, [api, deepAnalysisSchedule, selectedProjectId])

  return {
    deepAnalysisSchedule,
    setDeepAnalysisSchedule,
    deepAnalysisStatus,
    setDeepAnalysisStatus,
    deepAnalysisRunning,
    budgetUsage,
    tokenUsageData,
    fetchDeepAnalysisStatus,
    handleRunDeepAnalysis,
    handleCancelDeepAnalysis,
  }
}
