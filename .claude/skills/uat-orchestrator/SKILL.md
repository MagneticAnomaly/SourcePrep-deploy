---
name: uat-orchestrator
description: Use when asked to run hours-long automated pipeline-UI testing across real repos — overnight or multi-hour UAT campaigns, "test for a few hours and iterate", Phase 145 scorecard sessions, resuming an interrupted campaign, or deciding which repos are safe to target and whether the daemon may be restarted mid-campaign.
---

# UAT Campaign Orchestrator (Phase 145 T5)

You are the orchestration layer. `tools/phase145_uat/run_session.py` is the unit of work (one project × op matrix × N iters, resumable, scorecard out); this skill is the loop around it: pick targets, plan the campaign, run sessions, triage, file findings, decide what's next. The op matrix: Op-1 rebuild, Op-2 incremental, Op-3 mid-rebuild refresh, Op-4 update-during-rebuild, **Op-5 pause/resume mid-rebuild** (pause at 25s — defers until a group is actually running — resume at 55s, gated on ≥1 status poll observing the paused state). An Op-5 iter counts as pause coverage ONLY if events.jsonl shows `scheduled_pause_fired` then `scheduled_resume_fired`; a `scheduled_pause_never_fired` note (build finished too fast) or only `scheduled_pause_rejected` notes (lost the fire race every time) means the iter proved nothing about pause — re-run or say so in the scorecard notes. On a **never-built** project, Op-1 doubles as the initial-run test (fresh 15-stage build, state machine `idle→queued→running→completed` per group — pipeline-testing W1). Deeper pause scenarios (pause-at-boundary, pause-during-swarm, pause+cancel) stay manual via pipeline-testing §5. **Drive targets ONLY through `run_session` (Op-1..Op-5).** Never invoke `playwright_smoke` modes directly against user projects — `--modes initial` is `DELETE /index/destroy` and the scoped-reset modes wipe real indexes; the `playwright-smoke` skill stays authoritative for how the harness works, never for what to aim it at. `pipeline-testing` stays authoritative for backend probes — but see rule 1 before following any "restart the daemon" advice it gives.

**Governance:** Phase 145 is document-don't-fix. Harness improvements (`tools/`, `tests/`) are in-scope to ship with TDD; product/pipeline fixes (`src/`, `packages/`) require a scrutinized `PROPOSAL_*` and Eric's go-ahead. Commit locally per unit of work; never push.

## Safety rules (non-negotiable — the letter IS the spirit)

1. **Daemon restarts are gated, and `scripts/dev.sh` IS a daemon restart** (it kill-9s :8400 on every start). Before any restart, check `/system/pipeline-queue`: ANY paused group anywhere (long-parked pauses are deliberate — LLM-limit workarounds, Phase 148 territory) makes restart forbidden (F-65/F-69 corruption risk). In an unattended campaign the answer to "restart?" is always **stop the campaign and report**. "Explicit sign-off" means a message from Eric in the live conversation approving this specific restart — a standing "run overnight" prompt is NOT sign-off. If only the dashboard died, restart only it: `cd src/prep/dashboard && npm run dev` (background) — not `dev.sh`. (History: Applivation-Android held a deliberately-paused run for ~10 days until it was cancelled on 2026-07-22 — the gate exists because such parked runs recur; always check live.)
2. **Never `git stash`, `git checkout`, or otherwise mutate a target repo's working tree.** Proposal RU2's repo-locking is for Eric to do, not you. Record `git -C <repo> status --short` and interpret results accordingly. The harness's transient tick file is the only write you may cause — with one required cleanup: a timed-out incremental (Op-2) iter SIGKILLs the child before its own `tick.unlink()`, so **deleting the orphaned `prep_smoke_tick.py` at the target root after such an iter is required** and is not a violation. (Op-4's update action is an API call; it writes no file.)
3. **Never target, with any op:** SourcePrep itself (`f1636374-…` — it is the dogfood index your own MCP tools depend on, and rebuilding it mid-campaign conflates harness bugs with product bugs); any project whose queue entry shows a paused/held group; any project with an **active run you didn't start** (Eric runs parallel sessions); Halley/LinuxBrain (**banned pending Eric's explicit OK** — very large, never measured); any project whose dashboard toggle Eric has set inactive (the harness force-activates — don't override his toggle choices without his roster instruction); registry junk (pytest-leaked `api-test` entries were observed and cleaned 2026-07-22; treat any recurrence as junk, don't target it, note it).
4. **One driver at a time.** Before starting a session, `pgrep -f tools.phase145_uat.run_session` must be empty. After resuming an interrupted campaign, confirm `/pipeline/status` shows every group terminal before the first iter.
5. **`/pipeline/status` returning 500 = stop diagnosing UI, fix that first** (pipeline-testing §0/§8). The dashboard silently falls back to disk reads; every "UI bug" after that is noise.
6. **Spend is bounded by the campaign plan, not open-ended.** Real repos on real credits is approved policy (Eric, 2026-07-22) — within a plan you write BEFORE the first session (see loop step 0). At most one `--retry-non-pass` pass per session; a failure that survives it is a finding, not retry fuel.

