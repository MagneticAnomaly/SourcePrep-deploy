import { Image as ImageIcon } from 'lucide-react';
import { AnchorHeading } from '../../../components/AnchorHeading';

export default function Page() {
  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto max-w-3xl px-6 pb-16 pt-0">
        <a href="/guides" className="text-sm text-text-muted">
          &larr; Guides
        </a>

        <h1 className="mt-6 text-3xl font-bold tracking-tight">Knowledge Scope</h1>
        <p className="mt-4 text-lg text-text-muted">
          Select exactly which files and folders your AI assistant knows about.
        </p>

        {/* What is Knowledge Scope */}
        <section className="mt-10">
          <AnchorHeading id="what-is-knowledge-scope" level="h2">What is the Knowledge Scope?</AnchorHeading>
          <p className="mt-3 text-text-muted leading-relaxed">
            The Knowledge Scope is the set of files and folders you&apos;ve selected in the
            dashboard&apos;s <strong>FolderTree</strong> panel. When you toggle a file or folder
            on, it gets included in your project&apos;s index. When you toggle it off, it&apos;s
            excluded. Only selected files are searchable and available as context for your AI tools.
          </p>
          <div className="mt-4 p-4 rounded-lg border border-primary/20 bg-primary/5 text-sm">
            <strong>Two halves of CoDRAG&apos;s RAG:</strong> The <em>Code Graph</em> (trace) provides
            structural context automatically &mdash; imports, call chains, symbol relationships. The
            <em> Knowledge Scope</em> lets you manually curate which files are in the search index.
            Together, they give your AI both structural understanding and the exact files you care about.
          </div>
        </section>

        {/* How it works */}
        <section className="mt-10">
          <AnchorHeading id="how-it-works" level="h2">How it works</AnchorHeading>
          <div className="mt-4 rounded-lg bg-surface border border-border p-6 text-sm">
            <div className="space-y-3">
              <div className="flex items-start gap-3">
                <span className="shrink-0 w-6 h-6 rounded-full bg-primary/10 text-primary flex items-center justify-center text-xs font-bold">1</span>
                <div>
                  <div className="font-medium">Select files in the FolderTree</div>
                  <div className="mt-1 text-text-muted">Toggle individual files or entire folders. Selecting a folder includes all files inside it.</div>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <span className="shrink-0 w-6 h-6 rounded-full bg-primary/10 text-primary flex items-center justify-center text-xs font-bold">2</span>
                <div>
                  <div className="font-medium">Selection syncs to the server</div>
                  <div className="mt-1 text-text-muted">
                    Your selection is persisted server-side in the project config. It survives browser refreshes, works across clients (dashboard, Tauri app), and is readable by MCP tools.
                  </div>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <span className="shrink-0 w-6 h-6 rounded-full bg-primary/10 text-primary flex items-center justify-center text-xs font-bold">3</span>
                <div>
                  <div className="font-medium">Build indexes only your selected files</div>
                  <div className="mt-1 text-text-muted">
                    When you rebuild, only files in your Knowledge Scope are chunked and embedded. Files outside the scope are completely excluded from search results and context assembly.
                  </div>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <span className="shrink-0 w-6 h-6 rounded-full bg-primary/10 text-primary flex items-center justify-center text-xs font-bold">4</span>
                <div>
                  <div className="font-medium">Combine with Path Weights for fine-grained control</div>
                  <div className="mt-1 text-text-muted">
                    Use the Knowledge Scope to decide <em>what</em> is indexed, and <a href="/guides/path-weights" className="text-primary hover:underline">Path Weights</a> to control <em>how much</em> each file matters in search ranking.
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Dashboard usage */}
        <section className="mt-10">
          <AnchorHeading id="using-the-dashboard" level="h2">Using the dashboard</AnchorHeading>
          <p className="mt-3 text-text-muted leading-relaxed">
            Open the <strong>Knowledge Sources</strong> panel in your dashboard. Each file and folder
            has a checkbox. Checked items are in scope; unchecked items are excluded.
          </p>

          <div className="my-6 p-8 border-2 border-dashed border-border rounded-lg bg-surface flex flex-col items-center justify-center text-text-muted gap-2">
            <div className="w-12 h-12 rounded-full bg-surface border border-border flex items-center justify-center">
              <ImageIcon className="w-6 h-6" />
            </div>
            <p className="font-medium">Screenshot: Knowledge Scope Selection</p>
            <p className="text-sm text-center">Show the FolderTree panel with some files/folders checked and others unchecked.</p>
          </div>

          <ul className="mt-4 space-y-2 text-sm text-text-muted list-disc pl-5">
            <li><strong>Select a folder</strong> &mdash; includes all files inside it (descendants are cleaned up automatically)</li>
            <li><strong>Deselect a folder</strong> &mdash; removes it and all descendants; if a parent was selected, it &quot;explodes&quot; into sibling selections</li>
            <li><strong>Clear all</strong> &mdash; removes all selections (next build will index everything matching your glob patterns)</li>
          </ul>
          <p className="mt-3 text-sm text-text-muted">
            After changing your selection, click <strong>Build</strong> to re-index with the new scope.
            Pro-tier users with auto-rebuild enabled get automatic debounced rebuilds.
          </p>
        </section>

        {/* API usage */}
        <section className="mt-10">
          <AnchorHeading id="api-usage" level="h2">API usage</AnchorHeading>

          <h3 className="mt-6 text-lg font-medium">Get current scope</h3>
          <div className="mt-2 rounded-lg bg-surface border border-border p-4 font-mono text-sm overflow-x-auto">
            <div>curl http://localhost:8400/projects/my-project/included_paths</div>
          </div>
          <div className="mt-2 rounded-lg bg-surface border border-border p-4 font-mono text-xs text-text-muted overflow-x-auto">
            <div>{`{ "success": true, "data": { "included_paths": ["src", "docs/README.md"] } }`}</div>
          </div>

          <h3 className="mt-6 text-lg font-medium">Set scope (full replacement)</h3>
          <div className="mt-2 rounded-lg bg-surface border border-border p-4 font-mono text-sm overflow-x-auto">
            <div>curl -X PUT http://localhost:8400/projects/my-project/included_paths \</div>
            <div>  -H &quot;Content-Type: application/json&quot; \</div>
            <div>  -d &apos;{'{'} &quot;included_paths&quot;: [&quot;src&quot;, &quot;docs/README.md&quot;] {'}'}&apos;</div>
          </div>

          <h3 className="mt-6 text-lg font-medium">Add files to scope</h3>
          <div className="mt-2 rounded-lg bg-surface border border-border p-4 font-mono text-sm overflow-x-auto">
            <div>curl -X POST http://localhost:8400/projects/my-project/scope/add \</div>
            <div>  -H &quot;Content-Type: application/json&quot; \</div>
            <div>  -d &apos;{'{'} &quot;paths&quot;: [&quot;tests/test_auth.py&quot;] {'}'}&apos;</div>
          </div>

          <h3 className="mt-6 text-lg font-medium">Remove files from scope</h3>
          <div className="mt-2 rounded-lg bg-surface border border-border p-4 font-mono text-sm overflow-x-auto">
            <div>curl -X POST http://localhost:8400/projects/my-project/scope/remove \</div>
            <div>  -H &quot;Content-Type: application/json&quot; \</div>
            <div>  -d &apos;{'{'} &quot;paths&quot;: [&quot;vendor&quot;] {'}'}&apos;</div>
          </div>
        </section>

        {/* Relationship to other features */}
        <section className="mt-10">
          <AnchorHeading id="related-features" level="h2">How it fits together</AnchorHeading>
          <div className="mt-4 space-y-4">
            <div className="rounded-lg border border-border bg-surface p-4">
              <div className="font-medium text-sm">Knowledge Scope vs. Include/Exclude Globs</div>
              <div className="mt-2 text-sm text-text-muted">
                <strong>Globs</strong> (in Project Settings) define the file types CoDRAG can see: <code>**/*.py</code>, <code>**/*.md</code>.
                <strong> Knowledge Scope</strong> then lets you pick specific files/folders from that set. Think of globs as the &quot;universe&quot; and scope as your &quot;selection.&quot;
              </div>
            </div>
            <div className="rounded-lg border border-border bg-surface p-4">
              <div className="font-medium text-sm">Knowledge Scope vs. Path Weights</div>
              <div className="mt-2 text-sm text-text-muted">
                <strong>Scope</strong> controls <em>what</em> is indexed (binary: in or out).
                <strong> Path Weights</strong> control <em>how much</em> indexed files matter in ranking (0.0&ndash;2.0 multiplier).
                Use both together: scope to curate, weights to prioritize.
              </div>
            </div>
            <div className="rounded-lg border border-border bg-surface p-4">
              <div className="font-medium text-sm">Knowledge Scope + Code Graph</div>
              <div className="mt-2 text-sm text-text-muted">
                The Code Graph traces structural relationships (imports, calls) across your entire codebase.
                The Knowledge Scope controls the embedding index. When you use <code>codrag</code> (the primary MCP tool),
                it combines both: atlas routing from the graph + semantic search from your selected files.
              </div>
            </div>
          </div>
        </section>

        {/* API Reference */}
        <section className="mt-10">
          <AnchorHeading id="api-reference" level="h2">API reference</AnchorHeading>
          <div className="mt-4 space-y-4">
            <div className="rounded-lg border border-border bg-surface p-4">
              <div className="font-mono text-sm font-medium">GET /projects/{'{id}'}/included_paths</div>
              <p className="mt-1 text-sm text-text-muted">
                Returns the current Knowledge Scope (list of selected file/folder paths).
              </p>
            </div>
            <div className="rounded-lg border border-border bg-surface p-4">
              <div className="font-mono text-sm font-medium">PUT /projects/{'{id}'}/included_paths</div>
              <p className="mt-1 text-sm text-text-muted">
                Replace the entire scope. Body: <code>{`{ "included_paths": ["src", "docs"] }`}</code>.
                Paths are deduplicated and sorted.
              </p>
            </div>
            <div className="rounded-lg border border-border bg-surface p-4">
              <div className="font-mono text-sm font-medium">POST /projects/{'{id}'}/scope/add</div>
              <p className="mt-1 text-sm text-text-muted">
                Add paths to the scope. Body: <code>{`{ "paths": ["src/core"] }`}</code>.
                Adding a parent auto-removes explicit children.
              </p>
            </div>
            <div className="rounded-lg border border-border bg-surface p-4">
              <div className="font-mono text-sm font-medium">POST /projects/{'{id}'}/scope/remove</div>
              <p className="mt-1 text-sm text-text-muted">
                Remove paths from the scope. Body: <code>{`{ "paths": ["vendor"] }`}</code>.
                Removing a path also removes descendants.
              </p>
            </div>
            <div className="rounded-lg border border-border bg-surface p-4">
              <div className="font-mono text-sm font-medium">GET /projects/{'{id}'}/scope/status</div>
              <p className="mt-1 text-sm text-text-muted">
                Returns pipeline status (state, pending changes, debounce info) plus the full <code>included_paths</code> list.
              </p>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
