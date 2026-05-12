import type { Meta, StoryObj } from '@storybook/react';

const meta: Meta = {
  title: 'Foundations/Tokens/Typography',
  tags: ['autodocs'],
  parameters: { layout: 'padded' },
};

export default meta;
type Story = StoryObj;

/* ------------------------------------------------------------- *
 *  Helpers                                                      *
 * ------------------------------------------------------------- */

function SectionHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="border-b border-border pb-2">
      <div className="text-sm font-semibold text-text">{title}</div>
      {subtitle && <div className="text-xs text-text-muted mt-0.5">{subtitle}</div>}
    </div>
  );
}

function Row({
  label,
  meta,
  children,
}: {
  label: string;
  meta?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="grid grid-cols-[200px_1fr] gap-6 items-baseline">
      <div className="text-xs font-mono text-text-muted">
        <div>{label}</div>
        {meta && <div className="text-text-subtle">{meta}</div>}
      </div>
      <div className="text-text">{children}</div>
    </div>
  );
}

const SAMPLE = 'SourcePrep — context for the cursor.';
const CODE_SAMPLE = `from prep.search import semantic_search
results = semantic_search("hub files", top_k=10)`;

/* ------------------------------------------------------------- *
 *  Story: families                                              *
 * ------------------------------------------------------------- */

export const Families: Story = {
  name: 'Font Families',
  render: () => (
    <div className="space-y-4 max-w-4xl">
      <SectionHeader
        title="Font families"
        subtitle="JetBrains Mono carries the entire UI by default. IBM Plex Sans is reserved for true <h1>/<h2> headings on long-form pages."
      />
      <Row label="--font-sans" meta="JetBrains Mono · default body">
        <div className="font-sans text-base">{SAMPLE}</div>
      </Row>
      <Row label="--font-mono" meta="JetBrains Mono · code, paths, kbd">
        <div className="font-mono text-base">{SAMPLE}</div>
      </Row>
      <Row label="--font-heading" meta="IBM Plex Sans · h1/h2 only">
        <div className="font-heading text-2xl font-medium">{SAMPLE}</div>
      </Row>

      <div className="rounded-md border border-border bg-surface-raised p-3 text-xs text-text-muted leading-relaxed mt-4 space-y-1.5">
        <div>
          <span className="font-semibold text-text">Why everything looks like JetBrains:</span>{' '}
          <code className="font-mono">--font-sans</code> and <code className="font-mono">--font-mono</code> both resolve to JetBrains Mono in <code className="font-mono">tokens/index.css</code>. That&apos;s deliberate — the IDE-aligned aesthetic is mono-everywhere.
        </div>
        <div>
          <span className="font-semibold text-text">The h-tag rule:</span>{' '}
          <code className="font-mono">h1/h2/h4/h5/h6</code> auto-pick <code className="font-mono">--font-heading</code> (IBM Plex Sans);{' '}
          <code className="font-mono">h3</code> auto-picks <code className="font-mono">--font-mono</code>. Most panel titles are <code className="font-mono">&lt;div&gt;</code> tags, so they inherit body (mono) — which is why headings in the app rarely look like IBM Plex Sans.
        </div>
      </div>
    </div>
  ),
};

/* ------------------------------------------------------------- *
 *  Story: scale                                                 *
 * ------------------------------------------------------------- */

const SIZES: { className: string; token: string; px: string }[] = [
  { className: 'text-5xl', token: '--text-5xl', px: '48px' },
  { className: 'text-4xl', token: '--text-4xl', px: '36px' },
  { className: 'text-3xl', token: '--text-3xl', px: '30px' },
  { className: 'text-2xl', token: '--text-2xl', px: '24px' },
  { className: 'text-xl', token: '--text-xl', px: '20px' },
  { className: 'text-lg', token: '--text-lg', px: '18px' },
  { className: 'text-base', token: '--text-base', px: '16px' },
  { className: 'text-sm', token: '--text-sm', px: '14px' },
  { className: 'text-xs', token: '--text-xs', px: '12px' },
];

export const Scale: Story = {
  name: 'Type Scale',
  render: () => (
    <div className="space-y-4 max-w-4xl">
      <SectionHeader
        title="Type scale"
        subtitle="9 steps, xs → 5xl. All steps below text-base are heavily used (panel rows, labels, meta)."
      />
      {SIZES.map((s) => (
        <Row key={s.className} label={s.className} meta={`${s.token} · ${s.px}`}>
          <div className={s.className}>The five boxing wizards jump quickly.</div>
        </Row>
      ))}
    </div>
  ),
};

/* ------------------------------------------------------------- *
 *  Story: weights                                               *
 * ------------------------------------------------------------- */

