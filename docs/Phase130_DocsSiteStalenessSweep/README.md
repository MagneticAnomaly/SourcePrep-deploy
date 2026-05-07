# Phase 130 — Docs Site Staleness Sweep

> **Source issue:** Issue 12 in `docs/MARKETING_SITE_AUDIT.md`
> **Origin date:** 2026-05-07
> **Status:** Scoped, not started

## Problem

Phase 9's resolution caught a structural surprise: `docs.sourceprep.io/concepts/graph-enrichment`
described a stale 9-stage pipeline while the product had moved to 15 stages. That
single page was wrong by **six entire stages**, and the marketing site told a different
story than docs. Once we landed Issue 9, we discovered the mismatch was a *symptom*,
not the disease — multiple other docs surfaces are similarly out of sync with the
product. The most visible smoking guns:

- `websites/apps/docs/src/app/sitemap.ts` advertises routes that **don't exist** on the
  site (`/mcp/cursor`, `/mcp/windsurf`, `/concepts/trace-index`, `/dashboard/settings`)
  and is **missing** real routes (most `/guides/*` subroutes).
- The docs sidebar (`docs/src/config/docs.ts`) likewise lists `/mcp/cursor` and
  `/mcp/windsurf` even though the actual routes are `/mcp/ides` and `/mcp/terminal`.
- `docs/src/app/concepts/code-graph/page.tsx` previously embedded a stale 9-stage
  pipeline summary (fixed in Step C, but representative of the rot).
- `docs/src/app/dashboard/page.tsx` references panels and flows that may or may not
  match the current dashboard architecture.

The scope of this phase is to do a careful, deliberate pass over **every** docs page
and bring it into agreement with the product as it ships today.

## Scope

In scope:

- `websites/apps/docs/src/app/**` — every page under the docs Next.js app.
- `websites/apps/docs/src/config/docs.ts` — the sidebar registry.
- `websites/apps/docs/src/app/sitemap.ts` — the sitemap.
- `websites/apps/docs/src/components/**` — only if a page can't be fixed without a
  component change.

Out of scope:

- Marketing site copy. Issues 8 / 10 already addressed the major marketing
  inaccuracies; the comprehensive marketing audit lives at
  `docs/MARKETING_SITE_AUDIT.md` and is its own ongoing track.
- Visual redesign of docs pages. The marketing-style layout was applied to concept
  pages in Step C; other docs pages should keep the existing AnchorHeading-style
  prose layout.
- The `concepts/*` pages — these were just rewritten in Step C and are current.

## Sources of truth (the cross-references each docs page must agree with)

| Topic | Source of truth |
|-------|-----------------|
| Pipeline stages and their semantics | `src/prep/services/pipeline/stages.py` |
| MCP tools (the 6 user-facing tool schemas) | `src/prep/mcp_tools.py` |
| MCP setup configs per editor/CLI | `packages/ui/src/config/mcpSetup.ts` (and the per-app duplicates listed in `MARKETING_SITE_AUDIT.md` Issue 10) |
| CLI commands and flags | `src/prep/cli.py` |
| Free vs Pro tier features | `src/prep/core/feature_gate.py` |
| Dashboard panel registry | `packages/ui/src/config/panelRegistry.ts` |
| Integration taxonomy (Claude Code primary CLI, Cursor primary IDE, Codex grouped with Claude Code, …) | Memory `feedback_marketing_vs_docs_split.md` and `MARKETING_SITE_AUDIT.md` Issue 10 resolution |

## Approach

A page-by-page sweep, ordered by likelihood of staleness rather than alphabetical.
For each page: open the file, compare every claim against the source of truth above,
fix what's wrong, leave what's correct alone, **trim excess copy** in passing per
durable instruction (`feedback_marketing_trim_excess.md`).

Don't do it as one giant commit. Each page (or small group of pages) gets its own
commit with a tight message so any regression bisects cleanly.

## Concrete page checklist

Suggested ordering — most-suspect first, since the early sweeps will surface
patterns we'll want to apply systematically to later pages.

### Tier 1 — known-stale or known-suspect

