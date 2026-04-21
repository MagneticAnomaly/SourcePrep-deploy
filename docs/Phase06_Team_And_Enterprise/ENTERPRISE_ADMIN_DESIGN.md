# Enterprise Admin — Dashboard Design & IT Policy Controls

*Status: Design & Planning*
*Created: Mar 9, 2026*
*Dependencies: Phase 06 (Team Sync), Phase 45 (Multi-GPU Concurrency)*
*References: `ENTERPRISE_POSTURE_AND_ROADMAP.md`, `COMPUTE_MANAGEMENT_FOUNDATIONS.md`, `B2B_HOSTING_AND_MODEL_STRATEGY.md`, `INSTITUTION_MODEL_ASSIGNMENTS.md`*

---

## 1. Executive Summary

Enterprise IT administrators need centralized control over how Prep connects to LLM providers, what models developers can use, and visibility into fleet utilization and costs. This document designs the **Enterprise Admin experience** across three panel areas:

1. **AI Gateway Policy** — Provider allowlists, locked endpoints, model restrictions
2. **Fleet & Compute Management** — Compute nodes, sync fleet, scheduling
3. **Usage & Monitoring** — Cost tracking, stress metrics, audit logs

All admin-level panels use an **orange accent border** (`border-warning` / `border-amber-500`) to visually distinguish organization-controlled settings from user-controlled settings.

---

## 2. Visual Design: Orange Admin Border

### Specification

Admin-gated panels and sections use a distinct visual treatment so that any user looking at the dashboard immediately understands "this is controlled by my IT department."

```
┌─ border-l-4 border-amber-500 ──────────────────────────┐
│  🛡️  AI Gateway Policy                    Admin Only    │
│  ─────────────────────────────────────────────────────  │
│  Allowed Providers: Google (Gemini), Anthropic          │
│  Locked Endpoints: [Vertex AI prod] [Claude Bedrock]    │
│  Model Allowlist:  gemini-2.5-*, claude-3.5-sonnet-*    │
└─────────────────────────────────────────────────────────┘
```

**CSS pattern:**
```tsx
// Admin-level card wrapper
<div className={cn(
  'rounded-lg border bg-surface p-6',
  isAdmin ? 'border-l-4 border-l-amber-500 border-border' : 'border-border'
)}>
  {isAdmin && (
    <div className="flex items-center gap-1.5 text-amber-500 text-xs font-medium mb-3">
      <Shield className="w-3.5 h-3.5" />
      Admin Only
    </div>
  )}
  {children}
</div>
```

Non-admin users see a read-only summary: "Your organization restricts available providers. Contact your admin to change these settings."

### Where Orange Borders Appear

| Location | What's gated |
|---|---|
| AI Gateway → Provider Policy | Which providers are visible in the dropdown |
| AI Gateway → Locked Endpoints | Pre-configured endpoints that users can't edit/delete |
| AI Gateway → Model Allowlist | Glob patterns restricting which models can be selected |
| Enterprise Admin → Compute Fleet | Shared compute node management |
| Enterprise Admin → Usage & Billing | Cost and utilization metrics |
| Settings → Audit Log (future) | Immutable event log |

---

## 3. Panel Architecture

### Current State

The dashboard has **one panel** for enterprise: `enterprise-admin` (registered in `panelRegistry.ts`). This panel contains compute fleet, sync fleet, and usage KPIs — all in one component (`EnterpriseAdminPanel.tsx`).

### Proposed Structure: 3 Sections in 1-2 Panels

Rather than splitting into many panels (which fragments the admin experience), we keep a **two-panel layout**:

#### Panel 1: "AI Gateway" (existing `llm-status` panel, enhanced)

Already exists for all users. For admin users on Team/Enterprise tiers, it gains an orange-bordered **policy section** at the top:

- **Provider Allowlist** — checkboxes to show/hide providers
- **Locked Endpoints** — pre-configured endpoints users can see but not modify
- **Model Allowlist/Blocklist** — glob patterns (e.g., `gemini-2.5-*`, `!*preview*`)
- **API Key Policy** — admin-injected keys (masked) vs. user-provided keys

This keeps all LLM configuration in one place. Users see their endpoints below the admin policy section.

#### Panel 2: "Enterprise Admin" (existing `enterprise-admin` panel, enhanced)

Stays gated to admin role + team/enterprise tier. Split into tabs or sections:

- **Tab 1: Fleet & Scheduling** — Compute nodes, scheduler status, queue depth
- **Tab 2: Sync Fleet** — Per-project sync status, manual trigger
- **Tab 3: Usage & Stress** — Cost tracking, token usage, indexing minutes, seat count, error rates

### Single Dashboard, Not Two

One dashboard is sufficient. The admin panels are **addable** via the Panel Picker like any other panel. Non-admins don't see them in the picker (or see them grayed out with a lock icon). This avoids the complexity of a separate admin dashboard while keeping the experience clean for regular users.

---

## 4. AI Gateway Policy — Provider Controls

### 4.1 Design Principle: Flexible, Not Restrictive

The AI Gateway must remain **user-accessible in all scenarios**. Enterprise policy adds guardrails on top — it does NOT replace the gateway. Common real-world scenarios:

| Scenario | Admin configures | Users can still |
|---|---|---|
| **Cloud-only shop** | Lock Google Vertex + Anthropic endpoints | Nothing local needed |
| **Hybrid (most common)** | Lock corporate Google endpoint + allow `ollama` + `lm-studio` | Add local Ollama, load qwen3 locally for offline dev |
| **Air-gapped** | Lock internal Ollama fleet endpoint | Add their own local LM Studio for experiments |
| **Fully open** | No restrictions (suggest mode) | Add any provider, any model |
| **Strict compliance** | Lock endpoints, block user additions, enforce model allowlist | Use only approved models on approved endpoints |

**Key insight:** Even strict enterprises often want developers to run local models (Ollama, LM Studio) for quick iteration and offline work. The `allow_local_providers` flag (default: `true`) ensures local providers are always available unless explicitly blocked.

### 4.2 Policy Schema

**Config** (in `team_config.json` or admin settings API):

```json
{
  "admin_policy": {
    "enforcement": "enforce",
    "provider_policy": {
      "allowed_providers": ["google", "anthropic", "ollama", "lm-studio"],
      "allow_local_providers": true,
      "allow_user_endpoints": true,
      "allow_user_api_keys": true
    },
    "locked_endpoints": [
      {
        "name": "Corporate Vertex AI",
        "provider": "google",
        "url": "https://us-central1-aiplatform.googleapis.com",
        "api_key_env": "PREP_GOOGLE_API_KEY",
        "locked": true,
        "required_for_tasks": ["deep_enrichment", "group_reasoning", "atlas"]
      },
      {
        "name": "Corporate Bedrock (Claude)",
        "provider": "openai-compatible",
        "url": "https://bedrock-runtime.us-east-1.amazonaws.com",
        "api_key_env": "PREP_AWS_API_KEY",
        "locked": true
      }
    ],
    "model_policy": {
      "allowlist": ["gemini-2.5-*", "claude-3.5-sonnet-*", "qwen3*", "llama*"],
      "blocklist": ["*preview*", "*experimental*"],
      "require_approved_for_cloud": true
    },
    "data_policy": {
      "allowed_data_destinations": ["google", "anthropic"],
      "block_code_to_unapproved_cloud": true,
      "allow_local_processing": true
    }
  }
}
```

### 4.3 Policy Fields Reference

| Field | Default | Effect |
|---|---|---|
| `enforcement` | `"suggest"` | `"suggest"` = recommendations, user can override. `"enforce"` = mandatory, non-compliant options hidden. |
| `allowed_providers` | `null` (all) | Which provider types appear in "Add Endpoint". `null` = no restriction. |
| `allow_local_providers` | `true` | **Even in enforce mode**, `ollama` and `lm-studio` remain available unless explicitly set to `false`. This ensures developers always have a local escape hatch. |
| `allow_user_endpoints` | `true` | If `false`, users cannot add their own endpoints — only locked endpoints available. |
| `allow_user_api_keys` | `true` | If `false`, API key field hidden. Keys come from env vars or admin config only. |
| `locked_endpoints` | `[]` | Pre-configured endpoints with 🔒 icon. Users cannot edit/delete/see API key. |
| `required_for_tasks` | `null` | If set on a locked endpoint, the specified pipeline tasks MUST use this endpoint (overrides user model assignments). |
| `model_policy.allowlist` | `null` (all) | Glob patterns. Only matching model names shown when browsing. |
| `model_policy.blocklist` | `[]` | Matching models hidden. Evaluated after allowlist. |
| `model_policy.require_approved_for_cloud` | `false` | If `true`, cloud endpoints only accept models matching the allowlist. Local endpoints are unrestricted (experiment freely). |
| `data_policy.block_code_to_unapproved_cloud` | `false` | If `true`, source code is only sent to providers in `allowed_data_destinations`. Prevents accidental data leakage to unapproved APIs. |
| `data_policy.allow_local_processing` | `true` | Local Ollama/LM Studio always allowed for processing. Only relevant for DLP auditing. |

### 4.4 Enforcement Modes in Detail

- **`suggest`** (default for Team tier) — Admin settings shown as recommendations with a subtle info banner: "Your organization recommends these settings." User can override everything. Policy violations are logged but not blocked.
- **`enforce`** (typical for Enterprise tier) — Mandatory. Non-compliant user endpoints grayed out. Provider dropdown filtered. Model selector filtered. Locked endpoint task assignments cannot be overridden. Violations are blocked + logged.

### 4.5 UI Implementation

In `EndpointManager.tsx`:

```tsx
// Local providers are always available unless explicitly blocked
const LOCAL_PROVIDERS = ['ollama', 'lm-studio'];

const visibleProviders = useMemo(() => {
  if (!adminPolicy?.provider_policy?.allowed_providers) return PROVIDER_OPTIONS;
  const allowed = new Set(adminPolicy.provider_policy.allowed_providers);
  // Always include local providers unless explicitly disabled
  if (adminPolicy.provider_policy.allow_local_providers !== false) {
    LOCAL_PROVIDERS.forEach(p => allowed.add(p));
  }
  return PROVIDER_OPTIONS.filter(o => allowed.has(o.value));
}, [adminPolicy]);

// Show locked endpoints with lock icon, non-editable
{lockedEndpoints.map(ep => (
  <LockedEndpointRow key={ep.name} endpoint={ep} />
))}

// Show "Add Endpoint" only if allow_user_endpoints is true
{adminPolicy?.provider_policy?.allow_user_endpoints !== false && (
  <AddEndpointForm providers={visibleProviders} />
)}
```

---

## 5. Provider Gap Analysis

### Currently Supported (First-Class)

| Provider | Type | Auth | Standard URL | Status |
|---|---|---|---|---|
| **Ollama** | Local | None | `http://localhost:11434` | ✅ Full |
| **LM Studio** | Local | None | `http://localhost:1234` | ✅ Full (native API) |
| **OpenAI** | Cloud | Bearer token | `https://api.openai.com/v1` | ✅ Full |
| **Anthropic** | Cloud | `x-api-key` header | `https://api.anthropic.com` | ✅ Full |
| **Google (Gemini)** | Cloud | API key in URL param | `https://generativelanguage.googleapis.com` | ✅ Full |
| **OpenAI Compatible** | Any | Bearer token | (user-provided) | ✅ Catch-all |

