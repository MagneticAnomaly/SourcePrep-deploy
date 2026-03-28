/**
 * RoadmapTimeline — Pure React SVG vertical timeline (Phase 59).
 *
 * Renders a top-to-bottom vertical timeline with 4 tiers:
 *   Completed (top) → Active → Planned → Proposed (bottom)
 *
 * Each tier is a horizontally separated section with a center spine.
 * Nodes are rendered as cards offset left/right from the spine.
 * The Active tier's highest-priority node is the "North Star" (⭐).
 *
 * Design:
 *   - Pure React SVG + HTML overlay (no D3 dependency needed)
 *   - SVG draws the spine, tier labels, and connecting lines
 *   - HTML overlay renders the interactive node cards via CSS position
 *   - Proposed tier uses dotted spine line (user design decision)
 */
import { useMemo, useState } from 'react';
import {
  Star,
  ChevronDown,
  ChevronUp,
  Check,
  Circle,
  Clock,
  Lightbulb,
  Search,
  GitBranch,
} from 'lucide-react';
import { cn } from '../../lib/utils';
import type { RoadmapNode, RoadmapTier, RoadmapNorthStar } from '../../types';

// ── Layout constants ────────────────────────────────────────────

const TIER_CONFIG: Record<RoadmapTier, {
  label: string;
  emoji: string;
  color: string;
  bgColor: string;
  borderColor: string;
  spineColor: string;
  dashArray?: string;
}> = {
  completed: {
    label: 'Completed',
    emoji: '✅',
    color: 'text-emerald-400',
    bgColor: 'bg-emerald-500/10',
    borderColor: 'border-emerald-500/30',
    spineColor: '#34d399',
  },
  active: {
    label: 'Active',
    emoji: '🔥',
    color: 'text-amber-400',
    bgColor: 'bg-amber-500/10',
    borderColor: 'border-amber-500/30',
    spineColor: '#fbbf24',
  },
  planned: {
    label: 'Planned',
    emoji: '📋',
    color: 'text-blue-400',
    bgColor: 'bg-blue-500/10',
    borderColor: 'border-blue-500/30',
    spineColor: '#60a5fa',
  },
  proposed: {
    label: 'Proposed',
    emoji: '💡',
    color: 'text-purple-400',
    bgColor: 'bg-purple-500/10',
    borderColor: 'border-purple-500/30',
    spineColor: '#a78bfa',
    dashArray: '6,4',
  },
};

const TIERS_ORDER: RoadmapTier[] = ['completed', 'active', 'planned', 'proposed'];

const CATEGORY_BADGE: Record<string, { color: string; label: string }> = {
  architecture: { color: 'bg-violet-500/20 text-violet-400', label: 'Arch' },
  security: { color: 'bg-red-500/20 text-red-400', label: 'Sec' },
  feature: { color: 'bg-blue-500/20 text-blue-400', label: 'Feat' },
  tech_debt: { color: 'bg-amber-500/20 text-amber-400', label: 'Debt' },
  research: { color: 'bg-emerald-500/20 text-emerald-400', label: 'R&D' },
  product: { color: 'bg-cyan-500/20 text-cyan-400', label: 'UX' },
  market: { color: 'bg-pink-500/20 text-pink-400', label: 'Mkt' },
};

const PRIORITY_BADGE: Record<string, string> = {
  P0: 'bg-red-500/20 text-red-400',
  P1: 'bg-amber-500/20 text-amber-400',
  P2: 'bg-blue-500/20 text-blue-400',
  P3: 'bg-slate-500/20 text-slate-400',
};

const SOURCE_ICON: Record<string, typeof Star> = {
  manual: Circle,
  ai_proposed: Lightbulb,
  todo_scan: Search,
  github: GitBranch,
};

// ── Props ───────────────────────────────────────────────────────

export interface RoadmapTimelineProps {
  nodes: RoadmapNode[];
  northStar: RoadmapNorthStar | null;
  onNodeClick?: (nodeId: string) => void;
  onPromoteNode?: (nodeId: string, targetTier: RoadmapTier) => void;
  onDismissNode?: (nodeId: string) => void;
  selectedNodeId?: string | null;
  className?: string;
}

// ── Node Card ───────────────────────────────────────────────────

