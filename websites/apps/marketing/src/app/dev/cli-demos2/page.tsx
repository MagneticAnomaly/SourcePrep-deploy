'use client';

import { AnimatedCLI, AnimatedIDE } from '@prep/ui';
import { variants, type DemoTool } from '../cli-demos/variants';

interface SlotPlan {
  tool: DemoTool;
  pickedIds: string[];
  rejectedId: string;
  rationale: string;
  rejectedReason: string;
}

const SLOTS: SlotPlan[] = [
  {
    tool: 'prep',
    pickedIds: ['prep-rate-limiting', 'prep-tldr-overview', 'prep-build-webhook'],
    rejectedId: 'prep-payments-onboard',
    rationale:
      'Where-does-X-fit (rate limiting) → overview (tldr map) → build (pattern reuse). Three frames on structural orientation, all phrased the way a dev would actually type.',
    rejectedReason:
      "payments-onboard: phrasing felt forced — \"jumping into the payments module for the first time\" isn't how devs talk to AI.",
  },
  {
    tool: 'prep_search',
    pickedIds: ['search-retry-reuse', 'search-max-connections', 'search-build-worker'],
    rejectedId: 'search-oauth-callback',
    rationale:
      'Dedup ("do we already have…") → error string → source → pattern-reuse for a new worker. Each shows a different highest-signal search moment.',
    rejectedReason:
      'oauth-callback: realistic but vanilla — returns a flow walk-through that any tool with file access could approximate.',
  },
  {
    tool: 'prep_impact',
    pickedIds: ['impact-delete-unused', 'impact-extract-service', 'impact-async-migration'],
    rejectedId: 'impact-rename',
    rationale:
      '"You\'re confidently wrong" (delete) → pre-commitment feasibility (extract) → build with caveats (async). Each picks a different point in the change lifecycle.',
    rejectedReason:
      'rename: solid, but the alias-vs-naked-rename recommendation is a quieter payoff than the other three.',
  },
  {
    tool: 'prep_audit',
    pickedIds: ['audit-pr-sanity-check', 'audit-security-scan', 'audit-tighten-types'],
    rejectedId: 'audit-branch-review',
    rationale:
      'Own diff (PR sanity) → external SARIF with reachability → lint ranking by hub. Three different finding sources, all enriched with graph context.',
    rejectedReason:
      'branch-review: nearly identical narrative to pr-sanity — same own-diff enrichment, just slightly more imperative phrasing.',
  },
  {
    tool: 'prep_observe',
    pickedIds: ['observe-caching-recall', 'observe-investigation-recall', 'observe-save-ownership'],
    rejectedId: 'observe-zod-standard',
    rationale:
      'Stale-detection on recall → mid-task investigation continuity → ownership save with auto-link. Two recall flavors and one save, each demonstrating a distinct memory affordance.',
    rejectedReason:
      'zod-standard: the auto-link narrative is shared with save-ownership; ownership lands harder because cross-team handoff is a stronger frame than "we picked a library".',
  },
  {
    tool: 'prep_concepts',
    pickedIds: ['concepts-transaction-rule', 'concepts-queue-gotchas', 'concepts-build-refund'],
    rejectedId: 'concepts-document-rule',
    rationale:
      'Reactive ("why can\'t I…") → preflight risk-scan → build preflight with multiple rules. Covers immune-system surfacing under three real intents.',
    rejectedReason:
      "document-rule: \"let's document this rule\" is a rare prompt — devs almost never proactively codify constraints. Better suited for an internal-tooling demo than the home page.",
  },
  {
    tool: 'ide',
    pickedIds: ['ide-double-submit-fix', 'ide-loading-skeleton', 'ide-add-csv-export'],
    rejectedId: 'ide-live-pipeline-updates',
    rationale:
      'Bug fix → UI pattern match → new feature. Each demonstrates "agent finds existing code and reuses it" with a different end shape.',
    rejectedReason:
      'live-pipeline-updates: strong content but enterprisey — pipeline dashboards are inside-baseball. The other three land for any web dev on first watch.',
  },
];

