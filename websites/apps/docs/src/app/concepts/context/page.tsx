import { AnchorHeading } from '../../../components/AnchorHeading';

export default function Page() {
  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto max-w-3xl px-6 pb-16 pt-0">
        <a href="/concepts" className="text-sm text-text-muted">
          ← Back to Concepts
        </a>

        <h1 className="mt-6 text-3xl font-bold tracking-tight">Context Assembly</h1>
        <p className="mt-4 text-xl text-text-muted">
          Turning raw signals into an optimized LLM prompt.
        </p>

        <div className="mt-12 prose  max-w-none">
          <p>
            Retrieving code is easy. assembling it into a coherent prompt that fits within a context window 
            while maximizing information density is hard.
          </p>

          <AnchorHeading id="assembly-process" level="h2">The Assembly Process</AnchorHeading>
          
          <AnchorHeading id="retrieval" level="h3" className="text-lg font-semibold mt-6">1. Retrieval</AnchorHeading>
          <p>
            SourcePrep gathers candidates from multiple sources:
          </p>
          <ul className="list-disc pl-5">
            <li><span className="font-semibold text-text">Semantic Search:</span> Top-K chunks via vector similarity.</li>
            <li><span className="font-semibold text-text">Keyword Search:</span> BM25 matches for exact terms.</li>
            <li><span className="font-semibold text-text">Code Graph:</span> Related definitions and call sites (if trace expansion is on).</li>
          </ul>

          <AnchorHeading id="scoring" level="h3" className="text-lg font-semibold mt-6">2. Scoring & Weighting</AnchorHeading>
          <p>
            Candidates are re-scored based on:
          </p>
          <ul className="list-disc pl-5">
            <li><span className="font-semibold text-text">Relevance:</span> The raw vector distance.</li>
            <li><span className="font-semibold text-text">Query Intent:</span> SourcePrep classifies your query (e.g. &quot;docs&quot;, &quot;tests&quot;, &quot;code&quot;, or &quot;default&quot;) and automatically adjusts role weights. For example, &quot;how to use auth&quot; boosts documentation, while &quot;auth test failure&quot; boosts test files.</li>
            <li><span className="font-semibold text-text">Path Weights:</span> User-defined multipliers (e.g. boost <code>src/core</code> by 1.5x, suppress <code>tests/</code> by 0.5x).</li>
            <li><span className="font-semibold text-text">Priming:</span> Files named <code>AGENTS.md</code>, <code>PREP_PRIMER.md</code>, or <code>PROJECT_PRIMER.md</code> receive a global score boost (default +0.25). These files are ideal for high-level architectural overviews that should be considered relevant to most queries.</li>
            <li><span className="font-semibold text-text">Recency:</span> Slight boost for recently modified files (configurable).</li>
          </ul>

          <AnchorHeading id="budgeting" level="h3" className="text-lg font-semibold mt-6">3. Budgeting & Truncation</AnchorHeading>
          <p>
            You specify a <code>max_chars</code> or <code>max_tokens</code> budget. SourcePrep:
          </p>
          <ul className="list-disc pl-5">
            <li>Sorts chunks by their final score.</li>
            <li>Greedily adds chunks until the budget is near full.</li>
            <li>Ensures "glue" code (class headers, function signatures) is preserved for context.</li>
          </ul>

          <AnchorHeading id="compression" level="h3" className="text-lg font-semibold mt-6">4. Smart Compression</AnchorHeading>
          <p>
            When compression is enabled, SourcePrep uses two engines. <span className="font-semibold text-text">Code files</span> are structurally
            compressed at a Level of Detail (LOD) determined by relevance score &mdash; top results stay full,
            mid-relevance shows signatures, peripheral files show names only (3&ndash;20&times;, no model needed).
            <span className="font-semibold text-text">Documentation</span> is compressed with a lightweight language model that removes filler
            while preserving meaning (~2.4&times;). Both run on CPU. Tier-adaptive per client.
          </p>

          <AnchorHeading id="formatting" level="h3" className="text-lg font-semibold mt-6">5. Formatting</AnchorHeading>
          <p>
            The final output is formatted as XML, Markdown, or JSON, complete with file path citations 
            (<code>@src/file.ts:10-20</code>) that AI editors can parse to provide "Click to Open" links.
          </p>

          <hr className="my-12 border-border" />

          <AnchorHeading id="ui-controls" level="h2">Context Panel Controls</AnchorHeading>
          <p>
            The <span className="font-semibold text-text">Context Assembler</span> panel in the dashboard lets you tune this pipeline for your specific needs.
          </p>

          <div className="grid gap-6 md:grid-cols-2 mt-8">
            <div className="rounded-lg border border-border bg-surface p-6">
              <h4 className="font-semibold text-text mb-2">Retrieval Settings</h4>
              <ul className="space-y-3 text-sm text-text-muted">
                <li>
                  <span className="font-semibold text-text">Chunks (k):</span> Controls how many distinct code blocks are retrieved from the vector database. 
                  <br/><span className="text-xs">Default: 20. Increase for broad queries, decrease for precision.</span>
                </li>
                <li>
                  <span className="font-semibold text-text">Max Chars:</span> The hard limit for the final output. SourcePrep will stop adding chunks once this budget is hit.
                  <br/><span className="text-xs">Default: 24,000 chars (fits comfortably in most 32k context windows).</span>
                </li>
              </ul>
            </div>

            <div className="rounded-lg border border-border bg-surface p-6">
              <h4 className="font-semibold text-text mb-2">Output Toggles</h4>
              <ul className="space-y-3 text-sm text-text-muted">
                <li>
                  <span className="font-semibold text-text">Sources:</span> Adds the <code>@path/to/file:line-line</code> citation header to each chunk.
                  <br/><span className="text-xs">Essential for AI editors to provide clickable links.</span>
                </li>
                <li>
                  <span className="font-semibold text-text">Scores:</span> Appends the relevance score (0.0-1.0) to each chunk.
                  <br/><span className="text-xs">Useful for debugging why a specific piece of code was included.</span>
                </li>
                <li>
                  <span className="font-semibold text-text">Structured:</span> Returns a JSON object instead of a text blob.
                  <br/><span className="text-xs">Use this when building programmatic integrations.</span>
                </li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
