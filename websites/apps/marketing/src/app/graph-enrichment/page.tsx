"use client";

import { DetailPageLayout } from '@prep/ui';
import { Zap, Brain, GitBranch, CheckCircle, BookOpen, Layers, Network, Map, Cpu, Sparkles, RefreshCw, FileText, Lightbulb, ClipboardCheck, Shield, ArrowRight } from 'lucide-react';

const SECTIONS = [
  { id: 'journey', label: 'The Journey' },
  { id: 'sync', label: 'Sync (1–5)' },
  { id: 'enrich', label: 'Enrich (6–10)' },
  { id: 'finalize', label: 'Finalize (11–15)' },
  { id: 'always-running', label: 'Always Running' },
];

const SYNC_STAGES = [
  {
    number: 1,
    name: 'STRUCTURAL',
    icon: <GitBranch className="w-4 h-4" />,
    description: 'Parses every file via tree-sitter. Extracts imports, symbols, call sites. Builds the trace graph in seconds.',
  },
  {
    number: 2,
    name: 'INFERRED_EDGES',
    icon: <Network className="w-4 h-4" />,
    description: 'Finds edges static parsing misses — cross-language API calls, dynamic dispatch, interface satisfaction, implicit dependencies. Confidence-scored; never overrides parser-derived edges.',
  },
  {
    number: 3,
    name: 'CATALOGUE',
    icon: <BookOpen className="w-4 h-4" />,
    description: 'A one-line summary and tags for every file. The longest single Sync stage on a fresh index — runs while structural context is already serving your agent.',
  },
  {
    number: 4,
    name: 'VALIDATION',
    icon: <CheckCircle className="w-4 h-4" />,
    description: 'Integrity check. Verifies graph consistency, flags orphan nodes, discards hallucinated edges.',
  },
  {
    number: 5,
    name: 'KNOWLEDGE',
    icon: <Zap className="w-4 h-4" />,
    description: 'The catalogued graph becomes searchable. Deeper enrichment happens next, in Enrich.',
  },
];

const ENRICH_STAGES = [
  {
    number: 6,
    name: 'DEEP_REASONING',
    icon: <Brain className="w-4 h-4" />,
    description: 'Epistemic scoring — layers, domains, confidence ratings for every node in graph context.',
  },
  {
    number: 7,
    name: 'GROUP_REASONING',
    icon: <Cpu className="w-4 h-4" />,
    description: 'LLM consensus across related nodes. Identifies patterns and architectural themes.',
  },
  {
    number: 8,
    name: 'MODULE_SYNTHESIS',
    icon: <Layers className="w-4 h-4" />,
    description: 'Module boundary discovery. Groups files into logical subsystems.',
  },
  {
    number: 9,
    name: 'DEEPENING',
    icon: <Sparkles className="w-4 h-4" />,
    description: 'Iterative epistemic refinement with full graph context available.',
  },
  {
    number: 10,
    name: 'DEEP_KNOWLEDGE',
    icon: <Brain className="w-4 h-4" />,
    description: 'Re-embed everything with enriched data. The search index now reflects deep understanding.',
  },
];

const FINALIZE_STAGES = [
  {
    number: 11,
    name: 'ATLAS',
    icon: <Map className="w-4 h-4" />,
    description: 'Generates the architectural overview — segments, hub files, cross-cutting concerns, workspace map.',
  },
  {
    number: 12,
    name: 'RULES',
    icon: <FileText className="w-4 h-4" />,
    description: 'Generates IDE rules files — AGENTS.md, .cursor/, .windsurf/ — so your editors know about the MCP tools.',
  },
  {
    number: 13,
    name: 'CONCEPTS',
    icon: <Lightbulb className="w-4 h-4" />,
    description: 'Seeds concepts from atlas, modules, and audit findings. The "why" behind the architecture.',
  },
  {
    number: 14,
    name: 'AUDIT',
    icon: <ClipboardCheck className="w-4 h-4" />,
    description: 'Runs structural analyzers — coupling hotspots, import cycles, hub concentration, quality gaps.',
  },
  {
    number: 15,
    name: 'ANTIBODIES',
    icon: <Shield className="w-4 h-4" />,
    description: 'Derives immune system defenses from concept assertions. Constraint violations surface as alerts.',
  },
];

function StageCard({ stage, variant }: { stage: typeof SYNC_STAGES[number]; variant: 'light' | 'primary' | 'accent' }) {
  const styles = {
    light: 'border-border bg-surface',
    primary: 'border-primary/30 bg-primary/5',
    accent: 'border-[#3fb950]/30 bg-[#3fb950]/5',
  };
  const badgeStyles = {
    light: 'bg-background border-border text-text-muted',
    primary: 'bg-background border-primary/30 text-primary',
    accent: 'bg-background border-[#3fb950]/30 text-[#3fb950]',
  };

  return (
    <div className={`flex items-start gap-4 rounded-lg border px-5 py-4 ${styles[variant]}`}>
      <div className={`flex-shrink-0 flex items-center justify-center w-8 h-8 rounded-full border text-xs font-bold font-mono ${badgeStyles[variant]}`}>
        {stage.number}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-primary">{stage.icon}</span>
          <span className="font-mono font-bold text-sm text-text">{stage.name}</span>
        </div>
        <p className="text-sm text-text-muted">{stage.description}</p>
      </div>
    </div>
  );
}

