# Phase 06 — Team & Enterprise
 
## Problem statement
CoDRAG becomes dramatically more valuable when it supports team workflows: shared onboarding, repeatable indexing, and (optionally) a central server. Without a team story, adoption stalls at “personal tool” and breaks in real org environments.

From a business perspective, the **Team Tier ($15/seat/mo)** monetizes "Indexed Harmony"—ensuring every developer on the team has the exact same context configuration.

## Goal
Support team workflows as first-class: shared configurations, embedded indexes, network mode, and auth.

**Note:** This phase is **post-MVP implementation**. MVP incorporates team/enterprise requirements as **UX case studies and guardrails** (see `../WORKFLOW_RESEARCH.md` and ADR-012), but does not ship network-mode deployment, auth, or admin UX as implemented features.

## Scope
### In scope
- Embedded mode (`.codrag/` directory inside a repo)
- Network mode (daemon accessible to other machines)
- Basic authentication (API keys)
- Team onboarding flow (clone repo → add project → search)

### Out of scope
- Full RBAC and SSO integrations (post-MVP)
- Advanced compliance/audit features (post-MVP)
 
## Derived from
- `docs/ROADMAP.md`
- `docs/ARCHITECTURE.md`
 
## Deliverables
- **Shared Configuration** (Team Tier feature: export/import policies)
- Embedded mode (`.codrag/` in repo)
- Network mode (remote server)
- API key authentication
- Team onboarding workflow

## Artifact set
- [TEAM_TIER_TECHNICAL_SPEC.md](TEAM_TIER_TECHNICAL_SPEC.md)
- [ENTERPRISE_POSTURE_AND_ROADMAP.md](ENTERPRISE_POSTURE_AND_ROADMAP.md)
- [MARKETING_AND_COMMUNICATION.md](MARKETING_AND_COMMUNICATION.md)

## Functional specification

### Shared Configuration (Team Tier)
This feature allows teams to enforce consistent indexing rules across all developer machines.

- **Artifact:** `.codrag/team_config.json`
- **Scope:**
  - `include/exclude` patterns (e.g. "Always ignore /secrets")
  - `trace_enabled` defaults
  - `embedding_model` standardization
- **Workflow:**
  - Admin runs `codrag config export` to generate the file.
  - Developers' clients detect the file and apply settings (with override warnings).

### Embedded mode (`.codrag/`)

Embedded mode exists to make a project’s index **portable** and **repeatable** for teams.

#### Directory layout

In embedded mode, the project’s index lives at:

- `{project_root}/.codrag/`

Recommended structure:

- `.codrag/`
  - `project.json` (or equivalent) — minimal metadata about the embedded index
  - `index/`
    - `manifest.json`
    - `documents.json`
    - `embeddings.npy`
    - `trace_manifest.json` (optional)
    - `trace_nodes.jsonl` (optional)
    - `trace_edges.jsonl` (optional)

The embedded index should be treated as **rebuildable**. Any file not strictly required for reuse can be regenerated.

#### Compatibility and versioning

- Embedded indexes must include a `format_version` and should record the CoDRAG version used to build.
- If CoDRAG detects an incompatible `format_version`, it must:
  - mark the index as “incompatible” (not silently ignored)
  - offer a deterministic remedy: “Rebuild index” (full rebuild)

#### Commit policy (team choice)

CoDRAG should support both workflows:

- **Committed index** (fast onboarding): `.codrag/index/**` is committed to git.
- **Uncommitted index** (avoid repo bloat): `.codrag/` exists locally but is gitignored.

Default recommendation for MVP:
- Do not auto-commit.
- Provide explicit guidance in the dashboard/CLI on the trade-offs (size vs onboarding speed).

If `.codrag/index/**` is committed:
- Expect merges/conflicts; treat the index as a build artifact.
- The “source of truth” remains the repo; the index can always be rebuilt.

#### Merge conflicts and corruption handling

Rules:
- If git merge leaves conflict markers anywhere inside `.codrag/index/**`, the index is considered invalid.
- CoDRAG should surface a clear status:
  - “Embedded index has merge conflicts; rebuild required.”
- Preferred remediation:
  - delete the conflicted index files and run a full rebuild.

#### Watch-loop avoidance

- In embedded mode, watchers must ignore `.codrag/**` (Phase 03).
- Builds must not touch any files inside the watched source tree other than `.codrag/**`.

### Network mode (team server)

