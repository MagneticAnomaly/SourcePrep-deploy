import { useState, useEffect, useRef, useCallback } from 'react'

export interface HydrationController {
  /** The debounced project ID — hooks should hydrate against this, not the raw selection */
  hydratedProjectId: string | null
  /** AbortSignal that gets aborted on every project switch. Pass to fetch calls. */
  signal: AbortSignal
  /** True while hydration is in progress (critical + secondary tiers). Polls should wait. */
  isHydrating: boolean
  /** Call when your hook's hydration fetch completes (success or fail). */
  markHydrated: (hookId: string) => void
  /** Register a hook as needing hydration for the current switch. */
  registerHook: (hookId: string) => void
}

const DEBOUNCE_MS = 100

export function useHydrationController(rawProjectId: string | null): HydrationController {
  const [hydratedProjectId, setHydratedProjectId] = useState<string | null>(rawProjectId)
  const [isHydrating, setIsHydrating] = useState(false)
  const abortRef = useRef<AbortController>(new AbortController())
  const debounceRef = useRef<NodeJS.Timeout | null>(null)
  const pendingHooksRef = useRef<Set<string>>(new Set())

  // On rawProjectId change: abort previous, debounce new
  useEffect(() => {
    // Abort all in-flight requests from previous project
    abortRef.current.abort()
    abortRef.current = new AbortController()

    // Clear any pending debounce
    if (debounceRef.current) {
      clearTimeout(debounceRef.current)
    }

    if (!rawProjectId) {
      setHydratedProjectId(null)
      setIsHydrating(false)
      pendingHooksRef.current.clear()
      return
    }

    // Start hydrating immediately (even during debounce window)
    setIsHydrating(true)
    pendingHooksRef.current.clear()

    // Debounce the actual project ID propagation
    debounceRef.current = setTimeout(() => {
      setHydratedProjectId(rawProjectId)
    }, DEBOUNCE_MS)

    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current)
      }
    }
  }, [rawProjectId])

  const registerHook = useCallback((hookId: string) => {
    pendingHooksRef.current.add(hookId)
  }, [])

  const markHydrated = useCallback((hookId: string) => {
    pendingHooksRef.current.delete(hookId)
    if (pendingHooksRef.current.size === 0) {
      setIsHydrating(false)
    }
  }, [])

  return {
    hydratedProjectId,
    signal: abortRef.current.signal,
    isHydrating,
    markHydrated,
    registerHook,
  }
}
