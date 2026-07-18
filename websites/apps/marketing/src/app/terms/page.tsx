"use client";

import { Button } from '@prep/ui';

export default function Page() {
  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto max-w-7xl px-6 py-12">

        {/* Top Bar */}
        <div className="flex items-center justify-between border-b border-border pb-6 mb-8">
          <div className="flex items-center gap-4">
             <div className="w-3 h-3 bg-primary rounded-full"></div>
             <span className="font-mono text-sm uppercase tracking-widest text-text-subtle">System_Policy: Terms_v2.0_DRAFT</span>
          </div>
          <a href="/" className="text-sm font-medium text-text-muted hover:text-primary transition-colors">
            ← Return Home
          </a>
        </div>

        {/* Draft Notice */}
        <div className="mb-12 border-2 border-warning bg-warning/10 rounded-sm p-6 flex flex-col sm:flex-row sm:items-center gap-4">
          <span className="font-mono text-xs font-bold uppercase tracking-widest text-warning bg-warning/20 px-3 py-1.5 rounded shrink-0 self-start">
            Draft
          </span>
          <p className="text-base font-semibold text-text">
            Draft — this revision is pending legal review (Phase 144) and is not yet in effect.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12">

          {/* Sidebar Nav (Sticky) */}
          <div className="lg:col-span-3">
            <div className="sticky top-20 space-y-8">
              <div>
                <h1 className="text-4xl font-bold tracking-tight text-text mb-2">Terms of<br/>Service</h1>
                <p className="text-xs font-mono text-text-subtle">DRAFT_UPDATED: 2026-07-17</p>
                <p className="text-xs font-mono text-warning">STATUS: PENDING_LEGAL_REVIEW</p>
              </div>

              <nav className="space-y-1 border-l border-border-subtle">
                {['Overview', 'Licensing', 'Your Data', 'Payments', 'Support', 'Liability', 'Contact'].map((item) => (
                  <a key={item} href={`#${item.toLowerCase().replace(' ', '-')}`} className="block pl-4 py-2 text-sm text-text-muted hover:text-primary hover:border-l-2 hover:border-primary hover:bg-surface transition-all -ml-[1px]">
                    {item}
                  </a>
                ))}
              </nav>

              <div className="pt-8 border-t border-border-subtle">
                <Button asChild variant="outline" className="w-full justify-start text-xs font-mono mb-2">
                  <a href="/security">VIEW_SECURITY_&amp;_PRIVACY</a>
                </Button>
                <Button asChild variant="outline" className="w-full justify-start text-xs font-mono">
                  <a href="mailto:legal@sourceprep.io">CONTACT_LEGAL</a>
                </Button>
              </div>
            </div>
          </div>

          {/* Main Content */}
          <div className="lg:col-span-9">
            <div className="bg-surface border border-border shadow-sm rounded-sm overflow-hidden">

              {/* Header */}
              <div className="bg-surface-raised border-b border-border px-8 py-4 flex justify-between items-center">
                 <span className="font-mono text-xs font-bold text-primary uppercase">Document_Viewer</span>
                 <div className="flex gap-2">
                   <div className="w-2 h-2 rounded-full bg-border-subtle"></div>
                   <div className="w-2 h-2 rounded-full bg-border-subtle"></div>
                 </div>
              </div>

              <div className="p-8 md:p-12 space-y-16">

                <section id="overview">
                  <h2 className="text-xl font-bold text-text mb-4 flex items-center gap-3">
                    <span className="font-mono text-primary text-sm bg-primary/10 px-2 py-1 rounded">01.</span> Overview
                  </h2>
                  <div className="max-w-none">
                    <p className="text-lg leading-relaxed border-l-4 border-border pl-6 py-2 text-text-muted">
                      These Terms of Service (&ldquo;Terms&rdquo;) govern the paid products and
                      related services provided by Magnetic Anomaly LLC &mdash; license keys, signed builds,
                      automatic updates, hosted services, and support. The SourcePrep source code itself
                      is open source under the Apache License 2.0 and is governed by that license, not by
                      these Terms. By purchasing a license or using our services, you agree to these Terms.
                    </p>
                  </div>
                </section>

                <section id="licensing">
                  <h2 className="text-xl font-bold text-text mb-6 flex items-center gap-3">
                    <span className="font-mono text-primary text-sm bg-primary/10 px-2 py-1 rounded">02.</span> Licensing
                  </h2>

                  <div className="space-y-6">
                    <div className="border border-border p-6 rounded-sm">
                       <h3 className="font-bold text-text mb-2">Open-source software</h3>
                       <p className="text-sm text-text-muted">
                         The SourcePrep source code is licensed under the Apache License 2.0.
                         Your use, modification, and redistribution of the software itself are
                         governed by that license, not by these terms.
                       </p>
                    </div>

                    <div className="border border-border p-6 rounded-sm bg-surface-raised">
                       <h3 className="font-bold text-text mb-2">Paid products and services</h3>
                       <p className="text-sm text-text-muted">
                         These terms govern Pro, Teams, and Enterprise: license keys are issued
                         per purchaser and may not be shared or redistributed; signed builds,
                         auto-update, hosted services, and support are provided only to active
                         license holders.
                       </p>
                    </div>

                    <div className="bg-error/10 border border-error/30 p-6 rounded-sm">
                       <h3 className="font-bold text-error mb-2 text-sm uppercase">Restrictions</h3>
                       <p className="text-sm text-text-muted mb-3">
                         License keys may not be shared, resold, or redistributed. The
                         &ldquo;SourcePrep&rdquo; name and logo are trademarks of Magnetic Anomaly LLC;
                         the Apache License 2.0 does not grant trademark rights, and you may not use
                         them to brand a fork or derivative product, or to suggest endorsement by
                         Magnetic Anomaly LLC, without written permission.
                       </p>
                       <p className="text-sm text-text-muted">
                         Nothing in these restrictions limits any right granted to you by the
                         Apache License 2.0 with respect to the source code itself.
                       </p>
                    </div>
                  </div>
                </section>

                <section id="your-data">
                  <h2 className="text-xl font-bold text-text mb-4 flex items-center gap-3">
                    <span className="font-mono text-primary text-sm bg-primary/10 px-2 py-1 rounded">03.</span> Data Sovereignty
                  </h2>
                  <p className="text-sm text-text-muted leading-relaxed">
                    The SourcePrep desktop software processes your source code entirely on your local
                    machine. We do not access, collect, or store your source code, index data, or
                    AI-generated output. Optional hosted services (Teams and Enterprise, when available)
                    will be covered by service-specific data terms.
                    See our <a href="/security#data-collection" className="text-primary underline">Privacy Policy</a> for details.
                  </p>
                </section>

                <section id="payments">
                  <h2 className="text-xl font-bold text-text mb-4 flex items-center gap-3">
                    <span className="font-mono text-primary text-sm bg-primary/10 px-2 py-1 rounded">04.</span> Payments &amp; Refunds
                  </h2>
                   <div className="grid grid-cols-[120px_1fr] gap-4 text-sm text-text-muted border-t border-border pt-4">
                      <span className="font-bold text-text">Status</span>
                      <span>Paid tiers (Pro, Teams, Enterprise) are coming soon and are not yet on sale. No payment is required to use the open-source software.</span>

                      <span className="font-bold text-text">Processor</span>
                      <span>Lemon Squeezy (planned Merchant of Record for paid tiers)</span>

                      <span className="font-bold text-text">Currency</span>
                      <span>USD</span>

                      <span className="font-bold text-text">Refunds</span>
                      <span>Refund terms for paid products will be stated at the time of purchase (<a href="mailto:support@sourceprep.io" className="text-primary underline">support@sourceprep.io</a>)</span>
                   </div>
                </section>

                <section id="support">
                   <h2 className="text-xl font-bold text-text mb-4 flex items-center gap-3">
                    <span className="font-mono text-primary text-sm bg-primary/10 px-2 py-1 rounded">05.</span> Support
                  </h2>
                  <table className="w-full text-sm text-left border border-border">
                    <thead className="bg-surface-raised font-mono text-xs uppercase text-text-subtle">
                      <tr>
                        <th className="px-4 py-2 border-b border-r border-border">Tier</th>
                        <th className="px-4 py-2 border-b border-r border-border">Channel</th>
                        <th className="px-4 py-2 border-b border-border">Response Target</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      <tr>
                        <td className="px-4 py-3 border-r border-border font-medium text-text">Community</td>
                        <td className="px-4 py-3 border-r border-border text-text-muted">GitHub Issues + Discussions</td>
                        <td className="px-4 py-3 text-text-muted">Best-effort, no SLA</td>
                      </tr>
                      <tr>
                        <td className="px-4 py-3 border-r border-border font-medium text-text">Pro</td>
                        <td className="px-4 py-3 border-r border-border text-text-muted">Email (support@sourceprep.io)</td>
                        <td className="px-4 py-3 text-text-muted">5 business days</td>
                      </tr>
                      <tr>
                        <td className="px-4 py-3 border-r border-border font-medium text-text">Teams</td>
                        <td className="px-4 py-3 border-r border-border text-text-muted">Private channel + email</td>
                        <td className="px-4 py-3 text-text-muted">2 business days</td>
                      </tr>
                      <tr>
                        <td className="px-4 py-3 border-r border-border font-medium text-text">Enterprise</td>
                        <td className="px-4 py-3 border-r border-border text-text-muted">Dedicated channel + monthly office hours</td>
                        <td className="px-4 py-3 text-text-muted">Negotiated</td>
                      </tr>
                    </tbody>
                  </table>
                  <p className="text-xs text-text-subtle mt-3">
                    Response targets are goals, not contractual guarantees.
                  </p>
                </section>

                <section id="liability">
                  <h2 className="text-xl font-bold text-text mb-4 flex items-center gap-3">
                    <span className="font-mono text-primary text-sm bg-primary/10 px-2 py-1 rounded">06.</span> Liability &amp; Warranties
                  </h2>
                  <div className="text-sm text-text-subtle bg-surface-raised p-6 border border-border font-mono leading-relaxed">
                    <p className="mb-4">
                      THE SOFTWARE AND SERVICES ARE PROVIDED &quot;AS IS&quot;, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
                    </p>
                    <p>
                      IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
                    </p>
                  </div>
                  <p className="text-xs text-text-subtle mt-3">
                    For the open-source code, the warranty disclaimer and limitation of liability in
                    Sections 7 and 8 of the Apache License 2.0 also apply.
                  </p>
                </section>

                 <section id="contact" className="bg-surface-raised p-6 border border-border rounded-sm">
                  <h2 className="text-sm font-bold text-text mb-2 uppercase tracking-wide">
                    Legal Contact
                  </h2>
                  <p className="text-sm text-text-muted mb-4">
                    For inquiries regarding these terms:
                  </p>
                  <a href="mailto:legal@sourceprep.io" className="font-mono text-primary hover:underline">
                    legal@sourceprep.io
                  </a>
                </section>

              </div>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
