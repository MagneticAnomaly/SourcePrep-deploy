import { Target, Check, BrainCircuit } from 'lucide-react';
import type { SprintSuggestion } from '../../types';
import { Button } from '../primitives/Button';

export interface SprintCardProps {
  suggestion: SprintSuggestion | null;
  loading: boolean;
  onRefresh?: () => void;
}

export function SprintCard({ suggestion, loading, onRefresh }: SprintCardProps) {
  if (loading) {
    return (
      <div className="flex flex-col animate-pulse border border-border/50 bg-surface/30 rounded-lg p-4">
        <div className="h-4 w-32 bg-surface-raised mb-4 rounded" />
        <div className="space-y-2">
          <div className="h-8 w-full bg-surface-raised rounded opacity-50" />
          <div className="h-8 w-full bg-surface-raised rounded opacity-50" />
        </div>
      </div>
    );
  }

  if (!suggestion) {
    return (
      <div className="flex flex-col items-center justify-center p-6 border border-border/50 bg-surface/30 rounded-lg text-text-muted">
        <BrainCircuit className="h-6 w-6 text-text-muted/50 mb-2" />
        <p className="text-xs font-medium">Sprint Suggestion Unavailable</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col border border-indigo-500/20 bg-indigo-500/5 rounded-lg overflow-hidden">
      <div className="flex items-center justify-between px-3 py-2 border-b border-indigo-500/10 bg-indigo-500/10">
        <span className="text-[10px] font-semibold text-indigo-400 flex items-center gap-1.5 uppercase tracking-wider">
          <Target className="h-3 w-3" /> AI Sprint Planner
        </span>
        <div className="text-[10px] text-indigo-400 font-medium bg-indigo-500/20 px-1.5 py-0.5 rounded flex items-center gap-1">
          {suggestion.capacity} capacity
        </div>
      </div>
      
      <div className="p-4 space-y-4">
        {suggestion.rationale && (
          <p className="text-xs text-text-muted leading-relaxed">
            {suggestion.rationale}
          </p>
        )}
        
        {suggestion.confidence > 0 && (
          <div className="flex items-center gap-2">
            <div className="flex-1 h-1.5 bg-surface-raised rounded-full overflow-hidden">
              <div 
                className="h-full bg-indigo-500 rounded-full" 
                style={{ width: `${suggestion.confidence * 100}%` }} 
              />
            </div>
            <span className="text-[10px] text-text-muted shrink-0 font-mono">
              {Math.round(suggestion.confidence * 100)}% Match
            </span>
          </div>
        )}

        {suggestion.node_details && suggestion.node_details.length > 0 && (
          <div className="space-y-1.5 pt-2">
            <h4 className="text-[10px] uppercase font-semibold text-text-muted mb-2 tracking-wider">
              {suggestion.sprint_label || 'Proposed Sprint'}
            </h4>
            {suggestion.node_details.map(node => (
              <div key={node.id} className="flex items-center gap-2 p-2 bg-surface-raised border border-border/50 rounded-md">
                <Check className="h-3 w-3 text-indigo-400 shrink-0" />
                <span className="text-xs font-medium text-text truncate">{node.title}</span>
                <span className="ml-auto text-[9px] font-bold text-text-muted shrink-0 px-1 bg-surface rounded">
                  {node.priority}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {onRefresh && (
        <div className="px-4 pb-4">
          <Button variant="outline" size="sm" onClick={onRefresh} className="w-full text-xs">
            Generate New Plan
          </Button>
        </div>
      )}
    </div>
  );
}