### Missing Enterprise Providers

#### AWS Bedrock — HIGH priority for enterprise

| Aspect | Detail |
|---|---|
| **What it is** | AWS's managed LLM service. Hosts Claude, Llama, Mistral, Cohere, Amazon Titan |
| **Why it matters** | How Fortune 500 companies consume Claude. Falls under existing AWS Enterprise Agreements, SOC2, HIPAA compliance |
| **Auth model** | SigV4 (AWS IAM). Not Bearer tokens. Requires `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`, `AWS_REGION` |
| **API format** | Custom REST API (`/model/{modelId}/converse`). NOT OpenAI-compatible |
| **Endpoint URL** | `https://bedrock-runtime.{region}.amazonaws.com` |
| **Implementation** | New provider type: `'aws-bedrock'`. Requires `boto3` or manual SigV4 signing. Moderate effort |
| **Enterprise context** | Many large customers already have Bedrock set up. They will ask "can Prep use our Bedrock Claude?" on day one |

#### Azure OpenAI — HIGH priority for enterprise

| Aspect | Detail |
|---|---|
| **What it is** | Microsoft's managed OpenAI service on Azure |
| **Why it matters** | Dominant in Microsoft shops. Same models as OpenAI but under Azure EA billing and compliance |
| **Auth model** | `api-key` header (NOT `Authorization: Bearer`). Different header name. Also supports Azure AD OAuth |
| **API format** | OpenAI-compatible BUT uses deployment names instead of model names in the URL path |
| **Endpoint URL** | `https://{resource-name}.openai.azure.com/openai/deployments/{deployment-name}` |
| **Implementation** | Could work through `openai-compatible` with URL adjustments, but the `api-key` header difference and deployment-name URL pattern will confuse users. Better as a dedicated provider type: `'azure-openai'` with fields for resource name and deployment name |
| **Enterprise context** | The #1 most likely provider for Microsoft-shop enterprises |

#### Other Providers (Lower Priority)

| Provider | How to Access Today | First-Class Needed? |
|---|---|---|
| **Groq** | Works via `openai-compatible` | No — standard OpenAI-compat API |
| **Fireworks AI** | Works via `openai-compatible` | No |
| **Together AI** | Works via `openai-compatible` | No |
| **OpenRouter** | Works via `openai-compatible` | No |
| **Mistral** | Works via `openai-compatible` | No |
| **xAI (Grok)** | Works via `openai-compatible` | No |
| **DeepSeek** | Works via `openai-compatible` | No |
| **Cohere** | Custom API format | Low priority — niche usage |
| **HuggingFace Inference** | Works via `openai-compatible` | No — already tested with Kimi-K2.5 |

### Provider Roadmap

```
Phase 1 (Now):       Ollama, LM Studio, OpenAI, Anthropic, Google, OpenAI-Compatible ✅
Phase 2 (Team v1):   + Azure OpenAI (dedicated provider type)
Phase 3 (Enterprise): + AWS Bedrock (SigV4 auth, boto3)
```

---

## 6. Standard IT Tooling — Enterprise Feature Matrix

Beyond LLM provider controls, enterprise buyers expect a standard set of IT governance features. This section inventories all standard enterprise tooling and maps it to Prep's architecture.

### 6.1 Identity & Access Control

| Feature | Description | Priority | Status |
|---|---|---|---|
| **RBAC** | User vs Admin roles | HIGH | ✅ `UserRole` type exists (`'user' \| 'admin'`) |
| **API Key Auth** | Bearer token for network mode | HIGH | Designed in `ENTERPRISE_POSTURE_AND_ROADMAP.md` |
| **SSO / SAML** | Enterprise IdP integration (Okta, Azure AD) | MEDIUM | Roadmap — only if demanded by pilots |
| **SCIM Provisioning** | Auto-create/deactivate users from IdP | LOW | Roadmap — follows SSO |
| **Seat Management** | Active seat count, max seats per license | MEDIUM | ✅ `UsageData.activeSeats` in admin panel |
| **Dev Role Override** | Developer can simulate admin for testing | LOW | ✅ Built (Settings → Developer tab) |

### 6.2 Policy & Configuration Governance

| Feature | Description | Priority | Status |
|---|---|---|---|
| **Team Config** | Shared `.runprep/team_config.json` in repo | HIGH | ✅ Built (`team_config.py`) |
| **Enforcement Modes** | `suggest` vs `enforce` for team config | HIGH | ✅ Schema defined |
| **Config Provenance** | Show where each setting comes from (default/team/user) | MEDIUM | Planned (`P06-I3`) |
| **Provider Locking** | Admin controls which LLM providers are available | HIGH | **Designed in this doc** |
| **Model Restrictions** | Allowlist/blocklist of model names | HIGH | **Designed in this doc** |
| **Locked Endpoints** | Pre-configured endpoints users can't modify | HIGH | **Designed in this doc** |
| **Data Residency Policy** | Restrict which regions data can be sent to | LOW | Future — complex, deferred |

### 6.3 Audit & Compliance

| Feature | Description | Priority | Status |
|---|---|---|---|
| **Audit Log** | Who queried what, when, which project | HIGH | Roadmap (append-only local log) |
| **Export Audit** | Syslog or SIEM integration | MEDIUM | Roadmap — follows audit log |
| **Content Logging** | Log actual query content | LOW | Opt-in only — privacy concern |
| **DPA Compliance** | Data Processing Agreement documentation | MEDIUM | Business/legal — not code |
| **SOC2 Posture** | Evidence of security controls | MEDIUM | Documentation + audit log |

### 6.4 Deployment & Distribution

| Feature | Description | Priority | Status |
|---|---|---|---|
| **Signed Installers** | Code-signed macOS/Windows packages | HIGH | Planned (Phase 11) |
| **MDM Deployment** | Push via Jamf, Intune, etc. | MEDIUM | Follows signed installers |
| **Offline Licensing** | Ed25519 signed keys, no phone-home | HIGH | ✅ Designed (`LICENSING_IMPLEMENTATION.md`) |
| **Internal Mirror** | Host installers on internal artifact repo | LOW | Just a download URL |
| **Docker Images** | CPU + GPU headless images | HIGH | ✅ Built (`Dockerfile.cpu`, `Dockerfile.gpu`) |
| **Helm Chart** | K8s deployment for Prep Manager | LOW | Future — follows Docker |

### 6.5 Fleet Operations

| Feature | Description | Priority | Status |
|---|---|---|---|
| **Compute Node CRUD** | Add/edit/remove GPU servers | HIGH | ✅ Built (Phase 45D) |
| **Pipeline Scheduler** | Multi-node slot management + queuing | HIGH | ✅ Built (Phase 45D) |
| **Sync Fleet Status** | Per-project sync health | HIGH | ✅ Built in admin panel |
| **Health Monitoring** | Node online/degraded/offline | MEDIUM | Schema exists, polling TBD |
| **Cost Tracking** | Token usage × model pricing | MEDIUM | Schema exists (`UsageData`) |
| **Alerting** | Notify admin when queue backs up or node goes offline | LOW | Future |

---

## 7. Admin Panel Layout — Detailed Wireframe

### Panel 1: AI Gateway (Enhanced — All Users + Admin Section)

```
┌─────────────────────────────────────────────────────────┐
│  ⚙️  AI Gateway                                         │
│                                                         │
│  ┌─ 🟠 Admin Policy ──────────────────────────────────┐ │
│  │  Allowed Providers: [✓ Google] [✓ Anthropic] [✗ …] │ │
│  │  Locked Endpoints:                                  │ │
│  │    🔒 Corporate Vertex AI  (Google)  ✅ Connected   │ │
│  │    🔒 Corporate Bedrock    (OpenAI-compat)  ✅      │ │
│  │  Model Policy: gemini-2.5-*, claude-3.5-sonnet-*    │ │
│  └─────────────────────────────────────────────────────┘ │
│                                                         │
│  Saved Endpoints (User)                                 │
│    📡 My Local Ollama    ollama    localhost:11434  [▶]  │
│    + Add New Endpoint                                   │
│                                                         │
│  ── Model Assignments ─────────────────────────────────  │
│  [Standard Mode ▾]  [Mapped Mode ▾]                     │
│  Fast:   gemini-2.5-flash    on Corporate Vertex AI     │
│  Deep:   claude-3.5-sonnet   on Corporate Bedrock       │
│                                                         │
│  ── Compute Profile ───────────────────────────────────  │
│  Concurrency: [2]  Hardware: [Apple Silicon 64GB]       │
└─────────────────────────────────────────────────────────┘
```

### Panel 2: Enterprise Admin (Admin-Only)

```
┌─────────────────────────────────────────────────────────┐
│  🛡️  Enterprise Admin                     Admin Only    │
│                                                         │
│  [Fleet & Scheduling]  [Sync Fleet]  [Usage & Stress]   │
│                                                         │
│  ── Fleet & Scheduling ─────────────────────────────── │
│  ┌───────────────┬──────────┬───────┬────────┐          │
│  │ Node          │ Hardware │ Slots │ Status │          │
│  ├───────────────┼──────────┼───────┼────────┤          │
│  │ gpu-server-01 │ 4x A100  │ 3/4   │ 🟢     │          │
│  │ gpu-server-02 │ 2x 4090  │ 0/2   │ 🟢     │          │
│  │ mac-studio    │ M2 Ultra │ 1/1   │ 🟡     │          │
│  └───────────────┴──────────┴───────┴────────┘          │
│  Queue: 2 projects waiting · Est. wait: ~8 min          │
│                                                         │
│  ── Usage & Stress (Current Month) ──────────────────  │
│  Indexing:  142 min / 500 min  ████████░░░  28%         │
│  Storage:  12.4 GB / 50 GB    █████░░░░░░  25%         │
│  Seats:    14 / 25            ████████░░░  56%         │
│  API Cost: ~$847              ████████████  (no limit)  │
│                                                         │
│  Errors (7d): 3 failed builds, 1 sync timeout           │
│  Avg Build:   12m 34s (↓18% vs last month)              │
└─────────────────────────────────────────────────────────┘
```

### Panel 3 (Optional Future): Audit Log

If the audit surface grows large enough, a third admin panel could display:
- Immutable event timeline (who, what, when, which project)
- Filterable by user, action type, project
- Export to CSV/JSON for SIEM ingestion

For now, this can be a section within the Enterprise Admin panel.

---

## 8. Settings Tab Consideration

### Do We Need a Separate "Admin Settings" Tab?

The existing Settings drawer has tabs: General, Developer, (future: Appearance, etc.)

**Option A: Add an "Admin" tab to Settings**
- Contains: Provider policy editor, enforcement mode toggle, model allowlist editor
- Pros: Settings is the natural place for configuration
- Cons: Settings is a drawer (overlay), not a panel — limited space for complex admin forms

**Option B: Keep everything in dashboard panels**
- The AI Gateway panel handles policy config inline (orange section)
- The Enterprise Admin panel handles fleet/usage
- Pros: Everything is visible at a glance, no hidden settings
- Cons: Mixes admin config with user display

