"use client";

// TODO(MVP): Re-add the "VS Code Extension" section once the native
// extension (sidebar UI for search, context assembly, trace navigation,
// Pro tier graph features) is back in MVP scope. Previous copy lived in
// git history (search: "VS Code Extension" in prior commits of this file).
// The extension is still planned — just not pitched publicly during MVP.
// For now VS Code is listed only as an MCP-capable IDE via GitHub Copilot.

import { DetailPageLayout, AnimatedCLI, AnimatedIDE, prepOverviewDemo, ideDemoScript } from '@prep/ui';
import { Terminal, Plug, Cpu, ArrowRight } from 'lucide-react';

const SECTIONS = [
  { id: 'universal', label: 'One Server, Every Editor' },
  { id: 'cli', label: 'CLI Agents' },
  { id: 'ide', label: 'Agentic IDEs' },
  { id: 'client-aware', label: 'Client-Aware Delivery' },
];

const CLI_AGENTS = [
  { name: 'Claude Code', vendor: 'Anthropic', note: 'Primary target — deepest hooks' },
  { name: 'Gemini CLI', vendor: 'Google', note: 'Native MCP support' },
  { name: 'Qwen Code', vendor: 'Alibaba', note: 'Native MCP support' },
  { name: 'Any MCP CLI', vendor: '—', note: 'Aider, Amp, Zed terminal, and others' },
];

const IDES = [
  { name: 'Cursor', vendor: 'Cursor', note: 'Native MCP' },
  { name: 'Antigravity', vendor: 'Google', note: 'Native MCP' },
  { name: 'Windsurf', vendor: 'Codeium', note: 'Native MCP' },
  { name: 'VS Code', vendor: 'Microsoft', note: 'MCP via GitHub Copilot' },
];

