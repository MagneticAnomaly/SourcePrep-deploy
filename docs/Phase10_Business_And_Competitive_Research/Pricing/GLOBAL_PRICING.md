# Global Pricing Strategy — Purchasing Power Parity (PPP)

> **Status:** AUTHORITATIVE — This document defines Prep's international pricing strategy.
> Complements [`DISTRIBUTION_AND_REVENUE_PLAN.md`](../../DISTRIBUTION_AND_REVENUE_PLAN.md) §7.
>
> **Last reviewed:** 2026-02-21
> **Entity:** Magnetic Anomaly LLC

---

## Table of Contents

1. [Why Global Pricing Matters](#1-why-global-pricing-matters)
2. [Lemon Squeezy International Capabilities](#2-lemon-squeezy-international-capabilities)
3. [PPP Pricing Bands](#3-ppp-pricing-bands)
4. [Currency Display Strategy](#4-currency-display-strategy)
5. [Implementation Architecture](#5-implementation-architecture)
6. [Checkout Flow](#6-checkout-flow)
7. [Anti-Abuse Measures](#7-anti-abuse-measures)
8. [Revenue Impact Modeling](#8-revenue-impact-modeling)
9. [Implementation Options Comparison](#9-implementation-options-comparison)
10. [TODO — Implementation Checklist](#10-todo--implementation-checklist)
11. [Open Questions](#11-open-questions)

---

## 1. Why Global Pricing Matters

Prep is a desktop developer tool. Developers are everywhere. A $79 perpetual license
is affordable in the US ($79 ≈ 0.1% of median US dev salary) but represents a much
larger fraction of income in India ($79 ≈ 1.5% of median Indian dev salary), Brazil,
Eastern Europe, Southeast Asia, and Africa.

**The opportunity:**
- ~70% of the world's developers are outside the US/EU/UK tier-1 markets
- Developer tools that offer PPP pricing (JetBrains, 1Password, Tailwind UI) see
  significantly higher international adoption
- Prep's COGS is effectively zero (local-first, BYOK) — marginal cost of a
  discounted license is near-zero, so any sale at any price is pure margin

**The risk of NOT doing it:**
- Piracy / license sharing in price-sensitive markets
- Loss of adoption and community-building in fast-growing dev markets (India, Brazil,
  Nigeria, Indonesia, Vietnam, Philippines)
- Competitors who DO offer PPP pricing capture these markets

**Precedent:**
- **JetBrains**: Region-specific pricing (e.g., IntelliJ IDEA Personal: $149 US, ~$89 India)
- **Tailwind UI**: PPP banner with up to 50% off for qualifying countries
- **1Password**: Regional pricing via Paddle
- **Notion**: 50% education discount globally, PPP in emerging markets
- **Linear**: PPP pricing via Stripe geo-IP

---

## 2. Lemon Squeezy International Capabilities

### What LS Handles Automatically
- **Tax compliance (MoR):** VAT, GST, sales tax collected and remitted globally
- **130+ display currencies:** Prices shown in local currency at checkout
- **Real-time exchange rates:** Mid-market rates, no additional conversion fee
- **Localized checkout:** 30+ languages supported via `locale` parameter
- **Payment methods:** Credit card + PayPal globally. No local payment methods (no
  Boleto, UPI, iDEAL, etc. — this is a Lemon Squeezy limitation)

### What LS Does NOT Handle
- **PPP / regional pricing:** LS has no built-in "show different prices per country" feature
- **Geo-IP detection:** LS does not tell you where a visitor is from
- **Price localization on YOUR website:** Your pricing page shows whatever you build

### PPP Implementation Options in LS

| Mechanism | How It Works | Pros | Cons |
|:----------|:-------------|:-----|:-----|
| **Discount codes** | Pre-create % discount codes per PPP band (e.g., `PPP-BAND2-30`). Apply at checkout. | Simple, auditable, works with LS discount API | User sees "original price" struck through — feels like charity |
| **Custom price checkout** | Use LS Checkout API `custom_price` param to create checkout links with adjusted prices per region | Clean — user only sees their price | Need server-side or edge function to generate checkout URLs |
| **ParityDeals integration** | Third-party banner service. Detects geo-IP, shows discount code banner | Turnkey, no code, free tier (1 product/5K hits) | External dependency, banner UX feels cheap, limited customization |
| **Variants per region** | Create LS product variants for each PPP band | Native LS feature, clean checkout | Variant sprawl (5 tiers × 4 bands = 20 variants), management overhead |

**Recommendation: Custom price checkout (Option B) for the pricing page, with discount
codes (Option A) as fallback for direct links / referrals.**

---

## 3. PPP Pricing Bands

Based on World Bank PPP data and developer salary medians. Bands are intentionally
simple — 4 tiers cover 95%+ of developer traffic.

### Band Definitions

| Band | Name | Discount | Monthly | Perpetual | Team/seat/mo | Representative Countries |
|:-----|:-----|:---------|:--------|:----------|:-------------|:------------------------|
| **0** | Full Price | 0% | $7/mo | $79 | $15 | US, Canada, UK, Germany, France, Netherlands, Switzerland, Australia, Japan, Singapore, Israel, Nordics, Ireland |
| **1** | Moderate PPP | 20% | $5.60/mo | $63 | $12 | Spain, Italy, Portugal, South Korea, Taiwan, Czech Republic, Poland, Greece, Chile, UAE, Saudi Arabia, New Zealand |
| **2** | High PPP | 40% | $4.20/mo | $47 | $9 | Brazil, Mexico, Argentina, Turkey, South Africa, Romania, Bulgaria, Thailand, Malaysia, Colombia, Peru, China |
| **3** | Maximum PPP | 60% | $2.80/mo | $32 | $6 | India, Indonesia, Vietnam, Philippines, Pakistan, Bangladesh, Nigeria, Kenya, Egypt, Ukraine, Nepal, Sri Lanka, Ethiopia |

### Rounded Prices for Display

| Band | Monthly | Perpetual | Team |
|:-----|:--------|:----------|:-----|
| **0** | $7/mo | $79 | $15/seat/mo |
| **1** | $5/mo | $59 | $12/seat/mo |
| **2** | $4/mo | $45 | $9/seat/mo |
| **3** | $3/mo | $29 | $6/seat/mo |

*Note: Rounded to psychologically clean price points. Actual LS checkout will charge
the rounded amount. Free and Enterprise tiers are not affected by PPP.*

### Country → Band Mapping

```typescript
// Canonical mapping — used by website + checkout generation
export const COUNTRY_PPP_BAND: Record<string, number> = {
  // ── Band 0: Full Price ──────────────────────────
  US: 0, CA: 0, GB: 0, DE: 0, FR: 0, NL: 0, CH: 0, AT: 0,
  AU: 0, NZ: 0, JP: 0, SG: 0, IL: 0, IE: 0, LU: 0, BE: 0,
  SE: 0, NO: 0, DK: 0, FI: 0, IS: 0, HK: 0,

  // ── Band 1: Moderate PPP (20% off) ─────────────
  ES: 1, IT: 1, PT: 1, KR: 1, TW: 1, CZ: 1, PL: 1, GR: 1,
  CL: 1, AE: 1, SA: 1, QA: 1, KW: 1, HR: 1, SK: 1, SI: 1,
  EE: 1, LT: 1, LV: 1, HU: 1, MT: 1, CY: 1, UY: 1, CR: 1,
  PA: 1, MY: 1,

  // ── Band 2: High PPP (40% off) ─────────────────
  BR: 2, MX: 2, AR: 2, TR: 2, ZA: 2, RO: 2, BG: 2, TH: 2,
  CO: 2, PE: 2, CN: 2, EC: 2, DO: 2, GT: 2, RS: 2, BA: 2,
  MK: 2, AL: 2, GE: 2, JM: 2, TT: 2, MU: 2,

  // ── Band 3: Maximum PPP (60% off) ──────────────
  IN: 3, ID: 3, VN: 3, PH: 3, PK: 3, BD: 3, NG: 3, KE: 3,
  EG: 3, UA: 3, NP: 3, LK: 3, ET: 3, GH: 3, TZ: 3, UG: 3,
  RW: 3, SN: 3, CM: 3, MM: 3, KH: 3, LA: 3, MN: 3, UZ: 3,
  KG: 3, TJ: 3, BO: 3, PY: 3, HN: 3, NI: 3,
};

// Default for unlisted countries
export const DEFAULT_PPP_BAND = 0;
```

---

## 4. Currency Display Strategy

### On the Website (runprep.io/pricing)

**Display in USD for all visitors.** Rationale:
- Developer tools universally price in USD (JetBrains, GitHub, Cursor, Windsurf)
- Avoids currency display bugs and rounding confusion
- Lemon Squeezy checkout will show the local currency equivalent automatically
- PPP discount already adjusts for purchasing power — double-adjusting with local
  currency display adds complexity with marginal benefit

**What changes per region:**
- The **dollar amount** shown changes silently based on PPP band
- **No banners, no strikethroughs, no "adjusted for your region" badges.** We follow the Enterprise convention (JetBrains, Adobe, Microsoft) rather than the Indie convention. The price they see is simply "the price".
- The checkout button links to a LS checkout with the adjusted price

### At Checkout (Lemon Squeezy)

- LS checkout displays price in the customer's local currency (auto-detected)
- LS converts the USD custom_price to local currency at real-time mid-market rates
- Customer pays in their currency; we receive USD payout

### In the App (Prep Desktop)

- No pricing displayed in-app (upgrade prompts link to runprep.io/pricing)
- License tier is the same regardless of purchase price

---

## 5. Implementation Architecture

### Option A: ParityDeals (Fastest, Least Control)

```
Visitor → runprep.io/pricing
  │
  ├─ ParityDeals <script> tag detects country via IP
  ├─ Shows banner: "It looks like you're in India. Get 60% off with code PPP60"
  ├─ User clicks "Buy" → LS checkout with discount code auto-applied
  │
  └─ Done. No server-side code needed.
```

**Cost:** Free for 1 product / 5K hits/mo. $9/mo for 5 products / 50K hits/mo.
**Cons:** Banner feels promotional / cheap. Limited UI customization. Discount code
visible → can be shared. Third-party dependency.

### Option B: Edge-Function Geo-Pricing (Recommended)

```
Visitor → runprep.io/pricing
  │
  ├─ Next.js middleware OR Netlify Edge Function reads country from:
  │   - Netlify: `context.geo.country` header (free, automatic)
  │   - Cloudflare: `cf-ipcountry` header (free, automatic)
  │   - Vercel: `x-vercel-ip-country` header (free, automatic)
  │
  ├─ Country → PPP band lookup (static map, no API call)
  │
  ├─ Pricing page renders with adjusted prices
  │   - "$29 one-time" instead of "$79 one-time"
  │   - Small note: "Price adjusted for your region"
  │
  ├─ "Buy" button links to LS checkout with custom_price
  │   - Option 1: Pre-generated checkout URL with custom_price via LS API (server-side)
  │   - Option 2: Discount code appended to standard checkout URL (?discount=PPP60)
  │
  └─ Customer sees local currency at checkout. Pays. Gets license.
```

**Hosting note:** Prep marketing site is on Netlify. Netlify Edge Functions provide
`Deno.env.get("NETLIFY_COUNTRY")` or the `x-country` header automatically. No extra
service needed.

### Edge Function (Netlify)

```typescript
// netlify/edge-functions/geo-pricing.ts
import type { Context } from "@netlify/edge-functions";

export default async (request: Request, context: Context) => {
  const country = context.geo?.country?.code || "US";
  const response = await context.next();

  // Inject country as a cookie or header for the React page to read
  response.headers.set("x-visitor-country", country);
  return response;
};

export const config = { path: "/pricing" };
```

### React Page (Next.js)

```tsx
// In pricing/page.tsx — read country from cookie/header, look up band, render prices
const band = COUNTRY_PPP_BAND[country] ?? DEFAULT_PPP_BAND;
const prices = PPP_PRICES[band]; // { monthly: 7, perpetual: 79, team: 15 } etc.
```

### Checkout URL Generation

Two options for linking to LS checkout with the adjusted price:

**Option B1: Discount codes (simpler)**
- Pre-create 3 discount codes in LS dashboard: `PPP20`, `PPP40`, `PPP60`
- Checkout URL: `https://[store].lemonsqueezy.com/buy/[variant]?discount=PPP40`
- Pros: No server-side checkout API calls. Works with static site.
- Cons: Discount codes can leak. User sees "original price" crossed out.

**Option B2: Dynamic checkout via LS API (cleaner)**
- Server-side function calls `POST /v1/checkouts` with `custom_price` in cents
- Returns a unique checkout URL with the adjusted price baked in
- Pros: User only sees their price. No leakable discount codes.
- Cons: Requires server-side function (Netlify Function or API route). Latency on
  button click (~200ms to generate checkout URL).

**Recommendation: Start with B1 (discount codes). Migrate to B2 later if code
sharing becomes a problem.** B1 requires zero server-side infrastructure and works
with Netlify's static hosting.

---

## 6. Checkout Flow

### Happy Path: Developer in India Buys Perpetual

| Step | What Happens |
|:-----|:-------------|
| 1. Visit runprep.io/pricing | Netlify edge function detects country=IN |
| 2. Page renders | Shows "$29 one-time" (Band 3, 60% off). Badge: "Price adjusted for India" |
| 3. Click "Buy Perpetual" | Redirects to LS checkout: `?discount=PPP60` |
| 4. LS checkout loads | Shows ₹2,415 (INR equivalent of $29). Card/PayPal payment. |
| 5. Payment processes | LS collects ₹2,415, converts to ~$29 USD. Remits GST to India. |
| 6. Webhook fires | api.runprep.io generates Ed25519 license (tier=perpetual). Same license regardless of price paid. |
| 7. Email with key | Customer activates in Prep app. Fully offline from here. |

### Key Principle: Same License, Different Price

**The license file does NOT contain the price paid.** All perpetual licenses are identical
regardless of PPP band. The pricing adjustment is purely a checkout-time concern.

---

## 7. Anti-Abuse Measures

PPP pricing creates an incentive for US/EU users to use VPNs to get discounted prices.
This is a known problem for every company offering PPP pricing.

### Acceptable Abuse Rate

**Target: <5% of discounted purchases are geo-spoofed.** At Prep's price points
($29–$79), the effort of setting up a VPN to save $20–50 is not worth it for most
professional developers. The risk is low.

### Mitigation Layers

| Layer | Mechanism | Effectiveness |
|:------|:----------|:-------------|
| **1. Geo-IP match** | Country at checkout (LS-side) must match country detected on pricing page | Catches casual VPN users who forget to VPN during checkout |
| **2. Payment method geo** | LS sees the billing country on the card. If card country ≠ IP country, LS may flag | Automatic — LS handles this as part of fraud detection |
| **3. Discount code limits** | Set `max_redemptions` on PPP discount codes. Rotate codes monthly. | Limits damage from code sharing |
| **4. Honor system note** | "This price is adjusted for [Country]. If you're purchasing from a different region, please use the full-price option." | Surprisingly effective — most developers are honest |
| **5. Post-purchase audit** | Periodic check: if activation IP is consistently US/EU but purchase used PPP60, flag for review | Manual, low priority, do after launch |

### NOT Doing

- **No payment method blocking** — Developers travel. A US card used from India is legitimate.
- **No license revocation for geo mismatch** — Too aggressive. Damages trust.
- **No "prove your country" verification** — Friction kills conversion.

---

## 8. Revenue Impact Modeling

### Assumptions

- 1,000 paid licenses sold in year 1
- Without PPP: 80% from Band 0 countries, 15% Band 1, 5% Band 2+3
- With PPP: 50% Band 0, 20% Band 1, 15% Band 2, 15% Band 3

### Perpetual License Revenue (Year 1, 1000 licenses)

| Scenario | Band 0 | Band 1 | Band 2 | Band 3 | Total Revenue | vs. No PPP |
|:---------|:-------|:-------|:-------|:-------|:-------------|:-----------|
| **No PPP** | 800 × $79 = $63,200 | 150 × $79 = $11,850 | 50 × $79 = $3,950 | — | **$79,000** | — |
| **With PPP** | 500 × $79 = $39,500 | 200 × $59 = $11,800 | 150 × $45 = $6,750 | 150 × $29 = $4,350 | **$62,400** | −21% |

**Revenue per license drops, but total volume goes up.** The PPP model is a bet that
300 additional sales (at lower prices) from Band 2+3 more than compensate for the
Band 0 customers who remain.

**Break-even question:** Does PPP pricing generate enough ADDITIONAL sales to offset
the discount? At 1,000 total sales with PPP vs. 1,000 without, revenue drops 21%.
But if PPP enables 1,300+ total sales (30% volume lift), it's revenue-neutral.
If it enables 1,500+ sales (50% lift, common in industry reports), it's revenue-positive.

**Industry data:** Tailwind UI reported ~40% volume increase after introducing PPP
pricing. JetBrains sees majority of new license growth from PPP-eligible regions.

### Recommendation: Launch PPP pricing from day one. Revisit bands after 6 months
of data.

---

## 9. Implementation Options Comparison

| Criterion | ParityDeals | Edge + Discount Codes | Edge + LS Checkout API |
|:----------|:------------|:---------------------|:---------------------|
| **Setup time** | 1 hour | 1–2 days | 2–3 days |
| **Server-side code** | None | None (static) | Yes (Netlify Function) |
| **UX quality** | Banner overlay (cheap feel) | Native pricing page | Native pricing page |
| **Price visibility** | Shows original + discount | Shows original + discount | Shows only adjusted price |
| **Code sharing risk** | High (codes in banner) | Medium (codes in URL) | None (unique checkout URLs) |
| **Cost** | Free–$9/mo | Free | Free (LS API is free) |
| **Dependency** | ParityDeals service | None | Lemon Squeezy API |
| **Maintenance** | Low | Low | Medium |

**Phase 1 (launch):** Edge + Discount Codes — best balance of UX, simplicity, and speed.
**Phase 2 (post-launch):** Migrate to Edge + LS Checkout API if discount code abuse emerges.

---

## 10. TODO — Implementation Checklist

### Phase 1: Foundation (Pre-Launch)

- [ ] **LS-01: Create PPP discount codes in Lemon Squeezy**
  - `PPP20` — 20% off, applicable to Monthly + Perpetual + Team products
  - `PPP40` — 40% off, same products
  - `PPP60` — 60% off, same products
  - Set `max_redemptions` per code (e.g., 10,000) and rotate quarterly

- [ ] **LS-02: Create LS products for all tiers**
  - Monthly subscription product ($7/mo)
  - Perpetual license product ($79 one-time)
  - Team subscription product ($15/seat/mo)
  - Each with webhook → api.runprep.io for license generation

- [ ] **WEB-01: Add Netlify Edge Function for geo-detection**
  - Read `context.geo.country.code` on `/pricing` path
  - Set `x-visitor-country` cookie or header
  - Fallback: default to Band 0 (US pricing) if geo unavailable

- [ ] **WEB-02: Create `lib/pricing.ts` utility module**
  - `COUNTRY_PPP_BAND` map (country ISO → band 0-3)
  - `PPP_PRICES` per-band price table
  - `getPrices(country: string)` → `{ monthly, perpetual, team, discount, bandName }`
  - `getCheckoutUrl(product, country)` → LS checkout URL with discount param
  - `formatPrice(amount)` → display string

- [x] **WEB-03: Update `pricing/page.tsx` for dynamic pricing**
  - Read visitor country from cookie/header (SSR or edge)
  - Render prices from `getPrices(country)` instead of hardcoded values
  - Silent price adjustment (no banners or strikethroughs)
  - "Buy" buttons link to checkout URLs with discount code appended
  - Fallback: if JS disabled or country unknown, show full US prices

- [ ] **WEB-04: Add "Pricing may vary by region" footer note**
  - Small text under pricing grid explaining PPP
  - Link to FAQ: "Why is my price different?"

### Phase 2: Polish (Post-Launch)

- [ ] **WEB-05: Add pricing FAQ section**
  - "Why is my price different from what I see elsewhere?"
  - "Can I switch regions?"
  - "Is the license the same regardless of price?"

- [ ] **WEB-06: Add region override / manual country selector**
  - Dropdown to manually select country (for VPN users, travelers)
  - Updates prices on the page dynamically
  - Stores selection in localStorage

- [ ] **LS-03: Migrate to LS Checkout API (dynamic custom_price)**
  - Netlify Function: `POST /api/create-checkout` → calls LS API → returns checkout URL
  - Eliminates discount codes entirely
  - User sees ONLY their regional price at checkout

- [ ] **WEB-07: Add pricing A/B test framework**
  - Test Band 2/3 price points (e.g., $45 vs $39 for Band 2 Perpetual)
  - Measure conversion rate per band
  - Use LS discount code variants for testing

### Phase 3: Optimization (6+ Months Post-Launch)

- [ ] **DATA-01: Analyze PPP conversion data**
  - Revenue per band, conversion rate per band, abuse rate
  - Adjust band assignments and discount percentages based on data

- [ ] **WEB-08: Local payment method support**
  - Monitor LS roadmap for Boleto (Brazil), UPI (India), iDEAL (Netherlands)
  - These would significantly increase conversion in Band 2+3 countries

- [ ] **LS-04: Consider annual billing for Monthly tier**
  - $7/mo = $84/yr. Offer $59/yr annual (30% discount) with PPP on top
  - Example: Band 3 annual = $24/yr ($2/mo) — extremely compelling

---

## 11. Open Questions

1. **Should Team tier get PPP pricing?** Teams in Band 2/3 countries have lower budgets,
   but team purchases are often company-funded (less price-sensitive). Could offer
   smaller PPP discounts for Team (e.g., max 30% instead of 60%).

2. **Enterprise pricing?** Enterprise is "custom" — PPP is handled per-deal. No change
   needed for website.

3. **Founder's Edition interaction.** The existing plan mentions a $49 "Founder's
   Edition" for first 500 users. If PPP pricing is live at launch, Band 3 Perpetual
   is already $29. Should Founder's Edition be Band-0-only? Or should it stack
   (Band 3 Founder's = $19)?

4. **Education discount.** Separate from PPP. Many tools offer 50% education discount
   globally. This would stack with PPP for student developers in Band 3 countries
   (Perpetual: $29 × 50% = $15). Is this worth the complexity?

5. **Mac App Store pricing.** If/when Prep is on the Mac App Store (paid-upfront
   model), Apple has its own regional pricing tiers. These don't need to match our
   PPP bands exactly — Apple handles it. But the price points should be in the same
   ballpark.

6. **Currency display on website.** Current recommendation is USD-only on the website
   (LS checkout shows local currency). Should we show local currency estimates on
   the pricing page too? This adds complexity (exchange rate API, formatting) but
   may improve conversion.

---

## Appendix A: World Bank PPP Reference

PPP conversion factors (2024) for reference. A higher factor means the country's
currency buys more locally than the exchange rate suggests.

| Country | PPP Factor (vs USD) | Our Band | Discount |
|:--------|:--------------------|:---------|:---------|
| US | 1.00 | 0 | 0% |
| UK | 0.72 | 0 | 0% |
| Germany | 0.76 | 0 | 0% |
| Japan | 0.67 | 0 | 0% |
| Spain | 0.64 | 1 | 20% |
| Poland | 0.44 | 1 | 20% |
| South Korea | 0.60 | 1 | 20% |
| Brazil | 0.29 | 2 | 40% |
| Mexico | 0.34 | 2 | 40% |
| Turkey | 0.21 | 2 | 40% |
| India | 0.18 | 3 | 60% |
| Vietnam | 0.17 | 3 | 60% |
| Nigeria | 0.14 | 3 | 60% |
| Pakistan | 0.13 | 3 | 60% |

*Source: World Bank International Comparison Program (ICP). Factors approximate
and rounded for clarity.*

## Appendix B: Competitor PPP Pricing

| Product | PPP Approach | Discount Range | Countries |
|:--------|:-------------|:---------------|:----------|
| **JetBrains** | Region-specific base prices (not discount codes) | ~20-60% | 200+ |
| **Tailwind UI** | PPP banner (honor system) | 20-50% | ~50 countries |
| **Notion** | No explicit PPP (education discount only) | 50% edu | Global |
| **Linear** | Geo-IP detected, discount auto-applied | 20-40% | ~30 countries |
| **1Password** | Regional pricing via Paddle | 20-50% | ~40 countries |
| **Cursor** | No PPP | — | — |
| **Windsurf** | No PPP | — | — |
| **GitHub Copilot** | No PPP (verified student = free) | 100% students | Global |

**Opportunity:** Most AI code tools (Cursor, Windsurf, Copilot) do NOT offer PPP.
Prep can differentiate by being developer-friendly AND globally accessible.

---

**Legal Entity:** Magnetic Anomaly LLC
**Copyright:** © 2025–2026 Magnetic Anomaly LLC. All rights reserved.
