"use client";

import { DetailPageLayout } from '@prep/ui';
import { GitBranch, Zap, RefreshCw, ArrowRight } from 'lucide-react';

const SECTIONS = [
  { id: 'why', label: 'Why Paperclip + Prep' },
  { id: 'hybrid', label: 'Hybrid Integration' },
  { id: 'addresses', label: 'Prep Addresses' },
  { id: 'auto-push', label: 'Auto-Push Findings' },
  { id: 'agents', label: 'Agent Intelligence' },
];

export default function PaperclipPage() {
  return (
    <DetailPageLayout
      title="Paperclip Integration"
      subtitle="Agent Orchestration"
      description="Prep is the knowledge backbone for Paperclip's autonomous agent teams — providing structural codebase intelligence that agents use to understand, plan, and execute."
      badge="Integration"
      sections={SECTIONS}
      docsUrl="https://docs.runprep.io/integrations/paperclip"
      docsLabel="Paperclip setup guide"
    >
      {/* Why */}
      <section id="why">
        <h2 className="text-2xl font-semibold text-text mb-4">Why Paperclip + Prep</h2>
        <p className="text-text-muted leading-relaxed mb-6">
          Paperclip orchestrates autonomous agent teams — hiring AI agents to work on goals, issues, and routines.
          But agents working without codebase knowledge make shallow changes and miss architectural context.
          Prep gives every Paperclip agent deep structural awareness of the codebase they're working in.
        </p>
        <div className="grid sm:grid-cols-3 gap-4">
          {[
            { icon: <GitBranch className="w-5 h-5" />, title: 'Structural Context', desc: 'Agents see imports, call chains, and hub files — not just flat file contents' },
            { icon: <Zap className="w-5 h-5" />, title: 'Role-Scoped', desc: 'Security agents see auth code. UI agents see components. Automatically.' },
            { icon: <RefreshCw className="w-5 h-5" />, title: 'Always Current', desc: 'File watcher keeps the index fresh. Stale observations are flagged.' },
          ].map((item) => (
            <div key={item.title} className="rounded-lg border border-border bg-surface p-4">
              <div className="text-primary mb-2">{item.icon}</div>
              <h3 className="font-medium text-sm text-text mb-1">{item.title}</h3>
              <p className="text-xs text-text-muted">{item.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Hybrid Integration */}
      <section id="hybrid">
        <h2 className="text-2xl font-semibold text-text mb-4">Hybrid MCP + REST Architecture</h2>
        <p className="text-text-muted leading-relaxed mb-6">
          Prep connects to Paperclip through two complementary layers, giving agents both on-demand intelligence and proactive discovery.
        </p>
        <div className="grid sm:grid-cols-2 gap-6">
          <div className="rounded-lg border border-primary/30 bg-primary/5 p-6">
            <h3 className="font-mono font-bold text-sm text-primary mb-2">Pull: MCP Server</h3>
            <p className="text-sm text-text-muted mb-3">Agents call Prep tools on demand during their work.</p>
            <ul className="text-xs text-text-muted space-y-1.5 font-mono">
              <li>prep — structural overview</li>
              <li>prep_search — semantic search</li>
              <li>prep_impact — blast radius</li>
              <li>prep_audit — enriched findings</li>
              <li>prep_observe — persistent memory</li>
              <li>prep_concepts — design rationale</li>
            </ul>
          </div>
          <div className="rounded-lg border border-border bg-surface p-6">
            <h3 className="font-mono font-bold text-sm text-text mb-2">Push: REST API</h3>
            <p className="text-sm text-text-muted mb-3">Prep proactively pushes discoveries to Paperclip.</p>
            <ul className="text-xs text-text-muted space-y-1.5">
              <li>Audit findings become Paperclip issues</li>
              <li>Coupling hotspots become refactoring goals</li>
              <li>Import cycles become architectural tasks</li>
              <li>Resolved items auto-close in Paperclip</li>
            </ul>
          </div>
        </div>
      </section>

      {/* Prep Addresses */}
      <section id="addresses">
        <h2 className="text-2xl font-semibold text-text mb-4">Prep Addresses</h2>
        <p className="text-text-muted leading-relaxed mb-4">
          Every finding pushed to Paperclip carries a Prep address — a stable URI that agents can use to verify freshness and fetch updated context at work-time.
        </p>
        <div className="rounded-lg border border-border bg-[#0d1117] p-4 font-mono text-sm">
          <div className="text-[#8b949e] mb-2">{"// Agent verifies a finding before acting on it:"}</div>
          <div className="text-[#79c0ff]">prep://project-id/<span className="text-[#3fb950]">HEALTH-a7b9</span></div>
          <div className="text-[#8b949e] mt-2">{"// Returns: current status, structural context, related concepts"}</div>
        </div>
        <p className="text-sm text-text-muted mt-4">
          This means agents never act on stale intelligence. If the codebase changed since the finding was created, the agent knows before it starts work.
        </p>
      </section>

      {/* Auto-Push */}
      <section id="auto-push">
        <h2 className="text-2xl font-semibold text-text mb-4">Auto-Push Findings</h2>
        <p className="text-text-muted leading-relaxed mb-4">
          Prep's background intelligence engine (Pi Agent) continuously discovers structural issues and pushes them to Paperclip as actionable items — grouped by module or category.
        </p>
        <div className="space-y-3">
          {[
            { label: 'Watchdog', desc: 'Scans for new/resolved findings after every rebuild' },
            { label: 'Architect', desc: 'Proposes structural improvements based on graph analysis' },
            { label: 'Scholar', desc: 'Quality audits of enrichment coverage and depth' },
          ].map((agent) => (
            <div key={agent.label} className="flex items-start gap-3 rounded-lg border border-border bg-surface px-4 py-3">
              <span className="font-mono text-xs font-bold text-primary mt-0.5">{agent.label}</span>
              <span className="text-sm text-text-muted">{agent.desc}</span>
            </div>
          ))}
        </div>
      </section>

      {/* Agent Intelligence */}
      <section id="agents">
        <h2 className="text-2xl font-semibold text-text mb-4">Every Agent Gets Smarter</h2>
        <p className="text-text-muted leading-relaxed mb-6">
          When a Paperclip agent starts work on a goal, it calls <code className="text-primary font-mono text-sm">prep</code> to instantly understand the codebase's structure, hub files, and module boundaries. No ramp-up time, no context window waste.
        </p>
        <a
          href="https://docs.runprep.io/integrations/paperclip"
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-2 rounded-md bg-primary px-5 py-2.5 text-sm font-semibold text-background hover:bg-primary-hover transition-colors"
        >
          Set up Paperclip + Prep <ArrowRight className="w-4 h-4" />
        </a>
      </section>
    </DetailPageLayout>
  );
}
