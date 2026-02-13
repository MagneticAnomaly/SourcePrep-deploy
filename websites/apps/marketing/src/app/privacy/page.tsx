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
             <div className="w-3 h-3 bg-green-500 rounded-full"></div>
             <span className="font-mono text-sm uppercase tracking-widest text-slate-500">System_Policy: Privacy_v2.0</span>
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
                <h1 className="text-3xl font-bold tracking-tight text-slate-900 mb-2">Privacy<br/>Policy</h1>
                <p className="text-xs font-mono text-slate-500">LAST_UPDATED: 2026-02-01</p>
              </div>
              
              <nav className="space-y-1 border-l border-slate-200">
                {['Summary', 'Data Collection', 'Network', 'Payments', 'Retention', 'Contact'].map((item) => (
                  <a key={item} href={`#${item.toLowerCase().replace(' ', '-')}`} className="block pl-4 py-2 text-sm text-slate-500 hover:text-blue-600 hover:border-l-2 hover:border-blue-600 hover:bg-slate-100 transition-all -ml-[1px]">
                    {item}
                  </a>
                ))}
              </nav>

              <div className="pt-8 border-t border-slate-200">
                <Button asChild variant="outline" className="w-full justify-start text-xs font-mono mb-2">
                  <a href="/terms">VIEW_TERMS_OF_SERVICE</a>
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
                
                <section id="summary">
                  <h2 className="text-xl font-bold text-slate-900 mb-4 flex items-center gap-3">
                    <span className="font-mono text-blue-600 text-sm">01.</span> Summary
                  </h2>
                  <div className="prose prose max-w-none text-slate-600">
                    <p className="text-lg leading-relaxed border-l-4 border-blue-600 pl-6 bg-blue-50 py-4 pr-4">
                      <strong>Executive Summary:</strong> CoDRAG is a local-first desktop application. Your source code never leaves
                      your machine. We collect the absolute minimum data needed to operate the
                      business — license activation and optional support requests. That&apos;s it.
                    </p>
                  </div>
                </section>

                <section id="data-collection">
                  <h2 className="text-xl font-bold text-slate-900 mb-6 flex items-center gap-3">
                    <span className="font-mono text-blue-600 text-sm">02.</span> Data Inventory
                  </h2>
                  
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    {/* NOT Collected */}
                    <div className="border border-slate-200 bg-slate-50 p-6 rounded-sm">
                       <h3 className="font-mono text-xs font-bold uppercase text-red-600 mb-4 flex items-center gap-2">
                         <span className="w-2 h-2 rounded-full bg-red-600"></span> Not Collected
                       </h3>
                       <ul className="space-y-3 text-sm text-slate-600">
                         <li className="flex gap-3">
                           <span className="text-slate-400 font-mono">X</span> Source Code & Files
                         </li>
                         <li className="flex gap-3">
                           <span className="text-slate-400 font-mono">X</span> Index Data / Metadata
                         </li>
                         <li className="flex gap-3">
                           <span className="text-slate-400 font-mono">X</span> Telemetry / Usage Stats
                         </li>
                         <li className="flex gap-3">
                           <span className="text-slate-400 font-mono">X</span> AI Prompts / Responses
                         </li>
                       </ul>
                    </div>

                    {/* Collected */}
                    <div className="border border-slate-200 bg-white p-6 rounded-sm">
                       <h3 className="font-mono text-xs font-bold uppercase text-green-600 mb-4 flex items-center gap-2">
                         <span className="w-2 h-2 rounded-full bg-green-600"></span> Collected
                       </h3>
                       <ul className="space-y-3 text-sm text-slate-600">
                         <li className="flex gap-3">
                           <span className="text-slate-400 font-mono">✓</span> License Key (Activation)
                         </li>
                         <li className="flex gap-3">
                           <span className="text-slate-400 font-mono">✓</span> Machine ID (Hardware Lock)
                         </li>
                         <li className="flex gap-3">
                           <span className="text-slate-400 font-mono">✓</span> Email (Support/Billing)
                         </li>
                       </ul>
                    </div>
                  </div>
                </section>

                <section id="network">
                  <h2 className="text-xl font-bold text-slate-900 mb-4 flex items-center gap-3">
                    <span className="font-mono text-blue-600 text-sm">03.</span> Network Topology
                  </h2>
                  <div className="bg-slate-900 text-slate-300 p-6 font-mono text-sm rounded-sm overflow-x-auto">
                    <div className="mb-2 text-slate-500"># Outbound Connections</div>
                    <div className="grid grid-cols-[120px_1fr] gap-4">
                       <span className="text-green-400">api.codrag.io</span>
                       <span>HTTPS / POST /activate-license (One-time)</span>
                       
                       <span className="text-yellow-400">localhost:*</span>
                       <span>Ollama API (User Controlled / Optional)</span>
                       
                       <span className="text-yellow-400">api.openai...</span>
                       <span>Cloud LLM (User Controlled / BYOK Only)</span>
                    </div>
                  </div>
                  <p className="mt-4 text-sm text-slate-600">
                    All network connections (except license activation) are user-initiated and configurable. 
                    The application is fully functional in air-gapped environments after offline license installation.
                  </p>
                </section>

                <section id="payments">
                  <h2 className="text-xl font-bold text-slate-900 mb-4 flex items-center gap-3">
                    <span className="font-mono text-blue-600 text-sm">04.</span> Payments
                  </h2>
                  <p className="text-sm text-slate-600 leading-relaxed mb-4">
                    Payments are processed by <strong>Lemon Squeezy</strong>, our Merchant of Record. 
                    CoDRAG Inc. does not store credit card numbers, banking information, or tax IDs.
                  </p>
                </section>

                <section id="retention">
                   <h2 className="text-xl font-bold text-slate-900 mb-4 flex items-center gap-3">
                    <span className="font-mono text-blue-600 text-sm">05.</span> Data Retention
                  </h2>
                  <table className="w-full text-sm text-left border border-slate-200">
                    <thead className="bg-slate-50 font-mono text-xs uppercase text-slate-500">
                      <tr>
                        <th className="px-4 py-2 border-b border-r border-slate-200">Data Type</th>
                        <th className="px-4 py-2 border-b border-slate-200">Retention Period</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200">
                      <tr>
                        <td className="px-4 py-3 border-r border-slate-200 font-medium">License Records</td>
                        <td className="px-4 py-3 text-slate-600">Lifetime of active license + 2 years</td>
                      </tr>
                      <tr>
                        <td className="px-4 py-3 border-r border-slate-200 font-medium">Support Tickets</td>
                        <td className="px-4 py-3 text-slate-600">2 years from closure</td>
                      </tr>
                      <tr>
                        <td className="px-4 py-3 border-r border-slate-200 font-medium">Server Logs</td>
                        <td className="px-4 py-3 text-slate-600">30 days (rolling)</td>
                      </tr>
                    </tbody>
                  </table>
                </section>
                
                 <section id="contact" className="bg-slate-50 p-6 border border-slate-200 rounded-sm">
                  <h2 className="text-sm font-bold text-slate-900 mb-2 uppercase tracking-wide">
                    Compliance Officer
                  </h2>
                  <p className="text-sm text-slate-600 mb-4">
                    For data deletion requests or GDPR/CCPA inquiries:
                  </p>
                  <a href="mailto:privacy@codrag.io" className="font-mono text-blue-600 hover:underline">
                    privacy@codrag.io
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
