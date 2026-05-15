import { AnchorHeading } from '../../../components/AnchorHeading';

export default function Page() {
  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto max-w-3xl px-6 pb-16 pt-0">
        <a href="/cli" className="text-sm text-text-muted">
          ← CLI Reference
        </a>

        <h1 className="mt-6 text-3xl font-bold tracking-tight">Configuration</h1>
        <p className="mt-4 text-lg text-text-muted">
          Global and project-level configuration options.
        </p>

        <div className="mt-12 prose  max-w-none">
          
          <AnchorHeading id="global-config" level="h2">Daemon-wide State</AnchorHeading>
          <p>
            Default location: <code>~/.local/share/sourceprep/</code> on Mac and Linux. Override with the{' '}
            <code>PREP_DATA_DIR</code> environment variable (must be an absolute path).
          </p>
          <p className="text-sm text-text-muted">
            This directory holds the daemon&apos;s SQLite stores, registry, audit log, and standalone-mode
            project indexes. You typically edit settings via the Dashboard — manual edits are rarely
            needed.
          </p>
          <p className="text-sm text-text-muted">
            Pre-Phase-113 installs had state split between <code>./prep_data/</code> (CWD-relative)
            and the XDG location. Old layouts are auto-migrated on first daemon startup; the
            sentinel file <code>.migrated_from_cwd</code> records the migration.
          </p>

          <AnchorHeading id="project-config" level="h2">Project Config</AnchorHeading>
          <p>
            Stored in the internal SQLite database (managed via CLI/Dashboard). You can also place a <code>.sourceprep/config.json</code> in your project root to override settings for that specific repo.
          </p>

          <h3 className="text-base font-semibold mt-4">.sourceprep/ignore</h3>
          <p>
            Works exactly like <code>.gitignore</code>. Use this to exclude files from indexing that you might want to keep in git (or local-only files not in gitignore).
          </p>
          <pre className="overflow-x-auto text-sm">
            <code># Example .sourceprep/ignore
*.lock
docs/generated/
legacy/</code>
          </pre>

          <AnchorHeading id="env-vars" level="h2" className="mt-8">Environment Variables</AnchorHeading>
          <p>
            You can override certain behaviors using environment variables.
          </p>
          
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left">
                  <th className="py-2 pr-4 font-medium text-text">Variable</th>
                  <th className="py-2 pr-4 font-medium text-text">Values</th>
                  <th className="py-2 font-medium text-text">Description</th>
                </tr>
              </thead>
              <tbody className="text-text-muted">
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono">PREP_DATA_DIR</td>
                  <td className="py-2 pr-4">absolute path</td>
                  <td className="py-2">
                    Override the default daemon-state location. Defaults to{' '}
                    <code>~/.local/share/sourceprep/</code>.
                  </td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono">PREP_ENGINE</td>
                  <td className="py-2 pr-4"><code>auto</code> | <code>rust</code> | <code>python</code></td>
                  <td className="py-2">
                    Force the use of the Rust engine or Python fallback. Default: <code>auto</code>.
                  </td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono">PREP_TIER</td>
                  <td className="py-2 pr-4"><code>free</code> | <code>pro</code> | <code>team</code> | <code>enterprise</code></td>
                  <td className="py-2">
                    Override the license tier for testing/development. Requires <code>PREP_DEV_MODE=1</code> to take effect.
                  </td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono">PREP_DEV_MODE</td>
                  <td className="py-2 pr-4"><code>1</code></td>
                  <td className="py-2">
                    Enable development mode — required for <code>PREP_TIER</code> to override the license tier.
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

        </div>
      </div>
    </main>
  );
}
