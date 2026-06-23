# Phase 145 — Pipeline UI Reliability + Browser-Driven Diagnostics

**Status:** Open. **Evidence-corpus phase**, not a fix-execution phase. The goal is to document and organize every pipeline/UI reliability bug we hit so a future, more powerful orchestrator (Fable) can pick the whole bundle up at once and work through it structurally — *not* whack-a-mole one bug at a time as they surface.
**Owner:** Eric (created 2026-06-10, expanding as new symptoms land).
**Predecessor:** `docs/superpowers/plans/2026-06-08-pipeline-reliability-ux-fixes.md` (P1–P6, all landed).
**Related code:** `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx`, `src/prep/services/pipeline/`, `src/prep/api/routers/`.

**Working principles for this phase:**

- **Document, don't fix yet.** New symptoms land here as `§2x` entries + a `FINDING_*` file. Implementation `PROPOSAL_*` docs are welcome — they're *proposals*, not "execute this now." Code only ships once a proposal has been scrutinized and revised, ideally in a coordinated pass by a more capable orchestrator (Fable) that can see the whole phase at once.
- **Pin causes when we can, name uncertainty when we can't.** A `FINDING_*` should distinguish proved facts from hypotheses.
- **Plans get scrutinized before they execute.** Every `PROPOSAL_*` gets at least one scrutiny pass (recorded inline as a "Scrutiny" section or as a separate `SCRUTINY_*` doc) before it's marked ready. Defects are notes for the next revision, not reasons to delete the proposal.
- **Keep the false starts.** Earlier drafts of a proposal stay in the corpus when superseded — they teach the next reviewer what to verify before assuming. Mark them `superseded by → PROPOSAL_v2` rather than deleting.
- **Cross-link aggressively.** Each `FINDING_*`, `PROPOSAL_*`, `DIAGNOSTIC_*`, `EVIDENCE_*`, and `SCRUTINY_*` doc should link to the others it depends on or supersedes.

**Document type conventions:**

| Prefix | Purpose | Lifecycle |
|---|---|---|
| `FINDING_` | A specific bug, observation, or behavior with evidence. May contain hypotheses for the cause if not pinned. | Open → fixed (with commit cite) |
| `DIAGNOSTIC_` | A plan for capturing evidence we don't yet have. Often a prerequisite for a `PROPOSAL_`. | Open → completed (synthesis output linked) |
| `EVIDENCE_` | Captured artifacts from running a diagnostic (logs, scans, on-disk state snapshots). | Static — dated, not edited after capture |
| `PROPOSAL_` | A draft implementation plan. Includes TDD steps, exact files, exact code. Always subject to scrutiny. | Draft → scrutinized → revised → ready → executed (with PR cite) |
| `SCRUTINY_` | A second-guess pass on a `PROPOSAL_`. Records defects, missing coverage, broken assumptions. Optional — small proposals may have the scrutiny inline. | Static — dated per pass |
| `SYNTHESIS_` | A consolidating writeup over multiple findings/evidence docs. Usually authored before a multi-thread proposal. | Static — dated |

## Document index

