"use client";

import { Button } from '@codrag/ui';

export default function Page() {
  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto max-w-7xl px-6 py-12">

        {/* Top Bar */}
        <div className="flex items-center justify-between border-b border-border pb-6 mb-12">
          <div className="flex items-center gap-4">
             <div className="w-3 h-3 bg-primary rounded-full"></div>
             <span className="font-mono text-sm uppercase tracking-widest text-text-subtle">System_Policy: Terms_v1.0</span>
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
                <h1 className="text-4xl font-bold tracking-tight text-text mb-2">Terms of<br/>Service</h1>
                <p className="text-xs font-mono text-text-subtle">LAST_UPDATED: 2026-02-01</p>
              </div>

              <nav className="space-y-1 border-l border-border-subtle">
                {['Overview', 'License Grant', 'Your Data', 'Payments', 'Support', 'Liability', 'Contact'].map((item) => (
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
                  <a href="mailto:legal@codrag.io">CONTACT_LEGAL</a>
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
                      These Terms of Service (&ldquo;Terms&rdquo;) govern your use of CoDRAG software
                      and related services provided by CoDRAG Inc. By downloading, installing, or using CoDRAG, you agree to these Terms.
                    </p>
                  </div>
                </section>

                <section id="license-grant">
                  <h2 className="text-xl font-bold text-text mb-6 flex items-center gap-3">
                    <span className="font-mono text-primary text-sm bg-primary/10 px-2 py-1 rounded">02.</span> License Grant
                  </h2>

                  <div className="space-y-6">
                    <div className="border border-border p-6 rounded-sm">
                       <h3 className="font-bold text-text mb-2">Free Tier</h3>
                       <p className="text-sm text-text-muted">
                         Provided at no cost for personal/commercial use. Includes up to three active projects with all features.
                       </p>
                    </div>

                    <div className="border border-border p-6 rounded-sm bg-surface-raised">
                       <h3 className="font-bold text-text mb-2">Paid Licenses (Pro / Team)</h3>
                       <p className="text-sm text-text-muted mb-4">
                         Grants non-exclusive, non-transferable right to use CoDRAG on specified number of machines.
                       </p>
                       <ul className="space-y-2 text-xs font-mono text-text-subtle">
                         <li>- Pro (one-time): Perpetual license, does not expire.</li>
                         <li>- Pro (monthly) / Team: Subscription, active while paid.</li>
                       </ul>
                    </div>

                    <div className="bg-error/10 border border-error/30 p-6 rounded-sm">
                       <h3 className="font-bold text-error mb-2 text-sm uppercase">Restrictions</h3>
                       <p className="text-sm text-text-muted">
                         You may not reverse-engineer, decompile, or disassemble the software. You may not redistribute license keys.
                       </p>
                    </div>
                  </div>
                </section>

                <section id="your-data">
                  <h2 className="text-xl font-bold text-text mb-4 flex items-center gap-3">
                    <span className="font-mono text-primary text-sm bg-primary/10 px-2 py-1 rounded">03.</span> Data Sovereignty
                  </h2>
                  <p className="text-sm text-text-muted leading-relaxed">
                    CoDRAG processes your source code entirely on your local machine. We do not
                    access, collect, or store your source code, index data, or AI-generated output.
                    See our <a href="/security#data-collection" className="text-primary underline">Privacy Policy</a> for details.
                  </p>
                </section>

                <section id="payments">
                  <h2 className="text-xl font-bold text-text mb-4 flex items-center gap-3">
                    <span className="font-mono text-primary text-sm bg-primary/10 px-2 py-1 rounded">04.</span> Payments &amp; Refunds
                  </h2>
                   <div className="grid grid-cols-[120px_1fr] gap-4 text-sm text-text-muted border-t border-border pt-4">
                      <span className="font-bold text-text">Processor</span>
                      <span>Lemon Squeezy (Merchant of Record)</span>

                      <span className="font-bold text-text">Currency</span>
                      <span>USD</span>

                      <span className="font-bold text-text">Refunds</span>
                      <span>14-day money-back guarantee (<a href="mailto:support@codrag.io" className="text-primary underline">support@codrag.io</a>)</span>
                   </div>
                </section>

                <section id="support">
                   <h2 className="text-xl font-bold text-text mb-4 flex items-center gap-3">
                    <span className="font-mono text-primary text-sm bg-primary/10 px-2 py-1 rounded">05.</span> Support SLA
                  </h2>
                  <table className="w-full text-sm text-left border border-border">
                    <thead className="bg-surface-raised font-mono text-xs uppercase text-text-subtle">
                      <tr>
                        <th className="px-4 py-2 border-b border-r border-border">Tier</th>
                        <th className="px-4 py-2 border-b border-border">Channel</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      <tr>
                        <td className="px-4 py-3 border-r border-border font-medium text-text">Free</td>
                        <td className="px-4 py-3 text-text-muted">Community (GitHub Discussions)</td>
                      </tr>
                      <tr>
                        <td className="px-4 py-3 border-r border-border font-medium text-text">Pro / Team</td>
                        <td className="px-4 py-3 text-text-muted">Private Email (support@codrag.io)</td>
                      </tr>
                      <tr>
                        <td className="px-4 py-3 border-r border-border font-medium text-text">Enterprise</td>
                        <td className="px-4 py-3 text-text-muted">Priority SLA + Dedicated Account Mgr</td>
                      </tr>
                    </tbody>
                  </table>
                </section>

                <section id="liability">
                  <h2 className="text-xl font-bold text-text mb-4 flex items-center gap-3">
                    <span className="font-mono text-primary text-sm bg-primary/10 px-2 py-1 rounded">06.</span> Liability &amp; Warranties
                  </h2>
                  <div className="text-sm text-text-subtle bg-surface-raised p-6 border border-border font-mono leading-relaxed">
                    <p className="mb-4">
                      THE SOFTWARE IS PROVIDED &quot;AS IS&quot;, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
                    </p>
                    <p>
                      IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
                    </p>
                  </div>
                </section>

                 <section id="contact" className="bg-surface-raised p-6 border border-border rounded-sm">
                  <h2 className="text-sm font-bold text-text mb-2 uppercase tracking-wide">
                    Legal Contact
                  </h2>
                  <p className="text-sm text-text-muted mb-4">
                    For inquiries regarding these terms:
                  </p>
                  <a href="mailto:legal@codrag.io" className="font-mono text-primary hover:underline">
                    legal@codrag.io
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
