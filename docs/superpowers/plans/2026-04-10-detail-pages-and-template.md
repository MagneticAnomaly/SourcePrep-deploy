# Detail Pages & Template Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reusable `DetailPageLayout` template component and 5 new marketing detail pages that showcase Prep's key differentiators — keeping content at the "why/what" level and linking to docs.runprep.io for "how-to."

**Architecture:** A shared layout component in `@prep/ui` provides the structural skeleton (back link, hero, content area, docs CTA, footer CTA). Each page imports it and passes content as children/props. Landing page gets link cards in the capabilities section pointing to these pages.

**Tech Stack:** Next.js App Router, React, Tailwind CSS, `@prep/ui` component library, `constructMetadata()` helper.

---

## Information Flow Design

Each detail page occupies a specific position in the funnel:

```
Landing Page (awareness) → Detail Page (understanding) → docs.runprep.io (how-to/setup)
```

| Detail Page | Marketing Angle (why/what) | Docs Link Target | What NOT to include |
|---|---|---|---|
| **Paperclip** | Agent orchestration story, auto-push findings, Prep addresses | `docs.runprep.io/integrations/paperclip` | Plugin install steps, API config |
| **Claude Code** | First-class MCP integration, skills, auto-approve, AGENTS.md gen | `docs.runprep.io/integrations/claude-code` | .claude/settings.json setup, CLI flags |
| **Graph Enrichment** | 11-stage pipeline journey from Rust parse to deep knowledge | `docs.runprep.io/concepts/graph-enrichment` | Pipeline config, stage tuning |
| **Immune System** | Concepts → assertions → antibodies → violation alerts | `docs.runprep.io/concepts/immune-system` | Concept CRUD API, antibody config |
| **IDE Ecosystem** | Universal MCP story, per-editor value props, setup at a glance | `docs.runprep.io/integrations` | Full MCP config JSON, troubleshooting |

---

## File Structure

### New Files

```
packages/ui/src/components/marketing/DetailPageLayout.tsx    — Reusable template component
websites/apps/marketing/src/app/paperclip/page.tsx           — Paperclip integration page
websites/apps/marketing/src/app/paperclip/layout.tsx         — Metadata
websites/apps/marketing/src/app/claude-code/page.tsx         — Claude Code integration page
websites/apps/marketing/src/app/claude-code/layout.tsx       — Metadata
websites/apps/marketing/src/app/graph-enrichment/page.tsx    — Pipeline deep-dive page
websites/apps/marketing/src/app/graph-enrichment/layout.tsx  — Metadata
websites/apps/marketing/src/app/immune-system/page.tsx       — Immune system page
websites/apps/marketing/src/app/immune-system/layout.tsx     — Metadata
websites/apps/marketing/src/app/integrations/page.tsx        — IDE ecosystem page
websites/apps/marketing/src/app/integrations/layout.tsx      — Metadata
```

### Modified Files

```
packages/ui/src/components/marketing/index.ts                — Export DetailPageLayout
packages/ui/src/components/index.ts                          — Re-export from marketing
packages/ui/src/index.ts                                     — Re-export from components
websites/apps/marketing/src/app/page.tsx                     — Add link cards below capabilities
```

---

### Task 1: Build DetailPageLayout Component

**Files:**
- Create: `packages/ui/src/components/marketing/DetailPageLayout.tsx`
- Modify: `packages/ui/src/components/marketing/index.ts`
- Modify: `packages/ui/src/components/index.ts`
- Modify: `packages/ui/src/index.ts`

- [ ] **Step 1: Create the DetailPageLayout component**

