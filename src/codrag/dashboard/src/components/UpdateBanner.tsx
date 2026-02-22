import { useState, useEffect, useCallback, useRef } from 'react'
import { Download, RefreshCw, X, ExternalLink } from 'lucide-react'
import { Button } from '@codrag/ui'

type UpdateStatus = 'idle' | 'available' | 'downloading' | 'ready' | 'error'

interface UpdateManifest {
  version: string
  date?: string
  body?: string
}

interface UpdateBannerProps {
  checkIntervalMs?: number
}

// Detect if running inside Tauri
const isTauri = typeof window !== 'undefined' && !!(window as any).__TAURI__

export function UpdateBanner({ checkIntervalMs = 30 * 60 * 1000 }: UpdateBannerProps) {
  const [status, setStatus] = useState<UpdateStatus>('idle')
  const [manifest, setManifest] = useState<UpdateManifest | null>(null)
  const [dismissed, setDismissed] = useState(false)
  const [downloadProgress, setDownloadProgress] = useState(0)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const unlistenRef = useRef<(() => void) | null>(null)

  const checkForUpdate = useCallback(async () => {
    if (!isTauri) return

    try {
      const { checkUpdate } = await import('@tauri-apps/api/updater')
      const { shouldUpdate, manifest: m } = await checkUpdate()

      if (shouldUpdate && m) {
        setManifest({ version: m.version, date: m.date, body: m.body })
        setStatus('available')
        setDismissed(false)
      }
    } catch (e) {
      // Silently fail — no internet, server unreachable, etc.
      console.debug('[Updater] Check failed:', e)
    }
  }, [])

  // Periodic check
  useEffect(() => {
    if (!isTauri) return

    // Check on mount (after a short delay to let the app settle)
    const initialTimeout = setTimeout(checkForUpdate, 5000)
    const interval = setInterval(checkForUpdate, checkIntervalMs)

    return () => {
      clearTimeout(initialTimeout)
      clearInterval(interval)
    }
  }, [checkForUpdate, checkIntervalMs])

  // Cleanup updater event listener
  useEffect(() => {
    return () => {
      if (unlistenRef.current) {
        unlistenRef.current()
        unlistenRef.current = null
      }
    }
  }, [])

  const handleInstall = async () => {
    if (!isTauri) return

    setStatus('downloading')
    setDownloadProgress(0)

    try {
      const { installUpdate, onUpdaterEvent } = await import('@tauri-apps/api/updater')
      const { relaunch } = await import('@tauri-apps/api/process')

      // Listen for progress events
      const unlisten = await onUpdaterEvent(({ error, status: eventStatus }) => {
        if (error) {
          console.error('[Updater] Event error:', error)
          setStatus('error')
          setErrorMsg(String(error))
          return
        }

        switch (eventStatus) {
          case 'PENDING':
            setDownloadProgress(prev => Math.min(prev + 10, 90))
            break
          case 'DONE':
            setDownloadProgress(100)
            setStatus('ready')
            break
          case 'ERROR':
            setStatus('error')
            setErrorMsg('Update installation failed')
            break
        }
      })

      unlistenRef.current = unlisten

      // Start install (downloads + installs)
      await installUpdate()

      // On macOS/Linux, we need to manually relaunch
      // On Windows, the installer handles restart automatically
      await relaunch()
    } catch (e: any) {
      console.error('[Updater] Install failed:', e)
      setStatus('error')
      setErrorMsg(e?.message || 'Failed to install update')
    }
  }

  // Nothing to show
  if (!isTauri || status === 'idle' || dismissed) {
    return null
  }

  if (status === 'error') {
    return (
      <div className="fixed inset-x-0 top-0 z-[90] bg-warning/90 backdrop-blur text-warning-foreground px-4 py-2 text-sm font-medium flex items-center justify-center gap-3 shadow-lg">
        <RefreshCw className="w-4 h-4 flex-shrink-0" />
        <span>Update failed: {errorMsg || 'Unknown error'}</span>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => {
            setStatus('available')
            setErrorMsg(null)
          }}
        >
          Retry
        </Button>
        <button
          onClick={() => { setDismissed(true); setStatus('idle') }}
          className="ml-2 opacity-70 hover:opacity-100 transition-opacity"
          aria-label="Dismiss"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    )
  }

  if (status === 'downloading' || status === 'ready') {
    return (
      <div className="fixed inset-x-0 top-0 z-[90] bg-primary/95 backdrop-blur text-white px-4 py-2 text-sm font-medium shadow-lg">
        <div className="flex items-center justify-center gap-3">
          <Download className="w-4 h-4 flex-shrink-0 animate-pulse" />
          <span>
            {status === 'ready'
              ? 'Update installed. Restarting...'
              : 'Downloading update...'}
          </span>
        </div>
        <div className="mt-1 max-w-md mx-auto">
          <div className="h-1 bg-white/20 rounded-full overflow-hidden">
            <div
              className="h-full bg-white rounded-full transition-all duration-300"
              style={{ width: `${downloadProgress}%` }}
            />
          </div>
        </div>
      </div>
    )
  }

  // status === 'available'
  return (
    <div className="fixed inset-x-0 top-0 z-[90] bg-primary/95 backdrop-blur text-white px-4 py-2 text-sm font-medium flex items-center justify-center gap-3 shadow-lg">
      <Download className="w-4 h-4 flex-shrink-0" />
      <span>
        CoDRAG <strong>v{manifest?.version}</strong> is available.
      </span>
      {manifest?.body && (
        <button
          onClick={() => {
            if (manifest.body) {
              // Open release notes — could be a modal, for now just log
              window.open(
                `https://github.com/EricBintner/CoDRAG/releases/tag/app-v${manifest.version}`,
                '_blank'
              )
            }
          }}
          className="underline underline-offset-2 opacity-80 hover:opacity-100 flex items-center gap-1"
        >
          <ExternalLink className="w-3 h-3" />
          What&apos;s new
        </button>
      )}
      <Button
        variant="secondary"
        size="sm"
        onClick={handleInstall}
        icon={Download}
      >
        Update &amp; Restart
      </Button>
      <button
        onClick={() => setDismissed(true)}
        className="ml-2 opacity-70 hover:opacity-100 transition-opacity"
        aria-label="Dismiss"
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  )
}
