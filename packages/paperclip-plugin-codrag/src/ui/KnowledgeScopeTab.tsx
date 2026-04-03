/**
 * Knowledge Scope Detail Tab
 *
 * Shows the CoDRAG Knowledge Scope file list for a specific Paperclip agent.
 * Registered as a detail tab on agent entities.
 */

declare function usePluginData(key: string, params?: any): { data: any; loading: boolean; error: any };
declare function useHostContext(): { companyId?: string; projectId?: string; entityId?: string };

export function KnowledgeScopeTab() {
  const { entityId } = useHostContext();
  const { data, loading, error } = usePluginData('agent-knowledge-scope', { entityId });

  if (loading) return <div style={{ padding: 16, color: '#888' }}>Loading knowledge scope...</div>;
  if (error) return <div style={{ padding: 16, color: '#e55' }}>Error: {error.message}</div>;

  const files = data?.files ?? [];

  if (files.length === 0) {
    return (
      <div style={{ padding: 24, textAlign: 'center' }}>
        <div style={{ fontSize: 32, marginBottom: 8 }}>&#128269;</div>
        <div style={{ fontWeight: 600, marginBottom: 4 }}>No Knowledge Scope</div>
        <div style={{ fontSize: 13, color: '#888' }}>
          {data?.error ?? 'Run auto-populate in CoDRAG to assign files to this agent.'}
        </div>
      </div>
    );
  }

  return (
    <div style={{ padding: 16 }}>
      <div style={{ fontSize: 13, color: '#888', marginBottom: 8 }}>
        {files.length} files in scope
      </div>
      <div style={{ maxHeight: 400, overflow: 'auto' }}>
        {files.map((f: any, i: number) => (
          <div
            key={i}
            style={{
              padding: '4px 8px',
              fontFamily: 'monospace',
              fontSize: 12,
              borderBottom: '1px solid rgba(255,255,255,0.05)',
            }}
          >
            {f.path ?? f}
          </div>
        ))}
      </div>
    </div>
  );
}
