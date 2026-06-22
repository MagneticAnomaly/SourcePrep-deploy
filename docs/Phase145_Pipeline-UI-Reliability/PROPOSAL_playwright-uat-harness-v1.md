# PROPOSAL v1 — Playwright UAT harness extension: iterate a test repo through every operation, assert Phase 145 §8 invariants, record results

> **STATUS: DRAFT v1 — T1 + T2 + T3 SHIPPED 2026-06-22, T4 (baseline capture) + T5 (cadence doc) awaiting execution.** Authored so that Opus (or Fable later) can pick up and execute after a computer restart without re-deriving context. This is a **methodology + extension** proposal — the underlying Playwright tooling already exists (`tools/playwright_smoke.py`). What's new is the invariant assertion layer, the operation matrix, the iteration loop, and the scorecard format.
>
> **T1 status (2026-06-22):** invariant assertion library landed at `tools/phase145_uat/invariants.py` + pytest at `tests/test_phase145_invariants.py` (43 cases, all passing). Adversarial multi-lens review run pre-merge; Tier 1 + 2 findings fixed in the same drop, Tier 3 gaps documented in §9 below. See §5 T1 for the actual file paths + deviations from the draft text.
>
> **T2 status (2026-06-22):** invariants wired into `watch_until_idle`. Three pre-work blockers from §9.2 cleared in the same commit:
> - Constants extracted to `tools/phase145_uat/constants.py` (closes circular import between invariants and playwright_smoke).
> - `packages/ui` adds `data-testid="current-stage-indicator"` to the spinner container and `data-testid="last-run-chip"` to the Phase 49 provenance `<p>` (both in `GraphEnrichmentPipeline.tsx`).
> - Invariant block calls `run_all(page, status)` per API-poll tick, dedup'd by `(invariant_id → evidence-signature)` and gated by a **2-tick persistence window** (a failure must persist across ≥2 consecutive polls before emitting) to absorb pause/resume + recovering SSE-commit races. Failures log as `invariant_failure` events with `{invariant_id, label, evidence}` + a screenshot tagged `invariant_<id>_FAIL_<seq>.png`. New `ModeSummary.invariant_failure_count` rolls up into a new "Invariants" column in `report.md`.
> - 7 new pytest cases (50 total): 3 covering the I13 collapsed-group skip path + 4 covering the persistence-gate helper. The shared scrape optimization called out in §9.2 was NOT taken — see §9.3 for follow-up.
>
> **T3 status (2026-06-22):** iteration runner + scorecard generator landed at `tools/phase145_uat/run_session.py`. Two new flags in `playwright_smoke.py` (`--refresh-at-secs`, `--update-at-secs`) inject the Op-3 / Op-4 side effects mid-watch. Four-lens adversarial review pre-merge surfaced 5 Tier-1 blockers (cascade-fail after subprocess timeout, Op-4 always-409 silent burn, Op-4 fired before assertions ungated, Op-3 reload silenced I13 via empty-group skip, markdown cell injection from stderr newlines) — all five fixed in the same commit. Cheap Tier-2s landed too: deeper health probe, partial-session banner, bare-fail-no-failures trend, glob expansion in mapped-to-findings, project re-select after reload, post-reload recovery gate for the persistence buffer, WARN→fatal for non-rebuild + scheduled-flag combo, subprocess `stdout=DEVNULL`, extracted scheduling helper for unit testability. Tier 3 follow-ups recorded in §9.3. **97 pytest cases total** (50 invariants + 47 run_session). See §5 T3 for the actual file paths + deviations from the draft text.

**Goal:** Take the existing `playwright_smoke.py` harness, add Phase 145 §4a + §8 invariant assertions to it, and iterate it methodically against a known test repo across all user-triggerable operations. Each iteration produces a row in a scorecard documenting which invariants passed, which failed, which §-letter findings the failures map to, and screenshot evidence per failure. The output is the "before" baseline against which any future fix work (PROPOSAL v2 of state-machine re-centering, etc.) gets measured.

**Architecture:** Three layers, each independently shippable:

- **L1 — Invariant assertion library** (new): one Python module that exposes each Phase 145 §8 invariant (I1–I13) as a callable that takes a `(playwright_page, api_status_payload)` pair and returns `(passed: bool, evidence: dict)`. Importable by `playwright_smoke.py` and by future test files.
- **L2 — `playwright_smoke.py` extension**: hook the L1 invariants into the existing desync-detection path. When an invariant fails, capture the same screenshot+state-snapshot bundle the existing harness already produces for desyncs.
- **L3 — Iteration runner** (new): a thin orchestrator (Python script or shell loop) that runs `playwright_smoke.py` N times across the operation matrix, accumulates results into a `SCORECARD_*.md` doc per session, and rolls up cross-session trends into a `BASELINE_phase145_uat.md`.

**Why this isn't already done by `playwright_smoke.py`:** the existing harness checks for API↔DOM disagreement on a few specific endpoints. It doesn't assert the structured invariants from REFERENCE §8 (e.g., "exactly one row per group is `running`"), it doesn't iterate methodically across the operation matrix, and it doesn't roll up into the scorecard format that's useful as fix-validation evidence.

**Independence:** This entire proposal is independent of the state-machine re-centering proposal. It can ship in parallel. It produces the baseline data that re-centering's eventual T1 will be validated against.