const TOOL_BADGE: Record<DemoTool, string> = {
  prep: 'bg-blue-500/15 text-blue-300 ring-blue-500/30',
  prep_search: 'bg-purple-500/15 text-purple-300 ring-purple-500/30',
  prep_impact: 'bg-orange-500/15 text-orange-300 ring-orange-500/30',
  prep_audit: 'bg-red-500/15 text-red-300 ring-red-500/30',
  prep_observe: 'bg-emerald-500/15 text-emerald-300 ring-emerald-500/30',
  prep_concepts: 'bg-amber-500/15 text-amber-300 ring-amber-500/30',
  ide: 'bg-slate-500/15 text-slate-300 ring-slate-500/30',
};

const variantById = new Map(variants.map((v) => [v.id, v]));

export default function CliDemos2DevPage() {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto max-w-3xl px-6 py-12">
        <header className="mb-12">
          <p className="mb-2 text-xs font-mono uppercase tracking-wider text-slate-500">
            dev · not linked · not indexed · review page
          </p>
          <h1 className="mb-3 text-3xl font-semibold tracking-tight">
            CLI demo picks — for marketing slot review
          </h1>
          <p className="text-sm leading-relaxed text-slate-400">
            Curated 3-of-4 picks per tool slot. Demos are sized to match the live home page:
            full-width terminal, fixed content height (no growing during animation). Each section
            shows the rationale, the rejected variant, and the picks rendered exactly as they will
            appear in their slot on the marketing site.
          </p>
        </header>

        <div className="space-y-20">
          {SLOTS.map((slot) => {
            const picks = slot.pickedIds.map((id) => variantById.get(id)!).filter(Boolean);
            const rejected = variantById.get(slot.rejectedId);

            return (
              <section key={slot.tool}>
                <div className="mb-4 flex items-baseline gap-3">
                  <span
                    className={`inline-block rounded px-2 py-0.5 text-sm font-mono ring-1 ring-inset ${TOOL_BADGE[slot.tool]}`}
                  >
                    {slot.tool}
                  </span>
                  <span className="text-xs text-slate-500">
                    {picks.length} of 4 picked
                  </span>
                </div>

                <p className="mb-3 text-sm leading-relaxed text-slate-300">{slot.rationale}</p>

                <div className="mb-8 rounded-md border border-slate-800 bg-slate-900/40 p-3">
                  <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                    Rejected
                  </p>
                  <p className="mt-1 text-xs leading-relaxed text-slate-400">
                    <span className="font-mono text-slate-300">{slot.rejectedId}</span>
                    {rejected ? ` — ${rejected.label}` : ''}
                  </p>
                  <p className="mt-1 text-xs italic leading-relaxed text-slate-500">
                    {slot.rejectedReason}
                  </p>
                </div>

                <div className="mb-3 rounded-md border border-slate-800 bg-slate-900/30 p-3">
                  <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
                    Cycles through ({picks.length})
                  </p>
                  <ol className="space-y-1 text-xs text-slate-300">
                    {picks.map((v, idx) => (
                      <li key={v.id} className="flex items-start gap-2 leading-relaxed">
                        <span className="font-mono text-slate-500">{idx + 1}.</span>
                        <span className="flex-1">
                          <span className="font-medium text-slate-200">{v.label}</span>
                          {v.note && (
                            <span className="ml-2 italic text-slate-400">— {v.note}</span>
                          )}
                          <code className="ml-2 font-mono text-[10px] text-slate-500">{v.id}</code>
                        </span>
                      </li>
                    ))}
                  </ol>
                </div>

                <div className="overflow-hidden rounded-md">
                  {slot.tool === 'ide' ? (
                    <AnimatedIDE
                      scripts={picks.map((v) => v.script)}
                      className="w-full"
                    />
                  ) : (
                    <AnimatedCLI
                      scripts={picks.map((v) => v.script)}
                      theme="dark"
                      className="w-full"
                      contentClassName="min-h-[480px]"
                    />
                  )}
                </div>
              </section>
            );
          })}
        </div>

        <footer className="mt-16 border-t border-slate-800 pt-6 text-xs text-slate-500">
          Source variants: <code className="font-mono text-slate-400">../cli-demos/variants.ts</code>{' '}
          · Component: <code className="font-mono text-slate-400">@prep/ui AnimatedCLI / AnimatedIDE</code>
        </footer>
      </div>
    </div>
  );
}
