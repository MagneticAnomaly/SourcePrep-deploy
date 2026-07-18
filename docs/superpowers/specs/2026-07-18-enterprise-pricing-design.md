# Enterprise Pricing Restructure — Design

**Date:** 2026-07-18
**Status:** Approved (pending spec review)
**Scope:** Marketing pricing page — per-seat prices, seat minimums, and a new tiered setup-fee structure. Single file change in primary scope; secondary sweep for stale number references elsewhere.

> **Shipped update (2026-07-18):** the Teams **annual** figure below shipped as
> **$97/seat/yr (10% off)**, not the `$86/seat/yr (20% off)` in the body of this
> design (a later revision reduced the annual discount from 20% to 10%; commit
> `0f1a66c2`). The `$9/seat/mo` monthly and all Enterprise numbers are as
> written. Treat the shipped value as authoritative where this doc says `$86`.

## Context

SourcePrep is a solo-developer product. The pricing page (`websites/apps/marketing/src/app/pricing/page.tsx`) currently lists four tiers: Open Source ($0), Pro ($29 one-time), Teams ($10/seat/mo, 3-seat min), and Enterprise ($30/seat/mo, annual, 10-seat min, "Setup assistance available").

The problem the Enterprise tier was trying to solve — recovering the cost of an on-site setup visit — was packed into the per-seat price. That conflates a **one-time** cost (the trip) with a **recurring** obligation (named contact + monthly office hours + air-gapped support). The result is a price that is simultaneously too high to be competitive on the headline number and too low to cover the ongoing support burden in year 2+, once any one-time setup fee is spent.

This design decouples setup from the per-seat price: setup becomes a separate, tiered professional-services line item, and the per-seat price (combined with a higher seat minimum) covers only the recurring support burden.

## Key insight

**The setup fee and the per-seat price serve different purposes and cannot substitute for each other.**

- **Setup fee** recovers a **one-time** cost (airfare + hotel + days of time). Earned once.
- **Per-seat × min-seats** covers the **ongoing** burden — named contact, monthly office hours, air-gapped support — for **every year** the account is active.

A larger setup fee does not fix a too-low per-seat price, because the ongoing support burden persists in year 2, 3, 4 when the setup fee is long spent. Therefore the per-seat × min-seat floor must independently clear the "worth the named-contact burden" threshold.

## Decisions

1. **On-site setup is an optional paid add-on**, not baked into every Enterprise deal. Rationale: a solo developer's scarcest resource is time, not margin-per-deal. Baking on-site into every deal caps throughput at ~1-2 deals/month and turns the product company into a traveling consultancy. Most Enterprise deployments can be done remote-first (deploy script + screen-share); on-site is only genuinely required for air-gapped / regulated environments that cannot be reached remotely.

2. **Setup is a separate, tiered fee** (professional-services line item), published on the page as a "from" anchor with complex cases quoted:
   - Remote setup — **included** (default for all Teams and Enterprise).
   - On-site kickoff — **from $3,500, travel included** (1-2 days on-site).
   - Air-gapped / complex deployment — **quoted separately** (multi-day, Enterprise only).

3. **Enterprise min account value ≈ $4-5k/yr.** This is the floor that makes an Enterprise deal worth the named-contact + monthly office-hours burden for a solo developer.

4. **Approach A: competitive per-seat, higher floor.** Enterprise drops to $24/seat/mo with a 15-seat minimum, annual billing only. Floor = 15 × $24 × 12 = **$4,320/yr**, clearing the $4-5k target.

5. **Teams drops to $9/seat/mo** (3-seat min unchanged). Annual recomputed to $86/seat/yr (20% off $108).

6. **Pro and Open Source unchanged.**

7. **Pricing ladder is intentionally poetic:** $0 → $9 → $24 → $29 (OSS, Teams, Enterprise, Pro). Recurring tiers ascend cleanly (9 → 24); the one-time Pro price ($29) sits at the top of the ladder as the brand anchor; OSS zeroes it out. A buyer can hold the whole ladder in their head.

## Final pricing structure

