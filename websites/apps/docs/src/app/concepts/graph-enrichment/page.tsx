"use client";

import { useEffect, useState } from 'react';
import {
  Zap, Brain, GitBranch, CheckCircle, BookOpen, Layers, Network, Map, Cpu,
  Sparkles, RefreshCw, FileText, Lightbulb, ClipboardCheck, Shield, ArrowLeft,
} from 'lucide-react';
import { AnchorHeading } from '../../../components/AnchorHeading';

const SECTIONS = [
  { id: 'journey',          label: 'The Journey' },
  { id: 'sync',             label: 'Sync (1–5)' },
  { id: 'enrich',           label: 'Enrich (6–10)' },
  { id: 'finalize',         label: 'Finalize (11–15)' },
  { id: 'always-running',   label: 'Always Running' },
  { id: 'understanding',    label: 'Understanding Score' },
  { id: 'decay',            label: 'Score Decay' },
  { id: 'doc-mining',       label: 'Documentation Mining' },
  { id: 'why-it-matters',   label: 'Why It Matters' },
  { id: 'research',         label: 'Research Foundation' },
];

const SYNC_STAGES = [
  { number: 1,  name: 'STRUCTURAL',     icon: <GitBranch className="w-4 h-4" />,    description: 'Parses every file via tree-sitter. Extracts imports, symbols, call sites. Builds the trace graph in seconds.' },
  { number: 2,  name: 'INFERRED_EDGES', icon: <Network className="w-4 h-4" />,      description: 'Finds edges static parsing misses — cross-language API calls, dynamic dispatch, interface satisfaction, implicit dependencies. Confidence-scored; never overrides parser-derived edges.' },
  { number: 3,  name: 'CATALOGUE',      icon: <BookOpen className="w-4 h-4" />,     description: 'A one-line summary and tags for every file. The longest single Sync stage on a fresh index — runs while structural context is already serving your agent.' },
  { number: 4,  name: 'VALIDATION',     icon: <CheckCircle className="w-4 h-4" />,  description: 'Integrity check. Verifies graph consistency, flags orphan nodes, discards hallucinated edges.' },
  { number: 5,  name: 'KNOWLEDGE',      icon: <Zap className="w-4 h-4" />,          description: 'The catalogued graph becomes searchable. Deeper enrichment happens next, in Enrich.' },
];

const ENRICH_STAGES = [
  { number: 6,  name: 'DEEP_REASONING',   icon: <Brain className="w-4 h-4" />,     description: 'Epistemic scoring — layers, domains, confidence ratings for every node in graph context.' },
  { number: 7,  name: 'GROUP_REASONING',  icon: <Cpu className="w-4 h-4" />,       description: 'LLM consensus across related nodes. Identifies patterns and architectural themes.' },
  { number: 8,  name: 'MODULE_SYNTHESIS', icon: <Layers className="w-4 h-4" />,    description: 'Module boundary discovery. Groups files into logical subsystems.' },
  { number: 9,  name: 'DEEPENING',        icon: <Sparkles className="w-4 h-4" />,  description: 'Iterative epistemic refinement with full graph context available.' },
  { number: 10, name: 'DEEP_KNOWLEDGE',   icon: <Brain className="w-4 h-4" />,     description: 'Re-embed everything with enriched data. The search index now reflects deep understanding.' },
];

const FINALIZE_STAGES = [
  { number: 11, name: 'ATLAS',      icon: <Map className="w-4 h-4" />,            description: 'Generates the architectural overview — segments, hub files, cross-cutting concerns, workspace map.' },
  { number: 12, name: 'RULES',      icon: <FileText className="w-4 h-4" />,       description: 'Generates IDE rules files — AGENTS.md, .cursor/, .windsurf/ — so your editors know about the MCP tools.' },
  { number: 13, name: 'CONCEPTS',   icon: <Lightbulb className="w-4 h-4" />,      description: 'Seeds concepts from atlas, modules, and audit findings. The "why" behind the architecture.' },
  { number: 14, name: 'AUDIT',      icon: <ClipboardCheck className="w-4 h-4" />, description: 'Runs structural analyzers — coupling hotspots, import cycles, hub concentration, quality gaps.' },
  { number: 15, name: 'ANTIBODIES', icon: <Shield className="w-4 h-4" />,         description: 'Derives immune system defenses from concept assertions. Constraint violations surface as alerts.' },
];

