import { useMemo } from 'react';
import { Card, Title, Flex, Text, Badge } from '@tremor/react';
import { cn } from '../../lib/utils';

// Data model shared with CLI
export interface ActivityDay {
  date: string;           // ISO date (YYYY-MM-DD)
  embeddings: number;     // Files embedded
  trace: number;          // Symbols traced
  builds: number;         // Build count
}

export interface ActivityHeatmapData {
  days: ActivityDay[];
  totals: {
    embeddings: number;
    trace: number;
    builds: number;
  };
}

export interface ActivityHeatmapProps {
  data: ActivityHeatmapData;
  weeks?: number;
  showLegend?: boolean;
  showLabels?: boolean;
  className?: string;
}

// Color mixing: cyan (embeddings) + yellow (trace) = green (mixed)
function getCellColor(embeddings: number, trace: number, maxEmbeddings: number, maxTrace: number): string {
  if (embeddings === 0 && trace === 0) {
    return 'bg-surface-raised';
  }

  const embeddingIntensity = maxEmbeddings > 0 ? embeddings / maxEmbeddings : 0;
  const traceIntensity = maxTrace > 0 ? trace / maxTrace : 0;

  // Pure embedding (cyan)
  if (trace === 0) {
    if (embeddingIntensity > 0.75) return 'bg-cyan-500';
    if (embeddingIntensity > 0.5) return 'bg-cyan-400';
    if (embeddingIntensity > 0.25) return 'bg-cyan-300';
    return 'bg-cyan-200';
  }

  // Pure trace (yellow/amber)
  if (embeddings === 0) {
    if (traceIntensity > 0.75) return 'bg-amber-500';
    if (traceIntensity > 0.5) return 'bg-amber-400';
    if (traceIntensity > 0.25) return 'bg-amber-300';
    return 'bg-amber-200';
  }

  // Mixed (green)
  const combinedIntensity = (embeddingIntensity + traceIntensity) / 2;
  if (combinedIntensity > 0.75) return 'bg-green-500';
  if (combinedIntensity > 0.5) return 'bg-green-400';
  if (combinedIntensity > 0.25) return 'bg-green-300';
  return 'bg-green-200';
}

const DAYS_OF_WEEK = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

