import { useState, useCallback, useRef } from 'react'
import { useApiClient, type WatchStatus } from '@codrag/ui'

interface UseWatchSystemOptions {
  onError?: (msg: string) => void
}

/** Manages file watch system: start/stop controls, status refresh, and loading state. */
export function useWatchSystem(selectedProjectId: string | null, { onError }: UseWatchSystemOptions = {}) {
  const api = useApiClient()
  const onErrorRef = useRef(onError)
  onErrorRef.current = onError

  // ── State ───────────────────────────────────────────────────
  const [watchStatus, setWatchStatus] = useState<WatchStatus>({
    enabled: false,
    state: 'disabled',
    stale: false,
    pending: false,
  })
  const [watchLoading, setWatchLoading] = useState(false)

  // ── Handlers ────────────────────────────────────────────────

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
      onErrorRef.current?.(e instanceof Error ? e.message : 'Failed to start watch')
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
      onErrorRef.current?.(e instanceof Error ? e.message : 'Failed to stop watch')
    } finally {
      setWatchLoading(false)
    }
  }, [api, selectedProjectId, refreshWatchStatus])

  return {
    watchStatus,
    watchLoading,
    refreshWatchStatus,
    handleStartWatch,
    handleStopWatch,
  }
}
