import { AnchorHeading } from '../../../components/AnchorHeading';

export default function Page() {
  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto max-w-3xl px-6 py-16">
        <a href="/concepts" className="text-sm text-text-muted">
          ← Back to Concepts
        </a>

        <h1 className="mt-6 text-3xl font-bold tracking-tight">Graph Enrichment</h1>
        <p className="mt-4 text-xl text-text-muted">
          How CoDRAG builds a self-refining understanding of your codebase through
          multiple enrichment passes.
        </p>

        <div className="mt-12 prose max-w-none">
          <p>
            A structural graph tells you <em>what</em> code exists and <em>how</em> it connects.
            Graph Enrichment goes further — it builds a layered, cross-referenced understanding
            of what your codebase <em>is</em>, what it <em>intends</em>, and how concepts link
            across code and documentation.
          </p>

          <AnchorHeading id="the-pipeline" level="h2">The 7-Stage Pipeline</AnchorHeading>
          <p>
            Enrichment is not just a single pass; it is a full <strong>Knowledge Pipeline</strong> that transforms raw text into a navigable semantic graph.
          </p>

          <div className="not-prose my-8 space-y-4">
            <div className="flex items-start gap-4 p-4 bg-surface border border-border rounded-lg">
              <div className="flex-shrink-0 w-10 h-10 rounded-full bg-success/10 text-success flex items-center justify-center font-bold text-sm">1</div>
              <div>
                <div className="font-semibold">Structural Trace <span className="text-xs font-normal bg-surface-raised border border-border-subtle px-1.5 py-0.5 rounded ml-1">Rust</span></div>
                <div className="text-sm text-text-muted mt-1">
                  Tree-sitter parses code into symbols, imports, and call edges. A new Markdown
                  scanner extracts section headers and links. ~100ms per file.
                </div>
              </div>
            </div>

            <div className="flex items-start gap-4 p-4 bg-surface border border-border rounded-lg">
              <div className="flex-shrink-0 w-10 h-10 rounded-full bg-success/10 text-success flex items-center justify-center font-bold text-sm">2</div>
              <div>
                <div className="font-semibold">Vector Indexing <span className="text-xs font-normal bg-surface-raised border border-border-subtle px-1.5 py-0.5 rounded ml-1">Embeddings</span></div>
                <div className="text-sm text-text-muted mt-1">
                  Source code is chunked and embedded for semantic search retrieval. This runs in parallel with the graph build.
                </div>
              </div>
            </div>

            <div className="flex items-start gap-4 p-4 bg-surface border border-border rounded-lg">
              <div className="flex-shrink-0 w-10 h-10 rounded-full bg-primary/10 text-primary flex items-center justify-center font-bold text-sm">3</div>
              <div>
                <div className="font-semibold">Fast Catalogue <span className="text-xs font-normal bg-surface-raised border border-border-subtle px-1.5 py-0.5 rounded ml-1">3b LLM</span></div>
                <div className="text-sm text-text-muted mt-1">
                  A small, fast model reads strategic excerpts of each file (Rust-ranked hot sections) to produce a summary and role classification.
                </div>
              </div>
            </div>

            <div className="flex items-start gap-4 p-4 bg-surface border border-border rounded-lg">
              <div className="flex-shrink-0 w-10 h-10 rounded-full bg-warning/10 text-warning flex items-center justify-center font-bold text-sm">4</div>
              <div>
                <div className="font-semibold">Relationship Validation <span className="text-xs font-normal bg-surface-raised border border-border-subtle px-1.5 py-0.5 rounded ml-1">Rust</span></div>
                <div className="text-sm text-text-muted mt-1">
                  The LLM&apos;s relationship hypotheses are validated against the filesystem. &quot;FileA relates to FileB&quot; &rarr; Rust checks if both exist. Hallucinations are discarded.
                </div>
              </div>
            </div>

            <div className="flex items-start gap-4 p-4 bg-surface border border-border rounded-lg">
              <div className="flex-shrink-0 w-10 h-10 rounded-full bg-primary/10 text-primary flex items-center justify-center font-bold text-sm">5</div>
              <div>
                <div className="font-semibold">Epistemic Enrichment <span className="text-xs font-normal bg-surface-raised border border-border-subtle px-1.5 py-0.5 rounded ml-1">14b LLM</span></div>
                <div className="text-sm text-text-muted mt-1">
                  A larger model enriches nodes with domain tags, architecture layers, design patterns, and calculates an <strong>epistemic score</strong> (0.0–1.0).
                </div>
              </div>
            </div>

            <div className="flex items-start gap-4 p-4 bg-surface border border-border rounded-lg">
              <div className="flex-shrink-0 w-10 h-10 rounded-full bg-primary/10 text-primary flex items-center justify-center font-bold text-sm">6</div>
              <div>
                <div className="font-semibold">Cluster Synthesis <span className="text-xs font-normal bg-surface-raised border border-border-subtle px-1.5 py-0.5 rounded ml-1">14b LLM</span></div>
                <div className="text-sm text-text-muted mt-1">
                  Nodes are grouped by domain into subsystem clusters. The model generates module-level summaries to create a navigable high-level map.
                </div>
              </div>
            </div>

            <div className="flex items-start gap-4 p-4 bg-surface border border-border rounded-lg">
              <div className="flex-shrink-0 w-10 h-10 rounded-full bg-purple-500/10 text-purple-600 flex items-center justify-center font-bold text-sm">7</div>
              <div>
                <div className="font-semibold">Knowledge Embedding <span className="text-xs font-normal bg-surface-raised border border-border-subtle px-1.5 py-0.5 rounded ml-1">Deep</span></div>
                <div className="text-sm text-text-muted mt-1">
                  Synthesized knowledge and enriched connections are embedded for deep semantic retrieval, completing the cycle.
                </div>
              </div>
            </div>
          </div>

          <AnchorHeading id="epistemic-score" level="h2">Epistemic Scoring</AnchorHeading>
          <p>
            Every node in the graph gets an <strong>epistemic score</strong> (0.0–1.0) that
            represents how well the trace <em>understands</em> this node in context. This is
            different from search relevance — it measures the depth and currency of the graph&apos;s
            knowledge about each file.
          </p>
          <div className="not-prose my-6">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="p-3 bg-surface border border-border rounded-lg">
                <div className="text-sm font-semibold">Structural completeness</div>
                <div className="text-xs text-text-muted">Has symbols, imports, edges?</div>
              </div>
              <div className="p-3 bg-surface border border-border rounded-lg">
                <div className="text-sm font-semibold">Semantic richness</div>
                <div className="text-xs text-text-muted">Domain tags, patterns, architecture layer?</div>
              </div>
              <div className="p-3 bg-surface border border-border rounded-lg">
                <div className="text-sm font-semibold">Cross-reference density</div>
                <div className="text-xs text-text-muted">Connected to docs and neighbors?</div>
              </div>
              <div className="p-3 bg-surface border border-border rounded-lg">
                <div className="text-sm font-semibold">Temporal currency</div>
                <div className="text-xs text-text-muted">Recently validated? Not stale?</div>
              </div>
            </div>
          </div>
          <p>
            Scores decay when neighbors change, referenced docs are updated, or source files
            are modified — ensuring the graph stays current as your codebase evolves.
          </p>

          <AnchorHeading id="hypothesis-and-test" level="h2">Hypothesis-and-Test Loop</AnchorHeading>
          <p>
            A key innovation is the <strong>LLM hypothesizes, Rust validates</strong> pattern.
            The small model suggests relationships (&quot;FileA probably relates to FileB&quot;), and the
            Rust engine validates them against the actual graph structure. This means:
          </p>
          <ul className="list-disc pl-5">
            <li>Hallucinated relationships are discarded (referencing files that don&apos;t exist)</li>
            <li>Confirmed relationships get boosted confidence</li>
            <li>Inferred edges never override parser-derived structural edges</li>
            <li>The graph gains semantic connections without sacrificing accuracy</li>
          </ul>

          <AnchorHeading id="doc-mining" level="h2">Documentation Mining</AnchorHeading>
          <p>
            Most indexing tools treat <code>.md</code> files as flat text blobs. CoDRAG&apos;s enrichment
            pipeline extracts structure from documentation: section headers, code references,
            status markers, and cross-links. This enables:
          </p>
          <ul className="list-disc pl-5">
            <li><strong>Doc↔code links</strong> — docs reference code files and vice versa</li>
            <li><strong>Staleness detection</strong> — a doc referencing a renamed file is flagged as drifted</li>
            <li><strong>Decision tracking</strong> — architecture decisions and their outcomes are captured</li>
            <li><strong>Orphan detection</strong> — docs with no code references or incoming links are identified</li>
          </ul>

          <AnchorHeading id="research" level="h2">Research Foundation</AnchorHeading>
          <p>
            The pipeline draws on peer-reviewed research in knowledge graph construction and
            code intelligence:
          </p>
          <ul className="list-disc pl-5 text-sm">
            <li>Hierarchical graph + community summaries — <em>Microsoft GraphRAG (2024)</em></li>
            <li>LLM → validator multi-agent enrichment — <em>KARMA (2025)</em></li>
            <li>AST → code knowledge graph — <em>KG-based Repo-Level Code Gen (2025)</em></li>
            <li>Bottom-up topological enrichment — <em>RepoAgent, EMNLP 2024</em></li>
            <li>Iterative convergence — <em>Belief Propagation (Pearl 1988, Yedidia 2003)</em></li>
          </ul>

          <p className="bg-info/10 border-l-4 border-info p-4 mt-6 text-sm">
            <strong>In practice:</strong> After enrichment, asking your AI &quot;how does the ad
            framework work?&quot; doesn&apos;t just return files with &quot;ad&quot; in the name — it returns
            the module summary, the 6 files that compose the subsystem, their entry points,
            the 3 docs that describe the architecture, and a flag that one doc references a
            renamed file.
          </p>
        </div>
      </div>
    </main>
  );
}