| File | Type | Status | What's in it |
|---|---|---|---|
| `README.md` (this file) | index + symptom catalog | live | §1 background, §2 symptoms (2a–2u, growing), §3 data flow, §4 UI invariants, §5 diagnostic toolkit, §6 investigation plan, §7 open questions, §8 prior fixes, §9 file hotspots, §10 handoff |
| `FINDING_changeset-swallowed-edits.md` | finding | fixed 2026-06-15 | §2i — manifest writer dropped `hash_algo` + `built_at` |
| `FINDING_stage-progress-non-monotonic.md` | finding | open | §2j — `progress_current` regresses at sub-stage boundaries |
| `FINDING_concurrency-undershoot-and-cross-project-work-loss.md` | finding | open | §2k — 6 hypotheses for concurrency undershoot + work loss; needs live evidence capture |
| `FINDING_reset-barrier-stuck-on-failed-finalize.md` | finding | open | §2l — `.reset_barrier` never auto-clears on failed finalize; root cause pinned |
| `FINDING_daemon-stall-and-frontend-lockup.md` | finding | partial mitigation 2026-06-17 | §2m — 10-minute gap with uvicorn stall and idle-release trigger; UI lockup mitigated + embedder idle-touch corrected, but CoreML hang RCA still open |
| `FINDING_stage15-antibodies-never-complete.md` | finding | open | §2n — Immune System stage rendered as `Not run` regardless of whether the worker ran, failed, or returned zero derivables; UI count-gate + narrow derivation filter pinned, 5 hypotheses + diagnostic checklist |
| `FINDING_incremental-run-shows-50pct-work-after-interrupted-rebuild.md` | finding | open | §2o — Deep Reasoning shows ~57% remaining on a stable repo because a prior force-from-start rebuild reported `success_rate=1.0` after processing 20/2072 files; current run is legitimate recovery work but no UI signal explains why; 5 stacked issues + 4 hypotheses + 5 design questions |
| `FINDING_two-project-incremental-blocked-during-swarm.md` | finding | open | §2p — Second project's Update hangs with no queue surface while first project's swarm holds 10/10 cloud slots; 4 stacked issues + 4 hypotheses + 4 invariants; probably folds into Thread A as a new sub-thread A.8 |
| `FINDING_auto-incremental-never-fired-despite-stale-files.md` | finding | open | §2q — Project on Auto, 9 untraced files up to 7h old, no fast_sync in 7h; 6 hypotheses (watcher not started / OS events missed / debounce gated / silently enqueued behind §2p / glob filter / `_check_incomplete_deep_enrichment` self-heal stuck on §2n); probably paired with §2p |
| `FINDING_multiple-stages-show-running-simultaneously.md` | finding | open, limited-context | §2r — Two screenshots of a Rebuild All showing 2–3 group rows spinning at once with downstream rows holding stale `complete` metadata from earlier runs; circumstances lost, suggested Playwright invariant inline |
| `FINDING_edge-discovery-stuck-pending-auto-incremental-refuses.md` | finding | open | §2s — Edge Discovery row shows spinner but queue says `Pending`; auto-incremental refuses to fire despite 8 untraced files; refresh doesn't recover. 5 hypotheses + diagnostic checklist + rules out daemon stall, swarm block, barrier, UI rollup race. Likely shares root cause with §2q |
| `FINDING_edge-discovery-fast-completion-and-rebuild-progress-style-lag.md` | finding | open | §2t — HomeColab's 21s Edge Discovery verified legitimate (171 items, 8.26/sec). But SourcePrep's post-restart 0.82s / 260 items/sec is implausible — almost certainly cache hits reported as fresh work (§2o-family). Plus a minor UX note on rebuild progress-bar style lag |
| `FINDING_manual-update-click-triggers-ui-cluster.md` | finding — **meta-pattern** | open | §2u — Cascade chain: Auto broken (§2q + §2s) → user clicks Update workaround → non-deterministic cluster of UI symptoms (every other UI finding fires at once). Self-stabilizes by ~stage 8 with refresh. **Key execution-order implication: fix §2q first; removes the trigger and the cascade evaporates** |
| `SYNTHESIS_2026-06-18_did-the-state-machine-drift.md` | synthesis | open hypothesis | Asks whether the Phase 25B state machine is still canonical or has been progressively eclipsed by 8 parallel state stores. Maps every open §2 finding to a specific S1↔Sx disagreement. Investigation plan IQ1–IQ7 + sketch of a future `REFERENCE_canonical-pipeline-behavior.md` for the Fable pass. No code proposed |
| `EVIDENCE_s1-vs-everyone-sync-table.md` | evidence | static | IQ1 output. Direct-code map of how S1 sync covers the other 8 stores. **15 transition callsites, 4 stage_results writers bypass Event.*, 0 of 6 `compute*State` functions read S1, scheduler/watcher completely independent, status endpoint silently merges 4 sources.** Cited file:line throughout |
| `EVIDENCE_findings-replayed-against-pure-s1.md` | evidence | static | IQ2 output. Per-finding verdict on what would happen if UI read S1. **6 Fixed, 4 Persists, 2 Different bug, 7 N/A.** Confirms drift hypothesis for UI-rendering layer; not the cure for upstream subsystem issues |
| `REFERENCE_canonical-pipeline-behavior.md` | reference | living draft, awaiting OQ1–OQ8 | The target contract. State machine vocabulary + valid transitions + state-store inventory + canonical ownership rule + (action × state) matrix + (system event × state) matrix + UI rendering contract + Playwright invariant catalog. 8 open questions (OQ1–OQ8) for scrutiny to answer before ratification |
| `PROPOSAL_state-machine-re-centering-v1.md` | proposal — **draft, scrutinized 2026-06-18, awaiting v2** | open | T1 (UI re-centering) + T2 (4 subsystem repairs; 2 of them are PROPOSAL_thread-A-v1 + PROPOSAL_threads-B-and-C-v2) + T3 (long-term invariant enforcement). Risk register R1–R10 + 8 OQ dependencies + decision dependency graph. **11 defects found in scrutiny (3 critical) — see SCRUTINY_v1.** Do not execute T1 as written; needs the D1+D3 fixes |
| `SCRUTINY_v1_state-machine-re-centering.md` | scrutiny — first pass | static | Self-scrutiny pass on the v1 proposal. **11 defects D1–D11 (3 critical: T1 alone would mask §2l-A and §2n; helper exact-match fails on real failures; §2j/§2o IQ2 verdicts wrong).** Revised tally: 4 cleanly Fixed, 2 partial-needs-bundling, 6 Persists, 7 N/A. Risks R11–R14 added. Recommends fresh-eyes scrutiny by an independent agent before v2. Hypothesis itself holds |
| `PROPOSAL_playwright-uat-harness-v1.md` | proposal — **T1 + T2 + T3 + T4 shipped 2026-06-22, T5 (cadence) awaiting execution** | partial | Methodology + 5-task plan to extend the existing `tools/playwright_smoke.py` with 4 Phase 145 §8 invariants (I1, I2, I3, I13), drive a real project through 4 operations × 3 iterations, produce `SCORECARD_uat_*.md` baselines. Independent of all fix proposals. **T1 + T2 + T3 + T4 all shipped 2026-06-22.** T1 = invariant library; T2 = invariants wired into `watch_until_idle` with 2-tick persistence gate; T3 = iteration runner + scorecard generator; T4 = baseline SCORECARD captured against PowerMateReborn (HomeColab too big at 45-90min/rebuild). Four-lens adversarial review run pre-merge each drop; T3 caught 5 Tier-1 blockers; T4 caught a 6th (cancel-quiesce empty-body false negative). |
| `SCORECARD_uat_baseline_2026-06-22.md` + `.manifest.json` sidecar | **regression anchor** | live | First T4 baseline. PowerMateReborn (15 src files), 4 ops × 3 iters = 12 rows. **Surfaces three real bug classes**: I3 intra-group stale-leak (11/12 iters, dominant — §2r), I1 double-running stages (4/12 iters, sporadic — §2r), I13 per-row spinner missing despite T2 fix (5/12 iters, sporadic — §2u §6.2). Op-2 incremental iter 3 is the only fully-passing row across all 12. Manifest sidecar enables resume + future trend diffs. |
| `SCORECARD_uat_post-i3-fix_2026-06-22.md` + `.manifest.json` sidecar | **post-I3-fix regression check** | live | Post-fix sibling of the baseline above. Same PMR + ops + iter count + harness. **All three target invariants closed: I3 11/12→0/12, I1 4/12→0/12, I13 5/12→0/12.** I1 + I13 closed as emergent wins — the workflow had hypothesized them as independent code paths, but live data showed they were downstream symptoms of the same per-stage-state leak. Bare-fail-no-invariant rows (8/12) persist as the §9.3 #17 anomaly; rc-vs-summary skew, not a regression. DIFF block at the top of the file. |
| `FINDING_dashboard-stale-deep-enrichment-after-completion.md` | finding | open, 4 bug classes | 2026-06-23 dogfood screenshot + live API snapshot. **§9.3 #28-#31 filed.** Deep Reasoning 100%-but-spinning (possible I3 regression / coverage hole), 3 deep stages with-data-but-not-done (§9.1 cross-group, §9.3 #18 fresh evidence), Deep Knowledge Embedding literal "Not run" text against `stage_results.deep_knowledge=completed` (needs new I14), Fast Catalogue chip shows 5501% (`augmented/total × 100` math inverted; needs new I15). Smoke harness did not catch any of the 4 — detector blindness pinned for next coverage pass. |
| `SCORECARD_uat_post-17-fix_2026-06-22.md` + `.manifest.json` sidecar | **post-#17-fix validation** | live | 4-iter smoke (1× Op-1/2/3/4) after the §9.3 #17 fix landed. **Bare-fail-no-evidence class eliminated: 8/12 (pre) → 0/4 (post).** Every row that says `FAIL` now carries WHY in Notes — `error×1 'timed out'`, `desync×3 'api_running_dom_not_running'`, etc. **The newly visible signal surfaces two pre-existing real bugs** (§9.3 #20 daemon stuck-barrier on `/pipeline/rebuild` >120s for PMR, §9.3 #21 Op-4 subprocess crash on `--update-at-secs`) that the pre-fix SCORECARD pipeline had been hiding. DIFF block + interpretation at the top of the file. The fix did its job: noise → actionable signal. |
| `tools/phase145_uat/{constants,invariants,run_session}.py` + `tests/test_phase145_{invariants,run_session}.py` + `tools/playwright_smoke.py` + `packages/ui/.../GraphEnrichmentPipeline.tsx` | shipped code — T1 + T2 + T3 + T4 of UAT harness | live | **T1:** I1/I2/I3/I13 invariants with `ACTIVE_PIPELINE_PHASES = {running, pausing, paused, recovering, cancelling}`. **T2:** invariants wired into `watch_until_idle` per API-poll tick; `INVARIANT_PERSISTENCE_TICKS=2` absorbs SSE-commit-lag races; `data-testid="current-stage-indicator"` + `data-testid="last-run-chip"` land on `GraphEnrichmentPipeline.tsx`; new `invariant_failure` event kind + `invariant_failure_count` + `Invariants` column in `report.md`. **T3:** `run_session.py` drives the §4 operation matrix (Op-1..Op-4) N iterations each, journals to `<output>.manifest.json` for resume, emits SCORECARD markdown with planned-iter trends + glob-resolved evidence paths + `_md_cell` table-safe escape; two-step daemon health probe; `cancel_and_quiesce` after failed iter to prevent cascade-fail; `--refresh-at-secs` / `--update-at-secs` in `playwright_smoke` with `_advance_scheduled_actions` pure scheduler + `expand_all_groups` post-reload + `post_reload_recovery` gate. **T4:** baseline run + cancel-quiesce fix (`_pipeline_snapshot` helper + correct `{group, reason}` body + 409-as-already-stopped + multi-group iteration). **100 pytest cases total** (50 invariant + 50 run_session). Cross-group I3 gap + Op-4 UI-click variant + 14 other deferred follow-ups documented in PROPOSAL §9.3. |
| `PROPOSAL_threads-B-and-C-v1-barrier-and-rollup.md` | proposal — **draft, scrutinized, superseded** | superseded by v2 | First attempt at Thread B + C fixes. Five defects (D1–D5) found in scrutiny. Kept for context |
| `DIAGNOSTIC_2026-06-15_resume-point-and-failure-paths.md` | diagnostic | open | DG1–DG7 — evidence to capture before §2l Thread C can be planned correctly |
| `PROPOSAL_threads-B-and-C-v2-barrier-and-resume-detector.md` | proposal — **draft, awaiting scrutiny** | open | Corrected v2: Thread B with the right enums + broader fix location; Thread C reframed to the actual upstream cause (resume detector); Thread D as a UI safety net. Subject to scrutiny before execution |
| `PROPOSAL_thread-A-v1-concurrency-undershoot-and-work-loss.md` | proposal — **draft, awaiting scrutiny** | open | §2k — Thread A as A.1 (diagnostic) + A.2 (manual-floor, evidence solid) + A.3–A.7 (each gated on which evidence DG-A captures). Risk register RA1–RA7 + invariants from FINDING §5. Subject to scrutiny before execution |

**Reading order for an orchestrator opening this cold:**

1. README §1 + §2 symptom catalog for the lay of the land.
2. The `FINDING_*` files for each open §2 entry.
3. The `DIAGNOSTIC_*` files for items where evidence is still being captured.
4. Any `EVIDENCE_*` outputs that have landed.
5. The `PROPOSAL_*` files, newest first. For each, read the inline scrutiny section (or matching `SCRUTINY_*` doc) before deciding to execute. Defects flagged in earlier drafts are warnings about what to re-verify in newer drafts.
6. Only then propose to execute anything.

---

## 1. Why this phase exists

