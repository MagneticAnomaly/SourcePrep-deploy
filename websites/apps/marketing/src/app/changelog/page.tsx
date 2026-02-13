"use client";

import { Button } from '@codrag/ui';

interface ChangelogEntry {
  version: string;
  date: string;
  title: string;
  highlights: string[];
  type: 'major' | 'minor' | 'patch';
}

const CHANGELOG: ChangelogEntry[] = [
  {
    version: '1.0.0',
    date: '2026-03-01',
    title: 'Initial Release',
    type: 'major',
    highlights: [
      'Structural Code Graph — maps imports, calls, and symbol hierarchies',
      'Semantic code search with sub-100ms results',
      'MCP server for Cursor, Windsurf, VS Code, and Claude Desktop',
      'Real-time file watcher with incremental rebuild',
      'Modular dashboard with project management',
      'macOS and Windows support (Tauri desktop app)',
      'Free tier: 1 project, manual indexing',
      'Pro license: $79 one-time, unlimited projects',
    ],
  },
  {
    version: '0.9.0-beta',
    date: '2026-02-01',
    title: 'Public Beta',
    type: 'minor',
    highlights: [
      'Multi-project support with project registry',
      'Context assembly API for LLM prompt construction',
      'Embedded and standalone index modes',
      'CLI commands: serve, add, build, search, mcp',
      'Dashboard UI with panel-based layout',
    ],
  },
  {
    version: '0.5.0-alpha',
    date: '2025-12-01',
    title: 'Alpha Preview',
    type: 'minor',
    highlights: [
      'Core indexing engine with tree-sitter parsing',
      'Basic semantic search',
      'Single-project mode',
      'Initial MCP integration',
    ],
  },
];

function typeBadgeColor(type: ChangelogEntry['type']) {
  switch (type) {
    case 'major': return 'bg-[#8b5cf6] text-white border-black';
    case 'minor': return 'bg-[#facc15] text-black border-black';
    case 'patch': return 'bg-white text-black border-black';
  }
}

export default function Page() {
  return (
    <main className="min-h-screen bg-white text-black font-mono selection:bg-[#facc15] selection:text-black">
      {/* Neo-Brutalist / Raw Engine Layout */}
      <div className="mx-auto max-w-7xl px-6 py-24">
        
        {/* Nav Back - Raw Link */}
        <a href="/" className="inline-block text-sm font-bold uppercase tracking-widest hover:bg-black hover:text-white px-2 py-1 mb-12 border-2 border-transparent hover:border-black transition-none">
          ← // RETURN_HOME
        </a>

        {/* Header - Brutalist */}
        <div className="border-4 border-black p-8 mb-16 shadow-[8px_8px_0px_0px_rgba(0,0,0,1)] bg-white">
          <h1 className="text-6xl md:text-8xl font-black uppercase leading-[0.8] mb-6 break-words">
            Change<br/>Log
          </h1>
          <p className="text-xl md:text-2xl font-bold max-w-2xl leading-tight border-l-4 border-black pl-6 py-2">
            SYSTEM_UPDATES_AND_PATCH_NOTES.<br/>
            TRACKING_EVOLUTION_OF_CORE_ENGINE.
          </p>
        </div>

        {/* Timeline */}
        <div className="relative border-l-4 border-black ml-4 md:ml-12 pl-8 md:pl-16 space-y-20 py-8">
          {CHANGELOG.map((entry) => (
            <article key={entry.version} className="relative">
              {/* Node Marker */}
              <div className="absolute -left-[46px] md:-left-[78px] top-0 w-6 h-6 bg-black border-2 border-white ring-2 ring-black"></div>

              {/* Version Header */}
              <div className="flex flex-col md:flex-row md:items-baseline gap-4 mb-6 border-b-4 border-black pb-4">
                <span className="text-5xl font-black tracking-tighter">
                  v{entry.version}
                </span>
                <div className="flex gap-2 items-center">
                  <span className={`border-2 px-3 py-1 text-sm font-bold uppercase ${typeBadgeColor(entry.type)} shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]`}>
                    {entry.type}
                  </span>
                  <span className="text-sm font-bold bg-black text-white px-3 py-1.5">
                    {entry.date}
                  </span>
                </div>
              </div>

              {/* Content Box */}
              <div className="border-2 border-black p-6 md:p-8 bg-white shadow-[8px_8px_0px_0px_rgba(0,0,0,1)] hover:translate-x-1 hover:translate-y-1 hover:shadow-none transition-all duration-75 cursor-default">
                <h2 className="text-2xl font-bold uppercase mb-6 bg-[#facc15] inline-block px-2 py-1 border-2 border-black">
                  {entry.title}
                </h2>
                <ul className="space-y-3">
                  {entry.highlights.map((item, i) => (
                    <li key={i} className="flex items-start gap-4 text-lg font-medium leading-snug">
                      <span className="text-black font-black mt-1">&gt;&gt;</span>
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </article>
          ))}
        </div>

        {/* Raw Footer Actions */}
        <div className="mt-32 border-t-8 border-black pt-12 flex flex-col md:flex-row gap-6">
          <a href="/download" className="flex-1 bg-black text-white text-center py-6 text-2xl font-bold uppercase hover:bg-[#8b5cf6] hover:text-white border-4 border-black transition-colors shadow-[8px_8px_0px_0px_rgba(0,0,0,0.2)]">
            [ Download_Latest_Build ]
          </a>
          <a href="https://docs.codrag.io" className="flex-1 bg-white text-black text-center py-6 text-2xl font-bold uppercase hover:bg-[#facc15] border-4 border-black transition-colors shadow-[8px_8px_0px_0px_rgba(0,0,0,1)]">
            [ Read_Documentation ]
          </a>
        </div>
        
      </div>
    </main>
  );
}
