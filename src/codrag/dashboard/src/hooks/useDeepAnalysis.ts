import { useState, useCallback, useEffect, useRef } from 'react'
import {
  useApiClient,
  type DeepAnalysisSchedule,
  type DeepAnalysisRunStatus,
} from '@codrag/ui'

interface UseDeepAnalysisOptions {
  onError?: (msg: string) => void
}

export function useDeepAnalysis(selectedProjectId: string | null, { onError }: UseDeepAnalysisOptions = {}) {
  const api = useApiClient()
  const onErrorRef = useRef(onError)
  onErrorRef.current = onError

  // ── State ───────────────────────────────────────────────────
  const [deepAnalysisSchedule, setDeepAnalysisSchedule] = useState<DeepAnalysisSchedule>({
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
  })
  const [deepAnalysisStatus, setDeepAnalysisStatus] = useState<DeepAnalysisRunStatus>({})
  const [deepAnalysisRunning, setDeepAnalysisRunning] = useState(false)

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
      api.updateGlobalConfig({ deep_analysis: deepAnalysisSchedule }).catch(() => {})
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
