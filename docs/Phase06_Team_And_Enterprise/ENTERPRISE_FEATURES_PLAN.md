# Enterprise Features — Comprehensive Plan
*Created: March 9, 2026*
*Status: Research & Planning*

This document catalogs EVERY enterprise feature needed, what's built, what's missing, and the LemonSqueezy/licensing considerations. It's the authoritative checklist for the enterprise roadmap.

---

## SECTION 1: User & License Controls

### 1A. Current State (What Exists)

| Component | Status | Notes |
|-----------|--------|-------|
| `feature_gate.py` — tier gating | ✅ Built | Reads `~/.runprep/license.json`, maps tier → features |
| Ed25519 signature verification | ✅ Built | `licensing.py` has `verify_license_key()` |
| `expires_at` validation | ✅ Built | Downgrades to FREE when expired |
| `PREP_DEV_MODE` gating | ✅ Built | Requires `=1` alongside `PREP_TIER` |
| License UI in Settings | ✅ Built | Key input, activate/deactivate buttons |
| Dev tier override in Settings | ✅ Built | Developer tab dropdown |
| `signature_verified` field | ✅ Built | Displayed in license status |

### 1B. Missing: LemonSqueezy Integration (Critical for Launch)

These are the actual revenue-path items. Without these, we can't charge money.

| ID | Feature | Description | Depends On |
|----|---------|-------------|------------|
| **LS-INT-1** | `POST /license/activate` rewrite | Currently returns stubs. Must call LS API: `POST https://api.lemonsqueezy.com/v1/licenses/activate` with `license_key` + `instance_name`. Map `product_id` → tier. | Eric: LS-01 to LS-04 (create products) |
| **LS-INT-2** | Periodic re-validation | Every 7 days: `POST .../licenses/validate`. If valid → update `last_validated`. If invalid → downgrade to FREE. If network error → grace period (30 days). | LS-INT-1 |
| **LS-INT-3** | Offline grace period | If `last_validated` < 30 days old → trust cached tier. If > 30 days → FREE. App works fully offline for 30 days between checks. | LS-INT-2 |
| **LS-INT-4** | License recovery flow | `payments.runprep.io/recover` — enter email → LS API looks up orders → re-sends key. Currently a mock stub. | Eric: LS-06 webhook |
| **LS-INT-5** | Deactivation | `POST .../licenses/deactivate` — when user clicks "Deactivate" in Settings. Frees up an activation slot. | LS-INT-1 |
| **LS-INT-6** | `api.runprep.io` relay service | Serverless function that: receives LS webhook → generates Ed25519 signed license → stores in DB. Handles `/activate` exchange (LS key → signed license file). | Eric: LS-06, Ed25519 keypair |
| **LS-INT-7** | Ed25519 keypair generation | Generate signing keypair. Private key in HSM/secure vault. Public key shipped in app binary. | Eric: manual task |
| **LS-INT-8** | Activation limits per product | Monthly: 3 machines. Perpetual: 5 machines. Team: 1 per seat. Configured in LS product settings. | Eric: LS product setup |

### 1C. Missing: Seat Management (Team/Enterprise)

| ID | Feature | Description |
|----|---------|-------------|
| **SEAT-1** | Seat count tracking | Track active seats per team license. LS handles this via activation limits, but we need UI visibility. |
| **SEAT-2** | Seat management UI | Admin panel: see which machines are activated, deactivate individual seats remotely. |
| **SEAT-3** | Seat overflow handling | When all seats are used: show "Contact your admin" or "Purchase additional seats" message. |
| **SEAT-4** | Admin seat provisioning | Team admin can generate per-user license keys from the admin dashboard (or via LS portal). |
| **SEAT-5** | Onboarding flow | New team member: receives license key via email → enters in Prep → activates against team's seat pool. |
| **SEAT-6** | Offboarding flow | When employee leaves: admin deactivates their seat in LS → next validation check downgrades them to FREE. |

### 1D. LemonSqueezy-Specific Considerations

**Things that affect our architecture:**

1. **LS activation limits are per-product, not per-license.** A Team product with 10 seats means the license key can be activated on 10 machines total. Each `POST /activate` consumes a slot.

2. **LS doesn't have "roles".** There's no concept of admin vs user in LS. We need to implement role assignment ourselves — likely via the `admin_policy` section in `team_config.json` or a separate `roles` config.

