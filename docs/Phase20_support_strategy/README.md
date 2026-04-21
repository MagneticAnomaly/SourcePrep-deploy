# Phase 20: Lean Support Strategy

## Goal
Provide professional, reliable support as a single-person team without burning out or creating false expectations of 24/7 SLA.

## Core Philosophy
1.  **Community First:** 90% of "support" should happen in public (GitHub Discussions). This builds knowledge base and allows users to help each other.
2.  **Docs as Product:** Documentation is the primary support agent. If a question is asked twice, it belongs in docs.
3.  **Single Private Inbox:** One email address (`support@runprep.io`) for all private matters (Billing, Enterprise, Security). No functional silos.

## Infrastructure Strategy
- **KEEP** `websites/apps/support` (standalone Next.js app) as `support.runprep.io`.
  - *Reasoning:* Provides a robust, scalable foundation for future support features (e.g., ticketing, auth) without bloating the marketing site.
  - *Implementation:* "Headless GitHub Portal" — uses GitHub Discussions as the backend CMS but controls the frontend experience.

## Communication Channels

| Channel | Purpose | Audience | Response Expectation |
| :--- | :--- | :--- | :--- |
| **GitHub Discussions** | "How do I...?", Setup help, Workflows | Free & Pro Users | Community driven + "Best Effort" from maintainer |
| **GitHub Issues** | Verified Bugs, Feature Requests | All Users | Triage within 48h, fix based on roadmap |
| **support@runprep.io** | Billing, Licensing, Enterprise, Security | Customers, Enterprise | < 24h response |

## Marketing Copy Adjustments
- **Remove** `licenses@`, `enterprise@`, `security@` from public view.
- **Consolidate** "Contact" page into two clear paths:
  1.  **Technical Help?** -> GitHub (Public)
  2.  **Account/Business?** -> Email (Private)

## Implementation Plan
1.  **Update Marketing Site (`/contact`):** Replace the 4-card grid with a 2-card split (Community vs. Private).
2.  **Update Support Links:** Point "Support" nav items to GitHub Discussions or the Contact page.
3.  **Retire Support App:** Delete `websites/apps/support` from the monorepo.
