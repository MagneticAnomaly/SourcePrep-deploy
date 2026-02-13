"use client";

import { Button } from '@codrag/ui';

export default function Page() {
  return (
    <main className="min-h-screen bg-slate-50 text-slate-900 font-sans selection:bg-blue-600 selection:text-white">
      {/* Enterprise Console / Systems Posture */}
      <div className="mx-auto max-w-7xl px-6 py-12">
        
        {/* Top Bar */}
        <div className="flex items-center justify-between border-b border-slate-300 pb-6 mb-12">
          <div className="flex items-center gap-4">
             <div className="w-3 h-3 bg-blue-500 rounded-full"></div>
             <span className="font-mono text-sm uppercase tracking-widest text-slate-500">System_Policy: Terms_v1.0</span>
          </div>
          <a href="/" className="text-sm font-medium text-slate-600 hover:text-blue-600 transition-colors">
            ← ESC / Return Home
          </a>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12">
          
          {/* Sidebar Nav (Sticky) */}
          <div className="lg:col-span-3">
            <div className="sticky top-12 space-y-8">
              <div>
                <h1 className="text-3xl font-bold tracking-tight text-slate-900 mb-2">Terms of<br/>Service</h1>
                <p className="text-xs font-mono text-slate-500">LAST_UPDATED: 2026-02-01</p>
              </div>
              
              <nav className="space-y-1 border-l border-slate-200">
                {['Overview', 'License Grant', 'Your Data', 'Payments', 'Support', 'Liability', 'Contact'].map((item) => (
                  <a key={item} href={`#${item.toLowerCase().replace(' ', '-')}`} className="block pl-4 py-2 text-sm text-slate-500 hover:text-blue-600 hover:border-l-2 hover:border-blue-600 hover:bg-slate-100 transition-all -ml-[1px]">
                    {item}
                  </a>
                ))}
              </nav>

              <div className="pt-8 border-t border-slate-200">
                <Button asChild variant="outline" className="w-full justify-start text-xs font-mono mb-2">
                  <a href="/privacy">VIEW_PRIVACY_POLICY</a>
                </Button>
                <Button asChild variant="outline" className="w-full justify-start text-xs font-mono">
                  <a href="/security">VIEW_SECURITY_AUDIT</a>
                </Button>
              </div>
            </div>
          </div>

          {/* Main Content (Dense) */}
          <div className="lg:col-span-9">
            <div className="bg-white border border-slate-200 shadow-sm rounded-sm overflow-hidden">
              
              {/* Header */}
              <div className="bg-slate-100 border-b border-slate-200 px-8 py-4 flex justify-between items-center">
                 <span className="font-mono text-xs font-bold text-slate-500 uppercase">Document_Viewer</span>
                 <div className="flex gap-2">
                   <div className="w-2 h-2 rounded-full bg-slate-300"></div>
                   <div className="w-2 h-2 rounded-full bg-slate-300"></div>
                 </div>
              </div>

              <div className="p-8 md:p-12 space-y-16">
                
                <section id="overview">
                  <h2 className="text-xl font-bold text-slate-900 mb-4 flex items-center gap-3">
                    <span className="font-mono text-blue-600 text-sm">01.</span> Overview
                  </h2>
                  <div className="prose prose max-w-none text-slate-600">
                    <p className="text-lg leading-relaxed border-l-4 border-slate-300 pl-6 py-2">
                      These Terms of Service (&ldquo;Terms&rdquo;) govern your use of CoDRAG software
                      and related services provided by CoDRAG Inc. By downloading, installing, or using CoDRAG, you agree to these Terms.
                    </p>
                  </div>
                </section>

                <section id="license-grant">
                  <h2 className="text-xl font-bold text-slate-900 mb-6 flex items-center gap-3">
                    <span className="font-mono text-blue-600 text-sm">02.</span> License Grant
                  </h2>
                  
                  <div className="space-y-6">
                    <div className="border border-slate-200 p-6 rounded-sm">
                       <h3 className="font-bold text-slate-900 mb-2">Free Tier</h3>
                       <p className="text-sm text-slate-600">
                         Provided at no cost for personal/commercial use. Limited to one active project with manual indexing.
                       </p>
                    </div>

                    <div className="border border-slate-200 p-6 rounded-sm bg-slate-50">
                       <h3 className="font-bold text-slate-900 mb-2">Paid Licenses (Starter / Pro / Team)</h3>
                       <p className="text-sm text-slate-600 mb-4">
                         Grants non-exclusive, non-transferable right to use CoDRAG on specified number of machines.
                       </p>
                       <ul className="space-y-2 text-xs font-mono text-slate-500">
                         <li>- Pro: Perpetual license (does not expire).</li>
                         <li>- Starter/Team: Time-limited subscription.</li>
                       </ul>
                    </div>

                    <div className="bg-red-50 border border-red-100 p-6 rounded-sm">
                       <h3 className="font-bold text-red-900 mb-2 text-sm uppercase">Restrictions</h3>
                       <p className="text-sm text-red-800">
                         You may not reverse-engineer, decompile, or disassemble the software. You may not redistribute license keys.
                       </p>
                    </div>
                  </div>
                </section>

                <section id="your-data">
                  <h2 className="text-xl font-bold text-slate-900 mb-4 flex items-center gap-3">
                    <span className="font-mono text-blue-600 text-sm">03.</span> Data Sovereignty
                  </h2>
                  <p className="text-sm text-slate-600 leading-relaxed">
                    CoDRAG processes your source code entirely on your local machine. We do not
                    access, collect, or store your source code, index data, or AI-generated output.
                    See our <a href="/privacy" className="text-blue-600 underline">Privacy Policy</a> for details.
                  </p>
                </section>

                <section id="payments">
                  <h2 className="text-xl font-bold text-slate-900 mb-4 flex items-center gap-3">
                    <span className="font-mono text-blue-600 text-sm">04.</span> Payments & Refunds
                  </h2>
                   <div className="grid grid-cols-[120px_1fr] gap-4 text-sm text-slate-600 border-t border-slate-200 pt-4">
                      <span className="font-bold">Processor</span>
                      <span>Lemon Squeezy (Merchant of Record)</span>
                      
                      <span className="font-bold">Currency</span>
                      <span>USD</span>
                      
                      <span className="font-bold">Refunds</span>
                      <span>14-day money-back guarantee (<a href="mailto:support@codrag.io" className="text-blue-600 underline">support@codrag.io</a>)</span>
                   </div>
                </section>

                <section id="support">
                   <h2 className="text-xl font-bold text-slate-900 mb-4 flex items-center gap-3">
                    <span className="font-mono text-blue-600 text-sm">05.</span> Support SLA
                  </h2>
                  <table className="w-full text-sm text-left border border-slate-200">
                    <thead className="bg-slate-50 font-mono text-xs uppercase text-slate-500">
                      <tr>
                        <th className="px-4 py-2 border-b border-r border-slate-200">Tier</th>
                        <th className="px-4 py-2 border-b border-slate-200">Channel</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200">
                      <tr>
                        <td className="px-4 py-3 border-r border-slate-200 font-medium">Free</td>
                        <td className="px-4 py-3 text-slate-600">Community (GitHub Discussions)</td>
                      </tr>
                      <tr>
                        <td className="px-4 py-3 border-r border-slate-200 font-medium">Pro / Team</td>
                        <td className="px-4 py-3 text-slate-600">Private Email (support@codrag.io)</td>
                      </tr>
                      <tr>
                        <td className="px-4 py-3 border-r border-slate-200 font-medium">Enterprise</td>
                        <td className="px-4 py-3 text-slate-600">Priority SLA + Dedicated Account Mgr</td>
                      </tr>
                    </tbody>
                  </table>
                </section>

                <section id="liability">
                  <h2 className="text-xl font-bold text-slate-900 mb-4 flex items-center gap-3">
                    <span className="font-mono text-blue-600 text-sm">06.</span> Liability & Warranties
                  </h2>
                  <div className="text-sm text-slate-500 bg-slate-50 p-6 border border-slate-200 font-mono leading-relaxed">
                    <p className="mb-4">
                      THE SOFTWARE IS PROVIDED &quot;AS IS&quot;, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
                    </p>
                    <p>
                      IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
                    </p>
                  </div>
                </section>
                
                 <section id="contact" className="bg-slate-50 p-6 border border-slate-200 rounded-sm">
                  <h2 className="text-sm font-bold text-slate-900 mb-2 uppercase tracking-wide">
                    Legal Contact
                  </h2>
                  <p className="text-sm text-slate-600 mb-4">
                    For inquiries regarding these terms:
                  </p>
                  <a href="mailto:legal@codrag.io" className="font-mono text-blue-600 hover:underline">
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