Network mode makes the daemon accessible to other machines.

#### Binding defaults and foot-gun prevention

Defaults:
- Local mode binds to `127.0.0.1`.

To enable remote access, the operator must explicitly bind to a non-loopback interface.

Safety requirements:
- If binding to `0.0.0.0` (or any non-loopback interface), CoDRAG must require authentication.
- CoDRAG should refuse to start in remote-bind mode without auth unless a clearly named explicit override is provided (not recommended).

Dashboard requirements:
- If the server is in remote-bind mode, the UI must show a persistent “Remote mode” indicator.

#### Authentication (API keys)

Baseline authentication should be API-key based.

Header choice (pick one and standardize):
- `Authorization: Bearer <api_key>`

Behavior:
- In local-only mode, auth is optional.
- In remote-bind mode, auth is required for all endpoints except `GET /health`.

Error shapes:
- `UNAUTHORIZED` (missing/invalid key)
- `FORBIDDEN` (valid key but insufficient permission; can be future)

Key management (MVP baseline):
- Keys may be configured in a local config file on the server.
- Rotation should be supported by restart (dynamic rotation can be post-MVP).

#### Remote usage model

In network mode, clients typically:
- run the dashboard (served by the same daemon, or via Tauri in Phase 08)
- interact with projects registered on the server

Constraints:
- The server must never expose arbitrary filesystem browsing.
- Project paths are server-private; clients see only project IDs, names, and status.

### Analytics / telemetry posture (Team/Enterprise)

- **No mandatory telemetry**: Enterprise deployments may be air-gapped; analytics must be optional.
- **Customer-hosted server reality**: when customers self-host a team server, CoDRAG should assume limited visibility into usage.
- **Audit vs analytics**:
  - Analytics should be aggregated counters (build outcomes, error codes) and must not include code or raw queries by default.
  - Audit logging (roadmap) is a separate feature and must be explicit about what is recorded.
- **Seat enforcement**:
  - Strict online seat counting requires a license server and is out of scope for MVP.
  - Team/Enterprise posture relies on signed offline license keys and legal enforcement for seat counts.

### Team onboarding flows

#### Flow A: Embedded index committed

1. Team lead:
   - enables embedded mode for the repo
   - builds the index
   - (optionally) commits `.codrag/index/**`
2. Teammate:
   - clones the repo
   - runs `codrag add . --embedded`
   - CoDRAG detects existing `.codrag/` and immediately enables search
3. If the embedded index is missing or incompatible:
   - CoDRAG marks project as “needs rebuild” and offers one-click rebuild

#### Flow B: Shared server

1. Operator runs the daemon in remote-bind mode with API key auth.
2. Teammate connects via browser/Tauri app.
3. Teammate can search/context/trace without local indexing.

### Minimal API expectations

These extend the Phase 02 dashboard contract.

- All endpoints accept the auth header in network mode.
- Status endpoints should include enough info to render “team-safe” UI:
  - `server`: `{mode: "local"|"remote", requires_auth: bool}`
  - `project.mode`: `standalone|embedded`
  - `project.index_location`: omitted or redacted in remote mode

## Success criteria
- A teammate can clone a repo and get an index with minimal friction (embedded or server mode).
- Network mode is safe enough for a trusted LAN deployment (auth required, no accidental exposure).
- Embedded mode does not accidentally rebuild endlessly by watching its own output.

## Research deliverables
- Embedded-mode rules: what files exist, what can be committed, and how conflicts are handled
- Network-mode security baseline (binding defaults, auth, threat model assumptions)
- Minimal operational docs (how teams deploy, upgrade, and troubleshoot)

## Dependencies
- Phase 01 (core engine + persistence)
- Phase 02 (dashboard onboarding UX)

## Open questions
- Should `.codrag/` be committed by default or treated as optional/explicit
- How merge conflicts in `.codrag/` are detected and resolved (rebuild vs merge)
- Whether network mode must support TLS in MVP or can defer to reverse proxy

## Risks
- Security foot-guns (accidentally binding to 0.0.0.0 without auth)
- Git merge conflicts and index corruption in embedded mode

## Testing / evaluation plan
- Embedded mode test: create `.codrag/`, commit, clone elsewhere, verify instant search
- Network mode test: remote client can query with API key; cannot query without it

## Research completion criteria
- Phase README satisfies `../PHASE_RESEARCH_GATES.md` (global checklist + Phase 06 gates)
