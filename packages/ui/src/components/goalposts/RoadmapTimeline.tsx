/**
 * RoadmapTimeline — Interactive SVG circle-line roadmap visualization (Phase 59C).
 *
 * Renders a vertical SVG canvas with:
 *   - Center spine line (solid/dashed/dotted per tier)
 *   - Circle nodes positioned along the spine
 *   - Visual encoding: size=priority, color=category, border=source, fill=state
 *   - North Star = star overlay on active tier
 *   - Hover tooltips with full node details
 *   - Click to select, promote/dismiss actions
 *
 * This replaces the card-based layout with a cleaner data-viz approach.
 * Pure React SVG — no D3 dependency needed for this deterministic layout.
 */
import { useMemo, useCallback } from 'react';
import { Clock, Star } from 'lucide-react';
import { cn } from '../../lib/utils';
import type { RoadmapNode, RoadmapTier, RoadmapNorthStar } from '../../types';

// ── Visual Encoding Config ──────────────────────────────────────

const TIER_CONFIG: Record<RoadmapTier, {
  label: string;
  emoji: string;
  spineColor: string;
  fillOpacity: number;
  dashArray: string;
}> = {
  completed: { label: 'Completed', emoji: '✅', spineColor: '#34d399', fillOpacity: 1.0, dashArray: '' },
  active: { label: 'Active ★', emoji: '🔥', spineColor: '#fbbf24', fillOpacity: 0.9, dashArray: '' },
  planned: { label: 'Planned', emoji: '📋', spineColor: '#60a5fa', fillOpacity: 0.6, dashArray: '8,4' },
  proposed: { label: 'Proposed', emoji: '💡', spineColor: '#a78bfa', fillOpacity: 0.3, dashArray: '4,4' },
};

const TIERS_ORDER: RoadmapTier[] = ['completed', 'active', 'planned', 'proposed'];

/** Circle size by priority */
const PRIORITY_RADIUS: Record<string, number> = {
  P0: 14,
  P1: 11,
  P2: 9,
  P3: 7,
};

import { CATEGORY_COLOR, CATEGORY_LABEL } from './colors';

/** Border style by source */
const SOURCE_BORDER: Record<string, { dasharray: string; width: number }> = {
  manual: { dasharray: '', width: 2 },
  ai_proposed: { dasharray: '4,2', width: 2 },
  todo_scan: { dasharray: '2,2', width: 2 },
  github: { dasharray: '', width: 3 },  // thicker for GitHub
};

// ── Layout Constants ────────────────────────────────────────────
const SPINE_X = 50;           // X position of the spine line
const NODE_START_X = 80;      // X where node labels start
const FORK_OFFSET_X = 30;     // Horizontal offset for forked nodes
const ROW_HEIGHT = 44;        // Vertical space per node
const TIER_HEADER_HEIGHT = 36;
const TIER_GAP = 12;
const TOP_PAD = 16;

// ── Props ───────────────────────────────────────────────────────

export interface RoadmapTimelineProps {
  nodes: RoadmapNode[];
  northStar: RoadmapNorthStar | null;
  onNodeClick?: (nodeId: string) => void;
  selectedNodeId?: string | null;
  className?: string;
}

// Tooltip removed in Phase 59E - using NodeDetailView instead.

// ── Legend ───────────────────────────────────────────────────────

function Legend() {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 px-3 py-2 border-b border-border/30 text-[9px] text-text-muted">
      <span className="font-semibold uppercase tracking-wider">Key:</span>
      <span>Size = Priority</span>
      <span className="flex items-center gap-1">
        <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ background: CATEGORY_COLOR.feature }} />
        =Feature
      </span>
      <span className="flex items-center gap-1">
        <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ background: CATEGORY_COLOR.architecture }} />
        =Arch
      </span>
      <span className="flex items-center gap-1">
        <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ background: CATEGORY_COLOR.tech_debt }} />
        =Debt
      </span>
      <span className="flex items-center gap-1">
        <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ background: CATEGORY_COLOR.security }} />
        =Sec
      </span>
      <span>Dashed = AI</span>
      <span>Dotted = TODO</span>
      <span>Thick = GitHub</span>
    </div>
  );
}

// ── Main Component ──────────────────────────────────────────────

