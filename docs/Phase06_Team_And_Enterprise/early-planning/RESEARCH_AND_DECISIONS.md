# Phase 06 — Research & Decisions (Team & Enterprise)

## Purpose
Capture the research outcomes and decision points required to implement Phase 06 later, without writing production code yet.

This phase is **post-MVP implementation** per ADR-012. These decisions exist to avoid architectural dead-ends and to provide an implementation-ready starting point.

## References (existing Phase 06 artifacts)
- `README.md` (Phase 06 spec)
- `TEAM_TIER_TECHNICAL_SPEC.md` (team config schema + semantics)
- `ENTERPRISE_POSTURE_AND_ROADMAP.md` (enterprise posture, deployment patterns)
- `MARKETING_AND_COMMUNICATION.md` (tier framing; do-not-overpromise rules)

Cross-phase anchors:
- `../API.md` (auth header + response envelope + redaction note)
- `../DECISIONS.md` (ADR-003 embedded mode; ADR-012 MVP boundary)
- `../Phase10_Business_And_Competitive_Research/GIT_AND_CODEBASE_INTEGRATION.md`

---

## Decision ledger (draft)
These are defaults to implement unless later superseded.

- **D06-01 (Commit policy default):** `.codrag/team_config.json` is safe to commit by default; `.codrag/index/**` is **explicit opt-in**.
- **D06-02 (TLS posture for network mode):** initial network-mode posture assumes **TLS termination via reverse proxy**; daemon does not ship built-in TLS initially.
- **D06-03 (Remote bind safety):** binding to any non-loopback interface requires auth; daemon refuses unsafe startup unless explicit override.

---

## P06-R1: Embedded mode behavior

### Goals
- Make a project’s index **portable** and **repeatable** for teams.
- Preserve local-first invariants while allowing an optional “committed index” workflow.

### Directory layout (authoritative)
In embedded mode, all repo-local CoDRAG artifacts live under:
- `{project_root}/.codrag/`

Recommended layout:
- `.codrag/`
  - `team_config.json` (team policy baseline; safe to commit)
  - `project.json` (optional; embedded-mode metadata)
  - `index/` (index artifacts; may be committed depending on team choice)
    - `manifest.json`
    - `documents.json`
    - `embeddings.npy`
    - `fts.sqlite3` (optional)
    - `trace_manifest.json` (optional)
    - `trace_nodes.jsonl` (optional)
    - `trace_edges.jsonl` (optional)

Notes:
- The index artifacts must remain **rebuildable**.
- The directory layout intentionally mirrors the Phase 01/04 on-disk formats (STR-03).

### What can be committed
- Safe to commit:
  - `.codrag/team_config.json`
  - `.codrag/project.json` (if introduced; must remain secret-free)
- Optional to commit (team choice):
  - `.codrag/index/**`

Decision constraints:
- CoDRAG must never auto-commit index artifacts.
- UI/CLI should provide explicit trade-off guidance (repo size/merge conflict pain vs onboarding speed).

### Compatibility and versioning behavior
Embedded mode must detect when a committed index is unusable.

Minimum metadata requirements:
- `manifest.json` MUST include:
  - `format_version` (integer)
  - `codrag_version` (string)
  - `embedding_model` (string)

Compatibility rules:
- If `format_version` is unsupported:
  - mark index state as `incompatible`
  - do not silently ignore
  - remediation is deterministic: “Full rebuild required”

Future-proofing (not required initially):
- allow “read old format, write new format” upgrade when safe

### Embedded index states
These should be user-visible as stable states:
- `missing`
- `ok`
- `incompatible`
- `conflicted`
- `corrupted`

---

## P06-R2: Merge conflict and corruption handling (committed indexes)

### Merge conflict detection
Rule:
- If git merge conflict markers exist anywhere inside `.codrag/index/**`, treat the index as **invalid**.

Markers:
- `<<<<<<<`
- `=======`
- `>>>>>>>`

Behavior:
- Surface status: `conflicted`
- Provide remediation: full rebuild

Rationale:
- Index artifacts are rebuildable; merging them is brittle and not worth the UX complexity.

### Corruption detection
Corruption means “index artifacts exist but cannot be trusted/loaded.”

Minimum checks:
- required files exist (`manifest.json`, `documents.json`, `embeddings.npy`)
- `manifest.json` parses as JSON object
- `documents.json` parses as JSON list
- `embeddings.npy` loads successfully

If any check fails:
- Surface status: `corrupted`
- Remediation: full rebuild

---

## P06-R3: Network mode security baseline

### Binding defaults
- Default bind: `127.0.0.1` (local-only)
- “Remote bind” means binding to:
  - `0.0.0.0`, or
  - a LAN IP, or
  - any non-loopback interface

### Auth required rules
Per `../API.md`:
- In network/team mode, authentication is required for all endpoints except `GET /health`.
- Standard header:
  - `Authorization: Bearer <api_key>`

Safety requirement:
- Remote-bind mode **must refuse startup** if auth is not configured, unless an explicit override is provided.

### Threat model assumptions (explicit)
- Network mode is intended for a trusted network boundary (LAN/VPN) initially.
- Assume TLS is provided by a reverse proxy for early deployments (D06-02).
- The daemon must not expose arbitrary filesystem browsing.

Primary risks to mitigate:
- accidental unauthenticated remote exposure
- leakage of server filesystem paths via errors/status
- expansion of server-side attack surface via “browse” endpoints

---

## P06-R4: Onboarding UX for team mode (CLI + dashboard)

### Personas
- Team lead/admin: sets team baseline policy, optionally builds/commits embedded index.
- Teammate: clones repo and expects minimal setup.

### Flow A: Embedded index committed (fast onboarding)
1. Team lead:
  - create `.codrag/team_config.json`
  - build index into `.codrag/index/`
  - optionally commit `.codrag/index/**`
2. Teammate:
  - clone repo
  - add project in embedded mode
  - CoDRAG detects existing embedded index
  - if compatible + not conflicted: search is immediately available
  - otherwise: show status + offer full rebuild

### Flow B: Embedded mode without committed index (policy-only)
1. Team lead commits only `.codrag/team_config.json`
2. Teammate clones repo and adds project
3. CoDRAG applies team policy baseline
4. Build is required (but consistent across teammates)

### Flow C: Network mode (shared server) (post-MVP implementation)
1. Operator starts daemon in remote-bind mode with auth.
2. Teammate connects via dashboard/Tauri.
3. Teammate searches without local indexing.

### UX surfaces required (later)
Dashboard:
- Embedded index status badge: `ok/missing/incompatible/conflicted/corrupted`
- Team config presence + enforcement mode + drift indicator
- “Rebuild” action for incompatible/conflicted/corrupted

CLI:
- `codrag add <path> --embedded`
- `codrag config export --team`
- `codrag config validate --team-config <path>`

---

## Notes / blockers
- Commit guidance (D06-01) should be reflected as:
  - documentation templates
  - UI copy
  - optionally: a `.gitignore` snippet generator
- TLS posture (D06-02) should be reflected as:
  - a “reverse proxy required for Internet exposure” warning
  - no claim that daemon is hardened for public Internet by default
