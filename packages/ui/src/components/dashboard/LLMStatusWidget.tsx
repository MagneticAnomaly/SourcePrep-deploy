import { cn } from '../../lib/utils';
import { CheckCircle2, AlertCircle, CircleOff, HelpCircle } from 'lucide-react';
import { InfoTooltip } from '../primitives/InfoTooltip';

export interface LLMServiceStatus {
  name: string;
  url?: string; // This effectively holds the Provider Name (e.g., "Ollama", "OpenAI")
  model?: string; // The specific model name
  status: 'connected' | 'disconnected' | 'disabled' | 'not-configured';
  type: 'ollama' | 'clara' | 'openai' | 'other';
}

export interface LLMStatusWidgetProps {
  services: LLMServiceStatus[];
  className?: string;
  bare?: boolean;
}

export function LLMStatusWidget({ services, className, bare = false }: LLMStatusWidgetProps) {
  return (
    <div className={cn(
      !bare && 'border border-border bg-surface shadow-sm rounded-lg p-4',
      className
    )}>
      {!bare && (
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-text">AI Gateway</h3>
            <InfoTooltip 
              content="Configure your LLM providers." 
              href="https://docs.codrag.io/guides/models" 
            />
          </div>
        </div>
      )}
      
      <div className="space-y-2">
        {services.map((service) => {
          const isConnected = service.status === 'connected';
          const isConfigured = service.status !== 'not-configured' && service.status !== 'disabled';

          return (
            <div 
              key={service.name}
              className={cn(
                "group flex items-center justify-between p-3 rounded-lg transition-colors border",
                isConnected 
                  ? "bg-surface-raised border-border hover:border-success/30" 
                  : "bg-surface/50 border-transparent hover:bg-surface-raised/50"
              )}
            >
              <div className="flex items-center gap-3 overflow-hidden">
                {/* Status Icon */}
                <div className={cn(
                  "shrink-0 w-8 h-8 rounded-full flex items-center justify-center border",
                  isConnected ? "bg-success-muted/10 border-success-muted/20 text-success" :
                  service.status === 'disconnected' ? "bg-error-muted/10 border-error-muted/20 text-error" :
                  "bg-surface-raised border-border text-text-muted"
                )}>
                  {isConnected ? <CheckCircle2 className="w-4 h-4" /> :
                   service.status === 'disconnected' ? <AlertCircle className="w-4 h-4" /> :
                   service.status === 'not-configured' ? <HelpCircle className="w-4 h-4" /> :
                   <CircleOff className="w-4 h-4" />}
                </div>

                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className={cn(
                      "text-sm font-medium truncate",
                      isConnected ? "text-text" : "text-text-muted"
                    )}>
                      {service.name}
                    </span>
                    {isConnected && (
                      <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-success-muted/10 text-success">
                        Active
                      </span>
                    )}
                  </div>
                  
                  {isConfigured ? (
                    <div className="text-xs text-text-muted truncate flex items-center gap-1.5 mt-0.5">
                      <span className="font-medium text-text-subtle">{service.url}</span>
                      {service.model && (
                        <>
                          <span className="text-border">•</span>
                          <span className="opacity-75 truncate">{service.model}</span>
                        </>
                      )}
                    </div>
                  ) : (
                    <div className="text-xs text-text-muted/50 italic mt-0.5">
                      {service.status === 'not-configured' ? 'Not configured' : 'Disabled'}
                    </div>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