| Tier | Price | Min | Billing | What's included |
|---|---|---|---|---|
| Open Source | $0 forever | — | — | Full product, Apache 2.0, community support |
| Pro | $29 one-time | — | — | Signed installers, 12mo updates, ~$15/yr after, email support |
| Teams | $9/seat/mo | 3 seats | monthly or annual ($86/seat/yr, 20% off) | Shared index, SSO, RBAC+audit, priority support |
| Enterprise | $24/seat/mo | 15 seats | annual only | Everything in Teams + air-gapped + named contact + monthly office hours |

### Setup fees (separate from per-seat)

| Setup tier | Price | Applies to |
|---|---|---|
| Remote setup | Included | All Teams and Enterprise (default) |
| On-site kickoff | from $3,500 (travel included) | Optional Enterprise add-on |
| Air-gapped / complex deployment | Quoted separately | Enterprise only |

## What this achieves

- **Time protected:** every Enterprise deal clears $4,320/yr, above the $4-5k "worth the named-contact burden" bar. Sub-15-person companies route to Teams — the correct product for them.
- **On-site never loses money:** the trip is a separate, profitable line item, never packed into a small account.
- **Year-2 problem solved:** per-seat ($24) covers ongoing support independently; the setup fee is not relied on to fund recurring support.
- **Competitive headline:** $24/seat undercuts the prior $30 and most comparators, while the floor protects the solo developer's time.
- **Poetic ladder:** $0 → $9 → $24 → $29.

## Implementation scope

### Primary (single file)

`websites/apps/marketing/src/app/pricing/page.tsx`:

1. **Teams card:** price `$10` → `$9`. Annual line `$96/seat/yr (20% off)` → `$86/seat/yr (20% off)`. Min line `3-seat minimum` unchanged.
2. **Enterprise card:** price `$30` → `$24`. Min line `Annual billing, 10-seat minimum` → `Annual billing, 15-seat minimum`.
3. **Enterprise feature list:** replace the `Setup assistance available` bullet with a single bullet describing the tiered setup: `Setup: remote included · on-site from $3,500 · air-gapped quoted`.
4. No changes to Open Source or Pro cards.
5. No changes to the closed-beta banner, the "All prices in USD" note, the trust strip, or the mailto CTAs.

### Secondary (stale-number sweep)

Grep the marketing and docs apps for the old numbers (`$30`, `10-seat`, `$96/seat`, `$10/seat`) and update any non-pricing-page references that restate the prior pricing (e.g., FAQ, security page, terms, comparison tables). Leave unrelated uses of `$30` / `$10` untouched — match by surrounding pricing context, not by raw number.

### Out of scope

- The closed-beta banner copy and `IS_BETA_MODE` gating.
- The payments app and any billing backend — this is a marketing-page change; no payment integration is wired yet.
- Teams or Pro tier definitions beyond the price numbers above.
- Any change to the `mailto:` lead-capture CTAs.

## Verification

- `npm run build` (or `npm run dev`) in `websites/apps/marketing` renders the pricing page with the new numbers and no layout breakage from the longer setup-fee bullet.
- Visual check: the Enterprise card's setup bullet does not overflow the card at the default grid width; wrap behavior is acceptable.
- Grep sweep confirms no remaining stale references to `$30/seat`, `10-seat minimum`, `$96/seat`, or `$10/seat` in marketing/docs context.
- `npm run lint` and `npm run typecheck` for the marketing workspace pass.

## Risks / notes

- The 15-seat Enterprise minimum gates out 10-14 person companies. This is **intentional**: a 10-14 person shop is a Teams customer, not an Enterprise named-contact customer, and the floor exists to protect solo-developer support capacity.
- The "from $3,500" on-site anchor is a published marketing number; actual quotes may exceed it for distant/international/multi-day engagements. The "from" wording and "quoted separately" line for air-gapped cover this. If a real engagement comes in materially above $3,500, the page anchor may need revision — track this as a post-launch signal.
- $86/seat/yr is the exact 20%-off number for $9/mo ($108 → $86.40 rounded down). If a rounder annual number is later preferred, $89/seat/yr (~18% off) is the alternative; this spec uses $86 to preserve the clean "20% off" framing already on the page.