The 2026-06-08 plan (P1–P6) closed every single backend bug we traced from the original cross-project contamination incident. The orchestrator, scheduler, write guard, selfheal, and embedder all do the right thing now, and pipeline runs complete end-to-end.

**The UI does not consistently reflect that.** Three incidents in three days where:

- 2026-06-08: skipped stages displayed as `0% Running` indefinitely.
- 2026-06-09: the dashboard locked — clicks didn't register, the whole tab needed a refresh.
- 2026-06-10: every project shows `Deep Reasoning` (stage `enrichment`) stuck in an incomplete-looking state, and the UI is "extremely sluggish."

Each of these has a different proximate cause (uncommitted helper, broken PUT endpoint, state-rollup mismatch). The pattern is: **the UI's idea of pipeline state drifts from the daemon's reality, and the user can't tell why.**

Phase 145's job is to **stop firefighting individual UI bugs and produce a single source of truth for what the UI should display in every state**, plus a browser-driven test harness that pins it.

## 2. Symptom catalog (every observed bad behavior)

### 2a. Phase shows "incomplete" / "0% Running" when the stage actually finished

- **2026-06-08 form:** freshness-skipped stages emit `stage_start` + a `log` event, no `stage_end`. UI keeps the initial `"pending"` from `create_run_metadata` and renders "Iteration 0/?" / "Enriching…" forever.
- **Fix that landed:** `mark_stage_skipped` added to `pipeline_metadata.py` (P2, commit `1a04e097`).
- **Status:** verified live for new runs; **legacy projects whose metadata was written pre-fix still show the bug.**

### 2b. Deep Reasoning stuck across all projects (open, 2026-06-10)

- Every project's `enrichment` stage row shows incomplete in the panel.
- Probe of one project (SourcePrep) via `/projects/{id}/pipeline/status` shows `stages.enrichment.provenance.state == "match"` — i.e. **the backend says the stage is current**.
- `deep_enrichment` group is `null` (no active or recent run record).
- Hypothesis: the UI rollup in `GraphEnrichmentPipeline.tsx` derives stage state from a different source than `provenance.state` and they disagree.
- **Unverified.** See §6 Investigation Plan.

### 2c. Dashboard sluggish / unresponsive (open, 2026-06-09 and 2026-06-10)

- Whole-tab freeze where clicks queue but never fire.
- 2026-06-09 was traced (partially) to `PUT /global/config` returning 500 on every save because of a broken `_deep_merge` import — fixed in `883158db`.
- **The 2026-06-10 sluggishness persists after that fix**, so there's at least one more cause.
- Hypothesis: SSE event volume during long stages + React re-render storms on `/projects` list updates.
- **Unverified.**

### 2d. Cross-project surprise triggers

- Original 2026-06-08 incident: flipping a single project's auto toggle dispatched runs for every active trace-enabled project via a fan-out thread in the settings router.
- **Fixed** by P1 (`11033fc2`). Regression-pinned by `tests/test_settings_pipeline_config_no_fanout.py`.
- **Still worth verifying** that no other "global toggle → multi-project effect" paths exist (e.g., `crud.py:_activate_project`, `server.py:_startup_auto_run`).

### 2e. Process Logs panel hides the actual error

- The UI panel shows each log line as one row. When uvicorn writes `[uvicorn.error] Exception in ASGI application` followed by a 6–10 line Python traceback, the user sees one red row with a generic message and the traceback rows look like normal text below it. The actual exception class + message + file path are invisible at a glance.
- **Real symptom: the user couldn't tell what the daemon was failing at without dropping to the browser Network tab.**
- No fix landed for this yet.

### 2f. Sidebar queue shows stale state

- 2026-06-08 X-button heuristic (P3, `75dc3c9a` + `cf2d6874`) added toast-on-cancel + repeat-click escalation.
- **New symptom 2026-06-10:** Deep-Live-Cam shows `phase=queued, active=True` in `/projects/{id}/pipeline/status`, but `/system/pipeline-queue` returns empty. Two endpoints disagree about whether the project is queued.

### 2g. ImportError 500s on endpoints that aren't called at startup

- 2026-06-09: `PUT /global/config` 500'd for **weeks** without anyone noticing, because the broken `_deep_merge` import was inside the function body. Startup-time syntax/import checks didn't catch it.
- **Fixed by `883158db`** (the specific symbol) plus a regression test pinning the import path.
- **Class of bug worth auditing:** every other `from prep.server import ...` inside a function body could have the same latent break.

### 2h. Multiple "config" endpoints that look similar but behave differently

- `/global/config` (GET/PUT) — UI config blob.
- `/settings/pipeline-config` (GET/POST) — pipeline mode flags.
- `/mcp/config?ide=...` (GET) — MCP server snippet per IDE.
- `/projects/{id}/pm/config` (GET) — Paperclip plugin config.
- `/settings/advanced-config` (GET/POST) — advanced settings.
- `/admin/actions/approve-config` (POST) — admin gate.
- **No single API contract documents what state each endpoint owns**, leading to the dashboard PUTting partial updates to `/global/config` for things that probably belong elsewhere.

### 2i. Changeset never reports content edits — daemon-wide (FIXED, 2026-06-15)

- Edited source files (confirmed via `git diff`) were classified `changeset.unchanged` and never re-enriched or finalized — no error, no UI signal. Verified across **all 13 local projects**: every one had `hash_algo: None` and `modified=0`.
- **Root cause (one writer):** `ManifestStore.write_provenance` (STRUCTURAL branch) merged the stage provenance into `trace_manifest.json` preserving only `("file_hashes","config","file_errors")`, **dropping `hash_algo` and `built_at`**. Untagged → `_emit_changeset` always took Case 3 ("trust prior") → Case 2 (real diff) was dead → edits never `modified`. The dropped `built_at` is *also* the §earlier "always 0 stale" staleness bug. One writer, both symptoms.
- **Fix:** add `hash_algo` + `built_at` to `preserved_keys`. `_emit_changeset` is deliberately left alone (an untagged manifest is ambiguous vs a genuine pre-Phase-133 one, and already-swallowed edits have a poisoned baseline). Existing backlogs clear with a one-time force-rebuild.
- This is a **backend correctness** bug (distinct from the UI-drift focus of this phase, but surfaces as "the pipeline says up-to-date when it isn't").
- **Full root-cause + evidence:** [`FINDING_changeset-swallowed-edits.md`](FINDING_changeset-swallowed-edits.md). Tests: `test_phase145_provenance_preserves_hash_algo.py`, `test_phase145_changeset_swallow.py`, `test_phase145_finalize_incremental_hatch.py`.
- Related item, also fixed: Finalize never auto-chained on incremental runs (missing Phase 89 hatch in `run_finalize`).

### 2j. Stage `progress` regresses at sub-stage boundaries (open, 2026-06-15)

- Observed live: Group Reasoning's progress bar regressed mid-run (visible as bright-orange shrinkage under the old 3-slab incremental renderer). `progress_baseline` is frozen per stage (verified), so the regression is in `progress_current / progress_total`.
- Suspected cause: a stage worker with multiple internal phases reports each phase's progress as its own 0→N against the shared `progress_total`, so `current` snaps backward at phase boundaries. First place to look: `src/prep/core/epistemic_enrichment.py:842`.
- Visual symptom suppressed (not fixed) by the 3→2 slab collapse in `StageProgressBar` 'incremental' variant on 2026-06-15. Under the new renderer the green slab itself will visibly shrink if `progress` regresses — still wrong.
- **Full notes + recommended follow-up:** [`FINDING_stage-progress-non-monotonic.md`](FINDING_stage-progress-non-monotonic.md). Two layers: frontend monotonic guard (cheap, defensive) + backend stage-worker audit (correct).

### 2k. Concurrency undershoot + cross-project work loss on second-start (open, 2026-06-15)