```tsx
// packages/ui/src/components/marketing/DetailPageLayout.tsx
"use client";

import { ArrowLeft, ArrowRight, ExternalLink } from 'lucide-react';

export interface DetailPageSection {
  id: string;
  label: string;
}

export interface DetailPageLayoutProps {
  title: string;
  subtitle: string;
  description: string;
  badge?: string;
  sections: DetailPageSection[];
  docsUrl: string;
  docsLabel?: string;
  children: React.ReactNode;
}

export function DetailPageLayout({
  title,
  subtitle,
  description,
  badge,
  sections,
  docsUrl,
  docsLabel = 'Read the full guide',
  children,
}: DetailPageLayoutProps) {
  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto max-w-7xl px-6 py-12">

        {/* Top bar */}
        <div className="flex items-center justify-between border-b border-border pb-6 mb-12">
          <a href="/" className="text-sm text-text-muted hover:text-primary transition-colors inline-flex items-center gap-2">
            <ArrowLeft className="w-3 h-3" /> Home
          </a>
          {badge && (
            <span className="font-mono text-xs uppercase tracking-widest text-primary">{badge}</span>
          )}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12">

          {/* Sidebar */}
          <div className="lg:col-span-3">
            <div className="sticky top-20 space-y-8">
              <div>
                <p className="text-xs font-mono font-bold uppercase tracking-widest text-primary mb-3">{subtitle}</p>
                <h1 className="text-3xl font-bold tracking-tight text-text">{title}</h1>
                <p className="mt-3 text-sm text-text-muted leading-relaxed">{description}</p>
              </div>

              {sections.length > 0 && (
                <nav className="space-y-1 border-l border-border-subtle">
                  {sections.map((section) => (
                    <a
                      key={section.id}
                      href={`#${section.id}`}
                      className="block pl-4 py-2 text-sm text-text-muted hover:text-primary hover:border-l-2 hover:border-primary hover:bg-surface transition-all -ml-[1px]"
                    >
                      {section.label}
                    </a>
                  ))}
                </nav>
              )}

              <div className="pt-6 border-t border-border-subtle space-y-3">
                <a
                  href={docsUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 text-sm font-medium text-primary hover:underline underline-offset-4"
                >
                  <ExternalLink className="w-3.5 h-3.5" />
                  {docsLabel}
                </a>
                <a
                  href="mailto:support@runprep.io?subject=Prep%20Beta%20Access%20Request"
                  className="flex items-center gap-2 text-sm font-medium text-text-muted hover:text-text transition-colors"
                >
                  Request Beta Access <ArrowRight className="w-3 h-3" />
                </a>
              </div>
            </div>
          </div>

          {/* Main content */}
          <div className="lg:col-span-9 space-y-16">
            {children}
          </div>
        </div>
      </div>
    </main>
  );
}
```

- [ ] **Step 2: Export from marketing/index.ts**

Add to `packages/ui/src/components/marketing/index.ts`:
```ts
export { DetailPageLayout } from './DetailPageLayout';
export type { DetailPageLayoutProps, DetailPageSection } from './DetailPageLayout';
```

- [ ] **Step 3: Re-export from components/index.ts**

Add to `packages/ui/src/components/index.ts`:
```ts
export { DetailPageLayout } from './marketing';
export type { DetailPageLayoutProps, DetailPageSection } from './marketing';
```

- [ ] **Step 4: Re-export from top-level index.ts**

Add to `packages/ui/src/index.ts`:
```ts
export { DetailPageLayout } from './components/marketing';
export type { DetailPageLayoutProps, DetailPageSection } from './components/marketing';
```

- [ ] **Step 5: Build UI package**

Run: `npx turbo run build --filter=@prep/ui --force`
Expected: Build succeeds

- [ ] **Step 6: Commit**

```bash
git add packages/ui/src/components/marketing/DetailPageLayout.tsx packages/ui/src/components/marketing/index.ts packages/ui/src/components/index.ts packages/ui/src/index.ts
git commit -m "feat(ui): add DetailPageLayout template for marketing detail pages"
```

---

### Task 2: Paperclip Integration Page

**Files:**
- Create: `websites/apps/marketing/src/app/paperclip/page.tsx`
- Create: `websites/apps/marketing/src/app/paperclip/layout.tsx`

**Content strategy:** Tell the "agent orchestration" story. Prep as the knowledge backbone for Paperclip's autonomous agent teams. Show the hybrid MCP+REST model, Prep addresses, auto-push findings. Link to docs for plugin install and API setup.

- [ ] **Step 1: Create layout.tsx with metadata**

```tsx
// websites/apps/marketing/src/app/paperclip/layout.tsx
import { constructMetadata } from '../metadata-helper';

