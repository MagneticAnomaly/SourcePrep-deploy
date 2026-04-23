'use client';

import { useMemo, useState } from 'react';
import { AnimatedCLI, AnimatedIDE } from '@prep/ui';
import { variants, type DemoTool } from './variants';

const TOOL_OPTIONS: Array<{ value: 'all' | DemoTool; label: string }> = [
  { value: 'all', label: 'All tools' },
  { value: 'prep', label: 'prep' },
  { value: 'prep_search', label: 'prep_search' },
  { value: 'prep_impact', label: 'prep_impact' },
  { value: 'prep_audit', label: 'prep_audit' },
  { value: 'prep_observe', label: 'prep_observe' },
  { value: 'prep_concepts', label: 'prep_concepts' },
  { value: 'ide', label: 'ide' },
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

export default function CliDemosDevPage() {
  const [filter, setFilter] = useState<'all' | DemoTool>('all');

  const filtered = useMemo(
    () => (filter === 'all' ? variants : variants.filter((v) => v.tool === filter)),
    [filter],
  );

  const counts = useMemo(() => {
    const byTool = new Map<DemoTool, number>();
    for (const v of variants) byTool.set(v.tool, (byTool.get(v.tool) ?? 0) + 1);
    return byTool;
  }, []);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto max-w-7xl px-6 py-12">
        <header className="mb-10">
          <p className="mb-2 text-xs font-mono uppercase tracking-wider text-slate-500">
            dev · not linked · not indexed
          </p>
          <h1 className="mb-3 text-3xl font-semibold tracking-tight">CLI demo variants</h1>
          <p className="max-w-2xl text-sm leading-relaxed text-slate-400">
            Draft scripts for the marketing home-page animations. Goal is organic, realistic dev
            prompts where SourcePrep tools fire because the agent got smarter — not because the
            user asked for a tool. Promote blessed variants into{' '}
            <code className="font-mono text-slate-300">demo-scripts.ts</code> when ready.
          </p>

          <div className="mt-6 flex flex-wrap items-center gap-3">
            <label className="flex items-center gap-2 text-sm">
              <span className="text-slate-400">Filter:</span>
              <select
                value={filter}
                onChange={(e) => setFilter(e.target.value as 'all' | DemoTool)}
                className="rounded border border-slate-700 bg-slate-900 px-3 py-1.5 text-sm font-mono text-slate-200 focus:border-slate-500 focus:outline-none"
              >
                {TOOL_OPTIONS.map((opt) => {
                  const count =
                    opt.value === 'all'
                      ? variants.length
                      : counts.get(opt.value as DemoTool) ?? 0;
                  return (
                    <option key={opt.value} value={opt.value}>
                      {opt.label} ({count})
                    </option>
                  );
                })}
              </select>
            </label>
            <span className="text-xs text-slate-500">
              showing {filtered.length} of {variants.length}
            </span>
          </div>
        </header>

        {filtered.length === 0 ? (
          <div className="rounded-lg border border-dashed border-slate-700 p-12 text-center text-sm text-slate-500">
            No variants for this tool yet. Add one in{' '}
            <code className="font-mono text-slate-300">variants.ts</code>.
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
            {filtered.map((v) => (
              <article
                key={v.id}
                className="rounded-xl border border-slate-800 bg-slate-900/40 p-5 shadow-sm"
              >
                <div className="mb-3 flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <span
                      className={`inline-block rounded px-2 py-0.5 text-xs font-mono ring-1 ring-inset ${TOOL_BADGE[v.tool]}`}
                    >
                      {v.tool}
                    </span>
                    <h2 className="mt-2 text-base font-medium text-slate-100">{v.label}</h2>
                  </div>
                  <code className="shrink-0 font-mono text-xs text-slate-500">{v.id}</code>
                </div>

                {v.note && (
                  <p className="mb-4 text-xs italic leading-relaxed text-slate-400">{v.note}</p>
                )}

                <div className="mb-3 overflow-hidden rounded-md">
                  {v.tool === 'ide' ? (
                    <AnimatedIDE script={v.script} className="w-full" />
                  ) : (
                    <AnimatedCLI
                      script={v.script}
                      theme="dark"
                      className="w-full"
                      contentClassName="min-h-[360px] max-h-[440px]"
                    />
                  )}
                </div>

                <details className="group">
                  <summary className="cursor-pointer select-none text-xs text-slate-500 hover:text-slate-300">
                    raw script
                  </summary>
                  <pre className="mt-2 max-h-80 overflow-auto rounded bg-slate-950/60 p-3 text-[11px] leading-relaxed text-slate-400">
                    {JSON.stringify(v.script, null, 2)}
                  </pre>
                </details>
              </article>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
