import { AnchorHeading } from '../../../components/AnchorHeading';

export default function Page() {
  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto max-w-3xl px-6 py-16">
        <a href="/concepts" className="text-sm text-text-muted">
          ← Back to Concepts
        </a>

        <h1 className="mt-6 text-3xl font-bold tracking-tight">Code Graph</h1>
        <p className="mt-4 text-xl text-text-muted">
          The structural backbone of CoDRAG.
        </p>

        <div className="mt-12 prose  max-w-none">
          <p>
            Vector search is great for &quot;fuzzy&quot; questions (&quot;how does auth work?&quot;), but terrible 
            at precision (&quot;where is the <code>User</code> struct defined and what calls it?&quot;).
          </p>
          <p>
            To solve this, CoDRAG maintains a parallel <strong>Code Graph</strong> — a directed graph 
            of your codebase's structure.
          </p>

          <AnchorHeading id="rust-engine" level="h2">Rust Engine</AnchorHeading>
          <p>
            The Code Graph is built by a high-performance Rust engine (`codrag-engine`) that runs alongside the Python daemon.
          </p>
          <ul className="list-disc pl-5">
            <li><strong>Speed:</strong> Parses ~50k files in seconds.</li>
            <li><strong>Accuracy:</strong> Uses Tree-sitter to generate concrete syntax trees (CSTs) for accurate symbol extraction.</li>
            <li><strong>Multi-language:</strong> Supports Python, TypeScript, JavaScript, Go, Rust, Java, C, and C++.</li>
          </ul>

          <AnchorHeading id="the-graph" level="h2">The Graph</AnchorHeading>
          <p>
            The index maps three types of relationships:
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 my-6 not-prose">
            <div className="p-4 bg-surface border border-border rounded-lg text-center">
              <div className="font-bold mb-1">Definitions</div>
              <div className="text-xs text-text-muted">&quot;Where is X declared?&quot;</div>
            </div>
            <div className="p-4 bg-surface border border-border rounded-lg text-center">
              <div className="font-bold mb-1">References</div>
              <div className="text-xs text-text-muted">&quot;Where is X used?&quot;</div>
            </div>
            <div className="p-4 bg-surface border border-border rounded-lg text-center">
              <div className="font-bold mb-1">Imports</div>
              <div className="text-xs text-text-muted">&quot;What does file A depend on?&quot;</div>
            </div>
          </div>

          <AnchorHeading id="visualization" level="h2">Visualizing the Graph</AnchorHeading>
          <p>
            The <strong>Code Graph</strong> panel in the dashboard provides an interactive way to explore these relationships.
          </p>
          <ul className="list-disc pl-5 mt-2 mb-6">
            <li><strong>Interactive Map:</strong> Visualize your project's structure as a network of nodes (files/symbols) and edges (imports/calls).</li>
            <li><strong>Neighborhood View:</strong> Click any file to see its immediate dependencies (upstream) and consumers (downstream).</li>
            <li><strong>List View:</strong> Toggle to a detailed list to see exact import counts and symbol references.</li>
          </ul>

          <AnchorHeading id="usage" level="h2">Usage</AnchorHeading>
          <p>
            You generally don&apos;t query the code graph directly. Instead, you enable <strong>Graph Expansion</strong> 
            in your context request (or use the &quot;Trace&quot; keywords in your MCP editor).
          </p>
          <p>
            When enabled, CoDRAG:
          </p>
          <ol className="list-decimal pl-5">
            <li>Finds the primary chunks via vector search.</li>
            <li>Identifies key symbols in those chunks.</li>
            <li>Queries the Code Graph for their definition sites and usages.</li>
            <li>&quot;Expands&quot; the context to include those related files, even if they didn&apos;t match the search keywords.</li>
          </ol>
          
          <p className="bg-info/10 border-l-4 border-info p-4 mt-6 text-sm">
            <strong>Example:</strong> You ask &quot;How is billing calculated?&quot;. <br/>
            Vector search finds <code>billing.py</code>. <br/>
            The Code Graph notices <code>billing.py</code> imports <code>tax_rates.py</code>. <br/>
            CoDRAG includes <code>tax_rates.py</code> in the context automatically, preventing the AI from hallucinating tax logic.
          </p>

          <AnchorHeading id="knowledge-pipeline" level="h2">The Knowledge Pipeline</AnchorHeading>
          <p>
            The Code Graph is not a static artifact; it is the backbone of a dynamic <strong>7-Stage Knowledge Pipeline</strong> that transforms raw text into navigable knowledge.
          </p>
          
          <div className="mt-6 border border-border rounded-lg overflow-hidden">
            <div className="bg-surface-raised px-4 py-2 border-b border-border font-medium text-sm">Pipeline Stages</div>
            <div className="divide-y divide-border">
              <div className="p-4 bg-surface">
                <div className="font-semibold text-primary">1. Structural Trace (Rust)</div>
                <div className="text-sm text-text-muted mt-1">High-speed parsing of file structure to build the initial skeleton.</div>
              </div>
              <div className="p-4 bg-surface">
                <div className="font-semibold">2. Vector Indexing</div>
                <div className="text-sm text-text-muted mt-1">Generating search embeddings for source code chunks (Searchability).</div>
              </div>
              <div className="p-4 bg-surface">
                <div className="font-semibold">3. Fast Catalogue (3b)</div>
                <div className="text-sm text-text-muted mt-1">Lightweight tagging and classification of symbols.</div>
              </div>
              <div className="p-4 bg-surface">
                <div className="font-semibold text-primary">4. Relationship Validation (Rust)</div>
                <div className="text-sm text-text-muted mt-1">Verifying imports and call graph edges against the filesystem.</div>
              </div>
              <div className="p-4 bg-surface">
                <div className="font-semibold">5. Epistemic Enrichment (14b)</div>
                <div className="text-sm text-text-muted mt-1">Deep analysis to add "why" and "how" context to the nodes.</div>
              </div>
              <div className="p-4 bg-surface">
                <div className="font-semibold">6. Cluster Synthesis</div>
                <div className="text-sm text-text-muted mt-1">Grouping related files into functional modules.</div>
              </div>
              <div className="p-4 bg-surface">
                <div className="font-semibold text-purple-500">7. Knowledge Embedding</div>
                <div className="text-sm text-text-muted mt-1">Final deep-storage of synthesized knowledge and enriched connections.</div>
              </div>
            </div>
          </div>

          <p className="mt-6">
            This pipeline ensures that CoDRAG understands not just <em>where</em> code is (Structure), but <em>what</em> it does (Enrichment) and <em>how</em> it relates conceptually (Embeddings).
          </p>

          <p>
            <a href="/concepts/graph-enrichment" className="text-primary hover:underline">
              Learn more about Graph Enrichment →
            </a>
          </p>
        </div>
      </div>
    </main>
  );
}
