import { AnchorHeading } from '../../../components/AnchorHeading';

export default function Page() {
  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto max-w-3xl px-6 pb-16 pt-0">
        <a href="/guides" className="text-sm text-text-muted">
          ← Back to Guides
        </a>

        <h1 className="mt-6 text-3xl font-bold tracking-tight">
          Concurrency Discovery &amp; Locking
        </h1>
        <p className="mt-4 text-lg text-text-muted">
          Why your throughput may dip after a plan upgrade — and the one click
          that fixes it.
        </p>

        <div className="mt-8 prose max-w-none">
          <div className="rounded-lg bg-surface border border-border p-4 mb-8">
            <h4 className="font-semibold flex items-center gap-2">
              <span className="text-xl">🛟</span>
              Quick fix
            </h4>
            <p className="mt-2 text-sm">
              Just upgraded your Ollama Cloud plan and SourcePrep still feels
              slow? Open <span className="font-semibold text-text">AI Gateway</span>,
              click the <span className="font-semibold text-text">Developer</span> wrench
              under <span className="font-semibold text-text">Pipeline Activity</span>,
              and hit{' '}
              <span className="font-semibold text-text">Reset</span> next to your
              cloud endpoint. SourcePrep will re-discover the new limit on the
              next request.
            </p>
          </div>

          <AnchorHeading id="why-it-exists" level="h2">Why this exists</AnchorHeading>
          <p>
            When you point SourcePrep at a cloud LLM endpoint for the first time,
            the system has no idea how many parallel requests your provider will
            actually accept. Ollama Cloud, Together, OpenRouter, and most
            BYOK providers don&rsquo;t advertise their concurrency cap up front,
            and the &ldquo;real&rdquo; cap depends on your plan tier, your account
            region, and provider load.
          </p>
          <p>
            SourcePrep figures it out from real traffic. It starts conservatively,
            grows the parallel-request budget while latency stays healthy, and
            backs off the moment the provider returns a rate-limit error or
            latency spikes. The safe ceiling that emerges from this dance is
            the <span className="font-semibold text-text">discovered ceiling</span>.
          </p>
          <p>
            Once SourcePrep finds that ceiling, it{' '}
            <span className="font-semibold text-text">locks it for 24 hours</span> so
            it doesn&rsquo;t keep poking at the limit on every long-running build.
            That keeps your pipelines smooth and your provider happy. The trade-off:
            if the underlying capacity changes, the lock has to be invalidated
            for SourcePrep to find the new number.
          </p>

          <AnchorHeading id="what-youll-see" level="h2">What you&rsquo;ll see</AnchorHeading>
          <p>
            In the dashboard&rsquo;s pipeline queue (sidebar), each cloud endpoint
            shows its current concurrency state next to the in-flight count:
          </p>
          <ul className="list-disc pl-6 space-y-2">
            <li>
              <code className="text-xs">cloud:default_ollama 5/52 📈</code> — five requests
              in flight, current ceiling is 52, system is still climbing (probing).
            </li>
            <li>
              <code className="text-xs">cloud:default_ollama 50/52 🔒</code> — sitting at the
              discovered ceiling; the lock is held and won&rsquo;t grow further until
              it expires.
            </li>
            <li>
              <code className="text-xs">cloud:default_ollama 8/12 🌧️</code> — recent backoff
              detected; the system is recovering before trying to grow again.
            </li>
          </ul>
          <p className="text-sm text-text-muted mt-4">
            For the full timeline (every probe, every backoff, every recovery),
            open <span className="font-semibold text-text">Settings → Diagnostics → Concurrency Health</span>.
            Each cloud node has a live event feed showing why the current limit
            is what it is.
          </p>

          <AnchorHeading id="when-its-wrong" level="h2">When the ceiling is wrong</AnchorHeading>
          <p>
            The lock exists because re-probing every minute would itself be
            wasted capacity. But three things can make the locked ceiling stale:
          </p>
          <ol className="list-decimal pl-6 space-y-2">
            <li>
              <span className="font-semibold text-text">You upgraded your plan.</span> Ollama
              Cloud Free → Max, OpenRouter free tier → paid, and similar plan
              jumps usually come with higher concurrency limits. SourcePrep is
              still using the old, lower lock.
            </li>
            <li>
              <span className="font-semibold text-text">Your provider changed limits.</span> Rare,
              but providers occasionally raise (or lower) per-account quotas. The
              previous discovered ceiling no longer reflects reality.
            </li>
            <li>
              <span className="font-semibold text-text">Your network path changed.</span> A new
              VPN, a different egress region, or a switch between residential
              and corporate uplink can shift effective throughput enough that
              the old ceiling becomes the wrong number.
            </li>
          </ol>

          <AnchorHeading id="how-to-reset" level="h2">How to reset it</AnchorHeading>
          <p>You have three options, in order of convenience:</p>
          <div className="space-y-4 my-6">
            <div className="border border-border rounded-lg p-5 bg-surface">
              <h3 className="text-base font-semibold mt-0">1. The developer button (recommended)</h3>
              <p className="text-sm text-text-muted mb-3">
                Open <span className="font-semibold text-text">AI Gateway</span>{' '}
                in the dashboard. Scroll to{' '}
                <span className="font-semibold text-text">Pipeline Activity</span>.
                Click the small <span className="font-semibold text-text">Developer</span>{' '}
                wrench in the section header. Hit{' '}
                <span className="font-semibold text-text">Reset</span> next to the
                cloud endpoint you want to re-discover. Confirm.
              </p>
              <p className="text-sm text-text-muted">
                You&rsquo;ll see a <code className="text-xs">Cleared. New probe on next acquire.</code>{' '}
                confirmation. The next outbound request to that endpoint kicks off
                fresh discovery.
              </p>
            </div>

            <div className="border border-border rounded-lg p-5 bg-surface">
              <h3 className="text-base font-semibold mt-0">2. The HTTP API</h3>
              <p className="text-sm text-text-muted mb-3">
                For scripts, headless setups, or CI:
              </p>
              <pre className="bg-background border border-border rounded p-3 text-xs overflow-x-auto"><code>{`curl -X POST 'http://localhost:8400/compute/concurrency/clear?node_id=cloud:default_ollama'`}</code></pre>
              <p className="text-sm text-text-muted mt-3">
                Replace <code className="text-xs">cloud:default_ollama</code> with
                the node id of your endpoint. Run{' '}
                <code className="text-xs">GET /compute/scheduler</code> to list
                live nodes.
              </p>
            </div>

            <div className="border border-border rounded-lg p-5 bg-surface">
              <h3 className="text-base font-semibold mt-0">3. Wait it out</h3>
              <p className="text-sm text-text-muted">
                The lock expires automatically after 24 hours. After that, SourcePrep
                probes one step up on the next acquire and starts re-discovering.
                If you&rsquo;re patient, doing nothing works.
              </p>
            </div>
          </div>

          <AnchorHeading id="what-gets-reset" level="h2">What gets reset</AnchorHeading>
          <p>
            A reset only invalidates the persisted ceiling for{' '}
            <span className="font-semibold text-text">that one endpoint</span>. Specifically:
          </p>
          <ul className="list-disc pl-6 space-y-2">
            <li>The 24-hour lock for that <code className="text-xs">cloud:*</code> node is dropped.</li>
            <li>The in-memory slot is reset back to <code className="text-xs">probing</code> state.</li>
            <li>
              On the next request to that endpoint, discovery restarts from the
              system&rsquo;s jumpstart seed (typically 5 parallel requests, or whatever
              the provider&rsquo;s probe value suggests).
            </li>
          </ul>
          <p>Nothing else is touched:</p>
          <ul className="list-disc pl-6 space-y-2">
            <li>Other cloud endpoints keep their existing locks.</li>
            <li>Local node concurrency (VRAM-bounded) is unaffected.</li>
            <li>In-flight requests are not interrupted.</li>
            <li>Your saved endpoint config, model selection, and pipeline state are unchanged.</li>
          </ul>

          <AnchorHeading id="what-to-expect-after" level="h2">What to expect after a reset</AnchorHeading>
          <p>
            For a few seconds to a minute, throughput may{' '}
            <span className="font-semibold text-text">briefly drop</span> while
            the system climbs back from the conservative jumpstart. This is
            expected — discovery has to start somewhere safe. If you upgraded
            your plan, the new ceiling will land higher than before within
            a few minutes of normal traffic.
          </p>
          <p>
            If you don&rsquo;t see a higher ceiling settle in, your provider may
            still be capping you at the old limit (some plan upgrades take time
            to propagate). The{' '}
            <span className="font-semibold text-text">Concurrency Health</span> view
            in Settings → Diagnostics shows every backoff event, which is the
            quickest way to see what&rsquo;s actually happening.
          </p>

          <hr className="my-12 border-border" />

          <div className="rounded-lg bg-surface border border-border p-4">
            <h4 className="font-semibold flex items-center gap-2">
              <span className="text-xl">🤖</span>
              For AI agents
            </h4>
            <p className="mt-2 text-sm">
              If you&rsquo;re working with an AI assistant connected to SourcePrep
              via MCP, ask it to{' '}
              <code className="text-xs">prep_search &ldquo;concurrency ceiling&rdquo;</code>{' '}
              — the same explanation surfaces as a built-in concept the agent
              can read directly.
            </p>
          </div>
        </div>
      </div>
    </main>
  );
}