function NodeCard({
  node,
  isNorthStar,
  isSelected,
  side,
  onClick,
  onPromote,
  onDismiss,
}: {
  node: RoadmapNode;
  isNorthStar: boolean;
  isSelected: boolean;
  side: 'left' | 'right';
  onClick?: () => void;
  onPromote?: () => void;
  onDismiss?: () => void;
}) {
  const tierCfg = TIER_CONFIG[node.tier] || TIER_CONFIG.proposed;
  const catBadge = CATEGORY_BADGE[node.category] || CATEGORY_BADGE.feature;
  const priColor = PRIORITY_BADGE[node.priority] || PRIORITY_BADGE.P2;
  const SourceIcon = SOURCE_ICON[node.source] || Circle;

  return (
    <div
      className={cn(
        'group relative rounded-lg border px-3 py-2.5 transition-all duration-200 cursor-pointer',
        'hover:shadow-lg hover:shadow-black/20 hover:-translate-y-0.5',
        tierCfg.bgColor,
        tierCfg.borderColor,
        isSelected && 'ring-2 ring-primary/50 shadow-lg shadow-primary/10',
        isNorthStar && 'ring-2 ring-amber-400/40 shadow-lg shadow-amber-500/10',
        side === 'left' ? 'mr-2' : 'ml-2',
      )}
      onClick={onClick}
    >
      {/* North Star indicator */}
      {isNorthStar && (
        <div className="absolute -top-2 -right-2 bg-amber-500 rounded-full p-0.5 shadow-md">
          <Star className="h-3 w-3 text-black fill-black" />
        </div>
      )}

      {/* Header row: priority + category + source */}
      <div className="flex items-center gap-1.5 mb-1">
        <span className={cn('inline-flex items-center rounded px-1 py-0.5 text-[9px] font-bold uppercase tracking-wide', priColor)}>
          {node.priority}
        </span>
        <span className={cn('inline-flex items-center rounded px-1 py-0.5 text-[9px] font-semibold uppercase tracking-wide', catBadge.color)}>
          {catBadge.label}
        </span>
        <SourceIcon className="h-3 w-3 text-text-muted/60 ml-auto" />
      </div>

      {/* Title */}
      <p className={cn(
        'text-xs font-medium leading-snug',
        node.state === 'dismissed' ? 'text-text-muted line-through' : 'text-text',
      )}>
        {node.title}
      </p>

      {/* Task count */}
      {node.tasks.length > 0 && (
        <p className="text-[10px] text-text-muted mt-1">
          {node.tasks.length} task{node.tasks.length !== 1 ? 's' : ''}
        </p>
      )}

      {/* Action buttons (show on hover) */}
      {(onPromote || onDismiss) && (
        <div className="absolute -bottom-1 right-1 opacity-0 group-hover:opacity-100 transition-opacity flex gap-1">
          {onPromote && node.tier !== 'completed' && (
            <button
              onClick={(e) => { e.stopPropagation(); onPromote(); }}
              className="p-1 rounded bg-emerald-500/20 hover:bg-emerald-500/40 transition-colors"
              title="Promote to next tier"
            >
              <ChevronUp className="h-3 w-3 text-emerald-400" />
            </button>
          )}
          {onDismiss && node.state !== 'completed' && (
            <button
              onClick={(e) => { e.stopPropagation(); onDismiss(); }}
              className="p-1 rounded bg-red-500/20 hover:bg-red-500/40 transition-colors"
              title="Dismiss"
            >
              <Check className="h-3 w-3 text-red-400" />
            </button>
          )}
        </div>
      )}
    </div>
  );
}

// ── Tier Section ────────────────────────────────────────────────

