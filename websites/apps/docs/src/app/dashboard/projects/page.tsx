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
        <p className="mt-4 text-xl text-text-muted">
          Projects are the core unit of organization in CoDRAG. A project connects a local
          codebase directory to a <span className="font-semibold text-text">Knowledge Index</span> and <span className="font-semibold text-text">Trace Graph</span>.
        </p>
        
        <div className="mt-12 prose  max-w-none">
          
          <AnchorHeading id="adding-projects" level="h2">Adding Projects</AnchorHeading>
          <p>
            You can add projects via the CLI (<code>codrag add .</code>) or directly in the Dashboard.
          </p>
          <ol className="list-decimal pl-5 text-sm text-text-muted">
            <li>Open the CoDRAG desktop app.</li>
            <li>Click the <span className="font-semibold text-text">&quot;+&quot;</span> button in the sidebar project list.</li>
            <li>Select your repository folder using the file picker.</li>
            <li>Give it a friendly name (optional).</li>
          </ol>
          <div className="my-6 p-8 border-2 border-dashed border-border rounded-lg bg-surface flex flex-col items-center justify-center text-text-muted gap-2">
            <div className="w-12 h-12 rounded-full bg-surface border border-border flex items-center justify-center">
              <ImageIcon className="w-6 h-6" />
            </div>
            <p className="font-medium text-text">Screenshot: Add Project Modal</p>
            <p className="text-sm text-center">Show the <span className="font-semibold text-text">&apos;Add Project&apos;</span> modal with path and name fields.</p>
          </div>

          <AnchorHeading id="indexing-status" level="h2" className="mt-8">Indexing Status</AnchorHeading>
          <p>
            Once added, CoDRAG begins the 7-stage knowledge process managed by the <span className="font-semibold text-text">Knowledge Pipeline</span> (Panel B):
          </p>
          <ul className="list-disc pl-5 text-sm text-text-muted">
            <li><span className="font-semibold text-text">Structural Trace:</span> (Rust) Fast parsing of your codebase structure.</li>
            <li><span className="font-semibold text-text">Vector Indexing:</span> (Embeddings) Creating searchable chunks for the knowledge base.</li>
          </ul>
          <div className="my-6 p-8 border-2 border-dashed border-border rounded-lg bg-surface flex flex-col items-center justify-center text-text-muted gap-2">
            <div className="w-12 h-12 rounded-full bg-surface border border-border flex items-center justify-center">
              <ImageIcon className="w-6 h-6" />
            </div>
            <p className="font-medium text-text">Screenshot: Knowledge Pipeline</p>
            <p className="text-sm text-center">Show the pipeline list with active stages.</p>
          </div>

          <AnchorHeading id="file-management" level="h2" className="mt-8">File Management</AnchorHeading>
          <p>
            Use the <span className="font-semibold text-text">Graph Scope</span> panel (Panel A) to manage what gets indexed.
          </p>
          
          <h3 className="text-base font-semibold mt-4">Excluding Files</h3>
          <p className="text-sm">
            CoDRAG respects your <code>.gitignore</code> automatically. To exclude additional files (like large assets or generated code) without git-ignoring them:
          </p>
          <ul className="list-disc pl-5 text-sm text-text-muted">
            <li>Go to the <span className="font-semibold text-text">Excluded</span> tab in the Graph Scope panel.</li>
            <li>Use the interface to add patterns or manage ignored files.</li>
          </ul>

          <h3 className="text-base font-semibold mt-4">Pinning Files</h3>
          <p className="text-sm">
            Important documentation or context files can be <span className="font-semibold text-text">Pinned</span> within the Scope view. Pinned files are prioritized in context assembly.
          </p>
          <div className="my-6 p-8 border-2 border-dashed border-border rounded-lg bg-surface flex flex-col items-center justify-center text-text-muted gap-2">
            <div className="w-12 h-12 rounded-full bg-surface border border-border flex items-center justify-center">
              <ImageIcon className="w-6 h-6" />
            </div>
            <p className="font-medium text-text">Screenshot: Graph Scope Panel</p>
            <p className="text-sm text-center">Show the Scope panel with pinned items or context menu.</p>
          </div>

          <AnchorHeading id="project-settings" level="h2" className="mt-8">Project Settings</AnchorHeading>
          <p>
            Click the <span className="font-semibold text-text">Settings</span> tab in the dashboard to configure project-specific options.
          </p>
          <ul className="list-disc pl-5 text-sm text-text-muted space-y-2">
            <li><span className="font-semibold text-text">Include/Exclude Patterns:</span> Fine-tune exactly which files are indexed. Use <span className="font-semibold text-text">Auto-Detect Stack</span> to have CoDRAG scan your repo and suggest patterns for your framework.</li>
            <li><span className="font-semibold text-text">File Size Limits:</span> Adjust the max file size threshold (default 10MB) if you need to index large data files.</li>
            <li><span className="font-semibold text-text">Auto-Rebuild:</span> Toggle the background watcher for this specific project.</li>
          </ul>
          <div className="my-6 p-8 border-2 border-dashed border-border rounded-lg bg-surface flex flex-col items-center justify-center text-text-muted gap-2">
            <div className="w-12 h-12 rounded-full bg-surface border border-border flex items-center justify-center">
              <ImageIcon className="w-6 h-6" />
            </div>
            <p className="font-medium text-text">Screenshot: Project Settings</p>
            <p className="text-sm text-center">Show the Project Settings panel with the Auto-Detect button visible.</p>
          </div>

        </div>
      </div>
    </main>
  );
}
