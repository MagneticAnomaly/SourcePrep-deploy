"use client";

import { Button } from '@codrag/ui';

const RELEASES_URL =
  process.env.NEXT_PUBLIC_CODRAG_RELEASES_URL ??
  'https://github.com/EricBintner/CoDRAG/releases';

export default function Page() {
  return (
    <main className="min-h-screen bg-white text-black font-sans selection:bg-blue-600 selection:text-white">
      {/* Inclusive Focus / Direction K */}
      <div className="mx-auto max-w-7xl px-6 py-24">
        
        {/* Nav */}
        <a href="/" className="inline-flex items-center text-lg font-medium text-slate-600 hover:text-blue-700 hover:underline underline-offset-4 transition-colors mb-16 h-12">
          ← Return Home
        </a>

        <div className="max-w-4xl">
          <h1 className="text-5xl md:text-7xl font-bold tracking-tight text-slate-900 mb-8">
            Download CoDRAG.
          </h1>
          <p className="text-2xl md:text-3xl text-slate-700 leading-normal mb-12 max-w-3xl">
            The Rust-powered context layer for your code.
            <br />
            <span className="text-slate-500">Free to start. 100% Local. No cloud required.</span>
          </p>
        </div>

        {/* Primary Actions - Large Targets */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-24">
          <a 
            href={RELEASES_URL}
            className="group flex flex-col p-10 rounded-[2rem] bg-blue-600 text-white hover:bg-blue-700 hover:scale-[1.01] transition-all shadow-xl hover:shadow-2xl focus:ring-4 focus:ring-blue-300 focus:outline-none"
          >
            <div className="text-lg font-bold uppercase tracking-wider opacity-80 mb-2">For macOS</div>
            <div className="text-4xl font-bold mb-4">Download for Mac</div>
            <div className="text-blue-100 text-lg mb-8">macOS 11+ (Apple Silicon & Intel)</div>
            <div className="mt-auto flex items-center font-bold text-xl bg-white text-blue-600 px-8 py-4 rounded-full w-fit group-hover:bg-blue-50 transition-colors">
              Download .dmg ↓
            </div>
          </a>

          <a 
            href={RELEASES_URL}
            className="group flex flex-col p-10 rounded-[2rem] bg-slate-100 text-slate-900 border-2 border-slate-200 hover:border-slate-300 hover:bg-slate-200 hover:scale-[1.01] transition-all focus:ring-4 focus:ring-slate-300 focus:outline-none"
          >
            <div className="text-lg font-bold uppercase tracking-wider text-slate-500 mb-2">For Windows</div>
            <div className="text-4xl font-bold mb-4">Download for Windows</div>
            <div className="text-slate-600 text-lg mb-8">Windows 10+ (x64)</div>
            <div className="mt-auto flex items-center font-bold text-xl bg-slate-900 text-white px-8 py-4 rounded-full w-fit group-hover:bg-black transition-colors">
              Download .msi ↓
            </div>
          </a>
        </div>

        {/* Also available */}
        <div className="flex flex-wrap gap-4 mb-24 text-sm text-slate-500">
          <span className="px-4 py-2 rounded-full border border-slate-200 bg-white">Also on the Microsoft Store</span>
          <span className="px-4 py-2 rounded-full border border-slate-200 bg-white">Free tier included &mdash; no account required</span>
        </div>

        {/* Quick Start - Clean & Clear */}
        <div className="bg-slate-50 rounded-[2rem] p-10 md:p-16 mb-24 border border-slate-200">
          <h2 className="text-3xl font-bold mb-8 text-slate-900">Get Started in 3 Steps</h2>
          
          <div className="space-y-8">
            <div className="flex flex-col md:flex-row gap-6 md:items-center">
              <div className="flex-shrink-0 w-12 h-12 bg-blue-600 text-white rounded-full flex items-center justify-center text-xl font-bold">1</div>
              <div className="flex-1">
                <div className="text-xl font-semibold mb-2">Install & launch the app</div>
                <p className="text-slate-600">
                  Open the <code className="bg-white border border-slate-300 rounded px-2 py-0.5 text-sm font-mono">.dmg</code> or <code className="bg-white border border-slate-300 rounded px-2 py-0.5 text-sm font-mono">.msi</code> and follow the installer. CoDRAG starts the background daemon automatically.
                </p>
              </div>
            </div>

            <div className="flex flex-col md:flex-row gap-6 md:items-center">
              <div className="flex-shrink-0 w-12 h-12 bg-slate-200 text-slate-700 rounded-full flex items-center justify-center text-xl font-bold">2</div>
              <div className="flex-1">
                <div className="text-xl font-semibold mb-2">Add your project</div>
                <p className="text-slate-600">
                  Click <strong>+</strong> in the sidebar, select your project folder, and CoDRAG begins indexing immediately.
                </p>
              </div>
            </div>

            <div className="flex flex-col md:flex-row gap-6 md:items-center">
              <div className="flex-shrink-0 w-12 h-12 bg-slate-200 text-slate-700 rounded-full flex items-center justify-center text-xl font-bold">3</div>
              <div className="flex-1">
                <div className="text-xl font-semibold mb-2">Connect your AI editor via MCP</div>
                <p className="text-slate-600">
                  Add CoDRAG to your Cursor or Windsurf MCP config. Your AI assistant now has structural code intelligence.
                </p>
                <code className="block mt-3 bg-white border border-slate-300 rounded-xl px-6 py-4 text-sm font-mono text-slate-700 overflow-x-auto">
                  {`{ "codrag": { "command": "codrag", "args": ["mcp"] } }`}
                </code>
              </div>
            </div>
          </div>
        </div>

        {/* Verification - Calm */}
        <div className="max-w-3xl">
          <h2 className="text-2xl font-bold mb-4">Security & Verification</h2>
          <p className="text-lg text-slate-600 leading-relaxed mb-6">
            We sign every release. You can verify the integrity of your download using the SHA-256 checksums available on the releases page.
          </p>
          <div className="flex gap-4">
            <a href="https://docs.codrag.io" className="text-blue-700 font-bold hover:underline underline-offset-4 text-lg">
              Read Documentation →
            </a>
            <a href="/security" className="text-blue-700 font-bold hover:underline underline-offset-4 text-lg">
              Security Policy →
            </a>
          </div>
        </div>

      </div>
    </main>
  );
}
