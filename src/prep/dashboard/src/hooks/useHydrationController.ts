import { useState, useEffect, useRef } from 'react'

export interface HydrationController {
  /** The debounced project ID — hooks should hydrate against this, not the raw selection */
  hydratedProjectId: string | null
  /** AbortSignal that gets aborted on every project switch. Pass to fetch calls. */
  signal: AbortSignal
  /** True during the debounce window after a project switch. Polls should wait. */
  isHydrating: boolean
}

// 250ms debounce prevents rapid project clicks from flooding the daemon
// with requests that pile up in its thread pool (each click fires ~20 API
// calls, and aborted requests still process server-side)
const DEBOUNCE_MS = 250

export function useHydrationController(rawProjectId: string | null): HydrationController {
  const [hydratedProjectId, setHydratedProjectId] = useState<string | null>(rawProjectId)
  const [isHydrating, setIsHydrating] = useState(false)
  const abortRef = useRef<AbortController>(new AbortController())
  const debounceRef = useRef<NodeJS.Timeout | null>(null)
  const prevProjectRef = useRef<string | null>(rawProjectId)

  // Abort + replace synchronously during render so that hooks called
  // AFTER this one in the same render cycle get the NEW signal, not
  // the one that's about to be aborted.
  if (prevProjectRef.current !== rawProjectId) {
    abortRef.current.abort()
    abortRef.current = new AbortController()
    prevProjectRef.current = rawProjectId
  }

  // Handle debounce and isHydrating state transitions in an effect
  useEffect(() => {
    if (debounceRef.current) {
      clearTimeout(debounceRef.current)
    }

    if (!rawProjectId) {
      setHydratedProjectId(null)
      setIsHydrating(false)
      return
    }

    // Suppress polls during the debounce window
    setIsHydrating(true)

    // Debounce the actual project ID propagation
    debounceRef.current = setTimeout(() => {
      setHydratedProjectId(rawProjectId)
      setIsHydrating(false)
    }, DEBOUNCE_MS)

    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current)
      }
    }
  }, [rawProjectId])

  return {
    hydratedProjectId,
    signal: abortRef.current.signal,
    isHydrating,
  }
}
