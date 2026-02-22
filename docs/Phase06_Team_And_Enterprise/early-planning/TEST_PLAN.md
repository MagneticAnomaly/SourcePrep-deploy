# Phase 06 — Test Plan (Deferred Build)

## Purpose
Define a concrete testing and validation plan for Phase 06 so implementation can start later with clear acceptance criteria.

This plan covers:
- `P06-T1`–`P06-T3`

References:
- `RESEARCH_AND_DECISIONS.md`
- `IMPLEMENTATION_PLAN.md`
- `docs/API.md` (auth + envelope + remote redaction)

---

## Test environment assumptions
- Two machines or two clean environments are available (A and B).
- Git is available.
- A repo is available with:
  - `.codrag/team_config.json` committed
  - optional `.codrag/index/**` committed (for T1)

---

## P06-T1: Embedded committed index flow

### Goal
A teammate can clone a repo and search immediately without rebuilding (when the embedded index is committed and compatible).

### Setup
On machine A:
- Ensure embedded mode index exists at `{project_root}/.codrag/index/`.
- Ensure required artifacts exist:
  - `manifest.json`
  - `documents.json`
  - `embeddings.npy`

### Steps
1. On machine A:
  - build the embedded index
  - commit `.codrag/index/**`
2. On machine B:
  - clone the repo
  - add project in embedded mode
  - verify status reports embedded index state `ok`
  - run search and confirm results return without rebuilding

### Acceptance criteria
- Index is detected as `ok`.
- First search returns results without triggering a build.
- No `.codrag/**` watcher loops occur during project open.

---

## P06-T2: Merge conflict handling

### Goal
If conflict markers exist inside `.codrag/index/**`, the index is invalid and rebuild is required.

### Steps
1. Create a merge conflict inside `.codrag/index/**` (synthetic is fine):
  - insert conflict markers in any index file.
2. Start CoDRAG on the repo and load the project.

### Acceptance criteria
- Embedded index state is `conflicted`.
- Search is blocked or clearly warns that index is not usable.
- A “Full rebuild required” remediation path is offered.

---

## P06-T3: Network mode safety

### Goal
Remote binding without authentication is rejected; remote binding with auth works.

### Test cases

#### Case A: Remote bind without auth
Steps:
1. Configure daemon to bind to `0.0.0.0` (or LAN IP).
2. Ensure no API key is configured.
3. Start the daemon.

Acceptance criteria:
- Daemon refuses to start (or immediately exits) with an actionable message.

#### Case B: Remote bind with auth
Steps:
1. Configure daemon to bind to `0.0.0.0` (or LAN IP).
2. Configure an API key.
3. Start the daemon.
4. From another machine, call endpoints:
  - `GET /health` (no auth)
  - any other endpoint (auth required)

Acceptance criteria:
- `GET /health` succeeds without auth.
- Other endpoints:
  - return `401` without auth
  - succeed with `Authorization: Bearer <api_key>`
- Responses in remote mode do not leak server filesystem paths.