3. **LS subscription cancellation = key becomes invalid on next billing cycle.** The `validate` endpoint returns `valid: false` after expiry. Our grace period logic handles this gracefully.

4. **LS webhook events we need to handle:**
   - `order_created` — Generate Ed25519 license, store in DB
   - `subscription_updated` — Tier changes (upgrade/downgrade)
   - `subscription_cancelled` — Mark license for expiry
   - `subscription_payment_failed` — Grace period, then downgrade
   - `license_key_created` — For team seat provisioning

5. **PPP discount codes** (PPP20, PPP40, PPP60) are LS coupon codes applied at checkout. The license file is identical regardless of price paid — no tier difference.

6. **Enterprise = custom invoicing.** May bypass LS entirely for large enterprise deals. Need to support both LS-generated and manually-generated licenses.

---

## SECTION 2: AI Gateway Access Controls (Versatile)

### The Key Insight

IT admins need fine-grained control but **must not break the developer experience**. Common real-world scenarios:

| Scenario | What IT Wants | What Devs Need |
|----------|--------------|-----------------|
| **Cloud-only shop** | Only Google Gemini allowed | Use the IT-provided endpoint + key |
| **Security-conscious** | No cloud LLMs, local only | Run Ollama/LM Studio with any model |
| **Hybrid** | Cloud for fast tasks, local for code analysis | Both providers available, IT-approved cloud key |
| **BYOK-friendly** | Allow users to add their own OpenAI keys | Users can add endpoints but IT can block specific providers |
| **Locked down** | Only IT-configured endpoints, no user changes | Users see read-only locked endpoints, can't add/edit |
| **Model-restricted** | Allow local but only approved models | `allowed_models` list, users can still pick within it |

### 2A. What's Built

- ✅ `AdminPolicy.provider.allowed_providers` — hide providers from dropdown
- ✅ `AdminPolicy.provider.blocked_providers` — explicit blocklist
- ✅ `AdminPolicy.provider.allow_local_providers` — escape hatch for Ollama/LM Studio
- ✅ `AdminPolicy.provider.allow_user_endpoints` — gate on Add Endpoint button
- ✅ `AdminPolicy.provider.locked_endpoints` — IT-configured, non-editable endpoints
- ✅ `AdminPolicy.model.allowed_models` / `blocked_models` — model filtering
- ✅ `AdminPolicy.model.require_approved_models` — strict vs suggestion mode
- ✅ `AdminPolicy.enforcement_mode` — `suggest` (log but allow) vs `enforce` (block)
- ✅ Provider filtering in EndpointManager UI
- ✅ Locked endpoints display in EndpointManager
- ✅ Policy tab in EnterpriseAdminPanel with orange AdminSection borders

### 2B. What's Missing

| ID | Feature | Description | Priority |
|----|---------|-------------|----------|
| **GW-1** | Per-user model overrides | An admin locks endpoints but allows users to pick ANY local model from Ollama (not just from allowlist). Need a `allow_any_local_model: true` flag. | High |
| **GW-2** | API key injection | IT pre-configures cloud API keys so users don't need to manage secrets. Keys are masked in UI ("•••••sk-1234"). | High |
| **GW-3** | Per-slot policy | Different restrictions per slot: e.g., "Fast model must be local, Thinking model can be cloud". Currently policy applies globally. | Medium |
| **GW-4** | Cost limit per user | Individual user budget caps (not just team-wide). E.g., "Each dev gets 100K tokens/month". | Medium |
| **GW-5** | Approval workflow | User requests access to a blocked model → admin approves/denies. | Low (Enterprise) |
| **GW-6** | Policy push (centralized) | Admin changes policy in dashboard → pushed to all team clients via team_config.json sync. Already works via S3 sync for Team tier. | Built (via Team Sync) |
| **GW-7** | Policy audit trail | Log when admin changes policy settings (who changed what, when). Uses existing audit_log.py. | Medium |
| **GW-8** | Read-only AI Gateway for non-admins | Non-admin users see the AI Gateway but can't modify IT-locked settings. Currently the entire panel is visible to all. | High |

### 2C. Recommended `team_config.json` Example (Versatile)

