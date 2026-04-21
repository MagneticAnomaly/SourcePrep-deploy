# Git and Codebase Integration

## Purpose
This document defines how Prep should integrate with real customer codebases and Git workflows, including team onboarding.

This is not an implementation spec for Git features; it is a **workflow + constraints** guide.

## Core scenarios Prep must support
- Single repo (most common)
- Large monorepo (many languages/tools)
- Polyrepo workspace (multiple repos open at once)
- Repos with submodules

## Two index strategies (per ADR-003)
Prep supports:
- **Standalone mode (default)**: index stored in a central Prep data directory
- **Embedded mode**: index stored in `{project_root}/.runprep/`

Reference:
- `docs/DECISIONS.md` (ADR-003)

## Integration principles
- Treat indexes as **rebuildable artifacts**.
- Avoid creating Git foot-guns (watch loops, accidental commits, merge conflicts).
- Prefer explicit user choice over “magic automation” that mutates repos.

## MVP-friendly Git integration surface

### 1) Repo identification
When adding a project:
- If the provided path is inside a Git repository, Prep should treat the repo root as the “project root” (unless the user explicitly chooses a subdirectory).
- Display the repo name and mode (standalone vs embedded) in the dashboard.

### 2) Ignore patterns and watch exclusions
Defaults should avoid indexing noise:
- `.git/`
- dependency/vendor folders (e.g. `node_modules/`)
- build outputs
- `.runprep/` (always excluded from indexing and file watchers)

**Team Tier Note:** Enforcing shared ignore patterns across a team (via `.runprep/team_config.json`) is a paid feature.

Watch-loop avoidance requirement:
- Phase 06 explicitly requires watchers ignore `.runprep/**`.
- `docs/Phase06_Team_And_Enterprise/README.md`

### 3) Embedded mode onboarding workflow
Target “clone → instant search” (when `.runprep/index/**` is committed).

Flow:
1. Teammate clones repo.
2. Teammate runs `prep add . --embedded`.
3. Prep detects existing `.runprep/`.
4. If compatible, search is immediately available.

Reference:
- `docs/Phase06_Team_And_Enterprise/README.md`

### 4) Embedded mode commit policy
Prep should support both team choices:
- **Committed index** (fast onboarding)
- **Uncommitted index** (avoid repo bloat)

MVP recommendation (per Phase 06):
- Do not auto-commit.
- Provide explicit guidance on trade-offs.

Reference:
- Phase 06 “Commit policy (team choice)”.

### 5) Merge conflict handling for embedded indexes
If committed indexes are used, merges/conflicts are inevitable.

Rules (per Phase 06):
- If conflict markers exist anywhere inside `.runprep/index/**`, the index is invalid.
- Preferred remedy is a full rebuild.

Reference:
- `docs/Phase06_Team_And_Enterprise/README.md`

## Edge cases to plan for

### Large monorepos
Challenges:
- indexing time and storage
- many irrelevant paths
- language/tool diversity

Mitigations:
- strong include/exclude defaults
- per-project config editing in dashboard
- incremental rebuild (Phase 03)

### Submodules
Challenges:
- nested repos and checkout state

Approach:
- treat submodules as normal folders for indexing unless explicitly excluded
- allow users to add submodules as separate projects if desired

### Polyrepo workspaces
Common in real workflows:
- front-end repo + API repo + infra repo

Approach:
- Prep should make it cheap to register multiple projects.
- MCP “auto” mode should detect the correct project by cwd.

Reference:
- `docs/DECISIONS.md` (ADR-010 MCP)

## Guidance: when to choose embedded vs network mode

### Embedded mode is best when
- teams want portability via Git
- remote servers are hard to provision
- repos are small/medium

### Network mode is best when
- repos are huge
- teams don’t want index artifacts in Git
- centralized indexing is desired

Network mode constraints:
- no filesystem browsing for remote clients
- auth required for remote bind

Reference:
- `docs/Phase06_Team_And_Enterprise/README.md`

## Open questions
- Should Prep read `.gitignore` by default as an index exclude hint?
- Should embedded mode generate a `.runprep/` scaffold (`project.json`) via an explicit init command?
- Should CI build committed indexes (or should teams prefer network mode)?
