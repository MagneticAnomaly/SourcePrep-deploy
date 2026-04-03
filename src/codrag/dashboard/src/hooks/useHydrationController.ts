import { useState, useEffect, useRef } from 'react'

export interface HydrationController {
  /** The debounced project ID — hooks should hydrate against this, not the raw selection */
  hydratedProjectId: string | null
  /** AbortSignal that gets aborted on every project switch. Pass to fetch calls. */
  signal: AbortSignal
  /** True during the debounce window after a project switch. Polls should wait. */
  isHydrating: boolean
}

const DEBOUNCE_MS = 100

export function useHydrationController(rawProjectId: string | null): HydrationController {
  const [hydratedProjectId, setHydratedProjectId] = useState<string | null>(rawProjectId)
  const [isHydrating, setIsHydrating] = useState(false)
  const abortRef = useRef<AbortController>(new AbortController())
  const debounceRef = useRef<NodeJS.Timeout | null>(null)

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
      return
    }

    // Suppress polls during the debounce window
    setIsHydrating(true)

    // Debounce the actual project ID propagation
    debounceRef.current = setTimeout(() => {
      setHydratedProjectId(rawProjectId)
      // Debounce complete — hooks will now fire their hydration effects.
      // Reset isHydrating so polls can resume once those effects settle.
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
