import { useEffect, useMemo, useRef } from 'react'
import { createDebouncedSaver, type DebouncedSaver } from '@codrag/ui/lib/debouncedSaver'

export interface UseDebouncedAutoSaveOptions<T> {
  value: T
  onSave: (value: T) => Promise<void> | void
  delayMs?: number
  onPersist?: (value: T) => void
  equals?: (a: T, b: T) => boolean
  /** When false, schedule/flush are suppressed. Flip to true after initial hydrate. */
  enabled?: boolean
}

export interface UseDebouncedAutoSaveResult {
  flush: () => Promise<void>
}

/** Schedules a trailing-edge debounced save whenever `value` changes.
 *  Flushes any pending save synchronously on unmount. */
export function useDebouncedAutoSave<T>(opts: UseDebouncedAutoSaveOptions<T>): UseDebouncedAutoSaveResult {
  const { value, enabled = true, delayMs = 1500 } = opts

  // Stable refs for callbacks so the saver identity doesn't change every render.
  const onSaveRef = useRef(opts.onSave)
  onSaveRef.current = opts.onSave
  const onPersistRef = useRef(opts.onPersist)
  onPersistRef.current = opts.onPersist
  const equalsRef = useRef(opts.equals)
  equalsRef.current = opts.equals

  const saver: DebouncedSaver<T> = useMemo(
    () =>
      createDebouncedSaver<T>({
        onSave: (v) => onSaveRef.current(v),
        delayMs,
        onPersist: (v) => onPersistRef.current?.(v),
        equals: equalsRef.current ? (a, b) => equalsRef.current!(a, b) : undefined,
      }),
    [delayMs],
  )

  // Track whether we've seen the first enabled render so we can baseline.
  const hydratedRef = useRef(false)
  useEffect(() => {
    if (!enabled) return
    if (!hydratedRef.current) {
      hydratedRef.current = true
      return // baseline: don't save the initial value
    }
    saver.schedule(value)
  }, [value, enabled, saver])

  // Flush on unmount.
  useEffect(() => {
    return () => {
      void saver.flush()
    }
  }, [saver])

  return {
    flush: () => saver.flush(),
  }
}
