/**
 * Codebase Health Dashboard Widget
 *
 * Shows module count, readiness score, and hub file count.
 * Registered as a Paperclip dashboard widget via the plugin manifest.
 */

// Plugin SDK bridge hooks (will be provided by @paperclipai/plugin-sdk/ui)
declare function usePluginData(key: string, params?: any): { data: any; loading: boolean; error: any };
declare function usePluginAction(key: string): (params?: any) => Promise<any>;

export function CodebaseHealthWidget() {
  const { data, loading, error } = usePluginData('codebase-health');

  if (loading) {
    return <div style={{ padding: 16, color: '#888' }}>Loading codebase health...</div>;
  }

  if (error) {
    return (
      <div style={{ padding: 16, color: '#e55' }}>
        CoDRAG daemon unavailable. Is it running?
      </div>
    );
  }

  const readiness = data?.readiness;
  const status = data?.status;
  const score = readiness?.score ?? 0;
  const scoreColor = score >= 0.7 ? '#4a4' : score >= 0.4 ? '#ca4' : '#c44';

  return (
    <div style={{ padding: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
        <div>
          <div style={{ fontSize: 28, fontWeight: 700, color: scoreColor }}>
            {(score * 100).toFixed(0)}%
          </div>
          <div style={{ fontSize: 12, color: '#888' }}>Readiness</div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: 28, fontWeight: 700 }}>
            {status?.hr?.role_count ?? 0}
          </div>
          <div style={{ fontSize: 12, color: '#888' }}>Roles</div>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 16, fontSize: 13 }}>
        <div>
          <span style={{ color: '#888' }}>Research runs: </span>
          <strong>{status?.researcher?.run_count ?? 0}</strong>
        </div>
        <div>
          <span style={{ color: '#888' }}>Archived: </span>
          <strong>{status?.custodian?.archive_count ?? 0}</strong>
        </div>
      </div>

      {readiness?.missing?.length > 0 && (
        <div style={{ marginTop: 12, fontSize: 12, color: '#ca4' }}>
          {readiness.missing[0]}
        </div>
      )}
    </div>
  );
}
