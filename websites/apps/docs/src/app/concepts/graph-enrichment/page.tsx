import { AnchorHeading } from '../../../components/AnchorHeading';

export default function Page() {
  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto max-w-3xl px-6 pb-16 pt-0">
        <a href="/concepts" className="text-sm text-text-muted">
          ← Back to Concepts
        </a>

        <h1 className="mt-6 text-3xl font-bold tracking-tight">Graph Enrichment</h1>
        <p className="mt-4 text-xl text-text-muted">
          How Prep builds a self-refining understanding of your codebase — and why
          treating a code graph as an epistemological system changes everything.
        </p>

        <div className="mt-12 prose max-w-none">

          <AnchorHeading id="why-epistemology" level="h2">Why Epistemology?</AnchorHeading>
          <p>
            Most code intelligence tools answer a simple question: <em>&quot;Which files match this query?&quot;</em>
            Prep asks a fundamentally different one: <span className="font-semibold text-text">&quot;How well does the system understand
            this code — and how justified is that understanding?&quot;</span>
          </p>
          <p>
            That question is epistemological. Epistemology is the branch of philosophy concerned with
            knowledge itself — what it means to <em>know</em> something, how knowledge is <em>justified</em>,
            and when it becomes <em>stale</em>. These aren&apos;t abstract concerns when you&apos;re building a code graph:
          </p>
          <ul className="list-disc pl-5">
            <li>A file summary can be <span className="font-semibold text-text">accurate</span> (the text is correct) but not <span className="font-semibold text-text">understood</span> (we don&apos;t know how it connects to anything)</li>
            <li>A node&apos;s understanding <span className="font-semibold text-text">decays</span> when its neighbors change — because context is relational, not intrinsic</li>
            <li>A doc referencing a renamed file is <span className="font-semibold text-text">drifted knowledge</span> — technically present, epistemically broken</li>
            <li>Re-enriching the <em>least understood</em> nodes first (residual scheduling) mirrors how belief propagation converges in probabilistic graphical models</li>
          </ul>
          <p>
            The trace graph doesn&apos;t just <em>contain</em> knowledge about your code — it <span className="font-semibold text-text">knows
            about its own knowledge</span>.
          </p>

          <AnchorHeading id="the-pipeline" level="h2">The 9-Stage Pipeline</AnchorHeading>
          <p>
            Enrichment is split into two groups: a <span className="font-semibold text-text">Fast Sync</span> group that runs on
            every file save (~seconds), and a <span className="font-semibold text-text">Deep Enrichment</span> group that runs
            when the system is idle or on a schedule (~minutes).
          </p>

          <h3 className="text-lg font-semibold mt-6 mb-4">Group A: Fast Sync</h3>
          <div className="not-prose space-y-4">
            <div className="flex items-start gap-4 p-4 bg-surface border border-border rounded-lg">
              <div className="flex-shrink-0 w-10 h-10 rounded-full bg-success/10 text-success flex items-center justify-center font-bold text-sm">1</div>
              <div>
                <div className="font-semibold">Structural Graph <span className="text-xs font-normal bg-surface-raised border border-border-subtle px-1.5 py-0.5 rounded ml-1">Rust</span></div>
                <div className="text-sm text-text-muted mt-1">
                  Tree-sitter parses code into symbols, imports, and call edges. A Markdown scanner extracts section headers and links from documentation files. This is the factual skeleton — no LLM involved, no opinions, just structure.
                </div>
              </div>
            </div>

            <div className="flex items-start gap-4 p-4 bg-surface border border-border rounded-lg">
              <div className="flex-shrink-0 w-10 h-10 rounded-full bg-primary/10 text-primary flex items-center justify-center font-bold text-sm">2</div>
              <div>
                <div className="font-semibold">Fast Catalogue <span className="text-xs font-normal bg-surface-raised border border-border-subtle px-1.5 py-0.5 rounded ml-1">3b LLM</span></div>
                <div className="text-sm text-text-muted mt-1">
                  A small, fast model reads strategic excerpts of each file (Rust-ranked hot sections) to produce a summary, role classification, and initial confidence estimate. This is <em>triage</em>, not understanding — the 3b model&apos;s job is to answer &quot;what does this file appear to do?&quot;
                </div>
              </div>
            </div>

            <div className="flex items-start gap-4 p-4 bg-surface border border-border rounded-lg">
              <div className="flex-shrink-0 w-10 h-10 rounded-full bg-warning/10 text-warning flex items-center justify-center font-bold text-sm">3</div>
              <div>
                <div className="font-semibold">Relationship Validation <span className="text-xs font-normal bg-surface-raised border border-border-subtle px-1.5 py-0.5 rounded ml-1">Rust</span></div>
                <div className="text-sm text-text-muted mt-1">
                  The <span className="font-semibold text-text">LLM hypothesizes, Rust validates</span> pattern. The catalogue model suggests relationships (&quot;FileA probably relates to FileB&quot;) — the Rust engine checks if both files actually exist. Hallucinated edges are discarded. Confirmed edges gain boosted confidence. Inferred edges never override parser-derived structural edges.
                </div>
              </div>
            </div>

            <div className="flex items-start gap-4 p-4 bg-surface border border-border rounded-lg">
              <div className="flex-shrink-0 w-10 h-10 rounded-full bg-purple-500/10 text-purple-600 flex items-center justify-center font-bold text-sm">4</div>
              <div>
                <div className="font-semibold">Knowledge Embedding <span className="text-xs font-normal bg-surface-raised border border-border-subtle px-1.5 py-0.5 rounded ml-1">Embeddings</span></div>
                <div className="text-sm text-text-muted mt-1">
                  Validated nodes and their metadata are embedded for semantic search retrieval. This makes the catalogue immediately searchable while deep enrichment continues in the background.
                </div>
              </div>
            </div>
          </div>

          <h3 className="text-lg font-semibold mt-8 mb-4">Group B: Deep Enrichment</h3>
          <div className="not-prose space-y-4">
            <div className="flex items-start gap-4 p-4 bg-surface border border-border rounded-lg">
              <div className="flex-shrink-0 w-10 h-10 rounded-full bg-primary/10 text-primary flex items-center justify-center font-bold text-sm">5</div>
              <div>
                <div className="font-semibold">Deep Reasoning <span className="text-xs font-normal bg-surface-raised border border-border-subtle px-1.5 py-0.5 rounded ml-1">14b LLM</span></div>
                <div className="text-sm text-text-muted mt-1">
                  <em>Epistemic enrichment.</em> A larger model reasons about each node <span className="font-semibold text-text">in the context of its graph neighbors</span> — adding domain tags, architecture layers, design patterns, cross-references, and a self-reported reasoning confidence. Nodes are processed in reverse-topological order (leaf files first) so each node&apos;s neighbors already have enriched summaries when it&apos;s processed.
                </div>
              </div>
            </div>

            <div className="flex items-start gap-4 p-4 bg-surface border border-border rounded-lg">
              <div className="flex-shrink-0 w-10 h-10 rounded-full bg-primary/10 text-primary flex items-center justify-center font-bold text-sm">6</div>
              <div>
                <div className="font-semibold">Module Synthesis <span className="text-xs font-normal bg-surface-raised border border-border-subtle px-1.5 py-0.5 rounded ml-1">14b LLM</span></div>
                <div className="text-sm text-text-muted mt-1">
                  <em>Cluster synthesis.</em> Enriched nodes are grouped by domain tags and graph connectivity into subsystem modules. The model generates module-level summaries — creating navigable high-level architecture maps. Think of it as the trace graph discovering its own subsystems.
                </div>
              </div>
            </div>

            <div className="flex items-start gap-4 p-4 bg-surface border border-border rounded-lg">
              <div className="flex-shrink-0 w-10 h-10 rounded-full bg-primary/10 text-primary flex items-center justify-center font-bold text-sm">7</div>
              <div>
                <div className="font-semibold">Codebase Atlas <span className="text-xs font-normal bg-surface-raised border border-border-subtle px-1.5 py-0.5 rounded ml-1">Routing</span></div>
                <div className="text-sm text-text-muted mt-1">
                  Synthesized modules are used to build a pre-retrieval routing index. When your AI asks for context, the Atlas scopes the search to the right subsystem before retrieval begins — reducing noise without reducing coverage.
                </div>
              </div>
            </div>

            <div className="flex items-start gap-4 p-4 bg-surface border border-border rounded-lg">
              <div className="flex-shrink-0 w-10 h-10 rounded-full bg-primary/10 text-primary flex items-center justify-center font-bold text-sm">8</div>
              <div>
                <div className="font-semibold">Continuous Deepening <span className="text-xs font-normal bg-surface-raised border border-border-subtle px-1.5 py-0.5 rounded ml-1">Loop</span></div>
                <div className="text-sm text-text-muted mt-1">
                  <em>The convergence loop.</em> Nodes whose understanding scores have decayed — because a neighbor changed, a doc drifted, or source was modified — are re-enriched in priority order. Inspired by <span className="font-semibold text-text">belief propagation</span> (Pearl 1988): the least-understood nodes are processed first, and the loop continues until the graph stabilizes or a token budget is reached.
                </div>
              </div>
            </div>

            <div className="flex items-start gap-4 p-4 bg-surface border border-border rounded-lg">
              <div className="flex-shrink-0 w-10 h-10 rounded-full bg-purple-500/10 text-purple-600 flex items-center justify-center font-bold text-sm">9</div>
              <div>
                <div className="font-semibold">Deep Knowledge Embedding <span className="text-xs font-normal bg-surface-raised border border-border-subtle px-1.5 py-0.5 rounded ml-1">Embeddings</span></div>
                <div className="text-sm text-text-muted mt-1">
                  All enriched knowledge — module summaries, deepened connections, refined cross-references — is re-embedded for maximum retrieval accuracy. The search index now reflects the graph&apos;s full understanding, not just the initial catalogue.
                </div>
              </div>
            </div>
          </div>

          <AnchorHeading id="understanding-score" level="h2">The Understanding Score</AnchorHeading>
          <p>
            Every node in the graph gets an <span className="font-semibold text-text">understanding score</span> (0.0–1.0) — internally
            called the <em>epistemic score</em> — that represents how well the trace comprehends
            this node in the context of the entire codebase. This is fundamentally different from
            search relevance or summary accuracy. A file can have a perfect summary but a low
            understanding score if we don&apos;t know how it connects to anything else.
          </p>
          <p>
            The score is a weighted composite of six dimensions:
          </p>
          <div className="not-prose my-6">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="p-3 bg-surface border border-border rounded-lg">
                <div className="text-sm font-semibold">Summary confidence <span className="text-xs text-text-muted">(20%)</span></div>
                <div className="text-xs text-text-muted">How certain is the catalogue model about its own output?</div>
              </div>
              <div className="p-3 bg-surface border border-border rounded-lg">
                <div className="text-sm font-semibold">Validation depth <span className="text-xs text-text-muted">(15%)</span></div>
                <div className="text-xs text-text-muted">Has a larger model verified and enriched the summary?</div>
              </div>
              <div className="p-3 bg-surface border border-border rounded-lg">
                <div className="text-sm font-semibold">Neighbor coverage <span className="text-xs text-text-muted">(20%)</span></div>
                <div className="text-xs text-text-muted">Are connected nodes also enriched? Understanding is relational.</div>
              </div>
              <div className="p-3 bg-surface border border-border rounded-lg">
                <div className="text-sm font-semibold">Cross-reference density <span className="text-xs text-text-muted">(15%)</span></div>
                <div className="text-xs text-text-muted">How many doc↔code bidirectional links exist?</div>
              </div>
              <div className="p-3 bg-surface border border-border rounded-lg">
                <div className="text-sm font-semibold">Enrichment depth <span className="text-xs text-text-muted">(15%)</span></div>
                <div className="text-xs text-text-muted">How many reasoning passes has this node been through?</div>
              </div>
              <div className="p-3 bg-surface border border-border rounded-lg">
                <div className="text-sm font-semibold">Temporal currency <span className="text-xs text-text-muted">(15%)</span></div>
                <div className="text-xs text-text-muted">Has the source changed since enrichment? Stale knowledge scores zero.</div>
              </div>
            </div>
          </div>

          <AnchorHeading id="score-decay" level="h2">Score Decay — Knowledge Has a Half-Life</AnchorHeading>
          <p>
            Understanding scores aren&apos;t static. They <span className="font-semibold text-text">decay</span> when the world changes
            around a node — because in epistemology, knowledge that hasn&apos;t been re-verified against
            current evidence is no longer justified belief:
          </p>
          <div className="not-prose my-6 overflow-x-auto">
            <table className="text-sm w-full">
              <thead>
                <tr className="border-b border-border text-left text-text">
                  <th className="py-2 pr-4 font-medium text-text">Event</th>
                  <th className="py-2 pr-4 font-medium text-text">Effect</th>
                  <th className="py-2 font-medium text-text">Rationale</th>
                </tr>
              </thead>
              <tbody className="text-text-muted">
                <tr className="border-b border-border/50"><td className="py-2 pr-4">Source file changed</td><td className="py-2 pr-4">Score → 0.0</td><td className="py-2">Everything might be wrong</td></tr>
                <tr className="border-b border-border/50"><td className="py-2 pr-4">Neighbor re-enriched</td><td className="py-2 pr-4">Score × 0.95</td><td className="py-2">Context shifted slightly</td></tr>
                <tr className="border-b border-border/50"><td className="py-2 pr-4">Referenced doc updated</td><td className="py-2 pr-4">Score × 0.90</td><td className="py-2">Documentation changed, claims may be invalid</td></tr>
                <tr className="border-b border-border/50"><td className="py-2 pr-4">Trace rebuilt (structural)</td><td className="py-2 pr-4">Score × 0.80</td><td className="py-2">Edges changed, relationships may differ</td></tr>
                <tr><td className="py-2 pr-4">Module re-synthesized</td><td className="py-2 pr-4">Score × 0.97</td><td className="py-2">Module understanding refined</td></tr>
              </tbody>
            </table>
          </div>
          <p>
            Decay cascades through neighbors: if File A changes, File B (which imports A)
            decays slightly, and File C (which imports B) decays even less — up to a 3-hop
            propagation limit. This mirrors how uncertainty propagates through belief networks.
          </p>
          <p>
            Nodes with decayed scores enter a <span className="font-semibold text-text">re-analysis queue</span> ordered by score
            (lowest first). The Continuous Deepening stage processes this queue until the graph
            converges or the token budget is exhausted.
          </p>

          <AnchorHeading id="doc-mining" level="h2">Documentation Mining</AnchorHeading>
          <p>
            Most indexing tools treat <code>.md</code> files as flat text blobs. Prep&apos;s enrichment
            pipeline extracts structure from documentation: section headers, code references,
            status markers, and cross-links. This enables:
          </p>
          <ul className="list-disc pl-5">
            <li><span className="font-semibold text-text">Doc↔code links</span> — docs reference code files and vice versa</li>
            <li><span className="font-semibold text-text">Staleness detection</span> — a doc referencing a renamed file is flagged as drifted</li>
            <li><span className="font-semibold text-text">Decision tracking</span> — architecture decisions and their outcomes are captured</li>
            <li><span className="font-semibold text-text">Orphan detection</span> — docs with no code references or incoming links are identified</li>
          </ul>

          <AnchorHeading id="research" level="h2">Research Foundation</AnchorHeading>
          <p>
            The pipeline draws on peer-reviewed research in knowledge graph construction,
            code intelligence, and probabilistic reasoning:
          </p>
          <ul className="list-disc pl-5 text-sm">
            <li>Hierarchical graph + community summaries — <em>Microsoft GraphRAG (2024)</em></li>
            <li>LLM → validator multi-agent enrichment — <em>KARMA (2025)</em></li>
            <li>AST → code knowledge graph — <em>KG-based Repo-Level Code Gen (2025)</em></li>
            <li>Bottom-up topological enrichment — <em>RepoAgent, EMNLP 2024</em></li>
            <li>Iterative convergence via residual scheduling — <em>Belief Propagation (Pearl 1988, Yedidia 2003)</em></li>
            <li>Score decay and re-enrichment — inspired by <em>epistemic logic</em> and <em>truth-maintenance systems (Doyle 1979)</em></li>
          </ul>

          <AnchorHeading id="why-it-matters" level="h2">Why This Matters in Practice</AnchorHeading>
          <p className="bg-info/10 border-l-4 border-info p-4 text-sm">
            <span className="font-semibold text-text">Without enrichment:</span> asking your AI &quot;how does the ad framework work?&quot;
            might return one file that mentions &quot;ad&quot;.
          </p>
          <p className="bg-success/10 border-l-4 border-success p-4 mt-3 text-sm">
            <span className="font-semibold text-text">With enrichment:</span> the same query returns the module summary, the
            6 files that compose the subsystem, their entry points, the 3 docs that describe
            the architecture, and a flag that one doc references a renamed file. The understanding
            score tells the AI that the framework is well understood, but one file&apos;s score has decayed
            because one neighbor was recently modified and hasn&apos;t been re-analyzed yet.
          </p>
          <p>
            The difference isn&apos;t just better search results. It&apos;s the difference between a tool
            that <em>retrieves</em> and a tool that <em>understands</em> — and knows the boundary
            between the two.
          </p>
        </div>
      </div>
    </main>
  );
}