```json
{
  "admin_policy": {
    "enforcement_mode": "enforce",
    "provider": {
      "allowed_providers": ["google", "ollama", "lm-studio"],
      "allow_local_providers": true,
      "allow_user_endpoints": true,
      "locked_endpoints": [
        {
          "name": "Corp Gemini",
          "provider": "google",
          "url": "https://generativelanguage.googleapis.com",
          "api_key_env": "GOOGLE_API_KEY"
        }
      ]
    },
    "model": {
      "allowed_models": ["gemini-2.5-flash", "gemini-2.5-pro", "qwen3"],
      "blocked_models": [],
      "require_approved_models": false
    },
    "data": {
      "never_send_globs": ["*.pem", "*.key", ".env*", "secrets/**"],
      "redact_patterns": ["sk-[a-zA-Z0-9]{20,}", "ghp_[a-zA-Z0-9]{36}"],
      "block_unapproved_cloud": true,
      "allowed_destinations": ["google"]
    },
    "budgets": {
      "monthly_token_limit": 5000000,
      "monthly_cost_limit_usd": 100.00,
      "alert_threshold_percent": 0.8
    }
  }
}
```

This says: "Devs can use Google Gemini (IT-provided key) or any local model via Ollama/LM Studio. They can add their own local endpoints. Cloud data only goes to Google. Sensitive files are never sent. $100/month budget cap."

---

## SECTION 3: Additional Enterprise Features (Research)

### 3A. Authentication & Identity

| ID | Feature | Status | Notes |
|----|---------|--------|-------|
| **AUTH-1** | SSO/SAML | ❌ Not built | Enterprise expectation. Needed for: single sign-on, automatic seat provisioning. Requires `api.runprep.io` integration. |
| **AUTH-2** | SCIM provisioning | ❌ Not built | Auto-create/delete seats when employees join/leave in Okta/Azure AD. |
| **AUTH-3** | Role-based access (RBAC) | ⚠️ Partial | Currently only `user` / `admin`. Enterprise needs: `viewer`, `developer`, `admin`, `super-admin`. |
| **AUTH-4** | Multi-org support | ❌ Not built | Single license can manage multiple teams/departments. |

### 3B. Compliance & Audit

| ID | Feature | Status | Notes |
|----|---------|--------|-------|
| **COMP-1** | SOC 2 Type II readiness | ❌ Not done | Enterprise procurement requirement. Mostly policy/process docs, but audit_log.py is the technical foundation. |
| **COMP-2** | GDPR data export | ❌ Not built | "Download my data" endpoint for user PII. Prep stores very little PII (email in license). |
| **COMP-3** | Data residency controls | ❌ Not built | "Index data must stay in EU" — relevant for Team Sync S3 regions. |
| **COMP-4** | Immutable audit log export | ✅ Built | `audit_log.py` with `export_csv()` and API endpoint. |
| **COMP-5** | Security health dashboard | ✅ Built | 7-check security health + Security tab in admin panel. |
| **COMP-6** | Penetration test readiness | ❌ Not done | Enterprise procurement may require pen test report. |

### 3C. Deployment & Management

| ID | Feature | Status | Notes |
|----|---------|--------|-------|
| **DEPLOY-1** | MDM distribution | ❌ Not done | Enterprise distributes via Jamf/Intune. Needs MSI/DMG with silent install flags. |
| **DEPLOY-2** | Pre-configured install | ❌ Not built | Ship Prep with `team_config.json` baked into the installer so devs don't need to configure anything. |
| **DEPLOY-3** | Centralized config push | ⚠️ Partial | team_config.json syncs via S3 (Team Sync). But no real-time push — poll-based. |
| **DEPLOY-4** | Version pinning | ❌ Not built | IT can mandate a specific Prep version. Block auto-update until IT approves the new version. |
| **DEPLOY-5** | Telemetry opt-out/opt-in | ✅ Built | No telemetry by default. Verbose Telemetry is local-only (stdout). |

### 3D. Advanced AI Gateway Features

| ID | Feature | Status | Notes |
|----|---------|--------|-------|
| **ADV-1** | Model recommendation engine | ❌ Not built | "Based on your VRAM, we recommend qwen3:8b" — could use GPU detection. |
| **ADV-2** | Cost estimation per pipeline run | ⚠️ Partial | `cost_estimation.py` exists but not wired to UI. |
| **ADV-3** | API key rotation | ❌ Not built | Admin can rotate cloud API keys without disrupting users. |
| **ADV-4** | Failover / fallback chains | ❌ Not built | "If Google is down, fall back to local Ollama". |
| **ADV-5** | Rate limit management | ✅ Built | MCP rate limiting (120/60s). Cloud 429 detection in llm_client. |
| **ADV-6** | Token budget alerts | ⚠️ Partial | budget_enforcement.py exists. No UI alerts yet. |
| **ADV-7** | Multi-tenant isolation | ❌ Not built | Different teams on same machine share nothing. Currently single-tenant. |