**Recommendation: Option B (panels) for v1.** The admin policy section in AI Gateway is read-only for non-admins and editable for admins. This keeps configuration visible. If the admin config surface grows beyond what fits in a panel section, we can add a Settings → Admin tab later.

---

## 9. Data Flow: team_config.json → Admin Policy → UI

```
.runprep/team_config.json (committed to repo, secret-free)
    │
    ▼
Backend: parse_team_config() → TeamConfig
    │
    ├── enforcement_mode: "suggest" | "enforce"
    ├── admin_policy.allowed_providers: ["google", "anthropic"]
    ├── admin_policy.locked_endpoints: [...]
    ├── admin_policy.model_allowlist: ["gemini-*", "claude-*"]
    │
    ▼
API: GET /settings/admin-policy → AdminPolicyResponse
    │
    ▼
Frontend: useAdminPolicy() hook
    │
    ├── EndpointManager: filter PROVIDER_OPTIONS
    ├── EndpointManager: inject locked endpoints (read-only)
    ├── ModelSelector: filter available models
    └── AIModelsSettings: show orange admin section
```

For locked endpoint API keys, the key is stored server-side (env var or secrets manager) and never sent to the frontend. The frontend only knows the endpoint exists and whether it's connected.

---

## 10. Implementation Roadmap

### Phase A: Provider Policy (Near-term, with Team v1)

1. Extend `team_config.json` schema with `admin_policy` section
2. Backend: `GET /settings/admin-policy` endpoint
3. Frontend: `useAdminPolicy()` hook consumed by EndpointManager
4. Frontend: Orange admin section in AI Gateway panel
5. Frontend: Filter provider dropdown by allowlist
6. Frontend: Render locked endpoints with 🔒 icon
7. Tests: Admin policy filtering, enforcement modes

### Phase B: Azure OpenAI Provider (With Team v1)

1. Add `'azure-openai'` to `LLMProvider` type
2. Add to `PROVIDER_OPTIONS` with fields for resource name + deployment name
3. Backend: `_generate_azure_openai()` in `llm_client.py` (uses `api-key` header)
4. Batch profile registry entries for Azure models
5. Tests: Azure auth, deployment name URL construction

### Phase C: AWS Bedrock Provider (Enterprise)

1. Add `'aws-bedrock'` to `LLMProvider` type
2. Add to `PROVIDER_OPTIONS` with fields for region + model ID
3. Backend: `_generate_bedrock()` in `llm_client.py` (SigV4 signing via `boto3`)
4. Endpoint form: AWS credential fields (access key, secret key, region) or IAM role
5. Batch profile registry entries for Bedrock models
6. Tests: SigV4 signing, Bedrock converse API format

### Phase D: Audit Log (Enterprise)

1. Backend: Append-only SQLite audit table (user, action, project, timestamp)
2. API: `GET /admin/audit-log` with pagination + filters
3. Frontend: Audit Log section in Enterprise Admin panel
4. Export: CSV/JSON download endpoint
5. Future: Syslog forwarder

### Phase E: Usage & Cost Tracking (Enterprise)

1. Backend: Track token usage per endpoint per stage per build
2. Backend: Map token counts × model pricing to dollar estimates
3. API: `GET /admin/usage` with date range
4. Frontend: Usage & Stress tab in Enterprise Admin panel
5. Future: Budget alerts, cost anomaly detection

---

## 11. Open Questions

1. **Should provider policy live in `team_config.json` or in the admin API?**
   - `team_config.json` is committed to the repo (good for version control)
   - But API keys for locked endpoints can't be in the repo
   - Recommendation: Policy (allowlist, enforcement) in `team_config.json`. Secrets (locked endpoint keys) in env vars or admin API.

2. **How does provider locking interact with headless mode?**
   - Headless already accepts `--model-provider` and `--api-key` CLI flags
   - In enforced mode, headless should reject providers not in the allowlist
   - Implementation: `HeadlessRunner` reads `team_config.json` → validates provider

3. **Azure OpenAI: separate provider vs. enhanced OpenAI-Compatible?**
   - Separate provider is cleaner UX (resource name + deployment name fields)
   - OpenAI-Compatible works but requires users to construct the full URL manually
   - Recommendation: Separate `azure-openai` provider type

4. **Should the admin panel be visible in the Panel Picker for non-admins?**
   - Option A: Hidden entirely (cleaner)
   - Option B: Visible but grayed out with lock icon (discovery)
   - Recommendation: Option B — helps users discover that admin features exist

5. **Single dashboard vs. admin dashboard?**
   - One dashboard with admin panels addable via Panel Picker is sufficient for v1
   - If the admin surface grows to 5+ panels, consider a dedicated admin view
   - Recommendation: Single dashboard for now, revisit after Phase D/E

---

## 12. Licensing & User Controls

This is a critical enterprise concern and one of the most complex areas due to Prep's offline-first architecture, the LemonSqueezy Merchant of Record relationship, and the need for both individual and organizational license management.

### 12.1 Current Licensing Architecture

**What exists today** (reference: `DISTRIBUTION_AND_REVENUE_PLAN.md`, `feature_gate.py`, `licensing.py`):

| Component | Status | File |
|---|---|---|
| `Tier` enum (FREE → ENTERPRISE) | ✅ Built | `src/prep/core/feature_gate.py` |
| `License` dataclass (tier, email, expires_at, seats) | ✅ Built | `src/prep/core/feature_gate.py` |
| `FEATURE_TIERS` mapping | ✅ Built | `src/prep/core/feature_gate.py` |
| `check_feature()` / `require_feature()` / `get_feature_limit()` | ✅ Built | `src/prep/core/feature_gate.py` |
| Ed25519 signature verification | ✅ Built | `src/prep/core/licensing.py` |
| License file at `~/.runprep/license.json` | ✅ Built | `src/prep/core/feature_gate.py` |
| `PREP_TIER` env var override (dev) | ✅ Built | `src/prep/core/feature_gate.py` |
| `POST /license/activate` (LS exchange) | ❌ Stub only | `DISTRIBUTION_AND_REVENUE_PLAN.md` §10 |
| `api.runprep.io` relay service | ❌ Not implemented | — |
| LemonSqueezy product setup (5 tiers) | ❌ Not done | — |
| LemonSqueezy webhook integration | ❌ Not done | — |
| License recovery endpoint | ❌ Mock stub | — |
| Seat enforcement (Team/Enterprise) | ❌ Honor system | — |
| License UI in dashboard | ❌ Not built | — |

### 12.2 Tier ↔ LemonSqueezy Product Mapping

Each Prep tier maps to a LemonSqueezy product. This mapping is important because LS handles all payment processing, tax compliance, and subscription management.

| Prep Tier | LS Product Type | Price | LS Billing | License `expires_at` | License `updates_until` |
|---|---|---|---|---|---|
| **Free** | N/A | $0 | None | N/A | N/A |
| **Monthly** | Subscription | $7/mo | Recurring | End of billing period + grace | Rolling |
| **Perpetual** | One-time | $79 | One-time | `null` (never) | 1 year from purchase |
| **Team** | Subscription | $15/seat/mo | Recurring per-seat | End of billing period + grace | Rolling |
| **Enterprise** | Custom/Invoice | Custom | Manual invoice / PO | Contract term | Contract term |

### 12.3 Activation Flow (Desktop App ↔ LemonSqueezy ↔ api.runprep.io)

```
User buys on runprep.io/pricing
  → LemonSqueezy processes payment + tax
  → LS fires `order_completed` webhook to api.runprep.io
  → api.runprep.io generates Ed25519-signed license
  → User receives license key via email
  → User pastes key into Prep → Settings → License
  → App calls POST api.runprep.io/activate with LS order key
  → Server returns signed Ed25519 license payload
  → App saves to ~/.runprep/license.json
  → ✅ FULLY OFFLINE FROM HERE — no phone-home, no subscription heartbeat
```

### 12.4 Seat Management for Team/Enterprise

This is where it gets interesting. Prep is local-first, but Team/Enterprise licenses have seat counts.

#### The Problem

- Local-first means no central server counting active installs
- Ed25519 offline licenses don't phone home
- But the enterprise pays for N seats and expects enforcement

#### The Solution: Trust + Periodic Sync (Hybrid Model)

**For Team tier (managed via LemonSqueezy):**

1. **Purchase:** Admin buys N seats on LS → gets a single team license key
2. **Distribution:** Admin distributes the key to developers (via MDM, email, or `team_config.json` secret)
3. **Activation:** Each developer activates → `api.runprep.io/activate` tracks `machine_id` (hash of hostname + MAC)
4. **Enforcement:**
   - `api.runprep.io` counts unique `machine_id`s per license
   - If count > `seats`, new activation is **warned** but not blocked (soft enforcement)
   - Monthly reconciliation email to admin: "You have 17 active machines on a 15-seat license"
5. **Deactivation:** Admin can deactivate machines via `api.runprep.io/deactivate` or LS dashboard
6. **Offline grace:** If a machine can't reach `api.runprep.io`, it continues working with the cached license. Enforcement is eventual, not real-time.

**For Enterprise tier (managed via Prep Manager or manual):**

- Option A: Same as Team but with invoice billing and manual key distribution
- Option B: Self-hosted Prep Manager acts as the license server (machine activation/deactivation happens against the internal server, not `api.runprep.io`)
- Option C: Pure offline — signed license file with `seats: N` is delivered via MDM. Enforcement is legal/contractual only (GitKraken model).

#### LemonSqueezy Integration Points

| LS Event | Prep Action |
|---|---|
| `order_completed` | Generate Ed25519 license, store in DB, email to customer |
| `subscription_payment_success` | Extend `expires_at` by billing period |
| `subscription_payment_failed` | Set `grace_period` (14 days). After grace: tier reverts to FREE |
| `subscription_cancelled` | Set `expires_at` to end of current billing period |
| `subscription_resumed` | Clear `expires_at`, restore tier |
| `subscription_updated` (seat count change) | Update `seats` in license, notify admin |
| `refund_created` | Revoke license key (mark invalid in DB) |
| `license_key_activated` (if using LS built-in) | Track machine activation |

#### Admin License Dashboard (Enterprise Admin Panel)

The Enterprise Admin panel gains a **Licensing** tab:

```
┌─────────────────────────────────────────────────────────┐
│  🛡️  License Management                   Admin Only    │
│                                                         │
│  Plan: Team · 15 seats                                  │
│  Status: Active · Renews Apr 9, 2026                    │
│  License ID: PREP-TEAM-a7f3b2...                      │
│                                                         │
│  Active Machines (14/15):                               │
│  ┌───────────────┬──────────────┬─────────┬───────────┐ │
│  │ Machine       │ User         │ Last    │ Action    │ │
│  ├───────────────┼──────────────┼─────────┼───────────┤ │
│  │ mac-studio-01 │ alice@co.com │ 2h ago  │ [Revoke]  │ │
│  │ mbp-bob       │ bob@co.com   │ 1d ago  │ [Revoke]  │ │
│  │ win-ci-runner │ ci@co.com    │ 3h ago  │ [Revoke]  │ │
│  │ ...           │              │         │           │ │
│  └───────────────┴──────────────┴─────────┴───────────┘ │
│                                                         │
│  [+ Add Seats]  [Manage on LemonSqueezy →]              │
└─────────────────────────────────────────────────────────┘
```

