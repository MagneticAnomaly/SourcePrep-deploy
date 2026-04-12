# Distribution & Revenue Plan — AUTHORITATIVE

> **Status:** AUTHORITATIVE — This is the single source of truth for CoDRAG's distribution,
> payments, and licensing strategy. All other docs (Phase 10, Phase 11, Phase 12) are
> historical research. If they conflict with this document, **this document wins.**
>
> **Last reviewed:** 2026-02-12
> **Entity:** Magnetic Anomaly LLC
> **Product:** CoDRAG (Desktop Application)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Distribution Channels](#2-distribution-channels)
3. [Payments & Licensing](#3-payments--licensing)
4. [Money Flow](#4-money-flow)
5. [Customer Experience (End-to-End)](#5-customer-experience-end-to-end)
6. [App Store Compliance Analysis](#6-app-store-compliance-analysis)
7. [Pricing Tiers](#7-pricing-tiers)
8. [Operational Stack](#8-operational-stack)
9. [Superseded Documents](#9-superseded-documents)
10. [Open Items & Risks](#10-open-items--risks)

---

## 1. Executive Summary

CoDRAG is distributed as a **native Tauri desktop app** (macOS + Windows).

| Decision | Choice | Rationale |
|:---|:---|:---|
| **Primary distribution** | Direct download from codrag.io | Full control, zero commission, fastest iteration |
| **Secondary distribution** | Microsoft Store | Free listing, external licensing allowed per MS policy |
| **Deferred distribution** | Mac App Store | Apple requires IAP for feature unlocks; needs separate payment flow |
| **Payment processor** | **Lemon Squeezy** (Merchant of Record) | Handles tax, VAT, refunds globally. No Stripe Tax config needed. |
| **Licensing** | Ed25519-signed offline license files | One-time activation, then fully offline. No phone-home. |
| **NOT used** | pip / PyPI | CoDRAG is not a Python package for end users |
| **NOT used** | Stripe (direct) | Replaced by Lemon Squeezy as MoR (simpler tax compliance) |

---

## 2. Distribution Channels

### Channel A: Direct Download (PRIMARY — Launch Day)

The primary distribution channel. Highest margin, full control, fastest time to market.

- **Website:** codrag.io/download
- **Artifacts:**
  - macOS: `.dmg` (Universal — Apple Silicon + Intel), code-signed + notarized
  - Windows: `.msi` installer (x64), code-signed (EV certificate recommended)
- **Hosting:** GitHub Releases (`github.com/MagneticAnomaly/CoDRAG-MCP/releases`)
  - Download buttons on codrag.io/download link to the latest GitHub Release assets
  - SHA-256 checksums published alongside each release
- **Auto-update:** Tauri built-in updater checks for new releases on launch
- **Commission:** 0% (only Lemon Squeezy's MoR fee — see §4)

### Channel B: Microsoft Store (SECONDARY — Launch or Shortly After)

Low friction to set up. Microsoft allows external licensing for non-game desktop apps.

- **Listing:** Free download (the app itself costs nothing to install)
- **Licensing:** Via Lemon Squeezy (external) — **compliant** per MS Store Policy 10.8.1:
  > "Non-game products made available on PC devices may either use a secure
  > third-party purchase API or the Microsoft Store in-product purchase API
  > for in-app purchases of digital items or services."
- **Commission:** 0% on externally processed transactions
- **Requirements:**
  - Microsoft Partner Center developer account (Magnetic Anomaly LLC)
  - Code-signed MSI/EXE
  - Declare use of third-party purchase API in Partner Center submission
- **In-app UX:** "Upgrade to Pro" prompts are allowed. Users are directed to
  codrag.io/pricing (Lemon Squeezy checkout) or can enter a license key directly.

### Channel C: Mac App Store (DEFERRED — Post-Launch, If Pursued)

**⚠️ COMPLIANCE BLOCKER:** Apple App Store Review Guideline 3.1.1 explicitly prohibits
using license keys to unlock features:

> "If you want to unlock features or functionality within your app... you must use
> in-app purchase. Apps may not use their own mechanisms to unlock content or
> functionality, **such as license keys**, augmented reality markers, QR codes..."

**What this means:** You CANNOT list CoDRAG as free on the Mac App Store and have
users buy a Lemon Squeezy license to unlock Pro features. Apple will reject it.

**Options if you want Mac App Store presence:**

| Option | Pros | Cons |
|:---|:---|:---|
| **C1: IAP on App Store** | Full compliance, discovery | 15–30% commission, two payment systems, duplicate entitlement logic |
| **C2: Free-only on App Store** | Discovery, trust signal | No revenue; zero purchase CTAs allowed (Guideline 3.1.3(f)) |
| **C3: Skip App Store entirely** | Simple, one payment system | Lose discoverability (most dev tools skip MAS anyway) |
| **C4: Two separate apps — "CoDRAG" (free) + "CoDRAG Pro" ($84.99 paid-upfront)** | No IAP complexity, no license key, Apple handles billing, no Lemon Squeezy cut | Two App Store listings to maintain; App Sandbox still applies to both |

**Recommendation: Option C4 if/when Mac App Store is pursued.** Shipping a separate
paid-upfront "CoDRAG Pro" app is fully compliant — the license key prohibition only
applies to unlocking features inside a free app via external payment. A paid-upfront
app has no license mechanism at all: `CODRAG_TIER=pro` is baked in at build time,
Apple's purchase receipt tied to the user's Apple ID is the "license", and the app
optionally verifies the StoreKit receipt to prevent side-loading. No Lemon Squeezy,
no api.codrag.io, no machine activation limits — Apple handles all of it.

**Tiers on Apple:** Free app (free tier only) + Pro app ($84.99). **No Monthly tier** —
the subscription model doesn't map cleanly to a paid-upfront App Store app.

**For launch: Option C3 (Skip).** Revisit as C4 after direct download is stable.

**Precedent:** JetBrains, Sublime Text, Docker Desktop, Tower (partially), TablePlus
(partially) — all use direct download + license key as primary. Only some also offer
an IAP variant on the Mac App Store.

**Additional Mac App Store risks (documented in Phase 11):**
- App Sandbox may conflict with scanning arbitrary repos (CoDRAG's core workflow)
- Bundling and executing a Python sidecar needs validation under App Review
- These are schedule blockers even if the payment issue were resolved

### Channel D: Enterprise (FUTURE)

- Direct download (MSI/DMG) + offline Ed25519 license key
- Distributed via MDM / internal app catalogs
- Invoice/PO billing via Lemon Squeezy (or manual if needed)
- See `docs/Phase11_Deployment/ENTERPRISE_DISTRIBUTION_AND_LICENSING.md` for details
  (that doc's content is still accurate for enterprise patterns)

---

## 3. Payments & Licensing

### Payment Processor: Lemon Squeezy

| Property | Value |
|:---|:---|
| **Role** | Merchant of Record (MoR) |
| **What MoR means** | Lemon Squeezy is the legal seller. They handle sales tax, VAT, refunds, chargebacks, and compliance. You receive net payouts. |
| **Storefront** | payments.codrag.io (Lemon Squeezy-hosted checkout or embedded) |
| **Products** | Monthly Subscription, Perpetual License, Team Subscription (configured as LS products) |
| **Webhooks** | `order_completed` → triggers license generation on api.codrag.io |
| **Fee** | ~5% + payment processing (~2.9% + $0.30 per txn) |
| **Payout** | To Magnetic Anomaly LLC business bank account |

**Why Lemon Squeezy over Stripe:**
- **Tax compliance is automatic.** Stripe requires you to configure Stripe Tax, register
  for VAT in each jurisdiction, and file returns yourself. Lemon Squeezy handles all of
  this as MoR — they are the legal seller, not you.
- **Simpler for a solo/small team.** One dashboard for products, licenses, analytics.
- **Built-in license key generation.** (Though we use our own Ed25519 system for offline
  validation, LS keys serve as the activation input.)

### License Activation Flow ("Activation Exchange")

```
┌─────────────┐     ┌──────────────────┐     ┌──────────────────┐     ┌─────────────┐
│  Customer    │     │  Lemon Squeezy   │     │  api.codrag.io   │     │  CoDRAG App │
│  (Browser)   │     │  (MoR + Checkout)│     │  (Serverless)    │     │  (Desktop)  │
└──────┬───────┘     └────────┬─────────┘     └────────┬─────────┘     └──────┬──────┘
       │                      │                        │                      │
       │  1. Buy license      │                        │                      │
       │─────────────────────►│                        │                      │
       │                      │                        │                      │
       │  2. LS processes     │                        │                      │
       │     payment + tax    │                        │                      │
       │                      │                        │                      │
       │  3. Webhook:         │                        │                      │
       │     order_completed  │───────────────────────►│                      │
       │                      │                        │                      │
       │  4. Email with       │                        │  (License generated  │
       │     license key      │                        │   and stored)        │
       │◄─────────────────────│                        │                      │
       │                      │                        │                      │
       │  5. Enter key in app │                        │                      │
       │──────────────────────┼────────────────────────┼─────────────────────►│
       │                      │                        │                      │
       │                      │                        │  6. POST /activate   │
       │                      │                        │◄─────────────────────│
       │                      │                        │                      │
       │                      │                        │  7. Return signed    │
       │                      │                        │     Ed25519 license  │
       │                      │                        │─────────────────────►│
       │                      │                        │                      │
       │                      │                        │  8. Save to disk     │
       │                      │                        │     (~/.codrag/      │
       │                      │                        │      license.key)    │
       │                      │                        │                      │
       │                      │                        │  ✅ FULLY OFFLINE    │
       │                      │                        │     FROM HERE ON     │
```

**Steps 6–7 require a one-time internet connection.** After that, the app validates
the Ed25519 signature locally — no phone-home, no subscription heartbeat.

### License File Format

Ed25519-signed JSON payload (see `docs/Phase11_Deployment/LICENSING_IMPLEMENTATION.md`
for full schema). Key fields:

```json
{
  "id": "uuid-v4",
  "issued_to": "email@example.com",
  "tier": "pro",
  "seats": 1,
  "expires_at": null,
  "updates_until": 1767225600,
  "features": ["trace_index", "mcp_advanced", "auto_rebuild"]
}
```

---

## 4. Money Flow

### Direct Download (Channel A) — Primary Revenue

```
Customer pays $79 (Pro License)
        │
        ▼
Lemon Squeezy collects $79
        │
        ├── Sales tax / VAT withheld and remitted by LS (MoR obligation)
        ├── LS fee: ~5% of net ($3.56)
        ├── Stripe processing: ~2.9% + $0.30 ($2.59)
        │
        ▼
Net payout to Magnetic Anomaly LLC: ~$72.85
        │
        ▼
Business Checking Account (Mercury / Chase)
```

### Microsoft Store (Channel B) — Zero Additional Commission

Same flow as Channel A. Microsoft does not take a commission on externally
processed transactions for non-game desktop apps.

### Mac App Store (Channel C) — IF EVER PURSUED via Paid-Upfront Two-App Model (C4)

```
Customer pays $84.99 ("CoDRAG Pro" paid-upfront app)
        │
        ▼
Apple collects $84.99
        │
        ├── Apple commission: 15% ($12.75) — Small Business Program
        │   (or 30% / $25.50 if revenue > $1M/year from App Store)
        │
        ▼
Net payout to Magnetic Anomaly LLC: ~$72.24 (15%) or ~$59.49 (30%)
        │
        ▼
Business Checking Account
```

**Price rationale:** $84.99 at 15% Small Business rate nets ~$72.24 — nearly identical
to the $72.85 net from a $79 direct sale via Lemon Squeezy.

Note: No Lemon Squeezy, no api.codrag.io, no machine activation logic — Apple handles
all payment and receipt validation. Implementation cost is a build flag + optional
StoreKit receipt check. The real cost is App Sandbox compliance testing.

---

## 5. Customer Experience (End-to-End)

### Happy Path: New User → Free → Pro

| Step | What the user does | What happens behind the scenes |
|:---|:---|:---|
| 1. **Discover** | Finds CoDRAG via search, recommendation, or MCP marketplace | — |
| 2. **Download** | Goes to codrag.io/download, clicks "Download for Mac" | Browser downloads `.dmg` from GitHub Releases |
| 3. **Install** | Opens `.dmg`, drags to Applications | Standard macOS install. Gatekeeper passes (notarized). |
| 4. **Launch** | Opens CoDRAG from Applications | Tauri app starts, launches Python sidecar daemon on port 8400 |
| 5. **Use (Free)** | Adds 3 projects, connects MCP, uses CoDRAG | Free tier: 3 projects, fully automated syncing. No account needed. |
| 6. **Hit limit** | Tries to add a 4th project | Dashboard shows "Upgrade to Pro" with link to codrag.io/pricing |
| 7. **Buy** | Clicks link → codrag.io/pricing → Lemon Squeezy checkout | LS processes payment, handles tax. Webhook fires. |
| 8. **Receive key** | Gets email with license key | api.codrag.io generates Ed25519 license upon webhook receipt |
| 9. **Activate** | Pastes key into CoDRAG → Settings → License | App calls `POST api.codrag.io/activate` with the LS key |
| 10. **Activated** | Sees "Pro — Active" in dashboard | Signed license saved to `~/.codrag/license.key`. Fully offline from here. |
| 11. **Use (Pro)** | Unlimited projects, Trace Index, auto-rebuild, full MCP | Feature gates read tier from local license file |

### Recovery Path: Lost License Key

1. User goes to codrag.io/recover (or payments.codrag.io/recover)
2. Enters email address
3. Lemon Squeezy API looks up orders by email
4. License key is re-sent to the user's email
5. User re-enters key in the app

---

## 6. App Store Compliance Analysis

### Apple Mac App Store — Guideline 3.1.1

**Source:** https://developer.apple.com/app-store/review/guidelines/ (§3.1.1)

**Rule:** "If you want to unlock features or functionality within your app... you must
use in-app purchase. Apps may not use their own mechanisms to unlock content or
functionality, such as **license keys**..."

**CoDRAG impact:**
- ❌ Cannot use Lemon Squeezy license keys to unlock Pro features in a Mac App Store build
- ❌ Cannot show "Buy on codrag.io" or "Upgrade to Pro" prompts (unless using US storefront
  entitlement, which is iOS/iPadOS only)
- ✅ Could list a free-only version with zero purchase CTAs (Guideline 3.1.3(f))
  — but this provides no revenue and limits UX
- ✅ Could implement IAP for the App Store channel (Guideline 3.1.1 compliant)
  — but requires maintaining two payment systems

**Decision: Defer Mac App Store. Use direct download + notarization for macOS.**

### Microsoft Store — Policy 10.8.1

**Source:** https://learn.microsoft.com/en-us/windows/apps/publish/store-policies (§10.8.1)

**Rule:** "Non-game products made available on PC devices may either use a **secure
third-party purchase API** or the Microsoft Store in-product purchase API for in-app
purchases of digital items or services."

**CoDRAG impact:**
- ✅ Lemon Squeezy qualifies as a "secure third-party purchase API"
- ✅ Can show "Upgrade to Pro" prompts that link to Lemon Squeezy checkout
- ✅ Can accept license keys in-app for activation
- ⚠️ Must declare use of third-party purchase API in Partner Center submission
- ⚠️ Must identify Lemon Squeezy as the commerce provider at transaction time

**Decision: List on Microsoft Store at or shortly after launch.**

### Lemon Squeezy — MoR Obligations

**What LS handles (you don't have to):**
- Sales tax collection and remittance (US states)
- VAT collection and remittance (EU, UK, etc.)
- GST (Australia, NZ, etc.)
- Invoicing with correct tax IDs
- Refund processing
- Chargeback handling
- PCI DSS compliance (card data never touches your servers)

**What you still handle:**
- Product pricing decisions
- License key generation (your api.codrag.io service)
- Customer support (support@codrag.io)
- Accounting reconciliation (LS payouts vs. bank deposits)

---

## 7. Pricing Tiers

| Tier | Price | Duration | Projects | Key Features |
|:---|:---|:---|:---|:---|
| **Free** | $0 | Forever | 3 | Full automation, semantic search, full MCP suite |
| **Monthly** | $7/mo | Subscription | Unlimited | Real-time watchers, full MCP, auto-rebuild, CLaRa compression |
| **Perpetual** | $79 | One-time license | Unlimited | Everything in Monthly, never expires, offline activation |
| **Team** | $15/seat/mo | Subscription | Unlimited | Shared config, centralized policy, license management |
| **Enterprise** | Custom | Custom | Unlimited | Air-gapped, SSO/SCIM, audit logs, dedicated support |

All tiers are Lemon Squeezy products. Enterprise may involve manual invoicing.

### International Pricing (Purchasing Power Parity)

Prices above are **Band 0 (US/EU/UK/AU/JP)** base prices. CoDRAG uses a 4-band PPP
model to make pricing accessible in emerging developer markets while maintaining
revenue from tier-1 economies.

| Band | Discount | Monthly | Perpetual | Team | Example Countries |
|:-----|:---------|:--------|:----------|:-----|:------------------|
| **0 — Full** | 0% | $7/mo | $79 | $15/seat/mo | US, Canada, UK, Germany, Japan, Australia |
| **1 — Moderate** | 20% | $5/mo | $59 | $12/seat/mo | Spain, Poland, South Korea, Taiwan, Chile |
| **2 — High** | 40% | $4/mo | $45 | $9/seat/mo | Brazil, Mexico, Turkey, South Africa, Thailand |
| **3 — Maximum** | 60% | $3/mo | $29 | $6/seat/mo | India, Indonesia, Vietnam, Nigeria, Pakistan |

- Geo-detection via Netlify Edge Function (reads `context.geo.country`)
- Prices adjusted on codrag.io/pricing; LS checkout uses PPP discount codes
- License files are identical regardless of price paid — no tier difference
- Full strategy: [`Phase10_.../Pricing/GLOBAL_PRICING.md`](Phase10_Business_And_Competitive_Research/Pricing/GLOBAL_PRICING.md)

---

## 8. Operational Stack

| Function | Tool | Notes |
|:---|:---|:---|
| **Entity** | Magnetic Anomaly LLC | Holds IP, receives revenue |
| **Banking** | Mercury or Chase | Single business checking account |
| **Payments (MoR)** | Lemon Squeezy | Handles tax, compliance, refunds |
| **License Generation** | api.codrag.io (serverless) | Ed25519 signing on webhook receipt |
| **Hosting (website)** | Netlify | codrag.io, docs.codrag.io, support.codrag.io, payments.codrag.io (free tier, commercial OK) |
| **Hosting (releases)** | GitHub Releases | DMG, MSI, checksums |
| **DNS** | Cloudflare | Edge caching, redirects |
| **Accounting** | Xero or QuickBooks | Syncs with bank; tag revenue by channel |
| **Apple Developer** | $99/year | For code signing + notarization (NOT App Store) |
| **MS Partner Center** | Free (or $19 one-time) | For Microsoft Store listing |
| **Code Signing (Win)** | EV certificate | ~$200–500/year, immediate SmartScreen trust |

---

## 9. Superseded Documents

The following docs contain **stale or conflicting** information. They remain as historical
research but **this document takes precedence** on any point of conflict.

| Document | Conflict |
|:---|:---|
| `docs/Phase10_.../FINANCE_AND_LEGAL_STRUCTURE.md` | Says **Stripe** is payment processor (§3, §4). Should be **Lemon Squeezy**. |
| `docs/Phase11_.../LICENSING_IMPLEMENTATION.md` | Activation flow (line 118–122) says "Stripe Webhook → CoDRAG License Service". Should be **Lemon Squeezy webhook → api.codrag.io**. |
| `docs/Phase11_.../ENTERPRISE_DISTRIBUTION_AND_LICENSING.md` | Line 91: "App Store builds will likely be 'Pro' via In-App Purchase (IAP)". Correct for Apple, but **Mac App Store is deferred** per this plan. |
| `docs/Phase11_.../LEMON_SQUEEZY_INTEGRATION.md` | Referenced in MASTER_TODO.md (STR-09) but **file does not exist**. This document replaces it. |

---

## 10. Open Items & Risks

### Implementation Gaps (Blocking Launch)

| Item | Status | Ref |
|:---|:---|:---|
| `POST /license/activate` — full LS activation exchange | NOT_IMPLEMENTED (returns stub) | MASTER_TODO.md audit |
| api.codrag.io relay service (serverless) | NOT_IMPLEMENTED | — |
| Ed25519 key pair generation + secure storage (HSM) | NOT_IMPLEMENTED | LICENSING_IMPLEMENTATION.md |
| Lemon Squeezy product setup (5 tiers) | NOT_DONE | — |
| Lemon Squeezy webhook integration | NOT_DONE | — |
| License recovery endpoint (real LS API integration) | MOCK STUB | payments app `POST /api/recover` |
| macOS code signing + notarization pipeline | NOT_DONE | MACOS_DISTRIBUTION.md |
| Windows EV code signing | NOT_DONE | WINDOWS_DISTRIBUTION.md |

### Risks

| Risk | Impact | Mitigation |
|:---|:---|:---|
| Mac App Store exclusion limits discovery | Low — dev tools rarely acquired via App Store | SEO, MCP marketplace, content marketing |
| Windows SmartScreen warnings without EV cert | Medium — scares new users | Budget for EV cert ($200–500/yr) |
| Lemon Squeezy downtime blocks new purchases | Low — existing users unaffected (offline license) | LS has 99.9% uptime SLA |
| App Sandbox blocks Mac App Store (if pursued later) | High — CoDRAG needs filesystem access | Test thoroughly before committing to IAP work |
| Ed25519 private key compromise | High — all licenses become untrusted | Use HSM; have key rotation plan (ship new public key in app update) |

---

## Appendix: Why Not "Free on App Store + Charge Externally"?

This is the question that prompted this document. The short answer:

**Apple explicitly bans it.** Guideline 3.1.1 says apps "may not use their own mechanisms
to unlock content or functionality, such as license keys." There is no exception for
desktop developer tools.

The narrow exception in 3.1.3(f) ("free stand-alone companion to a paid web tool")
requires that there be **no purchasing inside the app** and **no calls to action for
purchase outside the app.** This means:
- No "Upgrade to Pro" button
- No "Visit codrag.io/pricing" link
- No indication that paid features exist
- The free version must feel complete on its own

This is impractical for a freemium product. If you can't tell users that Pro exists,
the App Store listing generates no revenue and provides minimal conversion value.

**The developer tool industry agrees:** JetBrains, Sublime Text, Docker Desktop,
Linear, Raycast, and most other successful desktop dev tools either skip the Mac
App Store entirely or maintain a separate IAP flow for the App Store channel.

**Bottom line:** Direct download from codrag.io is the correct primary channel.
Microsoft Store is a free bonus. Mac App Store is a future option requiring IAP work.
