# CLI Demos Dev Page — Design Spec

**Date:** 2026-04-22
**Status:** Draft
**Owner:** Eric

## Purpose

Create a dev-only preview page where we can iterate rapidly on marketing CLI/IDE animation scripts. Lets us see many script variations side-by-side in real marketing context, so we can choose the most natural/organic ones before promoting them to the production `demo-scripts.ts`.

## Problem

The current marketing home page uses six `AnimatedCLI` demos (one per SourcePrep tool) plus one `AnimatedIDE` demo, sourced from `packages/ui/src/components/console/demo-scripts.ts`. The prompts are too literal ("give me an overview of this project", "I ran ruff and semgrep — can you enrich these findings?") and don't reflect how devs actually talk to an AI agent.

We need a way to draft and visually compare many alternative scripts per tool without touching the production demos or the marketing home page.

## Scope

**In scope:**
- A new route `/dev/cli-demos` inside the marketing app
- A variants file holding draft `CliScript` definitions
- A grid layout that autoplays all variants in parallel, filterable by tool
- Exclusion from `sitemap.ts` and `robots.ts`

**Out of scope:**
- In-browser script editing
- A/B voting or analytics
- Production gating beyond non-indexing (URL-only discovery is sufficient)
- Modifying the existing `demo-scripts.ts` or marketing home page (promotion happens manually when a variant is blessed)

## Design

### File layout

```
websites/apps/marketing/src/app/dev/cli-demos/
  page.tsx       — the dev page (client component)
  variants.ts    — draft CliScript definitions + metadata
```

### Variants data shape

```ts
type DemoVariant = {
  id: string;              // stable key, e.g. "impact-rename"
  tool: 'prep' | 'prep_search' | 'prep_impact' | 'prep_audit' | 'prep_observe' | 'prep_concepts' | 'ide';
  label: string;           // short human name, e.g. "Rename with public API surface"
  note?: string;           // one-line "why this prompt" explanation for reviewer
  script: CliScript;       // the actual animation script
};
```

`variants.ts` exports `const variants: DemoVariant[]`. We seed it with the first approved scenario (`prep_impact` rename) and add more as we iterate.

### Page layout

- Header row: page title, short purpose blurb, a tool filter `<select>` (`all | prep | prep_search | prep_impact | prep_audit | prep_observe | prep_concepts | ide`)
- Grid: `grid-cols-1 md:grid-cols-2 gap-6` — flat, no tabs
- Each card:
  - Top bar: tool badge (colored pill), variant label
  - Optional note line (italic, muted)
  - `<AnimatedCLI script={v.script} theme="dark" autoPlay />` or `<AnimatedIDE script={v.script} />` depending on `tool === 'ide'`
  - Collapsible `<details>` showing pretty-printed JSON of the raw script for copy-paste

### Gating

- Page is not linked from nav, footer, or sitemap
- Add its path to `sitemap.ts` exclusion and `robots.ts` disallow
- No environment gating in this pass (URL-only is sufficient; harden later if needed)

## Non-goals

- Not changing the marketing home page
- Not changing `packages/ui/src/components/console/demo-scripts.ts`
- Not building Storybook stories for the variants (Storybook is for component API; this is for copy iteration)

## Testing

- Visual only. Run `npm run dev` from `websites/apps/marketing`, visit `/dev/cli-demos`, confirm all variants autoplay and loop.
- No automated tests in this pass.

## Follow-ups (not in scope)

- Once a variant is blessed, port it into `demo-scripts.ts` and update the marketing home page imports.
- Optionally, later, add environment gating (404 in production) if the page starts to leak.
