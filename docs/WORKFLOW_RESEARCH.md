# Prep Workflow Research (Cross-Phase)

This document defines:

- user archetypes
- explicit journey maps (end-to-end workflows)
- acceptance criteria per archetype
- hard MVP boundaries
- enterprise UX case studies (design-only)

It is intended to keep Phase01–Phase13 planning aligned around real user workflows.

## Definitions

- **MVP**: The first product release that reliably supports the core single-user, local-first loop (add → build → search → context) with a dashboard and IDE tooling.
- **Enterprise**: Features primarily required by organizations to deploy to teams at scale (network mode, auth, admin UX, audit). **Enterprise is not in MVP scope** (implementation). We still maintain enterprise UX case studies to guide future work.
- **Journey map**: A step-by-step workflow describing a user’s intent, actions, system responses, and success conditions.

## Hard MVP boundaries

### MVP in-scope (must ship)

- **Local-first daemon** with stable HTTP API (`API.md`).
- **Project management**: add/list/remove projects.
- **Index lifecycle**: build (incremental + full), status, predictable recovery.
- **Search + context**:
  - semantic search results with inspectable chunks
  - context assembly with citations and bounded outputs
- **Dashboard (Phase02)** using Tremor:
  - project list + tabs
  - status/build UX
  - search + chunk viewer
  - context UI
  - settings UI (include/exclude + model endpoints)
- **AutoRebuild (Phase03)**: optional per-project watcher + staleness UI.
- **TraceIndex (Phase04)**: optional, Python-focused MVP (symbol extraction + bounded neighbors); no full graph UI.
- **MCP (Phase05)**: local IDE integration (status/build/search/context; trace where available).
- **Polish baseline (Phase07)**:
  - stable errors with codes + actionable hints
  - integration tests for the core loop
- **Tauri wrapper (Phase08)**: desktop packaging that launches and monitors the daemon.

### MVP out-of-scope (hard exclusions)

- **Enterprise/team deployment features (implementation)**:
  - remote network mode as a supported deployment target
  - user management / admin UI
  - RBAC / SSO (OIDC/SAML)
  - audit logs and compliance features
- **Multi-tenant server behavior** (isolating multiple users on one daemon).
- **Cloud/managed services**.
- **Cross-project search by default**.
- **Full interactive graph visualization**.

### MVP “trust invariants” (non-negotiable)

- The user must always be able to answer:
  - “Am I looking at the right project?”
  - “Is it fresh?”
  - “Can I verify it?”
- Outputs are bounded:
  - context assembly respects `max_chars`
  - trace expansion has strict node/edge caps
- **Feature Gates are Enforced:**
  - Free tier users cannot add >2 projects.
  - Free tier users cannot enable Trace Index.
- Failure modes are actionable:
  - stable `error.code`
  - a recommended `hint`

## Archetypes

### A0) Prospective adopter (evaluation + installation)

- **Environment**: public docs/website, GitHub, word-of-mouth.
- **Primary goal**: understand what Prep does, trust the local-first posture, and successfully try it.
- **Primary risk**: unclear onboarding, unclear security posture, unclear “what is local vs remote”.

### A1) Solo developer (local-first)

- **Environment**: laptop, one or a few repos, iterative development.
- **Primary goal**: accelerate understanding and answering code questions.
- **Primary risk**: stale index / wrong repo / low trust.

### A2) Staff engineer / tech lead (multi-repo + onboarding)

- **Environment**: multiple repos, higher correctness expectations, onboarding others.
- **Primary goal**: repeatable “source of truth” about system behavior.
- **Primary risk**: opaque index state + nondeterministic results.

### A3) IDE agent user (MCP consumer)

- **Environment**: Cursor/Windsurf-style agent loops.
- **Primary goal**: fast, bounded context retrieval with citations.
- **Primary risk**: runaway latency / oversized context / unstable schemas.

### A4) Security/ops-conscious user

- **Environment**: regulated orgs or security-first teams.
- **Primary goal**: ensure local-only behavior and prevent accidental exposure.
- **Primary risk**: accidental network exposure; paths/data leaking in errors.

### A5) Enterprise admin (design-only; post-MVP)

- **Environment**: IT/security/platform teams.
- **Primary goal**: controlled rollout with authentication and governance.
- **Primary risk**: unmanaged access, unclear auditability.

## Journey maps + acceptance criteria

### Journey map coverage by phase

This table is the “planning spine” for Phase01–Phase10. A phase is considered successful if it improves at least one journey map without breaking MVP boundaries.

