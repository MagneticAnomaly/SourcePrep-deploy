# Phase 130 — Docs Site Staleness Sweep

> **Source issue:** Issue 12 in `docs/MARKETING_SITE_AUDIT.md`
> **Origin date:** 2026-05-07
> **Status:** Substantially complete 2026-05-08 — see "Outcome" below

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

- [x] `src/config/docs.ts` — sidebar registry. **Done** (commit 918c0a3c):
      replaced `/mcp/cursor` and `/mcp/windsurf` with the real `/mcp/ides` and
      `/mcp/terminal`; added missing real guides (audit-enrichment,
      dynamic-model-loading, smart-search).
- [x] `src/app/sitemap.ts` — sitemap. **Done** (commit 918c0a3c): removed
      deleted hubs (`/concepts`, `/guides`) and dead routes
      (`/concepts/trace-index`, `/dashboard/settings`, `/mcp/cursor`,
      `/mcp/windsurf`); added the real concept and guide pages plus `/search`.
- [x] `src/app/dashboard/page.tsx` and `src/app/dashboard/projects/page.tsx` —
      **Done** (commit 5c29bdef): the page sold a defunct "Two-Pane
      Architecture (Panel A / Panel B)" mental model. Rewrote against the
      shipping reality (modular ModularDashboard + 27 panels in 4 categories
      + 15-stage pipeline). 122 inserts / 164 deletes net.
- [x] `src/app/mcp/page.tsx` — **Done** (commit ae335f35): added the missing
      `prep_concepts` tool to the bullet list and the Tools Reference table
      (page had 5 of 6); fixed the `prep_audit` action enum to include the
      current values (`antibodies`, `advise`); refreshed prose for the dual
      structural / enrichment modes.

### Tier 2 — guides

- [x] `src/app/guides/embeddings/page.tsx` — verified current (commit 16523ebc
      triage notes): `prep models` CLI + `/embedding/{status,download}`
      endpoints all confirmed.
- [x] `src/app/guides/models/page.tsx` — **fixed** (commit d3e4d7a7): page
      claimed 4 model slots; actual is 5 (Embedding, Single/Fast, Code,
      Thinking, Swarm Coordinator). Storybook embed id was wrong
      (`llm-aimodelssettings--default` →
      `dashboard-widgets-settings-aimodelssettings--default`). Smart
      Compression demoted from "fourth slot" to a side note (it is a
      separate config block).
- [ ] `src/app/guides/model-advisor/page.tsx` — **deferred** to its own
      mini-phase: page has an in-source TODO admitting stale Claude pricing,
      and refresh needs live vendor + Ollama Cloud pricing research before
      bumping numbers. Logged as a Phase-130 follow-up.
- [x] `src/app/guides/dynamic-model-loading/page.tsx` — verified current
      (no staleness signals).
- [x] `src/app/guides/byok-batching/page.tsx` — **fixed** (commit 16523ebc):
      Privacy Policy link pointed at a non-existent `nicobailey/SourcePrep`
      repo; switched to the marketing site's `/security` page (the
      canonical URL). Storybook embed id corrected
      (`llm-endpointmanager--default` →
      `dashboard-widgets-settings-endpointmanager--interactive`).
- [x] `src/app/guides/concurrency-discovery/page.tsx` — verified current:
      `POST /compute/concurrency/clear` and `GET /compute/scheduler` exist
      exactly as documented in `src/prep/api/routers/compute.py`.
- [x] `src/app/guides/path-weights/page.tsx` — **fixed** (commit 16523ebc):
      "FolderTree panel" replaced with "Scope panel" (matches the actual
      panel title in panelRegistry.ts).
- [x] `src/app/guides/knowledge-scope/page.tsx` — **fixed** (commit d3e4d7a7):
      "FolderTree panel" / "Knowledge Sources panel" both replaced with
      "Scope panel"; broken Storybook embed
      (`agents-agentscopepanel--with-scopes`, story doesn't exist) replaced
      with the real one
      (`dashboard-widgets-foldertreepanel--scope-panel-named-populated`).
- [x] `src/app/guides/smart-search/page.tsx` — verified current: 7-intent
      enum and `TRACE > RATIONALE > COMPARE > EXAMPLE > DISCOVER > LOCATE >
      EXPLAIN` tiebreaker order both match `src/prep/core/intent.py` exactly.
- [x] `src/app/guides/audit-enrichment/page.tsx` — verified current: every
      enriched-finding field (dependents, hub_status, module, concepts,
      risk_score, recommendation) verified field-by-field against
      `EnrichedFinding` in `src/prep/core/enrichment.py`.
- [x] `src/app/guides/codebase-audit/page.tsx` — verified current: legacy
      `prep_audit_*` aliases are still exposed in `mcp_tools.py`;
      Storybook ids for AuditPanel and OpportunitiesPanel resolve.
- [x] `src/app/guides/compression/page.tsx` — verified current: 50K (Tier 1
      claude/gemini) and 20K (local cline) char budgets match
      `_CLIENT_BUDGETS` in `src/prep/mcp/server.py`.
- [x] `src/app/guides/team-sync/page.tsx` — Storybook embed id verified;
      no staleness signals.
- [x] `src/app/guides/enterprise-deploy/page.tsx` — no staleness signals
      under the source-of-truth checks. (Note: page links to
      `MagneticAnomaly/SourcePrep-deploy` GitHub repo — out of scope to
      verify whether the public repo currently exists; left untouched.)

### Tier 3 — reference-shape pages (lower drift risk)

- [x] `src/app/cli/page.tsx`, `src/app/cli/commands/page.tsx`,
      `src/app/cli/config/page.tsx` — **fixed** (commit 6d799794):
      `cli/commands` was advertised as "complete reference" but missed
      `prep config`, `prep drift`, `prep flow`, `prep opportunities` —
      added them. `cli/config` had stale `~/.sourceprep/config.json`
      paths from before Phase 113; switched to
      `~/.local/share/sourceprep/` and added the `PREP_DATA_DIR` env-var
      row. `cli/page` (overview) verified clean.
- [x] `src/app/getting-started/page.tsx`, `installation/page.tsx`,
      `quick-start/page.tsx` — quick-start had a stale "Knowledge Sources"
      panel reference (fixed to "Scope" in commit 6d799794). Other pages
      verified current: 11-analyzer claim matches actual analyzer count;
      "free tier 3 projects" matches `feature_gate.py`.
- [x] `src/app/troubleshooting/page.tsx` — **fixed** (commit 6d799794):
      stale "model (~300MB) on first run"; actual ONNX model is ~132 MB.
      `max_file_bytes` 500KB default verified against `config_manager.py`.
- [x] `src/app/page.tsx` (docs home) — **fixed** (commit 6d799794):
      "Guides" feature card linked to the deleted `/guides` hub (404 on
      every click). Replaced with a "Core Concepts" card (→
      `/concepts/indexing`) and an "Embedding Models" card (→
      `/guides/embeddings`); reordered the grid to put Getting Started and
      Concepts first.

## Outcome

Sweep landed 2026-05-08 across 8 commits between 918c0a3c and 6d799794.
13 of 14 tier-2 guides + every tier-1 and tier-3 page touched or
verified. One tier-2 page (`model-advisor`) deferred to its own
mini-phase because its pricing data needs live vendor research that
this sweep can't do confidently from inside.

For each fix, ground truth was sourced from the actual code (panel
registries, MCP tool schemas, audit analyzers, pipeline stage tables,
config defaults) — typically using `prep` MCP for the structural
overview and direct file reads for the specific values. The commit
messages document the source-of-truth file each claim was verified
against.

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
