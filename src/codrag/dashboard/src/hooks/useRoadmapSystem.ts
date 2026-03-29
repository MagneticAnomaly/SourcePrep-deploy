import { useState, useCallback, useEffect, useRef } from 'react'
import { useApiClient } from '@codrag/ui'
import type { RoadmapResponse, RoadmapTier, VelocityResponse, SprintSuggestion } from '@codrag/ui'

export interface UseRoadmapSystemReturn {
  state: RoadmapResponse | null
  velocityData: VelocityResponse | null
  sprintSuggestion: SprintSuggestion | null
  loadingSprint: boolean
  handleGenerate: () => void
  handleScanTodos: () => void
  handleUpdateEthos: (ethos: string) => void
  handlePromoteNode: (nodeId: string, targetTier: RoadmapTier) => void
  handleDismissNode: (nodeId: string) => void
  handleDeleteNode: (nodeId: string) => void
  handleCreateNode: (node: { title: string; description?: string; tier?: string; category?: string; priority?: string }) => void
  handleAnswerQuestion: (questionId: string, answer: string) => void
  handleSyncGitHub: () => void
  handleMineRoadmap: () => void
  handlePushNodeToGitHub: (nodeId: string) => void
  handleSuggestSprint: () => void
}

export function useRoadmapSystem(selectedProjectId: string | null): UseRoadmapSystemReturn {
  const api = useApiClient()

  const [state, setState] = useState<RoadmapResponse | null>(null)
  const pollRef = useRef<NodeJS.Timeout | null>(null)

  // Clean up polling on unmount or project change
  useEffect(() => {
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current)
        pollRef.current = null
      }
    }
  }, [selectedProjectId])

  // Hydrate roadmap data on project change
  useEffect(() => {
    setState(null)
    if (!selectedProjectId) return

    api.getRoadmap(selectedProjectId)
      .then((s) => setState(s))
      .catch(() => {})
  }, [selectedProjectId, api])

  // Poll helper: watches for generating/scanning to finish
  const startPolling = useCallback(() => {
    if (!selectedProjectId) return
    if (pollRef.current) clearInterval(pollRef.current)
    pollRef.current = setInterval(() => {
      api.getRoadmap(selectedProjectId)
        .then((s) => {
          setState(s)
          if (!s.generating && !s.scanning) {
            if (pollRef.current) clearInterval(pollRef.current)
            pollRef.current = null
          }
        })
        .catch(() => {
          if (pollRef.current) clearInterval(pollRef.current)
          pollRef.current = null
        })
    }, 2000)
  }, [selectedProjectId, api])

  const handleGenerate = useCallback(() => {
    if (!selectedProjectId) return
    setState((prev) => prev ? { ...prev, generating: true, error: null } : null)

    api.generateRoadmapProposals(selectedProjectId)
      .then(() => startPolling())
      .catch(() => setState((prev) => prev ? { ...prev, generating: false, error: 'Failed to start generation' } : null))
  }, [selectedProjectId, api, startPolling])

  const handleScanTodos = useCallback(() => {
    if (!selectedProjectId) return
    setState((prev) => prev ? { ...prev, scanning: true, error: null } : null)

    api.scanRoadmapTodos(selectedProjectId)
      .then(() => startPolling())
      .catch(() => setState((prev) => prev ? { ...prev, scanning: false, error: 'Failed to start TODO scan' } : null))
  }, [selectedProjectId, api, startPolling])

  const handleUpdateEthos = useCallback((ethos: string) => {
    if (!selectedProjectId) return
    setState((prev) => prev ? { ...prev, app_ethos: ethos } : null)

    api.updateRoadmapEthos(selectedProjectId, ethos)
      .catch(() => {})
  }, [selectedProjectId, api])

  const handlePromoteNode = useCallback((nodeId: string, targetTier: RoadmapTier) => {
    if (!selectedProjectId) return
    // Optimistic: move node to target tier
    setState((prev) => {
      if (!prev) return null
      return {
        ...prev,
        nodes: prev.nodes.map((n) =>
          n.id === nodeId ? { ...n, tier: targetTier, state: targetTier === 'completed' ? 'completed' as const : 'accepted' as const } : n
        ),
      }
    })

    api.updateRoadmapNode(selectedProjectId, nodeId, { tier: targetTier, state: targetTier === 'completed' ? 'completed' : 'accepted' })
      .then(() => {
        // Refresh velocity when tier changes (especially promote to completed)
        if (targetTier === 'completed') {
          api.getVelocity(selectedProjectId).then(setVelocityData).catch(() => {})
        }
      })
      .catch(() => {
        api.getRoadmap(selectedProjectId).then(setState).catch(() => {})
      })
  }, [selectedProjectId, api])

  const handleDismissNode = useCallback((nodeId: string) => {
    if (!selectedProjectId) return
    setState((prev) => {
      if (!prev) return null
      return {
        ...prev,
        nodes: prev.nodes.map((n) =>
          n.id === nodeId ? { ...n, state: 'dismissed' as const } : n
        ),
      }
    })

    api.updateRoadmapNode(selectedProjectId, nodeId, { state: 'dismissed' } as any)
      .catch(() => {
        api.getRoadmap(selectedProjectId).then(setState).catch(() => {})
      })
  }, [selectedProjectId, api])

  const handleDeleteNode = useCallback((nodeId: string) => {
    if (!selectedProjectId) return
    setState((prev) => {
      if (!prev) return null
      return {
        ...prev,
        nodes: prev.nodes.filter((n) => n.id !== nodeId),
      }
    })

    api.deleteRoadmapNode(selectedProjectId, nodeId)
      .catch(() => {
        api.getRoadmap(selectedProjectId).then(setState).catch(() => {})
      })
  }, [selectedProjectId, api])

  const handleCreateNode = useCallback((node: { title: string; description?: string; tier?: string; category?: string; priority?: string }) => {
    if (!selectedProjectId) return

    api.createRoadmapNode(selectedProjectId, node)
      .then(() => {
        // Re-fetch to get the full node with generated ID
        api.getRoadmap(selectedProjectId).then(setState).catch(() => {})
      })
      .catch(() => {})
  }, [selectedProjectId, api])

  const handleAnswerQuestion = useCallback((questionId: string, answer: string) => {
    if (!selectedProjectId) return
    setState((prev) => {
      if (!prev) return null
      return {
        ...prev,
        questions: prev.questions.map((q) =>
          q.id === questionId ? { ...q, answer, answered: true } : q
        ),
      }
    })

    api.answerRoadmapQuestion(selectedProjectId, questionId, answer)
      .catch(() => {
        api.getRoadmap(selectedProjectId).then(setState).catch(() => {})
      })
  }, [selectedProjectId, api])

  // ── Phase 59D: GitHub Sync + Mining ────────────────────────────

  const handleSyncGitHub = useCallback(() => {
    if (!selectedProjectId) return
    setState((prev) => prev ? { ...prev, error: null } : null)

    api.syncGitHub(selectedProjectId)
      .then(() => startPolling())
      .catch(() => setState((prev) => prev ? { ...prev, error: 'Failed to start GitHub sync' } : null))
  }, [selectedProjectId, api, startPolling])

  const handleMineRoadmap = useCallback(() => {
    if (!selectedProjectId) return
    setState((prev) => prev ? { ...prev, error: null } : null)

    api.mineRoadmap(selectedProjectId)
      .then(() => startPolling())
      .catch(() => setState((prev) => prev ? { ...prev, error: 'Failed to start pipeline mining' } : null))
  }, [selectedProjectId, api, startPolling])


  const [velocityData, setVelocityData] = useState<VelocityResponse | null>(null)
  const [sprintSuggestion, setSprintSuggestion] = useState<SprintSuggestion | null>(null)
  const [loadingSprint, setLoadingSprint] = useState(false)

  // Fetch velocity whenever project changes
  useEffect(() => {
    setVelocityData(null)
    setSprintSuggestion(null)
    if (!selectedProjectId) return

    api.getVelocity(selectedProjectId)
      .then(setVelocityData)
      .catch(() => {
        // Velocity endpoint may not exist on older servers — degrade gracefully
      })
  }, [selectedProjectId, api])

  const handleSuggestSprint = useCallback(() => {
    if (!selectedProjectId) return
    setLoadingSprint(true)
    api.suggestSprint(selectedProjectId)
      .then(setSprintSuggestion)
      .catch(() => {})
      .finally(() => setLoadingSprint(false))
  }, [selectedProjectId, api])

  const handlePushNodeToGitHub = useCallback((nodeId: string) => {
    if (!selectedProjectId) return
    api.pushToGitHub(selectedProjectId, [nodeId])
      .then(() => {
        // Refresh roadmap to get updated source_ref, and velocity (new completion may affect it)
        api.getRoadmap(selectedProjectId).then(setState).catch(() => {})
        api.getVelocity(selectedProjectId).then(setVelocityData).catch(() => {})
      })
      .catch(() => setState((prev) => prev ? { ...prev, error: 'Failed to push node to GitHub' } : null))
  }, [selectedProjectId, api])

  return {
    state,
    velocityData,
    sprintSuggestion,
    loadingSprint,
    handleGenerate,
    handleScanTodos,
    handleUpdateEthos,
    handlePromoteNode,
    handleDismissNode,
    handleDeleteNode,
    handleCreateNode,
    handleAnswerQuestion,
    handleSyncGitHub,
    handleMineRoadmap,
    handlePushNodeToGitHub,
    handleSuggestSprint,
  }
}
