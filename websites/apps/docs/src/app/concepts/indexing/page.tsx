import { AnchorHeading } from '../../../components/AnchorHeading';

export default function Page() {
  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto max-w-3xl px-6 pb-16 pt-0">
        <a href="/concepts" className="text-sm text-text-muted">
          ← Back to Concepts
        </a>

        <h1 className="mt-6 text-3xl font-bold tracking-tight">Vector Indexing</h1>
        <p className="mt-4 text-xl text-text-muted">
          Stage 2 of the Knowledge Pipeline: Creating the searchable semantic layer.
        </p>

        <div className="mt-12 prose  max-w-none">
          <AnchorHeading id="pipeline" level="h2">The Indexing Process</AnchorHeading>
          <p>
            <span className="font-semibold text-text">Vector Indexing</span> is the second stage of the <a href="/dashboard#knowledge-pipeline">Knowledge Pipeline</a>. While the Structural Trace (Stage 1) maps the skeleton of your code, Vector Indexing creates the "muscle" that allows for fuzzy semantic search.
          </p>
          <p>
            Unlike cloud-based tools, this happens entirely on your localhost.
          </p>

          <div className="my-8 pl-4 border-l-4 border-primary space-y-4">
            <div>
              <span className="font-semibold text-text">1. Discovery</span>
              <p className="text-sm text-text-muted">
                The <code>codrag-walker</code> crate (Rust) scans your directory, respecting 
                <code>.gitignore</code> and user-defined exclusions. It computes BLAKE3 hashes for change detection.
              </p>
            </div>
            <div>
              <span className="font-semibold text-text">2. Parsing & Chunking</span>
              <p className="text-sm text-text-muted">
                Files are parsed using Tree-sitter. Code is split into logical chunks (functions, classes) 
                rather than arbitrary text windows. Markdown docs are split by headers.
              </p>
            </div>
            <div>
              <span className="font-semibold text-text">3. Embedding</span>
              <p className="text-sm text-text-muted">
                Chunks are passed to the <span className="font-semibold text-text">Native Embedder</span> (ONNX/nomic-embed-text) or 
                an optional Ollama instance. This converts text into 768-dimensional vectors.
              </p>
            </div>
            <div>
              <span className="font-semibold text-text">4. Storage</span>
              <p className="text-sm text-text-muted">
                Vectors and metadata are stored in a local LanceDB instance (or Qdrant/Chroma if configured). 
                The raw text is never sent to the cloud.
              </p>
            </div>
          </div>

          <AnchorHeading id="incremental" level="h2">Incremental Updates</AnchorHeading>
          <p>
            CoDRAG includes a real-time file watcher (<code>watchdog</code>). When you save a file:
          </p>
          <ul className="list-disc pl-5">
            <li>The watcher detects the <code>modify</code> event.</li>
            <li>It debounces rapid changes (e.g. typing).</li>
            <li>It re-hashes the file content.</li>
            <li>If the hash changed, only that file is re-parsed and re-embedded.</li>
          </ul>
          <p>
            This typically takes &lt;200ms, ensuring your AI always sees the current state of your code.
          </p>

          <AnchorHeading id="exclusions" level="h2">Exclusions</AnchorHeading>
          <p>
            You can control what gets indexed via the Dashboard or <code>.codrag/ignore</code>.
            Common patterns like <code>node_modules/</code>, <code>dist/</code>, and <code>.git/</code> 
            are ignored by default.
          </p>

          <hr className="my-12 border-border" />

          <AnchorHeading id="ui-controls" level="h2">Dashboard Controls</AnchorHeading>
          <p>
            The <span className="font-semibold text-text">Knowledge Base</span> column in the dashboard gives you visibility and control over this process.
          </p>

          <AnchorHeading id="status-card" level="h3" className="text-xl font-semibold mt-8 mb-4">Index Status Card</AnchorHeading>
          <p>
            The top card provides a real-time health check. Watch for the status badge in the top right:
          </p>
          <ul className="list-disc pl-5 mt-2 space-y-2">
            <li><span className="text-emerald-500 font-medium text-text">Fresh</span>: The index is perfectly synced with your disk.</li>
            <li><span className="text-amber-500 font-medium text-text">Stale</span>: Files have changed, but the index hasn't updated yet (usually brief during debounce).</li>
            <li><span className="text-blue-500 font-medium text-text">Building</span>: The background worker is actively processing files.</li>
          </ul>
          <p className="mt-4">
            It also breaks down the index composition:
          </p>
          <ul className="list-disc pl-5 mt-2 space-y-2">
            <li><span className="font-semibold text-text">Code:</span> Source files (parsed into AST chunks).</li>
            <li><span className="font-semibold text-text">Instructions:</span> Markdown, text, and documentation files (parsed by headers).</li>
            <li><span className="font-semibold text-text">Graph:</span> Structural nodes (symbols, imports) used for graph traversal.</li>
          </ul>

          <AnchorHeading id="manual-rebuild" level="h3" className="text-xl font-semibold mt-8 mb-4">Manual Rebuild</AnchorHeading>
          <p>
            While the watcher handles 99% of changes, you might need the <span className="font-semibold text-text">Build Index</span> card for:
          </p>
          <ul className="list-disc pl-5 mt-2 space-y-2">
            <li><span className="font-semibold text-text">Branch Switching:</span> If you switch git branches and thousands of files change instantly, a manual rebuild ensures everything is caught.</li>
            <li><span className="font-semibold text-text">Config Changes:</span> If you change <code>path_weights</code> or exclusion patterns, a rebuild applies them to the entire codebase.</li>
            <li><span className="font-semibold text-text">Troubleshooting:</span> If search feels "off", a full rebuild (using the <code>--full</code> flag via CLI or the dashboard button) clears the vector store and starts fresh.</li>
          </ul>
        </div>
      </div>
    </main>
  );
}