- Ollama Pro with manual `llm_concurrency_deep = 10`. Running `ApplicationBrowser` alone on Deep Reasoning (`enrichment`, Stage 6 / Epistemic Enrichment) showed only **2–4 concurrent LLM calls** — not the configured 10. With one active project, Phase 91 fair-share says the project should get the full budget.
- Starting a second project (`SkyPath-Restart`) mid-run: second project also got only **2–4 calls**, and the first project's run **shut off mid-stage with apparent work loss**, with no surfaced failure.
- Per `Phase91_QueueRefinement/01_Resource_Allocation_Design.md`: a boost (★) + normal split at budget=10 should be 7/3, not 2–4 / 2–4; `capacity_changed` is supposed to **resize** running stages, not cancel them; cancellation only happens on `drain_timeout` and must surface as a visible `failed` state with reason. A second project's queued swarm ("star with a circle") must not dispossess the first project's in-flight non-swarm work.
- Backend scheduler/allocator bug — distinct from the UI-drift focus of the rest of this phase, but logged here for triage parity.
- **Full hypothesis list + evidence to capture:** [`FINDING_concurrency-undershoot-and-cross-project-work-loss.md`](FINDING_concurrency-undershoot-and-cross-project-work-loss.md).
- **Implementation proposal (v1, draft, awaiting scrutiny):** [`PROPOSAL_thread-A-v1-concurrency-undershoot-and-work-loss.md`](PROPOSAL_thread-A-v1-concurrency-undershoot-and-work-loss.md) — A.1 diagnostic sub-thread (DG-A1..A7), A.2 manual-floor (solid evidence, can ship today), A.3–A.7 each gated on what A.1 surfaces.
- **2026-06-19 scope clarification:** the swarm code path is confirmed working (`10×Swarm on Applifier` correctly fired on Group Reasoning). §2k concerns are about **non-swarm fair-share** only — Epistemic Enrichment / Catalogue / Module Synthesis / etc. Adjacent datapoint: Applifier alone on Deep Reasoning (Stage 6, non-swarm) only used 1/10 cloud slots when boost-priority alone should give the full budget. See finding §7.

### 2l. UI drift on Applifier: rows show "Not run" while backend says `match`; Run returns PIPELINE_UP_TO_DATE (open, 2026-06-15)

- Direct follow-on to §2k on Applifier (`/Volumes/Thunderbolt/AI/ApplicationBrowser`). After §2k left finalize failed, the user reopened the project and saw every Deep Enrichment row ("Deep Reasoning", "Group Reasoning", "Module Synthesis", "Continuous Deepening", "Deep Knowledge Embedding") rendered as empty circles with "Not run" / "Waiting for enrichment". Overall Health: 33% (5/15). Clicking **Run** on Deep Enrichment surfaces this toast:
  > ⚠ Deep Enrichment detected all stages as complete. If stages appear incomplete in the UI, try 'Force Reset' then 'Run' again.
- **Source of the toast:** `src/prep/api/routers/pipeline.py:271-278` — the daemon returns `409 PIPELINE_UP_TO_DATE` when `pipeline_orchestrator.run_deep_enrichment()` decides there's nothing to do. The backend is correct: `/projects/<id>/pipeline/status` shows `enrichment/group_reasoning/clustering/deepening/deep_knowledge` all at `provenance.state="match"`. **The UI rollup is reading from a different field** (the stages' top-level `enabled` flag — all five report `enabled: false` even though they ran to completion in this run). This is the §2b "drift" shape, on a new code path.
- **The user does have an escape hatch** — clicking Force Reset calls `clear_reset_barrier()` (`pipeline.py:244-247`) and then re-runs, so the project is not truly un-restartable. But the user is being told to trust the toast over what the dashboard is rendering, which inverts the §4c "Status-on-disk is truth" invariant.
- **The reset barrier is still stuck on disk** (`.sourceprep/.reset_barrier`, 40+ min old, `reason=full_reset`, `scope=all`). Selfheal logs every ~10 minutes: `Selfheal skipped: reset barrier active — awaiting genuine finalize`. Root cause pinned to `maybe_clear_scoped_barrier` being called only from the success branches of each group's post-run handler (`src/prep/services/pipeline/orchestrator.py:2121, 2158, 2169`). When finalize fails, the call is skipped and the barrier persists. Force Reset masks this for the user but the underlying barrier-auto-clear contract is broken — any failure path (LLM timeout, 5xx, cancel) reproduces it.
- Two threads, separable fixes:
  - **Thread A (UI rollup, §2b shape):** the deep-enrichment rows must derive state from `provenance.state` (or whichever field reliably reflects on-disk truth), not from `enabled`. Track in §6 alongside the existing §2b investigation.
  - **Thread B (barrier auto-clear):** move the three `maybe_clear_scoped_barrier` calls out of success branches into a post-run `finally`. Audit the soft-hold lifecycle for missing release paths. Don't require the user to learn about `.reset_barrier` or click Force Reset to recover from a failed run.
- **Full root cause + evidence + recommended fix shape:** [`FINDING_reset-barrier-stuck-on-failed-finalize.md`](FINDING_reset-barrier-stuck-on-failed-finalize.md).
- **Implementation proposals:** [`PROPOSAL_threads-B-and-C-v1-barrier-and-rollup.md`](PROPOSAL_threads-B-and-C-v1-barrier-and-rollup.md) (v1 — *superseded by v2*, kept for the scrutiny notes D1–D5) and [`PROPOSAL_threads-B-and-C-v2-barrier-and-resume-detector.md`](PROPOSAL_threads-B-and-C-v2-barrier-and-resume-detector.md) (v2 — current draft, awaiting scrutiny). Thread A (§2k) is deliberately out of scope until its evidence is captured.

### 2m. Daemon stalls and frontend locks up (partial mitigation 2026-06-17)

- Observed live in active terminal (ProcessId 53781). A 10-minute (600s) gap occurs during which no requests (including the highly frequent `/system/pipeline-queue` poll) are logged by uvicorn.
- Under-the-hood background OS threads continue ticking independently: exactly 10 minutes after inactivity starts, `prep-embedder-idle-release` detects idle state, calls `close_shared_embedders()`, and logs `Idle-release: dropped 1 embedder(s) after 600s of inactivity`.
- *Immediately* after the background idle-release completes, uvicorn unblocks and resumes processing incoming requests.
- **Activity-monitor evidence captured 2026-06-17 (Eric):** memory pressure GREEN, 832 KB swap, no paging. Daemon Python process ≈1.05 GB. **Not a resource exhaustion issue** — confirms H2 (native CoreML hang on the trailing batch).
- **2026-06-18 22:38 suspected recurrence — RETRACTED 2026-06-18 23:38.** Eric verified by browser refresh that the daemon was running and all queued work had completed under the hood at 22:38; the symptom was a frontend hang, NOT a backend stall. The original §2m 2026-06-17 terminal-log evidence (10-minute uvicorn gap) remains a real backend stall. The §2p / §2q "downstream of §2m" reattribution is withdrawn — they stand as independent bugs again. See `FINDING_daemon-stall-and-frontend-lockup.md` §9 for the retraction note.
- **Full notes + investigation hypotheses:** [`FINDING_daemon-stall-and-frontend-lockup.md`](FINDING_daemon-stall-and-frontend-lockup.md).
- **Partial mitigations landed 2026-06-17 (does NOT fix the underlying CoreML hang):**
  - **Frontend resilience:** `SidebarPipelineQueue.tsx` polling `fetch` now uses an `AbortController` with a 5s timeout. When the daemon stalls, the in-flight ref clears, the UI keeps rendering last-known queue state, and the next 10s tick retries — the sidebar no longer locks up indefinitely waiting on a frozen daemon.
  - **Embedder idle-touch correctness:** `NativeEmbedder._touch_idle()` was being called once per outer `embed_batch(...)` call. A multi-bucket dispatch (the common case for the Knowledge Embedding stage) makes many inner `_session.run(...)` calls; the entry-only touch meant a >600s legitimate run could race the idle-release timer and have its session closed mid-call. Moved to fire *after* each inner `_session.run(...)` returns — successful inner batches keep the embedder marked active, but a stuck `.run()` (which never returns) still goes stale and trips the recovery path that was observed unblocking the daemon in this incident.
  - **Regression tests:** `tests/test_phase139_pr2_batching.py::TestPhase145IdleTouchPlacement` (2 cases — touch-per-inner-call + timestamp-advances-per-call).
- **Still open** — neither change fixes the CoreML hang itself. Recovery still requires waiting up to 600s for the idle-release timer. Real RCA needs a py-spy dump captured during the next stall (per finding §4).

### 2n. Stage 15 (Immune System / Antibodies) never appears complete (open, 2026-06-17)

