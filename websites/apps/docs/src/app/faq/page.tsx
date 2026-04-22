import { AnchorHeading } from '../../components/AnchorHeading';

export default function Page() {
  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto max-w-3xl px-6 pb-16 pt-0">
        <a href="/" className="text-sm text-text-muted">
          ← Back to Docs
        </a>

        <h1 className="mt-6 text-3xl font-bold tracking-tight">FAQ</h1>
        <p className="mt-4 text-xl text-text-muted">
          Frequently asked questions about SourcePrep.
        </p>

        <div className="mt-12 space-y-8">
          
          <div>
            <AnchorHeading id="cloud-upload" level="h2" className="text-xl font-semibold text-text">Is my code uploaded to the cloud?</AnchorHeading>
            <p className="mt-2 text-text-muted leading-relaxed">
              <span className="font-semibold text-text">No.</span> SourcePrep is local-first software. All indexing, vector storage, and processing happens on your machine. 
              The only time data leaves your machine is if you explicitly configure a cloud LLM (BYOK) or during the one-time license activation check.
            </p>
          </div>

          <div>
            <AnchorHeading id="editor-support" level="h2" className="text-xl font-semibold text-text">Does it work with any editor?</AnchorHeading>
            <p className="mt-2 text-text-muted leading-relaxed">
              SourcePrep works best with editors that support the <span className="font-semibold text-text">Model Context Protocol (MCP)</span>, such as Cursor, Windsurf, and Claude Code. 
              There is also a VS Code extension in development. For other editors, you can copy-paste context from the Dashboard or CLI.
            </p>
          </div>

          <div>
            <AnchorHeading id="gpu-requirement" level="h2" className="text-xl font-semibold text-text">Do I need a GPU?</AnchorHeading>
            <p className="mt-2 text-text-muted leading-relaxed">
              <span className="font-semibold text-text">No.</span> The core features (indexing, trace graph, search, and compression) run efficiently on CPU. 
              The built-in embedding model is quantized and optimized for CPU inference. 
              Context compression is built in &mdash; structural compression for code runs instantly with no model, and language-aware compression for docs uses a lightweight CPU model.
            </p>
          </div>

          <div>
            <AnchorHeading id="ai-tool-usage" level="h2" className="text-xl font-semibold text-text">Why does the AI sometimes ignore the SourcePrep tools and use its own search?</AnchorHeading>
            <p className="mt-2 text-text-muted leading-relaxed">
              AI agents (like Cascade or Cursor) are trained to find the cheapest, fastest path to an answer. If you ask a <span className="font-semibold text-text">textual</span> question (e.g., &quot;audit the copy for mentions of 'cloud'&quot; or &quot;find the word 'Ollama'&quot;), the AI will usually prefer its native <code>grep</code> or file search tools because regex is the right tool for pure text matching.
            </p>
            <p className="mt-2 text-text-muted leading-relaxed">
              SourcePrep tools shine for <span className="font-semibold text-text">structural</span> and <span className="font-semibold text-text">semantic</span> tasks. The AI will naturally reach for SourcePrep when you ask about relationships (e.g., &quot;what breaks if I change this function?&quot;), architecture (e.g., &quot;map out the authentication flow&quot;), or when it needs to compress huge amounts of context. You can always force it to use SourcePrep by saying: <span className="italic">&quot;Use the prep tools to...&quot;</span>
            </p>
          </div>

          <div>
            <AnchorHeading id="cursor-diff" level="h2" className="text-xl font-semibold text-text">How is this different from Cursor&apos;s built-in index?</AnchorHeading>
            <p className="mt-2 text-text-muted leading-relaxed">
              Cursor&apos;s index is great, but SourcePrep adds a <span className="font-semibold text-text">Structural Code Graph layer</span> (understanding imports, definitions, and calls across the project) which reduces hallucinations. 
              SourcePrep also gives you explicit control over context via <span className="font-semibold text-text">Path Weights</span> and <span className="font-semibold text-text">Compression</span>, allowing you to fit much more relevant code into the context window than a standard RAG approach.
            </p>
          </div>

          <div>
            <AnchorHeading id="bug-reports" level="h2" className="text-xl font-semibold text-text">What data is included in bug reports?</AnchorHeading>
            <p className="mt-2 text-text-muted leading-relaxed">
              SourcePrep&apos;s built-in bug report (dashboard → log console → bug icon) collects only diagnostic metadata:
              app version, OS info, index stats, pipeline status, and error messages. <span className="font-semibold text-text">It never includes
              source code, file contents, embeddings, LLM prompts, or file paths beyond your project root name.</span> You
              can preview every field before submitting. If you&apos;re offline, the report saves as a local JSON
              file you can review and email manually. See the full breakdown on our{' '}
              <a href="https://sourceprep.io/security#bug-reports" className="text-primary hover:underline">Security &amp; Privacy</a> page.
            </p>
          </div>

          <div>
            <AnchorHeading id="free-tier" level="h2" className="text-xl font-semibold text-text">Is there a free tier?</AnchorHeading>
            <p className="mt-2 text-text-muted leading-relaxed">
              <span className="font-semibold text-text">Yes.</span> The Free tier includes 3 active projects with all features — real-time sync, the full enrichment pipeline, and trace-aware MCP.
              Upgrading to Pro unlocks unlimited projects.
            </p>
          </div>

        </div>
      </div>
    </main>
  );
}
