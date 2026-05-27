import { Image as ImageIcon } from 'lucide-react';
import { AnchorHeading } from '../../../components/AnchorHeading';

export default function Page() {
  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto max-w-3xl px-6 pb-16 pt-0">
        <a href="/dashboard" className="text-sm text-text-muted hover:text-primary transition-colors">
          ← Dashboard
        </a>

        <h1 className="mt-6 text-3xl font-bold tracking-tight">Managing Projects</h1>
        <p className="mt-4 text-xl text-text-muted">
          A project connects a local codebase directory to an indexed code graph
          and embedding store. Most users have one — teams running SourcePrep
          across multiple repos can register many.
        </p>

        <div className="mt-12 prose  max-w-none">

          <AnchorHeading id="adding-projects" level="h2">Adding a project</AnchorHeading>
          <p>
            Add projects via the CLI (<code>prep add .</code>) or directly in the dashboard.
            From the dashboard:
          </p>
          <ol className="list-decimal pl-5 text-sm text-text-muted">
            <li>Open the SourcePrep desktop app.</li>
            <li>Click the <span className="font-semibold text-text">+</span> button in the project list.</li>
            <li>Pick the repository folder.</li>
            <li>Optionally name it.</li>
          </ol>

          <AnchorHeading id="indexing-status" level="h2">Watching it index</AnchorHeading>
          <p>
            Once added, the engine starts building the index. Progress is visible
            in two panels:
          </p>
          <ul className="list-disc pl-5 text-sm text-text-muted">
            <li><span className="font-semibold text-text">Code-Graph Coverage:</span> file inventory and traced/untraced counts.</li>
            <li><span className="font-semibold text-text">Pipeline:</span> live status of each of the 15 enrichment stages. See <a href="/how-it-works/graph-enrichment" className="text-primary hover:underline">Graph Enrichment</a> for what each stage does.</li>
          </ul>

          <AnchorHeading id="file-management" level="h2" className="mt-8">Controlling what gets indexed</AnchorHeading>
          <p>
            SourcePrep respects <code>.gitignore</code> automatically. To exclude
            additional files (large assets, generated code) without git-ignoring
            them, use the <span className="font-semibold text-text">Excluded</span>
            tab in the Code-Graph Coverage panel — add patterns there and the
            engine will skip them on the next pass.
          </p>

          <h3 className="text-base font-semibold mt-4">Pinning files</h3>
          <p className="text-sm">
            Important documentation or context files can be pinned in the
            Coverage panel. Pinned files are prioritized during context assembly,
            so they're more likely to land in your AI's context window when
            relevant.
          </p>

          <AnchorHeading id="project-settings" level="h2" className="mt-8">Project settings</AnchorHeading>
          <p>
            Open the Settings panel and switch to the <span className="font-semibold text-text">Source</span> sub-page
            for project-scoped configuration.
          </p>
          <ul className="list-disc pl-5 text-sm text-text-muted space-y-2">
            <li><span className="font-semibold text-text">Include / Exclude globs:</span> exact patterns for what gets indexed. Use <span className="font-semibold text-text">Auto-Detect Stack</span> to seed sensible patterns based on your repo's frameworks.</li>
            <li><span className="font-semibold text-text">File size limits:</span> the default cap (set per project) keeps massive generated files out of the embedding store. Raise it if you need to index large data files.</li>
            <li><span className="font-semibold text-text">Auto-Rebuild:</span> per-project toggle for the background watcher. On by default; turn off if you'd rather rebuild manually.</li>
          </ul>

          <div className="my-6 p-8 border-2 border-dashed border-border rounded-lg bg-surface flex flex-col items-center justify-center text-text-muted gap-2">
            <div className="w-12 h-12 rounded-full bg-surface border border-border flex items-center justify-center">
              <ImageIcon className="w-6 h-6" />
            </div>
            <p className="font-medium text-text">Screenshot: Source settings sub-page</p>
            <p className="text-sm text-center">Auto-Detect Stack button + glob editor.</p>
          </div>

        </div>
      </div>
    </main>
  );
}