function StageCard({ stage, variant }: { stage: typeof SYNC_STAGES[number]; variant: 'light' | 'primary' | 'accent' }) {
  const styles = {
    light:   'border-border bg-surface',
    primary: 'border-primary/30 bg-primary/5',
    accent:  'border-[#3fb950]/30 bg-[#3fb950]/5',
  };
  const badgeStyles = {
    light:   'bg-background border-border text-text-muted',
    primary: 'bg-background border-primary/30 text-primary',
    accent:  'bg-background border-[#3fb950]/30 text-[#3fb950]',
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

/** Referrer-aware back-link: marketing → marketing, docs → docs (default). */
function BackLink() {
  const [target, setTarget] = useState<{ href: string; label: string }>({
    href: '/',
    label: 'Back to Docs',
  });

  useEffect(() => {
    if (typeof document === 'undefined') return;
    const ref = document.referrer;
    if (!ref) return;
    try {
      const url = new URL(ref);
      // Marketing site (sourceprep.io apex, NOT docs.sourceprep.io subdomain)
      if (url.hostname === 'sourceprep.io' || url.hostname === 'www.sourceprep.io') {
        setTarget({ href: 'https://sourceprep.io', label: 'Back to sourceprep.io' });
      } else if (url.hostname === 'localhost' && url.port === '3000') {
        // Local marketing dev server.
        setTarget({ href: 'http://localhost:3000', label: 'Back to sourceprep.io' });
      }
    } catch {
      /* invalid referrer URL — keep default */
    }
  }, []);

  return (
    <a href={target.href} className="text-sm text-text-muted hover:text-primary transition-colors inline-flex items-center gap-2">
      <ArrowLeft className="w-3 h-3" /> {target.label}
    </a>
  );
}

export default function Page() {
  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto max-w-7xl px-6 pb-16 pt-0">

        <div className="pb-6 mb-8 border-b border-border">
          <BackLink />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12">

          {/* Sticky section sidebar */}
          <div className="lg:col-span-3">
            <div className="sticky top-20 space-y-8">
              <div>
                <p className="text-xs font-mono font-bold uppercase tracking-widest text-primary mb-3">How It Works</p>
                <h1 className="text-3xl font-bold tracking-tight text-text">Graph Enrichment</h1>
                <p className="mt-3 text-sm text-text-muted leading-relaxed">
                  SourcePrep learns how your code actually connects — not just what words appear where. A 15-stage
                  pipeline turns raw source files into a living knowledge graph your AI can reason over: fast
                  structural parsing first, then deeper reasoning about meaning, and finally the guides, rules, and
                  safeguards your tools consume.
                </p>
              </div>

              <nav className="space-y-1 border-l border-border-subtle">
                {SECTIONS.map((section) => (
                  <a
                    key={section.id}
                    href={`#${section.id}`}
                    className="block pl-4 py-2 text-sm text-text-muted hover:text-primary hover:border-l-2 hover:border-primary hover:bg-surface transition-all -ml-[1px]"
                  >
                    {section.label}
                  </a>
                ))}
              </nav>
            </div>
          </div>

          {/* Main content */}
          <div className="lg:col-span-9 space-y-16">

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
                Runs in the background with full LLM passes. Each stage builds on the previous, producing
                progressively richer structural understanding. Supports swarm mode — multiple LLM workers
                processing nodes in parallel.
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
                Produces the deliverables your tools actually consume — the atlas document, IDE rules files, seeded
                concepts, audit findings, and immune system defenses. Most of these run in parallel once the atlas
                is ready; the safeguards are derived from your recorded concepts last.
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

            {/* ── Docs-side depth — preserved from the previous page ─────────── */}

            <section id="understanding">
              <AnchorHeading id="understanding" level="h2">The Understanding Score</AnchorHeading>
              <p className="mt-3 text-text-muted leading-relaxed">
                Every node in the graph gets an <span className="font-semibold text-text">understanding score</span> (0.0–1.0)
                — internally called the <em>epistemic score</em> — that represents how well the trace comprehends
                this node in the context of the entire codebase. This is fundamentally different from search
                relevance or summary accuracy. A file can have a perfect summary but a low understanding score
                if we don&apos;t know how it connects to anything else.
              </p>
              <p className="mt-3 text-text-muted leading-relaxed">The score is a weighted composite of six dimensions:</p>
              <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="p-3 bg-surface border border-border rounded-lg">
                  <div className="text-sm font-semibold text-text">Summary confidence <span className="text-xs text-text-muted">(20%)</span></div>
                  <div className="text-xs text-text-muted">How certain is the catalogue model about its own output?</div>
                </div>
                <div className="p-3 bg-surface border border-border rounded-lg">
                  <div className="text-sm font-semibold text-text">Validation depth <span className="text-xs text-text-muted">(15%)</span></div>
                  <div className="text-xs text-text-muted">Has a larger model verified and enriched the summary?</div>
                </div>
                <div className="p-3 bg-surface border border-border rounded-lg">
                  <div className="text-sm font-semibold text-text">Neighbor coverage <span className="text-xs text-text-muted">(20%)</span></div>
                  <div className="text-xs text-text-muted">Are connected nodes also enriched? Understanding is relational.</div>
                </div>
                <div className="p-3 bg-surface border border-border rounded-lg">
                  <div className="text-sm font-semibold text-text">Cross-reference density <span className="text-xs text-text-muted">(15%)</span></div>
                  <div className="text-xs text-text-muted">How many doc↔code bidirectional links exist?</div>
                </div>
                <div className="p-3 bg-surface border border-border rounded-lg">
                  <div className="text-sm font-semibold text-text">Enrichment depth <span className="text-xs text-text-muted">(15%)</span></div>
                  <div className="text-xs text-text-muted">How many reasoning passes has this node been through?</div>
                </div>
                <div className="p-3 bg-surface border border-border rounded-lg">
                  <div className="text-sm font-semibold text-text">Temporal currency <span className="text-xs text-text-muted">(15%)</span></div>
                  <div className="text-xs text-text-muted">Has the source changed since enrichment? Stale knowledge scores zero.</div>
                </div>
              </div>
            </section>

            <section id="decay">
              <AnchorHeading id="decay" level="h2">Score Decay — Knowledge Has a Half-Life</AnchorHeading>
              <p className="mt-3 text-text-muted leading-relaxed">
                Understanding scores aren&apos;t static. They <span className="font-semibold text-text">decay</span> when the world
                changes around a node — because in epistemology, knowledge that hasn&apos;t been re-verified against
                current evidence is no longer justified belief.
              </p>
              <div className="mt-4 overflow-x-auto">
                <table className="text-sm w-full border-collapse">
                  <thead>
                    <tr className="border-b border-border text-left text-text">
                      <th className="py-2 pr-4 font-medium text-text">Event</th>
                      <th className="py-2 pr-4 font-medium text-text">Effect</th>
                      <th className="py-2 font-medium text-text">Rationale</th>
                    </tr>
                  </thead>
                  <tbody className="text-text-muted">
                    <tr className="border-b border-border/50"><td className="py-2 pr-4">Source file changed</td><td className="py-2 pr-4">Score → 0.0</td><td className="py-2">Everything might be wrong</td></tr>
                    <tr className="border-b border-border/50"><td className="py-2 pr-4">Neighbor re-enriched</td><td className="py-2 pr-4">Score × 0.95</td><td className="py-2">Context shifted slightly</td></tr>
                    <tr className="border-b border-border/50"><td className="py-2 pr-4">Referenced doc updated</td><td className="py-2 pr-4">Score × 0.90</td><td className="py-2">Documentation changed, claims may be invalid</td></tr>
                    <tr className="border-b border-border/50"><td className="py-2 pr-4">Trace rebuilt (structural)</td><td className="py-2 pr-4">Score × 0.80</td><td className="py-2">Edges changed, relationships may differ</td></tr>
                    <tr><td className="py-2 pr-4">Module re-synthesized</td><td className="py-2 pr-4">Score × 0.97</td><td className="py-2">Module understanding refined</td></tr>
                  </tbody>
                </table>
              </div>
              <p className="mt-3 text-text-muted leading-relaxed">
                Decay cascades through neighbors: if File A changes, File B (which imports A) decays slightly,
                and File C (which imports B) decays even less — up to a 3-hop propagation limit. Nodes with
                decayed scores enter a re-analysis queue ordered by score (lowest first); the Deepening stage
                processes this queue until the graph converges or the token budget is exhausted.
              </p>
            </section>

            <section id="doc-mining">
              <AnchorHeading id="doc-mining" level="h2">Documentation Mining</AnchorHeading>
              <p className="mt-3 text-text-muted leading-relaxed">
                Most indexing tools treat <code>.md</code> files as flat text blobs. SourcePrep extracts structure
                from documentation: section headers, code references, status markers, and cross-links. This enables:
              </p>
              <ul className="mt-3 list-disc pl-5 space-y-1 text-text-muted">
                <li><span className="font-semibold text-text">Doc↔code links</span> — docs reference code files and vice versa</li>
                <li><span className="font-semibold text-text">Staleness detection</span> — a doc referencing a renamed file is flagged as drifted</li>
                <li><span className="font-semibold text-text">Decision tracking</span> — architecture decisions and their outcomes are captured</li>
                <li><span className="font-semibold text-text">Orphan detection</span> — docs with no code references or incoming links are identified</li>
              </ul>
            </section>

            <section id="why-it-matters">
              <AnchorHeading id="why-it-matters" level="h2">Why This Matters in Practice</AnchorHeading>
              <p className="mt-4 text-sm text-text-muted bg-info/10 border-l-4 border-info p-4 rounded-r">
                <span className="font-semibold text-text">Without enrichment:</span> asking your AI &quot;how does the ad framework work?&quot;
                might return one file that mentions &quot;ad&quot;.
              </p>
              <p className="mt-3 text-sm text-text-muted bg-success/10 border-l-4 border-success p-4 rounded-r">
                <span className="font-semibold text-text">With enrichment:</span> the same query returns the module summary, the 6 files
                that compose the subsystem, their entry points, the 3 docs that describe the architecture, and a
                flag that one doc references a renamed file. The understanding score tells the AI that the framework
                is well understood, but one file&apos;s score has decayed because one neighbor was recently modified
                and hasn&apos;t been re-analyzed yet.
              </p>
              <p className="mt-3 text-text-muted leading-relaxed">
                The difference isn&apos;t just better search results. It&apos;s the difference between a tool that
                <em> retrieves</em> and a tool that <em>understands</em> — and knows the boundary between the two.
              </p>
            </section>

            <section id="research">
              <AnchorHeading id="research" level="h2">Research Foundation</AnchorHeading>
              <p className="mt-3 text-text-muted leading-relaxed">
                The pipeline draws on peer-reviewed research in knowledge graph construction, code intelligence,
                and probabilistic reasoning:
              </p>
              <ul className="mt-3 list-disc pl-5 space-y-1 text-sm text-text-muted">
                <li>Hierarchical graph + community summaries — <em>Microsoft GraphRAG (2024)</em></li>
                <li>LLM → validator multi-agent enrichment — <em>KARMA (2025)</em></li>
                <li>AST → code knowledge graph — <em>KG-based Repo-Level Code Gen (2025)</em></li>
                <li>Bottom-up topological enrichment — <em>RepoAgent, EMNLP 2024</em></li>
                <li>Iterative convergence via residual scheduling — <em>Belief Propagation (Pearl 1988, Yedidia 2003)</em></li>
                <li>Score decay and re-enrichment — inspired by <em>epistemic logic</em> and <em>truth-maintenance systems (Doyle 1979)</em></li>
              </ul>
            </section>

          </div>
        </div>
      </div>
    </main>
  );
}