- The Finalize group's final stage continues to render `Not run` after a finalize run completes, with no progress bar and no checkmark — the user can't tell whether the worker is being dispatched, raising silently, or returning successfully with zero derived antibodies.
- **Code-level finding:** the UI's completion gate (`GraphEnrichmentPipeline.tsx:1551`) is `!!(effectiveAntibodiesStatus?.count)` — strictly count-based. The backend status route (`pipeline.py:789-803`) returns `count: 0` whenever EITHER `antibodies_manifest.json` is missing OR `antibody_store.list_antibodies(project_id)` returns `[]`. Six distinct scenarios (worker never dispatched / worker raised / worker skipped-no-concepts / derivation filter rejected every concept / `save_many` failed / cross-process `data_dir` divergence) all collapse to the same "Not run" rendering.
- Stage 15 is the only finalize stage gated on a count rather than an existence boolean (compare Atlas / Rules / Concepts / Audit). `STAGE_OUTPUT_FILE[StageId.ANTIBODIES] is None`, so the manifest carries no count of its own — the count lives entirely in the shared SQLite store, which makes the dual-gate read-side fragile.
- **Most-likely cause without diagnostic evidence yet:** the worker runs and produces zero derivables because `derive_antibodies_for_project`'s filter only accepts `kind="concept"` + `category in {"constraint","architecture"}` + anchors + text, and most projects' concepts are dominated by `module_rationale` rows that fail this filter. That makes the symptom a UX gap, not necessarily a bug — but H2–H5 in the finding are real bugs if they fire and the disambiguation is cheap.
- **Full notes + 5-step diagnostic checklist:** [`FINDING_stage15-antibodies-never-complete.md`](FINDING_stage15-antibodies-never-complete.md).
- **2026-06-19 recurrence:** confirmed "regular" pattern (3+ captures across different projects). Latest: small project with 1 concept renders all four other finalize stages ✓ but Immune System "Not run." Strongest hypothesis is scenario (d) — worker ran, filter rejected the only concept as a derivation source, manifest emitted `count: 0`, UI's count-gate renders "Not run." **Cleanly closed by `PROPOSAL_state-machine-re-centering-v1.md` T1** (read `stage_results["antibodies"]` from S1) + a "complete-but-empty" chip from T2.a / Thread D.

### 2o. Incremental Deep Reasoning shows >50% remaining on a stable repo (open, 2026-06-17)

- Live screenshot of the SourcePrep dashboard during a deep_enrichment run: Deep Reasoning bar at `896 / 2,073 files · 43%` with a ~57% in-progress segment, on a repo where the user had not modified anywhere near that many files.
- **Root cause pinned from on-disk logs:** a prior `force_from_start` rebuild dispatched at 15:43 EDT today wiped `trace_epistemic.jsonl` and then exited the enrichment stage after processing only ~20 of 2072 files — but the orchestrator wrote a manifest with `quality.success_rate: 1.0, processed: 20`. The next run at 17:27 correctly sees only 40 existing entries and is now doing legitimate recovery work to enrich the remaining 2033 files.
- The work currently in progress is *correct*. The UI surface that frames it as "incremental progress on user edits" is *wrong* — there's no signal distinguishing user-introduced delta from recovery-from-interrupted-prior-run.
- **At least five distinct issues stack here:** (3a) the enrichment manifest's `quality` block is computed from raw JSONL row count with no expected denominator, so partial completion looks like full completion; (3b) the rebuild trigger is not recorded in the log (UI? API? selfheal?); (3c) the two-tone bar has no copy explaining recovery context; (3d) the 20→40 row jump between the manifest write and the next run start is unexplained (probably deepening sharing the JSONL); (3e) `.sourceprep/logs/` contains events from another project (`7cdea5e4...` = Applifier), making per-project forensics fragile.
- **Full notes + 5-step diagnostic checklist + 5 design questions:** [`FINDING_incremental-run-shows-50pct-work-after-interrupted-rebuild.md`](FINDING_incremental-run-shows-50pct-work-after-interrupted-rebuild.md).

### 2p. Two-project incremental: second project hangs on Update with no queue surface; one project's swarm consumes full cloud budget (open, 2026-06-18)

- Two projects active, neither boosted: DebateHaus is `Swarming · Deep Enrichment · Module Synthesis · 19m 13s` per the queue widget; Applifier is the one the user clicked **Update** on.
- Applifier's Update button shows `Updating…` indefinitely. No queued badge, no "behind DebateHaus" hint, no visible feedback. `cloud:default_ollama` is at 10/10.
- Per Phase 91 contract: when no project is boost/exclusive and one project is swarming, other projects' stages should enter the queue and wait, rendered with `Hourglass + "Queued behind <project>"` (Phase 145 §4a). Today the queue widget shows only the active project — waiters are invisible.
- Side observations worth pinning: (2a) "Module Synthesis" badged as Swarming, though Phase 79 marks Stage 8 as Medium-benefit / future swarm candidate (Stage 7 Group Reasoning is the primary swarm target); (2b) AI Gateway label says "Deep Reasoning [10×] on DebateHaus" while the queue widget says "Module Synthesis" — stage names disagree at the same instant; (2c) 19m+ on a single stage with no progress signal.
- **Two layers stacked:** backend (is Applifier actually enqueued?) and UI (if so, why no surface?). Discriminator is a single `/system/pipeline-queue` snapshot while the symptom is live. Related to §2k (same scheduler subsystem, different manifestation — work loss vs no-start), §2f (queue widget shape).
- **Full notes + 7-step diagnostic checklist + 4 hypotheses + 4 invariants:** [`FINDING_two-project-incremental-blocked-during-swarm.md`](FINDING_two-project-incremental-blocked-during-swarm.md).
- **2026-06-18 23:38:** the daemon-freeze attribution from 22:38 is **withdrawn** — the daemon was healthy; this was a frontend hang. §2p stands as an independent bug. See finding §9.

### 2q. Auto-incremental pipeline never auto-triggered despite hours of untracked files (open, 2026-06-18)

- Same Applifier screenshot. Project has Auto enabled for Fast Sync + Deep Enrichment + Finalize. Graph Scope shows **9 untraced files** ranging from 3h to 7h old; **Last updated: 7h ago**. The `AutoRebuildWatcher` should have fired and processed these incrementally hours ago.
- No surface tells the user whether the watcher (a) never started for this project, (b) is running but the OS isn't delivering file events, (c) is firing but the debounce path is silently bailing on a gate (budget / reset-barrier / `_check_incomplete_deep_enrichment` self-heal check), or (d) is firing and enqueueing successfully but the work is invisibly queued behind another project's swarm (§2p).
- Hypotheses H-Q1 through H-Q6 cover each layer; the discriminator is a focused capture (`/projects/<id>/watch/status` + a probe `touch` + the daemon log tail).
- Probably paired with §2p — if the watcher *did* fire and §2p's invisible queue is the consequence, this is the same bug at a different surface. Need evidence to know.
- **Full notes + 7-step diagnostic checklist + 6 hypotheses + 5 design questions:** [`FINDING_auto-incremental-never-fired-despite-stale-files.md`](FINDING_auto-incremental-never-fired-despite-stale-files.md).
- **2026-06-18 23:38:** the daemon-freeze attribution from 22:38 is **withdrawn** — §2q stands as a standalone watcher-side bug. Six hypotheses (H-Q1..H-Q6) still apply. New adjacent symptom §2s (Edge Discovery stuck `Pending` with auto-incremental refusing to fire) is likely the same underlying bug surfacing on a different surface.

### 2r. Multiple Fast Sync rows render as `running` simultaneously during Rebuild All (open, screenshots only, 2026-06-17)

- Two screenshots from a `Rebuild All` run: in one, the header reads "stage 5/15: Knowledge Embedding · 74%" while three rows (Edge Discovery, Relationship Validation, Knowledge Embedding) all show spinners and progress bars at once; in the other, "stage 3/15: Fast Catalogue · 87%" while Edge Discovery + Fast Catalogue both spin and downstream rows (Validation, Knowledge Embedding) show as ✓ complete with stamps from earlier runs (`yesterday`, `1384 chunks embedded`).
- A sequential group state machine should have exactly one row in `running` at any moment per Phase 145 §4a.
- Limited-context capture — the user does not remember the project, the trigger, or the surrounding sequence. Treated as a documented "we saw this once, here's what's visibly wrong" entry rather than a diagnostic plan.
- Most likely the same `compute*State` family as §2a / §2l / §2n / §2o — the SSE forward-progression hints flip downstream rows to `running` before the API's per-stage running flag clears the upstream row.
- **Suggested closing action** (in the finding): add a Playwright invariant to Phase 145.3 — *during any SSE snapshot, no group has more than one stage in `running` state* — which would catch this whole class without depending on the lost circumstances.
- **Short finding:** [`FINDING_multiple-stages-show-running-simultaneously.md`](FINDING_multiple-stages-show-running-simultaneously.md).

### 2s. Edge Discovery (Stage 2) renders spinning but is actually `Pending`; auto-incremental refuses to fire; refresh doesn't recover (open, 2026-06-18)

