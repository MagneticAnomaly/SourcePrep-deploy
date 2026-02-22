# Team & Enterprise — Marketing and Communication Pack

## Purpose
Provide copy and framing that is:
- consistent with the product’s local-first architecture
- consistent with pricing tiers (Free/Pro/Team/Enterprise)
- consistent with **ADR-012** (enterprise implementation is post-MVP)

This is a Phase 06-specific pack; it feeds the Phase 12 website copy.

## Golden rules (do not break trust)
- Do not imply mandatory cloud.
- Do not imply SSO/SCIM/audit is shipping in MVP.
- Do not claim seat enforcement features that require a license server.
- Always say: **"No token markup"** (BYOK).

## Messaging: Team Tier (“Indexed Harmony”)

### One-liner
**Give your whole team the same context.** Shared scoping and indexing policy so results are reproducible across developers.

### Key benefits (bullets)
- Shared `.codrag/team_config.json` so everyone indexes the same code.
- Centralized policy defaults (ignore rules, trace defaults, embedding baseline).
- Drift detection: see when a developer’s local config diverges.

### What it is / what it isn’t
- It is:
  - a way to standardize how CoDRAG indexes your repos across people.
- It is not:
  - a hosted multi-tenant service
  - a requirement to upload code to a vendor cloud

### Pricing line
- **Team:** $15/seat/month (billed annually).

## Messaging: Enterprise Tier (“Local-first, deploy-anywhere”)

### One-liner
**Enterprise-grade local-first.** Signed installers, offline licensing, and a roadmap for governance in regulated environments.

### Key benefits (bullets)
- Air-gapped-friendly: offline license keys (no phone home).
- IT-controlled distribution: direct installers, internal catalogs.
- Roadmap governance: audit logging and identity integrations when needed.

### Explicit roadmap statement (must include)
- Network mode, auth, and admin surfaces are **post-MVP implementation**.
- SSO/SCIM is **not** an MVP feature.

## FAQ (Team/Enterprise)

### Does CoDRAG upload our code?
No. CoDRAG is local-first by default. Your indexes and code stay on your machine.

### Do you charge for tokens?
No. CoDRAG does not mark up inference costs. If you enable BYOK augmentation, you pay your provider directly.

### Is there a team server?
Network mode is planned as a post-MVP feature for teams that want centralized indexing.

### Can we run CoDRAG air-gapped?
Enterprise licensing is designed for offline validation using signed keys.

### Can we enforce “never index secrets”?
Team Tier supports a shared config baseline (`team_config.json`) and policy enforcement modes.

### Do you support SSO/SCIM?
Not in MVP. It is an enterprise roadmap item.

## Website copy inputs (Phase 12)

### Suggested `/team` page structure
- Hero: "Indexed Harmony"
- Section: Shared config + drift detection
- Section: Embedded mode onboarding (optional)
- CTA: "Talk to us" / "Get updates" (until post-MVP features ship)

### Suggested `/enterprise` page structure
- Hero: "Local-first, deploy-anywhere"
- Section: Offline licensing + signed installers
- Section: Roadmap governance (audit + SSO/SCIM)
- Clear "Roadmap" labeling to avoid overpromising

## Sales/procurement framing (lightweight)
- Legal entity: Magnetic Anomaly LLC
- Delivery: signed installers + offline license keys
- Data posture: local-first, BYOK, no mandatory telemetry
