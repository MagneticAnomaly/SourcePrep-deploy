/**
 * RunPrep Settings Page
 *
 * Plugin configuration: daemon URL, project mapping, index status.
 */

declare function usePluginData(key: string, params?: any): { data: any; loading: boolean; error: any };
declare function usePluginAction(key: string): (params?: any) => Promise<any>;

export function SettingsPage() {
  const { data, loading } = usePluginData('codebase-health');

  return (
    <div style={{ padding: 24, maxWidth: 600 }}>
      <h2 style={{ fontSize: 18, fontWeight: 700, marginBottom: 16 }}>
        RunPrep Configuration
      </h2>

      <div style={{ marginBottom: 24 }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 8 }}>Connection Status</h3>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span
            style={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              backgroundColor: loading ? '#ca4' : data ? '#4a4' : '#c44',
            }}
          />
          <span style={{ fontSize: 13 }}>
            {loading ? 'Connecting...' : data ? 'Connected' : 'Disconnected'}
          </span>
        </div>
      </div>

      <div style={{ marginBottom: 24 }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 8 }}>Available Tools</h3>
        <div style={{ fontSize: 13, color: '#888' }}>
          All Paperclip agents can use these RunPrep tools during their runs:
        </div>
        <ul style={{ fontSize: 13, marginTop: 8, paddingLeft: 20 }}>
          <li><code>prep:context</code> — Structural overview</li>
          <li><code>prep:search</code> — Semantic code search</li>
          <li><code>prep:impact</code> — Dependency analysis</li>
          <li><code>prep:audit</code> — Health findings</li>
          <li><code>prep:observe</code> — Cross-session memory</li>
        </ul>
      </div>

      <div style={{ fontSize: 12, color: '#666', marginTop: 32 }}>
        RunPrep v0.1.0 — <a href="https://runprep.io" target="_blank" rel="noopener">runprep.io</a>
      </div>
    </div>
  );
}
