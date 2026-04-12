"use client";

import { DetailPageLayout } from '@codrag/ui';
import { ArrowRight, Bot, Brain, FileText, History, Search, Shield, Zap } from 'lucide-react';

const SECTIONS = [
  { id: 'why', label: 'Why Claude Code + CoDRAG' },
  { id: 'tools', label: 'Six Tools at a Glance' },
  { id: 'auto-approve', label: 'Auto-Approve & Skills' },
  { id: 'agents-md', label: 'AGENTS.md Generation' },
  { id: 'client-aware', label: 'Client-Aware Delivery' },
];

const TOOLS = [
  {
    icon: <Brain className="w-4 h-4" />,
    name: 'codrag',
    desc: 'Ambient structural context, no query needed',
  },
  {
    icon: <Search className="w-4 h-4" />,
    name: 'codrag_search',
    desc: 'Semantic search with intent classification (7 intents auto-detected)',
  },
  {
    icon: <Zap className="w-4 h-4" />,
    name: 'codrag_impact',
    desc: 'Blast radius analysis before changes',
  },
  {
    icon: <Shield className="w-4 h-4" />,
    name: 'codrag_audit',
    desc: 'Enrich linter findings with structural context',
  },
  {
    icon: <History className="w-4 h-4" />,
    name: 'codrag_observe',
    desc: 'Persistent cross-session memory',
  },
  {
    icon: <FileText className="w-4 h-4" />,
    name: 'codrag_concepts',
    desc: 'Business rationale and design decisions',
  },
];

