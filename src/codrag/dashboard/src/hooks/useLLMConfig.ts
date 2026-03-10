import { useState, useCallback, useEffect, useRef } from 'react'
import {
  useApiClient,
  type LLMConfig,
  type SavedEndpoint,
  type EndpointTestResult,
  type LLMSlotsStatus,
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
    compression: { enabled: false, mode: 'auto', level: 'standard' },
    batch_mode: 'auto',
  })
  const [availableModels, setAvailableModels] = useState<Record<string, string[]>>({})
  const [modelDetails, setModelDetails] = useState<Record<string, Array<{ name: string; context_window?: string; cost_tier?: string; rate_limits?: { rpd?: number; rpm?: number }; batch_estimate?: { files_per_request: number; daily_file_capacity?: number } }>>>({})
  const [loadingModels, setLoadingModels] = useState<Record<string, boolean>>({})
  const [testingSlot, setTestingSlot] = useState<'embedding' | 'small' | 'large' | 'code' | null>(null)
  const [testResults, setTestResults] = useState<Record<string, EndpointTestResult>>({})

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
    setLLMConfig((prev) => ({
      ...prev,
      saved_endpoints: [...prev.saved_endpoints, { ...endpoint, id }],
    }))
    onDirtyRef.current?.()
  }, [])

  const handleEditEndpoint = useCallback((endpoint: SavedEndpoint) => {
    setLLMConfig((prev) => ({
      ...prev,
      saved_endpoints: prev.saved_endpoints.map((e) => (e.id === endpoint.id ? endpoint : e)),
    }))
    onDirtyRef.current?.()
  }, [])

  const handleDeleteEndpoint = useCallback((id: string) => {
    setLLMConfig((prev) => ({
      ...prev,
      saved_endpoints: prev.saved_endpoints.filter((e) => e.id !== id),
    }))
    onDirtyRef.current?.()
  }, [])

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
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      const json = await r.json()
      const data = json?.data ?? json
      const models = Array.isArray(data.models) ? data.models : []
      setAvailableModels((prev) => ({ ...prev, [endpointId]: models }))
      if (Array.isArray(data.model_details)) {
        setModelDetails((prev) => ({ ...prev, [endpointId]: data.model_details }))
      }
      return models
    } finally {
      setLoadingModels((prev) => ({ ...prev, [endpointId]: false }))
    }
  }, [llmConfig.saved_endpoints])

  const handleTestModel = useCallback(async (slotType: 'embedding' | 'small' | 'large' | 'code') => {
    let endpointId: string | undefined
    let model: string | undefined
    let kind = 'completion'
    if (slotType === 'embedding') {
      endpointId = llmConfig.embedding.endpoint_id; model = llmConfig.embedding.model; kind = 'embedding'
    } else if (slotType === 'small') {
      endpointId = llmConfig.small_model.endpoint_id; model = llmConfig.small_model.model
    } else if (slotType === 'code') {
      endpointId = llmConfig.code_model.endpoint_id; model = llmConfig.code_model.model
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
      const slotKey = slotType === 'small' ? 'small_model' : slotType === 'large' ? 'large_model' : slotType === 'code' ? 'code_model' : undefined
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

  const fetchCompressionStatus = useCallback(async () => {
    try {
      const status = await api.getCompressionStatus()
      if (status.lingua) {
        setLLMConfig((prev) => ({
          ...prev,
          compression: {
            ...prev.compression,
            lingua_downloaded: status.lingua.downloaded ?? false,
          },
        }))
      }
    } catch {
      // Silent — not critical
    }
  }, [api])

  const handleDownloadModel = useCallback(async (slot: 'embedding' | 'lingua') => {
    try {
      if (slot === 'embedding') {
        await api.downloadEmbedding()
      } else if (slot === 'lingua') {
        // Show downloading state immediately
        setLLMConfig((prev) => ({
          ...prev,
          compression: {
            ...prev.compression,
            lingua_download_progress: 0.1,
          },
        }))
        await api.downloadLinguaModel()
        // Mark as downloaded immediately, then confirm with server
        setLLMConfig((prev) => ({
          ...prev,
          compression: {
            ...prev.compression,
            lingua_downloaded: true,
            lingua_download_progress: undefined,
          },
        }))
        // Also refresh from server to be sure
        void fetchCompressionStatus()
      }
    } catch (err) {
      console.error(`Failed to trigger ${slot} download:`, err)
      // Clear downloading state on error
      if (slot === 'lingua') {
        setLLMConfig((prev) => ({
          ...prev,
          compression: {
            ...prev.compression,
            lingua_download_progress: undefined,
          },
        }))
      }
    }
  }, [api, fetchCompressionStatus])

  // ── Auto-save LLM config to backend ─────────────────────────
  const llmConfigSkipRef = useRef(0) // skip initial + loaded-from-backend
  useEffect(() => {
    if (llmConfigSkipRef.current < 2) {
      llmConfigSkipRef.current++
      return
    }
    const timeout = setTimeout(() => {
      api.updateGlobalConfig({ llm_config: llmConfig }).catch(() => {
        // Silent fail — config will be retried on next change
      })
    }, 500)
    return () => clearTimeout(timeout)
  }, [api, llmConfig])

  // ── Auto-fetch models for pre-configured endpoints ──────────
  useEffect(() => {
    const endpointIds = new Set<string>()
    if (llmConfig.embedding.source === 'endpoint' && llmConfig.embedding.endpoint_id) {
      endpointIds.add(llmConfig.embedding.endpoint_id)
    }
    if (llmConfig.small_model.endpoint_id) endpointIds.add(llmConfig.small_model.endpoint_id)
    if (llmConfig.large_model.endpoint_id) endpointIds.add(llmConfig.large_model.endpoint_id)

    for (const epId of endpointIds) {
      if (!availableModels[epId]?.length) {
        void handleFetchModels(epId)
      }
    }
    
    // Also fetch compression status on mount
    void fetchCompressionStatus()
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
    fetchLLMSlotsStatus,
  }
}