| Phase | Primary journeys enabled | Notes |
|------:|---------------------------|-------|
| Phase01 | A1-J1, A2-J2, A4-J1 | Core correctness + persistence + error codes |
| Phase02 | A1-J1/J2/J3, A2-J1, A4-J1 | Trust console UX using Tremor |
| Phase03 | A1-J4 | Freshness loop via watcher + debounce |
| Phase04 | A1-J5, A3-J3 | Structural questions via trace (bounded) |
| Phase05 | A3-J1/J2 | IDE agent workflows via MCP |
| Phase06 | E1/E2/E3 | Enterprise/team flows are design-only (post-MVP implementation) |
| Phase07 | All journeys | Reliability, recovery, testing, perf envelope |
| Phase08 | A4-J2, A1-J1 | Desktop packaging + sidecar lifecycle |
| Phase09 | Process support | Prevent post-MVP scope creep; enforce specs |
| Phase10 | Process support | Business/competitive loop into roadmap/ADRs |
| Phase11 | A0-J2, A4-J2 | Release engineering / deployment planning |
| Phase12 | A0-J1/J2 | Public docs, onboarding, positioning |
| Phase13 | All journeys | UI consistency via design system + Storybook |

### A0 Journey 1 — Evaluate Prep and decide to try it (Phase12)

Steps:

1. User lands on the website or docs.
2. User understands what Prep does (search/context/trace/MCP).
3. User confirms local-first posture (what is stored locally, what is never uploaded).
4. User follows a “Getting started” flow.
5. User successfully reaches the first trust loop (A1-J1).

Acceptance criteria:

- **Clarity**
  - The docs explain the core loop in <5 minutes.
- **Security posture**
  - Local-only default is explicit.
  - Network mode is clearly labeled as post-MVP implementation.
- **Consistency**
  - Docs match the dashboard terminology (project, build, stale, context).

### A0 Journey 2 — Download, upgrade, and recover (Phase11–12)

Steps:

1. User downloads the installer.
2. User installs and launches the app.
3. User upgrades to a newer version later.
4. User’s projects and indexes persist.

Acceptance criteria:

- **Persistence**
  - Registry + config persist across upgrades.
- **Recovery**
  - If an index format becomes incompatible, the UI clearly indicates rebuild required.

### A1 Journey 1 — First-run trust bootstrap (Phase01–02)

Steps:

1. User starts the daemon (CLI or Tauri).
2. User adds a project (UI or CLI).
3. User triggers build and watches status.
4. User runs a search for a known term.
5. User opens a result and verifies file/span.
6. User generates context and copies it.

Acceptance criteria:

- **Correct project confirmation**
  - UI shows the project name and path clearly.
- **Build clarity**
  - UI shows `building` state and last successful build timestamp.
- **Inspectability**
  - A search result can be opened to show full chunk text + source path + span.
- **Bounded context**
  - Context output is `<= max_chars` and includes citations.

Hard non-goals:
- No “magic” background indexing without explicit user intent (Phase03 is opt-in).

### A1 Journey 2 — Daily usage: fast context for an LLM (Phase02)

Steps:

1. User types a question.
2. User reviews top results.
3. User assembles context with default settings.
4. User copies context into an LLM.

Acceptance criteria:

- **Speed**
  - Hot search is responsive enough for iterative use.
- **Citations**
  - Context output shows clear per-chunk citation headers.
- **Usability**
  - Copy-to-clipboard is reliable.

### A1 Journey 3 — “Why is it wrong?” debugging (Phase02–03–07)

Steps:

1. User notices stale/wrong results.
2. User checks project status.
3. User inspects include/exclude settings.
4. User triggers full rebuild.

Acceptance criteria:

- **Staleness surfaced**
  - The UI clearly indicates stale vs fresh.
- **Recovery path**
  - Full rebuild is available and clearly labeled.
- **Actionable errors**
  - If Ollama is missing/unreachable, UI points the user to settings and/or a test button.

### A1 Journey 4 — Auto-rebuild freshness loop (Phase03)

Steps:

1. User enables auto-rebuild for a project.
2. User edits a file.
3. UI shows the project as stale.
4. After debounce, rebuild triggers.
5. UI returns to fresh state and search results reflect the change.

Acceptance criteria:

- **No rebuild storms**
  - Rapid edits are coalesced into a single rebuild.
- **Stale signal is fast**
  - UI indicates staleness quickly (seconds).
- **Loop avoidance**
  - Watcher ignores index output directories (including `.runprep/**` in embedded mode).

### A1 Journey 5 — Structural question with trace-assisted context (Phase04)

*Note: This journey requires a **Pro License**.*

Steps:

1. User enables trace for a project and builds.
2. User asks a structural question (e.g., “where is the entry point?”).
3. User generates context with trace expansion enabled.
4. User validates citations and spans.

Acceptance criteria:

- **Graceful fallback**
  - If trace is disabled/missing, context still works (without trace expansion).
- **Bounded expansion**
  - Trace expansion honors caps (nodes/edges/chars) and cannot explode output size.
- **Trust**
  - Added trace-derived chunks are clearly cited.

### A2 Journey 1 — Multi-project switching (Phase02)

Steps:

1. User adds multiple repos.
2. User opens multiple tabs.
3. User switches projects and searches within each.

Acceptance criteria:

- **Isolation**
  - Searches and contexts are always scoped to the active project.
- **State persistence**
  - Open tabs persist across refresh.