## Pre-flight (every session, not just campaign start)

```bash
curl -s localhost:8400/health | jq .status               # "ok" — if daemon is down entirely, see rule 1 before dev.sh
curl -sI localhost:5174 | head -1                         # 200 — if dead, dashboard-only restart (rule 1)
curl -s localhost:8400/projects | jq '.data.projects[] | {id,name,path}'   # re-confirm IDs live — never trust cached IDs
curl -s localhost:8400/system/pipeline-queue | jq         # paused/active anywhere → rules 1 & 3
curl -s localhost:8400/projects/<pid>/pipeline/status | jq '.data.barrier'  # per target: active barrier + nothing running = the §2v wedge — recover BEFORE the campaign
ps -o etime= -p "$(pgrep -f 'prep.cli serve' | head -1)"  # daemon age — §2v wedge risk grows with uptime
git -C <target-repo> status --short                       # record, don't mutate (rule 2)
pgrep -f tools.phase145_uat.run_session                   # must be empty (rule 4)
df -g /Volumes/4TB-BAD | tail -1                          # < 20 GB free → stop condition
caffeinate -is &                                          # overnight campaigns: keep the Mac awake; kill it at campaign end
```

Always `.venv/bin/python` (never system python).

**Daemon freshness (§2v wedge).** `FINDING_force-from-start-rebuild-hangs-pre-registration-orphans-all-barrier`: on a daemon with hours of accumulated uptime (~8h observed), a rebuild can hang pre-registration and orphan an `all`-scope `.reset_barrier` that **survives restart** and silently no-ops every later rebuild. Before a long campaign, if the queue shows no active AND no paused work, a fresh daemon restart is permitted by rule 1 and **recommended** (also reclaims embedder RSS); confirm no `.sourceprep/.reset_barrier` exists on any target at boot (finding §11.3 — the file must be absent when the daemon starts). The harness defends mid-campaign: `run_session` aborts with **rc=4** when it detects an orphaned barrier, and a forced build that produces zero activity logs `no_activity_after_forced_build` as an error instead of a false pass.

## Repo roster (campaign set per Eric, 2026-07-22 — his dashboard-active projects)

Measured numbers live here — **update this table when you measure a new repo.** PowerMateReborn is demoted to harness-plumbing checks only (Eric 2026-07-22: campaigns run on his real active projects, not PMR).

