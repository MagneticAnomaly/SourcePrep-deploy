import { AnchorHeading } from '../../../components/AnchorHeading';
import { StoryEmbed } from '../../../components/StoryEmbed';

export default function Page() {
  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto max-w-3xl px-6 pb-16 pt-0">
        <a href="/guides" className="text-sm text-text-muted">
          ← Back to Guides
        </a>

        <h1 className="mt-6 text-3xl font-bold tracking-tight">
          BYOK Cloud Batch Processing
        </h1>
        <p className="mt-4 text-lg text-text-muted">
          How CoDRAG optimizes API usage when you bring your own cloud model.
        </p>

        <div className="mt-8 prose max-w-none">
          <div className="rounded-lg bg-surface border border-border p-4 mb-8">
            <h4 className="font-semibold flex items-center gap-2">
              <span className="text-xl">🔒</span>
              Privacy Notice
            </h4>
            <p className="mt-2 text-sm">
              CoDRAG only sends data to external LLM providers when <span className="font-semibold text-text">you</span> configure
              a BYOK (Bring Your Own Key) endpoint and explicitly trigger a build.
              By default, all processing is local. See our{' '}
              <a href="https://github.com/nicobailey/CoDRAG/blob/main/public/codrag-mcp/PRIVACY.md" className="text-primary hover:underline">
                Privacy Policy
              </a>{' '}
              for full details.
            </p>
          </div>

          <AnchorHeading id="what-is-batching" level="h2">What Is Batch Processing?</AnchorHeading>
          <p>
            CoDRAG&apos;s pipeline analyzes your codebase in multiple stages &mdash; cataloguing files,
            detecting cross-file relationships, enriching each file with deeper analysis, and
            grouping files into subsystem clusters. Each stage needs to process every relevant
            file in your project.
          </p>
          <p>
            When using a <span className="font-semibold text-text">local model</span> (e.g., via Ollama), CoDRAG sends one file at
            a time to the model. This is fast locally and costs nothing.
          </p>
          <p>
            When using a <span className="font-semibold text-text">cloud model</span> (BYOK), sending files one at a time would mean
            hundreds of individual API calls &mdash; each with network latency and repeated overhead.
            Instead, CoDRAG <span className="font-semibold text-text">batches multiple files into a single API call</span>, getting
            results for many files at once.
          </p>

          <AnchorHeading id="what-is-sent" level="h2">What Data Is Sent?</AnchorHeading>
          <p>
            Each batch contains the same data that would be sent in individual calls:
          </p>
          <ul className="list-disc pl-6 space-y-2">
            <li>
              <span className="font-semibold text-text">Catalogue stage:</span> File names, symbol names, imports, and the first
              ~30 lines of each file.
            </li>
            <li>
              <span className="font-semibold text-text">Inferred edges stage:</span> Source code for each file, plus a list of
              known file paths in the project (for relationship detection).
            </li>
            <li>
              <span className="font-semibold text-text">Epistemic enrichment:</span> Source excerpts (up to 150 lines for code,
              up to 3000 lines for documentation), plus summaries of neighboring files.
            </li>
            <li>
              <span className="font-semibold text-text">Clustering:</span> Previously-generated summaries of files in each cluster
              (not raw source code).
            </li>
          </ul>
          <p className="text-sm text-text-muted mt-4">
            No data is sent to CoDRAG servers. All API calls go directly from your machine
            to the LLM provider you configured (e.g., OpenAI, Anthropic, Google).
          </p>

          <AnchorHeading id="how-batching-works" level="h2">How Batching Works</AnchorHeading>
          <p>
            CoDRAG automatically selects a <span className="font-semibold text-text">batch profile</span> based on the model you
            configure. The profile determines how many files are processed per API call at
            each pipeline stage.
          </p>

          <div className="my-6 overflow-x-auto">
            <table className="w-full text-sm border border-border">
              <thead>
                <tr className="bg-surface">
                  <th className="p-3 text-left border-b border-border text-text">Profile</th>
                  <th className="p-3 text-left border-b border-border text-text">Models</th>
                  <th className="p-3 text-left border-b border-border text-text">Typical items/call</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td className="p-3 border-b border-border font-medium text-text">Large</td>
                  <td className="p-3 border-b border-border text-text-muted">Claude Sonnet 4.5+, Gemini 2.5 Pro</td>
                  <td className="p-3 border-b border-border">50&ndash;100</td>
                </tr>
                <tr>
                  <td className="p-3 border-b border-border font-medium text-text">Standard</td>
                  <td className="p-3 border-b border-border text-text-muted">GPT-4.1, GPT-5, Claude 3</td>
                  <td className="p-3 border-b border-border">25&ndash;50</td>
                </tr>
                <tr>
                  <td className="p-3 border-b border-border font-medium text-text">Compact</td>
                  <td className="p-3 border-b border-border text-text-muted">DeepSeek, GPT-4o, Gemini Flash, Haiku 3.5</td>
                  <td className="p-3 border-b border-border">10&ndash;20</td>
                </tr>
                <tr>
                  <td className="p-3 border-b border-border font-medium text-text">Local</td>
                  <td className="p-3 border-b border-border text-text-muted">Ollama, LM Studio</td>
                  <td className="p-3 border-b border-border">1 (no batching)</td>
                </tr>
              </tbody>
            </table>
          </div>

          <p>
            The profile is selected automatically when you configure a model. You can override
            it in <span className="font-semibold text-text">Settings &gt; AI Models</span> if needed.
          </p>

          <div className="not-prose my-8">
            <StoryEmbed
              storyId="llm-endpointmanager--default"
              height={400}
              title="Endpoint Manager"
              caption="Live preview: Configure BYOK endpoints for OpenAI, Anthropic, Google, and custom providers."
            />
          </div>

          <AnchorHeading id="benefits" level="h2">Benefits</AnchorHeading>
          <ul className="list-disc pl-6 space-y-2">
            <li>
              <span className="font-semibold text-text">Faster builds:</span> A 200-file project completes in ~8 API calls
              instead of ~200, finishing in under a minute instead of 10&ndash;15 minutes.
            </li>
            <li>
              <span className="font-semibold text-text">Lower cost:</span> Batching amortizes per-call overhead (system prompts,
              instructions) across many items, saving ~25&ndash;33% on token costs.
            </li>
            <li>
              <span className="font-semibold text-text">Same results:</span> Each file receives the same analysis whether
              processed individually or in a batch. The prompts and expected outputs are identical.
            </li>
          </ul>

          <AnchorHeading id="structured-output" level="h2">Structured Output &amp; Reliability</AnchorHeading>
          <p>
            When supported by the provider (OpenAI, Anthropic, Google), CoDRAG uses{' '}
            <span className="font-semibold text-text">structured output mode</span> &mdash; a JSON schema that guarantees the model
            returns valid, correctly-formatted results. This eliminates parse errors and ensures
            every item in the batch produces a usable result.
          </p>
          <p>
            For providers without structured output support, CoDRAG falls back to robust JSON
            extraction with automatic retry for any items that fail to parse.
          </p>

          <AnchorHeading id="error-handling" level="h2">Error Handling</AnchorHeading>
          <p>
            If a batched call fails (timeout, rate limit, etc.), CoDRAG:
          </p>
          <ol className="list-decimal pl-6 space-y-2">
            <li>Retries the batch once.</li>
            <li>If it fails again, splits the batch in half and retries each half.</li>
            <li>As a last resort, falls back to processing items individually.</li>
          </ol>
          <p>
            No data is lost &mdash; failed items are always retried, and partial progress is saved.
          </p>

          <hr className="my-12 border-border" />

          <div className="rounded-lg bg-surface border border-border p-4">
            <h4 className="font-semibold flex items-center gap-2">
              <span className="text-xl">💡</span>
              Cost Estimation
            </h4>
            <p className="mt-2 text-sm">
              Before starting a build, the dashboard shows an estimated number of API calls
              and approximate cost based on your configured model. For example, a 200-file
              project with GPT-4.1 mini typically costs under $0.50.
            </p>
          </div>
        </div>
      </div>
    </main>
  );
}
