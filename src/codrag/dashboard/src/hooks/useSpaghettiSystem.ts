import { useState, useCallback, useEffect } from 'react'
import { useApiClient } from '@codrag/ui'
import type { SpaghettiFileScore } from '@codrag/ui'

export interface UseSpaghettiSystemReturn {
  spaghettiFiles: SpaghettiFileScore[]
  spaghettiFileCount: number
  spaghettiScoredCount: number
  spaghettiSeverityCounts: Record<string, number>
  spaghettiLoading: boolean
  handleSpaghettiRefresh: () => void
}

export function useSpaghettiSystem(selectedProjectId: string | null): UseSpaghettiSystemReturn {
  const api = useApiClient()

  const [files, setFiles] = useState<SpaghettiFileScore[]>([])
  const [fileCount, setFileCount] = useState(0)
  const [scoredCount, setScoredCount] = useState(0)
  const [severityCounts, setSeverityCounts] = useState<Record<string, number>>({})
  const [loading, setLoading] = useState(false)

  const fetchScores = useCallback((projectId: string, refresh = false) => {
    setLoading(true)
    api.getSpaghettiScores(projectId, { limit: 100, refresh })
      .then((r) => {
        setFiles(r.files || [])
        setFileCount(r.file_count || 0)
        setScoredCount(r.scored_count || 0)
        setSeverityCounts(r.severity_counts || {})
      })
      .catch(() => {
        // Clear state on error so stale data from a previous project isn't shown
        setFiles([])
        setFileCount(0)
        setScoredCount(0)
        setSeverityCounts({})
      })
      .finally(() => setLoading(false))
  }, [api])

  // Hydrate on project change
  useEffect(() => {
    // Always clear previous project's data immediately to prevent cross-contamination
    setFiles([])
    setFileCount(0)
    setScoredCount(0)
    setSeverityCounts({})

    if (!selectedProjectId) return

    fetchScores(selectedProjectId)
  }, [selectedProjectId, fetchScores])

  const handleSpaghettiRefresh = useCallback(() => {
    if (!selectedProjectId) return
    fetchScores(selectedProjectId, true)
  }, [selectedProjectId, fetchScores])

  return {
    spaghettiFiles: files,
    spaghettiFileCount: fileCount,
    spaghettiScoredCount: scoredCount,
    spaghettiSeverityCounts: severityCounts,
    spaghettiLoading: loading,
    handleSpaghettiRefresh,
  }
}