| Role | Project | State (probed 2026-07-22) | Numbers / approach |
|---|---|---|---|
| **Initial-run subjects** (never built — Op-1 IS the initial-build test, backend W1 + UI) | apple-to-google-factory `30f77b65-…`, HomeColab-Android `49c90b65-…` | 0/15 stages built | first session = `--iterations 1 --operations Op-1 --per-iter-timeout 7200`; that run is also the duration measurement |
| Small built (probe → likely Fast tier: full Op-1..Op-5 × 2-3 iters) | SkyPath-Restart `bfbe8ab2-…` | built 12/15 | measure-first Op-2 probe, then full matrix if ≤3 min |
| Medium built (single-op sessions) | HomeColab `ef18334f-…` | built 12/15 | rebuild 45–90 min → `--per-iter-timeout 7200`, `--iterations 1` per op (Op-2, Op-1, Op-5) |
| Large built (completeness — run to finish, one op per session) | DebateHaus `76e2450c-…`, Applifier `7cdea5e4-…` (⭐ boosted) | built 12/15 | Op-2 probe first; rebuild ops `--per-iter-timeout 10800` |
| Conditional (check queue immediately before) | Applivation-Android `77ef0fb2-…` | deep_enrichment `cancelled` 2026-07-22 (the ~10-day paused run was cancelled); large | only if queue shows it clear; Op-1 clean-build first (`10800`), then Op-5 |
| Harness plumbing check only | PowerMateReborn `6955793f-…` (15 files) | built; **dashboard-inactive** — this row is the standing exception to rule 3's inactive ban, for harness verification ONLY | incremental op ≈ 65 s; `--per-iter-timeout 1200` — verify the harness itself, never campaign coverage |
| Off-limits (rule 3) | SourcePrep (any op), Halley/LinuxBrain (pending Eric), dashboard-inactive projects (SkyPath, ChatUserMemory, AI-App-Management, Deep-Live-Cam, Dinner.Vision, Paperclip as of 2026-07-22), junk entries | — | — |

**Measure-first rule.** Prerequisite: the target must already be built — status shows all groups complete/idle with data. On an all-complete target, run a single Op-2 probe (`--iterations 1 --operations Op-2 --per-iter-timeout 1800`): ≤ 3 min → Fast tier; longer → single-op sessions at `--per-iter-timeout ≥ 2× measured`, and measure Op-1 once with a generous cap before scheduling repeats. **A never-built or partial target gets an Op-1 baseline with a generous cap (`--per-iter-timeout 7200` minimum) as its entire first session — that run IS the measurement.** Never fire the Op-2 probe at an unbuilt repo: incremental on an unbuilt project starts a full 15-stage build and the 1800s cap SIGKILLs it mid-enrichment, wasting the credits and producing a garbage classification. Record every measurement in the table above.

## Commands

```bash
# Full session (Fast tier). Scorecard naming: SCORECARD_uat_<context>_<date>.md
# (<context> = repo or purpose; matches the existing corpus files)
.venv/bin/python -m tools.phase145_uat.run_session \
  --project-id <pid> --iterations 3 --operations Op-1,Op-2,Op-3,Op-4 \
  --per-iter-timeout 1200 \
  --output docs/Phase145_Pipeline-UI-Reliability/SCORECARD_uat_<context>_<date>.md

# Big repo: --per-iter-timeout is the single knob — the child watch budget
# follows as N-30 and RAISES the smoke's built-in 60m rebuild ceiling.
#   HomeColab-class: 7200-10800, --iterations 1, one op per session.

# Live progress (per-iter capture logs — PROPOSAL_playwright-uat-harness-v1 §9.3 #5)
tail -f tests/eval/ui_smoke/capture/<session>_<op>_iter<N>.log

# Resume after crash/interrupt (skips recorded iters)
... --resume <scorecard>.manifest.json --output <same-scorecard>
# One optional retry pass per session for recorded fail/error/skipped iters:
... --resume <manifest> --retry-non-pass --output <same-scorecard>
```

