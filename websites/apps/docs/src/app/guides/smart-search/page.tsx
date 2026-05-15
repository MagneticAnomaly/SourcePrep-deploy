import { AnimatedCLI, searchRetryReuseDemo, conceptsTransactionRuleDemo } from '../../../components/cli-demos';
import { AnchorHeading } from '../../../components/AnchorHeading';

export const metadata = {
  title: 'Smart Search — SourcePrep Docs',
  description:
    'How prep_search routes your query to the right backend — symbol lookup, semantic search, concepts, or trace graph — based on what you actually asked.',
};

export default function Page() {
  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto max-w-3xl px-6 pb-16 pt-0">
        <a href="/" className="text-sm text-text-muted">
          ← Back to Docs
        </a>

        <h1 className="mt-6 text-3xl font-bold tracking-tight">
          Smart Search
        </h1>
        <p className="mt-4 text-lg text-text-muted">
          &quot;Where is the login handler?&quot; and &quot;Why does the login
          handler bypass the rate limiter?&quot; are different questions that
          deserve different answers. SourcePrep reads the shape of your query
          and routes it to the right backend automatically.
        </p>

        <div className="mt-12 prose max-w-none">
          <AnchorHeading id="overview" level="h2">Why routing matters</AnchorHeading>
          <p>
            A single search tool is only good at one kind of answer. If
            everything goes through semantic search, exact symbol lookups get
            polluted with near-matches. If everything goes through the symbol
            index, conceptual questions return nothing. SourcePrep classifies
            your query into one of seven intents and sends it to the backend
            that actually knows how to answer it.
          </p>
          <p>
            Classification is rule-based and deterministic — no LLM call, no
            latency — so the same query always routes the same way.
          </p>

          <AnchorHeading id="intents" level="h2">The seven intents</AnchorHeading>

          <div className="my-8 space-y-4 pl-4 border-l-4 border-primary">
            <div>
              <span className="font-semibold text-text">LOCATE</span>
              <p className="text-sm text-text-muted">
                Triggers on <em>where is</em>, <em>find</em>, <em>show me</em>.
                Routes to symbol lookup. Returns path, signature, and line
                number — the kind of answer you&apos;d get from &quot;Go to
                Definition.&quot;
              </p>
              <p className="text-xs text-text-muted mt-1 font-mono">e.g. &quot;where is the login handler&quot;</p>
              <div className="not-prose mt-4">
                <AnimatedCLI script={searchRetryReuseDemo} />
              </div>
            </div>

            <div>
              <span className="font-semibold text-text">EXPLAIN</span>
              <p className="text-sm text-text-muted">
                Triggers on <em>how does</em>, <em>what does</em>, or anything
                without a stronger signal. Runs semantic search with trace
                expansion so you see both the code and its immediate
                collaborators. This is the default.
              </p>
              <p className="text-xs text-text-muted mt-1 font-mono">e.g. &quot;how does authentication work&quot;</p>
            </div>

            <div>
              <span className="font-semibold text-text">RATIONALE</span>
              <p className="text-sm text-text-muted">
                Triggers on <em>why</em>. Hits recorded concepts first — the
                place where business rules and design decisions live — and
                falls back to semantic search if nothing lands.
              </p>
              <p className="text-xs text-text-muted mt-1 font-mono">e.g. &quot;why does the billing queue retry twice&quot;</p>
              <div className="not-prose mt-4">
                <AnimatedCLI script={conceptsTransactionRuleDemo} />
              </div>
            </div>

            <div>
              <span className="font-semibold text-text">TRACE</span>
              <p className="text-sm text-text-muted">
                Triggers on <em>who calls</em>, <em>who imports</em>,{' '}
                <em>dependents of</em>. Routes through <code>prep_impact</code>{' '}
                so you get graph-accurate callers and importers rather than
                string matches.
              </p>
              <p className="text-xs text-text-muted mt-1 font-mono">e.g. &quot;who imports the rate limiter&quot;</p>
            </div>

            <div>
              <span className="font-semibold text-text">EXAMPLE</span>
              <p className="text-sm text-text-muted">
                Triggers on <em>example of</em>, <em>how to use</em>. Returns
                real call sites rather than the definition — the thing you
                actually want when you&apos;re trying to use an API.
              </p>
              <p className="text-xs text-text-muted mt-1 font-mono">e.g. &quot;example of using the retry decorator&quot;</p>
            </div>

            <div>
              <span className="font-semibold text-text">COMPARE</span>
              <p className="text-sm text-text-muted">
                Triggers on <em>difference between</em>, <em>X vs Y</em>.
                Pulls both sides in parallel so they can be read side-by-side.
              </p>
              <p className="text-xs text-text-muted mt-1 font-mono">e.g. &quot;difference between eager and lazy loader&quot;</p>
            </div>

            <div>
              <span className="font-semibold text-text">DISCOVER</span>
              <p className="text-sm text-text-muted">
                Triggers on <em>what&apos;s in</em>, <em>overview of</em>.
                Returns a module-level summary — the right altitude for
                orientation rather than a specific answer.
              </p>
              <p className="text-xs text-text-muted mt-1 font-mono">e.g. &quot;what&apos;s in the auth directory&quot;</p>
            </div>
          </div>

          <AnchorHeading id="override" level="h2">Overriding the classifier</AnchorHeading>
          <p>
            The classifier is right most of the time, but it&apos;s not
            magic. If you know what you want and the phrasing is ambiguous,
            pass <code>intent</code> explicitly:
          </p>
          <pre className="bg-surface border border-border rounded-xl p-5 text-sm font-mono overflow-x-auto">
{`prep_search(query="session token", intent="locate")`}
          </pre>
          <p className="mt-4">
            Every returned result includes the intent that was used, so you
            can see at a glance whether routing matched your mental model.
          </p>

          <AnchorHeading id="query-rewriting" level="h2">Query rewriting</AnchorHeading>
          <p>
            Once an intent is detected, SourcePrep strips the signal words
            (&quot;where is&quot;, &quot;why does&quot;, &quot;how to&quot;)
            before passing the remainder to the chosen backend. That means{' '}
            <em>&quot;where is the login handler&quot;</em> becomes a clean{' '}
            <code>login handler</code> lookup against the symbol index —
            without the scaffolding words polluting the score.
          </p>

          <AnchorHeading id="evaluation-order" level="h2">How ties are broken</AnchorHeading>
          <p>
            A query can match multiple intent patterns at once. The classifier
            picks the most specific one using this priority:
          </p>
          <ol className="list-decimal pl-5 mt-2 space-y-1">
            <li>TRACE</li>
            <li>RATIONALE</li>
            <li>COMPARE</li>
            <li>EXAMPLE</li>
            <li>DISCOVER</li>
            <li>LOCATE</li>
            <li>EXPLAIN (fallback — always wins if nothing else matched)</li>
          </ol>
          <p className="mt-4">
            So &quot;why does the login handler retry&quot; routes to
            RATIONALE (concepts) rather than LOCATE (symbol lookup), because
            the <em>why</em> signal wins over the <em>login handler</em> noun
            phrase.
          </p>

          <div className="mt-8 rounded-xl border border-border bg-surface p-6">
            <p className="font-semibold text-text">Good to know</p>
            <ul className="mt-2 list-disc pl-5 space-y-2 text-text-muted">
              <li>Classification is local and deterministic — no model inference, no telemetry, no surprise latency.</li>
              <li>Results include a confidence score alongside the chosen intent, so low-confidence routes can be audited.</li>
              <li>If none of the patterns hit, the query defaults to EXPLAIN and runs as plain semantic search.</li>
            </ul>
          </div>
        </div>
      </div>
    </main>
  );
}