export const metadata = constructMetadata({
  title: 'Paperclip Integration — Agent Orchestration with Prep',
  description: 'Prep provides deep structural codebase intelligence to Paperclip agent teams. Auto-push findings, Prep addresses, and hybrid MCP+REST integration.',
  path: '/paperclip',
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
```

- [ ] **Step 2: Create page.tsx**

```tsx
// websites/apps/marketing/src/app/paperclip/page.tsx
"use client";

import { DetailPageLayout } from '@prep/ui';
import { GitBranch, Zap, Link2, RefreshCw, ArrowRight } from 'lucide-react';

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
          <div className="text-[#8b949e] mb-2">// Agent verifies a finding before acting on it:</div>
          <div className="text-[#79c0ff]">prep://project-id/<span className="text-[#3fb950]">HEALTH-a7b9</span></div>
          <div className="text-[#8b949e] mt-2">// Returns: current status, structural context, related concepts</div>
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
```

- [ ] **Step 3: Commit**

```bash
git add websites/apps/marketing/src/app/paperclip/
git commit -m "feat(marketing): add Paperclip integration detail page"
```

---

### Task 3: Claude Code Integration Page

**Files:**
- Create: `websites/apps/marketing/src/app/claude-code/page.tsx`
- Create: `websites/apps/marketing/src/app/claude-code/layout.tsx`

**Content strategy:** Position Prep as the #1 MCP server for Claude Code. Skills, auto-approve, AGENTS.md generation, client-aware content delivery. Link to docs for setup.

- [ ] **Step 1: Create layout.tsx**

```tsx
import { constructMetadata } from '../metadata-helper';

export const metadata = constructMetadata({
  title: 'Claude Code Integration — Prep MCP Server',
  description: 'Prep is the best MCP server for Claude Code. Six tools, auto-approve, skills integration, and client-aware content delivery.',
  path: '/claude-code',
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
```

- [ ] **Step 2: Create page.tsx**

Build page with sections: Why Claude Code + Prep, Six Tools at a Glance, Auto-Approve & Skills, AGENTS.md Generation, Client-Aware Delivery. Use `DetailPageLayout` with `docsUrl="https://docs.runprep.io/integrations/claude-code"`. Show the 6 tools in a compact grid. Include a MCP config snippet as a visual element (not how-to — just "this is all it takes"). Link to docs for full setup.

- [ ] **Step 3: Commit**

```bash
git add websites/apps/marketing/src/app/claude-code/
git commit -m "feat(marketing): add Claude Code integration detail page"
```

---

### Task 4: Graph Enrichment Pipeline Page

**Files:**
- Create: `websites/apps/marketing/src/app/graph-enrichment/page.tsx`
- Create: `websites/apps/marketing/src/app/graph-enrichment/layout.tsx`

**Content strategy:** The "how it works" deep-dive. Show the 11-stage pipeline journey from raw file → Rust parse → embeddings → LLM enrichment → deep knowledge. Emphasize that fast sync stages take seconds while deep stages run in the background. Link to docs for pipeline config.

- [ ] **Step 1: Create layout.tsx**

```tsx
import { constructMetadata } from '../metadata-helper';

export const metadata = constructMetadata({
  title: 'Graph Enrichment Pipeline — How Prep Understands Your Code',
  description: 'An 11-stage pipeline from Rust parsing to deep LLM knowledge. Fast sync in seconds, deep enrichment in the background.',
  path: '/graph-enrichment',
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
```

- [ ] **Step 2: Create page.tsx**

Build page with sections: The Journey, Fast Sync Stages (1-5), Deep Enrichment Stages (6-11), Always Running. Use `DetailPageLayout` with `docsUrl="https://docs.runprep.io/concepts/graph-enrichment"`. Show the 11 stages as a visual pipeline/timeline. Each stage gets a name, icon, and one-line description. Highlight the fast/deep split with a divider. Link to docs for pipeline tuning.

- [ ] **Step 3: Commit**

```bash
git add websites/apps/marketing/src/app/graph-enrichment/
git commit -m "feat(marketing): add graph enrichment pipeline detail page"
```

---

### Task 5: Immune System Page

**Files:**
- Create: `websites/apps/marketing/src/app/immune-system/page.tsx`
- Create: `websites/apps/marketing/src/app/immune-system/layout.tsx`

**Content strategy:** Show the concepts → assertions → antibodies → violation alerts flow. This is a unique differentiator no competitor has. Emphasize it's informational (nothing blocked), and that it creates a living set of architectural rules from recorded decisions. Link to docs for concept API.

- [ ] **Step 1: Create layout.tsx**

```tsx
import { constructMetadata } from '../metadata-helper';

export const metadata = constructMetadata({
  title: 'Immune System — Architectural Guardrails from Design Decisions',
  description: 'Prep derives runtime defenses from your design decisions. Concepts become testable assertions that catch architectural violations before they ship.',
  path: '/immune-system',
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
```

- [ ] **Step 2: Create page.tsx**

Build page with sections: How It Works, Concepts, Assertions & Antibodies, Violation Alerts, Living Architecture. Use `DetailPageLayout` with `docsUrl="https://docs.runprep.io/concepts/immune-system"`. Show the flow visually: Concept → Assertion → Antibody → Alert. Include an example concept ("payment module must not import db.transaction directly") and show how it becomes a runtime check. Link to docs for concept CRUD.

- [ ] **Step 3: Commit**

```bash
git add websites/apps/marketing/src/app/immune-system/
git commit -m "feat(marketing): add immune system detail page"
```

---

### Task 6: IDE Ecosystem Page

**Files:**
- Create: `websites/apps/marketing/src/app/integrations/page.tsx`
- Create: `websites/apps/marketing/src/app/integrations/layout.tsx`

**Content strategy:** Universal MCP story. One server, every editor. Per-editor value props and a quick "what you get" for each: Claude Code (best supported), Antigravity, Cursor, Windsurf, VS Code. Not a setup guide — link to docs for that. Show that Prep auto-detects the client and tailors content delivery.

- [ ] **Step 1: Create layout.tsx**

```tsx
import { constructMetadata } from '../metadata-helper';

export const metadata = constructMetadata({
  title: 'IDE Integrations — One MCP Server, Every Editor',
  description: 'Prep connects to Claude Code, Antigravity, Cursor, Windsurf, VS Code, and any MCP-compatible tool. One server, every editor.',
  path: '/integrations',
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
```

- [ ] **Step 2: Create page.tsx**

Build page with sections: One Server Every Editor, Claude Code (deepest), Antigravity, Cursor & Windsurf, VS Code Extension, Client-Aware Delivery. Use `DetailPageLayout` with `docsUrl="https://docs.runprep.io/integrations"`. Each editor gets a card with: logo placeholder, 2-3 bullet value props, link to its specific docs page. Emphasize Claude Code as the deepest integration. Link to docs for setup.

- [ ] **Step 3: Commit**

```bash
git add websites/apps/marketing/src/app/integrations/
git commit -m "feat(marketing): add IDE ecosystem detail page"
```

---

### Task 7: Add Link Cards to Landing Page

**Files:**
- Modify: `websites/apps/marketing/src/app/page.tsx`

**Content strategy:** Add a row of 5 compact link cards between the capabilities grid and the YouTube embed. Each card links to a detail page with a title, one-line hook, and arrow.

- [ ] **Step 1: Add link cards section**

After the `<FeatureBlocks ... variant="cards" />` line and before the YouTube section, add:

```tsx
{/* Deep-dive pages */}
<div className="mt-12 grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
  {[
    { href: '/claude-code', title: 'Claude Code', desc: 'Our deepest integration' },
    { href: '/paperclip', title: 'Paperclip', desc: 'Agent orchestration' },
    { href: '/graph-enrichment', title: 'Graph Enrichment', desc: '11-stage pipeline' },
    { href: '/immune-system', title: 'Immune System', desc: 'Architectural guardrails' },
    { href: '/integrations', title: 'IDE Ecosystem', desc: 'One server, every editor' },
  ].map((link) => (
    <Link
      key={link.href}
      href={link.href}
      className="flex items-center justify-between rounded-lg border border-border bg-surface px-4 py-3 hover:border-primary/40 hover:bg-surface-raised transition-all group"
    >
      <div>
        <span className="text-sm font-medium text-text group-hover:text-primary transition-colors">{link.title}</span>
        <span className="text-xs text-text-muted ml-2">{link.desc}</span>
      </div>
      <ArrowRight className="w-3.5 h-3.5 text-text-muted group-hover:text-primary transition-colors" />
    </Link>
  ))}
</div>
```

- [ ] **Step 2: Build and verify**

Run: `npx turbo run build --filter=@prep/ui --force && cd websites/apps/marketing && npx tsc --noEmit`
Expected: Both succeed

- [ ] **Step 3: Commit**

```bash
git add websites/apps/marketing/src/app/page.tsx
git commit -m "feat(marketing): add deep-dive link cards to landing page"
```

---

### Task 8: Build & Final Verification

- [ ] **Step 1: Build UI package**

Run: `npx turbo run build --filter=@prep/ui --force`
Expected: Success

- [ ] **Step 2: Typecheck marketing site**

Run: `cd websites/apps/marketing && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Verify all new routes exist**

Run: `find websites/apps/marketing/src/app -name 'page.tsx' | sort`
Expected: Should include paperclip, claude-code, graph-enrichment, immune-system, integrations

- [ ] **Step 4: Final commit**

```bash
git add .
git commit -m "feat(marketing): complete detail pages with template and link cards"
```
