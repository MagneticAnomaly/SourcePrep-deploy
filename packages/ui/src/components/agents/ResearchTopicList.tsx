/**
 * ResearchTopicList — Shows research run history and lets users trigger new runs.
 */
import { useState } from 'react';

export interface ResearchRun {
  run_id: string;
  timestamp: string;
  topic_count: number;
  plan_count: number;
}

export interface ResearchTopicListProps {
  runs: ResearchRun[];
  onRun: (maxTopics: number) => void;
  running?: boolean;
  className?: string;
}

export function ResearchTopicList({
  runs,
  onRun,
  running = false,
  className = '',
}: ResearchTopicListProps) {
  const [maxTopics, setMaxTopics] = useState(3);

  return (
    <div className={`rounded-lg border border-border p-4 space-y-4 ${className}`}>
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-sm">Research Pipeline</h3>
        <div className="flex items-center gap-2">
          <label className="text-xs text-muted-foreground">Topics:</label>
          <select
            value={maxTopics}
            onChange={e => setMaxTopics(Number(e.target.value))}
            className="text-xs px-2 py-1 rounded border border-border bg-background"
          >
            {[1, 2, 3, 5, 10].map(n => (
              <option key={n} value={n}>{n}</option>
            ))}
          </select>
          <button
            onClick={() => onRun(maxTopics)}
            disabled={running}
            className="px-3 py-1 text-xs rounded-md bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-40 transition-colors"
          >
            {running ? 'Running...' : 'Run Research'}
          </button>
        </div>
      </div>

      <p className="text-xs text-muted-foreground">
        Mines audit findings, researches solutions, and formulates implementation plans.
      </p>

      {runs.length === 0 ? (
        <p className="text-xs text-muted-foreground italic">
          No research runs yet. Click &quot;Run Research&quot; to analyze your codebase findings.
        </p>
      ) : (
        <div className="border border-border rounded overflow-hidden">
          <table className="w-full text-xs">
            <thead className="bg-muted/50">
              <tr>
                <th className="text-left px-3 py-1.5 font-medium">Run</th>
                <th className="text-left px-3 py-1.5 font-medium">Date</th>
                <th className="text-center px-3 py-1.5 font-medium">Topics</th>
                <th className="text-center px-3 py-1.5 font-medium">Plans</th>
              </tr>
            </thead>
            <tbody>
              {runs.slice().reverse().map(run => (
                <tr key={run.run_id} className="border-t border-border/50">
                  <td className="px-3 py-1.5 font-mono text-muted-foreground">{run.run_id}</td>
                  <td className="px-3 py-1.5">{run.timestamp.slice(0, 16).replace('T', ' ')}</td>
                  <td className="px-3 py-1.5 text-center">{run.topic_count}</td>
                  <td className="px-3 py-1.5 text-center">{run.plan_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
