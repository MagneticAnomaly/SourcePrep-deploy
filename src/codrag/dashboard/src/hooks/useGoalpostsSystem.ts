import { useState, useCallback, useEffect, useRef } from 'react'
import { useApiClient } from '@codrag/ui'
import type { GoalpostsResponse } from '@codrag/ui'

export interface UseGoalpostsSystemReturn {
  state: GoalpostsResponse | null
  handleGenerate: () => void
  handleUpdateIntent: (intent: string) => void
  handleApprove: (proposalId: string) => void
  handleDismiss: (proposalId: string) => void
  handleAnswerQuestion: (questionId: string, answer: string) => void
}

export function useGoalpostsSystem(
  selectedProjectId: string | null,
  options?: { signal?: AbortSignal; isHydrating?: boolean }
): UseGoalpostsSystemReturn {
  const api = useApiClient()

  const [state, setState] = useState<GoalpostsResponse | null>(null)
  const pollRef = useRef<NodeJS.Timeout | null>(null)

  // Clean up polling interval on unmount or project change
  useEffect(() => {
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current)
        pollRef.current = null
      }
    }
  }, [selectedProjectId])

  // Hydrate goalposts data on project change
  useEffect(() => {
    setState(null)
    if (!selectedProjectId) return

    const signal = options?.signal
    api.getGoalposts(selectedProjectId)
      .then((s) => { if (!signal?.aborted) setState(s) })
      .catch(() => {})
  }, [selectedProjectId, api])

  const handleGenerate = useCallback(() => {
    if (!selectedProjectId) return
    // Optimistic: set generating
    setState((prev) => prev ? { ...prev, generating: true, error: null } : null)

    api.triggerGoalpostsGenerate(selectedProjectId)
      .then(() => {
        // Clear any existing poll before starting a new one
        if (pollRef.current) clearInterval(pollRef.current)
        // Poll for completion
        pollRef.current = setInterval(() => {
          api.getGoalposts(selectedProjectId)
            .then((s) => {
              setState(s)
              if (!s.generating) {
                if (pollRef.current) clearInterval(pollRef.current)
                pollRef.current = null
              }
            })
            .catch(() => {
              if (pollRef.current) clearInterval(pollRef.current)
              pollRef.current = null
            })
        }, 2000)
      })
      .catch(() => setState((prev) => prev ? { ...prev, generating: false, error: 'Failed to start generation' } : null))
  }, [selectedProjectId, api])

  const handleUpdateIntent = useCallback((intent: string) => {
    if (!selectedProjectId) return
    // Optimistic
    setState((prev) => prev ? { ...prev, product_intent: intent, has_intent: !!intent.trim() } : null)

    api.updateGoalpostsIntent(selectedProjectId, intent)
      .catch(() => {})
  }, [selectedProjectId, api])

  const handleApprove = useCallback((proposalId: string) => {
    if (!selectedProjectId) return
    // Optimistic
    setState((prev) => {
      if (!prev) return null
      return {
        ...prev,
        proposals: prev.proposals.map((p) =>
          p.id === proposalId ? { ...p, state: 'approved' as const } : p
        ),
      }
    })

    api.updateGoalpostProposal(selectedProjectId, proposalId, 'approved')
      .catch(() => {
        // Revert on error
        api.getGoalposts(selectedProjectId).then(setState).catch(() => {})
      })
  }, [selectedProjectId, api])

  const handleDismiss = useCallback((proposalId: string) => {
    if (!selectedProjectId) return
    setState((prev) => {
      if (!prev) return null
      return {
        ...prev,
        proposals: prev.proposals.map((p) =>
          p.id === proposalId ? { ...p, state: 'dismissed' as const } : p
        ),
      }
    })

    api.updateGoalpostProposal(selectedProjectId, proposalId, 'dismissed')
      .catch(() => {
        api.getGoalposts(selectedProjectId).then(setState).catch(() => {})
      })
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

    api.answerGoalpostQuestion(selectedProjectId, questionId, answer)
      .catch(() => {
        api.getGoalposts(selectedProjectId).then(setState).catch(() => {})
      })
  }, [selectedProjectId, api])

  return {
    state,
    handleGenerate,
    handleUpdateIntent,
    handleApprove,
    handleDismiss,
    handleAnswerQuestion,
  }
}
