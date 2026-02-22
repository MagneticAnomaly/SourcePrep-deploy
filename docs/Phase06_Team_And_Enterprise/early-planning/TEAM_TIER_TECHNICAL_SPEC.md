# Team Tier — Technical Specification

## Purpose
Define the **Team Tier** (“Indexed Harmony”) as an implementable, testable feature set.

This spec turns the Phase 06 README into concrete requirements for:
- **Shared configuration** (`.codrag/team_config.json`)
- **Policy enforcement / drift detection**
- **Team-safe onboarding behavior** (embedded index optional; config always safe to commit)

## Scope

### In scope (Team Tier)
- `.codrag/team_config.json` schema and semantics
- Import/apply behavior (CLI + dashboard)
- Drift detection (local project settings vs team baseline)
- Policy enforcement modes (warn vs strict)

### Out of scope (Team Tier)
- Network mode / shared server deployment (covered by Phase 06 + Roadmap; post-MVP implementation)
- SSO/SCIM/RBAC
- Hard online seat counting enforcement (license server)

## Positioning / value contract
The Team Tier exists to solve one problem:

**Every developer on the team must build and query the same index, with the same scoping rules, so results are reproducible across people and machines.**

## Key artifact: `.codrag/team_config.json`

### File location
- Repo-relative path: `{project_root}/.codrag/team_config.json`

Rationale:
- Small, human-reviewable, and safe to commit.
- Lives alongside embedded index artifacts, but is logically separate from the index.

### Versioning
The file MUST include a format version.

- `format_version`: integer, starting at `1`.

### Schema (v1)
```json
{
  "format_version": 1,
  "generated_at": "2026-01-31T00:00:00Z",
  "generated_by": {
    "codrag_version": "0.1.0",
    "source": "dashboard" 
  },
  "enforcement": {
    "mode": "warn" 
  },
  "policy": {
    "include_globs": [],
    "exclude_globs": [
      ".git/**",
      ".codrag/**",
      "**/node_modules/**",
      "**/dist/**",
      "**/build/**",
      "**/.env",
      "**/.env.*",
      "**/*secret*",
      "**/*secrets*"
    ]
  },
  "features": {
    "trace_enabled_default": false
  },
  "models": {
    "embedding_model": "nomic-embed-text",
    "embedding_provider": "ollama"
  }
}
```

### Field semantics

#### `enforcement.mode`
- `warn`:
  - Apply the team config as the default baseline.
  - Allow local overrides.
  - UI MUST surface drift clearly.
- `strict`:
  - Team config becomes authoritative.
  - Local overrides that weaken policy MUST be blocked.
  - Local overrides that are strictly more restrictive MAY be allowed.

Default recommendation:
- `warn` for Team (fast adoption).
- `strict` is more appropriate for Enterprise governance.

#### `policy.include_globs`
- If empty: index is "include everything not excluded".
- If non-empty: only paths matching at least one include glob are indexable.

#### `policy.exclude_globs`
- Unioned with hard-coded safety excludes:
  - `.git/**`
  - `.codrag/**`
- In `strict` mode, the user MUST NOT be able to remove team-provided excludes.

#### `features.trace_enabled_default`
- Controls the default project-level trace setting.
- License gating still applies:
  - If the user does not have a Pro-or-higher license, trace remains unavailable even if the config defaults it on.

#### `models.*`
- Provides an organization-default embedding configuration.
- MUST NOT include API keys or secrets.
- If the selected provider requires credentials, those are supplied per-user via local settings.

## Application behavior

### Detection
When adding or opening a project, CoDRAG MUST detect `.codrag/team_config.json` if present.

### Apply rules
1. Parse JSON.
2. Validate `format_version` is supported.
3. Compute a stable hash of the normalized JSON (canonical ordering) and store it as the "applied config hash" in project state.
4. Apply the config baseline to the project settings.

### Drift detection
Drift is defined as any difference between:
- the current effective project settings, and
- the settings derived from the last applied team config

The dashboard MUST show:
- Team config present: yes/no
- Enforcement mode: warn/strict
- Drift status: clean/drifted
- Last applied hash

### Override policy
- In `warn` mode:
  - All overrides are allowed.
  - UI MUST show "Your config differs from team baseline".
- In `strict` mode:
  - Any override that *reduces* exclusions or expands indexing scope MUST be rejected.
  - Adding additional excludes is allowed.

## CLI requirements (Team Tier)
Minimum commands:
- `codrag config export --team`:
  - Writes `.codrag/team_config.json`.
  - Requires a Team/Enterprise license.
- `codrag config validate --team-config <path>`:
  - Validates schema + prints warnings.

## Dashboard requirements (Team Tier)
Minimum UI surfaces:
- Project Settings panel:
  - Show team config detection and enforcement mode.
  - Button: "Export Team Config" (Team/Enterprise only).
  - Button: "Re-apply Team Config".
  - Drift indicator.

## Test plan / acceptance criteria

### 1) Reproducible onboarding
- Given a repo with `.codrag/team_config.json` committed,
- When a teammate clones and adds the repo,
- Then indexing scope matches the team baseline without manual configuration.

### 2) Strict mode blocks weakening
- Given `enforcement.mode = strict`,
- When a user attempts to remove an excluded path,
- Then CoDRAG blocks the change and explains why.

### 3) `.codrag/**` is always excluded
- Even if team config is missing or malformed,
- `.codrag/**` MUST be excluded from indexing and file watchers.

## Open questions
- Should we support `required_exclude_globs` as a first-class field (vs treating all excludes as required in strict mode)?
- Should team config support a `repo_root_hint` or rely exclusively on Git repo detection?
- Should drift detection be calculated from normalized config or via explicit per-field compare?
