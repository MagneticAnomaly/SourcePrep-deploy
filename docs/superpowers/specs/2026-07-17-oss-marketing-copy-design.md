# OSS Marketing Copy Update — Design Spec

**Date:** 2026-07-17 (amended same day, evening — see Amendment note)
**Status:** Approved in session; amended per DECISION_MEMO_2026-07-17 + REPO_TOPOLOGY + reality-check audit, amendments confirmed by Eric
**Owner:** Eric / Claude session
**Depends on:** `docs/Phase142_OSS-First/DECISION_MEMO_2026-07-17.md` (Part 0, hardened),
`docs/Phase142_OSS-First/OPEN_CORE_SPLIT.md` (Teams/Enterprise pricing SoT),
`docs/Phase142_OSS-First/LICENSING_RECOMMENDATION.md` (Apache-2.0 + DCO),
`docs/Phase142_OSS-First/REPO_TOPOLOGY.md` (MagneticAnomaly org, DECIDED 2026-07-17)
**Related:** Phase 143 (docs/two-repo), Phase 144 (legal), Phase 146 (security audit — license-crypto blocker)

> **Amendment note (2026-07-17 evening):** the original spec encoded the
> 2026-05-30 OPEN_CORE_SPLIT lock ($7/mo + $70 Pro, Q3 2026 Teams,
> sourceprep/sourceprep). A same-day decision sweep found DECISION_MEMO
> Part 0 (13:05) and REPO_TOPOLOGY (19:04) superseding those points. Eric
> confirmed: $29 Pro per the memo; Apache 2.0 named per the licensing
> recommendation. A product-reality audit also surfaced factually stale
> site claims now folded in as in-scope fixes.

## Goal

Rewrite the marketing site (`websites/apps/marketing`) from closed-beta
proprietary positioning to the current open-core positioning, on an isolated
worktree/branch, reviewed locally. **Nothing is pushed or deployed** — Eric
deploys later, at or after OSS launch.

## Decisions (all confirmed by Eric in session)

1. **Scope:** update the website now, review locally; deploy later.
2. **CTA posture:** `IS_BETA_MODE` stays switchable; both states render
   coherently; Eric picks the state at deploy time.
3. **Terms:** full draft rewrite, entity fixed to Magnetic Anomaly LLC,
   visibly marked pending attorney review (Phase 144).
4. **Pro pricing (supersedes $7/$70):** **$29 one-time perpetual** — includes
   12 months of updates, app keeps working forever; optional ~$15/yr to keep
   updating after that; name-your-price with a $29 floor; self-build stays
   free and prominent. No subscription.
5. **No live purchase CTAs anywhere, in either flag state.** Checkout is
   unwired and Phase 146 proved the shipped license crypto void (forgeable
   keys). Pro CTAs are "coming soon / notify me" until that clears.
6. **License naming:** say **Apache 2.0** (per LICENSING_RECOMMENDATION:
   Apache-2.0 + **DCO, not CLA**, license permanent). Pre-deploy gate:
   backlog A1 formally closed before any push.
7. **GitHub home:** `https://github.com/MagneticAnomaly/SourcePrep`
   (REPO_TOPOLOGY, DECIDED 2026-07-17). Not sourceprep/sourceprep.

## Source of truth for positioning

| Tier | Price | What it is |
|---|---|---|
| Open Source | $0, Apache 2.0 | The **full single-user product**: engine, daemon, CLI, MCP server, dashboard, VS Code extension, all prompts. Unlimited projects. Self-hosted. Community support (GitHub Issues/Discussions). |
| Pro | **$29 one-time** (name-your-price, $29 floor) | Signed/notarized DMG/MSI, auto-update; 12 months of updates included, app works forever; optional ~$15/yr continued updates; email support (5 business days). Identity-bound convenience (signing + notarization), zero capability differences. **Coming soon — no live checkout.** |
| Teams | $15/seat/mo or $144/seat/yr, 3-seat min | Hosted org-shared indexes, SSO, RBAC, audit logs, faster support. **Coming soon (undated) + waitlist CTA.** |
| Enterprise | $50/seat/mo annual, 10-seat min; setup engagement available | Teams + air-gapped deployment + named contact/office hours. **Coming soon / contact.** |

Hard rules:

- The old Free tier (3 projects) is **retired**. No project-cap language.
- **Never imply the OSS is feature-limited.** Paid = installer polish, hosted
  infrastructure, support — never capabilities or prompts.
