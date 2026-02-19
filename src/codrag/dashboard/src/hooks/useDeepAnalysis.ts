import { useState, useCallback, useEffect, useRef } from 'react'
import {
  useApiClient,
  type DeepAnalysisSchedule,
  type DeepAnalysisRunStatus,
} from '@codrag/ui'

interface UseDeepAnalysisOptions {
  onError?: (msg: string) => void
}

/** Manages deep analysis schedule, run/cancel actions, status polling, and auto-save to backend. */
export function useDeepAnalysis(selectedProjectId: string | null, { onError }: UseDeepAnalysisOptions = {}) {
  const api = useApiClient()
  const onErrorRef = useRef(onError)
  onErrorRef.current = onError

  // ── State ───────────────────────────────────────────────────
  const DEFAULT_SCHEDULE: DeepAnalysisSchedule = {
    mode: 'manual',
    threshold_percent: 20,
    frequency: 'weekly',
    day_of_week: 0,
    hour: 2,
    budget_enabled: true,
    budget_max_tokens: 50_000,
    budget_max_minutes: 30,
    budget_max_items: 100,
    priority: 'lowest_confidence',
  }
  const [deepAnalysisSchedule, setDeepAnalysisSchedule] = useState<DeepAnalysisSchedule>(DEFAULT_SCHEDULE)
  const [deepAnalysisStatus, setDeepAnalysisStatus] = useState<DeepAnalysisRunStatus>({})
  const [deepAnalysisRunning, setDeepAnalysisRunning] = useState(false)

  // ── Load saved settings from backend on init ─────────────────
  useEffect(() => {
    let cancelled = false
    Promise.all([
      api.getGlobalConfig().catch(() => null),
      api.getSetting('pipeline_config').catch(() => null),
    ]).then(([cfg, pcResult]: [any, any]) => {
      if (cancelled) return
      // Load schedule details from deep_analysis (ui_config)
      const saved = cfg?.deep_analysis
      if (saved && typeof saved === 'object') {
        setDeepAnalysisSchedule((prev) => ({ ...prev, ...saved }))
      }
      // Prefer pipeline_config mode as authoritative (backend reads this)
      const pcMode = (pcResult?.value?.deep_enrichment || {}).mode
      if (pcMode === 'manual' || pcMode === 'auto' || pcMode === 'scheduled') {
        setDeepAnalysisSchedule((prev) => prev.mode !== pcMode ? { ...prev, mode: pcMode } : prev)
      }
    }).catch(() => { /* silent — use defaults */ })
    return () => { cancelled = true }
  }, [api])

  // ── Handlers ────────────────────────────────────────────────

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
      // Poll for progress updates (every 2s for responsive UI)
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
  const deepAnalysisSkipRef = useRef(0)
  useEffect(() => {
    if (deepAnalysisSkipRef.current < 2) {
      deepAnalysisSkipRef.current++
      return
    }
    const timeout = setTimeout(() => {
      // Save full schedule to global config (ui_config)
      api.updateGlobalConfig({ deep_analysis: deepAnalysisSchedule }).catch(() => {})
      // Sync to pipeline_config so backend has all schedule data
      api.updatePipelineConfig({
        deep_enrichment_mode: deepAnalysisSchedule.mode,
        schedule_frequency: deepAnalysisSchedule.frequency,
        schedule_day_of_week: deepAnalysisSchedule.day_of_week,
        schedule_hour: deepAnalysisSchedule.hour,
        schedule_threshold_enabled: deepAnalysisSchedule.schedule_threshold_enabled,
        schedule_time_enabled: deepAnalysisSchedule.schedule_time_enabled,
        threshold_percent: deepAnalysisSchedule.threshold_percent,
        budget_max_tokens: deepAnalysisSchedule.budget_max_tokens,
        budget_max_minutes: deepAnalysisSchedule.budget_max_minutes,
        budget_max_items: deepAnalysisSchedule.budget_max_items,
      }).catch(() => {})
    }, 500)
    return () => clearTimeout(timeout)
  }, [api, deepAnalysisSchedule])

  return {
    deepAnalysisSchedule,
    setDeepAnalysisSchedule,
    deepAnalysisStatus,
    setDeepAnalysisStatus,
    deepAnalysisRunning,
    fetchDeepAnalysisStatus,
    handleRunDeepAnalysis,
    handleCancelDeepAnalysis,
  }
}