### 12.5 License State Machine

```
┌─────────┐     activate      ┌──────────┐
│  NONE   │ ────────────────► │  ACTIVE  │
│ (Free)  │                   │          │◄──── payment_success
└─────────┘                   └────┬─────┘
                                   │
                    payment_failed │
                                   ▼
                              ┌──────────┐
                              │  GRACE   │  (14 days)
                              │  PERIOD  │
                              └────┬─────┘
                                   │
                    grace_expired  │  payment_success
                          ▼        │       ▲
                    ┌──────────┐   │       │
                    │ EXPIRED  │   └───────┘
                    │ (→ Free) │
                    └────┬─────┘
                         │
                  reactivate (new purchase)
                         │
                         ▼
                    ┌──────────┐
                    │  ACTIVE  │
                    └──────────┘

Parallel states:
  REVOKED — Admin or refund. Cannot reactivate same key.
  UPDATES_EXPIRED — Perpetual license, past updates_until date.
                     App works, but no new versions.
```

### 12.6 Open Licensing Questions

1. **Should Team seat enforcement be hard or soft?**
   - Hard: Block activation beyond seat count → breaks offline-first promise
   - Soft: Allow activation, warn admin monthly → preserves trust, relies on honesty
   - Recommendation: **Soft enforcement** (matches GitKraken, JetBrains model)

2. **Should license status be visible to non-admins?**
   - Users should see their own tier and expiration in Settings
   - Users should NOT see seat count, other machines, or billing details
   - The license tab in Enterprise Admin is admin-only

3. **LemonSqueezy built-in license keys vs. our own Ed25519?**
   - LS has a license key system, but it requires online validation
   - We use LS keys as the *activation input* but generate our own Ed25519 *offline license* via `api.runprep.io`
   - This gives us offline-first validation after one-time activation

4. **How to handle mid-cycle seat changes?**
   - Admin adds 5 seats on LS → webhook fires → `api.runprep.io` updates license `seats` field
   - Existing machines are unaffected until they next phone home (periodic soft check)
   - New activations immediately see updated seat count

---

## 13. Deep Enterprise IT Tooling — Comprehensive Inventory

This section catalogs every standard enterprise IT control that applies to a developer tool like Prep. Items are categorized by urgency and mapped to our architecture.

### 13.1 Corporate Proxy & Certificate Support

**Priority: 🔴 HIGH — Most common enterprise deployment blocker**

Many enterprises route all traffic through corporate HTTP proxies with custom CA certificates (for TLS inspection / MITM). If Prep can't connect through a proxy, it's dead on arrival for regulated industries.

| Requirement | Implementation | Status |
|---|---|---|
| **HTTP proxy support** (`HTTPS_PROXY`, `HTTP_PROXY`, `NO_PROXY` env vars) | Python `requests`/`httpx` respect these by default. Verify Rust engine + Ollama respect them too | ⚠️ Needs verification |
| **Custom CA certificate bundle** | Support `REQUESTS_CA_BUNDLE` / `SSL_CERT_FILE` env vars. Add `proxy.ca_bundle_path` to `team_config.json` | ❌ Not implemented |
| **NTLM/Kerberos proxy auth** | Typically handled by OS-level proxy config (CNTLM, PX). Document workaround | 📝 Documentation only |
| **Certificate pinning bypass** | Some security tools inject certs. Prep must not hard-pin certs | ✅ Not pinned (uses system trust store) |

**Config:**
```json
{
  "admin_policy": {
    "network": {
      "proxy_url": "http://proxy.corp.com:8080",
      "ca_bundle_path": "/etc/ssl/corp-ca-bundle.pem",
      "no_proxy": "localhost,127.0.0.1,.corp.internal"
    }
  }
}
```

### 13.2 Data Loss Prevention (DLP)

**Priority: 🔴 HIGH — Enterprises sending source code to LLM APIs need governance**

When Prep sends code to an LLM for enrichment, that code is leaving the machine. Enterprises need controls over where code goes.

| Control | Description | Implementation |
|---|---|---|
| **Approved destinations** | Admin specifies which providers can receive code | `data_policy.allowed_data_destinations` in Section 4.2 |
| **Block unapproved cloud** | Prevent code from going to non-approved APIs | `data_policy.block_code_to_unapproved_cloud` |
| **Local-only mode** | All processing stays on-machine (Ollama/LM Studio) | `data_policy.allow_local_processing` + block all cloud |
| **Sensitive file exclusion** | Glob patterns for files that should never be sent to any LLM (e.g., `.env`, `secrets/`, `*.pem`) | `data_policy.never_send_globs: ["**/.env*", "**/secrets/**", "**/*.pem", "**/*.key"]` |
| **Audit trail** | Log every LLM API call: which files, which provider, which model, timestamp | Part of audit log (Section 10, Phase D) |
| **Data retention** | Confirm LLM providers have zero-data-retention for training | Documentation / DPA compliance (business concern) |

**Config addition to `admin_policy`:**
```json
{
  "data_policy": {
    "allowed_data_destinations": ["google", "anthropic"],
    "block_code_to_unapproved_cloud": true,
    "allow_local_processing": true,
    "never_send_globs": ["**/.env*", "**/secrets/**", "**/*.pem", "**/*.key"],
    "redact_patterns": ["(?i)(api[_-]?key|password|secret|token)\\s*[:=]\\s*['\"][^'\"]+['\"]"]
  }
}
```

### 13.3 Telemetry & Analytics Controls

**Priority: 🟡 MEDIUM — Expected by infosec teams during procurement**

| Control | Description | Implementation |
|---|---|---|
| **Disable all telemetry** | Master switch: no data leaves the machine | `telemetry.enabled: false` in settings. Default: `false` (opt-in) |
| **Anonymous usage stats** | If enabled: anonymous feature usage counts, no PII, no code | Opt-in with clear disclosure |
| **Error reporting** | Crash reports with stack traces (no code content) | Opt-in (e.g., Sentry with PII scrubbing) |
| **Admin telemetry override** | Admin can force-disable telemetry for all team members | `admin_policy.telemetry.force_disabled: true` |
| **Telemetry audit** | Document exactly what is collected (required for SOC2) | Public telemetry disclosure page |

**Prep's posture: Telemetry is OFF by default.** This is a competitive advantage — many enterprises reject tools that phone home. We can truthfully say "Prep never sends data without explicit opt-in."

### 13.4 Update Management

**Priority: 🟡 MEDIUM — IT wants staged rollouts, not surprise updates**

| Control | Description | Implementation |
|---|---|---|
| **Disable auto-update** | Prevent app from checking for updates | `updates.auto_check: false` in settings or MDM/GPO config |
| **Update channel** | Stable / Beta / Canary | `updates.channel: "stable"` |
| **Internal update server** | Point updater at internal artifact mirror | `updates.feed_url: "https://artifacts.corp.internal/prep/"` |
| **Version pinning** | Admin specifies maximum allowed version | `admin_policy.updates.max_version: "1.5.*"` |
| **Rollback** | Ability to downgrade to previous version | Tauri updater supports this if previous installers are available |
| **Release notes gate** | Show changelog before update is applied | Tauri updater can surface this |

**MDM/GPO deployment pattern:**
```
macOS: defaults write com.prep.app UpdateChannel -string "stable"
       defaults write com.prep.app AutoUpdate -bool NO
Windows: HKLM\SOFTWARE\Prep\UpdateChannel = "stable"
         HKLM\SOFTWARE\Prep\AutoUpdate = 0
```

### 13.5 Configuration Deployment (MDM/GPO)

**Priority: 🟡 MEDIUM — How IT pushes settings to managed machines**

