import { useState, useCallback, useEffect, useRef } from 'react'
import { useApiClient } from '@prep/ui'
import type { AgentStatus as AgentStatusType } from '@prep/ui'

// ── Types ─────────────────────────────────────────────────────

export interface OpportunityItem {
  id: string
  title: string
  description: string
  category: string
  priority: string  // P0, P1, P2, P3
  severity: string  // critical, warning, info, suggestion
  effort: string    // trivial, small, medium, large
  source: string    // health, spaghetti, advisor, todo_scanner, roadmap
  analyzer: string
  state: string     // active, dismissed
  affected_files: string[]
  suggested_action: string
  evidence: string
  mcp_command: string
  created_at: string
  dismissed_at: string
}

export interface OpportunitiesSummary {
  total: number
  dismissed: number
  critical: number
  warning: number
  info: number
  actionable_count: number
  last_refresh: string | null
  by_priority: Record<string, number>
  by_category: Record<string, number>
  by_source: Record<string, number>
  by_analyzer: Record<string, number>
  by_severity: Record<string, number>
  top_analyzers: { analyzer: string; count: number }[]
}

export interface UseOpportunitiesSystemReturn {
  items: OpportunityItem[]
  summary: OpportunitiesSummary | null
  loading: boolean
  refreshing: boolean
  error: string | null
  handleRefresh: () => void
  handleDismiss: (itemId: string) => void
  handleRestore: (itemId: string) => void
  handleExport: (format: string) => void
  categoryFilter: string | null
  setCategoryFilter: (c: string | null) => void
  priorityFilter: string | null
  setPriorityFilter: (p: string | null) => void
  sourceFilter: string | null
  setSourceFilter: (s: string | null) => void
  showDismissed: boolean
  setShowDismissed: (b: boolean) => void
  /** Phase 66: Pi agent status from pipeline status API */
  agentStatus: AgentStatusType | null
}

// ── Hook ──────────────────────────────────────────────────────

