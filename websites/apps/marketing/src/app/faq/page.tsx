"use client";

import { useState, type ReactNode } from 'react';
import { ChevronDown, ArrowRight, HelpCircle, Lightbulb } from 'lucide-react';

interface FAQItem {
  id: string;
  q: string;
  a: ReactNode;
}

const faqs: FAQItem[] = [
  {
    id: "persistent-memory",
    q: "Does the AI remember what it learned about my code in previous sessions?",
    a: (
      <div className="space-y-4">
        <p><strong>Yes</strong> — and this is where CoDRAG diverges from every other context tool on the market. CoDRAG maintains a <strong>Persistent Agent Memory</strong>: a local store of observations — architectural decisions, discovered bugs, design patterns, working assumptions — each linked directly to specific files and symbols in your codebase.</p>
        <p>What makes this different from bolting a memory file onto your repo: CoDRAG&apos;s observations are <strong>staleness-aware</strong>. Modify <code className="bg-surface px-1.5 py-0.5 rounded text-xs border border-border-subtle">auth.py</code> and every observation tied to that file is automatically flagged <code className="bg-surface px-1.5 py-0.5 rounded text-xs border border-border-subtle">[STALE]</code>. In the next session, the AI receives both the updated code <em>and</em> a signal that its prior assumptions may no longer hold. It doesn&apos;t blindly repeat outdated notes — it knows to re-evaluate.</p>
        <p>This is not a prompt cache or a conversation log. It&apos;s a structured, file-linked, searchable knowledge layer that the AI maintains about your specific codebase. It works on <strong>every tier, including Free</strong> — it&apos;s local SQLite, zero cloud cost, zero telemetry. And because observations are injected alongside code context (not dumped in bulk), they respect the same tight token budget as everything else.</p>
      </div>
    ),
  },
  {
    id: "stale-context",
    q: "My code changes constantly. Does the AI just get stale context?",
    a: (
      <div className="space-y-4">
        <p>This is the central challenge of any indexing tool, and CoDRAG takes it more seriously than most. Three mechanisms work together:</p>
        <ol className="list-decimal list-inside space-y-3 text-text-muted">
          <li><strong className="text-text">Incremental re-indexing.</strong> CoDRAG tracks file hashes at the individual symbol level. When you edit a file, only the affected chunks are re-embedded — not the entire project. A real-time file watcher detects changes within seconds.</li>
          <li><strong className="text-text">Automatic observation staleness.</strong> CoDRAG&apos;s Persistent Agent Memory links observations to files. When a file changes, those observations are flagged <code className="bg-surface px-1 rounded border border-border-subtle text-xs">[STALE]</code> — the AI sees them with a clear warning, not as gospel.</li>
          <li><strong className="text-text">A visible health indicator.</strong> The Dashboard shows exactly which files have changed since the last index, how many are stale, and whether a rebuild is in progress. You never have to guess whether the AI&apos;s context is current.</li>
        </ol>
        <p>Most other tools stop at #1. CoDRAG is the only local context engine that extends freshness tracking all the way into the AI&apos;s own learned knowledge.</p>
      </div>
    ),
  },
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
              <tr className="border-b border-border-subtle"><td className="py-2 pr-6">Cursor default chat cap</td><td>~20,000</td></tr>
              <tr className="border-b border-border-subtle"><td className="py-2 pr-6">GPT-5.3 (OpenAI)</td><td>400,000</td></tr>
              <tr className="border-b border-border-subtle"><td className="py-2 pr-6">Claude Sonnet 4 / Opus 4.6 (standard)</td><td>200,000</td></tr>
              <tr className="border-b border-border-subtle"><td className="py-2 pr-6">Claude Sonnet 4.5 / Opus 4.6 (extended beta)</td><td>1,000,000</td></tr>
              <tr className="border-b border-border-subtle"><td className="py-2 pr-6">Gemini 3 Pro (Google)</td><td>1,000,000–2,000,000</td></tr>
              <tr><td className="py-2 pr-6">Qwen3-Coder-480B (local / open)</td><td>256,000 native · 1M extrapolated</td></tr>
            </tbody>
          </table>
        </div>
        <p>CoDRAG typically consumes <strong>under 1% of your available context window</strong> on any 2026 frontier model. It is designed to be a <em>precision instrument</em>, not a firehose — it sends the 5 most relevant code chunks under a hard character ceiling, not your entire codebase.</p>
      </div>
    ),
  },
  {
    id: "saturation",
    q: "How much context is too much? Is there a number?",
    a: (
      <div className="space-y-4">
        <p>Yes, and it&apos;s lower than you&apos;d think — even for 2026 frontier models. Research (ICLR 2025, &quot;Long-Context LLMs Meet RAG&quot;) consistently shows that <strong>RAG context saturates between 16K and 64K tokens</strong> depending on the model. After that, adding more retrieved passages produces diminishing returns — and eventually <em>hurts</em> performance. A bigger context window does not move the saturation point.</p>
        <div className="overflow-x-auto">
          <table className="text-sm w-full border-collapse">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left py-2 pr-6 text-text font-semibold">Model</th>
                <th className="text-left py-2 text-text font-semibold">Saturation Point</th>
              </tr>
            </thead>
            <tbody className="text-text-muted">
              <tr className="border-b border-border-subtle"><td className="py-2 pr-6">GPT-5.3 (OpenAI)</td><td>~16–32K tokens — larger windows don&apos;t eliminate degradation</td></tr>
              <tr className="border-b border-border-subtle"><td className="py-2 pr-6">Claude Opus 4.6 / Sonnet 4</td><td>~32K tokens — 1M window available, but RAG accuracy still peaks early</td></tr>
              <tr className="border-b border-border-subtle"><td className="py-2 pr-6">Gemini 3 Pro</td><td>~32–64K tokens — best long-context retrieval of any frontier model</td></tr>
              <tr><td className="py-2 pr-6">Qwen3-Coder-480B (local)</td><td>~16–32K tokens — strong coder, MoE architecture, 256K native window</td></tr>
            </tbody>
          </table>
        </div>
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
                  ["Smart compression (code + docs)", "No", "No", "No", "Yes"],
                  ["Transparency (scores, chunks, what was sent)", "No", "No", "Partial", "Yes"],
                  ["Works across all tools (MCP standard)", "\u2014", "\u2014", "\u2014", "Yes"],
                  ["Persistent agent memory (cross-session)", "No", "No", "No", "Yes"],
                  ["Editor portability (Cursor, Windsurf, Claude, VS Code)", "No", "No", "No", "Yes"],
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
    id: "claude-md",
    q: "Why not just put everything in a CLAUDE.md or rules file?",
    a: (
      <div className="space-y-4">
        <p><strong>Use both.</strong> Seriously \u2014 they solve different problems and work well together.</p>
        <p>A <code className="bg-surface px-1.5 py-0.5 rounded text-xs border border-border-subtle">CLAUDE.md</code> is ideal for conventions a human can articulate: &quot;We use Tailwind,&quot; &quot;Never mutate state directly,&quot; &quot;Deploy via Terraform.&quot; That&apos;s high-level project DNA.</p>
        <p>What a rules file <em>cannot</em> do is track the 3,000+ dependency edges in a real codebase. It can&apos;t tell the AI that <code className="bg-surface px-1.5 py-0.5 rounded text-xs border border-border-subtle">PaymentService.charge()</code> calls <code className="bg-surface px-1.5 py-0.5 rounded text-xs border border-border-subtle">StripeClient.create_intent()</code> which imports <code className="bg-surface px-1.5 py-0.5 rounded text-xs border border-border-subtle">crypto.sign()</code>. It can&apos;t automatically update when someone refactors the call chain. It can&apos;t compress 200 files into 2,000 tokens of structurally meaningful context.</p>
        <p>CoDRAG automates the granular, structural layer \u2014 the connective tissue of your codebase. Your rules file handles the human intent. Together, the AI gets both &quot;what the code does&quot; and &quot;what the team wants.&quot;</p>
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
              <tr><td className="py-2 pr-6">Compress what&apos;s sent</td><td>Enable <code className="bg-surface px-1 rounded border border-border-subtle text-xs">compression: &quot;auto&quot;</code> (structural for code, language-aware for docs)</td></tr>
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
    q: "Can't I just paste my whole codebase into Claude with its 1M window?",
    a: (
      <div className="space-y-4">
        <p>You can, but "more context" doesn't always mean "better results."</p>
        <p>Recent research (like Chen et al. 2025) demonstrates that even with <strong>perfect retrieval</strong> — where the model can literally recite the evidence verbatim — reasoning accuracy drops as input length increases. This was tested on math, QA, and <em>coding tasks</em> specifically.</p>
        <p>Other studies have found that <strong>even on simple retrieval tasks</strong>, performance degrades non-uniformly with input length. This holds for many frontier models despite their massive context windows. A bigger window raises the ceiling; it does not eliminate the degradation curve.</p>
        <p className="bg-surface border border-border rounded-lg p-4 text-sm text-text-muted italic">A massive context window can hold hundreds of pages, but a human doesn&apos;t read better by having 3,000 irrelevant pages open on their desk. Neither does an LLM.</p>
        <p>CoDRAG&apos;s approach — find the 5 best chunks, optionally follow structural relationships, and deliver ~2K tokens of high-signal context — aligns with the research recommendation of &quot;Retrieve then Solve.&quot;</p>
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
              <tr className="border-b border-border-subtle"><td className="py-2 pr-6"><code className="bg-surface px-1 rounded border border-border-subtle text-xs">compression: &quot;auto&quot;</code></td><td>Smart compression &mdash; structural for code, language-aware for docs</td></tr>
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
          <li><strong className="text-text">Smart context compression.</strong> Two built-in engines: structural compression for code (3&ndash;20&times; &mdash; keeps full source for top results, signatures for mid-relevance, names only for peripheral files) and language-aware compression for docs and markdown (preserves meaning while removing filler). No GPU required.</li>
          <li><strong className="text-text">Persistent cross-session knowledge.</strong> The AI accumulates linked observations about your codebase over time, with automatic staleness detection when files change. Its understanding of your project gets deeper across sessions, not just per-conversation.</li>
        </ul>
      </div>
    ),
  },
  {
    id: "cloud-upload",
    q: "Is my code uploaded to the cloud?",
    a: (
      <div className="space-y-4">
        <p><strong>No.</strong> CoDRAG is local-first software &mdash; indexing, embedding, graph construction, search, and compression all happen on your machine. Your code never leaves your filesystem.</p>
        <p>The only exceptions are things you explicitly opt into: if you configure a cloud LLM provider (OpenAI, Anthropic, Google) for the optional enrichment pipeline, only retrieved context snippets are sent to that provider &mdash; never your raw codebase. CoDRAG also makes a single HTTPS call during license activation. Both are optional and auditable.</p>
        <p>What makes this different from tools that <em>claim</em> local-first: CoDRAG ships its own embedding model (ONNX, runs on CPU) and its own Rust parser. You don&apos;t need Ollama, you don&apos;t need Docker, you don&apos;t need an internet connection for core functionality. The entire stack runs offline, cold.</p>
      </div>
    ),
  },
  {
    id: "lsp-wrapper",
    q: "Is this just a wrapper around the Language Server Protocol?",
    a: (
      <div className="space-y-4">
        <p><strong>No</strong> &mdash; and the distinction matters. LSP-backed tools require a running language server with the correct runtime environment configured for every project. Switch from Python to TypeScript? You need a different server. Working on a legacy project without a proper <code className="bg-surface px-1.5 py-0.5 rounded text-xs border border-border-subtle">tsconfig.json</code>? LSP can&apos;t help.</p>
        <p>CoDRAG builds its own persistent trace graph using tree-sitter, a zero-dependency parser that handles 15+ languages from a single binary. The graph persists to disk, loads instantly, and works offline. No runtime, no IDE backend, no configuration per language.</p>
        <p>The deeper difference: LSP gives you <em>live</em> analysis (great for autocomplete), but it can&apos;t answer cross-session questions, doesn&apos;t persist observations about your code, and can&apos;t compress structural context into a token budget. CoDRAG is a read-only context engine designed for a fundamentally different job &mdash; giving AI agents the right context at query time.</p>
      </div>
    ),
  },
  {
    id: "semantic-search",
    q: "I already use semantic search tools. How is CoDRAG different?",
    a: (
      <div className="space-y-4">
        <p>Pure semantic search (vector embeddings) excels at fuzzy discovery &mdash; finding code when you describe it in natural language. CoDRAG includes a full semantic search engine (ONNX embeddings, runs locally on CPU, no external service needed).</p>
        <p>But semantic search alone struggles with <strong>structural precision</strong>. It can find code that <em>sounds</em> related to &quot;authentication,&quot; but it can&apos;t traverse the actual import chain to tell you what <code className="bg-surface px-1.5 py-0.5 rounded text-xs border border-border-subtle">AuthService.validate()</code> calls, or what breaks if you change its signature.</p>
        <p>CoDRAG adds a <strong>deterministic dependency graph</strong> on top of embeddings. When the AI asks about blast radius, it gets exact callers and importers from the parsed AST &mdash; not a list of files that happen to mention similar words. And because the graph and the vector index share a token budget, you get both conceptual relevance and structural precision without blowing up your context window.</p>
      </div>
    ),
  },
  {
    id: "editor-support",
    q: "Which editors does it work with?",
    a: (
      <div className="space-y-4">
        <p>CoDRAG is a standalone daemon and an <strong>MCP (Model Context Protocol) server</strong>. It is not locked to any IDE. Today it works with <strong>Cursor</strong>, <strong>Windsurf</strong>, <strong>Claude Desktop</strong>, and <strong>Claude Code</strong> (terminal). A VS Code extension is in development.</p>
        <p>Because CoDRAG uses the open MCP standard, any future editor or agent that supports MCP will work automatically &mdash; no integration work on our end. Your index, weights, observations, and full project configuration are stored locally and editor-independent. Switch tools without losing anything.</p>
      </div>
    ),
  },
  {
    id: "gpu-requirement",
    q: "Do I need a GPU?",
    a: (
      <div className="space-y-4">
        <p><strong>No.</strong> Core features (indexing, trace graph, search) run efficiently on CPU. The built-in embedding model is quantized and optimized for CPU inference.</p>
        <p><strong>Also No.</strong> You can run Anthropic or OpenAI or any other BYOK models from the cloud if you want to enhance trace content.</p>
        <p><strong>Or Yes</strong> if you want to run a local model for enhancement.</p>
        <p><strong>Context compression</strong> is built in &mdash; structural compression for code files runs instantly with no model at all, and language-aware compression for docs uses a lightweight CPU model (~178 MB). No GPU, no sidecar.</p>
      </div>
    ),
  },
  {
    id: "pricing",
    q: "Why pay for this? Can\u2019t I build it myself?",
    a: (
      <div className="space-y-4">
        <p>You could build a basic RAG pipeline over a weekend. What takes years is everything beyond that: incremental rebuilds that don&apos;t re-embed your entire project on every save. A Rust parser that handles 15+ languages and produces a navigable dependency graph. Compression that treats code and documentation differently. An observation store that links AI knowledge to specific files and flags it stale when those files change. A real-time file watcher. A dashboard that shows you exactly what the AI sees.</p>
        <p>CoDRAG offers a <strong>Free tier</strong> for evaluation. Pro is a <strong>one-time $79 perpetual license</strong> &mdash; not a subscription. You pay once, own the software, and it works offline forever. We fund development through that, not by monetizing your data or adding telemetry.</p>
      </div>
    ),
  },
  {
    id: "docs-support",
    q: "Does it work on documentation, not just code?",
    a: (
      <div className="space-y-4">
        <p><strong>Yes</strong> &mdash; and it handles docs differently than code, which matters. CoDRAG runs two distinct compression strategies: <strong>structural compression</strong> for code files (preserving full source for top results, signatures for medium-relevance, names for peripheral) and <strong>language-aware compression</strong> for Markdown and text (preserving concepts while stripping filler words and redundant phrasing).</p>
        <p>This means you can include architecture docs, API references, and design decisions in your project scope, and CoDRAG will compress them intelligently alongside your code. The AI gets both implementation details and the human reasoning behind them.</p>
      </div>
    ),
  },
];

function FAQAccordionItem({ item, isOpen, onToggle }: { item: FAQItem; isOpen: boolean; onToggle: () => void }) {
  return (
    <div className="border border-border rounded-lg overflow-hidden">
      <button
        type="button"
        onClick={onToggle}
        className="w-full flex items-center justify-between px-6 py-5 text-left bg-surface hover:bg-surface-raised transition-colors gap-4"
        aria-expanded={isOpen}
      >
        <div className="flex items-start gap-3 flex-1 min-w-0">
          <HelpCircle className="w-5 h-5 text-primary mt-0.5 flex-shrink-0" />
          <span className="font-normal text-text text-base leading-snug">{item.q}</span>
        </div>
        <ChevronDown
          className={`w-5 h-5 text-text-muted flex-shrink-0 transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`}
        />
      </button>
      {isOpen && (
        <div className="pl-6 pr-[3.25rem] py-[2.25rem] border-t border-border bg-background">
          <div className="flex items-start gap-3">
            <Lightbulb className="w-6 h-6 text-text-muted mt-0.5 flex-shrink-0 -ml-0.5" />
            <div className="text-text-muted leading-relaxed flex-1 min-w-0 [&_strong]:text-text [&_strong]:font-semibold">{item.a}</div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function FAQPage() {
  const [openId, setOpenId] = useState<string | null>("persistent-memory");

  const toggle = (id: string) => setOpenId(prev => prev === id ? null : id);

  return (
    <div className="min-h-screen bg-background text-text">
      <div className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8 py-16">
        {/* Header */}
        <div className="text-center mb-16">
          <p className="text-sm font-semibold uppercase tracking-widest text-primary mb-3">Frequently Asked Questions</p>
          <h1 className="text-4xl font-medium tracking-tight text-text sm:text-5xl mb-4 max-w-xl mx-auto">
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
              href="https://github.com/MagneticAnomaly/CoDRAG-MCP/discussions"
              className="inline-flex items-center justify-center gap-2 rounded-md border border-border bg-background px-5 py-2.5 text-sm font-medium text-text hover:bg-surface transition-colors"
            >
              Ask the Community
            </a>
            <a
              href="https://docs.codrag.io"
              className="inline-flex items-center justify-center gap-2 rounded-md bg-primary px-5 py-2.5 text-sm font-semibold text-background hover:bg-primary-hover transition-colors"
            >
              Read the Docs <ArrowRight className="w-4 h-4" />
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
