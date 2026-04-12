# Pricing Strategy

> **⚠️ PARTIALLY SUPERSEDED** — Tier names have changed: Starter → **Monthly** ($7/mo),
> Pro → **Perpetual** ($79 one-time). International pricing is now covered in
> [`GLOBAL_PRICING.md`](GLOBAL_PRICING.md). The authoritative pricing tiers are in
> [`DISTRIBUTION_AND_REVENUE_PLAN.md`](../../DISTRIBUTION_AND_REVENUE_PLAN.md) §7.

## Executive Summary
CoDRAG adopts a **"Software License"** model (Perpetual License) for individuals and a **"Seat-Based Subscription"** for teams. This aligns with our local-first, BYOK architecture where COGS is low (no hosted inference costs).

**Core Philosophy:**
- **Local-First Trust:** Users own the software, not rent it.
- **BYOK Cost Savings:** We don't mark up tokens; users pay provider costs directly.
- **Gated by Value, Not Tokens:** We charge for *structural intelligence* (Trace Index), *scale* (Project Volume), and *governance*.

## 1. The "Indie/Pro" Model: Perpetual License
Target: Individual developers who value ownership and privacy.
Precedents: TablePlus, Sublime Text, JetBrains.

### Free Tier (The Hook)
- **Price:** $0
- **Limits:** 
  - **3 active projects** (indexed repos).
- **Features:** All features included — Trace Index, real-time watcher, full MCP suite, automation.
- **Purpose:** Compete with open-source, build trust, drive adoption.

### Starter Tier (The Bridge)
- **Price:** **$29** / 4-months (Pass).
- **Limits:**
  - **3 active projects**.
- **Features:**
  - Standard Trace Index.
  - Context Freshness (Real-time watcher).
- **Purpose:** Freelancers, single-project devs, "getting addicted".

### Pro License (Perpetual Ownership)
- **Price:** **$79** (One-time payment).
- **Model:** Perpetual fallback. Includes 1 year of updates.
  - After 1 year: Keep the last version forever, or renew for **~$30/year** for updates.
- **Features:**
  - **Unlimited projects**.
  - **Trace Index** (Structural Intelligence / Call Graphs).
  - **Full MCP Suite** (including advanced context assembly).
  - **Multi-Repo Agent** capabilities.
  - Priority local indexing.
- **Launch Strategy:** **"Founder’s Edition"** license at **$49** for the first 500 users.

## 2. The "Team" Model: Seat-Based Subscription
Target: Engineering teams (5–50) needing "Indexed Harmony."

### Team Tier
- **Price:** **$12–$15** per seat / month (Billed annually).
- **Value Proposition:**
  - **Shared Index Config:** Export/import `.codrag` configs (standardized ignore rules, scoping).
  - **Centralized Policy:** Admin-defined rules (e.g., "Never index /secrets").
  - **License Management:** Seat assignment/revocation.
  - **Support:** Priority email support.

## 3. The "Enterprise" Model: Security & Compliance
Target: Regulated industries (Banking, Defense) requiring air-gapped/governed usage.

### Enterprise Tier
- **Price:** Custom (Typically **$30+** per seat / month).
- **Value Proposition:**
  - **Air-gapped Support:** specialized builds for offline/restricted environments.
  - **SSO/SCIM:** Okta/Azure AD integration.
  - **Audit Logs:** Compliance tracking for indexing and search.
  - **SLA:** Dedicated support response times.

## Value Metrics (Feature Gating)

| Feature | Free | Starter | Pro | Team | Enterprise |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Project Limit** | 3 Repos | 3 Repos | Unlimited | Unlimited | Unlimited |
| **Indexing** | Full (Real-time) | Full (Real-time) | Full (Real-time) | Shared Configs | Governed Policy |
| **MCP Tools** | Full Suite | Full Suite | Full Suite | Full Suite | Full Suite |
| **Deployment** | Local | Local | Local | Local + Config Sync | Air-gapped / Managed |
| **Support** | Community | Community | Email | Priority | SLA |

## Marketing Positioning
- **"No Token Markup":** Explicitly market against cloud AI tools that mark up inference costs. CoDRAG is a "BYOK engine" that runs at cost.
- **"Your Code Stays Local":** The perpetual license reinforces the privacy narrative.

## Roadmap Implications
1.  **MVP Feature Gating:** The "Trace Index" (Phase 3) must be designed as a toggleable/gated feature.
2.  **License Engine:** We need a robust offline-friendly license validation system (Phase 11).
3.  **Config Sharing:** "Export Team Config" becomes a key Phase 06 (Team) deliverable.

---

**Legal Entity:** Magnetic Anomaly LLC  
**Copyright:** © 2025 Magnetic Anomaly LLC. All rights reserved.
