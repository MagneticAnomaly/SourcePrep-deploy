# Phase 144 — Legal Pre-Launch

> **The bet:** Before SourcePrep ships as Apache 2.0, the legal
> foundation must be sound. Trademark filed, IP chain clean, corporate
> structure acquisition-ready, contributor terms in place, and every
> open legal question answered with either a documented DIY decision
> or a written attorney opinion. This phase exists so that nothing
> about the public launch creates a legal surprise later.

## Why this phase exists

Apache 2.0 publication starts several clocks at once:

- **Patent priority** — once a method is published, US filings are
  limited to 12 months; most international jurisdictions are
  file-before-disclose (publication = forfeit)
- **Trademark exposure** — once "SourcePrep" is public at scale,
  others can file defensively or in bad faith; without a registered
  mark, defending is expensive
- **IP chain** — contributions from outside Eric/Magnetic Anomaly LLC
  start landing in the repo on day one of the public mirror;
  without a CLA, every contributor's IP ownership becomes a future
  acquisition-due-diligence problem
- **Customer terms** — the moment someone pays for a Pro license,
  there must be a Terms of Service and Refund Policy they agreed to
- **Liability** — the moment someone *uses* the OSS, there must be a
  License + Acceptable Use posture protecting Magnetic Anomaly LLC
- **Acquirer due diligence** — the things acquirers check first:
  trademark registration, IP chain, license hygiene, LLC operating
  agreement, customer terms. Any gap costs the deal or the price.

This phase exists so that **none of those clocks start in a state
that costs us later.**

## Scope

In:

- **Trademark** — USPTO search, application, defensive variants
- **Patent strategy** — novelty assessment of candidate methods,
  decision between provisional filing and defensive publication
- **Corporate structure review** — Magnetic Anomaly LLC operating
  agreement, IP assignment from Eric to LLC, entity-type decision
  (LLC vs C-Corp for acquisition prep)
- **Contributor License Agreement** — Apache ICLA template + CLA
  Assistant GitHub Action integration
- **License hygiene** — Apache 2.0 NOTICE file, dependency license
  audit, gstack attribution review, `LICENSE-AUDIT.md` private record
- **Public policies** — CONTRIBUTING, SECURITY, CODE_OF_CONDUCT,
  CHARTER (anti-rug-pull commitment)
- **Customer-facing terms** — ToS for sourceprep.io, Privacy Policy,
  Acceptable Use Policy, Refund Policy, EULA for Pro Tauri app,
  Subscription Terms
- **Security disclosure infrastructure** — `security@sourceprep.io`,
  GPG key, DMCA agent registration
- **Tax + compliance** — confirm Lemon Squeezy Merchant-of-Record
  coverage; identify any SourcePrep-specific gaps (e.g., EU/CA data
  subject rights)
- **Insurance** — E&O / Cyber liability review for the LLC

Out:

- Building any product features
- Marketing or launch activities (Phase 142 Parts D–H)
- Repo restructure (Phase 143 + Phase 142 Part B)
- SOC 2 certification (deferred to a later phase; only needed if
  Enterprise customers explicitly require it pre-purchase)

## Status

**Post-reframe (2026-06-15) checklist** — the original Parts A–K
plan is preserved in `IMPLEMENTATION_PLAN.md` as fallback, but the
actual remaining work after the reframe is now a flat DIY list per
`RESEARCH.md` "Open actions for Eric":

- [x] Phase scaffolded
- [x] Zero-users reframe applied to RESEARCH.md (2026-06-15)
- [x] IP-chain facts captured + template/checklist for IP Assignment
      Agreement (3.2, 2026-06-16)
- [x] License hygiene done (5.1 GPL deps replaced 2026-06-10, 5.2
      gstack audit clean 2026-06-08)
- [x] SECURITY.md drafted (7.1, 2026-06-10)
- [ ] USPTO TESS search (1.1 final step) — ~30 min
- [ ] USPTO TEAS Plus trademark filing, 2 classes (1.2, 1.3) — ~$500
- [ ] Run `scancode-toolkit` on repo (5.3) — DIY
- [ ] Compile NOTICE file (5.4) — DIY
- [ ] Draft CHARTER.md (10.1) — DIY using spec in RESEARCH.md
- [ ] Check in ICLA.md + CCLA.md (4.1, 4.2) — Apache templates
- [ ] Configure CLA Assistant on public mirror (4.3) — ~30 min
- [ ] Register DMCA agent (7.2) — $6, 30 min
- [ ] Create `security@sourceprep.io` alias (7.1 remaining)
- [ ] Execute IP Assignment Agreement (3.2) — template via future AI
      session; Eric signs both sides; store in LLC records
- [ ] Draft Phase 1 ToS, Privacy Policy, EULA (6.1, 6.2, 6.3) — DIY
      from templates; attorney review at first-paying-customer trigger
- [ ] Apply refund-policy text to Lemon Squeezy products (6.4)
- [ ] Finish business bank account (3.5) — in flight
- [ ] Phase 144 retro + sign-off for Phase 142 Part C

## Files in this phase

