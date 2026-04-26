# Phase 118 — UI Smoke Coverage of the Trace-Graph Pipeline

## Purpose

End-to-end UI smoke coverage for **every trigger path that drives the trace-graph
enrichment pipeline**, run against a single small repo (`tests/eval/sample_repos/generated/rust_repo`).
The point is **not** quality of the produced index — the repo is too small to
exercise quality. The point is to verify that for each trigger path:

1. The backend completes (or fails) in a way the API faithfully reports.
2. The dashboard pipeline panel **agrees with the API at every poll** (no
   UI↔API desync).
3. The progress-bar style matches the trigger path (cold vs incremental vs
   scoped rebuild vs scoped reset are visually distinct).
4. The Danger-Zone gates (typed-confirm, scope dropdown) behave correctly.
5. Queue state (`/system/pipeline-queue`) is consistent with what the
   per-project status endpoint reports.

## Why now

Phase 117 (RepairUX) added scoped rebuild endpoints (`/pipeline/fast`,
`/pipeline/deep` with `force_from_start=true`) and scoped reset endpoints
(`/enrichment/full-reset`, `/finalize/full-reset`). Phase 114 added the typed
confirm gate, the recover-stage panel, and the barrier indicator. Neither
phase added end-to-end UI coverage of the new surfaces. This phase closes
that gap and produces a regression net we can wire into CI later.

## Scope

| In scope | Out of scope |
|---|---|
| 6 trigger paths driven through the dashboard UI (or its API equivalent) | Quality of generated index/atlas (smoke repo is too small) |
| Verification that backend state, disk state, and UI state agree | Multi-project simultaneous runs (acknowledged but not exercised here) |
| Capturing screenshots + JSONL event logs per run | Performance benchmarking |
| Documenting any new bugs found, **without fixing them in this phase** | Fixes for known F-66/F-67/F-69/F-75/F-76/F-78 |

## Reference docs

- `PIPELINE_SPEC.md` — canonical "how it SHOULD behave" finalized for this
  phase. Read this first.
- `PIPELINE_REFERENCE.md` — code-grounded reference (state machine, scheduler,
  endpoints) with file:line citations.
- `RESULTS.md` — per-scenario findings (filled in as tests run).
- `.claude/skills/pipeline-testing/SKILL.md` — runbook this phase executes.
- `.claude/skills/playwright-smoke/SKILL.md` — harness wrapper extended in
  this phase.

## Test matrix

Each row is a scenario. The harness does the polling/screenshotting; this
table defines what each scenario means and what counts as pass.

| # | Scenario | Trigger | Backend pass | UI pass | Queue pass |
|---|---|---|---|---|---|
| T1 | Cold initial build | `DELETE /index/destroy` then `POST /pipeline/all` | All 15 stages reach `completed`; manifests on disk; journal rows show 3 group rows with `status=completed` | All 15 stage rows visible, single-tone bars 0→100, no desync events | Single project entry, no orphan queue entries after completion |
| T2 | Incremental rebuild | Touch one file, watcher fires `POST /pipeline/all` | Only stages with detected drift re-run; baseline preserved (F-66) | Two-tone progress bars (baseline vs new) on affected stages; untouched stages stay at 100% | Same project entry observed; no swarm window for trivial run |
| T3 | Rebuild all | `POST /pipeline/rebuild` (Danger Zone scope=all) | All 15 stages re-run from scratch; barrier scope=`all` written; cleared on stage 15 completion | Single-tone bars 0→100; barrier indicator visible during run; cleared at end | Single project entry; barrier visible in queue dump |
| T4 | Rebuild sync (1–5) | `POST /pipeline/fast` with `force_from_start=true` | Stages 1–5 re-run; 6–15 manifests untouched; barrier scope=`sync`; cleared on stage 5 completion | Only stages 1–5 animate; 6–15 stay green; scoped progress style matches scope | Project entry + barrier=sync; single active node |
| T5 | Rebuild enrichment (6–10) | `POST /pipeline/deep` with `force_from_start=true` | Stages 6–10 re-run; 1–5 + 11–15 manifests untouched; barrier scope=`enrichment`; cleared on stage 10 completion | Only stages 6–10 animate | Project entry + barrier=enrichment |
| T6 | Reset all | `DELETE /index/destroy` (Danger Zone Reset scope=all) | All disk state wiped; all SQLite stores cleared; barrier present | Pipeline panel shows pristine "never built" state immediately (no stale rows) | No project entry in queue |
| T7 | Reset enrichment (6–15) | `DELETE /enrichment/full-reset` | Stages 6–15 manifests deleted; concepts/antibodies stores cleared; stages 1–5 untouched; barrier reason=`enrichment_reset` | Stages 6–15 transition to "not built" badge while 1–5 keep green | Project entry shows scoped reset barrier |
| T8 | Reset finalize (11–15) | `DELETE /finalize/full-reset` | Stages 11–15 manifests deleted; stages 1–10 untouched; barrier reason=`finalize_reset` | Stages 11–15 transition to "not built"; 1–10 stay green | Project entry shows scoped reset barrier |

T1–T3 use the existing `tools.playwright_smoke --modes initial,incremental,rebuild`.
T4–T8 use the harness extension delivered in this phase
(`--modes rebuild-sync,rebuild-enrichment,reset-all,reset-enrichment,reset-finalize`).

## Pre-flight (run once per session)

```bash
# 1. Daemon up
curl -s localhost:8400/health | jq .status                   # "ok"

# 2. Dashboard up
curl -sI localhost:5174 | head -1                            # 200 OK

# 3. Smoke project exists
curl -s localhost:8400/projects | jq '.data.projects[] | select(.name=="smoke-test")'

# 4. Clear any synthetic-paused state from prior sessions
#    (PIPELINE_SPEC.md §3 explains why this is the right call)
curl -X DELETE localhost:8400/projects/ded7d1b9-436b-4741-98d4-5b1213c1ae47/index/destroy
```

## Running the matrix

```bash
# Project venv only — see auto-memory note about not using system python
.venv/bin/python -m tools.playwright_smoke \
  --project-id ded7d1b9-436b-4741-98d4-5b1213c1ae47 \
  --modes initial,incremental,rebuild,rebuild-sync,rebuild-enrichment,reset-enrichment,reset-finalize,reset-all

# Outputs land in tests/eval/ui_smoke/run_<UTC>/<mode>/
# Top-level report.md summarises all modes
```

Run modes individually if you need to debug:

```bash
.venv/bin/python -m tools.playwright_smoke \
  --project-id ded7d1b9-436b-4741-98d4-5b1213c1ae47 \
  --modes rebuild-sync \
  --headed   # watch the browser drive itself
```

## Success criteria for the phase

- All 8 scenarios run end-to-end without harness errors.
- Per-scenario pass/fail recorded in `RESULTS.md`.
- Any newly-found bugs filed as `F-NEW-N` entries in `RESULTS.md`
  (matching the `F-66/F-67/...` convention used by `pipeline-testing/references/known-gaps.md`).
- The harness exits non-zero if any desync or error is observed
  (already true for existing modes; new modes inherit this).
- Multi-pipeline concurrency contract is preserved — see `PIPELINE_SPEC.md` §4
  for the explicit rules the harness must not violate.

## Out-of-band: testids needed

The Danger-Zone settings page has no `data-testid` attributes today.
This phase adds them (Task #9) so the harness can drive the UI deterministically.
Selector contract is documented in `PIPELINE_SPEC.md` §6.
