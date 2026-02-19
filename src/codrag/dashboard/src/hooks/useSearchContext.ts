import { useState, useCallback, useRef } from 'react'
import { useApiClient, type SearchResult, type ContextMeta } from '@codrag/ui'

// ── Dependencies ──────────────────────────────────────────────

interface UseSearchContextDeps {
  onError?: (msg: string) => void
}

// ── Hook ──────────────────────────────────────────────────────

/**
 * Manages search query, results, context assembly, and copy-to-clipboard.
 * Self-contained — no project-change hydration needed (search is user-initiated).
 */
export function useSearchContext(selectedProjectId: string | null, { onError }: UseSearchContextDeps = {}) {
  const api = useApiClient()
  const onErrorRef = useRef(onError)
  onErrorRef.current = onError

  // ── Search state ───────────────────────────────────────────
  const [query, setQuery] = useState<string>('')
  const [searchK, setSearchK] = useState<number>(8)
  const [minScore, setMinScore] = useState<number>(0.15)
  const [searchLoading, setSearchLoading] = useState(false)
  const [searchResults, setSearchResults] = useState<SearchResult[]>([])
  const [selectedChunk, setSelectedChunk] = useState<SearchResult | null>(null)

  // ── Context state ──────────────────────────────────────────
  const [contextK, setContextK] = useState<number>(5)
  const [contextMaxChars, setContextMaxChars] = useState<number>(6000)
  const [contextIncludeSources, setContextIncludeSources] = useState(true)
  const [contextIncludeScores, setContextIncludeScores] = useState(false)
  const [contextStructured, setContextStructured] = useState(false)
  const [context, setContext] = useState<string>('')
  const [contextMeta, setContextMeta] = useState<ContextMeta | null>(null)

  // ── Handlers ────────────────────────────────────────────────

  const handleSearch = useCallback(async () => {
    if (!query.trim() || !selectedProjectId) return
    setSearchLoading(true)
    try {
      const data = await api.search(selectedProjectId, {
        query: query.trim(),
        k: searchK,
        min_score: minScore,
      })
      const results: SearchResult[] = data.results.map((r) => ({
        chunk_id: r.chunk_id,
        source_path: r.source_path,
        span: r.span,
        preview: r.preview,
        score: r.score,
        section: r.section,
        content: r.content,
      }))
      setSearchResults(results)
      setSelectedChunk(results[0] ?? null)
    } catch (e) {
      onErrorRef.current?.(e instanceof Error ? e.message : 'Search failed')
    } finally {
      setSearchLoading(false)
    }
  }, [api, minScore, query, searchK, selectedProjectId])

  const handleGetContext = useCallback(async () => {
    if (!query.trim() || !selectedProjectId) return
    try {
      const data = await api.assembleContext(selectedProjectId, {
        query: query.trim(),
        k: contextK,
        max_chars: contextMaxChars,
        include_sources: contextIncludeSources,
        include_scores: contextIncludeScores,
        min_score: minScore,
        structured: contextStructured,
      })
      setContext(String(data.context || ''))
      if ('chunks' in data && data.chunks) {
        setContextMeta({
          chunks: data.chunks.map((c) => ({
            source_path: c.source_path,
            section: '',
            score: c.score ?? 0,
            truncated: false,
          })),
          total_chars: data.total_chars ?? 0,
          estimated_tokens: data.estimated_tokens ?? 0,
        })
      } else {
        setContextMeta(null)
      }
    } catch (e) {
      onErrorRef.current?.(e instanceof Error ? e.message : 'Failed to get context')
    }
  }, [api, contextIncludeScores, contextIncludeSources, contextK, contextMaxChars, contextStructured, minScore, query, selectedProjectId])

  const handleCopyContext = useCallback(async () => {
    if (!context) return
    try {
      await navigator.clipboard.writeText(context)
    } catch (e) {
      onErrorRef.current?.(e instanceof Error ? e.message : 'Copy failed')
    }
  }, [context])

  // ── Reset (called by destroy handlers) ──────────────────────

  const resetSearch = useCallback(() => {
    setSearchResults([])
    setSelectedChunk(null)
    setContext('')
    setContextMeta(null)
  }, [])

  // ── Return ──────────────────────────────────────────────────

  return {
    // Search state
    query, setQuery,
    searchK, setSearchK,
    minScore, setMinScore,
    searchLoading,
    searchResults,
    selectedChunk, setSelectedChunk,
    // Context state
    contextK, setContextK,
    contextMaxChars, setContextMaxChars,
    contextIncludeSources, setContextIncludeSources,
    contextIncludeScores, setContextIncludeScores,
    contextStructured, setContextStructured,
    context,
    contextMeta,
    // Actions
    handleSearch,
    handleGetContext,
    handleCopyContext,
    resetSearch,
  }
}
