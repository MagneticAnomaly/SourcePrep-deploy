# Phase 06 — Implementation Plan (Deferred Build)

## Purpose
Provide an implementation-ready blueprint for Phase 06 without building it yet.

This plan is written to be executed later as post-MVP work (ADR-012).

## Scope mapping (Phase06 TODO)
This document covers:
- `P06-I1`–`P06-I9`

Research backing:
- `RESEARCH_AND_DECISIONS.md` (`P06-R1`–`P06-R4`)

Test plan:
- `TEST_PLAN.md` (`P06-T1`–`P06-T3`)

---

## Implementation prerequisites (must already exist)
- Stable on-disk index formats (Phase01)
- Stable API response envelope + error code taxonomy (STR-01)
- Stable watcher behavior that always excludes `.codrag/**` (STR-06)

---

## Shared configuration (Team Tier)

### P06-I1 Define `.codrag/team_config.json` schema (secret-free)
Source of truth:
- `TEAM_TIER_TECHNICAL_SPEC.md` (schema v1 + semantics)

Implementation notes:
- Treat `.codrag/team_config.json` as **repo-owned** configuration.
- Must remain **secret-free**; no API keys or tokens.
- Must be hashable with a stable canonicalization strategy.

Required capabilities:
- Parse + validate:
  - JSON is an object
  - `format_version` supported
  - enforcement mode is known
- Canonicalize + hash:
  - canonical JSON serialization (stable key ordering, no whitespace)
  - store `team_config_hash` in project state

Outputs:
- A normalized internal representation used as an input to config merging.

### P06-I2 Config merge precedence rules
Precedence order (authoritative):
- defaults → global → team → project overrides

Definitions:
- **defaults**: hard-coded safe defaults shipped with CoDRAG
- **global**: user/machine-wide preferences (local file or registry settings)
- **team**: `.codrag/team_config.json`
- **project overrides**: explicit per-project settings stored in the registry

Non-overridable safety baseline:
- `.git/**` must always be excluded
- `.codrag/**` must always be excluded

Proposed merge behavior (initial):
- `include_globs`:
  - if team supplies non-empty includes in strict mode, effective includes are constrained to that set
  - in warn mode, team includes become defaults but can be expanded by project overrides
- `exclude_globs`:
  - effective excludes = union of
    - safety excludes
    - team excludes
    - project excludes
  - in strict mode, project cannot remove team excludes

Model configuration merge:
- Team config sets org default embed provider/model.
- In warn mode: project may override but drift is surfaced.
- In strict mode: project override is rejected.

### P06-I3 Config provenance reporting plan (UI/diagnostics)
Goal:
- For each effective config value, be able to explain *where it came from*.

Minimum provenance sources:
- `default`
- `global`
- `team`
- `project`
- `safety` (non-overridable baseline)

Recommended representation:
- `effective_config`: the merged config used by builds
- `provenance`: per-field source + optional explanation

Example shape (illustrative):
- `effective.exclude_globs`: array
- `provenance.exclude_globs`: `{source: "union", contributors: ["safety", "team", "project"]}`

UI requirements (later):
- Show team config detection + enforcement mode
- Show drift status + “what differs” summary

---

## Embedded mode

### P06-I4 Embedded index directory layout aligned with Phase01 formats
Source of truth:
- `RESEARCH_AND_DECISIONS.md` (Embedded layout)
- `docs/ARCHITECTURE.md` (storage layer)

Implementation contract:
- `mode=embedded` means the index root is:
  - `{project_root}/.codrag/index/`

Notes:
- `.codrag/team_config.json` is adjacent to the index dir (repo-owned).
- `.codrag/index/**` may or may not be committed.

### P06-I5 Incompatible index detection and remediation UX
States:
- `missing`
- `ok`
- `incompatible`
- `conflicted`
- `corrupted`

Detection algorithm (minimum):
- If `.codrag/index/` missing → `missing`
- If conflict markers found in `.codrag/index/**` → `conflicted`
- Else attempt to load required artifacts → if failure → `corrupted`
- Else if manifest `format_version` unsupported → `incompatible`
- Else → `ok`

Remediation:
- Always “Full rebuild required” for `incompatible/conflicted/corrupted`

### P06-I6 Watch-loop avoidance requirements
Hard rule:
- Watchers must always ignore `.codrag/**`.

Implementation note:
- Ensure `.codrag/**` ignore exists even when:
  - no team config exists
  - repo policy is missing
  - embedded mode is disabled

---

## Network mode

### P06-I7 Remote bind requires auth; refuse unsafe startup unless explicit override
Bind modes:
- Local-only (default): bind to `127.0.0.1`
- Remote-bind: bind to `0.0.0.0` or non-loopback interface

Startup safety rules:
- If remote-bind and auth is not configured:
  - refuse to start
  - require an explicit override to bypass (not recommended)

### P06-I8 Auth header standardization
Source of truth:
- `docs/API.md`

Standard header:
- `Authorization: Bearer <api_key>`

Implementation:
- Add request authentication middleware for all endpoints except `GET /health`.

API key storage (baseline):
- local server config file (secret-bearing, not committed)
- rotation via restart (dynamic rotation can come later)

### P06-I9 Remote-mode redaction rules
Rule:
- Remote clients must not learn server filesystem paths.

Redaction requirements:
- Project listing/detail endpoints:
  - omit or redact `project.path`
- Error envelopes:
  - avoid embedding absolute paths in `error.message`, `error.hint`, or `error.details`
- Logs/diagnostics surfaced to clients:
  - must not include absolute paths

Acceptable leakage:
- repo-relative paths in search results (e.g. `src/foo.py`) are acceptable.

---

## Rollout milestones (suggested)
- Milestone 1: Team config parsing + hashing + drift detection (warn mode)
- Milestone 2: Provenance representation + UI surfaces
- Milestone 3: Embedded mode index state detection + remediation UX
- Milestone 4: Network-mode auth middleware + remote-bind safety
- Milestone 5: Remote-mode redaction hardening + regression tests
