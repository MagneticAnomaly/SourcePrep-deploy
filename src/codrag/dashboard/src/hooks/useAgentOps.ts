import { useState, useCallback, useEffect } from 'react'
import { useApiClient } from '@codrag/ui'
import type { AgentOpsData } from '@codrag/ui'

export interface UseAgentOpsReturn {
  agentStatus: AgentOpsData | null
  agentLoading: boolean
  roster: Array<{ slug: string; displayName: string; hasAgentsMd: boolean; hasSoulMd: boolean; hasKnowledgeMd: boolean }>
  readiness: { score: number; ready_for_list: boolean; ready_for_auto: boolean; missing: string[] } | null
  researchHistory: Array<{ run_id: string; timestamp: string; topic_count: number; plan_count: number }>
  handleHRGenerate: (mode: string, roleNames: string[]) => void
  handleResearchRun: (maxTopics: number) => void
  handleCustodianRun: (dryRun: boolean) => void
  refreshAgentStatus: () => void
}

export function useAgentOps(
  selectedProjectId: string | null,
  options?: { signal?: AbortSignal; isHydrating?: boolean }
): UseAgentOpsReturn {
  const api = useApiClient()

  const [agentStatus, setAgentStatus] = useState<AgentOpsData | null>(null)
  const [agentLoading, setAgentLoading] = useState(false)
  const [roster, setRoster] = useState<UseAgentOpsReturn['roster']>([])
  const [readiness, setReadiness] = useState<UseAgentOpsReturn['readiness']>(null)
  const [researchHistory, setResearchHistory] = useState<UseAgentOpsReturn['researchHistory']>([])

  const refreshAgentStatus = useCallback(() => {
    if (!selectedProjectId) return

    setAgentLoading(true)
    Promise.all([
      api.getAgentsStatus(selectedProjectId),
      api.getHRRoster(selectedProjectId),
      api.getHRReadiness(selectedProjectId),
      api.getResearchHistory(selectedProjectId),
    ])
      .then(([status, rosterData, readinessData, historyData]) => {
        if (options?.signal?.aborted) return
        setAgentStatus(status as AgentOpsData)
        setRoster(
          (rosterData.roles || []).map((r: any) => ({
            slug: r.slug,
            displayName: r.display_name,
            hasAgentsMd: r.has_agents_md,
            hasSoulMd: r.has_soul_md,
            hasKnowledgeMd: r.has_knowledge_md,
          }))
        )
        setReadiness(readinessData)
        setResearchHistory(historyData.runs || [])
      })
      .catch(() => {})
      .finally(() => { if (!options?.signal?.aborted) setAgentLoading(false) })
  }, [selectedProjectId, api])

  // Hydrate on project change
  useEffect(() => {
    setAgentStatus(null)
    setRoster([])
    setReadiness(null)
    setResearchHistory([])

    if (!selectedProjectId) return
    refreshAgentStatus()
  }, [selectedProjectId, refreshAgentStatus])

  const handleHRGenerate = useCallback(
    (mode: string, roleNames: string[]) => {
      if (!selectedProjectId) return
      setAgentLoading(true)
      api
        .generateHRRoles(selectedProjectId, mode, roleNames)
        .then(() => refreshAgentStatus())
        .catch(() => {})
        .finally(() => setAgentLoading(false))
    },
    [selectedProjectId, api, refreshAgentStatus]
  )

  const handleResearchRun = useCallback(
    (maxTopics: number) => {
      if (!selectedProjectId) return
      setAgentLoading(true)
      api
        .runResearcher(selectedProjectId, maxTopics)
        .then(() => refreshAgentStatus())
        .catch(() => {})
        .finally(() => setAgentLoading(false))
    },
    [selectedProjectId, api, refreshAgentStatus]
  )

  const handleCustodianRun = useCallback(
    (dryRun: boolean) => {
      if (!selectedProjectId) return
      setAgentLoading(true)
      api
        .runCustodian(selectedProjectId, dryRun, 20)
        .then(() => refreshAgentStatus())
        .catch(() => {})
        .finally(() => setAgentLoading(false))
    },
    [selectedProjectId, api, refreshAgentStatus]
  )

  return {
    agentStatus,
    agentLoading,
    roster,
    readiness,
    researchHistory,
    handleHRGenerate,
    handleResearchRun,
    handleCustodianRun,
    refreshAgentStatus,
  }
}
