# PROPOSAL v1 — Playwright UAT harness extension: iterate a test repo through every operation, assert Phase 145 §8 invariants, record results

> **STATUS: DRAFT v1 — T1 SHIPPED 2026-06-22, T2–T5 awaiting execution.** Authored so that Opus (or Fable later) can pick up and execute after a computer restart without re-deriving context. This is a **methodology + extension** proposal — the underlying Playwright tooling already exists (`tools/playwright_smoke.py`). What's new is the invariant assertion layer, the operation matrix, the iteration loop, and the scorecard format.
>
> **T1 status (2026-06-22):** invariant assertion library landed at `tools/phase145_uat/invariants.py` + pytest at `tests/test_phase145_invariants.py` (43 cases, all passing). Adversarial multi-lens review run pre-merge; Tier 1 + 2 findings fixed in the same drop, Tier 3 gaps documented in §9 below. See §5 T1 for the actual file paths + deviations from the draft text.

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

### T2 — Wire invariants into `playwright_smoke.py`  *[1 hour]*

**Files:**
- Modify: `tools/playwright_smoke.py`

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

### T3 — Iteration runner + scorecard generator  *[1-2 hours]*

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

### 9.2 T2 prerequisites (uncovered by T1)

Three concrete blockers before T2 can wire invariants into `tools/playwright_smoke.py`:

1. **packages/ui PR** adding `[data-testid="last-run-chip"]` (on rows that render a prior-run timestamp) and `[data-testid="current-stage-indicator"]` (on the row that is the group's active stage). Without this, I2 passes by-vacuity and I13 fails for every active group on the live dashboard.
2. **Constants extraction** — `invariants.py` currently imports `STAGE_ORDER` / `STAGE_TO_GROUP` / `DOM_STATE_TO_CANON` from `tools.playwright_smoke`. When T2 adds `from tools.phase145_uat.invariants import run_all` to `playwright_smoke.py`, that becomes a circular import. Fix: extract the constants into `tools/phase145_uat/constants.py` and have both modules import from there. ~30 LOC, mechanical.
3. **Shared scrape helper** — `_scrape_rows` (invariants) and `scrape_pipeline_dom` (playwright_smoke) overlap. Per-tick T2 would fire 4 redundant `page.evaluate` calls. Either extend `scrape_pipeline_dom` to also return `has_last_run_chip` / `has_current_stage_indicator`, or change the invariant signature from `(page, api)` to `(rows, api)` and have T2 pre-scrape once. Tests can keep page-driven scraping via a thin adapter.

---

## 10. Cross-references

- Existing tool: `/Volumes/4TB-BAD/HumanAI/CoDRAG/tools/playwright_smoke.py` (the foundation L2 extends).
- The invariants: [`REFERENCE_canonical-pipeline-behavior.md`](REFERENCE_canonical-pipeline-behavior.md) §8 (I1–I12) + [`FINDING_manual-update-click-triggers-ui-cluster.md`](FINDING_manual-update-click-triggers-ui-cluster.md) §6.2 (I13).
- The findings each invariant targets: §2a, §2l Thread A, §2n, §2r, §2u (per §3 table).
- The related fix proposal that consumes this baseline: [`PROPOSAL_state-machine-re-centering-v1.md`](PROPOSAL_state-machine-re-centering-v1.md) T3.b. **When v2 of the re-centering proposal lands, drop T3.b in favor of pointing at this doc.**
- The conventions for proposals + scrutiny: README §0 Working principles + Document type conventions.
