"use client";

import { FolderTree, Scale, Target, Cpu, FilterX } from 'lucide-react';
import { AnchorHeading } from '../../../components/AnchorHeading';
import { ConceptPageShell } from '../../../components/ConceptPageShell';
import { DemoIndexStatusLoaded, DemoFolderTreeKnowledgeScope } from '../../../components/demos';

const SECTIONS = [
  { id: 'status',        label: 'Watching your knowledge' },
  { id: 'scope',         label: 'Set the scope first' },
  { id: 'weights',       label: 'Weighted retrieval' },
  { id: 'best-practice', label: 'Best practices' },
  { id: 'under-hood',    label: 'Under the hood' },
  { id: 'initialize',    label: 'Initialising a project' },
];

export default function Page() {
  return (
    <ConceptPageShell
      subtitle="Targeted RAG"
      title="Knowledge"
      description="Pick the files your agent should know about. SourcePrep embeds them, learns their structure, and serves a focused context window — not a dump of your entire repo."
      sections={SECTIONS}
    >
      <section id="status">
        <h2 className="text-2xl font-semibold text-text mb-4">Watching your knowledge</h2>
        <p className="text-text-muted leading-relaxed mb-4">
          The <span className="font-semibold text-text">Knowledge Status</span> panel is where you
          confirm your knowledge is ready and watch it stay in sync as you work. It&apos;s the first
          panel to add to your dashboard — without it built, nothing else has anything to serve.
        </p>

        <DemoIndexStatusLoaded />
        <p className="text-xs text-text-subtle italic -mt-2 mb-4">
          The Knowledge Status panel — chunk count, embedding model, last build, and live freshness.
        </p>

        <p className="text-text-muted leading-relaxed mb-3">
          The status badge tells you whether you can trust what the agent is reading right now:
        </p>
        <ul className="list-disc pl-5 space-y-1 text-text-muted">
          <li><span className="text-emerald-500 font-medium">Fresh</span> — every chunk on disk is in the index.</li>
          <li><span className="text-amber-500 font-medium">Stale</span> — files changed; the next save reindexes them (usually under a second).</li>
          <li><span className="text-blue-500 font-medium">Building</span> — the background worker is processing files now.</li>
        </ul>
      </section>

      <section id="scope">
        <h2 className="text-2xl font-semibold text-text mb-4">Set the scope first</h2>
        <p className="text-text-muted leading-relaxed mb-4">
          SourcePrep doesn&apos;t need your whole repo. It needs the slice of your repo that&apos;s
          relevant to what you&apos;re working on right now. The <span className="font-semibold text-text">Knowledge Scope</span> panel
          (file tree) is where you mark that slice — folders and files toggle in and out with a click.
        </p>

        <DemoFolderTreeKnowledgeScope />
        <p className="text-xs text-text-subtle italic -mt-2 mb-4">
          The Knowledge Scope panel — the file tree where you pick what your agent will know about.
        </p>

        <p className="text-text-muted leading-relaxed mb-4">
          By default SourcePrep respects your <code>.gitignore</code> and drops standard noise
          directories so you don&apos;t have to spell them out:
        </p>
        <div className="rounded-lg border border-border bg-surface p-5 flex items-start gap-4">
          <div className="text-primary flex-shrink-0 mt-0.5"><FilterX className="w-5 h-5" /></div>
          <div>
            <h3 className="font-medium text-sm text-text mb-1">Excluded by default</h3>
            <p className="text-sm text-text-muted font-mono text-xs">
              node_modules/ · dist/ · build/ · .git/ · .next/ · target/ · venv/ · __pycache__/
            </p>
          </div>
        </div>

        <p className="text-sm text-text-muted mt-4">
          See <a href="/guides/knowledge-scope" className="text-primary hover:underline">Knowledge Scope</a> for
          the full include/exclude pattern syntax and named scope presets.
        </p>
      </section>

      <section id="weights">
        <h2 className="text-2xl font-semibold text-text mb-4">Weighted retrieval</h2>
        <p className="text-text-muted leading-relaxed mb-4">
          Within the scope you picked, not all folders deserve equal weight at query time. Path
          weights are query-time multipliers — boost the folders you want the agent to lean into,
          suppress the ones that are technically in scope but you don&apos;t want crowding results.
          No rebuild required.
        </p>

        <div className="rounded-lg border border-border bg-surface p-5 flex items-start gap-4">
          <div className="text-primary flex-shrink-0 mt-0.5"><Scale className="w-5 h-5" /></div>
          <div>
            <h3 className="font-medium text-sm text-text mb-1">Range 0.0 – 2.0</h3>
            <p className="text-sm text-text-muted">
              <code>1.0</code> = neutral. <code>1.5</code> boosts a folder 50% at ranking time.
              <code> 0.0</code> effectively hides it. Most-specific path wins.
            </p>
          </div>
        </div>

        <p className="text-sm text-text-muted mt-4">
          Full details in the <a href="/guides/path-weights" className="text-primary hover:underline">Path Weights</a> guide.
        </p>
      </section>

      <section id="best-practice">
        <h2 className="text-2xl font-semibold text-text mb-4">Best practices</h2>
        <p className="text-text-muted leading-relaxed mb-4">
          A tighter scope almost always beats a bigger one at the same token budget. The agent
          isn&apos;t fighting noise to find what matters, and retrieval is faster too. Scope to
          what you&apos;re actually working on; widen only when you need to.
        </p>

        <h3 className="text-lg font-semibold text-text mt-6 mb-3">How big should your scope be?</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="border-b border-border text-left text-text">
                <th className="py-2 pr-4 font-medium">Scope</th>
                <th className="py-2 font-medium">What it gets you</th>
              </tr>
            </thead>
            <tbody className="text-text-muted">
              <tr className="border-b border-border/50">
                <td className="py-2 pr-4 font-semibold text-text whitespace-nowrap">2–5 files</td>
                <td className="py-2">Just paste it. Below this an index is overkill.</td>
              </tr>
              <tr className="border-b border-border/50">
                <td className="py-2 pr-4 font-semibold text-text whitespace-nowrap">5–15 files</td>
                <td className="py-2">Sweet spot for focused work. Retrieval is essentially deterministic — the agent sees what you scoped.</td>
              </tr>
              <tr className="border-b border-border/50">
                <td className="py-2 pr-4 font-semibold text-text whitespace-nowrap">15–50 files</td>
                <td className="py-2">Selective retrieval, still excellent for focused tasks.</td>
              </tr>
              <tr className="border-b border-border/50">
                <td className="py-2 pr-4 font-semibold text-text whitespace-nowrap">50–200 files</td>
                <td className="py-2">Works fine; start using path weights to suppress noise.</td>
              </tr>
              <tr>
                <td className="py-2 pr-4 font-semibold text-text whitespace-nowrap">200+ files</td>
                <td className="py-2">Works for broad refactors; lean on path weights or sub-scopes.</td>
              </tr>
            </tbody>
          </table>
        </div>

        <h3 className="text-lg font-semibold text-text mt-8 mb-3">When each scope size fits</h3>
        <div className="rounded-lg border border-border bg-surface p-5 flex items-start gap-4">
          <div className="text-primary flex-shrink-0 mt-0.5"><Target className="w-5 h-5" /></div>
          <div className="flex-1 space-y-3">
            <div>
              <h3 className="font-medium text-sm text-text mb-1">Working on a feature</h3>
              <p className="text-sm text-text-muted">
                Scope to that feature&apos;s folder plus its immediate dependencies. Two or three
                directories is often enough.
              </p>
            </div>
            <div>
              <h3 className="font-medium text-sm text-text mb-1">Refactor pass</h3>
              <p className="text-sm text-text-muted">
                Broader scope is fine — but lean on path weights to suppress test fixtures, vendored
                code, and anything you don&apos;t want the agent to mirror.
              </p>
            </div>
            <div>
              <h3 className="font-medium text-sm text-text mb-1">Quick Q&amp;A</h3>
              <p className="text-sm text-text-muted">
                Narrowest scope wins. If you know which file the answer lives in, scope to just that
                directory. The agent will be ready in seconds.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section id="under-hood">
        <AnchorHeading id="under-hood" level="h2">Under the hood</AnchorHeading>
        <p className="mt-3 text-text-muted leading-relaxed">
          Files in scope are parsed with Tree-sitter, chunked at function/class boundaries (or by
          Markdown headers for docs), embedded with the built-in ONNX CPU embedder (or your local
          Ollama if you prefer), and stored alongside your project metadata. A file watcher catches
          edits as you save and re-embeds just the changed file — usually under 200 ms.
        </p>
        <div className="mt-4 rounded-lg border border-border bg-surface p-5 flex items-start gap-4">
          <div className="text-primary flex-shrink-0 mt-0.5"><Cpu className="w-5 h-5" /></div>
          <div>
            <h3 className="font-medium text-sm text-text mb-1">15+ languages, CPU-only by default</h3>
            <p className="text-sm text-text-muted">
              Tree-sitter handles parsing for Python, TypeScript, JavaScript, Rust, Go, Java, and a
              dozen more. ONNX embeddings run on your CPU at acceptable speed; nothing about
              indexing requires a GPU.
            </p>
          </div>
        </div>
        <p className="text-sm text-text-muted mt-4">
          For embedder options, see <a href="/how-it-works/embeddings" className="text-primary hover:underline">Embedding Models</a>.
          Everything stays on your machine — there&apos;s no cloud component to indexing.
        </p>
      </section>

      <section id="initialize">
        <AnchorHeading id="initialize" level="h2">Initialising a project</AnchorHeading>
        <p className="mt-3 text-text-muted leading-relaxed">
          Add a project via the dashboard <span className="font-semibold text-text">+</span> button
          (or <code>prep add /path/to/project</code>) and the first build kicks off automatically.
          You can watch it complete in the Knowledge Status panel above. The file watcher handles
          every change afterwards; you almost never need to trigger a rebuild by hand.
        </p>
        <p className="text-sm text-text-muted mt-3">
          For the rare cases the watcher misses — a thousand-file branch switch, an exclusion-pattern
          change, or a search that feels suspiciously off — there&apos;s a manual <em>Rebuild Knowledge</em> control
          available in the dashboard&apos;s developer-mode panels.
        </p>
      </section>
    </ConceptPageShell>
  );
}
