import { AnchorHeading } from '../../../components/AnchorHeading';

export default function Page() {
  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto max-w-3xl px-6 pb-16 pt-0">
        <a href="/getting-started" className="text-sm text-text-muted">
          ← Getting Started
        </a>

        <h1 className="mt-6 text-3xl font-bold tracking-tight">Installation</h1>
        <p className="mt-4 text-lg text-text-muted">
          Download and install the SourcePrep desktop app on your local machine.
        </p>

        <div className="mt-12 prose  max-w-none">
          
          <AnchorHeading id="prerequisites" level="h2">Prerequisites</AnchorHeading>
          <ul className="list-disc pl-5 text-sm text-text-muted">
            <li><span className="font-semibold text-text">OS:</span> macOS (11+) or Windows (10+). Linux support is planned.</li>
            <li><span className="font-semibold text-text">Disk:</span> ~500 MB for the app + embedding model. Index size depends on your codebase.</li>
          </ul>

          <AnchorHeading id="download" level="h2" className="mt-8">Download</AnchorHeading>
          <p>
            SourcePrep is a native desktop application. Choose your platform:
          </p>

          <div className="not-prose grid sm:grid-cols-2 gap-4 my-6">
            <a
              href="https://sourceprep.io/download"
              className="flex flex-col p-5 rounded-lg border border-border bg-surface hover:border-primary transition-colors"
            >
              <div className="text-lg font-bold">macOS</div>
              <div className="text-sm text-text-muted mt-1">Download .dmg (Apple Silicon & Intel)</div>
            </a>
            <a
              href="https://sourceprep.io/download"
              className="flex flex-col p-5 rounded-lg border border-border bg-surface hover:border-primary transition-colors"
            >
              <div className="text-lg font-bold">Windows</div>
              <div className="text-sm text-text-muted mt-1">Download .msi installer (x64)</div>
              <div className="text-xs text-text-muted mt-2">Microsoft Store distribution is planned post-MVP.</div>
            </a>
          </div>
          <p className="text-sm text-text-muted">
            <span className="font-semibold text-text">Linux:</span> support is planned post-MVP. SourcePrep is not currently distributed through the Mac App Store and won&apos;t be — the indexer requires full filesystem access, which sandboxed Mac App Store apps can&apos;t provide.
          </p>

          <AnchorHeading id="install-macos" level="h3" className="mt-6">macOS</AnchorHeading>
          <ol className="list-decimal pl-5 text-sm text-text-muted space-y-2">
            <li>Open the downloaded <code>.dmg</code> file.</li>
            <li>Drag <span className="font-semibold text-text">SourcePrep</span> into your Applications folder.</li>
            <li>Launch SourcePrep from Applications (or Spotlight: <code>Cmd+Space</code> → &quot;SourcePrep&quot;).</li>
          </ol>
          <p className="text-sm text-text-muted mt-2">
            <em>On first launch, macOS may ask you to confirm the app is from an identified developer. Click &quot;Open&quot; to proceed.</em>
          </p>

          <AnchorHeading id="install-windows" level="h3" className="mt-6">Windows</AnchorHeading>
          <ol className="list-decimal pl-5 text-sm text-text-muted space-y-2">
            <li>Run the downloaded <code>.msi</code> installer.</li>
            <li>Follow the installation wizard (default settings are fine).</li>
            <li>Launch SourcePrep from the Start Menu or Desktop shortcut.</li>
          </ol>

          <AnchorHeading id="verify" level="h2" className="mt-8">Verify Installation</AnchorHeading>
          <p>
            When you launch SourcePrep, it automatically starts the background daemon. You should see the dashboard
            appear with a green &quot;Connected&quot; status.
          </p>
          <p className="text-sm text-text-muted mt-2">
            The app also installs a <code>prep</code> CLI command. You can verify it in your terminal:
          </p>
          <pre className="overflow-x-auto text-sm">
            <code>prep --version</code>
          </pre>

          <AnchorHeading id="licensing" level="h2" className="mt-8">Licensing</AnchorHeading>
          <p>
            SourcePrep is <span className="font-semibold text-text">free to use</span> with up to 3 active projects and all features included. To unlock unlimited projects, purchase a license at{' '}
            <a href="https://sourceprep.io/pricing" className="text-primary hover:underline">sourceprep.io/pricing</a>.
          </p>
          <p className="text-sm text-text-muted mt-2">
            Payments are processed by <span className="font-semibold text-text">Lemon Squeezy</span> (our Merchant of Record). After purchase,
            enter your license key in the app to activate. Activation requires a one-time internet connection;
            after that, SourcePrep works fully offline.
          </p>

          <AnchorHeading id="upgrading" level="h2" className="mt-8">Upgrading</AnchorHeading>
          <p>
            SourcePrep checks for updates automatically and notifies you when a new version is available.
            You can also download the latest version from{' '}
            <a href="https://sourceprep.io/download" className="text-primary hover:underline">sourceprep.io/download</a>.
          </p>

          <div className="mt-8 rounded-lg border border-blue-500/20 bg-blue-500/5 p-4">
            <h3 className="text-base font-semibold text-blue-500 mb-2">Next Steps</h3>
            <p className="text-sm text-text-muted">
              Once installed, head over to the <a href="/getting-started/quick-start" className="text-primary hover:underline">Quick Start</a> guide to index your first project.
            </p>
          </div>
        </div>
      </div>
    </main>
  );
}
