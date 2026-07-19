import { AnchorHeading } from '../../../components/AnchorHeading';

export const metadata = {
  title: 'Audit Enrichment — SourcePrep Docs',
  description:
    'Pipe lint and static-analysis findings through prep_audit to get structural context — dependent count, hub status, related concepts, and risk score — attached to each result.',
};

export default function Page() {
  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto max-w-3xl px-6 pb-16 pt-0">
        <a href="/" className="text-sm text-text-muted">
          ← Back to Docs
        </a>

        <h1 className="mt-6 text-3xl font-bold tracking-tight">
          Audit Enrichment
        </h1>
        <p className="mt-4 text-lg text-text-muted">
          A lint warning in a hub file that 200 other files depend on is not the
          same as the same warning in a one-off script. SourcePrep takes raw
          findings from your linter and annotates each one with structural
          context so you can triage by blast radius, not just by severity.
        </p>

        <div className="mt-12 prose max-w-none">
          <AnchorHeading id="overview" level="h2">What it does</AnchorHeading>
          <p>
            Feed <code>prep_audit</code> a list of findings from any tool —
            ruff, ESLint, semgrep, CodeQL, GitHub Code Scanning — and SourcePrep
            layers structural information on top of each one:
          </p>
          <ul className="list-disc pl-5 mt-2 space-y-2">
            <li><span className="font-semibold text-text">Dependent count</span> — how many other files import the flagged file.</li>
            <li><span className="font-semibold text-text">Hub status</span> — <code>critical</code>, <code>high</code>, <code>moderate</code>, or <code>low</code>, derived from the file&apos;s position in the graph.</li>
            <li><span className="font-semibold text-text">Module</span> — which architectural module the file belongs to.</li>
            <li><span className="font-semibold text-text">Related concepts</span> — business rules or design decisions recorded for that file.</li>
            <li><span className="font-semibold text-text">Risk score</span> — a 0.0–1.0 number combining severity with structural impact.</li>
            <li><span className="font-semibold text-text">Recommendation</span> — a short plain-language hint about where this finding sits on the triage spectrum.</li>
          </ul>

          <AnchorHeading id="simple-format" level="h2">Simple format</AnchorHeading>
          <p>
            The simplest way to use this is with a flat list of findings. Each
            finding needs a file path, a line, a message, a severity, and the
            tool that produced it.
          </p>
          <pre className="bg-surface border border-border rounded-xl p-5 text-sm font-mono overflow-x-auto">
{`prep_audit(findings=[
  {
    "file": "src/prep/core/indexer.py",
    "line": 142,
    "message": "Unused import: pathlib.PurePath",
    "severity": "warning",
    "tool": "ruff"
  }
])`}
          </pre>
          <p className="mt-4">
            SourcePrep returns each finding with a <code>prep</code> object
            attached:
          </p>
          <pre className="bg-surface border border-border rounded-xl p-5 text-sm font-mono overflow-x-auto">
{`{
  "file": "src/prep/core/indexer.py",
  "line": 142,
  "message": "Unused import: pathlib.PurePath",
  "severity": "warning",
  "tool": "ruff",
  "prep": {
    "dependents": 47,
    "hub_status": "high",
    "module": "core",
    "concepts": ["indexer-must-be-idempotent"],
    "risk_score": 0.62,
    "recommendation": "Hub file — verify no dynamic import relies on this symbol before removal."
  }
}`}
          </pre>

          <AnchorHeading id="sarif" level="h2">SARIF round-trip</AnchorHeading>
          <p>
            If your pipeline already speaks SARIF (GitHub Code Scanning,
            semgrep, CodeQL), hand the SARIF document directly to{' '}
            <code>prep_audit</code>. SourcePrep detects the format, enriches every
            result, and returns a valid SARIF document back — the structural
            context rides along as <code>properties.prep</code> on each result.
          </p>
          <pre className="bg-surface border border-border rounded-xl p-5 text-sm font-mono overflow-x-auto">
{`# Your tool emits SARIF
semgrep --config auto --sarif --output findings.sarif

# Pipe it through prep_audit
prep_audit(findings=<SARIF dict>)

# Back comes enriched SARIF — every result now has properties.prep`}
          </pre>
          <p className="mt-4">
            Both SARIF 2.0.0 and 2.1.0 are accepted. The returned document
            round-trips cleanly into any SARIF viewer — the enrichment is
            additive, not destructive.
          </p>

          <AnchorHeading id="why" level="h2">Why this matters</AnchorHeading>
          <p>
            Linters and scanners are structure-blind by design — they look at
            one file at a time. That produces long flat lists where a dead
            import in a leaf utility looks identical to a dead import in a file
            that forty modules depend on. SourcePrep fixes that triage gap
            without changing your scanner:
          </p>
          <ul className="list-disc pl-5 mt-2 space-y-2">
            <li>Sort by <code>risk_score</code> to get the blast-radius-aware queue.</li>
            <li>Filter by <code>hub_status</code> to isolate findings in fragile areas.</li>
            <li>Cross-reference <code>concepts</code> to see which findings touch codified business rules.</li>
          </ul>

          <AnchorHeading id="example-workflow" level="h2">Example workflow</AnchorHeading>
          <p>
            Typical loop inside an AI agent or a CI job:
          </p>
          <ol className="list-decimal pl-5 mt-2 space-y-2">
            <li>Run your linter. Export JSON or SARIF.</li>
            <li>Call <code>prep_audit(findings=...)</code>.</li>
            <li>Re-sort results by <code>risk_score</code> descending.</li>
            <li>Attack the top findings first — those are the ones where fixing one line benefits the most of the codebase.</li>
          </ol>

          <div className="mt-8 rounded-xl border border-border bg-surface p-6">
            <p className="font-semibold text-text">Good to know</p>
            <ul className="mt-2 list-disc pl-5 space-y-2 text-text-muted">
              <li>Enrichment is read-only and runs locally against your existing index — nothing is sent to the cloud.</li>
              <li>If a file isn&apos;t in the trace graph, it is still returned with a <code>prep</code> object, but with <code>dependents: 0</code> and <code>hub_status: &quot;low&quot;</code>.</li>
              <li>The <code>tool</code> field is preserved end-to-end so downstream dashboards can still group by linter.</li>
            </ul>
          </div>
        </div>
      </div>
    </main>
  );
}
