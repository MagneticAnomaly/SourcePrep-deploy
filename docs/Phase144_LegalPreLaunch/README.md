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

- [x] Phase scaffolded
- [ ] DIY pre-attorney research complete (Part A)
- [ ] Consolidated attorney brief drafted (Part B)
- [ ] Attorney engagement complete (Part C)
- [ ] Trademark application filed (Part D)
- [ ] Patent decision made (Part E)
- [ ] Corporate structure review complete (Part F)
- [ ] Public policies drafted (Part G)
- [ ] License hygiene + dependency audit complete (Part H)
- [ ] Customer-facing terms drafted (Part I)
- [ ] Security disclosure infrastructure live (Part J)
- [ ] Insurance review complete (Part K)
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

| Item | Est cost | Est calendar time |
|---|---|---|
| USPTO trademark filing (2 classes, TEAS Standard) | ~$700 fees | 8–12 months to registration (use ™ immediately on filing) |
| Trademark attorney (consult + filing assistance) | $1,500–3,000 | 1–2 weeks |
| Patent attorney consult (1 hour, novelty assessment) | $400–800 | 1 hour |
| Provisional patent filing (if attorney recommends — IF any) | $1,500–3,000 each | 1 week |
| Corporate/IP attorney (LLC operating agreement review, IP assignment, CLA review) | $1,000–2,500 | 1–2 weeks |
| ToS + Privacy Policy + EULA drafting (template-based with attorney review) | $500–1,500 | 1 week |
| DMCA agent registration | $6 USPTO fee + 30 min | Same day |
| E&O / Cyber liability insurance quote | $0 (quote only at this phase) | 1 week |
| **Total Phase 144 budget** | **$5,000–11,000** | **3–4 weeks calendar** |

Note: most calendar time is *waiting on attorney/USPTO*, not active
work. Active work is ~1 week of Eric's time.

## Success criteria

Phase 144 is **complete** when:

1. Every open question in `RESEARCH.md` has either a documented DIY
   answer or a written attorney opinion
2. USPTO trademark application is filed (registration takes months;
   filing is what gates launch)
3. Patent decisions are recorded: skip / provisional / defensive
   publication, with rationale per candidate method
4. Magnetic Anomaly LLC operating agreement has been reviewed by an
   attorney; any required amendments are filed
5. Apache 2.0 NOTICE file is complete; dependency license audit
   passes (no GPL/AGPL/proprietary in the build); CLA Assistant
   integration tested
6. CONTRIBUTING.md, SECURITY.md, CODE_OF_CONDUCT.md, CHARTER.md
   drafted and reviewed
7. ToS, Privacy Policy, EULA, Subscription Terms, Refund Policy,
   Acceptable Use Policy drafted and attorney-reviewed
8. `security@sourceprep.io` is live with a GPG key; DMCA agent
   registered with USPTO
9. Insurance quotes obtained; decision recorded (purchase now /
   defer to Phase 2 / not needed)
10. Phase 144 hands off cleanly to Phase 142 Part C (public mirror
    can ship without legal surprises)

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