- **No live checkout/purchase links in any state** (Decision 5). The
  existing Lemon Squeezy URLs must not be user-reachable; leave `pricing.ts`
  mechanics in place but unused, with a code comment explaining why.
- **No dated promises.** "Q3 2026" is dead (DECISION_MEMO D11 re-baseline);
  Teams/Enterprise are undated "coming soon".
- Privacy claim preserved: indexing is local, code never leaves the machine;
  the future hosted backend syncs embeddings + graph metadata only.
- Funding statement reframed: "Pro and Teams fund development — not your data."
- Contribution mentions (if any) reference **DCO sign-off, never a CLA**.
- Voice: plain language / outcome first; jargon is supporting detail. Trim
  redundant copy while editing.
- Brand: "SourcePrep" in copy; `prep` only as CLI/tool names. Entity:
  **Magnetic Anomaly LLC**.
- Hero (`packages/ui` yale variant) untouched; **no `packages/ui` edits**.

## Worktree / branch setup — DONE

- Worktree `.claude/worktrees/oss-marketing-copy`, branch
  `marketing/oss-launch-copy` off local `main` (`8c24245c`). Deps installed
  (Node 20.20.1). Dev server: port **3100**. Baseline screenshot captured
  (`.playwright-mcp/baseline-home-3100.png`).

## Page-by-page changes

All paths relative to `websites/apps/marketing/`. Line anchors from the
2026-07-17 surveys; re-verify at edit time.

### `/pricing` — `src/app/pricing/page.tsx`, `src/lib/pricing.ts`, `src/app/pricing/layout.tsx`
- Four-column grid per the tier table. Pro card: $29 one-time, name-your-price
  floor noted, "12 months of updates included — the app is yours forever",
  self-build-free line, CTA "Coming soon — get notified" (mailto) in BOTH
  flag states. Teams/Enterprise: undated coming-soon + waitlist/contact.
- OSS card CTA: beta-ON existing Request-Beta mailto; beta-OFF "View on
  GitHub" → `GITHUB_REPO_URL`.
- Remove: 3-project cap, license-management framing, PPP band display for
  Pro (name-your-price supersedes regional discounts), `$79`/`$70`/`$7/mo`
  anywhere, "macOS, Windows & Linux" trust-strip claim (see truthfulness).
- `pricing.ts`: leave PPP/LS mechanics compiled but unreferenced by the page;
  comment: checkout deliberately unwired — license crypto void (Phase 146)
  and LS products unconfigured; do not re-link without fixing both.
- `layout.tsx:5` metadata → "SourcePrep is free and open source (Apache 2.0).
  Pro adds signed installers and auto-update — $29 one-time, coming soon."

### `/faq` — `src/app/faq/page.tsx`
- `:334-342` "Why pay for this?" → open source, Apache 2.0, full product; Pro
  is a $29 one-time convenience (signed installer, auto-update, email
  support); Teams is hosted infrastructure; "that funds development — not
  your data."
- `:275` license-activation call → Pro-installer-only; OSS makes no license
  calls.
- `:20` → "works in the open-source version — every capability ships open
  source."
- Truthfulness (same file): `:297` and `:338` "15+ languages" → name the
  actual set (Python, TypeScript/TSX, JavaScript, Go, Rust, Java, C, C++);
  `:44-65` token-budget answer → scope the ~1,500-token figure explicitly to
  per-query search context and drop "under 1%" (client-aware ambient budgets
  reach ~12.5K tokens for Claude Code).

### `/security` — `src/app/security/page.tsx`
- `:138-147` "Offline Verification" → Pro-installer-only; OSS has no license
  infrastructure. `:116-117` outbound table: `/activate-license` marked Pro
  only. `:250-252` collected data: license key/machine ID Pro-only; OSS
  collects nothing. `:258-266`, `:281-282` payments/retention scoped to paid
  tiers.

### `/about` — `src/app/about/page.tsx`
- `:104-108` "Own your tools" → Apache 2.0 inversion: you already own it;
  Pro/Teams fund development, never unlock features.

### `/compare/*`
- `prep-vs-greptile:108` → open source (Apache 2.0) + optional $29 Pro; `:97`
  sharpen open-source vs proprietary-dashboard contrast. Beta CTA rows follow
  the flag treatment.

### `/download` — `src/app/download/page.tsx` + `src/app/download/layout.tsx`
- `:84` badge → "Open source — Apache 2.0. No account, no license required."
- Install paths: OSS (pip/pipx, brew, build from source, GitHub Releases via
  `GITHUB_REPO_URL` constant) vs Pro signed DMG/MSI ("coming soon").