### A2 Journey 2 — Reproducible index configuration (Phase01–02)

Steps:

1. User sets include/exclude globs.
2. User rebuilds.
3. User verifies predictable file coverage.

Acceptance criteria:

- **Config determinism**
  - Project settings are persisted and reflected in subsequent builds.
- **Index transparency**
  - Status shows basic counts (files/chunks) and last build time.

### A3 Journey 1 — IDE agent loop via MCP (Phase05)

Steps:

1. Agent calls `prep_status`.
2. Agent calls `prep_search` or `prep`.
3. Agent consumes the returned context.

Acceptance criteria:

- **Stable tool schemas**
  - Tool inputs/outputs match `Phase05_MCP_Integration/README.md` and `API.md` mappings.
- **Bounded outputs**
  - Default `max_chars` is conservative; hard max caps exist.
- **Actionable errors**
  - If daemon is down, MCP returns `DAEMON_UNAVAILABLE` with a clear hint.

### A3 Journey 2 — Agent-driven “build if needed” (Phase01 + Phase05)

Steps:

1. Agent calls `prep_status`.
2. If the project index is missing/stale, agent calls `prep_build`.
3. Agent polls `prep_status` until `building=false` (or receives `BUILD_ALREADY_RUNNING`).
4. Agent calls `prep` with bounded defaults.

Acceptance criteria:

- **Idempotence**
  - If a build is already running, agent can proceed without error storms.
- **Bounded latency**
  - Status calls are cheap and safe to poll.
- **Schema stability**
  - The agent does not need to special-case response shapes across versions.

### A4 Journey 1 — Local-only assurance (Phase01–02–08)

Steps:

1. User installs/runs Prep.
2. User verifies it binds to loopback.
3. User verifies no auth is required locally.

Acceptance criteria:

- **Local binding**
  - Default base is `127.0.0.1`.
- **No accidental exposure**
  - UI clearly indicates “Local mode” (especially in Tauri).

### A4 Journey 2 — Desktop app “it just works” (Phase08)

Steps:

1. User installs Prep (desktop).
2. User launches the app.
3. App starts (or attaches to) the daemon automatically.
4. User can add a project and run the core loop without running `prep serve` manually.

Acceptance criteria:

- **Sidecar lifecycle**
  - The UI shows “Backend starting…” until `GET /health` succeeds.
- **Failure recovery**
  - If the backend crashes, the UI offers “Restart backend” and “View logs”.
- **Security**
  - The app does not enable network mode implicitly.

## Acceptance criteria summary (by archetype)

This section is used for “definition of done” reviews.

### A1 (Solo developer)

- Add/build/search/context can be completed purely via UI.
- User can always verify results (file + span).
- The system never silently returns stale results.

### A2 (Staff engineer / tech lead)

- Multiple projects remain isolated and switchable.
- Config changes are deterministic and observable.
- Status surfaces enough detail to debug failures without guesswork.

### A3 (IDE agent user)

- MCP tools are stable and bounded.
- Agent can recover from daemon-down and build-in-progress states.

### A4 (Security/ops-conscious)

- Default behavior is local-only.
- Remote-mode concepts are clearly indicated (even if not implemented in MVP).

## Enterprise UX case studies (design-only; post-MVP)

These are not MVP features. They exist to ensure current architecture and UI affordances do not paint us into a corner.

### Case study E1 — Team server onboarding

Actors:
- Admin
- Developer

Narrative:

1. Admin deploys Prep daemon on a team machine.
2. Admin enables network bind and configures API keys.
3. Developer opens the dashboard and authenticates.
4. Developer uses projects already registered on the server.

Acceptance criteria (design-only):

- UI has a clear “Remote mode” indicator.
- Errors and status views do not leak server filesystem paths.
- Auth failures are distinguishable from connectivity failures.

### Case study E2 — Audit and governance (future)

Narrative:

1. Admin reviews audit logs for project access/build activity.
2. Admin rotates API keys.

Acceptance criteria (design-only):

- Audit events have stable fields (who/what/when).
- Key rotation does not require rebuilding indexes.

### Case study E3 — Identity provider login (SSO) (future)

Narrative:

1. Admin configures OIDC/SAML.
2. Developer signs in via browser.
3. Developer only sees projects they are authorized to access.

Acceptance criteria (design-only):

- The product has a single “auth boundary” (middleware), not per-endpoint ad-hoc checks.
- Authorization decisions are auditable.
- Local-only mode remains usable without any identity provider.

## Cross-phase alignment checklist

Use this list when editing phase specs:

- Does the phase improve at least one journey map?
- Does it preserve MVP boundaries?
- Does it preserve trust invariants (verify project, freshness, citations)?
- Does it preserve bounded outputs?

## References

- `API.md`
- `ARCHITECTURE.md`
- `PHASES.md`
- `Phase01_Foundation/README.md`
- `Phase02_Dashboard/README.md`
- `Phase05_MCP_Integration/README.md`