- Live screenshot 23:38 on SourcePrep repo. Graph Scope shows 8 untraced markdown files aged 37m–1h (the Phase 145 docs being written today). Right panel: Edge Discovery row has a spinner and "Discovering edges…" label. Queue widget: `SourcePrep · Pending · Fast Sync · Edge Discovery`. `cloud:default_ollama: 0/10` — nothing in flight. **Browser refresh does NOT recover.**
- Three signals disagree at the same moment: row spinner says running, queue widget says pending, cloud load says idle, AI Gateway says `1 active`. Classic compute*State family bug (same shape as §2r) but refresh-resistant — distinguishes it from the §2m-22:38 frontend-hang family.
- Five hypotheses (H-S1..H-S5): silent failure swallowed; worker thread hung; orchestrator guard short-circuited (overlaps §2q H-Q6); changeset fingerprint missed the new files; auto-trigger deduplicated against an already-Pending entry that never started.
- Very likely the same underlying bug as §2q (auto-incremental never fired). The fact that auto won't fire while the daemon is otherwise healthy strengthens §2q's case as a real standalone bug, independent of the (now-retracted) §2m attribution.
- **Recurrence 2026-06-19 07:13 — manual Rebuild All, 8h stall, progress reached 93% then froze.** Stage 1 (Structural) completed in 4s, then Edge Discovery worker started, reached 93%, stalled for 8h. Rules out H-S3/H-S4/H-S5; reinforces H-S2 (worker hung mid-execution). Adds H-S6 (LLM call never returned, slot released by heartbeat but worker still thinks it holds the slot) and H-S7 (non-LLM coordination deadlock). **Implies a new sub-thread T4 — worker-side watchdog with wall-clock timeout** to add to the re-centering proposal v2. py-spy dump on the daemon's worker thread is the discriminator if symptom is still live.
- **Short finding + diagnostic checklist + 7 hypotheses:** [`FINDING_edge-discovery-stuck-pending-auto-incremental-refuses.md`](FINDING_edge-discovery-stuck-pending-auto-incremental-refuses.md).

### 2t. Edge Discovery completion time is hard to interpret (cache hits look like live runs); rebuild progress bar style switches mid-run (open, 2026-06-19)

- User clicked Rebuild All on HomeColab; Edge Discovery completed in 21s. User asked "did it actually do the work?" **Direct manifest read confirms yes** — 171 items processed at 8.26 items/sec, real avg_confidence 0.843. Plausible cloud-LLM throughput for a small project.
- **Adjacent concern:** SourcePrep's Edge Discovery manifest from the daemon-restart screenshot shows 214 items in **0.82s = 260 items/sec** with the same model. That's 30× HomeColab's rate — physically implausible for cloud LLM. Almost certainly cache hits from the §2s 8h-stalled prior run, but the manifest's `quality.processed: 214, success_rate: 1.0` doesn't distinguish cache hits from fresh LLM work. **§2o-family bug** — manifest reporting doesn't faithfully represent how the work happened. Three hypotheses (H-T1..H-T3) in the finding.
- **Minor UX:** rebuild progress bar renders in default-style for ~7s after Rebuild click, then switches to rebuild-style when the "Rebuilding All stage 2/15" banner appears. Cosmetic; suggested fix is optimistic local style on click.
- **Short finding + manifest evidence + diagnostic command + 3 hypotheses:** [`FINDING_edge-discovery-fast-completion-and-rebuild-progress-style-lag.md`](FINDING_edge-discovery-fast-completion-and-rebuild-progress-style-lag.md).

### 2u. Manual Update click triggers a non-deterministic cluster of UI hang symptoms (recurring, 2026-06-19)

- **The cluster pattern, not a new individual bug.** Each symptom (other projects don't load, missing/multi/wrong-style progress bars, "Update" silent, can't tell if backend is running) maps to an already-documented finding (§2c, §2f, §2m post-retraction, §2p, §2r, §2t §4). What's *new* is the **cascade**: Auto-incremental broken (§2q + §2s) → user clicks Update as workaround → cluster of UI hangs → multiple refreshes needed.
- **Cluster self-stabilizes by ~stage 8 with one refresh.** Backend healthy throughout. Suggests SSE event burst in the early-stages window overruns the frontend reducer's back-pressure handling — independent of the state-machine drift covered by T1.
- **Execution-order implication for the proposal:** **fixing §2q (Auto reliability) is the highest-leverage single intervention in the entire backlog** — not because it's the worst individual bug, but because it removes the trigger that exposes every other symptom. If Auto works, the user never clicks Update, the SSE burst never happens, the cascade never fires. `PROPOSAL_state-machine-re-centering-v1.md` should be re-ordered to prioritize §2q before T1.
- **Short finding + cascade chain + diagnostic capture script:** [`FINDING_manual-update-click-triggers-ui-cluster.md`](FINDING_manual-update-click-triggers-ui-cluster.md).
- **2026-06-21 recurrence (finding §6.2):** post-refresh, the Applifier panel shows no "current stage" indicator even though queue widget + AI Gateway confirm Deep Reasoning is running with 3× cloud calls in flight. Plus a new sub-symptom — Deep Reasoning row reads `1,069 / 1,058 files · 100%` (progress overshoots the total by 11 files). Suggests SSE channel doesn't replay the `stage_start` for the in-flight stage on reconnect — only cumulative state. Worker progress emission not bounded by `progress_total` (cross-ref to §2j §8).

## 3. What we know about the data flow

```
┌──────────────────────────────────────────────────────────────────────┐
│ STAGE COMPLETION SIGNALS — multiple sources, must agree              │
├──────────────────────────────────────────────────────────────────────┤
│ 1. pipeline_run_metadata.json    ← canonical: who finished what when │
│    stage_metadata[].status         pending|running|completed|failed|skipped │
│ 2. <stage>_manifest.json         ← provenance: did the stage write?  │
│    .provenance.state               match|drift|missing|self_healed   │
│ 3. PipelineGroupStateMachine     ← in-memory: is anything active now │
│    .stage_results[stage]           running|completed|failed|skipped  │
│ 4. ManifestStore.age_summary()   ← mtime-derived: how stale?         │
└──────────────────────────────────────────────────────────────────────┘
            │
            ▼
┌──────────────────────────────────────────────────────────────────────┐
│ DASHBOARD READS                                                       │
├──────────────────────────────────────────────────────────────────────┤
│ /projects/{id}/pipeline/status — combines (1)+(2)+(3) into one blob   │
│   data.fast_sync / deep_enrichment / finalize  ← from (3)             │
│   data.stages.<stage>                          ← from (2)+manifest    │
│ /events SSE                     — pipeline_status push updates        │
│ /system/pipeline-queue           — orchestrator's queue snapshot       │
└──────────────────────────────────────────────────────────────────────┘
            │
            ▼
┌──────────────────────────────────────────────────────────────────────┐
│ GraphEnrichmentPipeline.tsx → derives per-row state from many props  │
│   enrichmentState, fastKnowledgeState, ...                           │
│   promoteForRebuild(...) → 'complete' | 'running' | 'not_built' | … │
└──────────────────────────────────────────────────────────────────────┘
```

**Drift surfaces** (places where (1)/(2)/(3)/(4) disagree → UI confusion):

| Drift | Observed symptom |
|---|---|
| (1) says `pending`, (3) says `skipped` | Stage shows "Running 0%" forever (the 2026-06-08 bug; partially fixed by P2) |
| (2) says `match`, (3) says no run | Stage shows "complete" but rollup says "incomplete" (suspected 2026-06-10 bug) |
| `/projects/{id}/pipeline/status.deep_enrichment` is `null` but `/system/pipeline-queue` says queued | Cross-endpoint disagreement (open) |
| `/queue` 404 but UI still calls it | Dead endpoint (the `/queue` → `/system/pipeline-queue` migration left stale callers) |

## 4. UI behavior contract (the source-of-truth this phase produces)

Goal: **the next agent should know what the UI should show for any pipeline state without having to reverse-engineer it from React props.**

### 4a. Stage row states (every row in every group)

