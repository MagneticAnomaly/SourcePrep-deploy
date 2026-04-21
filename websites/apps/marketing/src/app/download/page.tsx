"use client";

import { useState } from 'react';
import { Button } from '@prep/ui';

const RELEASES_URL =
  process.env.NEXT_PUBLIC_PREP_RELEASES_URL ??
  'https://github.com/MagneticAnomaly/Prep-MCP/releases';

const MCP_CONFIGS = [
  {
    name: 'Claude Code',
    file: '.claude/mcp.json (project root)',
    config: `{
  "servers": {
    "prep": {
      "command": "prep",
      "args": ["mcp"]
    }
  }
}`,
  },
  {
    name: 'Cursor',
    file: '.cursor/mcp.json (project root)',
    config: `{
  "mcpServers": {
    "prep": {
      "command": "prep",
      "args": ["mcp"]
    }
  }
}`,
  },
  {
    name: 'Windsurf',
    file: '~/.codeium/windsurf/mcp_config.json',
    config: `{
  "mcpServers": {
    "prep": {
      "command": "prep",
      "args": ["mcp"],
      "disabled": false
    }
  }
}`,
  },
  {
    name: 'Copilot',
    file: '.vscode/mcp.json (project root)',
    config: `{
  "servers": {
    "prep": {
      "command": "prep",
      "args": ["mcp"]
    }
  }
}`,
  },
  {
    name: 'Gemini CLI',
    file: '~/.gemini/settings.json',
    config: `{
  "mcpServers": {
    "prep": {
      "command": "prep",
      "args": ["mcp"],
      "trust": true
    }
  }
}`,
  },
  {
    name: 'Zed',
    file: '~/.config/zed/settings.json',
    config: `{
  "context_servers": {
    "prep": {
      "command": "prep",
      "args": ["mcp"]
    }
  }
}`,
  },
];

function MCPConfigs() {
  const [active, setActive] = useState(0);
  return (
    <div className="bg-background border border-border rounded-xl overflow-hidden">
      <div className="flex flex-wrap border-b border-border">
        {MCP_CONFIGS.map((tool, i) => (
          <button
            key={tool.name}
            onClick={() => setActive(i)}
            className={`px-4 py-2.5 text-sm font-medium transition-colors ${
              i === active
                ? 'bg-primary text-background'
                : 'text-text-muted hover:text-text hover:bg-surface'
            }`}
          >
            {tool.name}
          </button>
        ))}
      </div>
      <div className="p-4">
        <div className="text-xs text-text-subtle mb-2 font-mono">{MCP_CONFIGS[active].file}</div>
        <pre className="text-sm font-mono text-text-muted whitespace-pre overflow-x-auto">
          {MCP_CONFIGS[active].config}
        </pre>
      </div>
    </div>
  );
}

