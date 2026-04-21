/**
 * Codebase Health Widget — Paperclip dashboard widget.
 * Shows: pipeline status, push summary, consensus hotspots, structural delta.
 */

interface ConsensusEntry {
  file_path: string;
  agents: string[];
  consensus_score: number;
}

interface HubChange {
  path: string;
  change: string;
  dependents_count?: number;
  rank?: number;
}

interface HealthData {
  status: {
    hr: { role_count: number };
    researcher: { run_count: number };
    custodian: { archive_count: number };
  } | null;
  readiness: { score: number } | null;
  push_summary: { total_pushes: number; latest_push_at: number | null } | null;
  consensus: ConsensusEntry[];
  delta: { hub_changes: HubChange[]; module_changes: any[]; is_empty: boolean } | null;
  error?: string;
}

// Note: usePluginData may not be importable yet since Paperclip SDK might not be installed.
// Write the component as if the import works. If the SDK isn't available, we mock it.
// For now, accept the data as a prop instead:

export interface CodebaseHealthWidgetProps {
  data: HealthData | null;
  loading?: boolean;
}

export function CodebaseHealthWidget({ data, loading = false }: CodebaseHealthWidgetProps) {
  if (loading) {
    return <div className="p-4 text-sm text-gray-500">Loading Prep status...</div>;
  }

  if (data?.error) {
    return (
      <div className="p-4">
        <div className="text-sm text-red-400">Prep daemon unavailable</div>
        <div className="text-xs text-gray-500 mt-1">{data.error}</div>
      </div>
    );
  }

  const pushSummary = data?.push_summary;
  const consensus = data?.consensus ?? [];
  const delta = data?.delta;

  return (
    <div className="p-4 space-y-3">
      <div className="text-sm font-medium">Prep Codebase Health</div>

      <div className="text-xs text-gray-400">
        <span className="inline-block w-2 h-2 rounded-full bg-green-400 mr-1.5" />
        Pipeline healthy
        {data?.readiness && (
          <span className="ml-2">· Readiness: {(data.readiness.score * 100).toFixed(0)}%</span>
        )}
      </div>

      {pushSummary && pushSummary.total_pushes > 0 && (
        <div className="text-xs">
          <div className="font-medium text-gray-300 mb-0.5">Recent Pushes</div>
          <div className="text-gray-400">
            {pushSummary.total_pushes} issues pushed
            {pushSummary.latest_push_at && (
              <span className="ml-1">
                · Last: {new Date(pushSummary.latest_push_at * 1000).toLocaleTimeString()}
              </span>
            )}
          </div>
        </div>
      )}

      {consensus.length > 0 && (
        <div className="text-xs">
          <div className="font-medium text-gray-300 mb-0.5">Consensus Hotspots</div>
          {consensus.slice(0, 3).map((entry) => (
            <div key={entry.file_path} className="flex items-center justify-between py-0.5">
              <span className="text-gray-400 truncate mr-2">{entry.file_path}</span>
              <span className="text-amber-400 shrink-0">
                {entry.agents.length} agents · {entry.consensus_score.toFixed(2)}
              </span>
            </div>
          ))}
        </div>
      )}

      {delta && !delta.is_empty && (
        <div className="text-xs">
          <div className="font-medium text-gray-300 mb-0.5">Structural Delta</div>
          {delta.hub_changes
            .filter((h: HubChange) => h.change === 'new' || h.change === 'removed')
            .slice(0, 3)
            .map((h: HubChange) => (
              <div key={h.path} className="text-gray-400 py-0.5">
                {h.change === 'new' ? '+ New hub: ' : '- Removed hub: '}
                <span className="text-gray-300">{h.path}</span>
                {h.dependents_count != null && (
                  <span className="ml-1">({h.dependents_count} deps)</span>
                )}
              </div>
            ))}
        </div>
      )}
    </div>
  );
}
