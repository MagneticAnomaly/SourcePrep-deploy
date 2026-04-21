# Local-First in Enterprise Ecosystems

## Purpose
This document defines what **“local-first”** should mean for Prep in real organizations, and what enterprise environments will require.

It is meant to guide:
- product boundaries (what Prep will and won’t do)
- security defaults (avoid foot-guns)
- the enterprise roadmap (Phase 06 and beyond)

## Definition: “local-first” for Prep
Local-first for Prep should mean:
- Prep can operate without any cloud service.
- The default operating mode keeps source code, indexes, and query history **on the user’s machine**.
- Network access is an explicit opt-in (team server mode), and is safe-by-default.

What “local-first” does **not** mean:
- “No networking ever.” It means networking is optional and under customer control.
- “No enterprise features.” It means enterprise features should not require external SaaS.

## Why this matters (market signals)
Enterprise messaging across AI dev tools consistently emphasizes:
- privacy and non-training on customer code
- governance and admin controls
- identity (SSO) and provisioning (SCIM)
- auditability

Examples:
- Cursor Enterprise lists audit logs, SCIM seat management, and granular admin/model controls.
  - https://cursor.com/pricing
- GitHub Copilot Business/Enterprise is framed around license management, policy management, and IP indemnity.
  - https://github.com/features/copilot/plans
  - https://docs.github.com/en/copilot/concepts/billing/organizations-and-enterprises
- Docker Business includes SSO and SCIM user provisioning.
  - https://www.docker.com/pricing/
- Tabnine highlights zero code retention and the ability to deploy on-prem behind a firewall.
  - https://www.tabnine.com/blog/key-takeaways-and-tabnine-faqs-from-nvidia-gtc/
- Gemini Code Assist Enterprise messaging includes “does not train on your organization’s private data” and the ability to purge.
  - https://cloud.google.com/blog/products/application-development/introducing-gemini-code-assist-enterprise

Prep should treat these expectations as constraints (even if not all are MVP features).

## Enterprise environments Prep must work in (roadmap)
- Developer laptops with strict endpoint security.
- Regulated orgs where source code cannot leave device/network.
- Air-gapped / offline networks.
- Corporate networks with outbound filtering and TLS inspection.

## Prep operating modes (and enterprise fit)

### Mode A: Local-only (default)
- Backend binds to loopback.
- No remote access.
- No cloud required.

Enterprise benefit:
- Easiest security posture to approve.

Enterprise friction:
- Harder to roll out / manage at scale (updates, licensing, policy).

### Mode B: Embedded index (team portability)
- `.prep/` inside the repo.
- Optional commit of index artifacts.

Enterprise benefit:
- Repeatable onboarding without needing a central server.

Enterprise friction:
- Repo bloat and merge conflicts if indexes are committed.

### Mode C: Network mode (team server)
- A shared daemon accessible to other machines.
- Must require authentication when binding to non-loopback (see Phase 06).

Enterprise benefit:
- Centralized indexing and easier onboarding.

Enterprise friction:
- Now the daemon is an internal service that must be secured, monitored, and upgraded.

## Security and governance requirements (roadmap anchors)

### 1) Safe defaults
- Default bind: loopback only.
- Remote bind requires explicit opt-in.
- Remote bind must require auth (Phase 06).

### 2) Data handling and privacy posture
Prep should be able to credibly state:
- No mandatory telemetry.
- No sending customer code off-device by default.

If Prep ever offers optional cloud:
- it must be opt-in
- it must be clear what is uploaded and why

Market expectation examples (privacy posture):
- Tabnine: “zero code retention” and on-prem option.
  - https://www.tabnine.com/blog/key-takeaways-and-tabnine-faqs-from-nvidia-gtc/
- Gemini Code Assist: “does not train… using your organization’s private data” and purge controls.
  - https://cloud.google.com/blog/products/application-development/introducing-gemini-code-assist-enterprise

### 3) Identity and provisioning (Enterprise tier)
Expected enterprise checklist (post-MVP):
- SSO (SAML/OIDC)
- SCIM provisioning
- admin controls over model usage / policy

Signals:
- Cursor Teams/Enterprise includes SAML/OIDC SSO and SCIM.
  - https://cursor.com/pricing
- Docker Business includes SSO and SCIM.
  - https://www.docker.com/pricing/

### 4) Auditability
Expected enterprise checklist (post-MVP):
- audit logs (who accessed what)
- ability to export logs

Signals:
- Cursor Enterprise includes “AI code tracking API and audit logs”.
  - https://cursor.com/pricing

### 5) BYOK and on-prem model options
To stay compatible with strict environments, enterprise customers will often expect:
- ability to use local models (Ollama or equivalent)
- BYOK for hosted model providers (customer’s own contracts)

Signals:
- Continue explicitly lists BYOK in its “Company” tier.
  - https://www.continue.dev/pricing

### 6) Offline Licensing (Perpetual/Term)
Enterprise environments often cannot "phone home" to validate subscriptions.
- **Requirement:** Cryptographically signed offline license keys.
- **Benefit:** Fits air-gapped deployments perfectly.

## Cloud option decision framework
Prep should assume “no cloud required” as the default.

If cloud is added, it should be because it unlocks a clear value that local-first cannot provide.

### Possible cloud “shapes” (in increasing complexity)
1. Licensing-only service
2. Encrypted backup/sync of indexes
3. Managed team server (hosted network mode)

### Decision criteria
Add cloud only if:
- enterprise procurement requires it (or significantly benefits from it)
- the feature cannot be delivered as self-hosted software
- it does not become a mandatory dependency

### Risks
- Operational burden for a solo developer
- Security and compliance scope explosion
- Violating local-first trust if the boundary is unclear

## Product implications (what to bake in early)
Even if enterprise is post-MVP implementation, MVP design should assume:
- stable on-disk formats and versioning (embedded mode viability)
- safe network-mode defaults and auth hooks
- data directory conventions and upgrade safety

## Open questions
- What is the minimum viable “enterprise posture” statement for MVP?
- Does Prep need any cloud for licensing at launch, or can licensing be offline-first?
- What is the minimal audit log surface (MVP vs enterprise)?
