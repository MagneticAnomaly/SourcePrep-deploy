/**
 * Issue Context Detail Tab
 *
 * Shows CoDRAG structural context for a specific Paperclip issue.
 * If the issue has a CoDRAG address, displays impact analysis and related files.
 */

declare function usePluginData(key: string, params?: any): { data: any; loading: boolean; error: any };
declare function useHostContext(): { companyId?: string; projectId?: string; entityId?: string };

export function IssueContextTab() {
  const { entityId } = useHostContext();
  const { data, loading, error } = usePluginData('issue-context', { entityId });

  if (loading) return <div style={{ padding: 16, color: '#888' }}>Loading codebase context...</div>;
  if (error) return <div style={{ padding: 16, color: '#e55' }}>Error: {error.message}</div>;

  if (!data?.available) {
    return (
      <div style={{ padding: 24, textAlign: 'center' }}>
        <div style={{ fontSize: 32, marginBottom: 8 }}>&#128200;</div>
        <div style={{ fontWeight: 600, marginBottom: 4 }}>No CoDRAG Context</div>
        <div style={{ fontSize: 13, color: '#888' }}>
          This issue was not created from CoDRAG audit findings.
          Use <code>codrag:search</code> or <code>codrag:impact</code> to add context.
        </div>
      </div>
    );
  }

  return (
    <div style={{ padding: 16 }}>
      <div style={{ fontSize: 13, color: '#888', marginBottom: 8 }}>
        CoDRAG project: <code>{data.project_id}</code>
      </div>
      <div style={{ fontSize: 13 }}>
        Codebase context is available. Agents working on this issue can call{' '}
        <code>codrag:search</code> and <code>codrag:impact</code> for live structural analysis.
      </div>
    </div>
  );
}