export default function IntegrationsPage() {
  return (
    <DetailPageLayout
      title="IDE Integrations"
      subtitle="One Server, Every Editor"
      description="SourcePrep speaks the Model Context Protocol. Any editor or agent that speaks MCP connects to the same daemon with the same config — no per-editor forks, no bespoke plugins."
      badge="MCP"
      sections={SECTIONS}
      docsUrl="https://docs.sourceprep.io/integrations"
      docsLabel="Integration setup guides"
    >
      {/* Universal */}
      <section id="universal">
        <h2 className="text-2xl font-semibold text-text mb-4">One Server, Every Editor</h2>
        <p className="text-text-muted leading-relaxed mb-6">
          Run <code className="text-primary font-mono text-sm">prep serve</code> once. Every MCP-aware
          agent in your workflow — CLI or IDE — reaches the same daemon and gets the same structural
          intelligence. No per-editor plugins, no vendor lock-in, no duplicated indexes.
        </p>

        <div className="grid sm:grid-cols-3 gap-6 mb-10">
          {[
            { icon: <Terminal className="w-5 h-5" />, title: 'Single Command', desc: 'One daemon serves every connected agent simultaneously' },
            { icon: <Plug className="w-5 h-5" />, title: 'MCP Standard', desc: 'Works with any tool that implements the Model Context Protocol' },
            { icon: <Cpu className="w-5 h-5" />, title: 'No Lock-in', desc: 'Switch tools freely — your index and context travel with you' },
          ].map((item) => (
            <div key={item.title}>
              <div className="text-primary mb-2">{item.icon}</div>
              <h3 className="font-medium text-sm text-text mb-1">{item.title}</h3>
              <p className="text-xs text-text-muted">{item.desc}</p>
            </div>
          ))}
        </div>

        <div className="rounded-lg border border-border bg-surface p-6">
          <p className="text-xs uppercase tracking-widest text-text-muted mb-3">Shared MCP config</p>
          <pre className="bg-background border border-border-subtle rounded-md p-3 text-xs font-mono overflow-x-auto text-text">
            {`"prep": {
  "command": "prep",
  "args": ["mcp"]
}`}
          </pre>
          <p className="text-xs text-text-muted mt-3">
            This is the common core. Every editor nests it slightly differently (<code className="font-mono">servers</code>{' '}
            vs <code className="font-mono">mcpServers</code> vs <code className="font-mono">context_servers</code>) and
            stores it at a different path. SourcePrep auto-generates these files when it detects a supported client.
          </p>
          <a
            href="/setup"
            className="inline-flex items-center gap-2 mt-4 text-sm font-medium text-primary hover:underline"
          >
            MCP config setup guides <ArrowRight className="w-4 h-4" />
          </a>
        </div>
      </section>

      {/* CLI Agents */}
      <section id="cli">
        <h2 className="text-2xl font-semibold text-text mb-4">CLI Agents</h2>
        <p className="text-text-muted leading-relaxed mb-6">
          Terminal-first coding agents see the biggest lift from structural context because they have no
          sidebar, no open tabs, no visible file tree to orient themselves. Claude Code is the primary
          target — the tool dispatch, auto-approve hints, and AGENTS.md generation are all shaped around
          it — but the MCP server works the same for Gemini CLI, Qwen Code, and other MCP-aware CLIs.
        </p>

        <div className="mb-8">
          <AnimatedCLI script={prepOverviewDemo} theme="dark" className="w-full" contentClassName="min-h-[440px] max-h-[520px]" />
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {CLI_AGENTS.map((agent) => (
            <div key={agent.name} className="rounded-lg border border-border bg-surface p-4">
              <div className="font-medium text-sm text-text">{agent.name}</div>
              <div className="text-xs text-text-muted mt-0.5">{agent.vendor}</div>
              <div className="text-xs text-text-muted mt-2">{agent.note}</div>
            </div>
          ))}
        </div>

        <a
          href="/claude-code"
          className="inline-flex items-center gap-2 mt-6 text-sm font-medium text-primary hover:underline"
        >
          Claude Code deep dive <ArrowRight className="w-4 h-4" />
        </a>
      </section>

      {/* Agentic IDEs */}
      <section id="ide">
        <h2 className="text-2xl font-semibold text-text mb-4">Agentic IDEs</h2>
        <p className="text-text-muted leading-relaxed mb-6">
          The big agentic editors all speak MCP natively — Cursor, Antigravity, Windsurf, and VS Code
          (via GitHub Copilot). The setup story is the same everywhere: drop the SourcePrep MCP block into
          the editor&apos;s config, restart, done. What differs is the editor itself, not the integration.
        </p>

        <div className="mb-8">
          <AnimatedIDE script={ideDemoScript} className="w-full" />
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {IDES.map((ide) => (
            <div key={ide.name} className="rounded-lg border border-border bg-surface p-4">
              <div className="font-medium text-sm text-text">{ide.name}</div>
              <div className="text-xs text-text-muted mt-0.5">{ide.vendor}</div>
              <div className="text-xs text-text-muted mt-2">{ide.note}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Client-Aware Delivery */}
      <section id="client-aware">
        <h2 className="text-2xl font-semibold text-text mb-4">Client-Aware Delivery</h2>
        <p className="text-text-muted leading-relaxed mb-4">
          The setup is uniform, but the output isn&apos;t. SourcePrep reads the MCP{' '}
          <code className="text-primary font-mono text-sm">clientInfo</code> handshake and tunes the
          response per client — format density, context budget, and which hints to attach. Agents get
          shaped output without any per-editor configuration.
        </p>
        <div className="grid sm:grid-cols-3 gap-4 mb-8">
          {[
            { client: 'Claude Code', detail: 'Compact format, auto-approve hints, skills context' },
            { client: 'Cursor', detail: 'Richer format with inline code blocks and annotations' },
            { client: 'Windsurf', detail: 'Budget tuned to Windsurf\'s context window' },
          ].map((item) => (
            <div key={item.client} className="rounded-lg border border-border bg-surface px-4 py-3">
              <span className="font-mono text-xs font-bold text-primary block mb-1">{item.client}</span>
              <span className="text-xs text-text-muted">{item.detail}</span>
            </div>
          ))}
        </div>
        <a
          href="https://docs.sourceprep.io/integrations"
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
