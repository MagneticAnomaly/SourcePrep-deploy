import { useState, useCallback, useEffect, useMemo, useRef } from 'react'
import {
  useApiClient,
  type LLMConfig,
  type SavedEndpoint,
  type EndpointTestResult,
  type LLMSlotsStatus,
  type AssignmentMode,
  type LLMAssignmentBlock,
} from '@prep/ui'
import { useDebouncedAutoSave } from './useDebouncedAutoSave'
import { stripModeFields } from '@prep/ui/components/llm/llmConfigHelpers'

interface UseLLMConfigOptions {
  onDirty?: () => void
  /** Fired after a successful auto-save persist. Typically wired to handleSwapModel. */
  onSwapModel?: () => void
  /**
   * Phase 119 Phase A 5b: fired when PUT /global/config returns advisory
   * warnings (e.g. saving an Ollama Cloud endpoint without a plan tier).  The
   * dashboard wires this to its toast system so the user sees something
   * visible instead of the warning silently disappearing.  Save still
   * succeeds; warnings are non-blocking.
   */
  onWarnings?: (warnings: string[]) => void
}

/** Manages LLM endpoint configuration, model fetching/testing, slot status, and auto-persistence. */
export function useLLMConfig({ onDirty, onSwapModel, onWarnings }: UseLLMConfigOptions = {}) {
  const api = useApiClient()
  const onDirtyRef = useRef(onDirty)
  onDirtyRef.current = onDirty
  const onSwapModelRef = useRef(onSwapModel)
  onSwapModelRef.current = onSwapModel
  const onWarningsRef = useRef(onWarnings)
  onWarningsRef.current = onWarnings

  /**
   * Phase 119 Phase A 5b: thin wrapper around updateGlobalConfigWithWarnings
   * that swallows network errors (legacy fire-and-forget contract for these
   * paths) but always forwards any backend warnings to the consumer.
   */
  const persistEndpointsWithWarnings = useCallback(
    async (saved_endpoints: SavedEndpoint[]): Promise<void> => {
      try {
        const { warnings } = await api.updateGlobalConfigWithWarnings({
          llm_config: { saved_endpoints } as unknown as LLMConfig,
        })
        if (warnings.length > 0) {
          onWarningsRef.current?.(warnings)
        }
      } catch {
        // Silent — matches legacy fire-and-forget policy on these endpoint
        // CRUD paths.  User can retry by editing again.
      }
    },
    [api]
  )

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
    setLLMConfig(cfg)
    onDirtyRef.current?.()
  }, [])

  const handleAddEndpoint = useCallback((endpoint: Omit<SavedEndpoint, 'id'>) => {
    const id = `ep_${Date.now()}_${Math.random().toString(16).slice(2)}`
    setLLMConfig((prev) => {
      const saved_endpoints = [...prev.saved_endpoints, { ...endpoint, id }]
      void persistEndpointsWithWarnings(saved_endpoints)
      return { ...prev, saved_endpoints }
    })
    onDirtyRef.current?.()
  }, [persistEndpointsWithWarnings])

  const handleEditEndpoint = useCallback((endpoint: SavedEndpoint) => {
    setLLMConfig((prev) => {
      const saved_endpoints = prev.saved_endpoints.map((e) => (e.id === endpoint.id ? endpoint : e))
      void persistEndpointsWithWarnings(saved_endpoints)
      return { ...prev, saved_endpoints }
    })
    onDirtyRef.current?.()
  }, [persistEndpointsWithWarnings])

  const handleDeleteEndpoint = useCallback((id: string) => {
    setLLMConfig((prev) => {
      const saved_endpoints = prev.saved_endpoints.filter((e) => e.id !== id)
      void persistEndpointsWithWarnings(saved_endpoints)
      return { ...prev, saved_endpoints }
    })
    onDirtyRef.current?.()
  }, [persistEndpointsWithWarnings])

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

  // ── Debounced auto-save ─────────────────────────────────────
  // Gate auto-save until the backend config has been loaded and markLLMConfigClean() has run.
  const [autoSaveEnabled, setAutoSaveEnabled] = useState(false)

  // Trailing-edge debounced persist of the full LLM config (minus mode-owned fields,
  // which are committed via the explicit "Apply mode" button path).
  const saveValue = useMemo(() => stripModeFields(llmConfig), [llmConfig])

  // Phase 118 U7: only fire onSwapModel when the active model identity for
  // a slot actually changed. The previous behavior fired it after EVERY
  // successful auto-save (e.g. updating a non-model field, re-saving the
  // same config, etc.), which paused the currently-running pipeline via
  // swap_model and left it stuck at the paused stage. Concretely: during
  // a PMR rebuild, an unrelated config save fired swap_model on
  // deep_enrichment mid-stage 1 → pause → no resume → the harness's
  // watch_until_idle saw "no group running" and exited after 226s,
  // making the rebuild appear to complete in ~2 min when only fast_sync
  // had actually run.
  const lastPersistedModelKeyRef = useRef<string>('')
  const modelKeyOf = (cfg: LLMConfig): string => {
    const pick = (slot?: { endpoint_id?: string; model?: string; enabled?: boolean }) =>
      slot?.enabled ? `${slot.endpoint_id ?? ''}/${slot.model ?? ''}` : ''
    return [
      pick(cfg.small_model),
      pick(cfg.large_model),
      pick(cfg.code_model),
      pick((cfg as LLMConfig & { coordinator_model?: { endpoint_id?: string; model?: string; enabled?: boolean } }).coordinator_model),
    ].join('|')
  }

  const { flush: flushPendingSave } = useDebouncedAutoSave({
    value: saveValue,
    enabled: autoSaveEnabled,
    delayMs: 1500,
    onSave: async () => {
      try {
        // Phase 119 Phase A 5b: also funnel debounced full-config saves through
        // the warnings-aware path so that, e.g., changing concurrency on an
        // existing cloud endpoint without a plan tier surfaces the validator
        // hint via the dashboard toast.
        const { warnings } = await api.updateGlobalConfigWithWarnings({ llm_config: llmConfig })
        if (warnings.length > 0) {
          onWarningsRef.current?.(warnings)
        }
      } catch {
        // Silent fail — matches legacy policy. User can retry by editing again.
      }
    },
    onPersist: () => {
      const nextKey = modelKeyOf(llmConfig)
      const prevKey = lastPersistedModelKeyRef.current
      lastPersistedModelKeyRef.current = nextKey
      // Only swap if the active model identity actually changed AND we
      // had a prior key (avoid swapping on the very first load).
      if (prevKey && prevKey !== nextKey) {
        onSwapModelRef.current?.()
      }
      void fetchLLMSlotsStatus()
    },
  })

  // Mark config as "clean" when loaded from backend (initial load).
  // This flips the auto-save gate on; the useDebouncedAutoSave hook then tracks changes.
  const markLLMConfigClean = useCallback(() => {
    setAutoSaveEnabled(true)
  }, [])

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
    markLLMConfigClean,
    fetchLLMSlotsStatus,
    flushPendingSave,
  }
}