const WEIGHTS: { className: string; token: string; value: string }[] = [
  { className: 'font-normal', token: '--font-normal', value: '400' },
  { className: 'font-medium', token: '--font-medium', value: '500' },
  { className: 'font-semibold', token: '--font-semibold', value: '600' },
  { className: 'font-bold', token: '--font-bold', value: '700' },
];

export const Weights: Story = {
  name: 'Weights',
  render: () => (
    <div className="space-y-4 max-w-4xl">
      <SectionHeader
        title="Font weights"
        subtitle="Medium and semibold do most of the UI work; bold is reserved for headings and emphasis."
      />
      {WEIGHTS.map((w) => (
        <Row key={w.className} label={w.className} meta={`${w.token} · ${w.value}`}>
          <div className={`text-lg ${w.className}`}>{SAMPLE}</div>
        </Row>
      ))}
    </div>
  ),
};

/* ------------------------------------------------------------- *
 *  Story: leading                                               *
 * ------------------------------------------------------------- */

const LEADINGS: { className: string; token: string; value: string }[] = [
  { className: 'leading-none', token: '--leading-none', value: '1' },
  { className: 'leading-tight', token: '--leading-tight', value: '1.25' },
  { className: 'leading-snug', token: '--leading-snug', value: '1.375' },
  { className: 'leading-normal', token: '--leading-normal', value: '1.5' },
  { className: 'leading-relaxed', token: '--leading-relaxed', value: '1.625' },
  { className: 'leading-loose', token: '--leading-loose', value: '2' },
];

export const LineHeights: Story = {
  name: 'Line Heights',
  render: () => (
    <div className="space-y-6 max-w-4xl">
      <SectionHeader
        title="Line heights"
        subtitle="Body copy is leading-normal. Tight/snug are reserved for headings and dense table rows."
      />
      {LEADINGS.map((l) => (
        <div key={l.className} className="grid grid-cols-[200px_1fr] gap-6 items-baseline">
          <div className="text-xs font-mono text-text-muted">
            <div>{l.className}</div>
            <div className="text-text-subtle">
              {l.token} · {l.value}
            </div>
          </div>
          <div className={`text-sm ${l.className}`}>
            SourcePrep builds a structural graph of your codebase and serves bounded, source-cited
            context to AI agents over MCP. Indexes update incrementally as files change.
          </div>
        </div>
      ))}
    </div>
  ),
};

/* ------------------------------------------------------------- *
 *  Story: applied                                               *
 * ------------------------------------------------------------- */

export const Applied: Story = {
  name: 'In the UI',
  render: () => (
    <div className="space-y-5 max-w-3xl">
      <SectionHeader
        title="Applied recipes"
        subtitle="The combinations actually used across panels, headers, and code surfaces."
      />

      <div className="rounded-md border border-border bg-surface p-4 space-y-1">
        <div className="text-xs font-mono text-text-muted mb-2">
          Hero · font-heading text-5xl font-medium tracking-tight
        </div>
        <h1 className="font-heading text-5xl font-medium tracking-tight">
          Context, not just code.
        </h1>
      </div>

      <div className="rounded-md border border-border bg-surface p-4 space-y-2">
        <div className="text-xs font-mono text-text-muted mb-2">
          Panel title · text-sm font-semibold
        </div>
        <div className="text-sm font-semibold">Graph Structure</div>
        <div className="text-xs font-mono text-text-muted mb-2 pt-2 border-t border-border-subtle">
          Section label · text-xs font-semibold uppercase tracking-wider text-text-muted
        </div>
        <div className="text-xs font-semibold uppercase tracking-wider text-text-muted">
          Module overview
        </div>
        <div className="text-xs font-mono text-text-muted mb-2 pt-2 border-t border-border-subtle">
          Body row · text-sm
        </div>
        <div className="text-sm">547 files indexed across 8 modules.</div>
        <div className="text-xs font-mono text-text-muted mb-2 pt-2 border-t border-border-subtle">
          Meta · text-xs text-text-muted
        </div>
        <div className="text-xs text-text-muted">Generated 2h ago · structural</div>
      </div>

      <div className="rounded-md border border-border bg-surface p-4">
        <div className="text-xs font-mono text-text-muted mb-2">
          Inline path · font-mono text-xs
        </div>
        <span className="font-mono text-xs">src/prep/core/atlas/generator.py</span>
      </div>

      <div className="rounded-md border border-border bg-surface p-4">
        <div className="text-xs font-mono text-text-muted mb-2">
          Code block · font-mono text-sm leading-normal
        </div>
        <pre className="rounded-md border border-border bg-surface-raised p-3 text-sm leading-normal font-mono overflow-x-auto">
          {CODE_SAMPLE}
        </pre>
      </div>
    </div>
  ),
};