| Method | Platform | Details |
|---|---|---|
| **macOS plist** | macOS | `com.prep.app.plist` pushed via Jamf/Intune/Mosyle |
| **Windows Registry** | Windows | `HKLM\SOFTWARE\Prep\` pushed via GPO or Intune |
| **Config file drop** | Cross-platform | Place `prep_managed.json` in a well-known path (e.g., `/etc/prep/` or `%ProgramData%\Prep\`) |
| **Environment variables** | CI/Docker | `PREP_TIER`, `PREP_LICENSE_KEY`, `PREP_PROXY`, etc. |

**Precedence (highest wins):**
```
1. Environment variables (PREP_*)
2. MDM/GPO managed config (prep_managed.json / plist / registry)
3. team_config.json (from repo)
4. User local settings (~/.runprep/settings)
5. Built-in defaults
```

This precedence is critical: IT-pushed config overrides team config which overrides user config. The admin always wins.

### 13.6 Budget & Cost Controls

**Priority: 🟡 MEDIUM — Prevents runaway API costs**

| Control | Description | Implementation |
|---|---|---|
| **Monthly token budget** | Hard limit on total tokens sent to cloud APIs per month | `admin_policy.budgets.monthly_token_limit: 50_000_000` |
| **Per-user budget** | Limit tokens per individual developer | `admin_policy.budgets.per_user_token_limit: 5_000_000` |
| **Per-project budget** | Limit tokens per project (prevents one massive repo from consuming all budget) | `admin_policy.budgets.per_project_token_limit: 10_000_000` |
| **Cost cap** | Estimated dollar limit based on model pricing | `admin_policy.budgets.monthly_cost_cap_usd: 500` |
| **Budget alerts** | Email/webhook when approaching limits (80%, 100%) | Admin notification + pipeline pauses at hard limit |
| **Budget dashboard** | Current month usage vs. limits | Enterprise Admin → Usage & Stress tab |

**When budget is exceeded:**
- Pipeline pauses with clear error: "Monthly token budget exceeded. Contact your admin."
- Local model processing continues (no cost)
- Admin can increase budget or wait for monthly reset

### 13.7 Data Retention & GDPR Compliance

**Priority: 🟡 MEDIUM — Required for EU enterprises**

| Requirement | Implementation |
|---|---|
| **Index auto-expiry** | Configurable TTL on project indexes: `retention.index_ttl_days: 90` |
| **Data deletion** | "Delete All Data" button per project — removes all index artifacts, embeddings, audit logs |
| **Right to erasure** | API endpoint: `DELETE /projects/{id}/data` — complete wipe |
| **Data export** | API endpoint: `GET /projects/{id}/export` — zip of all stored data |
| **No PII in indexes** | Prep indexes code, not personal data. But audit logs may contain usernames/emails |
| **Audit log retention** | Configurable: `retention.audit_log_days: 365` |
| **S3 lifecycle policies** | For Team Sync: set S3 lifecycle rules to auto-delete old index zips |

### 13.8 Network & Firewall Documentation

**Priority: 🟢 LOW (but important for IT procurement)**

Enterprises need a clear list of domains/IPs to allowlist in their firewalls. This is documentation, not code.

**Domains Prep may contact:**

| Domain | When | Purpose | Can be blocked? |
|---|---|---|---|
| `api.runprep.io` | License activation (one-time) | Exchange LS key for Ed25519 license | Yes, after initial activation |
| `api.lemonsqueezy.com` | Never (backend only) | Webhook delivery to api.runprep.io | N/A (server-to-server) |
| `github.com` | Auto-update check | Check for new releases | Yes (disable auto-update) |
| `objects.githubusercontent.com` | Auto-update download | Download new installer | Yes (disable auto-update) |
| User-configured LLM endpoints | During pipeline runs | API calls to LLM providers | Depends on admin policy |
| User-configured S3 endpoint | Team Sync | Upload/download shared indexes | Depends on team config |

**Air-gapped mode:** Block ALL of the above. License delivered via file. No auto-update. Local models only. Team Sync via sneakernet or internal S3.

### 13.9 Endpoint Security & EDR Compatibility

**Priority: 🟢 LOW — Usually "just works" but needs testing**

Enterprise machines run EDR agents (CrowdStrike Falcon, SentinelOne, Carbon Black). These can interfere with:

| Concern | Risk | Mitigation |
|---|---|---|
| **Process injection detection** | Tauri launching Python sidecar may trigger alerts | Document expected process tree for IT whitelisting |
| **File system scanning** | EDR scanning every file Prep indexes could slow builds | Document index directories for exclusion rules |
| **Network monitoring** | EDR may flag LLM API calls as data exfiltration | Document expected network behavior |
| **Binary signature** | Unsigned binaries flagged as suspicious | Code signing (already planned) |

**Deliverable:** An "IT Deployment Guide" (PDF/webpage) that includes:
- Expected process names and paths
- Recommended EDR exclusion paths (`.runprep/`, index directories)
- Expected network destinations
- File hash verification instructions

### 13.10 Multi-Tenancy & Org Isolation

**Priority: 🟢 LOW — Future, for large enterprises**

| Concept | Description | When Needed |
|---|---|---|
| **Org-scoped projects** | Projects belong to an org, not a user | Prep Manager (web service) |
| **Department budgets** | Separate token budgets per department | Prep Manager |
| **Cross-org isolation** | Org A cannot access Org B's indexes | Prep Manager |
| **Shared model catalog** | Central list of approved models for the org | Admin policy (Section 4) |

This is a Prep Manager (web service) concern, not desktop app. Desktop app handles one user's projects.

### 13.11 Export & Clipboard Controls

**Priority: 🟢 LOW — Niche DLP concern**

Some highly regulated environments restrict clipboard access and data export.

| Control | Description | Implementation |
|---|---|---|
| **Disable context copy** | Prevent users from copying assembled context to clipboard | `admin_policy.data_policy.allow_clipboard_export: false` |
| **Disable context download** | Prevent downloading context as file | Same policy |
| **Watermark exported content** | Inject invisible markers in exported text | Future — complex, low priority |

**Recommendation:** Implement `allow_clipboard_export` flag for Enterprise tier only. This is an edge case but a checkbox item for security reviews.

---

## 13A. Security & Compliance Panel — IT-Facing Security Features

This section bridges the security audit findings (`SECURITY_AUDIT.md`, `TEAM_ENTERPRISE_CODE_AUDIT.md`) into IT-visible admin features. Security is not just backend hardening — IT admins need **visibility and control** in the dashboard.

### 13A.1 Should This Be a New Panel or a Tab?

**Recommendation: New tab in Enterprise Admin panel ("Security & Compliance").**

The Enterprise Admin panel already has Fleet, Sync, and Usage tabs. Security is a natural fourth tab. A separate panel would fragment the admin experience. But if the security surface grows large (e.g., after SSO/SCIM), it can graduate to its own panel.

```
┌─────────────────────────────────────────────────────────┐
│  🛡️  Enterprise Admin                     Admin Only    │
│                                                         │
│  [Fleet & Scheduling] [Sync Fleet] [Usage] [Security]   │
│                                                         │
│  ── Security & Compliance ─────────────────────────────  │
│  ...                                                    │
└─────────────────────────────────────────────────────────┘
```

### 13A.2 Security Health Score

A single aggregate indicator at the top of the Security tab, similar to how "Index Health" works for the knowledge base.

```
┌─────────────────────────────────────────────────────────┐
│  Security Health: 🟡 7/10                                │
│  ██████████████████░░░░  3 warnings                      │
│                                                         │
│  ✅ License: Valid, signed, 14/15 seats                  │
│  ✅ Index integrity: All 5 projects verified             │
│  ✅ DLP policy: Enforced                                 │
│  ⚠️  Secrets file: 2 machines have open permissions      │
│  ⚠️  S3 endpoint: Not on approved allowlist              │
│  ⚠️  Credentials: 1 API key expiring in 7 days          │
└─────────────────────────────────────────────────────────┘
```

**Score calculation:** Each check is pass/warn/fail. Score = passed / total checks.

### 13A.3 Security Checks — Full Inventory

These are the individual health checks that compose the security score. Each maps back to a security audit finding or enterprise IT requirement.

#### Check 1: License Verification (from CRIT-1)

| Check | What it verifies | Source |
|---|---|---|
| **Signature valid** | Ed25519 signature on license.json matches embedded public key | `licensing.py` |
| **Not expired** | `expires_at` is null or in the future | `feature_gate.py` |
| **Seats within limit** | Active machines ≤ license `seats` | `api.runprep.io` (periodic check) |
| **Updates valid** | `updates_until` is in the future (or irrelevant for subscription) | `feature_gate.py` |
| **Not revoked** | License ID not on revocation list (optional online check) | `api.runprep.io` |

**UI:** Green shield if all pass. Yellow if updates expired. Red if signature invalid or license expired.

**Ties to:** ENTERPRISE_ADMIN_DESIGN §12 (Licensing), SECURITY_AUDIT CRIT-1.

#### Check 2: S3 Endpoint Security (from CRIT-2)

| Check | What it verifies | Source |
|---|---|---|
| **HTTPS only** | `s3_endpoint` uses `https://` scheme | `remote_sync.py` config validation |
| **On approved list** | Endpoint matches admin allowlist (if configured) | `admin_policy.sync.allowed_s3_endpoints` |
| **No internal IPs** | Endpoint does not resolve to RFC 1918 or link-local addresses | SSRF prevention |
| **No metadata URLs** | Endpoint is not `169.254.169.254` or cloud metadata service | SSRF prevention |

**Admin config:**
```json
{
  "admin_policy": {
    "sync": {
      "allowed_s3_endpoints": [
        "https://s3.amazonaws.com",
        "https://s3.*.amazonaws.com",
        "https://*.r2.cloudflarestorage.com"
      ],
      "require_https": true,
      "block_internal_endpoints": true
    }
  }
}
```

**UI:** Show current S3 endpoint for each synced project with pass/warn indicator.

**Ties to:** SECURITY_AUDIT CRIT-2, ENTERPRISE_ADMIN_DESIGN §13.1.

#### Check 3: Secrets & Credential Health

| Check | What it verifies | Source |
|---|---|---|
| **Secrets file permissions** | `.runprep/.secrets` is mode 600 (owner-only) on Unix | Local file check |
| **No secrets in team_config** | `team_config.json` doesn't contain credential-like keys | `remote_sync.py` (existing check) |
| **API key freshness** | Cloud API keys are valid (periodic test call) | Endpoint test |
| **API key rotation age** | Warn if key hasn't been rotated in >90 days (if admin sets policy) | `admin_policy.credentials.max_key_age_days` |
| **CLI secret usage** | Warn if `--api-key` or `--s3-secret-key` used (visible in process list) | `cli.py` detection |

**UI:** Per-machine credential health status in the machine list (ties into License Management tab).

**Ties to:** SECURITY_AUDIT HIGH-2, HIGH-3, CODE_AUDIT SEC-2.

#### Check 4: Index Integrity (from MED-3)

| Check | What it verifies | Source |
|---|---|---|
| **Content hash match** | Downloaded index zip SHA-256 matches `manifest.content_hash` | `s3_storage.py` (now fixed) |
| **Manifest signature** | Manifest signed by the CI build's key (future) | Prevents tampered indexes |
| **No zip bomb** | Uncompressed size < 10 GB limit | `s3_storage.py` (now fixed) |
| **No zip-slip paths** | No path traversal in zip entries | `s3_storage.py` (existing) |

**UI:** Per-project integrity status in the Sync Fleet tab. Green checkmark = verified. Red X = hash mismatch.

**Ties to:** SECURITY_AUDIT MED-3, HIGH-4, HIGH-5.

#### Check 5: Data Flow & DLP Compliance

| Check | What it verifies | Source |
|---|---|---|
| **Approved destinations only** | All LLM API calls went to approved providers | Audit log analysis |
| **No blocked files sent** | Files matching `never_send_globs` were excluded | Pipeline enforcement |
| **Local processing compliance** | If `allow_local_processing` is the only mode, no cloud calls made | Audit log |
| **Redaction applied** | If `redact_patterns` is configured, patterns were stripped | Pipeline log |

**UI:** Data flow summary: "This month: 2.3M tokens → Google Vertex AI, 1.1M tokens → Local Ollama. 0 policy violations."

**Ties to:** ENTERPRISE_ADMIN_DESIGN §13.2 (DLP), §4 (AI Gateway Policy).

#### Check 6: Configuration Drift Detection

| Check | What it verifies | Source |
|---|---|---|
| **team_config.json unchanged** | Config hash matches last admin-reviewed hash | `team_config.py` (config_hash field) |
| **No unauthorized provider changes** | Provider policy hasn't been tampered with | Config diff on load |
| **Enforcement mode intact** | `enforcement` field hasn't been downgraded from `enforce` to `suggest` | Config validation |

**UI:** "Configuration: ✅ No drift since last review (Mar 8, 2026)" or "⚠️ team_config.json changed — 3 fields modified. [Review Changes]"

**Admin action:** "Approve Changes" button to update the stored hash, or "Reject & Restore" to flag the change.

**Ties to:** ENTERPRISE_ADMIN_DESIGN §4.4, §13.5.

#### Check 7: Network Security

| Check | What it verifies | Source |
|---|---|---|
| **Proxy configured** | Corporate proxy is set (if admin requires it) | `admin_policy.network.proxy_url` |
| **CA bundle loaded** | Custom CA certs loaded successfully | `admin_policy.network.ca_bundle_path` |
| **TLS version** | All outbound connections use TLS 1.2+ | Python SSL defaults |
| **No plaintext HTTP** | No LLM endpoints configured with `http://` (except localhost) | Endpoint validation |

**UI:** Network config summary with pass/warn for each check.

**Ties to:** ENTERPRISE_ADMIN_DESIGN §13.1.

### 13A.4 Security Event Log

A focused subset of the audit log (§10 Phase D / §13.7) that surfaces only security-relevant events.

**Events to log:**

| Event | Severity | Details |
|---|---|---|
| License activation/deactivation | INFO | Machine ID, user, timestamp |
| License verification failure | WARNING | Invalid signature, expired, revoked |
| Policy violation (blocked) | WARNING | Provider/model blocked by enforce mode |
| Policy violation (allowed in suggest mode) | INFO | Provider/model used outside recommendation |
| S3 endpoint changed in team_config | WARNING | Old → new endpoint, who committed |
| Secrets detected in team_config | CRITICAL | Which keys found, file path |
| Index hash mismatch | CRITICAL | Project, expected vs. actual hash |
| Failed endpoint test | INFO | Provider, URL, error |
| API key rotation reminder | INFO | Key age, endpoint |
| DLP: blocked file send attempt | WARNING | File path, provider, why blocked |
| Budget threshold reached (80%, 100%) | WARNING | Current usage, limit |
| Unauthorized machine activation | WARNING | Machine ID, seat count exceeded |