| File | Purpose |
|---|---|
| `README.md` | This file — phase summary, status, scope |
| `IMPLEMENTATION_PLAN.md` | Ordered work (Parts A–K) with deliverables and acceptance criteria |
| `RESEARCH.md` | **The full set of open legal questions, organized by topic, with DIY-vs-attorney designation and deliverable per question. This is the doc to read first if you want to understand what we don't yet know.** |
| (later) `ATTORNEY_BRIEF.md` | Consolidated brief for the attorney consult (private) |
| (later) `LICENSE-AUDIT.md` | Private record of dependency license audit + date |
| (later) `CHARTER.md` | Public anti-rug-pull commitment (eventually ships in public mirror root) |

## Cost + time estimate

**Reframe applied 2026-06-15:** at zero users / zero revenue / solo
bootstrap, the legal risk profile is far smaller than what the
original cost table assumed. Industry-standard templates + DIY tools
cover the vast majority of items; attorney engagement is deferred to
trigger events (first paying customer / first acquirer LOI / first
EU prospect). See `RESEARCH.md` for the full decision record.

| Item | Est cost | Est calendar time |
|---|---|---|
| USPTO trademark filing (2 classes, TEAS Plus, DIY) | ~$500 fees | 8–12 months to registration (use ™ immediately on filing) |
| DMCA agent registration | $6 USPTO fee + 30 min | Same day |
| Accountant year-end call (sales tax confirmation) | $100–200 | 30 min |
| ToS + Privacy Policy + EULA + IP Assignment (template-based, DIY) | $0 | ~1 week of Eric drafting |
| CHARTER.md, CLA configuration, NOTICE compile, scancode run | $0 | 1–2 days |
| E&O / Cyber insurance quotes (deferred to Phase 2 trigger) | $0 at this phase | — |
| **Total Phase 144 budget (zero-users reframe)** | **~$256** | **~1 week active work** |
| **Attorney review at trigger** (first paying customer, first acquirer LOI) | $500–1,500 per engagement | At trigger only |

**Why this is OK at zero-users stage:**
- Templates from Cooley GO, Y Combinator, GitHub legal, EU
  Commission SCC are industry-standard and acquirer-acceptable
- No paying customers means no contract-dispute exposure yet
- No acquirer in pipeline means no diligence pressure yet
- Attorney review is cheaper and faster when scoped to one specific
  trigger event rather than "review everything just in case"
- The risk of *not* doing the DIY drafting is much higher than the
  risk of using industry-standard templates without legal review

## Success criteria

Phase 144 is **complete** when:

1. Every open question in `RESEARCH.md` has either a Decided, Answered,
   or Deferred-to-trigger status — no "Open" left
2. USPTO trademark application is filed (TEAS Plus, DIY, 2 classes;
   registration takes months but filing is what gates ™ usage)
3. Patent decisions are recorded: skip + defensive publication via
   Phase 142 Part G blog posts (decided 2026-06-15)
4. IP Assignment Agreement (Eric → Magnetic Anomaly LLC) executed and
   stored in LLC corporate records — covers Jan–Apr 2026 pre-LLC work
5. Apache 2.0 NOTICE file is complete; dependency license audit
   passes (5.1 already resolved 2026-06-10); CLA Assistant configured;
   scancode-toolkit run clean
6. CONTRIBUTING.md, SECURITY.md, CODE_OF_CONDUCT.md, CHARTER.md,
   ICLA.md, CCLA.md drafted (templates customized)
7. Phase 1 ToS, Privacy Policy, EULA, Refund Policy drafted from
   templates and published — attorney review queued at first-paying-
   customer trigger
8. `security@sourceprep.io` alias live; DMCA agent registered with
   USPTO
9. Insurance decision deferred to Phase 2 trigger with quotes-ready
   plan recorded
10. Phase 144 hands off cleanly to Phase 142 Part C (public mirror
    can ship without legal surprises at this stage's risk profile)

## Relationship to existing docs

| Existing doc | Phase 144 relationship |
|---|---|
| `docs/Phase142_OSS-First/OPEN_CORE_SPLIT.md` | Identifies Phase 144 as a prerequisite. Lists 8 open questions; some are answered in this phase. |
| `docs/Phase142_OSS-First/STRATEGY.md` §"Attribution to gstack" | Phase 144 Part H executes the attribution audit. |
| `docs/Phase142_OSS-First/SCRUTINY.md` §8 (dep license audit), §9 (trademark check), §10 (anti-rug-pull), §11 (existing customers), §16 (third-party license risk) | Phase 144 systematically addresses each. |
| `docs/Phase10_Business_And_Competitive_Research/FINANCE_AND_LEGAL_STRUCTURE.md` | Historical doc on legal structure. Phase 144 supersedes specific recommendations that conflict (e.g., references to Stripe instead of Lemon Squeezy). |
| `docs/DISTRIBUTION_AND_REVENUE_PLAN.md` | Already covers Lemon Squeezy mechanics + license key design. Phase 144 supplements with the legal terms that wrap them. |

## Dependencies

- **Blocks:** Phase 142 Part C (public README + CONTRIBUTING +
  SECURITY) and Part F (Show HN launch) — cannot ship publicly until
  legal is sound.
- **Blocked by:** None. Can start immediately.
- **Adjacent:** Phase 143 (docs cleanup) — runs in parallel.

## Operating principle

**No "we'll figure it out later" on legal items.** Every question
in `RESEARCH.md` gets either:

- A clearly-documented DIY answer with a citation/source, OR
- A written attorney opinion (even one paragraph in an email)

The goal is that 6 months from now, when a customer's lawyer or an
acquirer's diligence team asks "why did you do X," there is a
written rationale on file.
