"use client";

import { DetailPageLayout } from '@prep/ui';
import { Terminal, Code, Plug, Monitor, Cpu, ArrowRight } from 'lucide-react';

const SECTIONS = [
  { id: 'universal', label: 'One Server, Every Editor' },
  { id: 'claude-code', label: 'Claude Code' },
  { id: 'antigravity', label: 'Antigravity' },
  { id: 'cursor-windsurf', label: 'Cursor & Windsurf' },
  { id: 'vscode', label: 'VS Code Extension' },
  { id: 'client-aware', label: 'Client-Aware Delivery' },
];

export default function IntegrationsPage() {
  return (
    <DetailPageLayout
      title="IDE Integrations"
      subtitle="One Server, Every Editor"
      description="RunPrep connects to Claude Code, Antigravity, Cursor, Windsurf, VS Code, and any MCP-compatible tool via a single MCP server."
      badge="MCP"
      sections={SECTIONS}
      docsUrl="https://docs.runprep.io/integrations"
      docsLabel="Integration setup guides"
    >
      {/* Universal */}
      <section id="universal">
        <h2 className="text-2xl font-semibold text-text mb-4">One Server, Every Editor</h2>
        <p className="text-text-muted leading-relaxed mb-6">
          RunPrep is a single MCP server that connects to any tool supporting the Model Context Protocol.
          Run <code className="text-primary font-mono text-sm">prep serve</code> once, and every editor in your workflow
          gets the same structural intelligence. No per-editor plugins to maintain, no vendor lock-in.
        </p>
        <div className="grid sm:grid-cols-3 gap-4">
          {[
            { icon: <Terminal className="w-5 h-5" />, title: 'Single Command', desc: 'One daemon serves all connected editors simultaneously' },
            { icon: <Plug className="w-5 h-5" />, title: 'MCP Standard', desc: 'Works with any tool that supports Model Context Protocol' },
            { icon: <Cpu className="w-5 h-5" />, title: 'No Lock-in', desc: 'Switch editors freely — your index and context travel with you' },
          ].map((item) => (
            <div key={item.title} className="rounded-lg border border-border bg-surface p-4">
              <div className="text-primary mb-2">{item.icon}</div>
              <h3 className="font-medium text-sm text-text mb-1">{item.title}</h3>
              <p className="text-xs text-text-muted">{item.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Claude Code */}
      <section id="claude-code">
        <h2 className="text-2xl font-semibold text-text mb-4">Claude Code</h2>
        <p className="text-text-muted leading-relaxed mb-6">
          Claude Code receives RunPrep's deepest integration. The full suite of MCP tools is designed around Claude Code's
          agentic workflows, with client-aware context delivery, skills integration, and automatic project onboarding.
        </p>
        <div className="rounded-lg border border-primary/30 bg-primary/5 p-6 mb-4">
          <div className="flex items-center gap-2 mb-4">
            <Terminal className="w-5 h-5 text-primary" />
            <h3 className="font-semibold text-text">Claude Code</h3>
            <span className="ml-auto text-xs font-medium text-primary bg-primary/10 px-2 py-0.5 rounded-full">Deepest Integration</span>
          </div>
          <ul className="space-y-2 text-sm text-text-muted">
            <li className="flex items-start gap-2"><span className="text-primary mt-0.5">→</span> 6 MCP tools with auto-approve safety</li>
            <li className="flex items-start gap-2"><span className="text-primary mt-0.5">→</span> Skills integration for automated workflows</li>
            <li className="flex items-start gap-2"><span className="text-primary mt-0.5">→</span> AGENTS.md generation for project onboarding</li>
            <li className="flex items-start gap-2"><span className="text-primary mt-0.5">→</span> Client-aware content tailored for Claude Code</li>
          </ul>
          <a
            href="/claude-code"
            className="inline-flex items-center gap-2 mt-4 text-sm font-medium text-primary hover:underline"
          >
            Full Claude Code integration guide <ArrowRight className="w-4 h-4" />
          </a>
        </div>
      </section>

      {/* Antigravity */}
      <section id="antigravity">
        <h2 className="text-2xl font-semibold text-text mb-4">Antigravity</h2>
        <p className="text-text-muted leading-relaxed mb-6">
          Antigravity's agentic editing mode pairs naturally with RunPrep's structural intelligence — giving agents
          the codebase context they need to make confident, architecturally-aware edits.
        </p>
        <div className="rounded-lg border border-border bg-surface p-6">
          <div className="flex items-center gap-2 mb-4">
            <Code className="w-5 h-5 text-text-muted" />
            <h3 className="font-semibold text-text">Antigravity</h3>
          </div>
          <ul className="space-y-2 text-sm text-text-muted">
            <li className="flex items-start gap-2"><span className="text-primary mt-0.5">→</span> Full MCP tool support</li>
            <li className="flex items-start gap-2"><span className="text-primary mt-0.5">→</span> Ambient context on every task</li>
            <li className="flex items-start gap-2"><span className="text-primary mt-0.5">→</span> Works with Antigravity's agentic editing mode</li>
          </ul>
        </div>
      </section>

      {/* Cursor & Windsurf */}
      <section id="cursor-windsurf">
        <h2 className="text-2xl font-semibold text-text mb-4">Cursor &amp; Windsurf</h2>
        <p className="text-text-muted leading-relaxed mb-6">
          Both Cursor and Windsurf support MCP natively. RunPrep plugs in without any special configuration and adds
          structural depth that their built-in AI features don't provide.
        </p>
        <div className="rounded-lg border border-border bg-surface p-6">
          <div className="flex items-center gap-2 mb-4">
            <Monitor className="w-5 h-5 text-text-muted" />
            <h3 className="font-semibold text-text">Cursor &amp; Windsurf</h3>
          </div>
          <ul className="space-y-2 text-sm text-text-muted">
            <li className="flex items-start gap-2"><span className="text-primary mt-0.5">→</span> Native MCP support in both editors</li>
            <li className="flex items-start gap-2"><span className="text-primary mt-0.5">→</span> Auto-generated rules files (<code className="font-mono text-xs">.cursor/</code>, <code className="font-mono text-xs">.windsurf/</code>)</li>
            <li className="flex items-start gap-2"><span className="text-primary mt-0.5">→</span> Works alongside their built-in AI features — RunPrep adds structural depth they don't have</li>
          </ul>
        </div>
      </section>

      {/* VS Code */}
      <section id="vscode">
        <h2 className="text-2xl font-semibold text-text mb-4">VS Code Extension</h2>
        <p className="text-text-muted leading-relaxed mb-6">
          RunPrep ships a native VS Code extension with a sidebar UI for semantic search, context assembly, and trace navigation —
          no CLI required. Works alongside GitHub Copilot via MCP.
        </p>
        <div className="rounded-lg border border-border bg-surface p-6">
          <div className="flex items-center gap-2 mb-4">
            <Code className="w-5 h-5 text-text-muted" />
            <h3 className="font-semibold text-text">VS Code Extension</h3>
          </div>
          <ul className="space-y-2 text-sm text-text-muted">
            <li className="flex items-start gap-2"><span className="text-primary mt-0.5">→</span> Native VS Code extension with sidebar UI</li>
            <li className="flex items-start gap-2"><span className="text-primary mt-0.5">→</span> Semantic search, context assembly, trace navigation</li>
            <li className="flex items-start gap-2"><span className="text-primary mt-0.5">→</span> Free tier with Pro upgrade for graph features</li>
            <li className="flex items-start gap-2"><span className="text-primary mt-0.5">→</span> Works with Copilot via MCP</li>
          </ul>
        </div>
      </section>

      {/* Client-Aware Delivery */}
      <section id="client-aware">
        <h2 className="text-2xl font-semibold text-text mb-4">Client-Aware Delivery</h2>
        <p className="text-text-muted leading-relaxed mb-4">
          RunPrep auto-detects which client is connecting via MCP <code className="text-primary font-mono text-sm">clientInfo</code>.
          It tailors content delivery per client — compact format for Claude Code, richer format for Cursor, optimized
          budgets per client's context window. Your agents get exactly the right amount of context, automatically.
        </p>
        <div className="grid sm:grid-cols-3 gap-4 mb-8">
          {[
            { client: 'Claude Code', detail: 'Compact format, auto-approve hints, skills context' },
            { client: 'Cursor', detail: 'Richer format with inline code blocks and annotations' },
            { client: 'Windsurf', detail: 'Optimized budget for Windsurf\'s context window' },
          ].map((item) => (
            <div key={item.client} className="rounded-lg border border-border bg-surface px-4 py-3">
              <span className="font-mono text-xs font-bold text-primary block mb-1">{item.client}</span>
              <span className="text-xs text-text-muted">{item.detail}</span>
            </div>
          ))}
        </div>
        <a
          href="https://docs.runprep.io/integrations"
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-2 rounded-md bg-primary px-5 py-2.5 text-sm font-semibold text-background hover:bg-primary-hover transition-colors"
        >
          Integration setup guides <ArrowRight className="w-4 h-4" />
        </a>
      </section>
    </DetailPageLayout>
  );
}