**UI:** Filterable table with severity icons, newest first. Export to CSV.

### 13A.5 Admin Actions from Security Panel

The security tab isn't just read-only — admins can take action:

| Action | What it does |
|---|---|
| **Revoke Machine** | Deactivate a specific machine's license seat |
| **Approve Config Changes** | Accept detected drift in team_config.json |
| **Force Policy Sync** | Push current admin policy to all connected machines |
| **Rotate API Key Reminder** | Send reminder to users with stale API keys |
| **Export Security Report** | Generate PDF/JSON of current security posture for compliance |
| **Block Endpoint** | Immediately disable a specific endpoint for all users |
| **Quarantine Project** | Disable sync for a project with integrity failure |

### 13A.6 Security Panel Wireframe

```
┌─────────────────────────────────────────────────────────┐
│  🛡️  Enterprise Admin → Security & Compliance           │
│                                                         │
│  Security Health: 🟡 7/10  ███████████░░░  3 warnings   │
│                                                         │
│  ── Checks ────────────────────────────────────────────  │
│  ✅ License         Valid · Signed · 14/15 seats         │
│  ✅ Index Integrity  All 5 projects verified (SHA-256)   │
│  ✅ DLP Policy       Enforced · 0 violations (30d)       │
│  ⚠️  Credentials     1 API key expiring in 7 days        │
│  ⚠️  S3 Endpoint     Not on approved allowlist           │
│  ⚠️  Config Drift    team_config.json changed 2h ago     │
│                       [Review Changes] [Approve]         │
│  ✅ Network          Proxy configured · TLS 1.3          │
│                                                         │
│  ── Recent Security Events ────────────────────────────  │
│  🟡 2h ago   Config drift: team_config.json modified     │
│  🟡 1d ago   API key for 'Corp Vertex' expires in 7d    │
│  🔴 3d ago   Index hash mismatch: project-frontend      │
│              → Quarantined. [Investigate]                │
│  🟢 5d ago   Machine mbp-charlie activated (seat 14/15) │
│                                                         │
│  [Export Security Report]  [View Full Event Log →]       │
└─────────────────────────────────────────────────────────┘
```

---

## 14. Complete Enterprise Feature Matrix (Summary)

Every enterprise control in one table, sorted by implementation priority:

| # | Feature | Category | Priority | Tier | Status |
|---|---|---|---|---|---|
| 1 | Provider allowlist/locking | AI Policy | 🔴 HIGH | Team+ | Designed (§4) |
| 2 | Locked endpoints | AI Policy | 🔴 HIGH | Team+ | Designed (§4) |
| 3 | Model allowlist/blocklist | AI Policy | 🔴 HIGH | Team+ | Designed (§4) |
| 4 | License activation (LS exchange) | Licensing | 🔴 HIGH | All | Stub only (§12) |
| 5 | Seat management | Licensing | 🔴 HIGH | Team+ | Not built (§12) |
| 6 | Corporate proxy support | Network | 🔴 HIGH | All | Needs verification (§13.1) |
| 7 | Custom CA certs | Network | 🔴 HIGH | All | Not implemented (§13.1) |
| 8 | DLP: approved destinations | Data | 🔴 HIGH | Enterprise | Designed (§13.2) |
| 9 | DLP: sensitive file exclusion | Data | 🔴 HIGH | Enterprise | Designed (§13.2) |
| 10 | Orange admin borders | UI | 🟡 MEDIUM | Team+ | Designed (§2) |
| 11 | Enforcement modes (suggest/enforce) | Policy | 🟡 MEDIUM | Team+ | Designed (§4.4) |
| 12 | Azure OpenAI provider | Provider | 🟡 MEDIUM | All | Planned (§5) |
| 13 | AWS Bedrock provider | Provider | 🟡 MEDIUM | Enterprise | Planned (§5) |
| 14 | Audit log | Compliance | 🟡 MEDIUM | Enterprise | Planned (§10 Phase D) |
| 15 | Usage & cost tracking | Monitoring | 🟡 MEDIUM | Team+ | Planned (§10 Phase E) |
| 16 | Token budget controls | Cost | 🟡 MEDIUM | Team+ | Designed (§13.6) |
| 17 | Telemetry controls | Privacy | 🟡 MEDIUM | All | OFF by default (§13.3) |
| 18 | Update management (disable auto-update) | IT Control | 🟡 MEDIUM | All | Tauri native (§13.4) |
| 19 | MDM/GPO config deployment | IT Control | 🟡 MEDIUM | Enterprise | Designed (§13.5) |
| 20 | Data retention policies | Compliance | 🟡 MEDIUM | Enterprise | Designed (§13.7) |
| 21 | License state machine (grace period, revocation) | Licensing | 🟡 MEDIUM | All | Designed (§12.5) |
| 22 | Subscription lifecycle (LS webhooks) | Licensing | 🟡 MEDIUM | Monthly/Team | Designed (§12.4) |
| 23 | SSO/SAML | Identity | 🟢 LOW | Enterprise | Roadmap |
| 24 | SCIM provisioning | Identity | 🟢 LOW | Enterprise | Roadmap |
| 25 | Network allowlist documentation | IT Docs | 🟢 LOW | All | Designed (§13.8) |
| 26 | EDR compatibility guide | IT Docs | 🟢 LOW | All | Designed (§13.9) |
| 27 | Org isolation / multi-tenancy | Architecture | 🟢 LOW | Enterprise | Prep Manager (§13.10) |
| 28 | Clipboard/export controls | DLP | 🟢 LOW | Enterprise | Designed (§13.11) |
| 29 | Security health score + checks panel | Security | 🔴 HIGH | Enterprise | Designed (§13A) |
| 30 | Security event log | Security | 🟡 MEDIUM | Enterprise | Designed (§13A.4) |
| 31 | S3 endpoint allowlist + SSRF prevention | Security | 🔴 HIGH | Team+ | Designed (§13A.3) |
| 32 | Config drift detection + admin approval | Security | 🟡 MEDIUM | Team+ | Designed (§13A.3) |
| 33 | Index integrity verification UI | Security | 🟡 MEDIUM | Team+ | Designed (§13A.3) |
| 34 | Credential rotation tracking | Security | 🟡 MEDIUM | Enterprise | Designed (§13A.3) |
| 35 | License crypto verification (CRIT-1 fix) | Security | 🔴 HIGH | All | Audit finding (§13A.3) |
| 36 | Admin security actions (revoke, quarantine, block) | Security | 🟡 MEDIUM | Enterprise | Designed (§13A.5) |

---

## 15. Updated Implementation Roadmap

Supersedes Section 10. Now includes licensing and enterprise IT controls.

### Phase A: Licensing MVP (Pre-launch, blocking)

1. Deploy `api.runprep.io` serverless function (Cloudflare Workers or Netlify Functions)
2. Implement LemonSqueezy webhook handler (`order_completed` → generate Ed25519 license)
3. Implement `POST /activate` endpoint (LS key → signed license exchange)
4. Implement `POST /recover` endpoint (email → re-send license)
5. Create LemonSqueezy products: Free, Monthly ($7), Perpetual ($79), Team ($15/seat)
6. Build License UI in Settings: key input, tier display, expiration, upgrade CTA
7. Wire `feature_gate.py` into all gated UI surfaces (project limit, trace, auto-rebuild)
8. Test: Full purchase → activate → offline validation → expiry → renewal flow

### Phase B: Provider Policy + Admin UI (With Team v1)

1. Extend `team_config.json` schema with `admin_policy` section
2. Backend: `GET /settings/admin-policy` endpoint
3. Frontend: `useAdminPolicy()` hook
4. Frontend: Orange admin section in AI Gateway panel
5. Frontend: Provider dropdown filtering by allowlist + `allow_local_providers`
6. Frontend: Locked endpoints with 🔒 icon
7. Frontend: Admin license tab in Enterprise Admin panel
8. Tests: Policy filtering, enforcement modes, local provider escape hatch

### Phase C: Seat Management + Subscription Lifecycle (With Team v1)

1. Implement `POST /activate` with `machine_id` tracking
2. Implement `POST /deactivate` for admin seat revocation
3. Handle LS `subscription_*` webhooks (payment success/fail, cancel, resume, seat change)
4. Grace period logic (14 days after payment failure)
5. Monthly seat reconciliation email to admin
6. Admin dashboard: active machines list, revocation buttons

### Phase D: Azure OpenAI + Corporate Proxy (Team v1)

1. Add `'azure-openai'` provider to LLMProvider + EndpointManager
2. Backend: `_generate_azure_openai()` with `api-key` header auth
3. Verify HTTP proxy support (`HTTPS_PROXY`) across Python, Rust engine, and LLM client
4. Implement `proxy.ca_bundle_path` config for custom CA certs
5. Test behind corporate proxy with TLS inspection

### Phase E: DLP + Sensitive File Controls (Enterprise)

1. Implement `never_send_globs` — files matching these patterns are excluded from ALL LLM API calls
2. Implement `redact_patterns` — regex patterns for inline secrets stripped before sending to LLM
3. Implement `block_code_to_unapproved_cloud` enforcement in `llm_client.py`
4. Audit log: record every LLM API call with file list + provider + model

### Phase F: AWS Bedrock Provider (Enterprise)

1. Add `'aws-bedrock'` to LLMProvider
2. Backend: `_generate_bedrock()` with SigV4 signing via `boto3`
3. Batch profile registry for Bedrock-hosted models
4. Test with IAM role auth (no static keys)

### Phase G: Audit Log + Usage Tracking (Enterprise)

1. Append-only SQLite audit table
2. `GET /admin/audit-log` with pagination + filters
3. Token usage tracking per endpoint per stage per build
4. Cost estimation (token count × model pricing)
5. Budget enforcement (pause pipeline at limit)
6. Export: CSV/JSON download

### Phase H: IT Deployment Docs + MDM Config (Enterprise)

1. Write IT Deployment Guide (PDF/web): process tree, EDR exclusions, network destinations
2. Implement `prep_managed.json` config file support with highest-priority precedence
3. macOS plist schema for MDM
4. Windows registry schema for GPO
5. Network allowlist documentation

### Phase I: Security & Compliance Panel (Enterprise)

1. Security health score computation (7 checks → aggregate score)
2. Backend: `GET /admin/security-health` endpoint (runs all checks)
3. S3 endpoint allowlist validation + SSRF prevention in `remote_sync.py`
4. Config drift detection (hash comparison + diff on load)
5. Credential freshness tracking (API key age, expiry warnings)
6. Frontend: Security & Compliance tab in Enterprise Admin panel
7. Security event log (subset of audit log, severity-filtered)
8. Admin actions: Revoke machine, Quarantine project, Block endpoint, Export report

### Phase J: SSO/SCIM (Enterprise, if demanded)

1. SAML SSO integration (Okta, Azure AD, OneLogin)
2. SCIM user provisioning
3. Role mapping from IdP groups → Prep admin/user roles
4. This is post-launch and only built if real enterprise pilots demand it

---

## 16. Open Questions (Updated)

*Original questions from §11 plus new ones.*

1. **Should provider policy live in `team_config.json` or in the admin API?**
   - Recommendation: Policy in `team_config.json`. Secrets in env vars or admin API.