function TierSection({
  tier,
  nodes,
  northStarId,
  selectedNodeId,
  onNodeClick,
  onPromoteNode,
  onDismissNode,
  defaultExpanded = true,
}: {
  tier: RoadmapTier;
  nodes: RoadmapNode[];
  northStarId: string | null;
  selectedNodeId?: string | null;
  onNodeClick?: (nodeId: string) => void;
  onPromoteNode?: (nodeId: string, targetTier: RoadmapTier) => void;
  onDismissNode?: (nodeId: string) => void;
  defaultExpanded?: boolean;
}) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const config = TIER_CONFIG[tier];
  const sorted = useMemo(() =>
    [...nodes].sort((a, b) => a.position - b.position),
    [nodes]
  );

  // Promotion target tier mapping
  const promoteTo: Record<RoadmapTier, RoadmapTier> = {
    proposed: 'planned',
    planned: 'active',
    active: 'completed',
    completed: 'completed',
  };

  return (
    <div className="relative">
      {/* Tier header with spine dot */}
      <div className="flex items-center gap-2 py-2">
        {/* Spine dot */}
        <div className="flex items-center justify-center w-8">
          <div
            className="w-3 h-3 rounded-full border-2"
            style={{ borderColor: config.spineColor, backgroundColor: `${config.spineColor}40` }}
          />
        </div>

        {/* Label */}
        <button
          onClick={() => setExpanded(!expanded)}
          className={cn(
            'flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider transition-colors',
            config.color,
          )}
        >
          <span>{config.emoji}</span>
          <span>{config.label}</span>
          <span className="text-text-muted/60 font-normal normal-case lowercase">({nodes.length})</span>
          {expanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
        </button>
      </div>

      {/* Nodes grid */}
      {expanded && sorted.length > 0 && (
        <div className="relative ml-8 pl-4 border-l-2" style={{ borderColor: `${config.spineColor}40` }}>
          <div className="space-y-2 pb-3">
            {sorted.map((node, i) => (
              <div key={node.id} className="relative">
                {/* Connector line from spine to card */}
                <div
                  className="absolute left-[-16px] top-4 w-3 border-t"
                  style={{ borderColor: `${config.spineColor}60` }}
                />
                <NodeCard
                  node={node}
                  isNorthStar={node.id === northStarId}
                  isSelected={node.id === selectedNodeId}
                  side={i % 2 === 0 ? 'left' : 'right'}
                  onClick={() => onNodeClick?.(node.id)}
                  onPromote={onPromoteNode ? () => onPromoteNode(node.id, promoteTo[tier]) : undefined}
                  onDismiss={onDismissNode ? () => onDismissNode(node.id) : undefined}
                />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Empty tier message */}
      {expanded && sorted.length === 0 && (
        <div className="ml-8 pl-4 border-l-2 py-3" style={{ borderColor: `${config.spineColor}20` }}>
          <p className="text-[10px] text-text-muted italic">
            No {tier} items yet
          </p>
        </div>
      )}
    </div>
  );
}

// ── Main Timeline ───────────────────────────────────────────────

export function RoadmapTimeline({
  nodes,
  northStar,
  onNodeClick,
  onPromoteNode,
  onDismissNode,
  selectedNodeId,
  className,
}: RoadmapTimelineProps) {
  const nodesByTier = useMemo(() => {
    const grouped: Record<RoadmapTier, RoadmapNode[]> = {
      completed: [],
      active: [],
      planned: [],
      proposed: [],
    };
    for (const node of nodes) {
      if (node.state !== 'dismissed') {
        const tier = node.tier as RoadmapTier;
        if (grouped[tier]) grouped[tier].push(node);
      }
    }
    return grouped;
  }, [nodes]);

  const totalCount = useMemo(
    () => TIERS_ORDER.reduce((sum, t) => sum + nodesByTier[t].length, 0),
    [nodesByTier]
  );

  return (
    <div className={cn('relative', className)}>
      {/* North Star banner */}
      {northStar && (
        <div className="flex items-center gap-2 px-3 py-2 mb-3 rounded-lg bg-amber-500/10 border border-amber-500/30">
          <Star className="h-4 w-4 text-amber-400 fill-amber-400" />
          <div className="flex-1 min-w-0">
            <p className="text-[10px] font-semibold text-amber-400 uppercase tracking-wider">North Star</p>
            <p className="text-xs text-text font-medium truncate">{northStar.title}</p>
          </div>
          <span className={cn('inline-flex items-center rounded px-1 py-0.5 text-[9px] font-bold uppercase', PRIORITY_BADGE[northStar.priority])}>
            {northStar.priority}
          </span>
        </div>
      )}

      {/* Timeline spine */}
      {totalCount === 0 ? (
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <Clock className="h-10 w-10 text-text-muted/30 mb-3" />
          <p className="text-sm font-medium text-text">Empty Roadmap</p>
          <p className="text-xs text-text-muted mt-1 max-w-xs">
            Generate proposals, scan for TODOs, or manually add items to start building your roadmap.
          </p>
        </div>
      ) : (
        <div className="space-y-1">
          {TIERS_ORDER.map((tier) => (
            <TierSection
              key={tier}
              tier={tier}
              nodes={nodesByTier[tier]}
              northStarId={northStar?.id ?? null}
              selectedNodeId={selectedNodeId}
              onNodeClick={onNodeClick}
              onPromoteNode={onPromoteNode}
              onDismissNode={onDismissNode}
              defaultExpanded={tier !== 'completed'}
            />
          ))}
        </div>
      )}
    </div>
  );
}
