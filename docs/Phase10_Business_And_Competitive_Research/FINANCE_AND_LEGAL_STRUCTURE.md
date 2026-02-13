# Finance and Legal Structure: Magnetic Anomaly LLC

> **⚠️ PARTIALLY SUPERSEDED** — This document references **Stripe** as the payment
> processor. The authoritative plan now uses **Lemon Squeezy** as Merchant of Record.
> See [`docs/DISTRIBUTION_AND_REVENUE_PLAN.md`](../DISTRIBUTION_AND_REVENUE_PLAN.md)
> for the current source of truth.

## Purpose
This document outlines the operational financial structure for **Magnetic Anomaly LLC**, the umbrella entity for CoDRAG and future applications.

## 1. Corporate Structure
- **Entity Name:** Magnetic Anomaly LLC
- **Role:** Umbrella holding company.
- **Function:** Holds IP, manages banking, and receives all revenue.
- **Apps:**
  - CoDRAG (Developer Tool)
  - [Future Apps]

## 2. Banking Strategy
**Constraint:** Keep overhead low with a single centralized repository for funds.

- **Primary Account:** Single Business Checking Account (e.g., Mercury, Brex, or traditional bank).
- **Flow:** All revenue sources payout to this single IBAN/Account Number.
- **Accounting:** Use tags/labels in accounting software (e.g., Xero/Quickbooks) to attribute revenue to specific apps if needed, rather than separate bank accounts.

## 3. Revenue Channels & Implementation

### Channel A: Direct Sales (Web Licensing)
*Primary channel for CoDRAG Starter Passes and Pro Licenses.*

- **Platform:** **Stripe** (Direct Integration).
- **Setup:**
  - **Account:** One Stripe account for "Magnetic Anomaly LLC".
  - **Descriptors:** Use dynamic statement descriptors if possible (e.g., `MAGANOM* CODRAG`) or generic `MAGNETIC ANOMALY`.
  - **Domain:** `payments.codrag.io` (or similar subdomain).
- **Checkout Flow:**
  1. User clicks "Buy Starter Pass" or "Buy Pro License" on landing page.
  2. Redirects to Stripe Checkout (hosted session).
  3. **Webhook:** Stripe sends `checkout.session.completed` to CoDRAG License Server.
  4. **Fulfillment:** License Server generates `Ed25519` key (with expiration for Starter, perpetual for Pro) and emails it to user.
- **Tax Compliance:** 
  - *Note:* Using Stripe directly requires configuring **Stripe Tax** to handle VAT/Sales Tax collection and remittance automatically.

### Channel B: App Stores (Distribution)
*Secondary channel for discovery or specific platform compliance.*

- **Apple App Store (macOS):**
  - **Entity:** Magnetic Anomaly LLC (DUNS number required).
  - **Payout:** Monthly wire to Business Checking.
  - **Commission:** 15% (Small Business Program) or 30%.
- **Microsoft Store (Windows):**
  - **Entity:** Magnetic Anomaly LLC.
  - **Payout:** Monthly wire.

## 4. Operational Stack

| Function | Tool Recommendation | Notes |
| :--- | :--- | :--- |
| **Banking** | Mercury / Chase / SVB | Needs good API access for accounting. |
| **Payments** | Stripe | Enable "Stripe Tax" immediately to avoid liability. |
| **Accounting** | Xero / QuickBooks Online | Syncs with Stripe & Bank. |
| **Registered Agent** | [Provider Name] | Required for LLC compliance. |

## 5. Next Steps for Setup
1.  **Form LLC:** File Articles of Organization.
2.  **EIN:** Obtain from IRS.
3.  **Bank Account:** Open using EIN + Articles.
4.  **Stripe Account:** Activate using Bank Account + EIN.
5.  **Apple Developer:** Enroll as Organization (requires DUNS number).