export default function ClaudeCodePage() {
  return (
    <DetailPageLayout
      title="Claude Code"
      subtitle="Deepest Integration"
      description="CoDRAG is purpose-built for Claude Code. Six MCP tools, auto-approve safety, skills integration, and client-aware content delivery."
      badge="Integration"
      sections={SECTIONS}
      docsUrl="https://docs.codrag.io/integrations/claude-code"
      docsLabel="Claude Code setup guide"
    >
      {/* Why Claude Code + CoDRAG */}
      <section id="why">
        <h2 className="text-2xl font-semibold text-text mb-4">Why Claude Code + CoDRAG</h2>
        <p className="text-text-muted leading-relaxed mb-6">
          Claude Code is the most capable AI coding CLI — it reasons, plans, and executes across an entire codebase.
          But even the best model is limited by what context it can see. CoDRAG gives Claude Code structural codebase
          intelligence via MCP: the full module graph, import chains, hub files, design decisions, and semantic search.
          Together, Claude Code doesn&apos;t just read files — it understands architecture.
        </p>
        <div className="grid sm:grid-cols-3 gap-4">
          {[
            {
              icon: <Brain className="w-5 h-5" />,
              title: 'Structural Awareness',
              desc: 'Claude sees the full dependency graph, hub files, and import chains — not just flat file contents.',
            },
            {
              icon: <Bot className="w-5 h-5" />,
              title: 'Agent-Native',
              desc: 'CoDRAG is designed for autonomous agentic loops — low noise, high signal, source-cited.',
            },
            {
              icon: <Zap className="w-5 h-5" />,
              title: 'Zero Ramp-Up',
              desc: 'Call codrag once at the start of any task. Structural context lands in seconds.',
            },
          ].map((item) => (
            <div key={item.title} className="rounded-lg border border-border bg-surface p-4">
              <div className="text-primary mb-2">{item.icon}</div>
              <h3 className="font-medium text-sm text-text mb-1">{item.title}</h3>
              <p className="text-xs text-text-muted">{item.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Six Tools at a Glance */}
      <section id="tools">
        <h2 className="text-2xl font-semibold text-text mb-4">Six Tools at a Glance</h2>
        <p className="text-text-muted leading-relaxed mb-6">
          CoDRAG registers six MCP tools with Claude Code. Each is read-only and purpose-built for a specific
          type of codebase intelligence.
        </p>
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {TOOLS.map((tool) => (
            <div key={tool.name} className="rounded-lg border border-border bg-surface p-4 flex flex-col gap-2">
              <div className="flex items-center gap-2">
                <span className="text-primary">{tool.icon}</span>
                <span className="font-mono font-bold text-sm text-text">{tool.name}</span>
              </div>
              <p className="text-xs text-text-muted leading-relaxed">{tool.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Auto-Approve & Skills */}
      <section id="auto-approve">
        <h2 className="text-2xl font-semibold text-text mb-4">Auto-Approve &amp; Skills</h2>
        <p className="text-text-muted leading-relaxed mb-4">
          All six CoDRAG tools are read-only and completely safe to auto-approve. No writes, no side effects,
          no shell commands. CoDRAG generates the auto-approve config and a skills file for your project automatically
          — so Claude Code can call CoDRAG without a permission prompt on every invocation.
        </p>
        <div className="rounded-lg border border-border bg-[#0d1117] p-5 font-mono text-sm mb-4">
          <div className="text-[#8b949e] mb-2 text-xs">{"// .claude/settings.json"}</div>
          <div className="text-[#e6edf3]">{"{"}</div>
          <div className="pl-4 text-[#e6edf3]">
            <span className="text-[#79c0ff]">&quot;permissions&quot;</span>
            <span className="text-[#e6edf3]">{": {"}</span>
          </div>
          <div className="pl-8 text-[#e6edf3]">
            <span className="text-[#79c0ff]">&quot;allow&quot;</span>
            <span className="text-[#e6edf3]">{": ["}</span>
            <span className="text-[#a5d6ff]">&quot;mcp__codrag&quot;</span>
            <span className="text-[#e6edf3]">{"]"}</span>
          </div>
          <div className="pl-4 text-[#e6edf3]">{"}"}</div>
          <div className="text-[#e6edf3]">{"}"}</div>
        </div>
        <p className="text-sm text-text-muted">
          CoDRAG also generates a <code className="text-primary font-mono text-xs">.claude/skills/</code> file
          that tells Claude Code when and how to call each tool — reducing friction and ensuring tools are used
          at the right moment in agentic workflows.
        </p>
      </section>

      {/* AGENTS.md Generation */}
      <section id="agents-md">
        <h2 className="text-2xl font-semibold text-text mb-4">AGENTS.md Generation</h2>
        <p className="text-text-muted leading-relaxed mb-4">
          CoDRAG auto-generates an <code className="text-primary font-mono text-sm">AGENTS.md</code> file at the
          root of your project. This file is the bridge between static project knowledge and live queryable
          intelligence — it tells Claude Code about the MCP tools available, provides a codebase atlas, lists hub
          files and entry points, and maps the full module structure.
        </p>
        <div className="space-y-3 mb-6">
          {[
            { label: 'Codebase Atlas', desc: 'Auto-generated structural snapshot: stack, workspace segments, entry points, cross-cutting concerns' },
            { label: 'Hub Files', desc: 'Files with the highest dependency fan-in — the places most likely to cause cascading changes' },
            { label: 'Module Map', desc: 'Workspace boundaries and the symbols each segment exposes to others' },
            { label: 'Tool Instructions', desc: 'Front-loaded, aggressive instructions telling Claude Code to call codrag immediately at task start' },
          ].map((item) => (
            <div key={item.label} className="flex items-start gap-3 rounded-lg border border-border bg-surface px-4 py-3">
              <span className="font-mono text-xs font-bold text-primary mt-0.5 shrink-0">{item.label}</span>
              <span className="text-sm text-text-muted">{item.desc}</span>
            </div>
          ))}
        </div>
        <p className="text-sm text-text-muted">
          The file is regenerated whenever CoDRAG rebuilds the index. User additions outside the managed block
          are preserved across regenerations.
        </p>
      </section>

      {/* Client-Aware Delivery */}
      <section id="client-aware">
        <h2 className="text-2xl font-semibold text-text mb-4">Client-Aware Delivery</h2>
        <p className="text-text-muted leading-relaxed mb-4">
          CoDRAG detects it&apos;s talking to Claude Code and tailors content delivery accordingly. Claude Code gets
          compact, high-density responses optimized for its context window — not the verbose output suited for
          a human-facing dashboard. Token budgets, response format, and tool instructions are all tuned
          per-client automatically.
        </p>
        <div className="grid sm:grid-cols-2 gap-4 mb-8">
          <div className="rounded-lg border border-primary/30 bg-primary/5 p-4">
            <h3 className="font-mono text-xs font-bold text-primary mb-2 uppercase tracking-widest">Claude Code</h3>
            <ul className="text-xs text-text-muted space-y-1.5">
              <li>Compact response format</li>
              <li>Optimized token budgets</li>
              <li>Claude-specific tool instructions</li>
              <li>Skills + auto-approve config generated</li>
            </ul>
          </div>
          <div className="rounded-lg border border-border bg-surface p-4">
            <h3 className="font-mono text-xs font-bold text-text mb-2 uppercase tracking-widest">Other Clients</h3>
            <ul className="text-xs text-text-muted space-y-1.5">
              <li>Cursor: role-based atlas projection</li>
              <li>Windsurf: verbose structural context</li>
              <li>VS Code: webview-optimized output</li>
              <li>Generic: standard MCP response</li>
            </ul>
          </div>
        </div>
        <a
          href="https://docs.codrag.io/integrations/claude-code"
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-2 rounded-md bg-primary px-5 py-2.5 text-sm font-semibold text-background hover:bg-primary-hover transition-colors"
        >
          Claude Code setup guide <ArrowRight className="w-4 h-4" />
        </a>
      </section>
    </DetailPageLayout>
  );
}