export default function GraphEnrichmentPage() {
  return (
    <DetailPageLayout
      title="Graph Enrichment"
      subtitle="How It Works"
      description="SourcePrep learns how your code actually connects — not just what words appear where. A multi-step pipeline turns raw source files into a living knowledge graph your AI can reason over: fast structural parsing first, then deeper reasoning about meaning, and finally the guides, rules, and safeguards your tools consume."
      badge="Pipeline"
      sections={SECTIONS}
      docsUrl="https://docs.sourceprep.io/concepts/graph-enrichment"
      docsLabel="Learn more in the docs"
    >
      {/* The Journey */}
      <section id="journey">
        <h2 className="text-2xl font-semibold text-text mb-4">The Journey</h2>
        <p className="text-text-muted leading-relaxed mb-4">
          Indexing runs in three groups. <strong className="text-text">Sync</strong> delivers a structural map in seconds and layers in the catalogue and search index over the next few minutes.
          <strong className="text-text"> Enrich</strong> reasons about what each module does and how it fits the whole.
          <strong className="text-text"> Finalize</strong> produces the atlas, rules, concepts, audit findings, and safeguards your tools actually consume.
        </p>
        <div className="grid sm:grid-cols-3 gap-4">
          <div className="rounded-lg border border-border bg-surface p-4">
            <div className="text-primary mb-2"><Zap className="w-5 h-5" /></div>
            <h3 className="font-medium text-sm text-text mb-1">Sync — Structure first</h3>
            <p className="text-xs text-text-muted">Structural map in seconds (Rust). Catalogue and search index follow in minutes — your agent works the whole time.</p>
          </div>
          <div className="rounded-lg border border-primary/30 bg-primary/5 p-4">
            <div className="text-primary mb-2"><Brain className="w-5 h-5" /></div>
            <h3 className="font-medium text-sm text-text mb-1">Enrich — Background</h3>
            <p className="text-xs text-text-muted">Reasons about what each piece of code does, clusters related modules, and scores what matters most.</p>
          </div>
          <div className="rounded-lg border border-[#3fb950]/30 bg-[#3fb950]/5 p-4">
            <div className="text-[#3fb950] mb-2"><Shield className="w-5 h-5" /></div>
            <h3 className="font-medium text-sm text-text mb-1">Finalize — Deliver</h3>
            <p className="text-xs text-text-muted">Atlas, rules, concepts, audit findings, and guardrails. Runs in parallel where possible.</p>
          </div>
        </div>
      </section>

      {/* Sync Stages */}
      <section id="sync">
        <h2 className="text-2xl font-semibold text-text mb-2">Sync</h2>
        <p className="text-text-muted leading-relaxed mb-6">
          The structural map is ready in seconds. The catalogue and search index follow within minutes on most
          codebases — your agent is already working the whole time.
        </p>
        <div className="space-y-3">
          {SYNC_STAGES.map((stage) => (
            <StageCard key={stage.number} stage={stage} variant="light" />
          ))}
        </div>
      </section>

      {/* Divider */}
      <div className="flex items-center gap-4 py-2">
        <div className="flex-1 h-px bg-border" />
        <span className="text-xs font-mono text-text-muted uppercase tracking-widest px-2">LLM Deep Enrichment</span>
        <div className="flex-1 h-px bg-border" />
      </div>

      {/* Enrich Stages */}
      <section id="enrich">
        <h2 className="text-2xl font-semibold text-text mb-2">Enrich</h2>
        <p className="text-text-muted leading-relaxed mb-6">
          Runs in the background with full LLM passes. Each stage builds on the previous, producing progressively richer structural understanding. Supports swarm mode — multiple LLM workers processing nodes in parallel.
        </p>
        <div className="space-y-3">
          {ENRICH_STAGES.map((stage) => (
            <StageCard key={stage.number} stage={stage} variant="primary" />
          ))}
        </div>
      </section>

      {/* Divider */}
      <div className="flex items-center gap-4 py-2">
        <div className="flex-1 h-px bg-border" />
        <span className="text-xs font-mono text-text-muted uppercase tracking-widest px-2">Synthesis &amp; Delivery</span>
        <div className="flex-1 h-px bg-border" />
      </div>

      {/* Finalize Stages */}
      <section id="finalize">
        <h2 className="text-2xl font-semibold text-text mb-2">Finalize</h2>
        <p className="text-text-muted leading-relaxed mb-6">
          Produces the deliverables your tools actually consume — the atlas document, IDE rules files, seeded concepts, audit findings, and immune system defenses.
          Most of these run in parallel once the atlas is ready; the safeguards are derived from your recorded concepts last.
        </p>
        <div className="space-y-3">
          {FINALIZE_STAGES.map((stage) => (
            <StageCard key={stage.number} stage={stage} variant="accent" />
          ))}
        </div>
      </section>

      {/* Always Running */}
      <section id="always-running">
        <h2 className="text-2xl font-semibold text-text mb-4">Always Running</h2>
        <p className="text-text-muted leading-relaxed mb-6">
          The file watcher detects changes and triggers incremental rebuilds. Sync stages re-run in seconds.
          Enrich and Finalize queue in the background. Your agents always get fresh structural context.
        </p>
        <div className="rounded-lg border border-border bg-surface p-5 flex items-start gap-4">
          <div className="text-primary flex-shrink-0 mt-0.5"><RefreshCw className="w-5 h-5" /></div>
          <div>
            <h3 className="font-medium text-sm text-text mb-1">Incremental Rebuilds</h3>
            <p className="text-sm text-text-muted">
              Only changed files re-enter the pipeline. The graph is patched, not rebuilt from scratch.
              Hub files and structural relationships update in real time.
            </p>
          </div>
        </div>
      </section>
    </DetailPageLayout>
  );
}
