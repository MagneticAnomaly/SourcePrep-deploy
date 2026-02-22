import { Image as ImageIcon } from 'lucide-react';
import { AnchorHeading } from '../../../components/AnchorHeading';

export default function Page() {
  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto max-w-3xl px-6 pb-16 pt-0">
        <a href="/dashboard" className="text-sm text-text-muted">
          ← Dashboard
        </a>

        <h1 className="mt-6 text-3xl font-bold tracking-tight">Managing Projects</h1>
        <p className="mt-4 text-lg text-text-muted">
          Add, configure, and monitor your local repositories.
        </p>

        <div className="mt-12 prose  max-w-none">
          
          <AnchorHeading id="adding-projects" level="h2">Adding Projects</AnchorHeading>
          <p>
            You can add projects via the CLI (<code>codrag add .</code>) or directly in the Dashboard.
          </p>
          <ol className="list-decimal pl-5 text-sm text-text-muted">
            <li>Open the CoDRAG desktop app.</li>
            <li>Click the <strong>&quot;+&quot;</strong> button in the sidebar project list.</li>
            <li>Select your repository folder using the file picker.</li>
            <li>Give it a friendly name (optional).</li>
          </ol>
          <div className="my-6 p-8 border-2 border-dashed border-border rounded-lg bg-surface flex flex-col items-center justify-center text-text-muted gap-2">
            <div className="w-12 h-12 rounded-full bg-surface border border-border flex items-center justify-center">
              <ImageIcon className="w-6 h-6" />
            </div>
            <p className="font-medium">Screenshot: Add Project Modal</p>
            <p className="text-sm text-center">Show the &apos;Add Project&apos; modal with path and name fields.</p>
          </div>

          <AnchorHeading id="indexing-status" level="h2" className="mt-8">Indexing Status</AnchorHeading>
          <p>
            Once added, CoDRAG begins the 7-stage knowledge process managed by the <strong>Knowledge Pipeline</strong> (Panel B):
          </p>
          <ul className="list-disc pl-5 text-sm text-text-muted">
            <li><strong>Structural Trace:</strong> (Rust) Fast parsing of your codebase structure.</li>
            <li><strong>Vector Indexing:</strong> (Embeddings) Creating searchable chunks for the knowledge base.</li>
            <li><strong>Enrichment:</strong> (LLM) Deeper analysis and synthesis (if enabled).</li>
          </ul>
          <div className="my-6 p-8 border-2 border-dashed border-border rounded-lg bg-surface flex flex-col items-center justify-center text-text-muted gap-2">
            <div className="w-12 h-12 rounded-full bg-surface border border-border flex items-center justify-center">
              <ImageIcon className="w-6 h-6" />
            </div>
            <p className="font-medium">Screenshot: Knowledge Pipeline</p>
            <p className="text-sm text-center">Show the pipeline list with active stages.</p>
          </div>

          <AnchorHeading id="file-management" level="h2" className="mt-8">File Management</AnchorHeading>
          <p>
            Use the <strong>Graph Scope</strong> panel (Panel A) to manage what gets indexed.
          </p>
          
          <h3 className="text-base font-semibold mt-4">Excluding Files</h3>
          <p className="text-sm">
            CoDRAG respects your <code>.gitignore</code> automatically. To exclude additional files (like large assets or generated code) without git-ignoring them:
          </p>
          <ul className="list-disc pl-5 text-sm text-text-muted">
            <li>Go to the <strong>Excluded</strong> tab in the Graph Scope panel.</li>
            <li>Use the interface to add patterns or manage ignored files.</li>
          </ul>

          <h3 className="text-base font-semibold mt-4">Pinning Files</h3>
          <p className="text-sm">
            Important documentation or context files can be <strong>Pinned</strong> within the Scope view. Pinned files are prioritized in context assembly.
          </p>
          <div className="my-6 p-8 border-2 border-dashed border-border rounded-lg bg-surface flex flex-col items-center justify-center text-text-muted gap-2">
            <div className="w-12 h-12 rounded-full bg-surface border border-border flex items-center justify-center">
              <ImageIcon className="w-6 h-6" />
            </div>
            <p className="font-medium">Screenshot: Graph Scope Panel</p>
            <p className="text-sm text-center">Show the Scope panel with pinned items or context menu.</p>
          </div>

          <AnchorHeading id="project-settings" level="h2" className="mt-8">Project Settings</AnchorHeading>
          <p>
            Click the <strong>Settings</strong> tab in the dashboard to configure project-specific options.
          </p>
          <ul className="list-disc pl-5 text-sm text-text-muted space-y-2">
            <li><strong>Include/Exclude Patterns:</strong> Fine-tune exactly which files are indexed. Use <strong>Auto-Detect Stack</strong> to have CoDRAG scan your repo and suggest patterns for your framework.</li>
            <li><strong>File Size Limits:</strong> Adjust the max file size threshold (default 10MB) if you need to index large data files.</li>
            <li><strong>Auto-Rebuild:</strong> Toggle the background watcher for this specific project.</li>
          </ul>
          <div className="my-6 p-8 border-2 border-dashed border-border rounded-lg bg-surface flex flex-col items-center justify-center text-text-muted gap-2">
            <div className="w-12 h-12 rounded-full bg-surface border border-border flex items-center justify-center">
              <ImageIcon className="w-6 h-6" />
            </div>
            <p className="font-medium">Screenshot: Project Settings</p>
            <p className="text-sm text-center">Show the Project Settings panel with the Auto-Detect button visible.</p>
          </div>

        </div>
      </div>
    </main>
  );
}
