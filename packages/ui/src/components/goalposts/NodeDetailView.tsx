import { useMemo } from 'react';
import { Bot, GitBranch, Shield, Star, Activity, Copy, CheckCircle, Trash2, Map } from 'lucide-react';
import type { RoadmapNode, RoadmapTier } from '../../types';
import { Button } from '../primitives/Button';
import { cn } from '../../lib/utils';
import { CATEGORY_LABEL, CATEGORY_COLOR } from './colors';

export interface NodeDetailViewProps {
  node: RoadmapNode;
  isNorthStar: boolean;
  onPromote?: (tier: RoadmapTier) => void;
  onDismiss?: () => void;
  onPushToGitHub?: () => void;
  onCopyForAI?: () => void;
  onDelete?: () => void;
}

export function NodeDetailView({
  node,
  isNorthStar,
  onPromote,
  onDismiss,
  onPushToGitHub,
  onCopyForAI,
  onDelete,
}: NodeDetailViewProps) {
  
  const categoryLabel = CATEGORY_LABEL[node.category] || node.category;
  const categoryColor = CATEGORY_COLOR[node.category] || '#94a3b8';

  const sourceIcon = useMemo(() => {
    switch (node.source) {
      case 'github': return <GitBranch className="h-4 w-4" />;
      case 'ai_proposed': return <Bot className="h-4 w-4" />;
      case 'todo_scan': return <CheckCircle className="h-4 w-4" />;
      default: return null;
    }
  }, [node.source]);

  const sourceLabel = useMemo(() => {
    switch (node.source) {
      case 'github': return 'GitHub Sync';
      case 'ai_proposed': return 'AI Proposal';
      case 'todo_scan': return 'TODO Scan';
      default: return 'Manual Entry';
    }
  }, [node.source]);

  // Try to parse GitHub issue number from source_ref if available
  const githubIssueNumber = useMemo(() => {
    if (node.source === 'github' && node.source_ref) {
      // E.g. "https://github.com/org/repo/issues/123"
      const match = node.source_ref.match(/\/issues\/(\d+)$/);
      if (match) return match[1];
    }
    return null;
  }, [node.source, node.source_ref]);

  return (
    <div className="flex flex-col h-full backdrop-blur-sm p-6 overflow-y-auto w-full">
      {/* North Star Banner */}
      {isNorthStar && (
        <div className="flex items-center gap-2 mb-4 bg-amber-500/10 border border-amber-500/30 rounded-lg px-3 py-2">
          <Star className="h-4 w-4 text-amber-400 fill-amber-400" />
          <span className="text-xs font-semibold text-amber-400 uppercase tracking-wide">
            This is your North Star
          </span>
        </div>
      )}

      {/* Header */}
      <div className="mb-6">
        <h2 className={cn(
          "text-xl font-bold text-text mb-3",
          node.state === 'dismissed' && "line-through opacity-50"
        )}>
          {node.title}
        </h2>
        
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="px-2 py-1 rounded bg-surface-raised font-bold text-text border border-border/50">
            {node.priority}
          </span>
          <span 
            className="px-2 py-1 rounded font-semibold text-white/90 border"
            style={{ 
              backgroundColor: `${categoryColor}30`, 
              borderColor: `${categoryColor}50`,
              color: categoryColor,
            }}
          >
            {categoryLabel}
          </span>
          <span className="flex items-center gap-1.5 text-text-muted px-2 py-1 rounded border border-border/30">
            {sourceIcon} {sourceLabel}
          </span>
          {node.source_ref && node.source === 'github' && (
            <a 
              href={node.source_ref} 
              target="_blank" 
              rel="noreferrer"
              className="flex items-center gap-1 text-primary hover:underline px-2 py-1 bg-primary/10 rounded"
            >
              Issue #{githubIssueNumber || 'Link'}
            </a>
          )}
        </div>
      </div>

      {/* Description */}
      {node.description && (
        <div className="mb-6">
          <h3 className="text-[10px] font-semibold text-text-muted uppercase tracking-wider mb-2">Description</h3>
          <p className="text-sm text-text-muted leading-relaxed whitespace-pre-wrap">
            {node.description}
          </p>
        </div>
      )}

      {/* Tasks */}
      {node.tasks && node.tasks.length > 0 && (
        <div className="mb-6">
          <h3 className="text-[10px] font-semibold text-text-muted uppercase tracking-wider mb-3">Tasks</h3>
          <div className="space-y-2">
            {node.tasks.map((task, i) => (
              <div key={i} className="flex items-start gap-3 p-3 rounded-lg bg-surface-raised border border-border/50">
                <div className="mt-0.5">
                  <div className="h-4 w-4 rounded-full border border-text-muted/50" />
                </div>
                <div className="flex-1">
                  <p className="text-sm text-text">
                    {task.description}
                  </p>
                </div>
                {task.effort && (
                  <span className="shrink-0 inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-surface text-text-muted border border-border shadow-sm">
                    <Activity className="h-3 w-3 mr-1 opacity-70" /> {task.effort}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Impact & Alignment */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
        {node.business_impact && (
          <div className="p-4 rounded-lg bg-indigo-500/5 border border-indigo-500/20">
            <h3 className="text-[10px] font-semibold text-indigo-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
              <Map className="h-3 w-3" /> Business Impact
            </h3>
            <p className="text-xs text-text-muted leading-relaxed">
              {node.business_impact}
            </p>
          </div>
        )}
        {node.ethos_alignment && (
          <div className="p-4 rounded-lg bg-emerald-500/5 border border-emerald-500/20">
            <h3 className="text-[10px] font-semibold text-emerald-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
              <Shield className="h-3 w-3" /> Ethos Alignment
            </h3>
            <p className="text-xs text-text-muted leading-relaxed">
              {node.ethos_alignment}
            </p>
          </div>
        )}
      </div>

      <div className="mt-auto pt-4 border-t border-border/50 flex flex-wrap items-center justify-between gap-4">
        {/* Actions */}
        <div className="flex items-center gap-2">
          {onPromote && node.tier !== 'completed' && node.state !== 'dismissed' && (
            <Button variant="default" onClick={() => onPromote(
              node.tier === 'proposed' ? 'planned' :
              node.tier === 'planned' ? 'active' : 'completed'
            )}>
              Promote to {
                node.tier === 'proposed' ? 'Planned' :
                node.tier === 'planned' ? 'Active' : 'Completed'
              }
            </Button>
          )}
          
          {onPushToGitHub && !githubIssueNumber && (
            <Button variant="outline" onClick={onPushToGitHub} className="gap-2">
              <GitBranch className="h-4 w-4" /> Push to GitHub
            </Button>
          )}
          
          {onDismiss && node.state !== 'dismissed' && node.tier !== 'completed' && (
            <Button variant="ghost" className="text-amber-500 hover:text-amber-400 hover:bg-amber-500/10" onClick={onDismiss}>
              Dismiss
            </Button>
          )}
        </div>
        
        <div className="flex items-center gap-2">
          {onCopyForAI && (
            <Button variant="outline" size="sm" onClick={onCopyForAI} className="h-8 text-xs gap-1.5" title="Copy for passing to LLMs">
              <Copy className="h-3.5 w-3.5" /> Copy
            </Button>
          )}
          {onDelete && (
            <Button variant="ghost" size="sm" onClick={onDelete} className="h-8 text-xs text-red-500 hover:text-red-400 hover:bg-red-500/10" title="Delete permanently">
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
