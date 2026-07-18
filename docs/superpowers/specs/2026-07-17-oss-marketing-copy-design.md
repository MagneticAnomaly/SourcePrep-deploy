# OSS Marketing Copy Update — Design Spec

**Date:** 2026-07-17
**Status:** Approved in session (design); spec pending Eric review
**Owner:** Eric / Claude session
**Depends on:** `docs/Phase142_OSS-First/OPEN_CORE_SPLIT.md` (decisions locked 2026-05-30)
**Related:** Phase 143 (docs cleanup / two-repo), Phase 144 (legal — blocks *deploy*, not this prep work)

## Goal

Rewrite the marketing site (`websites/apps/marketing`) from closed-beta
proprietary positioning to the locked Phase 142 open-core positioning, on an
isolated worktree/branch, reviewed locally. **Nothing is pushed or deployed** —
Eric deploys later, at or after OSS launch.

## Decisions made in this brainstorm

1. **Scope:** update the website now, review locally; deploy later (Eric).
2. **CTA posture:** keep `IS_BETA_MODE` switchable. Both states must render
   coherently with the new copy; Eric picks the state at deploy time.
3. **Terms:** full draft rewrite to open-core reality, entity fixed to
   Magnetic Anomaly LLC, visibly marked pending attorney review (Phase 144).

## Source of truth for positioning

`docs/Phase142_OSS-First/OPEN_CORE_SPLIT.md`. Key facts the copy must state
correctly:

| Tier | Price | What it is |
|---|---|---|
| Open Source | $0, Apache 2.0 | The **full single-user product**: engine, daemon, CLI, MCP server, dashboard, VS Code extension, all prompts. Unlimited projects. Self-hosted. Community support (GitHub Issues/Discussions). |
| Pro | $7/mo or **$70 one-time** (was $79) | Signed/notarized DMG/MSI from sourceprep.io, auto-update, license-key activation, email support (5 business days). Same engine — zero capability differences. |
| Teams | $15/seat/mo or $144/seat/yr, 3-seat min | Hosted org-shared indexes, SSO, RBAC, audit logs, faster support. **Phase 1 posture: "Coming soon — Q3 2026" + waitlist CTA.** |
| Enterprise | $50/seat/mo annual, 10-seat min; $5k setup engagement | Teams + air-gapped deployment + named contact/office hours. **Phase 1 posture: coming soon / contact.** |

Hard rules:

- The old Free tier (3 projects) is **retired** — OSS replaces it. No
  3-project-cap language anywhere.
- **Never imply the OSS is feature-limited.** Paid = infrastructure + services
  (installer polish, hosted backend, support), never capabilities or prompts.
- Privacy claim preserved: indexing is local, code never leaves the machine;
  the future hosted backend syncs embeddings + graph metadata only.
- Funding statement survives reframed: "we fund development through Pro/Teams,
  not by monetizing your data."
- Voice: plain language / outcome first; jargon (epistemic, AST, 15-stage) is
  supporting detail only. Trim redundant copy while editing.
- Brand: "SourcePrep" in user-facing copy; `prep` only as CLI/tool names.
- Entity: **Magnetic Anomaly LLC** (not "SourcePrep Inc.").

## Worktree / branch setup

- Worktree: `.claude/worktrees/oss-marketing-copy`
- Branch: `marketing/oss-launch-copy`, based on **local `main` (`e4f04392`)**
  — the unpushed Phase 145/147 train does not touch marketing surfaces
  (verified), so this equals origin content for our scope while keeping the
  eventual merge trivial.
- `npm install` inside the worktree so the marketing dev server and builds run
  from it.
- Main working tree (32 dirty files, unrelated WIP), stash (incl. protected
  `stash@{0}`), and existing worktrees are untouched. No git push at any point.

## Page-by-page changes

All paths relative to `websites/apps/marketing/`. Line anchors from the
2026-07-17 survey; re-verify at edit time.

### `/pricing` — `src/app/pricing/page.tsx`, `src/lib/pricing.ts`, `src/app/pricing/layout.tsx`
- New 4-column grid per the tier table above. Teams/Enterprise render as
  coming-soon cards with waitlist/contact CTAs (mailto convention).
- Remove 3-project cap, "License management", "unlimited projects" upsell
  framing. Pro perpetual $79 → $70 ("Best value" crossover: 10× monthly).
- `pricing.ts`: PPP discount bands stay (they apply to Pro). Keep
  `LS_CHECKOUT_URLS` mechanics; **flag:** perpetual URL still points at the
  $79 Lemon Squeezy product until Eric reconfigures LS — code comment at the
  URL, copy shows $70.
- `layout.tsx:5` metadata: replace free-tier/perpetual-license phrasing with
  open-source + Pro framing.

### `/faq` — `src/app/faq/page.tsx`
- `:334-342` "Why pay for this?" → open-source answer: the product is free and
  Apache 2.0; Pro buys signed installer + auto-update + support; funding
  statement reframed.
