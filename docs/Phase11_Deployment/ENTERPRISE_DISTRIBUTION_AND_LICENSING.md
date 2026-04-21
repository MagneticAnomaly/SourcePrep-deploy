# Enterprise Distribution and Licensing

## Purpose
Plan early for an enterprise tier (per-seat licensing) without forcing Prep into a cloud dependency.

This doc is intentionally scoped to:
- distribution patterns enterprise IT expects
- licensing constraints (offline, air-gapped, procurement)

## Enterprise distribution patterns

### 1) Direct installer + internal rollout
Common enterprise expectation:
- signed installers
- IT-controlled rollout mechanisms

Prep implications:
- signing is non-negotiable
- stable data directory and upgrade behavior are required

### 2) Private/internal app catalog
Some orgs prefer distributing apps via an internal catalog rather than public app stores.

Prep implications:
- release artifacts must be easily mirrorable
- updates must be controllable (disable auto-update, or point to internal feed)

### 3) Central server mode (team server)
For enterprise, “local-first” does not preclude a self-hosted internal server.

Prep constraints:
- network mode must be safe-by-default and require auth when binding to non-loopback.

Reference:
- `docs/Phase06_Team_And_Enterprise/README.md`

## Licensing requirements (enterprise reality)

### Offline / restricted-network support
Enterprises may be:
- air-gapped
- outbound-restricted
- proxy-only

Therefore:
- licensing must have an offline-capable mode.

### Procurement expectations
Enterprise tiers often require:
- invoice/PO billing
- seat management

Competitor signals:
- Cursor Enterprise includes invoice/PO billing and SCIM seat management.
  - https://cursor.com/pricing
- Docker Business includes “Purchase via invoice”.
  - https://www.docker.com/pricing/

## License management shapes (roadmap)

### Primary Strategy: Offline License Keys (Option A)
This is the default for Prep Enterprise.
- **Format:** Signed JSON payload (Ed25519).
- **Delivery:** File-based (`license.key`) distributed via MDM or manual entry.
- **Validation:** Completely local/offline. No "phone home".

Pros:
- **True Air-gapped Support:** Zero network requirement.
- **Simplicity:** No license server to maintain for the customer.

Cons:
- **Revocation:** Harder to revoke keys without an update (but acceptable for perpetual model).

### Option B: Self-hosted license server (Post-MVP)
Only if customers demand centralized seat counting enforcement.
- Comparable to GitKraken on-prem.

### Deprecated Options
- **Cloud license service:** Incompatible with our "Local-First" trust promise for Enterprise.
- **Serverless true-up:** Too loose for some compliance depts.

## App stores vs enterprise licensing
App stores typically provide their own purchase/licensing mechanisms for public distribution.
Enterprise contracts often require:
- separate licensing
- offline validation
- custom terms

Practical implication:
- **Enterprise distribution will be Direct Download (MSI/DMG) + License Key.**
- App Store builds will likely be "Pro" via In-App Purchase (IAP) or separate SKUs.

## Recommended roadmap posture
- MVP:
  - Implement **Offline License Key** verification (Ed25519).
  - Ship signed installers.
- Enterprise roadmap:
  - Add **Audit Logging** (local file or syslog integration).
  - Add **Shared Configuration** support (Team Tier).
  - Design hooks for future SSO (post-MVP).

## Open questions
- Does enterprise demand require a managed hosted offering? **Current assumption: No, Self-Hosted/Local is the differentiator.**

