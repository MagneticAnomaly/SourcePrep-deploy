import { useEffect, useRef, useState, useCallback } from 'react'
import { useApiClient, type PipelineHealth } from '@codrag/ui'

const POLL_MS = 10_000 // 10s — health is a slow-moving aggregate

export interface UsePipelineHealthReturn {
  health: PipelineHealth | null
  refetch: () => Promise<void>
  clearBarrier: () => Promise<void>
}

/**
 * Lightweight polling for /pipeline/health.
 *
 * - Polls every 10s when panelVisible is true and a project is selected.
 * - Skips when document.hidden or another fetch is in flight.
 * - Resets state on project change.
 * - Returns refetch() for action-triggered refresh (e.g. after a stage restore).
 * - Returns clearBarrier() that calls the DELETE endpoint then refetches.
 */
export function usePipelineHealth(
  projectId: string | null,
  panelVisible: boolean,
): UsePipelineHealthReturn {
  const api = useApiClient()
  const [health, setHealth] = useState<PipelineHealth | null>(null)
  const inFlightRef = useRef(false)
  // Capture latest projectId so async fetches can guard against project-switch races
  const latestProjectIdRef = useRef(projectId)
  useEffect(() => {
    latestProjectIdRef.current = projectId
  }, [projectId])

  const refetch = useCallback(async () => {
    if (!projectId) return
    if (inFlightRef.current) return
    inFlightRef.current = true
    try {
      const next = await api.getPipelineHealth(projectId)
      if (latestProjectIdRef.current === projectId) setHealth(next)
    } catch {
      // silent — health is informational, not a hard failure surface
    } finally {
      inFlightRef.current = false
    }
  }, [api, projectId])

  const clearBarrier = useCallback(async () => {
    if (!projectId) return
    try {
      await api.clearResetBarrier(projectId)
    } catch {
      // surfaced via subsequent refetch returning barrier still active
    }
    await refetch()
  }, [api, projectId, refetch])

  // Reset state on project change
  useEffect(() => {
    setHealth(null)
  }, [projectId])

  // Poll
  useEffect(() => {
    if (!projectId) return
    if (!panelVisible) return

    // Initial fetch
    void refetch()

    const tick = () => {
      if (document.hidden) return
      void refetch()
    }
    const interval = setInterval(tick, POLL_MS)
    return () => clearInterval(interval)
  }, [projectId, panelVisible, refetch])

  return { health, refetch, clearBarrier }
}