export function ActivityHeatmap({
  data,
  weeks = 12,
  showLegend = true,
  showLabels = true,
  className,
}: ActivityHeatmapProps) {
  // Build a map of date -> activity
  const activityMap = useMemo(() => {
    const map = new Map<string, ActivityDay>();
    for (const day of data.days) {
      map.set(day.date, day);
    }
    return map;
  }, [data.days]);

  // Calculate max values for intensity scaling
  const { maxEmbeddings, maxTrace } = useMemo(() => {
    let maxE = 0;
    let maxT = 0;
    for (const day of data.days) {
      if (day.embeddings > maxE) maxE = day.embeddings;
      if (day.trace > maxT) maxT = day.trace;
    }
    return { maxEmbeddings: maxE || 1, maxTrace: maxT || 1 };
  }, [data.days]);

  // Generate grid of dates (weeks x 7 days)
  const grid = useMemo(() => {
    const today = new Date();
    const endDate = new Date(today);
    endDate.setHours(0, 0, 0, 0);
    
    // Find the start of the week containing (weeks ago)
    const startDate = new Date(endDate);
    startDate.setDate(startDate.getDate() - (weeks * 7) - startDate.getDay());
    
    const result: { date: Date; activity: ActivityDay | null }[][] = [];
    const current = new Date(startDate);
    
    let weekData: { date: Date; activity: ActivityDay | null }[] = [];
    
    while (current <= endDate) {
      const dateStr = current.toISOString().split('T')[0];
      weekData.push({
        date: new Date(current),
        activity: activityMap.get(dateStr) || null,
      });
      
      if (weekData.length === 7) {
        result.push(weekData);
        weekData = [];
      }
      
      current.setDate(current.getDate() + 1);
    }
    
    // Add partial week if any
    if (weekData.length > 0) {
      result.push(weekData);
    }
    
    return result;
  }, [weeks, activityMap]);

  // Calculate month labels
  const monthLabels = useMemo(() => {
    const labels: { month: string; weekIndex: number }[] = [];
    let lastMonth = -1;
    
    grid.forEach((week, weekIndex) => {
      const firstDayOfWeek = week[0]?.date;
      if (firstDayOfWeek) {
        const month = firstDayOfWeek.getMonth();
        if (month !== lastMonth) {
          labels.push({ month: MONTHS[month], weekIndex });
          lastMonth = month;
        }
      }
    });
    
    return labels;
  }, [grid]);

  return (
    <Card className={cn('border border-border bg-surface shadow-sm', className)}>
      <Flex justifyContent="between" alignItems="center" className="mb-4">
        <Title className="text-text">Index Activity</Title>
        <Flex className="gap-2">
          <Badge color="cyan" size="xs">{data.totals.embeddings.toLocaleString()} embeddings</Badge>
          <Badge color="amber" size="xs">{data.totals.trace.toLocaleString()} graph nodes</Badge>
        </Flex>
      </Flex>

      <div className="overflow-x-auto">
        {/* Month labels */}
        {showLabels && (
          <div className="flex mb-1 ml-8">
            {monthLabels.map(({ month, weekIndex }, i) => (
              <div
                key={i}
                className="text-xs text-text-muted"
                style={{ marginLeft: i === 0 ? weekIndex * 14 : (monthLabels[i].weekIndex - monthLabels[i - 1].weekIndex - 1) * 14 }}
              >
                {month}
              </div>
            ))}
          </div>
        )}

        <div className="flex">
          {/* Day labels */}
          {showLabels && (
            <div className="flex flex-col mr-2 text-xs text-text-muted">
              {DAYS_OF_WEEK.map((day, i) => (
                <div key={day} className="h-3 flex items-center" style={{ display: i % 2 === 1 ? 'flex' : 'none' }}>
                  {day}
                </div>
              ))}
            </div>
          )}

          {/* Grid */}
          <div className="flex gap-0.5">
            {grid.map((week, weekIndex) => (
              <div key={weekIndex} className="flex flex-col gap-0.5">
                {DAYS_OF_WEEK.map((_, dayIndex) => {
                  const dayData = week[dayIndex];
                  if (!dayData) {
                    return <div key={dayIndex} className="w-3 h-3" />;
                  }

                  const activity = dayData.activity;
                  const embeddings = activity?.embeddings || 0;
                  const trace = activity?.trace || 0;
                  const colorClass = getCellColor(embeddings, trace, maxEmbeddings, maxTrace);

                  return (
                    <div
                      key={dayIndex}
                      className={cn(
                        'w-3 h-3 rounded-sm transition-colors cursor-pointer',
                        'hover:ring-2 hover:ring-primary hover:ring-offset-1',
                        colorClass
                      )}
                      title={`${dayData.date.toLocaleDateString()}\nEmbeddings: ${embeddings}\nGraph: ${trace}`}
                    />
                  );
                })}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Legend */}
      {showLegend && (
        <Flex className="mt-4 gap-4" justifyContent="end">
          <Text className="text-xs text-text-muted">Less</Text>
          <div className="flex gap-0.5">
            <div className="w-3 h-3 rounded-sm bg-surface-raised" />
            <div className="w-3 h-3 rounded-sm bg-cyan-200" title="Embeddings (low)" />
            <div className="w-3 h-3 rounded-sm bg-cyan-400" title="Embeddings (high)" />
            <div className="w-3 h-3 rounded-sm bg-green-300" title="Mixed" />
            <div className="w-3 h-3 rounded-sm bg-amber-300" title="Graph (low)" />
            <div className="w-3 h-3 rounded-sm bg-amber-500" title="Graph (high)" />
          </div>
          <Text className="text-xs text-text-muted">More</Text>
        </Flex>
      )}
    </Card>
  );
}

// Generate sample data for Storybook
export function generateSampleActivityData(weeks: number = 12): ActivityHeatmapData {
  const days: ActivityDay[] = [];
  const today = new Date();
  let totalEmbeddings = 0;
  let totalTrace = 0;
  let totalBuilds = 0;

  for (let i = weeks * 7; i >= 0; i--) {
    const date = new Date(today);
    date.setDate(date.getDate() - i);
    const dateStr = date.toISOString().split('T')[0];

    // Skip weekends with lower probability
    const isWeekend = date.getDay() === 0 || date.getDay() === 6;
    const hasActivity = Math.random() > (isWeekend ? 0.7 : 0.3);

    if (hasActivity) {
      const embeddings = Math.floor(Math.random() * 50);
      const trace = Math.random() > 0.5 ? Math.floor(Math.random() * 30) : 0;
      const builds = Math.random() > 0.7 ? Math.floor(Math.random() * 3) + 1 : 0;

      days.push({ date: dateStr, embeddings, trace, builds });
      totalEmbeddings += embeddings;
      totalTrace += trace;
      totalBuilds += builds;
    }
  }

  return {
    days,
    totals: {
      embeddings: totalEmbeddings,
      trace: totalTrace,
      builds: totalBuilds,
    },
  };
}