---

## SECTION 4: Priority Matrix

### Tier 1 — Revenue Path (Must Have for Launch)
1. **LS-INT-1** through **LS-INT-6**: LemonSqueezy activation exchange
2. **LS-INT-7**: Ed25519 keypair (Eric manual task)
3. **GW-8**: Read-only AI Gateway for non-admin users

### Tier 2 — Enterprise Sales (Must Have for First Enterprise Customer)
4. **SEAT-1** through **SEAT-6**: Seat management
5. **GW-1**: Per-user local model override
6. **GW-2**: IT-managed API key injection
7. **AUTH-3**: Expanded RBAC (viewer/developer/admin)
8. **COMP-1**: SOC 2 readiness documentation
9. **GW-7**: Policy change audit trail

### Tier 3 — Enterprise Maturity (6-12 Month Roadmap)
10. **AUTH-1**: SSO/SAML
11. **AUTH-2**: SCIM provisioning
12. **COMP-3**: Data residency controls
13. **GW-3**: Per-slot policy
14. **GW-4**: Per-user cost limits
15. **DEPLOY-1**: MDM distribution
16. **DEPLOY-2**: Pre-configured installer
17. **ADV-4**: Failover chains
18. **ADV-3**: API key rotation

### Tier 4 — Enterprise Excellence (12+ Month)
19. **GW-5**: Approval workflow
20. **AUTH-4**: Multi-org support
21. **ADV-7**: Multi-tenant isolation
22. **COMP-2**: GDPR data export
23. **COMP-6**: Pen test readiness

---

## SECTION 5: LemonSqueezy Architecture Decision

### The Two Approaches (Choose One)

**Approach A: LS-Only License Validation (Simpler)**
- App calls LS API directly for activate/validate
- No `api.runprep.io` needed
- LS is the source of truth
- Downside: requires internet every 30 days, no custom fields in license

**Approach B: LS + api.runprep.io Relay (More Control)**
- LS webhook → api.runprep.io → generates Ed25519 signed license
- App activates via api.runprep.io, then works offline forever
- Custom fields in license (features list, seat assignments, admin role)
- Downside: need to build and host api.runprep.io

**Current plan (from SECURITY_DESIGN_DECISIONS.md): Approach A for MVP, Approach B for enterprise.**

The DISTRIBUTION_AND_REVENUE_PLAN.md shows Approach B in the activation flow diagram. The two docs slightly conflict — SECURITY_DESIGN_DECISIONS.md recommends LS-only (Approach A), while DISTRIBUTION_AND_REVENUE_PLAN.md shows the full Ed25519 relay (Approach B).

**Recommendation:** Start with **Approach A** (LS direct validation). It's simpler, faster to ship, and covers Free/Monthly/Perpetual. Add **Approach B** (Ed25519 relay) when the first enterprise customer needs air-gapped/offline-forever licenses.

---

## SECTION 6: Implementation Sequence

```
Phase 1 (Launch MVP):
  ├── LS-INT-1: Rewrite /license/activate to call LS API
  ├── LS-INT-2: Periodic validation (7-day check)
  ├── LS-INT-3: 30-day offline grace period
  ├── LS-INT-5: Deactivation
  └── GW-8: Read-only AI Gateway for non-admins

Phase 2 (Post-Launch, Pre-Enterprise):
  ├── LS-INT-4: License recovery flow
  ├── LS-INT-8: Activation limits
  ├── SEAT-1/2: Seat count tracking + UI
  ├── GW-1: Per-user local model override
  └── GW-2: IT API key injection

Phase 3 (Enterprise):
  ├── LS-INT-6: api.runprep.io relay (Ed25519 offline licenses)
  ├── LS-INT-7: Ed25519 keypair (Eric)
  ├── SEAT-3-6: Full seat lifecycle
  ├── AUTH-3: Expanded RBAC
  ├── GW-7: Policy audit trail
  └── COMP-1: SOC 2 docs
```
