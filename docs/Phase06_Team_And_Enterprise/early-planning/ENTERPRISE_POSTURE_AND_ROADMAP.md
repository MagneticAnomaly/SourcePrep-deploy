# Enterprise Tier — Posture and Roadmap

## Purpose
Define what "Enterprise" means for CoDRAG in a way that is:
- implementable (clear technical anchors)
- honest (no overpromising)
- compatible with **ADR-012** (enterprise implementation is post-MVP)

## MVP boundary (ADR-012)
MVP ships the single-user local-first product.

Enterprise-related items in MVP are:
- design constraints (avoid architectural dead-ends)
- UX case studies and guardrails (`WORKFLOW_RESEARCH.md`)

Enterprise-related items **not shipped in MVP**:
- network mode
- authentication / admin UX
- governance features (audit, SSO/SCIM)

## Enterprise pillars (what buyers care about)

### 1) Distribution and IT control
Enterprise expectation:
- signed installers
- predictable upgrade behavior
- mirrorable artifacts for internal catalogs

CoDRAG posture:
- Direct installer rollout is the default.
- App store builds (if any) are a separate channel and not the enterprise contract path.

References:
- `docs/Phase11_Deployment/MACOS_DISTRIBUTION.md`
- `docs/Phase11_Deployment/WINDOWS_DISTRIBUTION.md`

### 2) Offline / air-gapped operation
Enterprise expectation:
- works without outbound internet

CoDRAG posture:
- License validation is **offline** via signed keys (Ed25519).

References:
- `docs/Phase11_Deployment/LICENSING_IMPLEMENTATION.md`
- `docs/Phase11_Deployment/ENTERPRISE_DISTRIBUTION_AND_LICENSING.md`

### 3) Governance and traceability
Enterprise expectation:
- policy enforcement
- auditability

CoDRAG posture:
- Team Tier introduces shared policy baseline (`team_config.json`).
- Enterprise adds stricter enforcement + audit surfaces.

### 4) Identity and access
Enterprise expectation:
- SSO/SCIM
- RBAC

CoDRAG posture:
- Post-MVP: start with API keys (Phase 06 network mode baseline).
- Later: SSO/SCIM integration if demanded.

## Capability matrix (truthful)

| Capability | Team | Enterprise | Notes |
| :--- | :--- | :--- | :--- |
| Shared config (`.codrag/team_config.json`) | Yes | Yes | Team: drift detection; Enterprise: strict enforcement |
| Embedded mode (`.codrag/` index) | Yes | Yes | Optional commit of index artifacts |
| Network mode (shared server) | Roadmap | Roadmap | Post-MVP implementation |
| Auth baseline | Roadmap | Roadmap | API keys first |
| Audit logging | Roadmap | Roadmap | Start with local log export |
| SSO/SCIM | No | Roadmap | Explicitly not MVP |
| Air-gapped licensing | Yes | Yes | Signed offline keys |

## Deployment patterns (enterprise-friendly)

### Pattern A: Managed laptops (no server)
- CoDRAG installed via MDM.
- License key deployed as a file.
- Team policy distributed via repo (`.codrag/team_config.json`).

Pros:
- Maximum "local-first" posture.
- No internal service to operate.

### Pattern B: Self-hosted team server (internal)
- CoDRAG daemon binds to LAN interface.
- Auth required.
- Reverse proxy terminates TLS (recommended initial posture).

Key constraint:
- The server must never expose arbitrary filesystem browsing.

Reference:
- `docs/Phase06_Team_And_Enterprise/README.md`

### Pattern C: Air-gapped enclave
- Signed installers delivered offline.
- License keys delivered via offline channel.
- BYOK augmentation may be disabled or restricted per policy.

## Audit logging (roadmap anchor)
Minimum viable audit logging should answer:
- who ran a query
- when
- against which project
- whether results/context were exported

Non-goals (initially):
- full content logging by default (may create privacy/compliance issues)

## Enterprise roadmap anchors (implementation sequence)

1. **Team shared config**
   - schema + drift detection + strict enforcement option
2. **Embedded mode hardening**
   - versioning, conflict detection, deterministic rebuild flow
3. **Network mode baseline**
   - safe-by-default bind rules
   - API key auth
   - project ID abstraction (no filesystem exposure)
4. **Audit export**
   - local append-only log
   - optional syslog integration later
5. **Identity integrations (optional)**
   - SSO/SCIM only if demanded by real enterprise pilots

## Open questions
- Do we need first-class TLS in the daemon, or is "reverse proxy terminates TLS" sufficient for early enterprise pilots?
- What is the minimum audit surface that satisfies real security reviews without logging sensitive content?
- Should Enterprise require `enforcement.mode = strict` for team config, or offer it as a Team feature?
