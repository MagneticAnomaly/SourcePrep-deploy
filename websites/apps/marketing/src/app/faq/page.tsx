"use client";

import { useState, type ReactNode } from 'react';
import { ChevronDown, ArrowRight } from 'lucide-react';

interface FAQItem {
  id: string;
  q: string;
  a: ReactNode;
}

const faqs: FAQItem[] = [
  {
    id: "context-window",
    q: "Won't this just use up my whole context window?",
    a: (
      <div className="space-y-4">
        <p><strong>No.</strong> CoDRAG&apos;s default output is <strong>~1,500 tokens</strong> (6,000 characters). With trace expansion enabled, it&apos;s ~2,000 tokens.</p>
        <div className="overflow-x-auto">
          <table className="text-sm w-full border-collapse">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left py-2 pr-6 text-text font-semibold">What</th>
                <th className="text-left py-2 text-text font-semibold">Tokens</th>
              </tr>
            </thead>
            <tbody className="text-text-muted">
              <tr className="border-b border-border-subtle"><td className="py-2 pr-6">CoDRAG default context</td><td>~1,500</td></tr>
              <tr className="border-b border-border-subtle"><td className="py-2 pr-6">CoDRAG + trace expansion</td><td>~2,000</td></tr>
              <tr className="border-b border-border-subtle"><td className="py-2 pr-6">Cursor&apos;s default chat cap</td><td>~20,000</td></tr>
              <tr className="border-b border-border-subtle"><td className="py-2 pr-6">Claude Code usable window</td><td>~140,000</td></tr>
              <tr className="border-b border-border-subtle"><td className="py-2 pr-6">GPT-4o full window</td><td>128,000</td></tr>
              <tr><td className="py-2 pr-6">Claude 3.5 Sonnet full window</td><td>200,000</td></tr>
            </tbody>
          </table>
        </div>
        <p>CoDRAG typically consumes <strong>1–3% of your available context window.</strong> CoDRAG is designed to be a <em>precision instrument</em>, not a firehose — it sends the 5 most relevant code chunks under a hard character ceiling, not your entire codebase.</p>
      </div>
    ),
  },
  {
    id: "saturation",
    q: "How much context is too much? Is there a number?",
    a: (
      <div className="space-y-4">
        <p>Yes, and it&apos;s lower than you&apos;d think. Research consistently shows that <strong>RAG context saturates between 4K and 16K tokens</strong> depending on the model. After that, adding more context produces diminishing returns — and eventually <em>hurts</em> performance.</p>
        <div className="overflow-x-auto">
          <table className="text-sm w-full border-collapse">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left py-2 pr-6 text-text font-semibold">Model</th>
                <th className="text-left py-2 text-text font-semibold">Saturation Point</th>
              </tr>
            </thead>
            <tbody className="text-text-muted">
              <tr className="border-b border-border-subtle"><td className="py-2 pr-6">Mixtral-8x7B</td><td>~4K tokens</td></tr>
              <tr className="border-b border-border-subtle"><td className="py-2 pr-6">GPT-4-turbo</td><td>~16K tokens</td></tr>
              <tr className="border-b border-border-subtle"><td className="py-2 pr-6">Claude 3.5 Sonnet</td><td>~32K tokens</td></tr>
              <tr><td className="py-2 pr-6">Llama-3.1-8B</td><td>30K tokens causes <strong>24% accuracy drop</strong></td></tr>
            </tbody>
          </table>
        </div>
        <p className="bg-warning/10 border border-warning/30 rounded-lg p-4 text-sm">The most surprising finding: <strong>even when the model can perfectly retrieve the answer from the context, its reasoning accuracy still degrades as input length increases.</strong> This was demonstrated with whitespace padding — literally adding blank lines degrades reasoning. The problem isn&apos;t distraction, it&apos;s distance.</p>
        <p>CoDRAG&apos;s defaults (1,500–2,000 tokens) sit well below every known saturation point.</p>
      </div>
    ),
  },
  {
    id: "already-indexed",
    q: "Doesn't my AI tool (Cursor, Windsurf, Claude Code) already index my codebase?",
    a: (
      <div className="space-y-6">
        <p><strong>Yes — and CoDRAG doesn&apos;t replace that.</strong> All three tools solve the basic problem of &quot;find relevant code and inject it.&quot; CoDRAG uses the same foundational technique (embed → cosine similarity → top-K) for core retrieval. <strong>We are not reinventing that wheel.</strong></p>
        <div>
          <p className="font-semibold text-text mb-3">What CoDRAG adds on top:</p>
          <div className="overflow-x-auto">
            <table className="text-sm w-full border-collapse">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left py-2 pr-6 text-text font-semibold">Capability</th>
                  <th className="text-center py-2 px-3 text-text font-semibold">Cursor</th>
                  <th className="text-center py-2 px-3 text-text font-semibold">Windsurf</th>
                  <th className="text-center py-2 px-3 text-text font-semibold">Claude Code</th>
                  <th className="text-center py-2 px-3 text-primary font-semibold">CoDRAG</th>
                </tr>
              </thead>
              <tbody className="text-text-muted">
                {[
                  ["Trace graph (imports, calls, inheritance)", "No", "No", "No", "Yes"],
                  ['Structural expansion (\u201cwhat calls this?\u201d)', "No", "No", "No", "Yes"],
                  ["Role weights (code vs docs vs tests)", "No", "No", "No", "Yes"],
                  ["Path weights (per-directory relevance)", "No", "No", "No", "Yes"],
                  ["Intent detection (query → weight adjustment)", "No", "No", "No", "Yes"],
                  ["Context compression (CLaRa)", "No", "No", "No", "Yes"],
                  ["Transparency (scores, chunks, what was sent)", "No", "No", "Partial", "Yes"],
                  ["Works across all tools (MCP standard)", "—", "—", "—", "Yes"],
                ].map(([cap, cursor, windsurf, claude, codrag]) => (
                  <tr key={cap as string} className="border-b border-border-subtle">
                    <td className="py-2 pr-6">{cap}</td>
                    <td className="text-center py-2 px-3">{cursor}</td>
                    <td className="text-center py-2 px-3">{windsurf}</td>
                    <td className="text-center py-2 px-3">{claude}</td>
                    <td className="text-center py-2 px-3 text-primary font-semibold">{codrag}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    ),
  },
  {
    id: "trace-dump",
    q: "Does the trace graph get dumped into my context?",
    a: (
      <div className="space-y-4">
        <p><strong>No. Never.</strong> The trace graph for even a small project (~40 Python files) is <strong>547 nodes and 656 edges</strong>. Dumping that raw would be ~68,000 tokens — research shows this would <em>catastrophically</em> degrade LLM performance.</p>
        <p>Instead, CoDRAG uses the trace graph as a <strong>navigation structure</strong>:</p>
        <ol className="list-decimal list-inside space-y-2 text-text-muted">
          <li>Semantic search finds the 5 most relevant chunks</li>
          <li>If <code className="bg-surface px-1.5 py-0.5 rounded text-xs border border-border-subtle">trace_expand</code> is on, CoDRAG follows the graph edges to find structurally related code</li>
          <li>Those related chunks are added under a <strong>separate 2,000-character budget</strong></li>
          <li>Total trace contribution: ~500 additional tokens</li>
        </ol>
        <p className="text-text-muted text-sm italic">Think of it as using Google Maps to find directions vs. printing out every road in the city. CoDRAG reads the map, gives you just the route.</p>
      </div>
    ),
  },
  {
    id: "weights",
    q: "If I set a file's weight to 0.5, does that save context space?",
    a: (
      <div className="space-y-4">
        <p><strong>No.</strong> Path weights change <em>ranking</em>, not <em>volume</em>. A file weighted 0.5 is less likely to appear in the top results — but if it&apos;s so relevant it still ranks, it takes up the exact same space as any other chunk.</p>
        <p className="font-semibold text-text">To control how much context is sent, use these knobs:</p>
        <div className="overflow-x-auto">
          <table className="text-sm w-full border-collapse">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left py-2 pr-6 text-text font-semibold">Want less context?</th>
                <th className="text-left py-2 text-text font-semibold">Do this</th>
              </tr>
            </thead>
            <tbody className="text-text-muted">
              <tr className="border-b border-border-subtle"><td className="py-2 pr-6">Fewer chunks</td><td>Lower <code className="bg-surface px-1 rounded border border-border-subtle text-xs">k</code> (default: 5)</td></tr>
              <tr className="border-b border-border-subtle"><td className="py-2 pr-6">Smaller total output</td><td>Lower <code className="bg-surface px-1 rounded border border-border-subtle text-xs">max_chars</code> (default: 6,000)</td></tr>
              <tr className="border-b border-border-subtle"><td className="py-2 pr-6">Stricter relevance filter</td><td>Raise <code className="bg-surface px-1 rounded border border-border-subtle text-xs">min_score</code> (default: 0.15)</td></tr>
              <tr><td className="py-2 pr-6">Compress what&apos;s sent</td><td>Enable <code className="bg-surface px-1 rounded border border-border-subtle text-xs">compression: "clara"</code></td></tr>
            </tbody>
          </table>
        </div>
        <p className="text-text-muted">Path weights are a <strong className="text-text">relevance tool</strong> — they shape <em>what</em> gets sent, not <em>how much</em>.</p>
      </div>
    ),
  },
  {
    id: "lost-in-middle",
    q: "What\u2019s the \u201clost in the middle\u201d problem? Should I worry about it?",
    a: (
      <div className="space-y-4">
        <p>&quot;Lost in the middle&quot; (Liu et al., 2023) is a well-documented phenomenon: LLMs pay the most attention to the <strong>beginning and end</strong> of their context window, and systematically under-utilize information in the middle.</p>
        <p><strong>Should you worry?</strong> Less than you think — CoDRAG already mitigates it:</p>
        <ul className="space-y-2 text-text-muted">
          <li><strong className="text-text">Most relevant first.</strong> CoDRAG sorts chunks by descending relevance score. The highest-scoring chunk is at the top — exactly where models pay the most attention.</li>
          <li><strong className="text-text">Small context volume.</strong> At 1,500–2,000 tokens, CoDRAG&apos;s output is short enough that there <em>isn&apos;t</em> a meaningful &quot;middle&quot; to get lost in. The problem primarily affects contexts &gt;10K tokens.</li>
          <li><strong className="text-text">Trace chunks are appended last.</strong> Structurally related trace chunks go at the end — the other position where models pay strong attention.</li>
        </ul>
      </div>
    ),
  },
  {
    id: "paste-codebase",
    q: "Can't I just paste my whole codebase into Claude with its 200K window?",
    a: (
      <div className="space-y-4">
        <p>You can. It will work worse than you expect.</p>
        <p>Chen et al. (2025) demonstrated that even with <strong>perfect retrieval</strong> — the model can literally recite the evidence verbatim — reasoning accuracy drops 13.9% to 85% as input length increases. This was tested on math, QA, and <em>coding tasks</em> specifically.</p>
        <p>Chroma Research (2025) tested 18 current LLMs and found that <strong>even on trivial retrieval tasks</strong>, performance degrades non-uniformly with input length. This includes Claude Sonnet 4, GPT-4o, and Gemini 2.5 — the latest models with the biggest windows.</p>
        <p className="bg-surface border border-border rounded-lg p-4 text-sm text-text-muted italic">A 200K window can hold ~300 pages. But a human doesn&apos;t read better by having 300 irrelevant pages open on their desk. Neither does an LLM.</p>
        <p>CoDRAG&apos;s approach — find the 5 best chunks, optionally follow structural relationships, deliver ~2K tokens of high-signal context — aligns with the research recommendation of &quot;Retrieve then Solve.&quot;</p>
      </div>
    ),
  },
  {
    id: "not-enough",
    q: "What if CoDRAG's 5 chunks aren't enough?",
    a: (
      <div className="space-y-4">
        <p>This is a real concern. Here&apos;s how to address it:</p>
        <div className="overflow-x-auto">
          <table className="text-sm w-full border-collapse">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left py-2 pr-6 text-text font-semibold">Adjustment</th>
                <th className="text-left py-2 text-text font-semibold">When to use</th>
              </tr>
            </thead>
            <tbody className="text-text-muted">
              <tr className="border-b border-border-subtle"><td className="py-2 pr-6"><code className="bg-surface px-1 rounded border border-border-subtle text-xs">k: 8</code></td><td>Want broader coverage across files</td></tr>
              <tr className="border-b border-border-subtle"><td className="py-2 pr-6"><code className="bg-surface px-1 rounded border border-border-subtle text-xs">trace_expand: true</code></td><td>Need structural relationships (what calls this?)</td></tr>
              <tr className="border-b border-border-subtle"><td className="py-2 pr-6"><code className="bg-surface px-1 rounded border border-border-subtle text-xs">max_chars: 10000</code></td><td>Complex multi-file question</td></tr>
              <tr className="border-b border-border-subtle"><td className="py-2 pr-6"><code className="bg-surface px-1 rounded border border-border-subtle text-xs">compression: "clara"</code></td><td>Same info, fewer tokens</td></tr>
              <tr><td className="py-2 pr-6"><code className="bg-surface px-1 rounded border border-border-subtle text-xs">max_chars: 15000+</code></td><td>Rarely — verify it actually helps</td></tr>
            </tbody>
          </table>
        </div>
        <p className="text-text-muted text-sm"><strong className="text-text">First:</strong> increase K before increasing max_chars. Getting 8 diverse chunks is usually better than getting 5 longer chunks.</p>
      </div>
    ),
  },
  {
    id: "just-rag",
    q: "Is this just another RAG tool?",
    a: (
      <div className="space-y-4">
        <p>CoDRAG&apos;s <em>foundation</em> is RAG — embed, search, retrieve. That&apos;s the same technique Cursor, Windsurf, and most modern tools use internally.</p>
        <p>What makes CoDRAG different is what happens <strong>on top of</strong> basic retrieval:</p>
        <ul className="space-y-3 text-text-muted">
          <li><strong className="text-text">Graph-aware retrieval.</strong> The trace graph (built by a Rust engine that parses your code&apos;s AST) captures imports, function calls, class inheritance, and module dependencies. No other AI coding tool does this natively.</li>
          <li><strong className="text-text">Intent-aware weighting.</strong> CoDRAG detects whether your query is about implementation, debugging, or architecture and adjusts which types of content are prioritized. Automated — not something you configure per query.</li>
          <li><strong className="text-text">User transparency and control.</strong> Every other tool is a black box. CoDRAG shows you the scores, lets you set weights, and tells you exactly what was sent and why.</li>
          <li><strong className="text-text">Tool-agnostic via MCP.</strong> Your index, configuration, and codebase understanding work whether you&apos;re in Cursor today or Claude Code tomorrow.</li>
          <li><strong className="text-text">Context compression.</strong> The CLaRa sidecar can distill context by 30–70%, sending the same semantic information in fewer tokens.</li>
        </ul>
      </div>
    ),
  },
  {
    id: "cloud-upload",
    q: "Is my code uploaded to the cloud?",
    a: (
      <div className="space-y-4">
        <p><strong>No.</strong> CoDRAG is local-first software. All indexing, vector storage, and processing happens on your machine. The only time data leaves your machine is if you explicitly configure a cloud LLM (BYOK) or during the one-time license activation check.</p>
      </div>
    ),
  },
  {
    id: "editor-support",
    q: "Which editors does it work with?",
    a: (
      <div className="space-y-4">
        <p>CoDRAG works best with editors that support the <strong>Model Context Protocol (MCP)</strong> — currently <strong>Cursor</strong>, <strong>Windsurf</strong>, and <strong>Claude Desktop</strong>. A VS Code extension is in development.</p>
        <p>For other editors, you can copy-paste context from the Dashboard or use the CLI directly.</p>
      </div>
    ),
  },
  {
    id: "gpu-requirement",
    q: "Do I need a GPU?",
    a: (
      <div className="space-y-4">
        <p><strong>No.</strong> Core features (indexing, trace graph, search) run efficiently on CPU. The built-in embedding model is quantized and optimized for CPU inference.</p>
        <p>However, if you enable <strong>CLaRa compression</strong> locally, a GPU (NVIDIA or Apple Silicon) is highly recommended for reasonable latency.</p>
      </div>
    ),
  },
];

function FAQAccordionItem({ item, isOpen, onToggle }: { item: FAQItem; isOpen: boolean; onToggle: () => void }) {
  return (
    <div className="border border-border rounded-lg overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between px-6 py-5 text-left bg-surface hover:bg-surface-raised transition-colors gap-4"
        aria-expanded={isOpen}
      >
        <span className="font-semibold text-text text-base leading-snug">{item.q}</span>
        <ChevronDown
          className={`w-5 h-5 text-text-muted flex-shrink-0 transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`}
        />
      </button>
      {isOpen && (
        <div className="px-6 py-5 border-t border-border bg-background text-text-muted leading-relaxed">
          {item.a}
        </div>
      )}
    </div>
  );
}

export default function FAQPage() {
  const [openId, setOpenId] = useState<string | null>("context-window");

  const toggle = (id: string) => setOpenId(openId === id ? null : id);

  return (
    <div className="min-h-screen bg-background text-text">
      <div className="mx-auto max-w-3xl px-4 sm:px-6 lg:px-8 py-16">
        {/* Header */}
        <div className="text-center mb-16">
          <p className="text-sm font-semibold uppercase tracking-widest text-primary mb-3">Frequently Asked Questions</p>
          <h1 className="text-4xl font-bold tracking-tight text-text sm:text-5xl mb-4">
            Context, tokens, and how CoDRAG actually works
          </h1>
          <p className="text-lg text-text-muted max-w-xl mx-auto">
            Answers about token budgets, context quality, and how CoDRAG fits alongside the tools you already use.
          </p>
        </div>

        {/* Accordion */}
        <div className="space-y-3">
          {faqs.map((item) => (
            <FAQAccordionItem
              key={item.id}
              item={item}
              isOpen={openId === item.id}
              onToggle={() => toggle(item.id)}
            />
          ))}
        </div>

        {/* Bottom CTA */}
        <div className="mt-16 rounded-2xl border border-border bg-surface p-8 text-center">
          <h2 className="text-xl font-bold text-text mb-2">Still have questions?</h2>
          <p className="text-text-muted mb-6 text-sm">
            Open an issue, ask in the community, or read the research behind these answers.
          </p>
          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <a
              href="https://github.com/EricBintner/CoDRAG/discussions"
              className="inline-flex items-center justify-center gap-2 rounded-md border border-border bg-background px-5 py-2.5 text-sm font-medium text-text hover:bg-surface transition-colors"
            >
              Ask the Community
            </a>
            <a
              href="https://docs.codrag.io"
              className="inline-flex items-center justify-center gap-2 rounded-md bg-primary px-5 py-2.5 text-sm font-semibold text-white hover:bg-primary-hover transition-colors"
            >
              Read the Docs <ArrowRight className="w-4 h-4" />
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