**Out of scope (still):**
- Authoring fixes for any failing invariant (those are the existing proposals' job).
- Generating the test repo from scratch (we'll use HomeColab — small, real, verified working).
- Full CI integration (this is local-laptop UAT; CI integration is a future scope).

---

## 0. Pre-flight: pick up after restart

If you're reading this after a computer restart, the only state you need is in this doc + the corpus. **Nothing in this proposal depends on in-memory state.** Bootstrap:

1. Open this file. Read §1–§4 to understand the plan.
2. Confirm the existing `tools/playwright_smoke.py` runs: `.venv/bin/python -m tools.playwright_smoke --help`.
3. Confirm playwright is installed: `.venv/bin/python -c "from playwright.sync_api import sync_playwright; print('ok')"`. If not: `.venv/bin/pip install playwright && .venv/bin/python -m playwright install chromium`.
4. Confirm the dashboard runs: `scripts/dev.sh` (or just `prep serve` + `cd src/prep/dashboard && npm run dev`).
5. Confirm HomeColab is registered: `curl -s http://localhost:8400/projects | python3 -c "import json,sys; print([p['id'] for p in json.load(sys.stdin)['data']['projects'] if 'HomeColab' in p['name']])"`. If not present, register it via the dashboard's Add Project flow against `/Volumes/Thunderbolt/XcodeProjects/HomeColab`.
6. Execute T1 → T2 → T3 from §5.

Everything else needed is in this doc. The proposal is self-contained.

---

## 1. Why this exists (and why now, before fix work)

We have 21 documented Phase 145 findings (§2a–§2u). Most have a hypothesis. None have a deterministic repro that survives a daemon restart. **Without deterministic repros, fix work is regression-prone**: we land a fix, the live-dogfood capture stops appearing, we declare victory, then it recurs in three weeks because we never had a test that would have caught it.

The Phase 145 §8 invariant catalog (in [`REFERENCE_canonical-pipeline-behavior.md`](REFERENCE_canonical-pipeline-behavior.md) §8) defines I1–I12. The recurrence at 2026-06-21 19:48 (logged in `FINDING_manual-update-click-triggers-ui-cluster.md` §6.2) suggests I13 too. Turning these into runnable assertions + iterating them across a known test repo produces three things:

1. **A baseline scorecard** — which invariants are passing today, which are failing, and how often.
2. **Deterministic repros** — when an invariant fails, the captured screenshot + API snapshot + daemon log tail is the repro a fix can be validated against.
3. **Regression coverage** — once fixes land, the same iteration loop confirms the invariant moves from failing → passing without breaking neighbors.

This is parallel to fix work (PROPOSAL_state-machine-re-centering-v1 + its SCRUTINY_v1). The fix work can author + scrutinize while the harness runs and produces the baseline. When fix work executes T1, this harness becomes the validator.

---

## 2. The test repo: HomeColab

**Why HomeColab:** small (1058 files, 171 inferred edges per `FINDING_edge-discovery-fast-completion-and-rebuild-progress-style-lag.md` §2.1), real codebase, verified working under Edge Discovery (`8.26 items/sec` is plausible). Small means each full rebuild takes ~3–5 minutes — fast enough to iterate meaningfully.

**Why NOT SourcePrep (this repo):** too large (2090 files, 30K+ nodes). One rebuild takes hours. Also, it's the dogfood subject — running UAT against it conflates "is the harness right?" with "is the product right?"

**Why NOT DebateHaus, SkyPath, etc.:** all valid candidates, but HomeColab has the most-recent verified-clean evidence. If HomeColab proves unstable for UAT, swap.

**Test repo state to maintain:**
- HomeColab should start each session at "all complete, ✓ on every stage." If it's in a different state, run one clean Rebuild All to get there.
- Don't modify HomeColab source files during UAT — keep the changeset small/none so we can isolate "did the pipeline behave correctly" from "did changes get picked up correctly."

---

## 3. The invariant subset for v1 (5 invariants, CI-grade)

From REFERENCE §8 + the recurrence in `FINDING_manual-update-click-triggers-ui-cluster.md` §6.2. Triaged per REFERENCE OQ8 ("which run in CI vs which are exploratory"):

| ID | Invariant | Closes finding | Implementation note |
|---|---|---|---|
| **I1** | At most one row with `data-stage-state` in {running, rerunning, rebuilding} per group whose phase is in `ACTIVE_PIPELINE_PHASES`. | §2r | Pure DOM check. Active set: {running, pausing, paused, recovering, cancelling}. Weakened from REFERENCE §8 "exactly one" to "at most one" — 0-running is allowed at stage boundaries; the §2r class is N ≥ 2. |
| **I2** | No row with state in {running, rerunning, rebuilding} simultaneously renders a VISIBLE `[data-testid="last-run-chip"]`. | DEFENSIVE — not §2r evidence | §2r screenshots actually show stale chips on COMPLETE downstream rows (I3 territory), not on running rows. I2 stays as a contract enforcement in case a future regression adds the bug class. |
| **I3** | No row at position > `current_stage_index` has state in {complete, stale, warning} for groups whose phase is in `ACTIVE_PIPELINE_PHASES`. | §2r | Needs both API (`current_stage`) and DOM. Active set is the same as I1/I13. Silently passes if phase is active but `current_stage` is missing (documented gap; see §9). |
| **I10** | `compute*State` invocation against any `(S1, status_payload)` pair produces the row state defined in REFERENCE §7.1. | §2a, §2l Thread A, §2n | Unit-test invariant, NOT a Playwright invariant — handled separately via the existing vitest setup proposed in PROPOSAL_threads-B-and-C-v2 Thread D. Don't include in this harness. |
| **I13** | For any group whose phase is in `ACTIVE_PIPELINE_PHASES`, exactly one row in that group has a VISIBLE `[data-testid="current-stage-indicator"]`. | §2u §6.2 (new) | Narrowed from "phase != idle" — terminal phases (completed/cancelled/failed) have no current stage so the invariant is N/A. _scrape_rows uses `offsetParent !== null` to reject display:none indicators. |

**v1 ships I1, I2, I3, I13** — landed 2026-06-22 in `tools/phase145_uat/invariants.py`. I10 is unit-testable (faster, more focused) and belongs in the vitest setup, not here.

**Phase set unification.** I1, I3, I13 all gate on the same `ACTIVE_PIPELINE_PHASES` set: `{running, pausing, paused, recovering, cancelling}`. This is wider than the proposal's first-draft "phase == 'running'" gate — the adversarial review caught that the §2u cluster includes pause/recover windows where the bug class is still visible. Single shared set so all three invariants stay in sync as phases evolve.

**Defer to v2 of this proposal** (when v1 has shipped + produced baseline data):
- I4 (queue widget surface), I5 (Force Reset toast), I6 (barrier cleared on failure), I7 (Knowledge Embedding stat after run), I8 (Update toast), I9 (auto-watcher fire visible), I11 (worker error surfaces), I12 (capacity_changed resizes don't cancel).

These are valuable but require either backend test fixtures we don't have (I6, I12), browser network capture beyond what `playwright_smoke.py` does (I8, I9), or scenarios that take much longer to set up (I11). v1 starts focused.

---

## 4. The operation matrix (what to drive HomeColab through)

Each operation gets one entry. The invariants in §3 should hold during every operation. v1 ships these four:

| ID | Operation | How to trigger via Playwright | Expected duration | Primary invariants exercised |
|---|---|---|---|---|
| **Op-1** | Rebuild All (clean state → all stages re-run) | Click Danger Zone → Reset All → confirm; wait for completion | ~5 min | I1, I3, I13 (rebuild has clean stage advancement) |
| **Op-2** | Incremental Update (touch one file, click Update) | Programmatic file touch outside the harness; in browser, click Update button on Graph Scope card | ~1 min | I1, I3, I13 (small update should fire 1-2 stages) |
| **Op-3** | Mid-rebuild refresh (start Rebuild All, refresh browser at ~30s in) | Click Rebuild → wait 30s → `page.reload()` → assert UI reconnects with correct state | ~5 min | I13 specifically — the SSE replay symptom from §2u §6.2 |
| **Op-4** | Click Update while Rebuild All is mid-run (the §2u cascade trigger) | Click Rebuild → wait 10s → click Update on Graph Scope → observe cluster | ~5 min | I1, I3, I13 — the §2u cluster |

**Iteration count per session:** start with **3 iterations per operation = 12 iteration-runs per session.** Roughly 20 minutes of harness + 10 minutes of HomeColab work between runs. Bump to 5 iterations once v1 is stable.

**Total session wall-clock: ~3-4 hours for a full v1 pass.** Schedule accordingly.

---

## 5. Task list (concrete, Opus-executable)

These are the steps to land v1 of the harness. Each is sized to be a single PR-shaped commit. TDD where it makes sense.

### T1 — Build the invariant assertion library  *[shipped 2026-06-22]*

**Files actually shipped** (proposal text deviated — see below):
- `tools/phase145_uat/__init__.py` (empty) ✓
- `tools/phase145_uat/invariants.py` ✓ — 4 invariants (I1, I2, I3, I13) + `InvariantResult` dataclass + `run_all` helper + selector contract docstring
- `tests/test_phase145_invariants.py` ✓ — 43 pytest cases (positive + negative + edge cases for each invariant + cross-cutting tests for `run_all`). Lives under `tests/` per pyproject.toml `testpaths`, not under `tools/phase145_uat/` as the proposal text said — deviation made so default `pytest` discovery picks them up as a regression net.

**Selector contract status:**
- Present in dashboard today (T1 wirable now): `[data-testid="pipeline-stage-row-{stage_id}"]`, `data-stage-id`, `data-stage-state`.
- Missing — required before T2 can wire I2 and I13: `[data-testid="last-run-chip"]` and `[data-testid="current-stage-indicator"]`. **Small packages/ui PR is a T2 prerequisite.** Until it lands, I2 passes by-vacuity on the live dashboard (no chip = no fail), and I13 fails loudly for every active group (no indicator = guaranteed fail) — both behaviors are deliberate forcing functions.

**Adversarial review (2026-06-22):** four-lens review (spec correctness, bug-class detection, integration contract, test coverage) run pre-merge via Workflow tool. Three critical issues caught and fixed in the same drop:
1. I1, I3, I13 phase gate widened from `phase == "running"` to `ACTIVE_PIPELINE_PHASES` ({running, pausing, paused, recovering, cancelling}). Original draft would silently pass during pause/recover windows of the §2u cluster.
2. I13 scrape tightened to `offsetParent !== null` so a packages/ui implementation that CSS-hides the indicator doesn't false-pass.
3. I2 docstring corrected — re-anchored as defensive (the §2r evidence does not show the chip-on-running-row pattern; I3 carries the actual §2r weight).

10 new regression tests added the same drop (phase variants, hidden-indicator, cross-group localization, etc.).

**Shape of `invariants.py`:**

```python
"""Phase 145 §8 UI invariants — callable assertions.

Each invariant returns InvariantResult(passed, evidence).
Evidence dict is what the caller writes alongside a screenshot
when the invariant fails.

Per PROPOSAL_playwright-uat-harness-v1.md §3.
"""
from dataclasses import dataclass, field
from typing import Any
from playwright.sync_api import Page


@dataclass
class InvariantResult:
    invariant_id: str
    passed: bool
    evidence: dict[str, Any] = field(default_factory=dict)


def I1_one_running_row_per_group(page: Page, api: dict) -> InvariantResult:
    """For any group at any moment, exactly one row in that group has data-state=running."""
    failures = []
    for group_id in ("fast_sync", "deep_enrichment", "finalize"):
        group_phase = (api.get(group_id) or {}).get("phase")
        if group_phase != "running":
            continue
        rows = page.locator(f'[data-group-id="{group_id}"] [data-stage-row][data-state="running"]')
        count = rows.count()
        if count != 1:
            failures.append({"group": group_id, "running_rows": count, "expected": 1})
    return InvariantResult("I1", not failures, {"failures": failures} if failures else {})


# ... I2, I3, I13 similar shape ...
```

**Test surface (`test_invariants.py`):** use Playwright's `static_html` trick — feed each invariant a mock DOM and mock API payload, assert the right pass/fail. No live dashboard needed.

Sample test:

```python
def test_I1_passes_with_one_running_row():
    html = """
    <div data-group-id="fast_sync">
      <div data-stage-row data-state="complete"></div>
      <div data-stage-row data-state="running"></div>
      <div data-stage-row data-state="not_yet_reached"></div>
    </div>
    """
    api = {"fast_sync": {"phase": "running"}}
    with sync_playwright() as p:
        page = p.chromium.launch().new_page()
        page.set_content(html)
        result = I1_one_running_row_per_group(page, api)
    assert result.passed


def test_I1_fails_with_two_running_rows():
    # ... similar but with two data-state="running" rows
    assert not result.passed
    assert result.evidence["failures"][0]["running_rows"] == 2
```

**Acceptance:** pytest passes for all 4 invariants with both positive and negative cases.

### T2 — Wire invariants into `playwright_smoke.py`  *[shipped 2026-06-22]*

**Files actually shipped** (deviated from the original draft below — see below):
- `tools/phase145_uat/constants.py` *(new)* — `STAGE_ORDER`, `STAGE_TO_GROUP`, `DOM_STATE_TO_CANON`, `CANON_STATES`. Extracted from `playwright_smoke.py` to break the circular import; both modules now import from here.
- `tools/playwright_smoke.py` *(modified)* — imports `run_all` as `run_invariants`; adds `ModeSummary.invariant_failure_count`; new persistence-gate helpers `_should_emit_invariant_failure` + `_clear_pending_invariant` (`INVARIANT_PERSISTENCE_TICKS = 2`); invariant block inside `watch_until_idle` between the per-stage desync loop and the idle-settle check, gated on `elapsed > startup_grace_seconds`; new `Invariants` column in `report.md`.
- `tools/phase145_uat/invariants.py` *(modified)* — imports moved to `constants.py`; I13 gains the empty-group skip; I3 docstring documents the cross-group gap; I2 / I13 docstrings updated to reflect the now-shipped selector contract.
- `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx` *(modified)* — `data-testid="current-stage-indicator"` on the spinner container (attribute conditional on `isRunning || isPaused`); `data-testid="last-run-chip"` on the Phase 49 provenance `<p>`.
- `tests/test_phase145_invariants.py` *(modified)* — 7 new cases: 3 for I13 collapsed-group skip, 4 for the persistence-gate helper. **50 total cases, all passing.**

**Adversarial review (2026-06-22):** four-lens review (T2 wiring, selector contract, constants extraction, failure-mode coverage) run pre-merge via Workflow. Tier-1 fixes landed in this commit:
1. **2-tick persistence gate** — pre-fix raw signature dedup would fire on a single SSE/DOM commit-lag tick during pause→resume. Now a failure must persist across `INVARIANT_PERSISTENCE_TICKS` consecutive polls before emitting; a pass between failures resets the counter. Trust-erosion concern addressed.
2. **I13 empty-group skip** — pre-fix the default collapsed dashboard rendered `CondensedGroupRow` instead of per-stage rows, so I13 fired with `marked_count=0` on every active group. Now an active group with zero rendered rows is treated as N/A (caller responsibility to expand groups before asserting).
3. **I3 cross-group leak documented** — review flagged that I3's §2r coverage only catches intra-group leaks. The cross-group sub-class (stale `finalize` rows during a `deep_enrichment` run) needs per-row provenance attributes that don't exist today. Documented as a known gap in I3's docstring + §9.1.
4. Stale `invariants.py` docstring sections refreshed (the "T2 not yet wired" + "PROVISIONAL selector contract" blocks were misleading post-T2).

**Deferred to T2 follow-up** (see §9.3): shared scrape per tick, StageRow vitest pinning, smarter per-invariant dedup key, `API_PHASE_TO_CANON` dead-code cleanup.

---

#### Original T2 draft (kept for reference)

In the existing desync-detection block (search for `desync` in the file), add a call to each invariant. When an invariant fails, write its evidence into the existing desync-event JSON + take a screenshot with the invariant ID in the filename.

```python
# inside the existing per-poll-tick block
from tools.phase145_uat.invariants import (
    I1_one_running_row_per_group,
    I2_running_row_has_no_stale_chip,
    I3_downstream_not_complete,
    I13_current_stage_decoration_exists,
)

INVARIANTS = [
    I1_one_running_row_per_group,
    I2_running_row_has_no_stale_chip,
    I3_downstream_not_complete,
    I13_current_stage_decoration_exists,
]

for inv_fn in INVARIANTS:
    result = inv_fn(page, api_status)
    if not result.passed:
        ts = datetime.now(timezone.utc).isoformat()
        page.screenshot(path=f"reports/{run_id}_{ts}_{result.invariant_id}_FAIL.png")
        write_event({
            "ts": ts,
            "kind": "invariant_failure",
            "invariant_id": result.invariant_id,
            "evidence": result.evidence,
            "screenshot": f"{run_id}_{ts}_{result.invariant_id}_FAIL.png",
        })
```

**Pre-condition:** the dashboard's per-stage row needs `data-stage-row` + `data-state` + `data-group-id` attributes. If they don't exist on every row today, add them in a separate small UI PR before T2 runs. Audit:

```bash
grep -rn "data-state\|data-stage-row\|data-group-id" packages/ui/src/components/trace/
```

If missing on some rows, that's a small `packages/ui` PR before this task can land. Roll it into T2's commit if trivial.

**Acceptance:** run `playwright_smoke.py --modes rebuild --iterations 1 --project-id <HomeColab-id>`, check `reports/` for at least one invariant_failure event (if any of §2r/§2u-shape bugs are live, they'll fire).

### T3 — Iteration runner + scorecard generator  *[shipped 2026-06-22]*

**Files actually shipped** (deviated from the original draft below — see notes):
- `tools/phase145_uat/run_session.py` *(new, ~660 LOC)* — `Operation` dataclass, `OPERATIONS` table (Op-1..Op-4), `SessionManifest` / `IterResult` with atomic-rename persistence, `daemon_healthy` + `project_pipeline_ready` two-step health probe, `cancel_and_quiesce` post-failure handler, `run_one_iter` subprocess wrapper, `parse_iter_result` event-log walker, `render_scorecard` markdown generator with `_md_cell` table-safe escape + partial-session banner + planned-iter trend denominator + glob-resolved evidence paths.
- `tools/playwright_smoke.py` *(modified)* — `--refresh-at-secs` / `--update-at-secs` CLI flags; pure `_advance_scheduled_actions` scheduler (unit-testable); `expand_all_groups` helper (clicks every chevron with `aria-label="Expand group"`); `watch_until_idle` gains `project_name` kwarg + `post_reload_recovery` gate that suppresses invariant emit/clear during the empty-DOM tick that follows `page.reload()`; scheduled-update 409 from the `PIPELINE_ALREADY_RUNNING` orchestrator guard is logged as `note` not `error` so Op-4 doesn't burn every iter as `ERR`; WARN→fatal if a scheduled-flag is paired with a mode other than `rebuild`; `run_rebuild` calls `expand_all_groups` once at the top of every watch so I13 has per-stage rows from t=0.
- `tests/test_phase145_run_session.py` *(modified)* — 47 cases total: `_advance_scheduled_actions` (6), `_md_cell` escape (6 + 2 integration), partial-session banner + planned-denominator trend (3), bare-fail-no-failures trend (1), `_resolve_evidence_paths` glob (4), `project_pipeline_ready` + `cancel_and_quiesce` + `wait_for_pipeline_idle` failure paths (3), plus the earlier 22 cases for parse/render/manifest/CLI. **97 pytest cases across Phase 145 T1+T2+T3, all passing.**

**Adversarial review (2026-06-22):** four-lens review (runner correctness + resume, scorecard fidelity, scheduled-action races, test coverage) run pre-merge via Workflow. **Five Tier-1 blockers** caught and fixed in this commit:
1. **Lens A #1 — cascade-fail after subprocess timeout.** Pre-fix, a 15-minute TimeoutExpired SIGKILLed the child but the daemon-side pipeline kept running. Every subsequent iter 409'd on `/pipeline/rebuild` and recorded `ERR`. One stall would have poisoned 11 of 12 iters in a 3-hour session. Now: after any non-pass / non-zero-rc iter, `cancel_and_quiesce` POSTs `/pipeline/cancel` and polls until no group is `running` (≤30s cap). The detail string lands in the scorecard notes so the reader sees what the runner did.
2. **Lens C #1 — Op-4 always-409 silent burn.** Pre-fix, `api.run_all(pid)` during a rebuild raised on the orchestrator's `PIPELINE_ALREADY_RUNNING` guard. The except branch logged it as an `error` and incremented `error_count`. Op-4 status would have read ERR in every iter, indistinguishable from real bugs. Now: the 409 is matched (HTTP status + RuntimeError-string variants) and logged as a `scheduled_update_rejected` `note` subtype.
3. **Lens C #2 — Op-4 fired before assertions were ungated.** Pre-fix, `--update-at-secs 10` against `startup_grace_seconds=15` + `INVARIANT_PERSISTENCE_TICKS=2` meant the cluster window had closed before the first invariant emit was possible. Now: Op-4 fires at `20s`. Documented in `OPERATIONS` rationale.
4. **Lens C #3 — Op-3 reload silenced I13 via empty-group skip.** Pre-fix, `page.reload()` reset `fastCollapsed`/`deepCollapsed`/`finalizeCollapsed` React state to `True` defaults → groups rendered `CondensedGroupRow` → `_scrape_rows` returned 0 per-stage rows → I13's empty-group skip fired → I13 reported ✓ on every Op-3 iter regardless of bug. Now: `expand_all_groups` runs once at top of every rebuild watch (so I13 has rows from t=0) AND inside the new `post_reload_recovery` block (so it runs again as soon as the panel re-hydrates after a scheduled refresh). `watch_until_idle` also takes `project_name` so it can `select_project_in_dashboard` after reload — the auto-select-first-project effect in `useProjectManager.ts` is a footgun for any account with multiple projects.
5. **Lens B #1 — markdown table corrupted by `\n`/`|` in stderr-derived notes.** Pre-fix, a Python traceback in `notes` (which `parse_iter_result` builds from subprocess stderr tail) terminated the markdown table row. Every subsequent row rendered as broken text and the scorecard reader silently lost evidence. Now: `_md_cell` escapes `|` → `\|` and collapses `\n` → ` · `. Applied to every table-cell interpolation. Two pytest cases pin the regression.

**Cheap Tier-2 fixes also landed in this commit** (not all of Lens A/B/C/D — only the ones whose blast-radius matched the files we were already editing):
- Lens A #3: two-step health probe — `daemon_healthy` (cheap `/health` 200) + `project_pipeline_ready` (full `/projects/{pid}/pipeline/status` 200). Catches the partial-startup case where the daemon is up but the registry hasn't hydrated.
- Lens A #4: trend percentages use PLANNED denominator (`manifest.iterations`), not just observed. Partial sessions get a banner + `observed N/M` suffix per trend line. No more `1/1 (100%)` reading like `1 of 3 failed`.
- Lens B #2: `status=='fail'` with empty `failures` list now surfaces in trends (`failed without invariant evidence — see Notes`). Pre-fix, trends could say "all passed" while Results table showed FAIL.
- Lens B #4: `_resolve_evidence_paths` globs the actual screenshot files at render time and emits concrete paths. Falls back to the `*.png` pattern + a `_(pattern; no files on disk)_` marker only when the run_dir is missing.
- Lens C #4: project re-select after `page.reload()` (threaded `project_name` through `run_rebuild` → `watch_until_idle`).
- Lens C #5: `post_reload_recovery` gate suppresses invariant emit AND `_clear_pending_invariant` during the post-reload empty-DOM window. A real bug whose persistence buffer was mid-accumulation when reload fired survives the reload without losing its count.
- Lens C #6: WARN→fatal when scheduled-flag is paired with non-`rebuild` mode (silent ignore was the wrong ergonomics).
- Lens D #1: `_advance_scheduled_actions` extracted as a pure function — 6 unit tests on the scheduling state machine without spawning a browser.
- Lens D #2: `test_refresh_flag_with_non_rebuild_mode_*` now points at `--api-url http://127.0.0.1:1` so it's deterministic regardless of whether the user has a daemon on `:8400`.
- Lens D #3: subprocess `stdout=subprocess.DEVNULL` instead of `capture_output=True`. 12 iters × 15-minute × verbose-logging no longer accumulates hundreds of MB in the parent.

**Deferred to T3 follow-ups** (see §9.3 for the list): streaming subprocess output to file vs DEVNULL, `--retry-non-pass` resume flag, browser/subprocess `atexit` cleanup after SIGKILL, forward-incompatible manifest tolerance, per-iter unique subdir for run_<ts> collision-proofing, defense-in-depth `set_active` from the runner, Op-4 UI-click variant (more faithful §2u repro than the API-call path), multi-fire guard doc in `watch_until_idle`, Op-4 scorecard cell classification of rc-nonzero reasons, ModeSummary schema contract test, resume-from-real-manifest integration test.

---

#### Original T3 draft (kept for reference)

**Files:**
- Create: `tools/phase145_uat/run_session.py`
- Create: `docs/Phase145_Pipeline-UI-Reliability/SCORECARD_uat_2026-MM-DD.md` (per session)

**`run_session.py` shape:**

```python
"""Phase 145 UAT session runner — drives playwright_smoke.py through the §4 operation matrix.

Reads operations from a config, runs N iterations of each, accumulates results.

Usage:
    .venv/bin/python -m tools.phase145_uat.run_session \\
        --project-id <homecolab-id> \\
        --iterations 3 \\
        --output docs/Phase145_Pipeline-UI-Reliability/SCORECARD_uat_$(date +%Y-%m-%d).md
"""
OPERATIONS = [
    {"id": "Op-1", "modes": "rebuild", "label": "Rebuild All clean"},
    {"id": "Op-2", "modes": "incremental", "label": "Incremental Update"},
    {"id": "Op-3", "modes": "rebuild", "extra": "--refresh-at-secs 30", "label": "Mid-rebuild refresh"},
    {"id": "Op-4", "modes": "rebuild", "extra": "--update-at-secs 10", "label": "Update during Rebuild"},
]

# Op-3 and Op-4 require new flags in playwright_smoke.py — author them in T3 too
```

**Scorecard output format** (one `## Operation` section per op, one `### Iteration N` per run):

```markdown
# Phase 145 UAT Scorecard — 2026-06-22

**Project:** HomeColab (id `ef18334f-...`)
**Iterations per op:** 3
**Session start:** 2026-06-22T08:00:00Z

| Op | Iter | I1 | I2 | I3 | I13 | Notes |
|---|---:|:--:|:--:|:--:|:--:|---|
| Op-1 Rebuild All | 1 | ✓ | ✓ | ✗ | ✓ | I3 fail: Group Reasoning showed complete at stage 6 — see screenshot |
| Op-1 Rebuild All | 2 | ✓ | ✓ | ✓ | ✓ | clean |
| Op-1 Rebuild All | 3 | ✓ | ✗ | ✓ | ✗ | I2: Knowledge Embedding row spinning with "yesterday 1384 chunks" chip; I13 missing for ~3s mid-stage-5 |
| Op-2 Incremental Update | 1 | … | … | … | … | … |
... etc ...

## Rolled-up trends

- **I3 failure rate: 1/3 (33%) on Op-1** — recurrence of §2r in rebuild scenarios
- **I2 failure rate: 1/3 (33%) on Op-1** — same root family as I3 (compute*State family race)
- **Op-4 cluster reproductions: 3/3 (100%)** — §2u reliably reproducible via "Update during Rebuild"

## Mapped to findings

| Failure | Maps to | Evidence file |
|---|---|---|
| Op-1 iter 1 I3 | §2r | reports/Op-1_iter-1_I3_FAIL.png |
| Op-3 iter 2 I13 | §2u §6.2 | reports/Op-3_iter-2_I13_FAIL.png |
```

**Acceptance:** running `run_session.py` produces a SCORECARD doc with at least 12 rows (4 ops × 3 iters), and the rolled-up trends section is non-empty if any failures occurred.

### T4 — Establish baseline + commit it  *[1 hour passive (run time) + 30 min review]*

Run a full session (T3 with default settings) against HomeColab. Commit the SCORECARD output as `SCORECARD_uat_baseline_2026-MM-DD.md` to the corpus. This becomes the "before" snapshot.

**Acceptance:** the SCORECARD doc is committed to `docs/Phase145_Pipeline-UI-Reliability/`. README's document index updated to include it.

### T5 — Wire the harness into Opus's regular check-in pattern  *[30 min]*

Document in this proposal (§6 below) how to invoke the harness on a recurring cadence — e.g., every day before starting fix work, run one iteration of each op to detect overnight drift.

---

## 6. After v1 ships: cadence and feedback

Once T1–T4 are committed:

- **Daily UAT:** before any code change, run `run_session.py --iterations 1`. Takes ~20 min. Compare scorecard to baseline. Any new failures → log to corpus as §2x recurrence + investigate.
- **Pre-fix-PR UAT:** before opening a PR for any Phase 145 fix, run full session (3 iters). The PR's "Test plan" section should reference the SCORECARD delta.
- **Post-fix-PR UAT:** after merging, run full session again. Confirm the targeted invariant moves from FAIL → PASS without other regressions.

The SCORECARD docs accumulate in the corpus as a time-series. After 10–20 sessions, the trend data is itself a Phase 145 deliverable — "here's what was broken, here's what we fixed, here's what's stable."

---

## 7. Risk register

| # | Risk | Mitigation |
|---|---|---|
| **RU1** | The dashboard's stage rows don't have the `data-stage-row` / `data-state` / `data-group-id` attributes the invariants assume. | T2 includes an audit step. If attrs missing, add them in a tiny UI PR before T2 lands (the attrs are aria/test-friendly anyway). |
| **RU2** | HomeColab proves unstable for UAT (e.g., its content drifts or it's modified during sessions). | Lock HomeColab's git state at the start of each session: `cd /Volumes/Thunderbolt/XcodeProjects/HomeColab && git stash && git checkout HEAD`. Document in §2. |
| **RU3** | Op-3 (mid-rebuild refresh) and Op-4 (update-during-rebuild) require flags that don't exist in `playwright_smoke.py`. | Author the flags in T3 as part of the runner work. Each is ~20 lines. |
| **RU4** | The 5-iteration cap is too tight to catch flaky failures. | Start with 3 (per §4). If pass/fail oscillates within a single op, bump to 5 in v2. |
| **RU5** | The scorecard format becomes its own analysis burden — generating insight requires reading 20+ docs. | After 10 sessions, write `SYNTHESIS_phase145_uat_trends.md` that rolls up the scorecard time-series. Don't try to read every individual scorecard. |
| **RU6** | Daemon stalls (§2m) corrupt UAT sessions — what looks like an invariant failure is actually a daemon hang. | Add a daemon-health pre-check to `run_session.py`: `curl -s http://localhost:8400/health` before each iteration. If silent, abort iter, log + skip. |
| **RU7** | The harness adds a per-poll-tick overhead (4 invariant checks × 30 ticks/min × N rows = noticeable). | If the smoke run is noticeably slower with invariants on, drop the per-tick cadence to every 2nd tick. Acceptable tradeoff. |
| **RU8** | Opus has limited test attention span — running long iterations without supervision risks the harness drifting. | T3's runner writes JSON event log per iter; on harness restart, runner resumes from the last completed iter. State is on disk, not in memory. |

---

## 8. Scrutiny prompts (the second-guess pass)

When this v1 is scrutinized:

1. **Are the 4 invariants enough for v1?** Or should I5 (Force Reset toast) be added so we can verify barrier-clear behavior?
2. **Is HomeColab the right test repo, or is a synthetic fixture better?** A synthetic repo (e.g., `tests/eval/sample_repos/generated/rust_repo` — the existing `smoke-test` project) might be more controllable, but it's not a real-world shape. Trade-off worth discussing.
3. **Should the iteration runner be Python or shell?** Python is more portable + can structure the scorecard output directly. Shell is simpler for low-overhead iteration. Recommendation: Python (it integrates cleanly with the existing tool surface).
4. **What's the right cadence after v1?** Daily UAT is the proposal's suggestion. Could be too aggressive (interrupts work) or too lax (drift between sessions). Worth picking based on actual fix-PR rhythm.
5. **Does this proposal conflict with anything in `PROPOSAL_state-machine-re-centering-v1.md` T3.b (Playwright invariant suite)?** That proposal mentioned the invariant suite as part of T3 (long-term invariant enforcement). This proposal *is* T3.b's concrete authoring plan. Worth cross-linking so the v2 state-machine-re-centering proposal can drop T3.b in favor of this doc.

---

## 9. What this proposal does NOT propose

- **A fix for any failing invariant.** That's the existing proposals' job. This harness only detects + records.
- **CI integration.** v1 is local-laptop UAT. CI is a future scope.
- **Coverage of every Phase 145 finding.** Only the §-letters that map to I1–I3 + I13 are exercised. Others stay tracked in the corpus.
- **Authoring new invariants beyond I1–I3, I13.** I4–I12 stay in REFERENCE §8 for v2 of this proposal.

### 9.1 Known gaps after T1 (from 2026-06-22 adversarial review)

The four-lens review of the T1 library named these as bug classes the v1 harness does **not** detect. They're listed here so future reviewers don't assume coverage that doesn't exist. Each is a candidate for v2 of this proposal or a separate Thread-D-shape follow-up.

| Gap | Bug class | Findings affected | Fix shape |
|---|---|---|---|
| **I-NEW-PROGRESS** | Progress numerator > denominator (`1069 / 1058 files · 100%`) or non-monotonic regression mid-stage. Scraper reads only `data-stage-state`; never reads `data-stage-progress`. | §2j, §2u §6.2 | New invariant: per row, `progress_current ≤ progress_total` and monotonic non-decreasing within a single active window. Requires a new field in `_scrape_rows`. |
| **I-NEW-SPINNER** | Spinner glyph rendered on a row whose `data-stage-state` is in `pending` / `not_built` (the "Not run with a spinner glyph" symptom). I1/I2 never inspect non-running rows. | §2u §6.2 | New invariant: `has_spinner` iff state in `RUNNING_DOM_STATES`. Requires a `data-testid="row-spinner"` or equivalent affordance, plus a `has_spinner` field in `_scrape_rows`. |
| **I-NEW-COMPLETION-VS-MANIFEST** | Stage rendered as "Not run" while its worker actually ran (with 0 derivables or a failure that wrote a manifest). UI's count-gate doesn't agree with `manifest-exists` on disk. | §2n | Not invariant territory — UI-gate fix (replace count-gate with manifest-exists gate per `FINDING_stage15-antibodies-never-complete.md` §5 Q1). Track as a separate T-issue. |
| **I3 + I13 silent-skip** | When `phase` is in `ACTIVE_PIPELINE_PHASES` but `current_stage` is missing/null, I3 and I13 short-circuit silently. The phase-active-with-no-current-stage shape is itself a REFERENCE §4 contract violation. | Potential during §2u §6.2 SSE-replay window | Sibling invariant or harness-level anomaly log: "active phase ⇒ current_stage present." Don't bury as silent pass. |
| **I1 zero-running across N polls** | I1 weakens to "at most one" to ignore stage-boundary transients. A persistent 0-running observation across many consecutive polls (e.g., refresh dropped the `data-stage-state="running"` attribute and never restored it) is a real bug class and is invisible to I1. | §2u §6.2 family | Sibling invariant (I1b): "phase active for ≥ N polls AND zero running rows ⇒ failure." Requires harness state across ticks; not a stateless invariant. |
| **I13 visibility** | Current visibility check uses `offsetParent !== null`, which catches `display:none` but not `visibility:hidden` or `opacity:0`. A regression that swaps to those hide methods would false-pass I13. | Future regression | Tighten the scrape predicate with `getComputedStyle(el).visibility !== 'hidden' && getComputedStyle(el).opacity !== '0'`. Cheap; do when first false-pass observed. |
| **I3 cross-group stale-leak** *(added 2026-06-22 T2 review)* | I3 only inspects rows in groups whose API phase is in `ACTIVE_PIPELINE_PHASES`. If deep_enrichment is running while finalize-group rows still show `stale`/`complete` from a prior run, I3 silently passes (finalize's phase is idle/queued/completed, so the loop short-circuits). The §3 table claims I3 closes §2r — that's only true for the intra-group leak path. | §2r (cross-group sub-class) | Needs a per-row "this-run vs prior-run" provenance attribute on stage rows so a stale row in a non-active group can be flagged when ANY group is active. Out of scope for T2; track as a known gap. |
| **I13 condensed-group rendering** *(addressed in T2)* | Default dashboard renders `CondensedGroupRow` for collapsed groups; per-stage rows are absent from the DOM. Before the T2 fix, every active collapsed group fired I13 with `marked_count=0`. | Default dashboard state | **Closed in T2 by skipping groups with zero rendered rows.** Documented in I13's docstring + 3 new pytest cases. The harness must expand groups before running invariants if it wants live coverage of a specific build — otherwise I13 is N/A by design. |
| **I13 recovering/cancelling false positives** *(absorbed in T2)* | During phase=recovering or pausing→resuming, brief tick windows can leave both `isRunning` and `isPaused` false on every row. Raw signature-dedup would fire on each such tick, eroding trust. | Pause/resume + crash recovery | **Absorbed in T2 by a 2-tick persistence gate** in the harness — a failure must persist across ≥2 consecutive polls before emitting. False-positive races shorter than `poll_interval * (persistence_ticks - 1)` (≈4s at defaults) are silently dropped. |
| **Op-3 reload silenced I13 via empty-group skip** *(addressed in T3)* | `page.reload()` resets React's per-group `fastCollapsed`/`deepCollapsed`/`finalizeCollapsed` state to True. Collapsed groups render `CondensedGroupRow` and `_scrape_rows` returns 0 per-stage rows → I13's empty-group skip (T2 fix) short-circuits as N/A. Without an expand step, Op-3 reports I13=✓ on every iter regardless of the §2u §6.2 bug. | §2u §6.2 (Op-3 specifically) | **Closed in T3**: `expand_all_groups` runs at the top of every `rebuild` watch (so I13 has rows from t=0) AND inside a new `post_reload_recovery` block (re-expands as soon as the panel re-hydrates post-reload). `watch_until_idle` also re-selects the project after reload — the auto-select-first-project effect in `useProjectManager.ts` was a footgun for accounts with multiple projects. |
| **Op-4 scheduled update always 409s mid-rebuild** *(addressed in T3, half-deferred)* | The orchestrator's `PIPELINE_ALREADY_RUNNING` guard rejects `POST /pipeline/all` while a rebuild is in flight. The httpx `raise_for_status` bubbled the 409 as an exception that pre-fix went through the `except Exception` → log as `error` → increment `error_count` path. Every Op-4 iter would have read as `ERR` in the scorecard, indistinguishable from real subprocess failures. | §2u (Op-4 specifically) | **Closed in T3 for the false-fail blast radius**: scheduled-update 409 is caught (status-code + RuntimeError-string variants) and logged as a `note` event subtype `pipeline_already_running`, not `error`. **Still open for repro fidelity**: the React-side cluster symptoms (toast, loading state) fire from a Playwright button click against the Update widget more reliably than from an API call. Tracked as §9.3 follow-up #11. |
| **Op-4 fired before assertions ungated** *(addressed in T3)* | Original T3 draft put `--update-at-secs 10`, but `startup_grace_seconds=15` + `INVARIANT_PERSISTENCE_TICKS=2` mean the first invariant-emit-eligible tick is ≈19s. The Op-4 cluster window had closed by then. | §2u (Op-4 specifically) | **Closed in T3**: Op-4 now fires at `--update-at-secs 20`, one safety tick after the persistence gate's first emit window. Constants documented in `OPERATIONS` table comment. |
| **SCORECARD table corrupted by stderr-newlines / pipes** *(addressed in T3)* | `parse_iter_result` builds the `notes` field from subprocess stderr tail + json decode errors, both of which can contain `\n` (Python tracebacks always do) or `|` (rare but possible). Without escaping, a single errored iter row terminated the markdown table and corrupted every subsequent row. Silent SCORECARD corruption is exactly the "wastes a 3-hour session" failure mode T3 is supposed to prevent. | All ops, but most visible on `error` status | **Closed in T3**: `_md_cell` helper escapes `|` → `\|` and collapses `\n` → ` · `. Applied to every interpolation in the Results table + Mapped-to-findings table. 8 pytest cases cover the escape behavior + table integration. |

### 9.2 T2 prerequisites *(closed 2026-06-22)*

All three blockers cleared in the T2 commit:

1. ✅ **packages/ui PR** — `data-testid="current-stage-indicator"` lives on the spinner container (attribute is conditionally present; element always mounted for layout stability). `data-testid="last-run-chip"` lives on the Phase 49 provenance `<p>`. Both in `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx`.
2. ✅ **Constants extraction** — `tools/phase145_uat/constants.py` now owns `STAGE_ORDER`, `STAGE_TO_GROUP`, `DOM_STATE_TO_CANON`, `CANON_STATES`. Both `playwright_smoke.py` and `invariants.py` import from there. Identity-preserving (verified via runtime `is` check).
3. ⏸ **Shared scrape helper** — **deferred** to a T2 follow-up (see §9.3). Per-tick T2 currently fires 4 redundant `page.evaluate` calls; the perf cost is small (~40ms / 2s tick) but the bigger concern is same-tick consistency (each invariant samples a slightly different DOM moment). Worth tightening once the harness has run end-to-end and the signature is stable.

### 9.3 T2 + T3 follow-ups (post-2026-06-22)

Things explicitly deferred so the T2 / T3 PRs stayed scoped:

**From T2 (2026-06-22 review):**

1. **Shared scrape per tick** — extend `scrape_pipeline_dom` to also return `has_last_run_chip` and `has_current_stage_indicator`, then change the invariant signature from `(page, api)` to `(rows, api)`. Cuts 4 `page.evaluate` calls per tick to 1 and guarantees same-tick consistency across invariants. Tests keep page-driven scraping via a thin adapter.
2. **StageRow vitest coverage** — `packages/ui/src/components/trace/__tests__/` has no test pinning the `current-stage-indicator` / `last-run-chip` contract on the React side. If someone refactors the spinner container or the provenance `<p>`, vitest stays green and the regression only surfaces when the next Playwright smoke runs. ~40 LOC of JSX-tree-walk tests (no `@testing-library/react` needed) closes this. Follow the pattern in `RebuildingRow.test.tsx`.
3. **Smarter dedup key per invariant** — current dedup hashes the full evidence JSON; a recurring leak whose `current_stage` changes naturally as the build advances re-fires per current_stage change instead of once. Could be replaced with an `InvariantResult.dedupe_key()` method declared per invariant (e.g. I3 keys on `(downstream_stage, downstream_state)`, I1 keys on `frozenset(running_stages)`).
4. **`API_PHASE_TO_CANON` cleanup** — defined in `playwright_smoke.py` but no references repo-wide. Pre-existing dead code; delete on the next harness pass.

**From T3 (2026-06-22 review):**

5. **Stream subprocess output to file** *(Lens A #2)* — T3 dropped `stdout=DEVNULL` to avoid the OOM risk of capturing hundreds of MB in RAM. But this also means the unattended operator has zero progress signal during a 15-minute iter. Better: pipe both streams to `<run_dir>/runner_capture.log` via `stdout=open(path,'w')` and `tee` a tail to the parent's stdout. ~15 LOC.
6. **`--retry-non-pass` flag for resume** *(Lens A #5)* — Today, `is_completed` treats all terminal statuses (pass/fail/error/skipped) as "done" so resume skips them. The user's most common resume case is "daemon died on iter 3, restarted daemon, re-run" — and today they have to hand-edit the manifest. Add a flag that, on resume, drops any IterResult with `status != 'pass'` and re-attempts. Default off so passive resume after Ctrl-C still works unchanged.
7. **Browser/subprocess SIGKILL atexit cleanup** *(Lens A #6)* — `subprocess.TimeoutExpired` SIGKILLs the child; spawned headless-chromes don't get cleanup hooks. Over a long session with 2-3 timeouts, orphan chromes accumulate GBs of RAM and can block subsequent Playwright launches via the user-data-dir lock. Either SIGTERM-then-SIGKILL escalation via `subprocess.Popen` or a defensive `pkill -f 'chromium.*<expected-user-data-dir>'` after timeout.
8. **`IterResult.from_json` forward-incompatibility** *(Lens A #7)* — `cls(**data)` raises `TypeError` if a future schema adds fields and the user resumes with an older binary. Filter with `{k:v for k,v in data.items() if k in {f.name for f in fields(cls)}}` + WARN on dropped keys.
9. **Per-iter unique subdir for run_<ts>** *(Lens A #8)* — mtime-sort-of-set-diff is robust for single-runner usage, but two concurrent run_session instances against the same `--out-root` could pick up each other's dirs. Pass `--out-root` with `session_id_op_iter` per iter and skip the snapshot diff entirely.
10. **Defense-in-depth `set_active` from the runner** *(Lens A #9)* — Today `set_active(True)` is only called inside the child `playwright_smoke.main`. A future refactor that removes it would silently cause run_session iters to produce skipped-pipeline runs.
11. **Op-4 UI-click variant** *(Lens C #1 deferred half)* — Current Op-4 fires `api.run_all(pid)`, which the orchestrator 409s mid-rebuild. The React-side cluster symptoms (toast, loading state, panel re-render) that §2u documents fire from the rejected request, but a more faithful repro would click the Update button via Playwright instead. Adds dependency on the Graph Scope card's Update testid.
12. **Multi-fire guard doc in `watch_until_idle`** *(Lens C #7)* — `refresh_fired` / `update_fired` are function-local. A future caller that wraps `watch_until_idle` in a retry loop would re-fire side effects. Either move state to `RunContext` or document the per-call contract.
13. **Op-4 scorecard cell classification of rc-nonzero reasons** *(Lens C #8)* — `parse_iter_result` only builds `failures` from invariant_failure events. An rc-nonzero with no invariant_failure produces a `(smoke rc=1)` note that doesn't distinguish "scheduled_update_rejected" from "watch_timeout" from "api.status() exception". Add an event-walker pass that classifies the first non-invariant error event by `where=` field.
14. **ModeSummary schema contract test** *(Lens D #5)* — `parse_iter_result` reads only a few keys from `summary.json`. Today no test pins which fields it depends on against `ModeSummary.to_json`. A TypedDict + round-trip test would catch a rename like `pass_` → `passed` that would silently mark every iter as fail.
15. **Resume-from-real-manifest integration test** *(Lens D #6)* — The current round-trip test uses synthetic IterResults; it doesn't prove that a manifest written by a real session can be re-loaded. Vendor a real manifest under `tests/fixtures/` once T4 produces one.
16. **Watch-loop scheduled-action integration test** *(Lens D #1 deferred half)* — T3 extracted `_advance_scheduled_actions` and unit-tested the pure scheduler, but no test exercises the full `watch_until_idle` integration where the scheduled action actually triggers `page.reload()` / `api.run_all()`. Would require a fake-playwright-page + fake-api shim.

---

## 10. Cross-references

- Existing tool: `/Volumes/4TB-BAD/HumanAI/CoDRAG/tools/playwright_smoke.py` (the foundation L2 extends).
- The invariants: [`REFERENCE_canonical-pipeline-behavior.md`](REFERENCE_canonical-pipeline-behavior.md) §8 (I1–I12) + [`FINDING_manual-update-click-triggers-ui-cluster.md`](FINDING_manual-update-click-triggers-ui-cluster.md) §6.2 (I13).
- The findings each invariant targets: §2a, §2l Thread A, §2n, §2r, §2u (per §3 table).
- The related fix proposal that consumes this baseline: [`PROPOSAL_state-machine-re-centering-v1.md`](PROPOSAL_state-machine-re-centering-v1.md) T3.b. **When v2 of the re-centering proposal lands, drop T3.b in favor of pointing at this doc.**
- The conventions for proposals + scrutiny: README §0 Working principles + Document type conventions.