export function RoadmapTimeline({
  nodes,
  northStar,
  onNodeClick,
  selectedNodeId,
  className,
}: RoadmapTimelineProps) {
  const nodesByTier = useMemo(() => {
    const grouped: Record<RoadmapTier, RoadmapNode[]> = {
      completed: [], active: [], planned: [], proposed: [],
    };
    for (const node of nodes) {
      if (node.state !== 'dismissed') {
        const tier = node.tier as RoadmapTier;
        if (grouped[tier]) grouped[tier].push(node);
      }
    }
    // Sort by position within each tier
    for (const tier of TIERS_ORDER) {
      grouped[tier].sort((a, b) => a.position - b.position);
    }
    return grouped;
  }, [nodes]);

  // Calculate layout positions
  const layout = useMemo(() => {
    const positions: Array<{
      node: RoadmapNode;
      tier: RoadmapTier;
      cx: number;
      cy: number;
      radius: number;
      color: string;
      fillOpacity: number;
      strokeDash: string;
      strokeWidth: number;
      isNorthStar: boolean;
      isFork: boolean;
      forkSide: 'left' | 'right' | 'center';
    }> = [];

    const tierRanges: Array<{
      tier: RoadmapTier;
      startY: number;
      endY: number;
      labelY: number;
    }> = [];

    let y = TOP_PAD;

    for (const tier of TIERS_ORDER) {
      const tierNodes = nodesByTier[tier];
      const tierConfig = TIER_CONFIG[tier];
      const startY = y;
      const labelY = y + TIER_HEADER_HEIGHT / 2;

      y += TIER_HEADER_HEIGHT;

      if (tierNodes.length === 0) {
        y += ROW_HEIGHT * 0.5; // slim empty tier
      }

      for (const node of tierNodes) {
        const radius = PRIORITY_RADIUS[node.priority] || 9;
        const color = CATEGORY_COLOR[node.category] || CATEGORY_COLOR.feature;
        const border = SOURCE_BORDER[node.source] || SOURCE_BORDER.manual;
        const isNorthStar = node.id === northStar?.id;
        const isFork = !!node.parent_id;
        // Alternate fork children left/right
        const forkIndex = isFork ? tierNodes.filter(
          (n, j) => j < tierNodes.indexOf(node) && n.parent_id === node.parent_id
        ).length : 0;
        const forkSide: 'left' | 'right' | 'center' = isFork
          ? (forkIndex % 2 === 0 ? 'left' : 'right')
          : 'center';
        const cx = isFork
          ? (forkSide === 'left' ? SPINE_X - FORK_OFFSET_X : SPINE_X + FORK_OFFSET_X)
          : SPINE_X;

        positions.push({
          node,
          tier,
          cx,
          cy: y + ROW_HEIGHT / 2,
          radius,
          color,
          fillOpacity: tierConfig.fillOpacity,
          strokeDash: border.dasharray,
          strokeWidth: border.width,
          isNorthStar,
          isFork,
          forkSide,
        });

        y += ROW_HEIGHT;
      }

      tierRanges.push({
        tier,
        startY,
        endY: y,
        labelY,
      });

      y += TIER_GAP;
    }

    return { positions, tierRanges, totalHeight: y + TOP_PAD };
  }, [nodesByTier, northStar]);

  const handleNodeClick = useCallback((nodeId: string) => {
    onNodeClick?.(nodeId);
  }, [onNodeClick]);

  const totalCount = TIERS_ORDER.reduce((sum, t) => sum + nodesByTier[t].length, 0);

  if (totalCount === 0) {
    return (
      <div className={cn('relative', className)}>
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <Clock className="h-10 w-10 text-text-muted/30 mb-3" />
          <p className="text-sm font-medium text-text">Empty Roadmap</p>
          <p className="text-xs text-text-muted mt-1 max-w-xs">
            Generate proposals, scan for TODOs, sync GitHub, or mine your codebase to populate the roadmap.
          </p>
        </div>
      </div>
    );
  }

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
          <span className="inline-flex items-center rounded px-1.5 py-0.5 text-[9px] font-bold uppercase bg-amber-500/20 text-amber-400">
            {northStar.priority}
          </span>
        </div>
      )}

      {/* Legend */}
      <Legend />

      {/* SVG Canvas */}
      <div className="overflow-auto min-h-0 h-full">
        <svg
          width="100%"
          height={layout.totalHeight}
          className="w-full"
          style={{ minWidth: 360 }}
        >
          {/* Tier spine segments */}
          {layout.tierRanges.map(({ tier, startY, endY }) => {
            const cfg = TIER_CONFIG[tier];
            return (
              <line
                key={`spine-${tier}`}
                x1={SPINE_X}
                y1={startY + TIER_HEADER_HEIGHT}
                x2={SPINE_X}
                y2={endY}
                stroke={cfg.spineColor}
                strokeWidth={2}
                strokeDasharray={cfg.dashArray}
                strokeOpacity={0.5}
              />
            );
          })}

          {/* Tier labels */}
          {layout.tierRanges.map(({ tier, labelY }) => {
            const cfg = TIER_CONFIG[tier];
            const count = nodesByTier[tier].length;
            return (
              <g key={`label-${tier}`}>
                <text
                  x={SPINE_X + 20}
                  y={labelY + 4}
                  className="fill-current"
                  style={{ fill: cfg.spineColor, fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em' }}
                >
                  {cfg.emoji} {cfg.label} ({count})
                </text>
                {/* Small dot on spine at tier header */}
                <circle cx={SPINE_X} cy={labelY} r={4} fill={cfg.spineColor} fillOpacity={0.4} />
              </g>
            );
          })}

          {/* Fork connectors (C-7): curved lines from parent to fork children */}
          {layout.positions.filter(p => p.isFork).map((forkPos) => {
            const parentPos = layout.positions.find(p => p.node.id === forkPos.node.parent_id);
            if (!parentPos) return null;

            // Quadratic bezier from parent to fork child
            const midY = (parentPos.cy + forkPos.cy) / 2;
            const path = `M ${parentPos.cx} ${parentPos.cy} Q ${forkPos.cx} ${midY} ${forkPos.cx} ${forkPos.cy}`;

            return (
              <g key={`fork-${forkPos.node.id}`}>
                <path
                  d={path}
                  fill="none"
                  stroke={forkPos.color}
                  strokeWidth={1.5}
                  strokeDasharray="6,3"
                  strokeOpacity={0.4}
                />
                {/* Fork label */}
                {forkPos.node.fork_label && (
                  <text
                    x={forkPos.cx + (forkPos.forkSide === 'left' ? -8 : 8)}
                    y={midY}
                    textAnchor={forkPos.forkSide === 'left' ? 'end' : 'start'}
                    style={{ fill: 'rgba(255,255,255,0.4)', fontSize: 8, fontStyle: 'italic' }}
                  >
                    {forkPos.node.fork_label}
                  </text>
                )}
              </g>
            );
          })}

          {/* Node circles + labels */}
          {layout.positions.map((pos) => {
            const isSelected = pos.node.id === selectedNodeId;
            const catLabel = CATEGORY_LABEL[pos.node.category] || pos.node.category;

            return (
              <g
                key={pos.node.id}
                className="cursor-pointer group"
                onClick={() => handleNodeClick(pos.node.id)}
              >
                {/* Hover/selection glow */}
                <circle
                  cx={pos.cx}
                  cy={pos.cy}
                  r={pos.radius + 5}
                  fill="none"
                  stroke={pos.color}
                  strokeWidth={1.5}
                  strokeOpacity={isSelected ? 0.6 : 0}
                  className={cn(
                    "transition-opacity duration-200",
                    !isSelected && "group-hover:stroke-opacity-40"
                  )}
                />

                {/* Connector line from circle to label area */}
                <line
                  x1={pos.cx + pos.radius + 2}
                  y1={pos.cy}
                  x2={NODE_START_X}
                  y2={pos.cy}
                  stroke={pos.color}
                  strokeWidth={1}
                  strokeOpacity={0.3}
                />

                {/* Main circle */}
                <circle
                  cx={pos.cx}
                  cy={pos.cy}
                  r={pos.radius}
                  fill={pos.color}
                  fillOpacity={pos.fillOpacity}
                  stroke={pos.color}
                  strokeWidth={pos.strokeWidth}
                  strokeDasharray={pos.strokeDash}
                  strokeOpacity={0.8}
                  className={cn(
                    'transition-all duration-200 group-hover:drop-shadow-lg',
                    isSelected && 'drop-shadow-lg filter brightness-110'
                  )}
                />

                {/* North Star overlay */}
                {pos.isNorthStar && (
                  <text
                    x={pos.cx}
                    y={pos.cy + 1}
                    textAnchor="middle"
                    dominantBaseline="central"
                    className="fill-current pointer-events-none"
                    style={{ fill: '#000', fontSize: 10, fontWeight: 900 }}
                  >
                    ★
                  </text>
                )}

                {/* Priority label inside circle (for P0/P1) */}
                {!pos.isNorthStar && pos.radius >= 11 && (
                  <text
                    x={pos.cx}
                    y={pos.cy + 1}
                    textAnchor="middle"
                    dominantBaseline="central"
                    className="pointer-events-none"
                    style={{ fill: 'rgba(0,0,0,0.6)', fontSize: 7, fontWeight: 800 }}
                  >
                    {pos.node.priority}
                  </text>
                )}

                {/* Node title text */}
                <text
                  x={NODE_START_X + 4}
                  y={pos.cy - 3}
                  className="pointer-events-none"
                  style={{
                    fill: pos.node.state === 'dismissed' ? 'rgba(255,255,255,0.3)' : 'rgba(255,255,255,0.85)',
                    fontSize: 11,
                    fontWeight: 500,
                    textDecoration: pos.node.state === 'dismissed' ? 'line-through' : 'none',
                  }}
                >
                  {pos.node.title.length > 38 ? pos.node.title.slice(0, 38) + '…' : pos.node.title}
                </text>

                {/* Meta line: category badge + source + tasks */}
                <text
                  x={NODE_START_X + 4}
                  y={pos.cy + 11}
                  className="pointer-events-none"
                  style={{ fill: 'rgba(255,255,255,0.35)', fontSize: 9 }}
                >
                  {catLabel}
                  {pos.node.source !== 'manual' && ` · ${pos.node.source === 'github' ? 'GitHub' : pos.node.source === 'ai_proposed' ? 'AI' : 'TODO'}`}
                  {pos.node.tasks.length > 0 && ` · ${pos.node.tasks.length} tasks`}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}