Scorecards + manifests go in `docs/Phase145_Pipeline-UI-Reliability/`; screenshots/events stay under `tests/eval/ui_smoke/` (gitignored — cite paths, don't commit). Evidence grows by hundreds of MB per campaign; never delete `run_*` dirs cited by committed scorecards, and any other pruning needs Eric's OK.

## The campaign loop

0. **Plan first.** Before the first session, write the campaign plan into the conversation (or the scorecard doc header): ordered sessions (repo × ops × iters), expected duration each, and the campaign end point. The campaign ends when the plan completes or a stop condition fires — never open-ended. A healthy completion gets a closing summary + trend DIFF versus the prior scorecards.
1. **Session** — one `run_session` invocation, run as a background task; wait on its completion notification (or a monitor/until-loop sized to the session length). Never hot-poll; never chain short sleeps. Tail the capture log only when you wake.
2. **Triage** — read the scorecard Results table. Invariant fail (I1/I2/I3/I13) → open the named `*_invariant_*_FAIL.png`, map via `INV_TO_FINDING`. `FAIL` with desync-only Notes → real §2r/§2b-family bug the invariants deliberately don't cover — file it, never dismiss as harness noise. `ERR`/`skip` → harness or daemon health; see pipeline-testing §7/§8 for diagnosis but rule 1 overrides its restart advice. Suspiciously all-green → check the selector contract hasn't gone blind (playwright-smoke §7).
3. **File** — recurrences get a dated note on the existing `FINDING_*`; new symptoms get `FINDING_*.md` + a `§2x` entry + a README document-index row. Add a DIFF block when a prior scorecard covers the same subject (format: `SCORECARD_uat_post-i3-fix_2026-06-22.md`). Durable cross-session facts (durations, repo quirks) → the roster table above or `prep_observe`.
4. **Decide** — harness gap → fix in `tools/` with TDD (in-scope). Product bug → file only. Then the next planned session, or the campaign end.

## Stop conditions (end the campaign, report, don't push through)

- **Intra-session abort:** 3+ consecutive iters timing out within one session → end the session now and go to evidence-capture; don't feed more iters to a stalling daemon. (Each timed-out iter still ran a real rebuild.)
- Two sessions dominated by `error×N 'timed out'` while `/health` stays ok → daemon-stall family (§2m). **First check for a sleep artifact:** a burst of simultaneous timeouts right after a gap in log timestamps means the Mac slept (caffeinate died?), not a daemon stall.
- A session dominated by ERR/skip of any single signature → re-run the full pre-flight (a dead dashboard produces exactly this) before scheduling anything else.
- LLM-failure signatures in daemon logs (repeated cloud errors, stages failing fast) → credits/limits exhausted; stop burning iterations, note Phase 148 (global LLM pause is unbuilt).
- **run_session exits rc=4** (orphaned-barrier abort), or rebuild POSTs hang while `barrier.active=true` with nothing running → the §2v pre-registration wedge. Recovery is finding §12 (`rm .sourceprep/.reset_barrier` + daemon restart) — the restart is rule-1 gated, so unattended: stop, report, cite the finding with the daemon's uptime (each occurrence is a time-to-wedge datapoint the proposal needs). Never `--retry-non-pass` through rc=4.
- `/pipeline/status` 500, journal-vs-state-machine disagreement, selfheal resurrecting fresh stages → pipeline-testing §8 red flags; evidence-capture mode.
- Disk: < 20 GB free on the data volume → stop (the daemon's SQLite state shares it; filling it risks index corruption, not just lost screenshots).
- Any queue entry newly paused/held that you didn't cause → hands off, report.

## Common mistakes

| Mistake | Reality |
|---|---|
| `scripts/dev.sh` to "fix the dashboard" | dev.sh kill-9s the daemon = ungated restart. Dashboard-only: `cd src/prep/dashboard && npm run dev`. |
| Restarting the daemon to "start clean" | Rule 1. Paused runs are load-bearing; unattended answer is stop-and-report. |
| `playwright_smoke --modes initial` on a user project | That's `DELETE /index/destroy`. Targets are driven through run_session ops only. |
| Rebuilding SourcePrep "because only incremental was banned" | SourcePrep is off-limits for every op — it's your own MCP context. |
| Measuring an unbuilt repo with the Op-2 probe | Unbuilt targets get an Op-1 baseline with a generous cap first. |
| Stashing a dirty target repo | Never mutate user repos — record and interpret instead. |
| Guessing budgets for a new repo | Measure-first rule. A guessed cap on a 60m rebuild burns the iter AND poisons the next one. |
| Treating desync-only FAILs as harness noise | They're the §2r/§2b family — file them. |
| Fixing the product mid-campaign | Document-don't-fix. `tools/` yes; `src/`/`packages/` needs a proposal. |
| Open-ended "keep testing" | Loop step 0: the plan defines the end. Retry-non-pass at most once per session. |
