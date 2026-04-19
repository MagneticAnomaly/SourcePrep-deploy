import { useState, useCallback, useEffect, useRef } from 'react'
import {
  useApiClient,
  type LLMConfig,
  type SavedEndpoint,
  type EndpointTestResult,
  type LLMSlotsStatus,
  type AssignmentMode,
  type LLMAssignmentBlock,
} from '@codrag/ui'

interface UseLLMConfigOptions {
  onDirty?: () => void
}

/** Manages LLM endpoint configuration, model fetching/testing, slot status, and auto-persistence. */
export function useLLMConfig({ onDirty }: UseLLMConfigOptions = {}) {
  const api = useApiClient()
  const onDirtyRef = useRef(onDirty)
  onDirtyRef.current = onDirty

  // ── State ───────────────────────────────────────────────────
  const [llmConfig, setLLMConfig] = useState<LLMConfig>({
    saved_endpoints: [
      { id: 'default_ollama', name: 'Default Ollama', provider: 'ollama', url: 'http://localhost:11434' },
    ],
    embedding: { source: 'endpoint', endpoint_id: 'default_ollama', model: 'nomic-embed-text' },
    small_model: { enabled: false },
    large_model: { enabled: false },
    code_model: { enabled: false },
  })
  const [availableModels, setAvailableModels] = useState<Record<string, string[]>>({})
  const [modelDetails, setModelDetails] = useState<Record<string, Array<{ name: string; context_window?: string; cost_tier?: string; rate_limits?: { rpd?: number; rpm?: number }; batch_estimate?: { files_per_request: number; daily_file_capacity?: number } }>>>({})
  const [loadingModels, setLoadingModels] = useState<Record<string, boolean>>({})
  const [testingSlot, setTestingSlot] = useState<'embedding' | 'small' | 'large' | 'code' | 'coordinator' | null>(null)
  const [testResults, setTestResults] = useState<Record<string, EndpointTestResult>>({})

  /** Merge context_tokens from fetched model details into the persisted model_context_cache. */
  const mergeContextCache = useCallback((details: Array<{ name: string; context_tokens?: number }>) => {
    const updates: Record<string, number> = {}
    for (const d of details) {
      if (d.context_tokens && d.context_tokens > 0) {
        updates[d.name] = d.context_tokens
      }
    }
    if (Object.keys(updates).length === 0) return
    setLLMConfig((prev) => ({
      ...prev,
      model_context_cache: { ...prev.model_context_cache, ...updates },
    }))
    onDirtyRef.current?.()
  }, [])

  const handleClearTestResult = useCallback((slot: string) => {
    setTestResults((prev) => {
      const next = { ...prev }
      delete next[slot]
      return next
    })
  }, [])
  const [llmSlotsStatus, setLlmSlotsStatus] = useState<LLMSlotsStatus | null>(null)

  // ── Handlers ────────────────────────────────────────────────

  const handleLLMConfigChange = useCallback((cfg: LLMConfig) => {
    setLLMConfig((prev) => {
      // Auto-save embedding changes immediately (separated from model scheme button)
      if (JSON.stringify(prev.embedding) !== JSON.stringify(cfg.embedding)) {
        void api.updateGlobalConfig({ llm_config: { embedding: cfg.embedding } as unknown as LLMConfig })
      }
      return cfg
    })
    onDirtyRef.current?.()
  }, [api])

  const handleAddEndpoint = useCallback((endpoint: Omit<SavedEndpoint, 'id'>) => {
    const id = `ep_${Date.now()}_${Math.random().toString(16).slice(2)}`
    setLLMConfig((prev) => {
      const saved_endpoints = [...prev.saved_endpoints, { ...endpoint, id }]
      void api.updateGlobalConfig({ llm_config: { saved_endpoints } as unknown as LLMConfig })
      return { ...prev, saved_endpoints }
    })
    onDirtyRef.current?.()
  }, [api])

  const handleEditEndpoint = useCallback((endpoint: SavedEndpoint) => {
    setLLMConfig((prev) => {
      const saved_endpoints = prev.saved_endpoints.map((e) => (e.id === endpoint.id ? endpoint : e))
      void api.updateGlobalConfig({ llm_config: { saved_endpoints } as unknown as LLMConfig })
      return { ...prev, saved_endpoints }
    })
    onDirtyRef.current?.()
  }, [api])

  const handleDeleteEndpoint = useCallback((id: string) => {
    setLLMConfig((prev) => {
      const saved_endpoints = prev.saved_endpoints.filter((e) => e.id !== id)
      void api.updateGlobalConfig({ llm_config: { saved_endpoints } as unknown as LLMConfig })
      return { ...prev, saved_endpoints }
    })
    onDirtyRef.current?.()
  }, [api])

  const handleTestEndpoint = useCallback(async (endpoint: SavedEndpoint) => {
    const r = await fetch('/api/llm/proxy/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ provider: endpoint.provider, url: endpoint.url, api_key: endpoint.api_key }),
    })
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    const json = await r.json()
    const data = json?.data ?? json
    if (Array.isArray(data.models)) {
      setAvailableModels((prev) => ({ ...prev, [endpoint.id]: data.models }))
    }
    if (Array.isArray(data.model_details)) {
      setModelDetails((prev) => ({ ...prev, [endpoint.id]: data.model_details }))
      mergeContextCache(data.model_details)
    }
    return data as EndpointTestResult
  }, [])

  const handleFetchModels = useCallback(async (endpointId: string, slot?: string) => {
    const ep = llmConfig.saved_endpoints.find((e) => e.id === endpointId)
    if (!ep) return []
    setLoadingModels((prev) => ({ ...prev, [endpointId]: true }))
    try {
      const r = await fetch('/api/llm/proxy/models', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider: ep.provider, url: ep.url, api_key: ep.api_key, slot }),
      })
      const json = await r.json().catch(() => null)
      if (!r.ok) {
        const errMsg = json?.error?.message || json?.message || `HTTP ${r.status}`
        console.warn(`[LLM] Failed to fetch models for ${ep.provider}: ${errMsg}`)
        return []
      }
      const data = json?.data ?? json
      const models = Array.isArray(data.models) ? data.models : []
      setAvailableModels((prev) => ({ ...prev, [endpointId]: models }))
      if (Array.isArray(data.model_details)) {
        setModelDetails((prev) => ({ ...prev, [endpointId]: data.model_details }))
        mergeContextCache(data.model_details)
      }
      return models
    } catch (e) {
      console.warn('[LLM] Model fetch error:', e)
      return []
    } finally {
      setLoadingModels((prev) => ({ ...prev, [endpointId]: false }))
    }
  }, [llmConfig.saved_endpoints])

  const handleTestModel = useCallback(async (slotType: 'embedding' | 'small' | 'large' | 'code' | 'coordinator') => {
    let endpointId: string | undefined
    let model: string | undefined
    let kind = 'completion'
    if (slotType === 'embedding') {
      endpointId = llmConfig.embedding.endpoint_id; model = llmConfig.embedding.model; kind = 'embedding'
    } else if (slotType === 'small') {
      endpointId = llmConfig.small_model.endpoint_id; model = llmConfig.small_model.model
    } else if (slotType === 'code') {
      endpointId = llmConfig.code_model.endpoint_id; model = llmConfig.code_model.model
    } else if (slotType === 'coordinator') {
      endpointId = llmConfig.coordinator_model?.endpoint_id; model = llmConfig.coordinator_model?.model
    } else {
      endpointId = llmConfig.large_model.endpoint_id; model = llmConfig.large_model.model
    }
    const ep = llmConfig.saved_endpoints.find((e) => e.id === endpointId)
    if (!ep || !model) {
      const res: EndpointTestResult = { success: false, message: 'Model not configured.' }
      setTestResults((prev) => ({ ...prev, [slotType]: res }))
      return res
    }
    setTestingSlot(slotType)
    try {
      const slotKey = slotType === 'small' ? 'small_model' : slotType === 'large' ? 'large_model' : slotType === 'code' ? 'code_model' : slotType === 'coordinator' ? 'coordinator_model' : undefined
      const r = await fetch('/api/llm/proxy/test-model', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider: ep.provider, url: ep.url, api_key: ep.api_key, model, kind, slot: slotKey }),
      })
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      const json = await r.json()
      const data = (json?.data ?? json) as EndpointTestResult
      setTestResults((prev) => ({ ...prev, [slotType]: data }))
      return data
    } finally {
      setTestingSlot(null)
    }
  }, [llmConfig])

  const fetchLLMSlotsStatus = useCallback(async () => {
    try {
      const status = await api.getLLMSlotsStatus()
      setLlmSlotsStatus(status)
    } catch {
      // Silent — not critical
    }
  }, [api])

  // ── Live polling: keep sidebar AI Gateway in sync with real pipeline state ──
  // Adaptive interval: 3s when pipeline is active (running_tasks exist), 10s idle.
  // Skips polls while tab is hidden (Chrome throttles background timers anyway).
  const hasRunningTasks = (llmSlotsStatus?.running_tasks?.length ?? 0) > 0
  useEffect(() => {
    const intervalMs = hasRunningTasks ? 3000 : 10000
    const poll = () => {
      if (!document.hidden) {
        void fetchLLMSlotsStatus()
      }
    }
    const interval = setInterval(poll, intervalMs)
    // Also poll immediately when switching from idle → active (interval change)
    return () => clearInterval(interval)
  }, [fetchLLMSlotsStatus, hasRunningTasks])

  const handleDownloadModel = useCallback(async (slot: 'embedding') => {
    try {
      if (slot === 'embedding') {
        await api.downloadEmbedding()
      }
    } catch (err) {
      console.error(`Failed to trigger ${slot} download:`, err)
    }
  }, [api])

  const handleModeSwitch = useCallback(async (mode: AssignmentMode, blocks?: LLMConfig['assignment_blocks']) => {
    try {
      const result = await api.switchAssignmentMode(mode, blocks as LLMAssignmentBlock[] | undefined)
      // Update local config to reflect the switch
      setLLMConfig((prev) => ({
        ...prev,
        assignment_mode: mode,
        assignment_blocks: blocks ?? prev.assignment_blocks,
      }))
      // Refresh slot status to pick up new assignment_mode + running_task_id
      void fetchLLMSlotsStatus()
      return result
    } catch (err) {
      console.error('Mode switch failed:', err)
      throw err
    }
  }, [api, fetchLLMSlotsStatus])

  // ── Explicit save (no auto-save) ────────────────────────────
  // Model/endpoint changes update local state immediately but only
  // persist to backend when the user clicks Save.  This prevents
  // accidental swap_model triggers while the user is still editing.
  const lastSavedRef = useRef<string>('')
  const [llmConfigDirty, setLlmConfigDirty] = useState(false)

  // Track dirtiness by comparing serialized config to last save
  // We only track the "model scheme" fields for the Save button (small_model, large_model, code_model, etc),
  // because endpoints and embeddings now auto-save immediately.
  useEffect(() => {
    const getSchemeState = (cfg: LLMConfig) => JSON.stringify({
      small: cfg.small_model,
      large: cfg.large_model,
      code: cfg.code_model,
      coordinator: cfg.coordinator_model,
      mode: cfg.assignment_mode,
      blocks: cfg.assignment_blocks,
      // Phase 112 fix 1: include Advanced LLM Settings so toggling
      // enforce_cloud_token_safety / max_thinking_budget
      // marks the form dirty and enables the Save button.
      advanced: cfg.advanced,
    })
    
    if (lastSavedRef.current) {
      try {
        const oldScheme = getSchemeState(JSON.parse(lastSavedRef.current))
        const newScheme = getSchemeState(llmConfig)
        setLlmConfigDirty(oldScheme !== newScheme)
      } catch {
        setLlmConfigDirty(true)
      }
    }
  }, [llmConfig])

  const saveLLMConfig = useCallback(async () => {
    try {
      await api.updateGlobalConfig({ llm_config: llmConfig })
      lastSavedRef.current = JSON.stringify(llmConfig)
      setLlmConfigDirty(false)
      // Refresh slot status after saving so the widget picks up endpoint/model changes
      void fetchLLMSlotsStatus()
    } catch {
      // Silent fail — user can retry
    }
  }, [api, llmConfig, fetchLLMSlotsStatus])

  // Mark config as "clean" when loaded from backend (initial load)
  const markLLMConfigClean = useCallback(() => {
    lastSavedRef.current = JSON.stringify(llmConfig)
    setLlmConfigDirty(false)
  }, [llmConfig])

  // ── Auto-fetch models for pre-configured endpoints ──────────
  useEffect(() => {
    const endpointIds = new Set<string>()
    if (llmConfig.embedding.source === 'endpoint' && llmConfig.embedding.endpoint_id) {
      endpointIds.add(llmConfig.embedding.endpoint_id)
    }
    if (llmConfig.small_model.endpoint_id) endpointIds.add(llmConfig.small_model.endpoint_id)
    if (llmConfig.large_model.endpoint_id) endpointIds.add(llmConfig.large_model.endpoint_id)
    if (llmConfig.coordinator_model?.endpoint_id) endpointIds.add(llmConfig.coordinator_model.endpoint_id)

    for (const epId of endpointIds) {
      if (!availableModels[epId]?.length) {
        void handleFetchModels(epId)
      }
    }
  // Run once on mount — intentionally omitting deps to avoid re-fetching on every config change
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return {
    llmConfig,
    setLLMConfig,
    availableModels,
    modelDetails,
    loadingModels,
    testingSlot,
    testResults,
    llmSlotsStatus,
    llmConfigDirty,
    handleLLMConfigChange,
    handleAddEndpoint,
    handleEditEndpoint,
    handleDeleteEndpoint,
    handleTestEndpoint,
    handleFetchModels,
    handleTestModel,
    handleClearTestResult,
    handleDownloadModel,
    handleModeSwitch,
    saveLLMConfig,
    markLLMConfigClean,
    fetchLLMSlotsStatus,
  }
}
