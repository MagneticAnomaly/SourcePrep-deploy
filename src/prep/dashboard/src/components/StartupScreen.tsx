import { useState, useEffect, useRef } from 'react'
import { AlertCircle, RefreshCw, Power } from 'lucide-react'
import { Button } from '@prep/ui'

type StartupStage = 'connecting' | 'initializing' | 'ready'

interface StartupScreenProps {
  apiBaseUrl: string
  onReady: () => void
  timeoutMs?: number
  /** Override the displayed stage (e.g. 'initializing' while loading config). */
  stage?: StartupStage
  /** Custom subtitle text for the current stage. */
  stageMessage?: string
}

export function StartupScreen({ apiBaseUrl, onReady, timeoutMs = 30000, stage: externalStage, stageMessage }: StartupScreenProps) {
  const [status, setStatus] = useState<'connecting' | 'failed'>('connecting')
  const [attempts, setAttempts] = useState(0)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [retryKey, setRetryKey] = useState(0)
  const onReadyRef = useRef(onReady)
  useEffect(() => { onReadyRef.current = onReady }, [onReady])

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
          const data = await res.json()
          if (data && data.status === 'ok') {
            onReadyRef.current()
            return
          }
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
  }, [apiBaseUrl, timeoutMs, retryKey])

  const handleRetry = () => {
    setStatus('connecting')
    setAttempts(0)
    setErrorMsg(null)
    setRetryKey(k => k + 1)
  }

  // Determine displayed stage — external stage takes priority (e.g. 'initializing' after connection).
  const displayStage: StartupStage | 'failed' = externalStage ?? (status === 'connecting' ? 'connecting' : 'failed')

  const stageLabels: Record<StartupStage, { title: string; subtitle: string }> = {
    connecting: { title: 'Starting Engine', subtitle: 'Initializing local daemon and verifying ports' },
    initializing: { title: 'Loading Dashboard', subtitle: stageMessage || 'Loading projects and configuration…' },
    ready: { title: 'Ready', subtitle: 'Launching dashboard…' },
  }

  const currentLabel = displayStage !== 'failed' ? stageLabels[displayStage] : stageLabels.connecting

  if (displayStage !== 'failed' && status !== 'failed') {
    return (
      <div className="fixed inset-0 bg-background flex flex-col items-center justify-center p-4 z-50 overflow-hidden">
        <style>{`
          @keyframes loading-slide {
            0% { transform: translateX(-100%); }
            100% { transform: translateX(300%); }
          }
          @keyframes loading-float {
            0%, 100% { transform: translateY(0); }
            50% { transform: translateY(-10px); }
          }
          @keyframes loading-glow {
            0%, 100% { opacity: 0.15; transform: scale(1); filter: blur(60px); }
            50% { opacity: 0.3; transform: scale(1.1); filter: blur(80px); }
          }
          @keyframes loading-pulse-fast {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.7; }
          }
          .animate-loading-slide { animation: loading-slide 2s ease-in-out infinite; }
          .animate-loading-float { animation: loading-float 4s ease-in-out infinite; }
          .animate-loading-glow { animation: loading-glow 4s ease-in-out infinite; }
          .animate-loading-pulse-fast { animation: loading-pulse-fast 2s ease-in-out infinite; }
        `}</style>

        {/* Ambient background glow */}
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div className="w-[400px] h-[400px] bg-primary rounded-full animate-loading-glow"></div>
        </div>

        <div className="relative z-10 flex flex-col items-center">
          {/* Logo Container */}
          <div className="relative w-32 h-32 mb-8 flex items-center justify-center animate-loading-float">
            {/* Spinning Rings */}
            <div className="absolute inset-0 border-t-2 border-l-2 border-primary/80 rounded-full animate-spin"></div>
            <div className="absolute inset-2 border-r-2 border-b-2 border-primary/50 rounded-full animate-[spin_3s_linear_infinite_reverse]"></div>
            <div className="absolute inset-4 border-t-2 border-primary/30 rounded-full animate-[spin_4s_linear_infinite]"></div>
            
            {/* Transparent Logo */}
            <img 
              src="/prep-logo.png" 
              alt="Prep Logo" 
              className="w-16 h-16 object-contain animate-loading-pulse-fast"
              style={{ filter: 'drop-shadow(0 0 15px hsl(var(--primary) / 0.5))' }}
            />
          </div>

          {/* Text */}
          <h1 
            className="text-5xl font-black text-text mb-8 animate-loading-pulse-fast"
            style={{ 
              fontFamily: 'var(--font-sans, "Inter", system-ui, sans-serif)',
              letterSpacing: '-0.04em'
            }}
          >
            Prep
          </h1>
          
          <div className="flex flex-col items-center space-y-6">
            {/* Progress Bar */}
            <div className="h-1.5 w-64 bg-surface-raised rounded-full overflow-hidden relative shadow-inner">
               <div className="absolute top-0 bottom-0 left-0 w-1/3 bg-primary rounded-full animate-loading-slide shadow-[0_0_12px_hsl(var(--primary)_/_0.8)]"></div>
            </div>
            
            {/* Status Text */}
            <div className="flex flex-col items-center gap-2 text-center" style={{ fontFamily: '"Inter", system-ui, sans-serif' }}>
              <p className="text-sm text-text font-bold tracking-widest uppercase">
                {currentLabel.title}
              </p>
              <p className="text-sm text-text-muted font-medium">
                {currentLabel.subtitle}
              </p>
              {displayStage === 'connecting' && (
                <div className="mt-3 text-xs text-text-subtle font-mono flex items-center gap-2 bg-surface px-4 py-2 rounded-md border border-border/50 shadow-sm">
                  <span className="relative flex h-2 w-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-primary"></span>
                  </span>
                  Connecting to {apiBaseUrl} <span className="opacity-50">(Attempt {attempts + 1})</span>
                </div>
              )}
              {displayStage === 'initializing' && (
                <div className="mt-3 text-xs text-text-subtle font-mono flex items-center gap-2 bg-surface px-4 py-2 rounded-md border border-border/50 shadow-sm">
                  <span className="relative flex h-2 w-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-primary"></span>
                  </span>
                  {stageMessage || 'Hydrating dashboard state…'}
                </div>
              )}
            </div>
          </div>
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
          {errorMsg || 'Could not connect to the Prep daemon.'}
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
