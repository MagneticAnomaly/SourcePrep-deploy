/**
 * BurndownChart — Sprint burndown visualization (Phase 59D-4).
 *
 * Renders a SVG area chart showing remaining vs completed items over time.
 * Data comes from the VelocityResponse.burndown field.
 */
import { useMemo } from 'react';
import { TrendingDown, BarChart3 } from 'lucide-react';
import type { BurndownPoint } from '../../types';

export interface BurndownChartProps {
  data: BurndownPoint[];
  className?: string;
}

export function BurndownChart({ data, className }: BurndownChartProps) {
  const chartData = useMemo(() => {
    if (!data || data.length < 2) return null;

    const maxRemaining = Math.max(...data.map(d => d.remaining), 1);
    const maxCompleted = Math.max(...data.map(d => d.completed), 1);
    const maxY = Math.max(maxRemaining, maxCompleted);

    const width = 100;
    const height = 60;
    const padding = { top: 4, right: 4, bottom: 16, left: 4 };
    const plotW = width - padding.left - padding.right;
    const plotH = height - padding.top - padding.bottom;

    const xStep = plotW / Math.max(data.length - 1, 1);

    const remainingPath = data.map((d, i) => {
      const x = padding.left + i * xStep;
      const y = padding.top + plotH - (d.remaining / maxY) * plotH;
      return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(' ');

    const remainingArea = remainingPath +
      ` L${(padding.left + (data.length - 1) * xStep).toFixed(1)},${(padding.top + plotH).toFixed(1)}` +
      ` L${padding.left},${(padding.top + plotH).toFixed(1)} Z`;

    const completedPath = data.map((d, i) => {
      const x = padding.left + i * xStep;
      const y = padding.top + plotH - (d.completed / maxY) * plotH;
      return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(' ');

    // Date labels (first and last)
    const firstDate = data[0].date.slice(5); // MM-DD
    const lastDate = data[data.length - 1].date.slice(5);

    return {
      remainingPath,
      remainingArea,
      completedPath,
      firstDate,
      lastDate,
      width,
      height,
      padding,
      latest: data[data.length - 1],
    };
  }, [data]);

  if (!chartData) {
    return (
      <div className={`flex items-center gap-2 text-xs text-muted-foreground ${className || ''}`}>
        <BarChart3 className="w-3.5 h-3.5" />
        <span>Insufficient data for burndown chart</span>
      </div>
    );
  }

  return (
    <div className={`${className || ''}`}>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-1.5">
          <TrendingDown className="w-3.5 h-3.5 text-emerald-400" />
          <span className="text-xs font-medium text-foreground/80">Sprint Burndown</span>
        </div>
        <div className="flex items-center gap-3 text-[10px] text-muted-foreground">
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-amber-400/60" />
            Remaining: {chartData.latest.remaining}
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-emerald-400/60" />
            Done: {chartData.latest.completed}
          </span>
        </div>
      </div>

      <svg
        viewBox={`0 0 ${chartData.width} ${chartData.height}`}
        className="w-full h-auto"
        style={{ maxHeight: '120px' }}
      >
        {/* Remaining area (amber) */}
        <path
          d={chartData.remainingArea}
          fill="rgba(245, 158, 11, 0.15)"
          stroke="none"
        />
        <path
          d={chartData.remainingPath}
          fill="none"
          stroke="rgba(245, 158, 11, 0.6)"
          strokeWidth="1"
          strokeLinecap="round"
        />

        {/* Completed line (emerald) */}
        <path
          d={chartData.completedPath}
          fill="none"
          stroke="rgba(52, 211, 153, 0.7)"
          strokeWidth="1"
          strokeDasharray="3,2"
          strokeLinecap="round"
        />

        {/* X-axis date labels */}
        <text
          x={chartData.padding.left}
          y={chartData.height - 2}
          fontSize="5"
          fill="currentColor"
          opacity="0.4"
        >
          {chartData.firstDate}
        </text>
        <text
          x={chartData.width - chartData.padding.right}
          y={chartData.height - 2}
          fontSize="5"
          fill="currentColor"
          opacity="0.4"
          textAnchor="end"
        >
          {chartData.lastDate}
        </text>
      </svg>
    </div>
  );
}
