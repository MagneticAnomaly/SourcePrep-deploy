import { useState, useEffect } from 'react'
import { AlertCircle, RefreshCw, Power } from 'lucide-react'
import { Button, LoadingState } from '@codrag/ui'

interface StartupScreenProps {
  apiBaseUrl: string
  onReady: () => void
  timeoutMs?: number
}

export function StartupScreen({ apiBaseUrl, onReady, timeoutMs = 30000 }: StartupScreenProps) {
  const [status, setStatus] = useState<'connecting' | 'failed'>('connecting')
  const [attempts, setAttempts] = useState(0)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  useEffect(() => {
    let mounted = true
    const start = Date.now()
    let timeoutId: NodeJS.Timeout

    const checkHealth = async () => {
      try {
        const res = await fetch(`${apiBaseUrl}/health`, { 
            headers: { Accept: 'application/json' } 
        })
        if (res.ok && mounted) {
          onReady()
          return
        }
      } catch (e) {
        // ignore errors while polling
      }

      if (!mounted) return

      if (Date.now() - start > timeoutMs) {
        setStatus('failed')
        setErrorMsg('Connection timed out. The backend daemon failed to start.')
      } else {
        setAttempts(p => p + 1)
        timeoutId = setTimeout(checkHealth, 1000)
      }
    }

    checkHealth()

    return () => {
      mounted = false
      clearTimeout(timeoutId)
    }
  }, [apiBaseUrl, onReady, timeoutMs, attempts]) // Depend on attempts to trigger re-poll if needed, though recursive timeout handles it. Actually recursive is better.

  const handleRetry = () => {
    setStatus('connecting')
    setAttempts(0)
    setErrorMsg(null)
  }

  if (status === 'connecting') {
    return (
      <div className="fixed inset-0 bg-background flex flex-col items-center justify-center p-4 z-50">
        <LoadingState 
          message="Starting CoDRAG engine..." 
        />
        <p className="text-sm text-text-muted mt-2">Initializing local daemon and verifying ports.</p>
        <div className="mt-8 text-xs text-text-muted font-mono">
          Connecting to {apiBaseUrl} (Attempt {attempts + 1})
        </div>
      </div>
    )
  }

  return (
    <div className="fixed inset-0 bg-background flex flex-col items-center justify-center p-4 z-50">
      <div className="max-w-md w-full bg-surface border border-border rounded-lg p-8 shadow-xl text-center">
        <div className="mx-auto w-12 h-12 bg-error/10 rounded-full flex items-center justify-center mb-6">
          <AlertCircle className="w-6 h-6 text-error" />
        </div>
        <h2 className="text-xl font-bold text-text mb-2">Backend Connection Failed</h2>
        <p className="text-text-muted mb-6">
          {errorMsg || 'Could not connect to the CoDRAG daemon.'}
        </p>
        
        <div className="flex gap-3 justify-center">
          <Button onClick={handleRetry} icon={RefreshCw}>
            Retry Connection
          </Button>
          <Button variant="outline" onClick={() => window.close()} icon={Power}>
            Quit App
          </Button>
        </div>

        <div className="mt-8 p-4 bg-surface-raised rounded text-left">
          <p className="text-xs font-bold text-text mb-2 uppercase tracking-wider">Troubleshooting</p>
          <ul className="text-xs text-text-muted space-y-1 list-disc pl-4">
            <li>Check if port 8400 is occupied by another application.</li>
            <li>Verify you have Python 3.10+ installed if running in dev mode.</li>
            <li>Check <code>daemon.log</code> in the app data directory.</li>
          </ul>
        </div>
      </div>
    </div>
  )
}