export function useOpportunitiesSystem(
  selectedProjectId: string | null,
  options?: { signal?: AbortSignal; isHydrating?: boolean }
): UseOpportunitiesSystemReturn {
  const api = useApiClient()

  const [items, setItems] = useState<OpportunityItem[]>([])
  const [summary, setSummary] = useState<OpportunitiesSummary | null>(null)
  const [loading, setLoading] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Filters
  const [categoryFilter, setCategoryFilter] = useState<string | null>(null)
  const [priorityFilter, setPriorityFilter] = useState<string | null>(null)
  const [sourceFilter, setSourceFilter] = useState<string | null>(null)
  const [showDismissed, setShowDismissed] = useState(false)

  // Phase 66: Pi agent status from pipeline status API
  const [agentStatus, setAgentStatus] = useState<AgentStatusType | null>(null)
  const agentPollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const isHydratingRef = useRef(options?.isHydrating)
  isHydratingRef.current = options?.isHydrating

  // Hydrate on project change
  useEffect(() => {
    setItems([])
    setSummary(null)
    setError(null)
    setLoading(false)
    setRefreshing(false)
    setCategoryFilter(null)
    setPriorityFilter(null)
    setSourceFilter(null)
    setShowDismissed(false)

    if (!selectedProjectId) return

    setLoading(true)
    const signal = options?.signal
    Promise.all([
      api.getOpportunities(selectedProjectId, { limit: 200 }),
      api.getOpportunitiesSummary(selectedProjectId),
    ])
      .then(([opps, sum]) => {
        if (signal?.aborted) return
        setItems(opps.items || [])
        // Merge missing fields to satisfy UI interface, as old daemons might omit them
        setSummary(sum ? {
          ...sum,
          actionable_count: (sum as any).actionable_count ?? 0,
          by_analyzer: (sum as any).by_analyzer ?? {},
          by_severity: (sum as any).by_severity ?? {},
          top_analyzers: (sum as any).top_analyzers ?? []
        } : null)
      })
      .catch((e) => {
        if (signal?.aborted) return
        // Not a hard error — endpoint might not exist on older daemons
        console.warn('[Opportunities] Failed to load:', e.message)
      })
      .finally(() => { if (!signal?.aborted) setLoading(false) })
  }, [selectedProjectId, api])

  // Phase 66: Poll pipeline status for agent data
  useEffect(() => {
    if (!selectedProjectId) {
      setAgentStatus(null)
      return
    }

    const signal = options?.signal
    const fetchAgent = () => {
      if (signal?.aborted || isHydratingRef.current) return
      api.getPipelineStatus(selectedProjectId)
        .then((ps) => {
          if (signal?.aborted) return
          setAgentStatus((ps as any)?.agent ?? null)
        })
        .catch(() => { /* pipeline status may not be available */ })
    }

    // Initial fetch
    fetchAgent()

    // Poll every 30s (agent runs are async, user wants to see updates).
    // F-11: skip when tab is hidden so backgrounded dashboards don't
    // contribute to the polling storm.
    agentPollRef.current = setInterval(() => {
      if (document.hidden) return
      fetchAgent()
    }, 30_000)

    return () => {
      if (agentPollRef.current) clearInterval(agentPollRef.current)
    }
  }, [selectedProjectId, api])

  // Refresh: run fresh scan
  const handleRefresh = useCallback(() => {
    if (!selectedProjectId) return
    setRefreshing(true)
    setError(null)

    api.refreshOpportunities(selectedProjectId)
      .then((data) => {
        setItems(data.items || [])
        setSummary(data.summary || null)
      })
      .catch((e) => setError(`Refresh failed: ${e.message}`))
      .finally(() => setRefreshing(false))
  }, [selectedProjectId, api])

  // Dismiss
  const handleDismiss = useCallback((itemId: string) => {
    if (!selectedProjectId) return
    // Optimistic update
    setItems(prev => prev.map(item =>
      item.id === itemId ? { ...item, state: 'dismissed' } : item
    ))
    setSummary(prev => prev ? {
      ...prev,
      total: Math.max(0, prev.total - 1),
      dismissed: prev.dismissed + 1,
    } : prev)

    api.dismissOpportunity(selectedProjectId, itemId)
      .catch(() => {
        // Revert on failure
        setItems(prev => prev.map(item =>
          item.id === itemId ? { ...item, state: 'active' } : item
        ))
      })
  }, [selectedProjectId, api])

  // Restore
  const handleRestore = useCallback((itemId: string) => {
    if (!selectedProjectId) return
    // Optimistic update
    setItems(prev => prev.map(item =>
      item.id === itemId ? { ...item, state: 'active', dismissed_at: '' } : item
    ))
    setSummary(prev => prev ? {
      ...prev,
      total: prev.total + 1,
      dismissed: Math.max(0, prev.dismissed - 1),
    } : prev)

    api.restoreOpportunity(selectedProjectId, itemId)
      .catch(() => {
        setItems(prev => prev.map(item =>
          item.id === itemId ? { ...item, state: 'dismissed' } : item
        ))
      })
  }, [selectedProjectId, api])

  // Export
  const handleExport = useCallback((format: string) => {
    if (!selectedProjectId) return

    api.exportOpportunities(selectedProjectId, format)
      .then((text) => {
        // Copy to clipboard
        navigator.clipboard.writeText(text).catch(() => {})

        // Also trigger download for file-like formats
        if (['sarif', 'csv', 'json'].includes(format)) {
          const mimeTypes: Record<string, string> = {
            sarif: 'application/json',
            csv: 'text/csv',
            json: 'application/json',
          }
          const blob = new Blob([text], { type: mimeTypes[format] || 'text/plain' })
          const url = URL.createObjectURL(blob)
          const a = document.createElement('a')
          a.href = url
          a.download = `codrag-opportunities.${format}`
          a.click()
          URL.revokeObjectURL(url)
        }
      })
      .catch((e) => setError(`Export failed: ${e.message}`))
  }, [selectedProjectId, api])

  return {
    items,
    summary,
    loading,
    refreshing,
    error,
    handleRefresh,
    handleDismiss,
    handleRestore,
    handleExport,
    categoryFilter,
    setCategoryFilter,
    priorityFilter,
    setPriorityFilter,
    sourceFilter,
    setSourceFilter,
    showDismissed,
    setShowDismissed,
    agentStatus,
  }
}
