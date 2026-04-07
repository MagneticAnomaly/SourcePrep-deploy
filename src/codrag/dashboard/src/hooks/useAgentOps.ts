import { useState, useCallback, useEffect } from 'react'
import { useApiClient } from '@codrag/ui'
import type { AgentOpsData, PushSettingsData } from '@codrag/ui'

export interface UseAgentOpsReturn {
  agentStatus: AgentOpsData | null
  agentLoading: boolean
  pushSettings: PushSettingsData | null
  handlePushSettingsUpdate: (settings: PushSettingsData) => void
  refreshAgentStatus: () => void
}

export function useAgentOps(
  selectedProjectId: string | null,
  options?: { signal?: AbortSignal; isHydrating?: boolean }
): UseAgentOpsReturn {
  const api = useApiClient()

  const [agentStatus, setAgentStatus] = useState<AgentOpsData | null>(null)
  const [agentLoading, setAgentLoading] = useState(false)
  const [pushSettings, setPushSettings] = useState<PushSettingsData | null>({
    auto_push: false,
    min_significance: 'recommended',
    paperclip_project: '',
  })

  const refreshAgentStatus = useCallback(() => {
    if (!selectedProjectId) return

    setAgentLoading(true)
    api
      .getAgentsStatus(selectedProjectId)
      .then((status: any) => {
        if (options?.signal?.aborted) return
        // Map API response to AgentOpsData shape.
        // The API may return richer objects; extract last_run and default push_count to 0.
        const toEngineStatus = (raw: any) => ({
          last_run: raw?.last_run ?? raw?.latest_run ?? null,
          push_count: raw?.push_count ?? 0,
        })
        setAgentStatus({
          hr: toEngineStatus(status?.hr),
          researcher: toEngineStatus(status?.researcher),
          custodian: toEngineStatus(status?.custodian),
        })
      })
      .catch(() => {})
      .finally(() => {
        if (!options?.signal?.aborted) setAgentLoading(false)
      })
  }, [selectedProjectId, api])

  // Hydrate on project change
  useEffect(() => {
    setAgentStatus(null)

    if (!selectedProjectId) return
    refreshAgentStatus()
  }, [selectedProjectId, refreshAgentStatus])

  const handlePushSettingsUpdate = useCallback((settings: PushSettingsData) => {
    setPushSettings(settings)
  }, [])

  return {
    agentStatus,
    agentLoading,
    pushSettings,
    handlePushSettingsUpdate,
    refreshAgentStatus,
  }
}
