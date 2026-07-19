'use client';

import { AnimatedCLI, auditPrSanityCheckDemo } from '../../../components/cli-demos';
import { AnchorHeading } from '../../../components/AnchorHeading';
import { DemoAuditPanelWithFindings, DemoOpportunitiesWithItems } from '../../../components/demos';

export default function Page() {
  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto max-w-3xl px-6 pb-16 pt-0">
        <a href="/" className="text-sm text-text-muted">
          ← Back to Docs
        </a>

        <h1 className="mt-6 text-4xl font-bold tracking-tight">
          Codebase Audit
        </h1>
        <p className="mt-4 text-xl text-text-muted">
          Autonomous codebase health analysis powered by the trace graph.
          Get architecture reports, gap analysis, tech debt summaries, and
          actionable recommendations — all generated from your existing
          enrichment data.
        </p>

        <div className="mt-12 prose max-w-none">
          <AnchorHeading id="overview" level="h2">Overview</AnchorHeading>
          <p>
            AutoAudit analyzes your trace graph (nodes, edges, augmentations,
            epistemic enrichment, modules, and atlas) to produce structured
            findings and optional LLM-generated reports. It runs as an
            independent tool — not a pipeline stage — so you trigger it when
            you want insights, not on every file change.
          </p>
          <p className="mt-4">
            <strong>AutoAudit V2</strong> transforms SourcePrep from a "passive observer" into an "active taskmaster". Findings are categorized into flat tabs (Architecture, Quality, Coverage, Tech Debt), prioritized, and include concrete actionable items. You can select findings and click <strong>"Copy AI Command"</strong> to instantly hand off the context assembly to your AI via MCP.
          </p>

          <div className="not-prose">
            <DemoAuditPanelWithFindings />
            <p className="text-xs text-text-subtle italic -mt-4">
              Live preview: AutoAudit findings organized by severity and category with AI handoff.
            </p>
          </div>

          <div className="not-prose my-8 rounded-xl border border-border bg-surface p-6">
            <h3 className="text-lg font-semibold">Two Tiers</h3>
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <div className="rounded-lg border border-border p-4">
                <div className="font-mono text-sm text-primary">Tier 1 — Analyzers</div>
                <p className="mt-2 text-sm text-text-muted">
                  Pure graph queries. No LLM needed. Runs in &lt;2 seconds.
                  Produces structured findings (JSON).
                </p>
              </div>
              <div className="rounded-lg border border-border p-4">
                <div className="font-mono text-sm text-primary">Tier 2 — Synthesis</div>
                <p className="mt-2 text-sm text-text-muted">
                  LLM-generated markdown reports. Uses your configured large
                  model. Produces 5 documents.
                </p>
              </div>
            </div>
          </div>

          <AnchorHeading id="quick-start" level="h2">Quick Start</AnchorHeading>

          <AnchorHeading id="cli" level="h3">CLI</AnchorHeading>
          <p>
            Audits are triggered via the MCP <code>prep_audit</code> tool, the REST API,
            or the dashboard&apos;s Audit panel — not a direct CLI command. To read findings
            from the most recent run from a terminal, use <code>prep opportunities</code>:
          </p>
          <pre className="rounded-lg bg-surface-raised p-4"><code>{`# List actionable findings from the latest audit
prep opportunities

# Filter by minimum priority
prep opportunities --priority P1

# Export as SARIF for CI ingestion
prep opportunities --format sarif

# Pipe a high-priority subset to an AI agent prompt
prep opportunities --priority P0 --format ai_prompt`}</code></pre>

          <div className="not-prose my-6">
            <AnimatedCLI script={auditPrSanityCheckDemo} />
          </div>
          <p className="text-xs text-text-muted text-center italic mt-2">
            What a PR-sanity audit looks like when an agent calls <code>prep_audit</code> mid-review.
          </p>

          <AnchorHeading id="mcp" level="h3">MCP Tool</AnchorHeading>
          <p>
            One MCP tool, <code className="text-primary">prep_audit</code>, exposes all audit functionality
            across Cursor, Windsurf, Claude Code, and any MCP-compatible editor. The behavior is
            selected via the <code>action</code> parameter:
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="py-2 pr-4 text-left font-semibold">Action</th>
                  <th className="py-2 text-left font-semibold">What it does</th>
                </tr>
              </thead>
              <tbody className="text-text-muted">
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono text-xs">scan (default)</td>
                  <td className="py-2 text-xs">Run analyzers and return structured findings. Set <code>synthesize: true</code> to also generate LLM reports.</td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono text-xs">report</td>
                  <td className="py-2 text-xs">Read a specific generated report by name (<code>AUDIT_SUMMARY</code>, <code>ARCHITECTURE_ANALYSIS</code>, <code>GAP_ANALYSIS</code>, <code>COMPONENT_INVENTORY</code>, <code>TECH_DEBT_REPORT</code>).</td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono text-xs">refactor</td>
                  <td className="py-2 text-xs">Context-assembly handoff. Pass <code>finding_ids</code> (e.g. <code>["ARCH-1", "QUAL-2"]</code>) and get back the structural trace graph for all affected files, priming the AI for an immediate refactor.</td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono text-xs">verify</td>
                  <td className="py-2 text-xs">Re-run a named subset of <code>analyzers</code> to confirm recent edits actually resolved the finding.</td>
                </tr>
                <tr>
                  <td className="py-2 pr-4 font-mono text-xs">antibodies</td>
                  <td className="py-2 text-xs">List immune-system defenses derived from concept assertions.</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p className="mt-4">
            Findings can also be passed in via the <code>findings</code> parameter to enrich
            external lint output (ruff, eslint, semgrep, SARIF) with structural context — see the{' '}
            <a href="/guides/audit-enrichment" className="text-primary hover:underline">Audit Enrichment guide</a>.
          </p>

          <AnchorHeading id="api" level="h3">REST API</AnchorHeading>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="py-2 pr-4 text-left font-semibold">Method</th>
                  <th className="py-2 pr-4 text-left font-semibold">Endpoint</th>
                  <th className="py-2 text-left font-semibold">Purpose</th>
                </tr>
              </thead>
              <tbody className="text-text-muted">
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono text-xs">POST</td>
                  <td className="py-2 pr-4 font-mono text-xs">/projects/&#123;id&#125;/audit</td>
                  <td className="py-2 text-xs">Trigger audit (Tier 1 + optional Tier 2)</td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono text-xs">GET</td>
                  <td className="py-2 pr-4 font-mono text-xs">/projects/&#123;id&#125;/audit/status</td>
                  <td className="py-2 text-xs">Check progress and last run metadata</td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono text-xs">GET</td>
                  <td className="py-2 pr-4 font-mono text-xs">/projects/&#123;id&#125;/audit/findings</td>
                  <td className="py-2 text-xs">Raw structured findings (filterable)</td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono text-xs">GET</td>
                  <td className="py-2 pr-4 font-mono text-xs">/projects/&#123;id&#125;/audit/reports</td>
                  <td className="py-2 text-xs">List generated report documents</td>
                </tr>
                <tr>
                  <td className="py-2 pr-4 font-mono text-xs">GET</td>
                  <td className="py-2 pr-4 font-mono text-xs">/projects/&#123;id&#125;/audit/report/&#123;name&#125;</td>
                  <td className="py-2 text-xs">Read a specific report</td>
                </tr>
              </tbody>
            </table>
          </div>

          <AnchorHeading id="analyzers" level="h2">Built-in Analyzers</AnchorHeading>
          <p>
            AutoAudit ships with 11 analyzers. Each reads the trace graph and
            produces structured findings — no LLM, no side effects.
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="py-2 pr-4 text-left font-semibold">Analyzer</th>
                  <th className="py-2 pr-4 text-left font-semibold">Category</th>
                  <th className="py-2 text-left font-semibold">What It Finds</th>
                </tr>
              </thead>
              <tbody className="text-text-muted">
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono text-xs">large_files</td>
                  <td className="py-2 pr-4 text-xs">size</td>
                  <td className="py-2 text-xs">Files over configurable line thresholds</td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono text-xs">circular_deps</td>
                  <td className="py-2 pr-4 text-xs">architecture</td>
                  <td className="py-2 text-xs">Import cycles (Tarjan&apos;s SCC algorithm)</td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono text-xs">misplaced_imports</td>
                  <td className="py-2 pr-4 text-xs">architecture</td>
                  <td className="py-2 text-xs">Cross-module dependency bottlenecks</td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono text-xs">hub_bottlenecks</td>
                  <td className="py-2 pr-4 text-xs">architecture</td>
                  <td className="py-2 text-xs">Files with disproportionate fan-in (z-score outliers)</td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono text-xs">dead_code</td>
                  <td className="py-2 pr-4 text-xs">quality</td>
                  <td className="py-2 text-xs">Files with zero importers that aren&apos;t entry points</td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono text-xs">duplicate_logic</td>
                  <td className="py-2 pr-4 text-xs">quality</td>
                  <td className="py-2 text-xs">Files with suspiciously similar summaries (Jaccard)</td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono text-xs">tech_debt</td>
                  <td className="py-2 pr-4 text-xs">quality</td>
                  <td className="py-2 text-xs">Aggregated tech debt from epistemic enrichment</td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono text-xs">staleness</td>
                  <td className="py-2 pr-4 text-xs">quality</td>
                  <td className="py-2 text-xs">Enrichments that are out of date</td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono text-xs">test_coverage</td>
                  <td className="py-2 pr-4 text-xs">testing</td>
                  <td className="py-2 text-xs">Source files with no associated test file</td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono text-xs">naming_consistency</td>
                  <td className="py-2 pr-4 text-xs">naming</td>
                  <td className="py-2 text-xs">Language-specific naming convention violations</td>
                </tr>
                <tr>
                  <td className="py-2 pr-4 font-mono text-xs">api_surface</td>
                  <td className="py-2 pr-4 text-xs">coverage</td>
                  <td className="py-2 text-xs">Public symbols missing docstrings</td>
                </tr>
              </tbody>
            </table>
          </div>

          <AnchorHeading id="reports" level="h2">Generated Reports</AnchorHeading>
          <p>
            When you run an audit with <code>synthesize: true</code> (via the MCP
            <code>prep_audit</code> tool or the REST API), an LLM generates 5 markdown
            documents from the findings:
          </p>
          <ul className="list-disc pl-6 space-y-2">
            <li><strong>AUDIT_SUMMARY</strong> — Health grade (A–F), critical findings, top recommendations</li>
            <li><strong>ARCHITECTURE_ANALYSIS</strong> — Module dependency flow, bottlenecks, boundary violations</li>
            <li><strong>GAP_ANALYSIS</strong> — Misplaced concerns, duplicated logic, missing abstractions</li>
            <li><strong>COMPONENT_INVENTORY</strong> — Every file with purpose, module, summary, in-degree</li>
            <li><strong>TECH_DEBT_REPORT</strong> — Debt items by module with remediation roadmap</li>
          </ul>

          <AnchorHeading id="output-location" level="h2">Output Location</AnchorHeading>
          <p>All audit output is stored inside the project&apos;s index directory:</p>
          <pre className="rounded-lg bg-surface-raised p-4"><code>{`# Standalone mode (default):
~/.local/share/sourceprep/projects/{project-id}/audit/
  ├── findings.json            # Raw structured findings
  ├── audit_manifest.json      # Run metadata (timestamps, counts)
  ├── AUDIT_SUMMARY.md         # LLM-generated (if synthesized)
  ├── ARCHITECTURE_ANALYSIS.md
  ├── GAP_ANALYSIS.md
  ├── COMPONENT_INVENTORY.md
  └── TECH_DEBT_REPORT.md

# Embedded mode:
/path/to/project/.sourceprep/audit/
  └── (same files)`}</code></pre>
          <p>
            These files are also indexed by SourcePrep&apos;s search engine, so you can
            query them via <code>prep_search</code> (e.g., &quot;what tech debt
            exists in the auth module?&quot;).
          </p>

          <AnchorHeading id="settings" level="h2">Settings</AnchorHeading>
          <p>
            Audit behavior is configurable via the dashboard Settings panel or
            the <code>audit_config</code> section in <code>ui_config.json</code>:
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="py-2 pr-4 text-left font-semibold">Setting</th>
                  <th className="py-2 pr-4 text-left font-semibold">Default</th>
                  <th className="py-2 text-left font-semibold">Description</th>
                </tr>
              </thead>
              <tbody className="text-text-muted">
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono text-xs">auto_run_after_deep</td>
                  <td className="py-2 pr-4 text-xs">false</td>
                  <td className="py-2 text-xs">Auto-run Tier 1 after deep enrichment completes</td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono text-xs">auto_synthesize</td>
                  <td className="py-2 pr-4 text-xs">false</td>
                  <td className="py-2 text-xs">Also generate LLM reports when auto-running</td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono text-xs">large_file_threshold_bytes</td>
                  <td className="py-2 pr-4 text-xs">80,000</td>
                  <td className="py-2 text-xs">File size for &quot;critical&quot; severity (~2000 lines)</td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono text-xs">large_file_warning_bytes</td>
                  <td className="py-2 pr-4 text-xs">40,000</td>
                  <td className="py-2 text-xs">File size for &quot;warning&quot; severity (~1000 lines)</td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono text-xs">hub_z_threshold</td>
                  <td className="py-2 pr-4 text-xs">2.0</td>
                  <td className="py-2 text-xs">Z-score for hub bottleneck detection</td>
                </tr>
                <tr>
                  <td className="py-2 pr-4 font-mono text-xs">similarity_threshold</td>
                  <td className="py-2 pr-4 text-xs">0.65</td>
                  <td className="py-2 text-xs">Jaccard threshold for duplicate logic detection</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div className="not-prose">
            <DemoOpportunitiesWithItems />
            <p className="text-xs text-text-subtle italic -mt-4">
              Live preview: Opportunities panel consolidating all improvement items with filters and Pi Agent status.
            </p>
          </div>

          <AnchorHeading id="pipeline-connection" level="h2">Pipeline Connection</AnchorHeading>
          <p>
            AutoAudit is <strong>not</strong> a pipeline stage. It&apos;s an independent
            tool that reads the same data the pipeline writes. The connection:
          </p>
          <ol className="list-decimal pl-6 space-y-2">
            <li>The enrichment pipeline runs to completion and produces trace_nodes, trace_augmented, trace_epistemic, trace_modules, and atlas.json.</li>
            <li>You trigger an audit (via the MCP <code>prep_audit</code> tool, the REST API, or the dashboard Audit panel) when you want insights. The audit reads all that data and produces findings + reports.</li>
            <li>If <code>auto_run_after_deep</code> is enabled, Tier 1 analyzers run automatically when deep enrichment completes.</li>
            <li>Audit reports are indexed by SourcePrep&apos;s search engine and served via MCP, so your AI tools can access them.</li>
          </ol>
        </div>
      </div>
    </main>
  );
}