- Truthfulness: remove/soften `:83` "Also on the Microsoft Store" (not live);
  `layout.tsx:5` meta description drops Linux until a build exists; gate the
  live .dmg/.msi buttons on the same beta flag for coherence.

### `/support` — `src/app/support/page.tsx`
- `:63`, `:76` → Pillar 3 matrix (Community GitHub best-effort / Pro email
  5 bd / Teams private channel 2 bd / Enterprise named contact + office
  hours); "license activation" scoped to Pro.

### `/terms` — `src/app/terms/page.tsx` (DRAFT, flagged for legal)
- Banner: draft pending legal review (Phase 144), not yet in effect.
- `:72` entity → Magnetic Anomaly LLC.
- `:77-108` → two-part: OSS governed by Apache 2.0 (not these terms);
  commercial terms govern paid products only (keys per purchaser,
  non-redistributable; the source itself is Apache 2.0).
- `:150-160` SLA table → Pillar 3 matrix.

### `/changelog`, home, sitewide metadata — light touch + truthfulness
- `changelog:15-17`: planned entry mentions open-source launch; factual.
- Home `page.tsx:35-42` sr-only SEO block: add open-source; fix "Kimi 2.6" →
  model-family naming (per the FAQ's own maintenance rule).
- `layout.tsx:24` JSON-LD `operatingSystem` → "macOS, Windows" (drop Linux).
- Home `page.tsx:52,221` "3–20× more signal per token" → re-anchor to
  "up to 20× structural compression" (Phase 73 audit: range is design-based,
  untested) — **flag in handoff for Eric's per-page review**.
- `claude-code/page.tsx:118-120` auto-approve claim → "generates the skills
  file and documents the one-line auto-approve config".
- `integrations/page.tsx:164` + `claude-code/page.tsx:195` Codex bullet →
  "first-class AGENTS.md consumer"; drop the mcpServers-config claim.
- **Hero untouched.**

### GitHub links
- `src/lib/links.ts` (new): `GITHUB_REPO_URL = "https://github.com/MagneticAnomaly/SourcePrep"`.

## IS_BETA_MODE treatment

- Flags stay (`page.tsx:10`, `pricing/page.tsx:29`, compare pages). No new
  plumbing.
- **Beta ON:** Request-Beta mailtos atop open-core copy.
- **Beta OFF (launch):** OSS CTAs go live (GitHub, install docs); Pro stays
  "coming soon — get notified"; Teams waitlist; Enterprise contact. No
  checkout links in either state.
- Both states reviewed page-by-page.

## Verification

1. `npm run lint`, `npm run typecheck`, production `npm run build`
   (marketing workspace, inside the worktree).
2. Dev server on :3100; Playwright walk of every changed page in both flag
   states; screenshots for review; hero pixel-identical to baseline.
3. Adversarial content verification (independent read-only agents): each
   changed page vs this spec's tier table + hard rules + voice/brand/entity
   rules.
4. Eric reviews live at :3100.

## Acceptance

- All listed pages coherent in both flag states; no page implies the OSS is
  limited.
- Zero hits in `websites/apps/marketing/src` for:
  `free tier|3 projects|three projects`, `\$79|\$70|\$7/mo`, `Q3 2026`,
  `SourcePrep Inc`, `Microsoft Store` (unless "coming to"), `15\+ languages`,
  `sourceprep/sourceprep`; Linux only in "coming"/roadmap phrasing.
- Prices shown: $29 Pro (one-time), $15/$144 Teams, $50 Enterprise; no
  reachable checkout link anywhere.
- Terms carries the legal banner + Magnetic Anomaly LLC.
- lint + typecheck + build pass; branch local-only.

## Pre-deploy checklist (Eric, before any push — not this branch's work)

1. Backlog A1: license decision formally closed (Apache 2.0 assumed here).
2. `feature_gate.py` FREE=3 removed so "unlimited projects" is true in the
   shipped OSS (backlog C3).
3. Lemon Squeezy: old $79/$7 products retired; $29 name-your-price product
   configured **and** license crypto fixed (Phase 146 N1) before re-enabling
   any checkout.
4. Terms reviewed by attorney (Phase 144); remove draft banner.
5. `MagneticAnomaly/SourcePrep` repo actually public; GitHub links resolve.
6. Trademark federal search (B1) cleared or accepted risk.

## Out of scope

- Home hero; any `packages/ui` edit; `LICENSE`/`pyproject` flips; LS
  configuration; docs site (follow-up grep only); Phase 143 deliverables;
  any `git push`.
