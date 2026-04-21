# Licensing Implementation Specification

> **⚠️ PARTIALLY SUPERSEDED** — The activation flow (§ "Activation Flow") references
> **Stripe** webhooks. The authoritative plan now uses **Lemon Squeezy** as Merchant of
> Record. See [`docs/DISTRIBUTION_AND_REVENUE_PLAN.md`](../DISTRIBUTION_AND_REVENUE_PLAN.md)
> for the current payment and activation flow. The **license format, validation logic,
> and feature gating** sections below remain accurate.

## Purpose
This document defines the technical implementation for CoDRAG's licensing system, ensuring it supports:
-   **Offline-first validation** (no mandatory phone home).
-   **Perpetual fallback** (app keeps working after updates expire).
-   **Feature gating** (Free vs Pro vs Team).
-   **Tamper resistance** (cryptographically signed keys).

## License Key Format
We will use a **Signed JSON Payload** encoded in Base64 (similar to JWT but simpler/custom to avoid typical JWT exploit surfaces if desired, or standard JWT with EdDSA).

**Algorithm:** Ed25519 (EdDSA) for high security and small key size.
**Encoding:** Base64URL-safe.

### Payload Schema
```json
{
  "id": "uuid-v4",
  "issued_to": "email@example.com",
  "issued_at": 1735689600,  // Unix timestamp
  "updates_until": 1767225600, // Unix timestamp (1 year later for Pro)
  "expires_at": null, // Unix timestamp (OPTIONAL: Hard expiration for Starter passes)
  "tier": "pro", // "starter", "pro", "team", "enterprise"
  "seats": 1, // 1 for pro/starter, N for team
  "features": [
    "trace_index",
    "mcp_advanced"
  ],
  "meta": {
    "edition": "founder" // Optional marketing badge
  }
}
```

### The License String
`{header}.{payload}.{signature}`
*(Or simply `base64(json) + "." + base64(signature)` if we enforce one algo)*

## Validation Logic (Client-Side)

The CoDRAG desktop app (Tauri/Rust) and daemon (Python) will both contain the **Public Key**.

### 1. Integrity Check
-   Split string by `.`.
-   Decode payload and signature.
-   Verify signature against payload using the embedded **Ed25519 Public Key**.
-   **Failure:** `INVALID_LICENSE` (The key is fake or modified).

### 2. Expiration Check (Starter Tier / Term License)
-   **expires_at** (if present):
    -   If `current_date > expires_at`:
        -   **Result:** `LICENSE_EXPIRED`.
        -   **Action:** Revert to Free Tier limits. Show "Pass Expired" banner.

### 3. Entitlement Check (Updates)
-   **updates_until**:
    -   Compare with current date.
    -   If `current_date > updates_until` AND license is NOT expired:
        -   **App:** ALLOW launch (Perpetual fallback for Pro).
        -   **Updates:** DENY download of new versions released *after* this date.
        -   **UI:** Show "Updates Expired - Renew to get vNext".
-   **tier/features**:
    -   Enable gated modules (TraceManager, Advanced MCP).

### 4. Seat/Machine Check (Team/Enterprise only)
-   *Strict enforcement usually requires a license server.*
-   **Local-First Approach:**
    -   We trust the user for offline scenarios.
    -   For Team/Enterprise, we may bind the license to a `machine_id` if we implement activation (optional for MVP).
    -   **MVP Decision:** Honor the license file. Rely on legal enforcement for seat counts in Enterprise.

## Feature Gating Implementation

### Free Tier (Default state)
-   `ProjectRegistry`: Enforce `project_count <= 1`.
-   `TraceManager`: Disabled. Returns "Upgrade to Pro" error on `trace_build`.
-   `Dashboard`: Show "Pro" badges on locked features.

### Starter Tier (Term Pass)
-   `ProjectRegistry`: Enforce `project_count <= 3`.
-   `TraceManager`: Enabled (Standard).
-   `ContextFreshness`: Real-time watchers enabled.
-   **Expiration:** Reverts to Free Tier behavior when `expires_at` is reached.

### Enforcement points (by runtime mode)

- **Daemon / server mode (multi-project)**:
  - Project count limits are enforced by the daemon (authoritative) via `ProjectRegistry`.
  - HTTP API and MCP server-mode tooling MUST return consistent license error envelopes when limits are exceeded.
- **Direct MCP mode (single repo, no daemon)**:
  - Repo-count gating is not meaningful (Direct mode is scoped to the current working directory).
  - License enforcement in Direct mode is optional; recommended gating is feature-based (e.g., trace) rather than “repo count”.
- **Network / team server deployments (Phase 06)**:
  - Remote access and multi-client usage will require explicit authentication.
  - Seat enforcement is not strictly enforceable without an online license server; Enterprise posture relies on signed offline keys + legal enforcement.

### Pro Tier
-   `ProjectRegistry`: Unlimited.
-   `TraceManager`: Enabled.
-   `MCP`: Full access.

### Team Tier
-   **Shared Configs:** Import/Export `.prep/team_config.json` enabled.
-   **UI:** Show Organization Name (if present in license).

## Offline & Air-Gapped Support
-   The license check **NEVER** requires internet access.
-   Validation is purely mathematical (Signature verification).
-   Enterprise deployments receive a `license.key` file during rollout (e.g., via MDM to `%AppData%/CoDRAG/license.key`).

## Security Considerations
-   **Key Rotation:** If the private key is compromised, we must ship a new app version with a new public key. Old keys would become invalid (user friction). **Mitigation:** Use a highly secure, offline HSM for signing.
-   **Clock Tampering:** Users sets clock back to get updates. **Mitigation:** Check file mtimes or network time if available (soft check). Do not block app launch, just updates.
-   **Binary Patching:** Users patching the `verify_license()` function. **Mitigation:** Code signing (OS level) helps. Rust logic is harder to patch than JS. Accept that determined crackers will crack; optimize for honest customers.

## Activation Flow (Direct Sales)
1.  User buys on website (Stripe).
2.  Stripe Webhook -> CoDRAG License Service (Cloud).
3.  Service generates signed Key.
4.  Service emails Key to user.
5.  User pastes Key into App -> App validates & saves to disk.