2. **How does provider locking interact with headless mode?**
   - `HeadlessRunner` reads `team_config.json` → validates provider against allowlist.

3. **Azure OpenAI: separate provider vs. enhanced OpenAI-Compatible?**
   - Recommendation: Separate `azure-openai` provider type.

4. **Should the admin panel be visible in the Panel Picker for non-admins?**
   - Recommendation: Visible but grayed out with lock icon (discovery).

5. **Single dashboard vs. admin dashboard?**
   - Recommendation: Single dashboard for now, revisit after Phase G/H.

6. **Should Team seat enforcement be hard or soft?**
   - Recommendation: Soft (allow activation, warn admin monthly). Hard enforcement breaks offline-first promise.

7. **LemonSqueezy built-in license keys vs. our own Ed25519?**
   - Use LS keys as activation INPUT → exchange for our Ed25519 offline license. Best of both worlds.

8. **How to handle `api.runprep.io` downtime during activation?**
   - Activation requires one-time internet. If api.runprep.io is down, show retry + manual key entry fallback.
   - After activation, app is fully offline. Downtime doesn't affect existing users.

9. **Should DLP `never_send_globs` be enforced at the file level or content level?**
   - File level first (cheaper, deterministic). Content-level redaction (`redact_patterns`) as opt-in second layer.

10. **Should budget enforcement pause the entire pipeline or just skip cloud-dependent stages?**
    - Pause entire pipeline with clear error. Local stages can't produce useful results without the cloud stages in a typical run.

11. **Corporate proxy: do we need to handle NTLM auth ourselves?**
    - No. Document that enterprises should use CNTLM or PX as a local proxy bridge. Standard `HTTPS_PROXY` with basic auth is all we support directly.

12. **Config precedence: should MDM config override team_config.json?**
    - Yes. MDM is the IT admin's most direct control. Precedence: env vars > MDM config > team_config.json > user settings > defaults.

---

## 17. Security Research — Emerging Threats & Industry Findings (Mar 2026)

This section documents research conducted prior to implementation, covering recent AI security breaches, OWASP guidelines, and open-source tools that should inform our security architecture.

### 17.0 Security Feature Tier Classification

Not all security features require admin management. Most are core app protections that benefit every user automatically. Here's the definitive classification:

#### Tier 1: Core App Security (All tiers, including Free — No admin needed)

These are baked into the product. They run automatically. No configuration, no admin panel, no team_config.json. Every Prep user gets them.

| Feature | Why it's core | TODO ref |
|---|---|---|
| Ed25519 license signature verification | Protects revenue for ALL tiers | EA-A6 |
| `expires_at` validation | Prevents expired license abuse | EA-A7 |
| Dev mode restriction on `PREP_TIER` | Prevents trivial license bypass | EA-A8 |
| Input sanitization before LLM calls (Unicode stripping, prompt injection detection) | Protects every user from poisoned repo content | EA-B10 |
| Output validation after LLM responses (anomaly detection) | Protects every user from manipulated enrichment | EA-B11 |
| Context sanitization (triple backtick escaping) | Prevents prompt injection via context output | EA-B5 |
| SSRF prevention on S3 endpoints (HTTPS-only, block metadata IPs) | Protects every Team Sync user | EA-B1 |
| Secrets file permission check (mode 600) | Protects every user's credentials | EA-B3 |
| CLI secret deprecation warnings | Prevents accidental secret exposure in CI logs | EA-B4 |
| HTTP proxy support (`HTTPS_PROXY`) | Enables enterprise network compatibility | EA-B6 |
| Custom CA certificate bundle | Enables corporate proxy compatibility | EA-B7 |
| Trivy in CI (CVE scanning of our own deps) | Protects all users from vulnerable dependencies | EA-B8 |
| Gitleaks in CI (prevent our secret commits) | Protects our codebase integrity | EA-B9 |
| MCP tool audit logging + rate limiting | Protects all MCP users from bulk exfiltration | EA-B12 |
| Content hash verification on S3 download | Protects all Team Sync users from tampered indexes | Already fixed |
| Zip bomb / zip-slip protection | Protects all Team Sync users | Already fixed |
| Git clone `--` separator | Prevents flag injection | Already fixed |
| Telemetry OFF by default | Privacy by default for all users | By design |

#### Tier 2: Team Config Security (Team+ — Admin edits `team_config.json`, no dashboard needed)

These are configured by the team lead in `team_config.json` (committed to the repo). They don't require the Enterprise Admin dashboard panel — just editing a JSON file.

| Feature | What admin configures | TODO ref |
|---|---|---|
| Provider allowlist | Which LLM providers are visible | EA-C1, EA-C5 |
| `allow_local_providers` escape hatch | Whether devs can always use Ollama/LM Studio | EA-C5 |
| Locked endpoints | Pre-configured endpoints users can't modify | EA-C6 |
| Model allowlist/blocklist | Which models are permitted | EA-C9 |
| Enforcement mode (`suggest` / `enforce`) | How strictly policy is applied | EA-C8 |
| S3 endpoint allowlist | Which S3 endpoints are trusted for Team Sync | EA-B2 |
| `never_send_globs` (DLP file exclusion) | Which files should never go to any LLM | EA-F1 |
| `allowed_data_destinations` | Which cloud providers can receive code | EA-F4 |
| Config drift detection | Automatic — alerts on team_config.json changes | EA-I7 |

#### Tier 3: Enterprise Admin Security (Enterprise — Full admin dashboard panel required)

These require the admin role, the Enterprise Admin panel, and often backend infrastructure (`api.runprep.io`, audit database, etc.).

| Feature | Why it needs admin dashboard | TODO ref |
|---|---|---|
| Security Health Score (7 checks → aggregate) | Visual dashboard display + drill-down | EA-I1–I8 |
| Security Event Log | Filterable event timeline | EA-I9 |
| Admin actions (revoke, quarantine, block) | Interactive management controls | EA-I11 |
| Export Security Report (PDF/JSON) | Compliance deliverable | EA-I12 |
| Seat management (machine list, revocation) | License administration | EA-D1–D10 |
| Budget enforcement (token/cost limits) | Cost controls with pipeline pausing | EA-H5–H6 |
| Credential rotation tracking | API key age monitoring | EA-I4 |
| Usage & cost tracking dashboard | Visual usage meters | EA-H3–H4, EA-H7 |
| Full audit log with export | Compliance-grade event logging | EA-H1–H2, EA-H8 |
| Unicode sanitization check | Security panel indicator | EA-I13 |
| Embedding integrity check | Security panel indicator | EA-I14 |
| Supply chain health display | Security panel indicator (Trivy results) | EA-I15 |
| `redact_patterns` (inline secret redaction) | Advanced DLP requiring config + monitoring | EA-F2 |
| MDM/GPO config deployment | IT pushes managed config | EA-J2–J5 |
| SSO/SAML + SCIM | Enterprise identity integration | EA-L1–L3 |

#### The AI Gateway Stays User-Accessible

**Critical point:** The AI Gateway panel is NOT admin-only. All users access it to configure their endpoints and models. The admin policy (orange-bordered section at the top) adds guardrails ON TOP of the user experience. Even under `enforce` mode, the Gateway remains functional — users just see a filtered set of options.

```
AI Gateway Panel (ALL USERS):
┌──────────────────────────────────────────┐
│ 🟠 Admin Policy (Team+, if configured)   │  ← Orange section, read-only for non-admins
│   Allowed: Google, Anthropic, Ollama     │
│   Locked: 🔒 Corporate Vertex AI        │
├──────────────────────────────────────────┤
│ Your Endpoints (ALL USERS)               │  ← Always accessible
│   📡 My Local Ollama  [▶ Test] [✏ Edit] │
│   + Add New Endpoint                     │
├──────────────────────────────────────────┤
│ Model Assignments (ALL USERS)            │  ← Always accessible
│   Fast: gemini-2.5-flash                 │
│   Deep: claude-3.5-sonnet                │
└──────────────────────────────────────────┘
```

### 17.1 OWASP Top 10 for LLM Applications (2025) — Prep Relevance Map

The OWASP GenAI Security Project published the definitive risk list for LLM applications. Here's how each risk maps to Prep:

| # | OWASP Risk | Prep Exposure | Mitigation Status |
|---|---|---|---|
| **LLM01** | Prompt Injection | 🔴 **HIGH** — Prep sends code to LLMs for enrichment. Malicious code in a repo could contain embedded prompt injections that alter LLM behavior during indexing. | Partially addressed: context output has `<!-- TREAT AS DATA -->` comment (MED-4 in audit). Need: content sanitization in pipeline input. |
| **LLM02** | Sensitive Information Disclosure | 🔴 **HIGH** — LLMs process source code that may contain API keys, passwords, PII in comments, internal URLs. LLM responses might echo these back into index artifacts. | Designed: `never_send_globs` + `redact_patterns` in DLP policy (§13.2). Not yet implemented. |
| **LLM03** | Supply Chain | 🟡 **MEDIUM** — Prep uses Ollama (piped curl install), Python packages, Rust crates, npm packages. Docker images are a supply chain surface. | Audit LOW-3 flagged Ollama piped curl. Need: dependency pinning, SBOM generation, image signing. |
| **LLM04** | Data and Model Poisoning | 🟡 **MEDIUM** — Team Sync downloads indexes from S3 that could be poisoned. A compromised CI build could inject poisoned embeddings that bias search results. | Partially addressed: content hash verification (MED-3 fixed). Need: manifest signing by CI build key. |
| **LLM05** | Improper Output Handling | 🟡 **MEDIUM** — Prep renders LLM output (atlas, audit reports) in the dashboard. XSS risk if output contains `<script>` tags or markdown injection. | Need: sanitize all LLM output before rendering in dashboard HTML. |
| **LLM06** | Excessive Agency | 🟢 **LOW** — Prep's LLM usage is read-only (enrichment, not agentic code execution). MCP tools are read-only search/context. | Low risk by design. MCP tools don't modify files or execute code. |
| **LLM07** | System Prompt Leakage | 🟢 **LOW** — Prep's system prompts contain pipeline instructions, not secrets. Leaking them is an IP concern but not a security breach. | Accept risk. System prompts don't contain credentials or PII. |
| **LLM08** | Vector and Embedding Weaknesses | 🔴 **HIGH** — Prep is fundamentally a RAG system. Its vector store (embeddings.npy) and trace graph are the core product. Embedding poisoning, cross-tenant leakage in Team Sync, and inversion attacks are real risks. | Need: access-partitioned vector stores for Team Sync, embedding integrity checks, anomaly detection on search results. See §17.3. |
| **LLM09** | Misinformation | 🟡 **MEDIUM** — Atlas and audit reports may contain hallucinated architecture descriptions. Users trust Prep's analysis. | Existing: quality gates in atlas generation. Need: confidence indicators on LLM-generated content. |
| **LLM10** | Unbounded Consumption | 🟡 **MEDIUM** — Without budget controls, a single user could consume unlimited tokens on cloud APIs. Malicious repos could contain files designed to maximize token consumption. | Designed: budget controls (§13.6). Not yet implemented. |

### 17.2 AI Coding Tool CVEs (Dec 2025) — Lessons for Prep

