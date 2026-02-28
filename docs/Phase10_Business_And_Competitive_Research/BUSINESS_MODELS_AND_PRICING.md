# Business Models and Pricing

## Purpose
This document summarizes business model patterns relevant to CoDRAG’s goals:
- Self-contained local-first companion app
- App-store + direct-download distribution (macOS/Windows)
- Enterprise tier roadmap with per-seat licensing

It is intentionally **decision-oriented** (what should CoDRAG do next), not a generic market report.

## Comparable business model patterns

### Pattern A: Free core app + paid optional services (local-first)
Example: Obsidian
- Core app is free.
- Monetization is via optional services like Sync.

Source:
- https://obsidian.md/pricing

### Pattern B: Free personal use + paid org use (trust + admin controls)
Example: Docker Desktop
- Personal tier is free.
- Paid tiers introduce org features (SSO/SCIM, admin controls, invoice purchasing).

Source:
- https://www.docker.com/pricing/

### Pattern C: Per-seat assistant with clear “Business” and “Enterprise” differentiation
Examples:
- GitHub Copilot
- Cursor
- Windsurf

Signals:
- Individuals pay ~$10–$20/mo.
- Team tiers frequently move to $30–$40/user/mo.
- Enterprise pricing is higher ($39/user/mo and up) or custom.

Sources:
- https://github.com/features/copilot/plans
- https://docs.github.com/en/copilot/concepts/billing/organizations-and-enterprises
- https://cursor.com/pricing
- https://windsurf.com/pricing

### Pattern D: “Local-first memory” with a Pro tier
Example: Pieces for Developers
- Free tier exists.
- Pro tier monetizes access to premium capabilities.

Source:
- https://pieces.app/features

### Pattern E: Enterprise deploy-anywhere posture (BYOK/on-prem) with per-seat enterprise pricing
Example: Tabnine
- Pro and Enterprise tiers are explicitly positioned around privacy and deployment flexibility.

Source:
- https://www.tabnine.com/blog/key-takeaways-and-tabnine-faqs-from-nvidia-gtc/

### Pattern F: On-prem or “serverless” enterprise license management
Example: GitKraken on-prem pricing
- Options for self-hosted license server (LDAP) or serverless license management.

Source:
- https://www.gitkraken.com/git-client/on-premise-pricing

## Pricing sanity check (market snapshot)
These are not “correct” prices; they are anchors to avoid pricing in a vacuum.

- Individual:
  - GitHub Copilot Pro: $10/mo
    - https://github.com/features/copilot/plans
  - Windsurf Pro: $15/mo
    - https://windsurf.com/pricing
  - Cursor Pro: $20/mo
    - https://cursor.com/pricing
  - Pieces Pro: $18.99/mo (+ taxes)
    - https://pieces.app/features
- Team:
  - Cursor Teams: $40/user/mo
    - https://cursor.com/pricing
  - Windsurf Teams: $30/user/mo (as shown)
    - https://windsurf.com/pricing
  - Copilot Business: $19/user/mo
    - https://docs.github.com/en/copilot/concepts/billing/organizations-and-enterprises
- Enterprise anchors:
  - Copilot Enterprise: $39/user/mo
    - https://docs.github.com/en/copilot/concepts/billing/organizations-and-enterprises
  - Gemini Code Assist Enterprise: $45/user/mo (promo $19/user/mo on 1-year until Mar 31, 2025)
    - https://cloud.google.com/blog/products/application-development/introducing-gemini-code-assist-enterprise
  - Sourcegraph pricing page shows $49/user/monthy (as shown)
    - https://sourcegraph.com/pricing

## Decision: The "License-First" Model

We have selected a **Perpetual License** model for individuals and a **Seat-Based Subscription** for teams.

**Rationale:**
- Aligns with "Local-First" ethos (ownership vs rent).
- Low COGS (BYOK) allows avoiding the "AI Subscription" trap.
- Creates trust with privacy-conscious developers.

**The Strategy (The "Context Drug" Ladder):**
- **Free:** 1 project, manual builds only (The Hook).
- **Pro — monthly:** $7/mo, unlimited projects, full automation (The Bridge).
- **Pro — one-time:** $79, all Pro features, never expires (Ownership).
- **Team:** $15/seat/mo, headless CI/CD indexing, shared trace graph (Standardization).
- **Enterprise:** Custom pricing, air-gapped deployment, SSO/SCIM, audit logging.

See the detailed strategy in: [Pricing/PRICING_STRATEGY.md](Pricing/PRICING_STRATEGY.md)

> **Note (Feb 2026):** The "Starter" tier ($29/4-month pass) was removed. Monthly and Perpetual are
> both "Pro" — feature-identical, differing only in billing model.

## Decision outputs
- **Adoption funnel:** Free (1 project) → Pro Monthly ($7/mo) → Pro Perpetual ($79) → Team ($15/seat/mo).
- **Packaging:**
    - **Free:** 1 active project, manual builds.
    - **Pro (Monthly / Perpetual):** Unlimited projects, full automation, full MCP, trace-aware context.
    - **Team:** Everything in Pro + headless CI/CD indexer, shared trace graph via S3, delta sync.
    - **Enterprise:** Everything in Team + air-gapped deployment, SSO/SCIM, audit logging.
- **Cloud requirement:** None for Pro. Team uses S3-compatible storage for shared indexes (Cloudflare R2, AWS S3, MinIO).

