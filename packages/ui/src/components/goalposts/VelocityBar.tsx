import { useMemo } from 'react';
import type { VelocityResponse } from '../../types';

export interface VelocityBarProps {
  velocityData: VelocityResponse | null;
}

export function VelocityBar({ velocityData }: VelocityBarProps) {
  const chartHeight = 80;
  const paddingY = 20;
  const paddingX = 10;

  const points = useMemo(() => {
    if (!velocityData || velocityData.snapshots.length === 0) return [];
    
    // Sort chronologically just in case (oldest to newest)
    const sorted = [...velocityData.snapshots].sort(
      (a, b) => new Date(a.window_start).getTime() - new Date(b.window_start).getTime()
    );

    // Limit to last 8 sprints to not clutter
    const recent = sorted.slice(-8);

    const maxCount = Math.max(...recent.map(s => s.completed_count || 0), 1);
    
    return recent.map((snapshot, i) => {
      const count = snapshot.completed_count || 0;
      // Calculate normalized height (0 to 1) relative to max value
      const normalizedH = count / maxCount;
      return {
        index: i,
        // Calculate X positioning: distribute evenly
        x: paddingX + (i * ((380 - (paddingX * 2)) / Math.max(recent.length - 1, 1))),
        // Calculate Y positioning: invert because SVG y increases downwards
        y: chartHeight - paddingY - (normalizedH * (chartHeight - paddingY * 2)),
        count,
        label: new Date(snapshot.window_start).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
      };
    });
  }, [velocityData]);

  const pathD = useMemo(() => {
    if (points.length === 0) return '';
    if (points.length === 1) return `M ${points[0].x} ${points[0].y} L ${points[0].x} ${points[0].y}`;
    
    // Create a smooth curve (catmull-rom or simplified bezier)
    // For simplicity, using straight lines with soft curves could also work, or just straight lines.
    const start = `M ${points[0].x} ${points[0].y}`;
    const lines = points.slice(1).map(p => {
      return `L ${p.x} ${p.y}`;
    }).join(' ');
    return `${start} ${lines}`;
  }, [points]);

  const fillPathD = useMemo(() => {
    if (!pathD) return '';
    const lastX = points[points.length - 1].x;
    return `${pathD} L ${lastX} ${chartHeight} L ${points[0].x} ${chartHeight} Z`;
  }, [pathD, points, chartHeight]);

  if (!velocityData) {
    return (
      <div className="flex items-center justify-center p-4 border border-border/50 bg-surface/30 rounded-lg text-text-muted text-xs h-[120px]">
        No velocity data tracked yet
      </div>
    );
  }

  const { average_velocity } = velocityData;

  return (
    <div className="flex flex-col border border-border/50 bg-surface-raised/40 rounded-lg overflow-hidden shrink-0">
      <div className="flex items-center justify-between px-3 py-2 border-b border-border/30 bg-surface-raised/60">
        <span className="text-[10px] font-semibold text-text-muted uppercase tracking-wider">Sprint Velocity</span>
        <div className="flex items-center gap-1.5 font-mono text-xs">
          <span className="text-emerald-400 font-bold">{average_velocity.toFixed(1)}</span>
          <span className="text-text-muted">avg / sprint</span>
        </div>
      </div>
      
      <div className="relative h-[80px] w-full">
        {points.length > 0 ? (
          <svg width="100%" height={chartHeight} viewBox={`0 0 380 ${chartHeight}`} preserveAspectRatio="none">
            {/* Gradient definition */}
            <defs>
              <linearGradient id="velocityFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#34d399" stopOpacity="0.3" />
                <stop offset="100%" stopColor="#34d399" stopOpacity="0.0" />
              </linearGradient>
            </defs>

            {/* Average Line */}
            {average_velocity > 0 && points.length > 0 && (
              <g>
                <line 
                  x1={points[0].x} 
                  y1={chartHeight - paddingY - ((average_velocity / Math.max(...points.map(p => p.count), 1)) * (chartHeight - paddingY * 2))}
                  x2={points[points.length - 1].x} 
                  y2={chartHeight - paddingY - ((average_velocity / Math.max(...points.map(p => p.count), 1)) * (chartHeight - paddingY * 2))}
                  stroke="#94a3b8" 
                  strokeDasharray="4 4"
                  strokeWidth={1}
                  strokeOpacity={0.4}
                />
              </g>
            )}

            {/* Area fill */}
            <path 
              d={fillPathD} 
              fill="url(#velocityFill)" 
            />

            {/* Line */}
            <path 
              d={pathD} 
              fill="none" 
              stroke="#34d399" 
              strokeWidth={2} 
            />

            {/* Points */}
            {points.map((p, i) => (
              <g key={i}>
                <circle 
                  cx={p.x} 
                  cy={p.y} 
                  r={3.5} 
                  fill="#16161e" 
                  stroke="#34d399" 
                  strokeWidth={1.5} 
                />
                {/* Show label for first, last, or if there's enough space */}
                {(i === 0 || i === points.length - 1 || points.length <= 5) && (
                  <text 
                    x={p.x} 
                    y={chartHeight - 4} 
                    textAnchor={i === 0 ? 'start' : i === points.length - 1 ? 'end' : 'middle'} 
                    className="text-[9px] fill-text-muted font-medium"
                  >
                    {p.count}
                  </text>
                )}
              </g>
            ))}
          </svg>
        ) : (
          <div className="absolute inset-0 flex items-center justify-center text-xs text-text-muted">
            Insufficient tracking history
          </div>
        )}
      </div>
    </div>
  );
}