- `:275` cloud-call answer: license activation call is Pro-installer-only; the
  OSS path makes no license calls.
- `:20` "works on every tier, including Free" → works in the open-source
  version.

### `/security` — `src/app/security/page.tsx`
- `:138-147` "Offline Verification" → scoped to Pro installer.
- `:116-117` allowed-outbound table: `/activate-license` marked Pro-only.
- `:250-252` collected data: license key / machine ID marked Pro-only; OSS
  path collects nothing.
- `:258-266` payments and `:281-282` license-record retention stay (paid tiers
  exist) with Pro/Teams scoping.

### `/about` — `src/app/about/page.tsx`
- `:104-108` "Own your tools" → OSS inversion: it's Apache 2.0, you already
  own it; Pro/Teams fund development.

### `/compare/prep-vs-greptile` — `page.tsx`
- `:108` perpetual-license claim → open source (Apache 2.0) + optional Pro
  perpetual; `:97` sharpen open-source vs proprietary-dashboard contrast.
- Beta CTA rows (`:124-125`, and `prep-vs-cursor-indexing:106-107`) follow the
  IS_BETA_MODE treatment below.

### `/download` — `src/app/download/page.tsx`
- `:84` "Free tier included — no account required" → open-source framing
  (Apache 2.0, no account, no license).
- Present both install paths per the distribution table: OSS (pip/pipx, brew,
  build from source, GitHub Releases) vs Pro (signed DMG/MSI from
  sourceprep.io with auto-update).

### `/support` — `src/app/support/page.tsx`
- `:63`, `:76` align tier names and response targets to the Pillar 3 support
  matrix (Community / Pro / Teams / Enterprise); "license holders" phrasing
  only where it applies (Pro+).

### `/terms` — `src/app/terms/page.tsx` (DRAFT, flagged for legal)
- `:72` entity → Magnetic Anomaly LLC.
- `:77-108` License Grant/Restrictions → split: OSS governed by Apache 2.0
  (its own license, not these terms); commercial terms govern only Pro/Teams/
  Enterprise purchases (license keys non-transferable, etc. — keys may not be
  redistributed; the *source* may, under Apache 2.0).
- `:150-160` SLA table → Pillar 3 matrix.
- Visible banner: draft pending attorney review (Phase 144).

### `/changelog`, home below-hero — light touch
- `changelog:15-17` beta entry: mention open-source launch in the planned
  entry; keep factual.
- Home `page.tsx:35-42` sr-only SEO block: add open-source to the description.
- **Hero (`packages/ui` yale variant) is OFF-LIMITS. No edits to
  `packages/ui`.** `MarketingHero` receives `isBetaMode` as a prop from the
  marketing app, which is sufficient for the flag treatment.

### GitHub links
- Public repo URL `https://github.com/sourceprep/sourceprep` behind one shared
  constant in a new `src/lib/links.ts` — org name still unconfirmed; one-line
  change later.

## IS_BETA_MODE treatment

- Flags stay where they are (`src/app/page.tsx:10`,
  `src/app/pricing/page.tsx:29`, compare pages). No new plumbing — this is a
  copy pass, not a refactor; consolidation is out of scope.
- **Beta ON:** Request-Beta mailto CTAs unchanged, surrounding copy is
  open-core. Copy must not promise "download now / buy now" while gated.
- **Beta OFF:** launch CTAs — OSS download/install, Pro checkout, Teams
  waitlist mailto, Enterprise contact.
- Both states reviewed page-by-page before handoff.

## Verification

1. `npm run lint`, `npm run typecheck`, production `npm run build` for the
   marketing workspace, run inside the worktree.
2. Dev server from the worktree; Playwright walk of every changed page in
   **both** flag states; screenshots captured for review.
3. Adversarial content verification (independent agents): every changed page
   checked against OPEN_CORE_SPLIT facts (prices, tier names, retired Free
   tier, no OSS-is-limited implication), voice rules, brand split, entity
   naming, and hero-untouched.
4. Eric reviews live at localhost (commands provided) and/or via screenshots.

## Out of scope

- Home hero content (standing rule).
- `packages/ui` edits of any kind.
- `LICENSE` / `pyproject.toml` license-field flips (happen at mirror publish).
- Lemon Squeezy product reconfiguration ($70 product) — Eric, external.
- Docs site (`websites/apps/docs`) — grep for tier/pricing mentions is a
  follow-up check, not this pass.
- Phase 143 deliverables (ADRs, triage review, mirror tooling) — separate
  effort.
- Any `git push`, deploy, or Netlify trigger.

## Acceptance

- All listed pages read coherently as open-core in both flag states.
- No page implies the OSS is limited; no 3-project/Free-tier residue anywhere
  (`rg -i 'free tier|3 projects|three projects'` clean in marketing app,
  excluding intentional "Community" framing).
- Prices match OPEN_CORE_SPLIT exactly ($7/$70/$15/$144/$50 + minimums).
- Terms page carries the legal-review banner and Magnetic Anomaly LLC.
- lint + typecheck + build pass; branch exists only locally.
