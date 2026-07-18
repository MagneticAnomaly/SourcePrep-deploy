# OSS Marketing Copy — Handoff for Eric's Review

**Date:** 2026-07-18 (work executed 2026-07-17 → 07-18)
**Branch:** `marketing/oss-launch-copy` (19 commits, `eaa99ae4` → `059568a7`)
**Worktree:** `.claude/worktrees/oss-marketing-copy` — 23 files, +384/−414 (net −30 lines)
**Nothing pushed.** Deploy/merge is entirely your call, later.

## How to review

- Dev server is running: **http://localhost:3100** (isolated; :3000/:5174 untouched).
  If it dies: `cd .claude/worktrees/oss-marketing-copy/websites/apps/marketing && nvm use 20 && npm run dev -- -p 3100`
- Screenshots of every page: `.playwright-mcp/verify-*.png` (plus `baseline-home-3100.png` = before).
- **Launch-state preview:** flip `IS_BETA_MODE` to `false` in **6 files** (`rg -n 'IS_BETA_MODE = true' websites/apps/marketing/src` → home `page.tsx`, `pricing`, `download`, `changelog`, both `compare/*`). All 6 currently `true` (committed state). Consider consolidating the flag into `src/lib/links.ts` so launch day is a one-line flip.

## What changed (all pages verified in both flag states)

| Page | Now says |
|---|---|
| `/pricing` | 4-card open-core grid: OSS $0 full product / Pro $29 one-time coming-soon / Teams $15/seat + waitlist / Enterprise $50/seat. No checkout links anywhere. PPP/LS code kept compiled but unreachable, marked NOT LIVE. |
| `/faq` | Open-core answers ($29 coming soon, 12-mo updates), license calls scoped to Pro installer, real 8-language list, honest token-budget answer. |
| `/security` | All license/activation/payment claims scoped to Pro/paid; OSS collects nothing (with bug-report carve-out); every privacy absolute hedged with the BYOK opt-in qualifier; vuln acknowledgment aligned to SECURITY.md (5 business days). |
| `/download` | OSS install paths (pip/pipx, brew, source, GitHub Releases) vs Pro signed installers coming-soon; MS Store and Linux claims removed; Quick Start matches real CLI behavior (`prep add` then `prep build`). |
| `/support` | Community/Pro/Teams/Enterprise matrix with response *targets*; paid-plan CTA framed as ask/notify, not a live channel. |
| `/terms` | DRAFT banner (pending legal review); Magnetic Anomaly LLC; Apache 2.0 governs the code, commercial terms only paid tiers; reverse-engineering ban deleted + Apache savings clause; liability cap extended to services and names the LLC. |
| `/about`, `/compare/*` | Apache-2.0 ownership framing; greptile claims aligned to the page's own evidence; compare pages gained the beta/launch CTA switch. |
| Home, `/changelog`, sitewide | Hero pixel-identical to baseline. SEO block open-source + model-family naming; compression claims hedged "up to 20×"; geo-cookie middleware deleted; stale SourcePrep-MCP URLs → `MagneticAnomaly/SourcePrep` (single constant in `src/lib/links.ts`); footer LLC casing; JSON-LD macOS/Windows. |

## Verification record

- `lint` / `typecheck` / production `build` all green (build proves the middleware deletion safe; 27 routes static).
- Acceptance greps: zero old-model residue ($79/$70/$7-mo, free tier, 3 projects, Q3 2026, SourcePrep Inc, SourcePrep-MCP, 15+ languages, Microsoft Store, unhedged 20×).
- Dual-state rendered-HTML sweep across all 11 pages; both states coherent; tree restored clean.
- Adversarial 8-verifier pass (per-page skeptics vs the spec): 5 confirmed violations found and fixed (privacy absolutes, tier-fact errors); 2 findings judged false-positive (spec-sanctioned "(Linux planned)" and compiled-but-unreachable pricing.ts).
- Every implementation task passed two-stage review (spec compliance, then code quality) with fix loops.

## Needs YOUR sign-off (before or at deploy)

1. **Competitor copy** — greptile page wording (softened to matrix-aligned claims; final call yours).
2. **"Up to 20×" reframe** — home/FAQ/compare now hedged; **`packages/ui` still renders unhedged "3–20×"** (FeatureBlocks card, TechStackMatrix, hero variants incl. yale's "3-20+ (Smart)" chip and "MAC / WIN / LINUX" line). Off-limits this branch per your hero/ui rule — needs a separate packages/ui pass. FeatureBlocks also has typos worth fixing there ("can be challenge", "stategic", "infomed", "structually").
3. **New commitments the copy now makes:** Pro installers "notarized"; "checksums published for every release"; Teams/Enterprise support response targets. All hedged as targets, but they're promises — confirm intent.
4. **x.com/Prep_io** social handle — stale brand? (rule says "prep" = CLI only).
5. **Security §08 / terms** will need a Teams carve-out when hosted sync ships (Phase 2).
6. **Sequencing assumption:** beta-ON copy speaks of the product as open source in present tense — the repo must be public (and PyPI/brew live) before the site deploys.

## Attorney flags (terms draft, Phase 144)

Refund policy deferred to time-of-purchase; no termination/governing-law/acceptable-use sections (pre-existing gap); trademark clause is layman-drafted; agreement trigger narrowed to purchase/services; "active license holders" undefined vs Pro perpetual month-13; "(Phase 144)" internal jargon on a public page; "Privacy Policy" links point at /security#data-collection (no standalone privacy doc; sourceprep.io/privacy redirect must exist).

## Pre-deploy checklist (from the spec)

1. License decision (A1) formally closed — copy says Apache 2.0 per LICENSING_RECOMMENDATION.
2. `feature_gate.py` FREE=3 removed so "unlimited projects" is true in the shipped OSS.
3. Lemon Squeezy: old products retired; $29 name-your-price configured **and** license crypto fixed (Phase 146 N1) before wiring any checkout.
4. Terms attorney-reviewed; draft banner removed.
5. `MagneticAnomaly/SourcePrep` repo public; GitHub links resolve.
6. Trademark search (B1) cleared or risk accepted.
7. Netlify deploy gating in place (deploys only on explicit flag — per standing rule).

## Spec / plan / this doc

- Spec: `docs/superpowers/specs/2026-07-17-oss-marketing-copy-design.md`
- Plan: `docs/superpowers/plans/2026-07-17-oss-marketing-copy.md`
- Committed on the docs branch (`docs/feedback-concept-pipeline-audit-2026-07-11`), local only.
