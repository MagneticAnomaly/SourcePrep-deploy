"use client";

import { Button } from '@prep/ui';

export default function Page() {
  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto max-w-7xl px-6 py-12">

        {/* Top Bar */}
        <div className="flex items-center justify-between border-b border-border pb-6 mb-12">
          <div className="flex items-center gap-4">
             <div className="w-3 h-3 bg-error rounded-full animate-pulse"></div>
             <span className="font-mono text-sm uppercase tracking-widest text-text-subtle">System_Policy: Security_v3.1</span>
          </div>
          <a href="/" className="text-sm font-medium text-text-muted hover:text-primary transition-colors">
            ← Return Home
          </a>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12">

          {/* Sidebar Nav (Sticky) */}
          <div className="lg:col-span-3">
            <div className="sticky top-20 space-y-8">
              <div>
                <h1 className="text-4xl font-bold tracking-tight text-text mb-2">Security &amp;<br/>Privacy</h1>
                <p className="text-xs font-mono text-text-subtle">LAST_AUDIT: 2026-02-01</p>
              </div>

              <nav className="space-y-1 border-l border-border-subtle">
                {['Local First', 'Telemetry', 'Network', 'Embedding', 'Licensing', 'Releases', 'Reporting', 'Bug Reports', 'Data Collection', 'Payments', 'Retention'].map((item) => (
                  <a key={item} href={`#${item.toLowerCase().replace(' ', '-')}`} className="block pl-4 py-2 text-sm text-text-muted hover:text-primary hover:border-l-2 hover:border-primary hover:bg-surface transition-all -ml-[1px]">
                    {item}
                  </a>
                ))}
              </nav>

              <div className="pt-8 border-t border-border-subtle">
                <Button asChild variant="outline" className="w-full justify-start text-xs font-mono mb-2">
                  <a href="/terms">VIEW_TERMS_OF_SERVICE</a>
                </Button>
                <Button asChild variant="outline" className="w-full justify-start text-xs font-mono">
                  <a href="mailto:security@sourceprep.io">CONTACT_SEC_TEAM</a>
                </Button>
              </div>
            </div>
          </div>

          {/* Main Content */}
          <div className="lg:col-span-9">
            <div className="bg-surface border border-border shadow-sm rounded-sm overflow-hidden">

              {/* Header */}
              <div className="bg-surface-raised border-b border-border px-8 py-4 flex justify-between items-center">
                 <span className="font-mono text-xs font-bold text-primary uppercase">Architecture_Viewer</span>
                 <div className="flex gap-2">
                   <div className="w-2 h-2 rounded-full bg-border-subtle"></div>
                   <div className="w-2 h-2 rounded-full bg-border-subtle"></div>
                 </div>
              </div>

              <div className="p-8 md:p-12 space-y-16">

                {/* --- SECURITY SECTIONS --- */}

                <section id="local-first">
                  <h2 className="text-xl font-bold text-text mb-4 flex items-center gap-3">
                    <span className="font-mono text-primary text-sm bg-primary/10 px-2 py-1 rounded">01.</span> Local-First Architecture
                  </h2>
                  <div className="max-w-none">
                    <p className="text-lg leading-relaxed border-l-4 border-success pl-6 bg-success/10 py-4 pr-4 text-text">
                      <strong>Assertion:</strong> Your source code never leaves your machine.
                    </p>
                    <p className="mt-4 text-sm text-text-muted">
                      SourcePrep runs entirely on localhost. Indexes, embeddings, and configuration are
                      stored locally in <code className="text-xs bg-background border border-border rounded px-1 py-0.5 font-mono">~/.local/share/sourceprep</code> (or
                      in-project via embedded mode). There is no cloud component, no server-side
                      processing, and no mechanism to upload source code.
                    </p>
                  </div>
                </section>

                <section id="telemetry">
                  <h2 className="text-xl font-bold text-text mb-6 flex items-center gap-3">
                    <span className="font-mono text-primary text-sm bg-primary/10 px-2 py-1 rounded">02.</span> Telemetry &amp; Analytics
                  </h2>

                  <div className="border border-border bg-surface-raised p-6 rounded-sm">
                     <div className="grid grid-cols-[1fr_auto] items-center mb-2">
                       <span className="font-bold text-text">Usage Analytics</span>
                       <span className="font-mono text-xs text-error font-bold uppercase">DISABLED / NONE</span>
                     </div>
                     <div className="grid grid-cols-[1fr_auto] items-center mb-2">
                       <span className="font-bold text-text">Crash Reporting</span>
                       <span className="font-mono text-xs text-error font-bold uppercase">DISABLED / NONE</span>
                     </div>
                     <div className="grid grid-cols-[1fr_auto] items-center">
                       <span className="font-bold text-text">Behavioral Tracking</span>
                       <span className="font-mono text-xs text-error font-bold uppercase">DISABLED / NONE</span>
                     </div>
                  </div>
                </section>

                <section id="network">
                  <h2 className="text-xl font-bold text-text mb-4 flex items-center gap-3">
                    <span className="font-mono text-primary text-sm bg-primary/10 px-2 py-1 rounded">03.</span> Network Isolation
                  </h2>
                  <p className="text-sm text-text-muted mb-4">
                    The SourcePrep daemon binds to <code className="text-xs bg-background border border-border rounded px-1 py-0.5 font-mono">127.0.0.1:8400</code> by default.
                    Remote access requires explicit configuration.
                  </p>
                  <div className="bg-background text-text-muted p-6 font-mono text-sm rounded-sm overflow-x-auto border border-border">
                    <div className="mb-2 text-text-subtle"># Allowed Outbound Connections</div>
                    <div className="grid grid-cols-[120px_1fr] gap-4">
                       <span className="text-success">api.sourceprep.io</span>
                       <span>HTTPS / POST /activate-license (One-time)</span>

                       <span className="text-warning">localhost:*</span>
                       <span>Ollama API (User Controlled / Optional)</span>

                       <span className="text-warning">api.openai...</span>
                       <span>Cloud LLM (User Controlled / BYOK Only)</span>
                    </div>
                  </div>
                </section>

                <section id="llm-usage">
                  <h2 className="text-xl font-bold text-text mb-4 flex items-center gap-3">
                    <span className="font-mono text-primary text-sm bg-primary/10 px-2 py-1 rounded">04.</span> LLM & Embedding Usage
                  </h2>
                  <p className="text-sm text-text-muted leading-relaxed">
                    SourcePrep&apos;s structural code graph (imports, calls, symbol graphs) and semantic search (via built-in ONNX embeddings) work entirely locally without any external LLM. For deep reasoning and trace enrichment, you may bring your own cloud API keys (BYOK) or connect Ollama locally. We never proxy calls, never store keys, and never mark up
                    token costs.
                  </p>
                </section>

                <section id="licensing">
                   <h2 className="text-xl font-bold text-text mb-4 flex items-center gap-3">
                    <span className="font-mono text-primary text-sm bg-primary/10 px-2 py-1 rounded">05.</span> Offline Verification
                  </h2>
                  <p className="text-sm text-text-muted leading-relaxed">
                    License activation requires a single online key exchange. After activation,
                    SourcePrep stores a signed Ed25519 license file locally and verifies it offline.
                    No periodic phone-home, no subscription heartbeat.
                  </p>
                </section>

                <section id="releases">
                   <h2 className="text-xl font-bold text-text mb-4 flex items-center gap-3">
                    <span className="font-mono text-primary text-sm bg-primary/10 px-2 py-1 rounded">06.</span> Supply Chain Security
                  </h2>
                  <p className="text-sm text-text-muted leading-relaxed mb-4">
                    All installers are code-signed and include SHA-256 checksums.
                  </p>
                  <div className="p-4 bg-background border border-border rounded-sm font-mono text-xs text-text-muted">
                    $ shasum -a 256 SourcePrep-1.0.0-mac.dmg<br/>
                    &gt; 7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d90bc
                  </div>
                </section>

                 <section id="reporting" className="bg-surface-raised p-6 border border-border rounded-sm">
                  <h2 className="text-sm font-bold text-text mb-2 uppercase tracking-wide">
                    Vulnerability Reporting
                  </h2>
                  <p className="text-sm text-text-muted mb-4">
                    If you discover a security vulnerability, please report it responsibly. We acknowledge reports within 48 hours.
                  </p>
                  <a href="mailto:security@sourceprep.io" className="font-mono text-primary hover:underline">
                    security@sourceprep.io
                  </a>
                </section>

                <section id="bug-reports">
                  <h2 className="text-xl font-bold text-text mb-4 flex items-center gap-3">
                    <span className="font-mono text-primary text-sm bg-primary/10 px-2 py-1 rounded">07.</span> Bug Reports &amp; Debug Logs
                  </h2>
                  <p className="text-sm text-text-muted leading-relaxed mb-4">
                    SourcePrep includes a one-click bug report feature (accessible from the dashboard log console).
                    When you submit a report, here&apos;s exactly what&apos;s included — and what&apos;s not:
                  </p>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
                    <div className="border border-border bg-surface p-6 rounded-sm">
                      <h3 className="font-mono text-xs font-bold uppercase text-success mb-4 flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full bg-success"></span> Included in Reports
                      </h3>
                      <ul className="space-y-2 text-sm text-text-muted">
                        <li className="flex gap-3"><span className="text-text-subtle font-mono">&#10003;</span> App version &amp; OS info</li>
                        <li className="flex gap-3"><span className="text-text-subtle font-mono">&#10003;</span> Index stats (file count, chunk count)</li>
                        <li className="flex gap-3"><span className="text-text-subtle font-mono">&#10003;</span> Pipeline stage &amp; build status</li>
                        <li className="flex gap-3"><span className="text-text-subtle font-mono">&#10003;</span> Error messages &amp; stack traces</li>
                        <li className="flex gap-3"><span className="text-text-subtle font-mono">&#10003;</span> Your description &amp; steps to reproduce</li>
                      </ul>
                    </div>
                    <div className="border border-border bg-surface-raised p-6 rounded-sm">
                      <h3 className="font-mono text-xs font-bold uppercase text-error mb-4 flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full bg-error"></span> Never Included
                      </h3>
                      <ul className="space-y-2 text-sm text-text-muted">
                        <li className="flex gap-3"><span className="text-text-subtle font-mono">X</span> Source code or file contents</li>
                        <li className="flex gap-3"><span className="text-text-subtle font-mono">X</span> Index embeddings or vectors</li>
                        <li className="flex gap-3"><span className="text-text-subtle font-mono">X</span> File paths beyond project root name</li>
                        <li className="flex gap-3"><span className="text-text-subtle font-mono">X</span> LLM prompts or responses</li>
                        <li className="flex gap-3"><span className="text-text-subtle font-mono">X</span> License keys or credentials</li>
                      </ul>
                    </div>
                  </div>
                  <p className="text-sm text-text-muted leading-relaxed">
                    Bug reports are previewed before submission — you can review every field. If you&apos;re offline
                    or prefer not to send data, the report is saved as a local JSON file you can inspect and
                    email manually to <a href="mailto:support@sourceprep.io" className="text-primary hover:underline">support@sourceprep.io</a>.
                  </p>
                </section>

                {/* --- PRIVACY SECTIONS (merged from /privacy) --- */}

                <div className="border-t-4 border-primary pt-12">
                  <h2 className="text-2xl font-bold text-text mb-2">Privacy Policy</h2>
                  <p className="text-xs font-mono text-text-subtle mb-12">LAST_UPDATED: 2026-02-01</p>

                  <div className="space-y-16">
                    <section id="data-collection">
                      <h2 className="text-xl font-bold text-text mb-6 flex items-center gap-3">
                        <span className="font-mono text-primary text-sm bg-primary/10 px-2 py-1 rounded">08.</span> Data Inventory
                      </h2>
                      <p className="text-lg leading-relaxed border-l-4 border-primary pl-6 bg-primary/10 py-4 pr-4 text-text mb-6">
                        <strong>Executive Summary:</strong> SourcePrep is a local-first desktop application. Your source code never leaves
                        your machine. We collect the absolute minimum data needed to operate the
                        business — license activation and optional support requests. That&apos;s it.
                      </p>

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div className="border border-border bg-surface-raised p-6 rounded-sm">
                           <h3 className="font-mono text-xs font-bold uppercase text-error mb-4 flex items-center gap-2">
                             <span className="w-2 h-2 rounded-full bg-error"></span> Not Collected
                           </h3>
                           <ul className="space-y-3 text-sm text-text-muted">
                             <li className="flex gap-3"><span className="text-text-subtle font-mono">X</span> Source Code &amp; Files</li>
                             <li className="flex gap-3"><span className="text-text-subtle font-mono">X</span> Index Data / Metadata</li>
                             <li className="flex gap-3"><span className="text-text-subtle font-mono">X</span> Telemetry / Usage Stats</li>
                             <li className="flex gap-3"><span className="text-text-subtle font-mono">X</span> AI Prompts / Responses</li>
                           </ul>
                        </div>

                        <div className="border border-border bg-surface p-6 rounded-sm">
                           <h3 className="font-mono text-xs font-bold uppercase text-success mb-4 flex items-center gap-2">
                             <span className="w-2 h-2 rounded-full bg-success"></span> Collected
                           </h3>
                           <ul className="space-y-3 text-sm text-text-muted">
                             <li className="flex gap-3"><span className="text-text-subtle font-mono">&#10003;</span> License Key (Activation)</li>
                             <li className="flex gap-3"><span className="text-text-subtle font-mono">&#10003;</span> Machine ID (Hardware Lock)</li>
                             <li className="flex gap-3"><span className="text-text-subtle font-mono">&#10003;</span> Email (Support/Billing)</li>
                           </ul>
                        </div>
                      </div>
                    </section>

                    <section id="payments">
                      <h2 className="text-xl font-bold text-text mb-4 flex items-center gap-3">
                        <span className="font-mono text-primary text-sm bg-primary/10 px-2 py-1 rounded">09.</span> Payments
                      </h2>
                      <p className="text-sm text-text-muted leading-relaxed">
                        Payments are processed by <strong className="text-text">Lemon Squeezy</strong>, our Merchant of Record.
                        SourcePrep Inc. does not store credit card numbers, banking information, or tax IDs.
                      </p>
                    </section>

                    <section id="retention">
                       <h2 className="text-xl font-bold text-text mb-4 flex items-center gap-3">
                        <span className="font-mono text-primary text-sm bg-primary/10 px-2 py-1 rounded">10.</span> Data Retention
                      </h2>
                      <table className="w-full text-sm text-left border border-border">
                        <thead className="bg-surface-raised font-mono text-xs uppercase text-text-subtle">
                          <tr>
                            <th className="px-4 py-2 border-b border-r border-border">Data Type</th>
                            <th className="px-4 py-2 border-b border-border">Retention Period</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-border">
                          <tr>
                            <td className="px-4 py-3 border-r border-border font-medium text-text">License Records</td>
                            <td className="px-4 py-3 text-text-muted">Lifetime of active license + 2 years</td>
                          </tr>
                          <tr>
                            <td className="px-4 py-3 border-r border-border font-medium text-text">Support Tickets</td>
                            <td className="px-4 py-3 text-text-muted">2 years from closure</td>
                          </tr>
                          <tr>
                            <td className="px-4 py-3 border-r border-border font-medium text-text">Server Logs</td>
                            <td className="px-4 py-3 text-text-muted">30 days (rolling)</td>
                          </tr>
                        </tbody>
                      </table>
                    </section>

                    <section className="bg-surface-raised p-6 border border-border rounded-sm">
                      <h2 className="text-sm font-bold text-text mb-2 uppercase tracking-wide">
                        Compliance Officer
                      </h2>
                      <p className="text-sm text-text-muted mb-4">
                        For data deletion requests or GDPR/CCPA inquiries:
                      </p>
                      <a href="mailto:privacy@sourceprep.io" className="font-mono text-primary hover:underline">
                        privacy@sourceprep.io
                      </a>
                    </section>
                  </div>
                </div>

              </div>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