| State | When | What the row should show | What it must NOT show |
|---|---|---|---|
| `disabled` | Stage is configured off | Greyed-out icon, label, no progress, hint "Disabled" | A progress bar, a percent, a spinner |
| `not_built` | First run never happened OR stage was reset | Label + "Not built" | A spinner, a 0% bar, "Pending" |
| `running` | Stage actively in-flight | Spinner, label, % progress (or indeterminate bar if `progress_total` unknown), live stat ("12/47 nodes…") | Stale stat from a prior run |
| `complete` | Stage finished, manifest matches, no newer inputs | Green check, label, last-run stat, age chip | A spinner, "Running…" |
| `complete_stale` | Stage finished but downstream inputs newer | Green check + amber stale chip | A green check with no chip |
| `failed` | Stage raised | Red icon, label, error tooltip | Silent success |
| `skipped` | Freshness check determined nothing to do | Grey check + "skipped: <reason>" tooltip | "Running 0%", "Iteration 0/?" |
| `paused` | User clicked pause | Pause icon, "Paused at stage N" | Spinner |
| `queued` | Stage acquired but waiting for slot | Hourglass, "Queued behind <other-project>" | Spinner |
| `recovering` | Selfheal is filling in a missing manifest | Spinner + "Self-healing…" | Plain "Running" |

### 4b. Group rollup states (Fast Sync / Deep Enrichment / Finalize headers)

A group's header state is the **lowest-priority terminal state across its stages**:

| Group state | When |
|---|---|
| `complete` | Every stage is `complete` or `skipped` |
| `complete_stale` | Every stage is `complete`/`skipped`, ≥1 stage's inputs newer than outputs |
| `running` | ≥1 stage is `running` or `queued` |
| `failed` | ≥1 stage is `failed` |
| `paused` | ≥1 stage is `paused` |
| `not_built` | ≥1 stage is `not_built` AND no stage is `running`/`failed` |

### 4c. Invariants the UI MUST hold

1. **Status-on-disk is truth.** When `pipeline_run_metadata.json:stage_metadata[X].status == "skipped"`, the panel for stage X must show `skipped`, not `running`. (P2 closed the *writer* side of this; we still need a UI test that exercises the *reader* side.)
2. **No `null` group → "stuck" rollup.** If `/projects/{id}/pipeline/status.deep_enrichment` is `null`, the group header should derive from stages, not show "incomplete by default."
3. **No conflicting `is_active`/`phase`.** `is_active: true` ↔ `phase ∈ {running, queued, paused}`. If we ever see `is_active: false, phase: running`, that's a state machine bug to surface, not a UI bug to paper over.
4. **No silent endpoint failure.** A 500 from a polled endpoint should produce a visible degraded-state indicator, not propagate as `undefined` into React props that then render as "stuck."
5. **No cross-project state.** Setting any flag on project A must not change what's displayed for project B.
6. **Refresh fixes everything.** A hard browser refresh must bring the UI back to a known-good state. If it doesn't, that's a daemon-side state bug, not a UI bug.

## 5. Diagnostic toolkit (the next agent runs these to interrogate live state)

```bash
# Daemon health + which process is serving
curl -s http://localhost:8400/health
ps aux | grep "prep.cli serve" | grep -v grep

# Per-project status (the dashboard's main poll target)
curl -s http://localhost:8400/projects/<PID>/pipeline/status | python3 -m json.tool | less

# Queue snapshot (note: NOT /queue — that path is dead, see §2f)
curl -s http://localhost:8400/system/pipeline-queue | python3 -m json.tool | head -30

# What manifest state actually says on disk
ls -la /Volumes/<path>/<project>/.sourceprep/*_manifest.json
cat /Volumes/<path>/<project>/.sourceprep/pipeline_run_metadata.json | python3 -m json.tool

# Tail the most recent run's structured event log
ls -lat /Volumes/<path>/<project>/.sourceprep/logs/pipeline_*.log | head -3
tail -50 /Volumes/<path>/<project>/.sourceprep/logs/pipeline_<latest>.log

# Streaming events the dashboard receives
timeout 5 curl -sN http://localhost:8400/events

# Test that PUT /global/config doesn't 500 (regression-prone area)
curl -s -X PUT http://localhost:8400/global/config -H "Content-Type: application/json" -d '{}' -w "\nHTTP: %{http_code}\n"

# Audit all `from prep.server import` inside function bodies (potential latent breaks like §2g)
grep -rn "from prep.server import" src/prep/ --include="*.py" | grep -v "def __init__" | head -20
```

## 6. Investigation plan (staged, for the next agent)

### Phase 145.1 — Browser-driven diagnostic harness (Playwright)

**Goal:** capture the symptom *while it's happening*, not via post-mortem.

#### Setup (one-time)

```bash
# Node 20+ required (matches the .nvmrc)
cd /Volumes/4TB-BAD/HumanAI/CoDRAG
npm install --save-dev @playwright/test
npx playwright install chromium webkit
mkdir -p tools/playwright/pipeline-uat
```

#### Harness script: `tools/playwright/pipeline-uat/probe-pipeline.ts`

The script should:

1. Boot a Chromium context with **console + network capture** enabled.
2. Navigate to `http://localhost:5174` (Vite dev) or `http://localhost:8400` (built dashboard served by daemon).
3. Snapshot the network requests during dashboard load: status codes, URLs, sizes. Flag any 4xx/5xx.
4. Snapshot the browser console: errors, warnings.
5. Wait until the Graph Enrichment panel is rendered.
6. For each panel row (Deep Reasoning, Group Reasoning, Module Synthesis, Continuous Deepening, Deep Knowledge), read the rendered text and the icon's `data-state` attribute (or compute it from CSS class).
7. Cross-reference each row's state against `/projects/{id}/pipeline/status.stages.<stage>` fetched directly.
8. Write a report to `tools/playwright/pipeline-uat/reports/<timestamp>.json` listing:
   - Network errors (URL, status, response body)
   - Console errors (message, stack)
   - State drifts (UI row says X, API says Y, for each row)
9. Take a full-page screenshot in light + dark mode.
10. Optionally: simulate a click on the X button in the queue and verify the toast fires + the cancel endpoint is called with `reason: "user_action"`.

#### Wiring it as a watcher (the user's actual ask)

```bash
# Run once
npx playwright test tools/playwright/pipeline-uat/probe-pipeline.ts

# Run every 30 seconds (Playwright doesn't have built-in watching;
# wrap in a shell loop or use the Monitor pattern from elsewhere in this repo)
while sleep 30; do
  npx playwright test tools/playwright/pipeline-uat/probe-pipeline.ts \
    --reporter=line || echo "DRIFT DETECTED at $(date)"
done
```

#### What this proves

- **If the harness can NOT reproduce the "Deep Reasoning stuck" symptom**, it's an environment-specific issue (browser cache, localStorage, etc.) and we add a "clear state" step.
- **If it can reproduce**, the report JSON will show *exactly* which signal (network call, prop, state-rollup) is producing the wrong rendered state. That collapses 2026-06-10's "sluggish + stuck" reports into a specific drift to fix.

### Phase 145.2 — State reconciliation audit

Inventory every place stage status is read, written, or derived:

- **Writers:** `pipeline_metadata.mark_stage_*`, `ManifestStore.write_*`, `PipelineGroupStateMachine.transition`.
- **Readers:** `/projects/{id}/pipeline/status` handler, `/projects/{id}/status` handler, the SSE event emitters in `orchestrator.py`.
- **Deriver:** the rollup logic at `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx:1391+` (the `deepStages` array) and the equivalent in `fastStages` / `finalizeStages`.