In December 2025, security researcher Omer Marzouk published findings on **30+ vulnerabilities** across Cursor (CVE-2025-49150), Roo Code (CVE-2025-53097), JetBrains Junie (CVE-2025-58335), GitHub Copilot, and Claude Code. Key attack patterns:

#### Attack Pattern 1: Rules File Backdoor (Pillar Security, Mar 2025)
**What:** Malicious instructions hidden in AI configuration files (`.cursor/rules`, `.github/copilot-instructions.md`) using invisible Unicode characters (zero-width joiners, bidirectional text markers). The AI reads these instructions but human reviewers can't see them.

**Prep relevance:** Prep has `.runprep/team_config.json` and `.windsurf/workflows/*.md` — both are config files read by AI tools. A malicious contributor could inject hidden Unicode instructions.

**Mitigation needed:**
- Strip/flag invisible Unicode characters in `team_config.json` on load
- Validate that config files contain only expected JSON/ASCII content
- Add a "Unicode sanitizer" check to the Security Health panel

#### Attack Pattern 2: MCP Tool Poisoning
**What:** A malicious MCP server includes hidden instructions in tool descriptions that manipulate the AI agent to exfiltrate data using other MCP tools in the same session.

**Prep relevance:** Prep publishes an MCP server (`prep-mcp`). If a user connects Prep's MCP alongside a malicious MCP server, the malicious server could influence the AI to misuse Prep's tools. Prep's MCP tools are read-only, limiting damage, but search results could still be exfiltrated.

**Mitigation needed:**
- Prep MCP tools should have explicit scope declarations
- Consider rate-limiting MCP tool calls
- Document MCP security best practices for users

#### Attack Pattern 3: Prompt Injection via Repository Content
**What:** Malicious content embedded in source code files, README.md, issue descriptions, or comments can inject prompts into any AI tool that reads repository content.

**Prep relevance:** 🔴 **This is Prep's most critical attack surface.** Prep reads EVERY file in a repository, sends code to LLMs for enrichment, and stores the results. A poisoned file could:
1. Inject instructions into the LLM during augmentation → produce misleading index entries
2. Contain invisible text that biases search results → developers get wrong context
3. Include prompt injection in code comments → Prep's atlas/audit reports get manipulated

**Mitigation needed:**
- Input sanitization before sending to LLM: strip invisible Unicode, flag suspicious patterns
- Output validation: detect anomalous LLM responses (unexpected URLs, instructions to ignore context)
- Separate "trusted" (admin-verified) vs "untrusted" (user-submitted) content in the index
- Monitor for prompt injection indicators in LLM responses

### 17.3 OWASP LLM08 — Vector & Embedding Weaknesses (Direct Prep Impact)

This OWASP category was created for products exactly like Prep. Key risks:

#### Risk 1: Cross-Tenant Data Leakage in Team Sync
If multiple teams share an S3 bucket (different prefixes), a misconfigured prefix could expose one team's embeddings to another. Embedding inversion attacks could reconstruct original source code from the vector representations.

**Mitigation:**
- Enforce strict S3 prefix isolation (already in HIGH-4 fix)
- Consider encrypting embedding files at rest (AES-256) with per-team keys
- Document that embedding files contain derived representations of source code

#### Risk 2: Index Poisoning via Compromised CI Build
A malicious actor who gains access to the CI pipeline could inject poisoned documents into the index — for example, fake "security advisory" documents that tell developers to use a vulnerable library.

**Mitigation:**
- Sign index manifests with a CI build key (planned in §13A.3 Check 4)
- Verify manifest signatures on download
- Alert admin on unsigned or differently-signed indexes

#### Risk 3: Embedding Inversion
Research shows that embeddings can be partially inverted to reconstruct source content. If embeddings are leaked (e.g., via S3 misconfiguration), an attacker could recover meaningful code fragments.

**Mitigation:**
- Treat `embeddings.npy` as sensitive as source code
- Apply same access controls to index artifacts as to the source repo
- Document this risk for enterprise customers in the IT Deployment Guide

### 17.4 MCP Security Breaches Timeline (Apr-Dec 2025)

A documented timeline of MCP-related security incidents shows systemic patterns:

| Date | Incident | Root Cause |
|---|---|---|
| Apr 2025 | WhatsApp MCP: chat history exfiltration | Tool poisoning + over-privileged access |
| May 2025 | GitHub MCP: private repo data heist | Prompt injection via public issues + broad PAT scopes |
| Jun 2025 | Asana MCP: cross-tenant data exposure | Logic flaw in MCP access control |
| Jun 2025 | Anthropic MCP Inspector: RCE | Trusted localhost = exposed remote API |
| Jul 2025 | mcp-remote: OS command injection | Untrusted input to shell commands |
| Aug 2025 | Filesystem MCP: path traversal | Insufficient path validation |
| Sep 2025 | Malicious MCP server in the wild | Supply chain — fake MCP server on npm |
| Oct 2025 | Smithery hosting: supply-chain breach | Shared build pipeline compromised |

**Patterns:** Over-privileged tokens, untrusted content in LLM context, no isolation between MCP tools, localhost services treated as trusted.

**Prep MCP mitigations:**
- Prep MCP tools are read-only (no file writes, no code execution) ✅
- Prep MCP doesn't accept user-provided file paths for write ✅
- Need: Validate that MCP search queries don't contain injection payloads
- Need: Rate limiting on MCP tool calls to prevent bulk exfiltration
- Need: MCP tool audit logging (who called what, when)

### 17.5 Open-Source Security Tools to Leverage

#### For Build & CI Security

| Tool | What It Does | How Prep Uses It | Priority |
|---|---|---|---|
| **[Semgrep](https://semgrep.dev)** | SAST — static analysis with custom rules. Free for open source. | Run in CI to catch security patterns (SQL injection, path traversal, command injection) in Prep Python/TS code | 🟡 MEDIUM |
| **[Trivy](https://github.com/aquasecurity/trivy)** | Container + dependency vulnerability scanner | Scan Docker images (`prep-headless:cpu/gpu`) for CVEs, scan Python deps, generate SBOM | 🔴 HIGH |
| **[Gitleaks](https://github.com/gitleaks/gitleaks)** | Secrets detection in git history | Run in pre-commit hook + CI to prevent accidental secret commits | 🔴 HIGH |
| **[Cosign](https://github.com/sigstore/cosign)** | Container image signing (Sigstore) | Sign Docker images so enterprise customers can verify authenticity | 🟡 MEDIUM |
| **[Syft](https://github.com/anchore/syft)** | SBOM generation | Generate Software Bill of Materials for compliance (SOC2, FedRAMP) | 🟡 MEDIUM |

#### For LLM/AI-Specific Security

| Tool | What It Does | How Prep Uses It | Priority |
|---|---|---|---|
| **[LLM Guard](https://github.com/protectai/llm-guard)** | Input/output scanning for LLM interactions. Detects PII, prompt injection, secrets in prompts. Python library. | Integrate as pre-send filter before LLM API calls. Scans code content for secrets/PII before sending to cloud APIs. Replaces our custom `redact_patterns` regex with a battle-tested library. | 🔴 HIGH |
| **[NeMo Guardrails](https://github.com/NVIDIA-NeMo/Guardrails)** | LLM input/output moderation, fact-checking, jailbreak detection. | Too heavy for our use case (designed for conversational AI). But `topical rails` concept could inform our output validation. | 🟢 LOW |
| **[Pytector](https://github.com/MaxMLang/pytector)** | Lightweight prompt injection detection using DeBERTa/DistilBERT. | Could scan repo content for embedded prompt injections before indexing. Lightweight ONNX model fits Prep's architecture. | 🟡 MEDIUM |

#### For the Security Panel

| Tool | What It Does | How Prep Uses It | Priority |
|---|---|---|---|
| **[OSSF Scorecard](https://github.com/ossf/scorecard)** | Security health score for open source projects | Inspiration for our Security Health Score design. Same concept (aggregate checks → score) but applied to Prep deployment health instead of repo health. | Design reference |

### 17.6 Actionable Additions to Existing Plans

Based on this research, the following items should be **added to the TODO**:

#### New: EA-B8 through EA-B12 (Security Hardening Sprint)

- **EA-B8**: Add Trivy to CI pipeline — scan Docker images + Python/Node dependencies for CVEs
- **EA-B9**: Add Gitleaks to pre-commit hooks + CI — prevent secret commits
- **EA-B10**: Input sanitization before LLM calls — strip invisible Unicode chars, flag prompt injection patterns using LLM Guard or Pytector
- **EA-B11**: Output validation after LLM responses — detect anomalous patterns (unexpected URLs, "ignore previous instructions", exfiltration attempts)
- **EA-B12**: MCP tool audit logging + rate limiting

#### New: EA-I13 through EA-I15 (Security Panel)

- **EA-I13**: Unicode sanitization check — flag `team_config.json` or `.runprep/` files with invisible Unicode
- **EA-I14**: Embedding integrity check — verify `embeddings.npy` hasn't been tampered with (hash in manifest)
- **EA-I15**: Supply chain health — display Trivy scan results (CVE count in dependencies) in Security panel

### 17.7 Key Takeaways

1. **Prep's biggest unique risk is prompt injection via repository content (OWASP LLM01).** Every file in the repo is potential attack surface. This is different from chatbot prompt injection because the "user input" is the entire codebase, not a single message.

2. **Embedding/vector security (OWASP LLM08) is a new category created for products like Prep.** We need to treat `embeddings.npy` as sensitive data and protect Team Sync's shared indexes against poisoning and inversion.

3. **MCP breaches in 2025 show that read-only tools are safer** — Prep's MCP design (no write tools) is already a strong position. But we need audit logging and rate limiting.

4. **LLM Guard by ProtectAI is the most promising tool** for our use case — it provides PII detection, prompt injection scanning, and secrets detection as a Python library. This could replace our custom `redact_patterns` regex and add battle-tested protection.

5. **Trivy + Gitleaks are table-stakes for any enterprise product** — enterprises will ask for SBOM and vulnerability scanning in procurement. Adding these to CI is low effort, high signal.

6. **The "Rules File Backdoor" attack (invisible Unicode in config files) is a real threat to `team_config.json`** — we need a Unicode sanitizer.

### 17.8 References

- [OWASP Top 10 for LLM Applications 2025](https://genai.owasp.org/llm-top-10/)
- [OWASP LLM08: Vector and Embedding Weaknesses](https://genai.owasp.org/llmrisk/llm082025-vector-and-embedding-weaknesses/)
- [30+ Flaws in AI Coding Tools (TheHackerNews, Dec 2025)](https://thehackernews.com/2025/12/researchers-uncover-30-flaws-in-ai.html)
- [Rules File Backdoor (Pillar Security, Mar 2025)](https://www.pillar.security/blog/new-vulnerability-in-github-copilot-and-cursor-how-hackers-can-weaponize-code-agents)
- [MCP Security Breaches Timeline (AuthZed)](https://authzed.com/blog/timeline-mcp-breaches)
- [LLM Guard by ProtectAI](https://github.com/protectai/llm-guard)
- [Trivy — Container & Dependency Scanner](https://github.com/aquasecurity/trivy)
- [Gitleaks — Secrets Detection](https://github.com/gitleaks/gitleaks)