- [ ] `src/config/docs.ts` — sidebar registry. Remove fake routes (`/mcp/cursor`,
      `/mcp/windsurf`); ensure every kept entry maps to an actual file. Audit guide
      coverage (some sub-guides aren't listed in the sidebar).
- [ ] `src/app/sitemap.ts` — sitemap. Same cleanup as the sidebar plus add the
      missing `/guides/*` entries (and any other real routes).
- [ ] `src/app/dashboard/page.tsx` and `src/app/dashboard/projects/page.tsx` —
      verify against the current dashboard panel registry / current shipping
      dashboard UX. Likely outdated since the dashboard has been heavily reworked.
- [ ] `src/app/mcp/page.tsx` — the MCP overview page already had several fixes
      during Issue 10; verify the prose still matches the current MCP_TOOLS list
      and tool semantics.

### Tier 2 — guides

- [ ] `src/app/guides/embeddings/page.tsx`
- [ ] `src/app/guides/models/page.tsx` (in-line TODO comment about model refresh)
- [ ] `src/app/guides/model-advisor/page.tsx`
- [ ] `src/app/guides/dynamic-model-loading/page.tsx`
- [ ] `src/app/guides/byok-batching/page.tsx`
- [ ] `src/app/guides/concurrency-discovery/page.tsx`
- [ ] `src/app/guides/path-weights/page.tsx`
- [ ] `src/app/guides/knowledge-scope/page.tsx`
- [ ] `src/app/guides/smart-search/page.tsx`
- [ ] `src/app/guides/audit-enrichment/page.tsx`
- [ ] `src/app/guides/codebase-audit/page.tsx`
- [ ] `src/app/guides/compression/page.tsx`
- [ ] `src/app/guides/team-sync/page.tsx`
- [ ] `src/app/guides/enterprise-deploy/page.tsx`

### Tier 3 — reference-shape pages (lower drift risk)

- [ ] `src/app/cli/page.tsx`, `src/app/cli/commands/page.tsx`, `src/app/cli/config/page.tsx`
      — CLI reference. Verify against `src/prep/cli.py`.
- [ ] `src/app/getting-started/page.tsx`, `installation/page.tsx`, `quick-start/page.tsx`
      — install + first-run flow. Cross-check the package install instructions.
- [ ] `src/app/troubleshooting/page.tsx` — triage common failures. Cross-check error
      messages and remediation text against current behavior.
- [ ] `src/app/page.tsx` (docs home) — verify the feature card grid still matches
      the rest of the site.

## Out-of-scope but related (note for future work)

- Concept pages (`/concepts/*`) — already rewritten in Step C, current.
- `docs.sourceprep.io/faq` — already deleted (Step 4).
- The marketing-vs-docs canonical split is governed by
  `docs/MARKETING_NAV_CANONICAL.md` and the `feedback_marketing_vs_docs_split.md`
  memory rule. Any cross-site link this phase touches must respect them.

## Definition of done

- Every page in the checklist above has been visited.
- Each page either: (a) was correct as-is and is checked off, or (b) has a fix
  committed against it.
- The docs sitemap (`src/app/sitemap.ts`) and sidebar (`src/config/docs.ts`)
  contain only real routes and reflect the current site shape.
- No remaining cross-references to deleted or renamed routes anywhere under
  `websites/apps/docs/`.
- Issue 12 in `docs/MARKETING_SITE_AUDIT.md` is marked **RESOLVED**.

## Risk / blockers

- The dashboard pages are the highest-risk: the panel architecture has been
  reworked multiple times (Phase 122/124 spaghetti migration, Phase 127 multi-project
  queue) and the docs may need a substantive rewrite, not just touch-ups. If the
  rewrite turns into a redesign, split it into its own phase rather than letting
  this one balloon.
- Some guides describe Pro/Team-tier features that may have shifted; verify against
  `feature_gate.py` to avoid promising or gating things wrongly.

## Out-of-scope but worth recording

- The `marketing/dev/cli-demos` curation gallery (Step 2 / Issue 7) is gated dev-only
  but the variants catalog is still 1,888 lines and should eventually migrate into
  Storybook stories. Not this phase.
- Issue 13 (atlas prompt injection) is a product bug logged in `docs/MASTER_TODO.md`,
  not a docs-staleness item.