Build a state-flow diagram. Identify each pair where the writer and reader use different field names or different state vocabularies. (For example: `stage_metadata.status` uses `"skipped"`, but `stage_results` uses `"skipped"` too — good. `provenance.state` uses `"match" | "drift" | "missing"`, which doesn't translate 1:1 to a row state — possible drift source.)

### Phase 145.3 — UI invariant tests

For each row in §4a, write a Playwright test that:

1. Mocks the daemon's `/projects/{id}/pipeline/status` response to a specific shape.
2. Asserts the corresponding panel row renders the expected state per §4a.

Coverage targets:
- All 9 row states across all 15 stages.
- The 6 invariants in §4c.
- The known drift cases in §3.

### Phase 145.4 — Performance audit (the "sluggish" symptom)

1. Capture a Chrome DevTools Performance trace during a 60-second window where the dashboard is "sluggish."
2. Identify the main-thread blockers — the typical suspects:
   - SSE event handler doing sync work on every event (look for handlers in `state/enrichmentReducer.ts`, `hooks/useEnrichment.ts`).
   - Large list renders without virtualization (the Concepts panel after 1700+ concepts; the Audit panel after 2000+ findings).
   - Toast queue accumulating without cleanup (P3's `cf2d6874` fixed the timer leak; verify it's still fixed in dist).
3. For each blocker, propose a fix (memoization, virtualization, debouncing) but **do not implement in this phase** — produce the audit report only.

### Phase 145.5 — Latent-broken-import audit

Class of bug from §2g. Grep every `from prep.server import` inside function bodies and verify each symbol still exists in `prep.server`.

```bash
grep -rn "from prep.server import" src/prep/ --include="*.py" -A 3 | grep -B 1 -A 3 "def "
```

For each hit, run `python -c "from prep.server import <symbol>"` to verify it imports. Fix any others like `_deep_merge`.

## 7. Open questions (the next agent should answer these before proposing code changes)

1. **Why does `Deep Reasoning` show stuck across all projects on 2026-06-10 when SourcePrep's `enrichment.provenance.state == "match"`?**
   - Hypothesis A: the panel reads from a different field (e.g., `epistemic.enriched_nodes` count) and a recent change reset that field without restoring it.
   - Hypothesis B: the panel reads from `stage_results` in the in-memory state machine, but the daemon was restarted and the state machine doesn't rehydrate this signal.
   - Hypothesis C: `promoteForRebuild()` is being called with a stale rebuild scope marker.
2. **Why is `/system/pipeline-queue` empty but `Deep-Live-Cam` shows `phase=queued, active=True`?**
   - These two endpoints must derive from the same source. If they don't, that's the bug.
3. **What is the dashboard saving via `PUT /global/config` on load?** The 231-byte payload from the 2026-06-09 Network tab is the question. If it's saving a partial UI preference, the writer should be moved to a per-project endpoint.
4. **How many ASGI-Exception 500s land per dashboard load today?** The 2026-06-09 screenshot showed ≥7 in the first minute. Whitelisting "expected startup races" (e.g., `__embedding__` slot probe before slots are init'd) vs. surfacing real bugs requires counting them.
5. **Does the `_check_incomplete_deep_enrichment` watcher (`src/prep/core/watcher.py:664`) fire across projects on file events?** Per the P1 contract it should be per-project — but the symptom "every project stuck" hints at a cross-project trigger we haven't found.
6. **What's the actual cause of the 2026-06-10 sluggishness now that the PUT /global/config 500 is fixed?** Requires Phase 145.4 perf trace.

## 8. What we already fixed (do not redo)

| Commit | Fix |
|---|---|
| `cac65709` | Phase 136 Part 15 concurrency observability + SWARM_CAPABLE gating |
| `bb27f152` | Projects router: tri-state `included_paths` + watcher parity |
| `bfdabc55` | Reset: added 9 missing files to TRACE_FILES |
| `5adba8ed` | mcp_direct: prep no-arg routes to tool_hi |
| `11033fc2` + `b3c6f45f` | **P1: killed settings router cross-project fan-out** |
| `1a04e097` | **P2: added missing mark_stage_skipped helper** |
| `beba167e` + `a06caae2` | **P3a: cancel endpoint accepts `reason` field** |
| `75dc3c9a` + `cf2d6874` | **P3b: X-button toast + repeat-click escalation** |
| `f88c6b8c` + `01774ea2` | **P4: Write Guard 10% baseline shrink tolerance** |
| `62a6bb59` + `554666ae` | **P5: selfheal defers Write-Guard-rejected stages** |
| `7c9d01c2` + `e1bf3360` | **P6: scoped close_shared_embedders** |
| `f214fd39` | Auto_config deep-merge (fixes Switch-to-Manual clobber) |
| `551ad579` | Watcher clears guard markers for all stage groups |
| `f0f6af2d` | `.guard_rejections.json` added to RECOVERY_MARKERS |
| `883158db` | **`PUT /global/config` 500 — `_deep_merge` import fix (UI hang root cause)** |
| `2c6fb8a1` | **`useToast` non-throwing no-op default + Storybook wrap** |

## 9. Files the next agent should know

### Backend hotspots

| File | Why |
|---|---|
| `src/prep/services/pipeline/orchestrator.py` | Stage transitions, write guard recovery, journal writes |
| `src/prep/services/pipeline_metadata.py` | `mark_stage_started/completed/failed/skipped`, the source of UI state |
| `src/prep/services/pipeline/recovery.py` | Selfheal + guard rejection markers |
| `src/prep/api/routers/projects/watch.py` | Watcher trigger, debounce, `_check_incomplete_deep_enrichment` parallel |
| `src/prep/api/routers/projects/build.py` | Build trigger |
| `src/prep/api/routers/system.py` | `/global/config` GET + PUT, validation |
| `src/prep/api/routers/queue.py` | `/system/pipeline-queue` snapshot |
| `src/prep/server.py` | Startup auto-run, SSE setup, registry hydration |
| `src/prep/core/watcher.py` | `AutoRebuildWatcher`, file-event handling, `_on_debounce_fire` |

### Frontend hotspots

| File | Why |
|---|---|
| `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx` | The panel that displays Deep Reasoning + all stage rows. Rollup logic at lines 1391+. |
| `packages/ui/src/components/trace/pipelineRollup.ts` | Group rollup computation (`computeGroupRollup`) |
| `packages/ui/src/components/trace/rebuildProgress.ts` | Rebuild progress + scope handling |
| `src/prep/dashboard/src/hooks/useEnrichment.ts` | SSE reaction + polling + state machine |
| `src/prep/dashboard/src/state/enrichmentReducer.ts` | Reducer for the enrichment state tree |
| `packages/ui/src/components/navigation/SidebarPipelineQueue.tsx` | Queue widget, X-button cancel flow, toast wiring |
| `packages/ui/src/components/primitives/Toast.tsx` | Toast provider, useToast, no-op default |
| `packages/ui/src/components/console/LogConsole.tsx` | Process Logs panel (§2e — needs traceback grouping) |
| `packages/ui/src/api/client.ts` | Daemon HTTP wrapper, `/global/config` GET/PUT (line 1037 was the 2026-06-09 culprit) |

### Tests that pin current contracts

```
tests/test_settings_pipeline_config_no_fanout.py   ← P1 contract
tests/test_freshness_skip_metadata.py              ← P2 contract (end-to-end)
tests/test_pipeline_metadata_skip.py               (does not exist; user wrote test_freshness_skip_metadata.py instead)
tests/test_pipeline_cancel_reason.py               ← P3a contract
tests/test_write_guard_clustering_shrink.py        ← P4 contract
tests/test_orphan_clustering_recovery.py           ← P5 contract
tests/test_close_shared_embedders_scope.py         ← P6 contract
tests/test_project_update_auto_config_merge.py     ← auto_config deep-merge contract
tests/test_recovery_markers_destroy.py             ← guard markers destroy contract
tests/test_global_config_put_import.py             ← PUT /global/config import contract
```

## 10. Handoff instructions for the next agent

You're picking up an investigation, not a code task. Read this document end-to-end before doing anything. Then:

1. **Do not start coding fixes.** Phase 145.1 (Playwright harness) and 145.2 (state reconciliation audit) are diagnostic phases that produce evidence. Phases 145.3+ propose fixes based on what 145.1/145.2 surface.
2. **Run the diagnostic toolkit in §5 first.** Capture the current state. Compare to the user's reports (§2b, §2c) to verify the symptoms are still active.
3. **Build the Playwright harness from §6.1.** That's the user's actual ask: "use Playwright to actually watch the browser and see its behavior." Don't skip it for shortcuts.
4. **For each open question in §7, write a short hypothesis-and-test document** in this phase folder (`docs/Phase145_Pipeline-UI-Reliability/Q1-deep-reasoning-stuck.md`, etc.) before proposing a fix.
5. **Treat the UI invariants in §4c as a contract.** Any proposed code change must preserve them.
6. **Daemon restart is required** any time you touch `src/prep/**`. `prep serve` has no hot-reload.

### Anti-patterns from this session

- **Dismissing user reports because the backend says it's fine.** I did this on 2026-06-09 ("the pipeline completed, you must be confused") — the user was right and the UI was hung. Believe the user's reported experience; the backend's `result: "completed"` doesn't help if the UI never reflects it.
- **Fixing symptoms one at a time.** The plan that landed (P1–P6) closed real bugs but left the broader UI-state-contract gap unexamined. Don't fix the next single "stuck" report; produce the contract first.
- **Skipping daemon restart before live validation.** Multiple times this session I "fixed" something and the user kept hitting the bug because the daemon was running pre-fix code.

### When you're done

- Phase 145.1 lands a working harness + report format.
- Phase 145.2 lands a state-reconciliation audit document.
- §7 open questions each have an answer (with evidence) recorded.
- §4 invariants have at least one Playwright test each.
- This phase doc gets a "Status: closed" line at the top, dated.