export default function Page() {
  return (
    <div className="min-h-screen bg-background text-text font-sans selection:bg-primary/20 border-t-8 border-primary">
      <div className="mx-auto max-w-7xl px-6 py-24">

        <div className="max-w-4xl">
          <h1 className="text-5xl md:text-7xl font-bold tracking-tight text-text mb-8">
            Download Prep.
          </h1>
          <p className="text-2xl md:text-3xl text-text-muted leading-normal mb-12 max-w-3xl">
            Epistemic codebase indexing, trace graphs, and MCP integration, with Private by Design architecture.
          </p>
        </div>

        {/* Primary Actions */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-24">
          <a
            href={RELEASES_URL}
            className="group flex flex-col p-10 rounded-2xl bg-primary text-background hover:opacity-90 hover:scale-[1.01] transition-all shadow-lg focus:outline-none focus:ring-2 focus:ring-primary"
          >
            <div className="text-lg font-bold uppercase tracking-wider opacity-70 mb-2">For macOS</div>
            <div className="text-4xl font-bold mb-4">Download for Mac</div>
            <div className="opacity-80 text-lg mb-8">macOS 11+ (Apple Silicon)</div>
            <div className="mt-auto flex items-center font-bold text-xl bg-background text-primary px-8 py-4 rounded-full w-fit group-hover:opacity-90 transition-opacity">
              Download .dmg ↓
            </div>
          </a>

          <a
            href={RELEASES_URL}
            className="group flex flex-col p-10 rounded-2xl bg-surface text-text border border-border hover:border-primary hover:scale-[1.01] transition-all focus:outline-none focus:ring-2 focus:ring-primary"
          >
            <div className="text-lg font-bold uppercase tracking-wider text-text-muted mb-2">For Windows</div>
            <div className="text-4xl font-bold mb-4">Download for Windows</div>
            <div className="text-text-muted text-lg mb-8">Windows 10+ (x64)</div>
            <div className="mt-auto flex items-center font-bold text-xl bg-text text-background px-8 py-4 rounded-full w-fit group-hover:opacity-80 transition-opacity">
              Download .msi ↓
            </div>
          </a>
        </div>

        {/* Also available */}
        <div className="flex flex-wrap gap-4 mb-24 text-sm text-text-subtle">
          <span className="px-4 py-2 rounded-full border border-border bg-surface">Also on the Microsoft Store</span>
          <span className="px-4 py-2 rounded-full border border-border bg-surface">Free tier included &mdash; no account required</span>
        </div>

        {/* Quick Start */}
        <div className="bg-surface rounded-2xl p-10 md:p-16 mb-24 border border-border">
          <h2 className="text-3xl font-bold mb-8 text-text">Get Started in 3 Steps</h2>

          <div className="space-y-8">
            <div className="flex flex-col md:flex-row gap-6 md:items-center">
              <div className="flex-shrink-0 w-12 h-12 bg-primary text-background rounded-full flex items-center justify-center text-xl font-bold">1</div>
              <div className="flex-1">
                <div className="text-xl font-semibold mb-2">Install &amp; launch the app</div>
                <p className="text-text-muted">
                  Open the <code className="bg-background border border-border rounded px-2 py-0.5 text-sm font-mono">.dmg</code> or <code className="bg-background border border-border rounded px-2 py-0.5 text-sm font-mono">.msi</code> and follow the installer. Prep starts the background daemon automatically.
                </p>
              </div>
            </div>

            <div className="flex flex-col md:flex-row gap-6 md:items-center">
              <div className="flex-shrink-0 w-12 h-12 bg-surface-raised border border-border text-text-muted rounded-full flex items-center justify-center text-xl font-bold">2</div>
              <div className="flex-1">
                <div className="text-xl font-semibold mb-2">Add your project</div>
                <p className="text-text-muted">
                  Click <strong>+</strong> in the sidebar, select your project folder, and Prep begins indexing immediately.
                </p>
              </div>
            </div>

            <div className="flex flex-col md:flex-row gap-6 md:items-start">
              <div className="flex-shrink-0 w-12 h-12 bg-surface-raised border border-border text-text-muted rounded-full flex items-center justify-center text-xl font-bold">3</div>
              <div className="flex-1">
                <div className="text-xl font-semibold mb-2">Connect your AI editor via MCP</div>
                <p className="text-text-muted mb-4">
                  Add Prep to your editor&apos;s MCP config. Your AI assistant gets structural code intelligence, semantic search, and dependency analysis.
                </p>
                <MCPConfigs />
              </div>
            </div>
          </div>
        </div>

        {/* Verification */}
        <div className="max-w-3xl">
          <h2 className="text-2xl font-bold mb-4">Security &amp; Verification</h2>
          <p className="text-lg text-text-muted leading-relaxed mb-6">
            We sign every release. You can verify the integrity of your download using the SHA-256 checksums available on the releases page.
          </p>
          <div className="flex flex-wrap gap-4">
            <a href="/setup" className="text-primary font-bold hover:underline underline-offset-4 text-lg">
              Full MCP Setup Guide →
            </a>
            <a href="https://docs.runprep.io" className="text-primary font-bold hover:underline underline-offset-4 text-lg">
              Read Documentation →
            </a>
            <a href="/security" className="text-primary font-bold hover:underline underline-offset-4 text-lg">
              Security Policy →
            </a>
          </div>
        </div>

      </div>
    </div>
  );
}
