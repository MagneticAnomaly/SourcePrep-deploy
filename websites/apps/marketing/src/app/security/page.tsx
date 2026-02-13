"use client";

import { Button } from '@codrag/ui';

export default function Page() {
  return (
    <main className="min-h-screen bg-slate-50 text-slate-900 font-ibm-sans selection:bg-blue-600 selection:text-white">
      {/* Enterprise Console / Systems Posture */}
      <div className="mx-auto max-w-7xl px-6 py-12">
        
        {/* Top Bar */}
        <div className="flex items-center justify-between border-b border-slate-300 pb-6 mb-12">
          <div className="flex items-center gap-4">
             <div className="w-3 h-3 bg-red-500 rounded-full animate-pulse"></div>
             <span className="font-ibm-mono text-sm uppercase tracking-widest text-slate-500">System_Policy: Security_v3.1</span>
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
                <h1 className="text-3xl font-bold tracking-tight text-slate-900 mb-2">Security &<br/>Privacy</h1>
                <p className="text-xs font-ibm-mono text-slate-500">LAST_AUDIT: 2026-02-01</p>
              </div>
              
              <nav className="space-y-1 border-l border-slate-200">
                {['Local First', 'Telemetry', 'Network', 'Embedding', 'Licensing', 'Releases', 'Reporting'].map((item) => (
                  <a key={item} href={`#${item.toLowerCase().replace(' ', '-')}`} className="block pl-4 py-2 text-sm text-slate-500 hover:text-blue-600 hover:border-l-2 hover:border-blue-600 hover:bg-slate-100 transition-all -ml-[1px]">
                    {item}
                  </a>
                ))}
              </nav>

              <div className="pt-8 border-t border-slate-200">
                <Button asChild variant="outline" className="w-full justify-start text-xs font-ibm-mono mb-2">
                  <a href="/privacy">VIEW_PRIVACY_POLICY</a>
                </Button>
                <Button asChild variant="outline" className="w-full justify-start text-xs font-ibm-mono">
                  <a href="mailto:security@codrag.io">CONTACT_SEC_TEAM</a>
                </Button>
              </div>
            </div>
          </div>

          {/* Main Content (Dense) */}
          <div className="lg:col-span-9">
            <div className="bg-white border border-slate-200 shadow-sm rounded-sm overflow-hidden">
              
              {/* Header */}
              <div className="bg-slate-100 border-b border-slate-200 px-8 py-4 flex justify-between items-center">
                 <span className="font-ibm-mono text-xs font-bold text-slate-500 uppercase">Architecture_Viewer</span>
                 <div className="flex gap-2">
                   <div className="w-2 h-2 rounded-full bg-slate-300"></div>
                   <div className="w-2 h-2 rounded-full bg-slate-300"></div>
                 </div>
              </div>

              <div className="p-8 md:p-12 space-y-16">
                
                <section id="local-first">
                  <h2 className="text-xl font-bold text-slate-900 mb-4 flex items-center gap-3">
                    <span className="font-ibm-mono text-blue-600 text-sm">01.</span> Local-First Architecture
                  </h2>
                  <div className="prose prose max-w-none text-slate-600">
                    <p className="text-lg leading-relaxed border-l-4 border-green-500 pl-6 bg-green-50 py-4 pr-4 text-green-900">
                      <strong>Assertion:</strong> Your source code never leaves your machine.
                    </p>
                    <p className="mt-4 text-sm">
                      CoDRAG runs entirely on localhost. Indexes, embeddings, and configuration are
                      stored locally in <code className="text-xs bg-slate-100 border border-slate-300 px-1 py-0.5 rounded font-ibm-mono text-slate-800">~/.local/share/codrag</code> (or
                      in-project via embedded mode). There is no cloud component, no server-side
                      processing, and no mechanism to upload source code.
                    </p>
                  </div>
                </section>

                <section id="telemetry">
                  <h2 className="text-xl font-bold text-slate-900 mb-6 flex items-center gap-3">
                    <span className="font-ibm-mono text-blue-600 text-sm">02.</span> Telemetry & Analytics
                  </h2>
                  
                  <div className="border border-slate-200 bg-slate-50 p-6 rounded-sm">
                     <div className="grid grid-cols-[1fr_auto] items-center mb-2">
                       <span className="font-bold text-slate-900">Usage Analytics</span>
                       <span className="font-ibm-mono text-xs text-red-600 font-bold uppercase">DISABLED / NONE</span>
                     </div>
                     <div className="grid grid-cols-[1fr_auto] items-center mb-2">
                       <span className="font-bold text-slate-900">Crash Reporting</span>
                       <span className="font-ibm-mono text-xs text-red-600 font-bold uppercase">DISABLED / NONE</span>
                     </div>
                     <div className="grid grid-cols-[1fr_auto] items-center">
                       <span className="font-bold text-slate-900">Behavioral Tracking</span>
                       <span className="font-ibm-mono text-xs text-red-600 font-bold uppercase">DISABLED / NONE</span>
                     </div>
                  </div>
                </section>

                <section id="network">
                  <h2 className="text-xl font-bold text-slate-900 mb-4 flex items-center gap-3">
                    <span className="font-ibm-mono text-blue-600 text-sm">03.</span> Network Isolation
                  </h2>
                  <p className="text-sm text-slate-600 mb-4">
                    The CoDRAG daemon binds to <code className="text-xs bg-slate-100 border border-slate-300 px-1 py-0.5 rounded font-ibm-mono">127.0.0.1:8400</code> by default. 
                    Remote access requires explicit configuration.
                  </p>
                  <div className="bg-slate-900 text-slate-300 p-6 font-ibm-mono text-sm rounded-sm overflow-x-auto">
                    <div className="mb-2 text-slate-500"># Allowed Outbound Connections</div>
                    <div className="grid grid-cols-[120px_1fr] gap-4">
                       <span className="text-green-400">api.codrag.io</span>
                       <span>HTTPS / POST /activate-license (One-time)</span>
                       
                       <span className="text-yellow-400">localhost:*</span>
                       <span>Ollama API (User Controlled / Optional)</span>
                       
                       <span className="text-yellow-400">api.openai...</span>
                       <span>Cloud LLM (User Controlled / BYOK Only)</span>
                    </div>
                  </div>
                </section>

                <section id="embedding">
                  <h2 className="text-xl font-bold text-slate-900 mb-4 flex items-center gap-3">
                    <span className="font-ibm-mono text-blue-600 text-sm">04.</span> Flexible Embedding
                  </h2>
                  <p className="text-sm text-slate-600 leading-relaxed">
                    CoDRAG&apos;s structural code graph (imports, calls, symbol graphs) works entirely
                    without any LLM. For optional semantic embeddings, you may connect Ollama locally or bring
                    your own cloud API keys. We never proxy calls, never store keys, and never mark up
                    token costs.
                  </p>
                </section>

                <section id="licensing">
                   <h2 className="text-xl font-bold text-slate-900 mb-4 flex items-center gap-3">
                    <span className="font-ibm-mono text-blue-600 text-sm">05.</span> Offline Verification
                  </h2>
                  <p className="text-sm text-slate-600 leading-relaxed">
                    License activation requires a single online key exchange. After activation,
                    CoDRAG stores a signed Ed25519 license file locally and verifies it offline.
                    No periodic phone-home, no subscription heartbeat.
                  </p>
                </section>

                <section id="releases">
                   <h2 className="text-xl font-bold text-slate-900 mb-4 flex items-center gap-3">
                    <span className="font-ibm-mono text-blue-600 text-sm">06.</span> Supply Chain Security
                  </h2>
                  <p className="text-sm text-slate-600 leading-relaxed mb-4">
                    All installers are code-signed and include SHA-256 checksums.
                  </p>
                  <div className="p-4 bg-slate-50 border border-slate-200 rounded-sm font-ibm-mono text-xs text-slate-600">
                    $ shasum -a 256 CoDRAG-1.0.0-mac.dmg<br/>
                    &gt; 7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d90bc
                  </div>
                </section>
                
                 <section id="reporting" className="bg-slate-50 p-6 border border-slate-200 rounded-sm">
                  <h2 className="text-sm font-bold text-slate-900 mb-2 uppercase tracking-wide">
                    Vulnerability Reporting
                  </h2>
                  <p className="text-sm text-slate-600 mb-4">
                    If you discover a security vulnerability, please report it responsibly. We acknowledge reports within 48 hours.
                  </p>
                  <a href="mailto:security@codrag.io" className="font-ibm-mono text-blue-600 hover:underline">
                    security@codrag.io
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
