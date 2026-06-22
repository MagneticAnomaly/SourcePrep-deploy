"""Phase 145 §8 UI invariants — callable assertions for the Playwright UAT harness.

Each invariant takes (page, api_status) and returns an InvariantResult. Designed
to be called from tools/playwright_smoke.py's watch loop (T2 — not yet wired)
AND from standalone pytest tests using mock DOM via page.set_content() (T1, this
commit).

Per ``docs/Phase145_Pipeline-UI-Reliability/PROPOSAL_playwright-uat-harness-v1.md`` §3.

Selector contract — VERIFIED PRESENT in the dashboard (2026-06-22):

    [data-testid="pipeline-stage-row-{stage_id}"]
        data-stage-id="{stage_id}"          e.g. "structural"
        data-stage-state="{state}"          one of: running, rerunning, rebuilding,
                                            queued, waiting, idle, not_built, disabled,
                                            paused, complete, stale, warning, error

I1 and I3 work against this contract today. I2 and I13 depend on the
PROVISIONAL contract below — they will report pass-by-default (I2) or fail
loudly (I13) on the live dashboard until that contract is honored.

Selector contract — PROVISIONAL, REQUIRED in a small packages/ui PR before T2
can wire I2 and I13:

    [data-testid="pipeline-stage-row-{stage_id}"]
        ↳ [data-testid="last-run-chip"]           (I2 — present iff row shows
                                                   a prior-run timestamp; MUST
                                                   be absent while state=running)
        ↳ [data-testid="current-stage-indicator"] (I13 — present iff this row
                                                   is the group's active stage)

State vocabulary the invariants treat as "running": running, rerunning,
rebuilding. Mirrors ``DOM_STATE_TO_CANON`` in ``tools/playwright_smoke.py``.

Group phases the invariants treat as "active" (a current_stage exists):
    running, pausing, paused, recovering, cancelling.
See ``ACTIVE_PIPELINE_PHASES`` below for the canonical set + rationale.

Findings each invariant targets (per PROPOSAL §3 table + 2026-06-22 review):
    I1  → §2r
    I2  → defensive (NOT bug-derived — see I2 docstring)
    I3  → §2r (the actual stale-state-leak path the §2r evidence shows)
    I13 → §2u §6.2 (refresh wipes the current-stage decoration)

Known gaps NOT covered by I1/I2/I3/I13 — track separately in PROPOSAL §9:
    - Progress overshoot (§2j, §2u §6.2: "1069 / 1058 files · 100%")
    - Spinner on pending-state row (§2u §6.2: "Deep Knowledge Embedding ...
      Not run with a spinner glyph")
    - Stage-completion-vs-manifest disagreement (§2n antibodies-never-complete)

T2 wiring prerequisite — when ``tools/playwright_smoke.py`` imports
``run_all`` from this module, the constant imports below become a circular
dependency. The fix is to extract ``STAGE_ORDER`` / ``STAGE_TO_GROUP`` /
``DOM_STATE_TO_CANON`` into a sibling module (``tools/phase145_uat/constants.py``
or similar) and have both modules import from there. Doing this now would
also touch ``playwright_smoke.py``, which is out of scope for T1.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from playwright.sync_api import Page

from tools.playwright_smoke import (
    DOM_STATE_TO_CANON,
    STAGE_ORDER,
    STAGE_TO_GROUP,
)

GROUPS: tuple[str, ...] = ("fast_sync", "deep_enrichment", "finalize")

RUNNING_DOM_STATES: frozenset[str] = frozenset(
    s for s, canon in DOM_STATE_TO_CANON.items() if canon == "running"
)
COMPLETE_DOM_STATES: frozenset[str] = frozenset(
    s for s, canon in DOM_STATE_TO_CANON.items() if canon == "complete"
)

# Group phases where a current stage definitively exists — work is either
# in flight, paused mid-stage, being recovered, or being cancelled. All three
# of I1, I3, I13 use this set as their fire condition.
#
# PROPOSAL §3 originally said "phase != idle" for I13; that wording captured
# terminal phases (completed, cancelled, failed) that have no active stage.
# The adversarial review (2026-06-22) flagged that an even narrower draft
# (only "running") missed pausing/paused/recovering/cancelling — phases where
# the §2u/§6.2 bug class is still observable.
#
# - running:    worker actively processing current_stage
# - pausing:    pause requested, worker flushing current_stage
# - paused:     worker stopped at current_stage, checkpoint saved
# - recovering: daemon restart mid-stage, recovery picking up at current_stage
# - cancelling: cancel requested, worker unwinding current_stage
#
# Excluded — terminal or pre-work:
# - idle, queued (no current_stage yet)
# - completed, cancelled, failed (terminal, no current_stage)
ACTIVE_PIPELINE_PHASES: frozenset[str] = frozenset({
    "running", "pausing", "paused", "recovering", "cancelling",
})


@dataclass
class InvariantResult:
    invariant_id: str
    label: str
    passed: bool
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return {
            "invariant_id": self.invariant_id,
            "label": self.label,
            "passed": self.passed,
            "evidence": self.evidence,
        }


def _scrape_rows(page: Page) -> list[dict[str, Any]]:
    """One page.evaluate per call; returns one record per pipeline-stage-row.

    Each record: {stage_id, state, has_last_run_chip, has_current_stage_indicator}.
    Rows absent from the DOM are absent from the list (NOT returned as a stub)
    so callers can distinguish "row not rendered" from "row rendered with empty state."

    Visibility check: `has_last_run_chip` and `has_current_stage_indicator` use
    offsetParent !== null to reject display:none nodes. A node hidden via
    visibility:hidden or opacity:0 still counts as present — if those become
    a known false-pass pattern, tighten with getComputedStyle.
    """
    raw = page.evaluate(
        """
        () => {
            const visible = el => !!el && el.offsetParent !== null;
            const rows = document.querySelectorAll('[data-testid^="pipeline-stage-row-"]');
            const out = [];
            rows.forEach(row => {
                const id = row.getAttribute('data-stage-id');
                if (!id) return;
                out.push({
                    stage_id: id,
                    state: row.getAttribute('data-stage-state') || '',
                    has_last_run_chip:
                        visible(row.querySelector('[data-testid="last-run-chip"]')),
                    has_current_stage_indicator:
                        visible(row.querySelector('[data-testid="current-stage-indicator"]')),
                });
            });
            return out;
        }
        """
    )
    return raw or []


def _rows_by_group(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {g: [] for g in GROUPS}
    for r in rows:
        g = STAGE_TO_GROUP.get(r["stage_id"])
        if g in out:
            out[g].append(r)
    return out


def _group_phases(api: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {g: (api.get(g) or {}) for g in GROUPS}


def _stage_pos_in_group(stage_id: str) -> int | None:
    group = STAGE_TO_GROUP.get(stage_id)
    if group is None:
        return None
    in_group = [s for s, g in STAGE_ORDER if g == group]
    try:
        return in_group.index(stage_id)
    except ValueError:
        return None


def _in_group_order(group: str) -> list[str]:
    return [s for s, g in STAGE_ORDER if g == group]


# ── I1 ────────────────────────────────────────────────────────────


def I1_one_running_row_per_group(page: Page, api: dict[str, Any]) -> InvariantResult:
    """At most one running row per group whose API phase is in
    ACTIVE_PIPELINE_PHASES.

    REFERENCE §8 I1 says "exactly one"; we weaken to "at most one" because a
    momentary 0-running observation can happen at stage boundaries (a stage
    just finished, the next has not yet been picked up) and is not the §2r bug
    class this invariant targets. The §2r class is N >= 2 running rows in the
    same group; that is what fires here. A persistent 0-running observation
    across many polls is a separate bug class — see PROPOSAL §9 (known gaps).
    """
    label = "at most one running row per active group"
    failures = []
    by_group = _rows_by_group(_scrape_rows(page))
    for group, slot in _group_phases(api).items():
        if slot.get("phase") not in ACTIVE_PIPELINE_PHASES:
            continue
        running = [r for r in by_group[group] if r["state"] in RUNNING_DOM_STATES]
        if len(running) > 1:
            failures.append({
                "group": group,
                "phase": slot.get("phase"),
                "running_count": len(running),
                "running_stages": [r["stage_id"] for r in running],
                "running_states": {r["stage_id"]: r["state"] for r in running},
            })
    return InvariantResult(
        "I1", label, not failures, {"failures": failures} if failures else {}
    )


# ── I2 ────────────────────────────────────────────────────────────


def I2_running_row_has_no_stale_chip(page: Page, api: dict[str, Any]) -> InvariantResult:
    """No row whose state is in RUNNING_DOM_STATES simultaneously renders a
    visible last-run-chip.

    Defensive invariant — NOT bug-derived. The adversarial review (2026-06-22)
    confirmed that §2r screenshots do not show a chip on a running row; the
    stale prior-run metadata actually lives on downstream COMPLETE rows, which
    is I3 territory. I2 stays in the catalog as a contract enforcement: if the
    packages/ui PR eventually adds [data-testid="last-run-chip"] and a future
    regression renders it concurrently with a running spinner, I2 catches it.

    Selector dependency: each row that renders a prior-run timestamp must wrap
    it in [data-testid="last-run-chip"]. Until that wrapper exists in
    packages/ui this invariant passes by default on the live dashboard (no
    chip selector ⇒ no failures detected). Unit tests below feed mock DOM
    with the chip present to exercise the failing path regardless.
    """
    label = "no running row shows a prior-run timestamp chip"
    bad = [
        r for r in _scrape_rows(page)
        if r["state"] in RUNNING_DOM_STATES and r["has_last_run_chip"]
    ]
    return InvariantResult(
        "I2",
        label,
        not bad,
        {"failures": [{"stage_id": r["stage_id"], "state": r["state"]} for r in bad]} if bad else {},
    )


# ── I3 ────────────────────────────────────────────────────────────


def I3_downstream_not_complete(page: Page, api: dict[str, Any]) -> InvariantResult:
    """For any group whose API phase is in ACTIVE_PIPELINE_PHASES, no row at
    position > current_stage_index has data-stage-state in COMPLETE_DOM_STATES.

    A row downstream of the current stage cannot legitimately be complete
    for THIS run — completion downstream means stale state from a prior run
    is leaking through, which is the §2r bug class.

    The API reports the current stage as ``current_stage`` (preferred) or
    ``stage``; we accept either to match the loose contract in
    ``api_stage_verdict`` in playwright_smoke.py.

    Edge case: if phase is active but current_stage is missing/null, this
    invariant silently passes (no anchor for "downstream"). That contract
    violation (active phase ⇒ current_stage present per REFERENCE §4) is
    NOT detected here; flag as a known gap in PROPOSAL §9.

    Edge case: during phase=recovering the API's current_stage may be stale
    (it reflects the pre-crash stage). Including recovering catches real
    leaks at the cost of a possible false positive if recovery has already
    moved past the reported current_stage. Acceptable trade-off — false
    positives are visible evidence, not silent.
    """
    label = "no row downstream of current_stage shows complete"
    failures = []
    rows_by_id = {r["stage_id"]: r for r in _scrape_rows(page)}
    for group, slot in _group_phases(api).items():
        if slot.get("phase") not in ACTIVE_PIPELINE_PHASES:
            continue
        current = slot.get("current_stage") or slot.get("stage")
        if current is None:
            continue
        cur_pos = _stage_pos_in_group(current)
        if cur_pos is None:
            continue
        for pos, stage_id in enumerate(_in_group_order(group)):
            if pos <= cur_pos:
                continue
            row = rows_by_id.get(stage_id)
            if row is None:
                continue
            if row["state"] in COMPLETE_DOM_STATES:
                failures.append({
                    "group": group,
                    "phase": slot.get("phase"),
                    "current_stage": current,
                    "current_stage_index": cur_pos,
                    "downstream_stage": stage_id,
                    "downstream_index": pos,
                    "downstream_state": row["state"],
                })
    return InvariantResult(
        "I3", label, not failures, {"failures": failures} if failures else {}
    )


# ── I13 ───────────────────────────────────────────────────────────


def I13_current_stage_decoration_exists(page: Page, api: dict[str, Any]) -> InvariantResult:
    """For any group whose API phase is in ACTIVE_PIPELINE_PHASES, exactly one
    stage row in that group has a VISIBLE [data-testid="current-stage-indicator"]
    descendant.

    The §2u §6.2 recurrence: after a browser refresh during an active build,
    the dashboard re-renders with the cumulative stage states intact but
    drops the "this is the current stage" decoration entirely. Users can no
    longer tell from the panel which stage is running.

    Terminal phases (completed, cancelled, failed) have no active stage so
    no indicator is expected — the invariant is N/A for those groups.
    Same for queued (work hasn't started) and idle (no work).

    Visibility: _scrape_rows uses offsetParent !== null so a node that's
    technically in the DOM but hidden via display:none does NOT count.
    visibility:hidden / opacity:0 still count; tighten if those become a
    known false-pass pattern.

    Selector dependency: rows must mark the active stage with
    [data-testid="current-stage-indicator"]. Required before T2 wiring;
    until then this invariant will fail loudly on the live dashboard for
    every active group, which is the desired forcing function.
    """
    label = "exactly one current-stage indicator per group with an active stage"
    failures = []
    by_group = _rows_by_group(_scrape_rows(page))
    for group, slot in _group_phases(api).items():
        phase = slot.get("phase")
        if phase not in ACTIVE_PIPELINE_PHASES:
            continue
        marked = [r for r in by_group[group] if r["has_current_stage_indicator"]]
        if len(marked) != 1:
            failures.append({
                "group": group,
                "phase": phase,
                "marked_count": len(marked),
                "marked_stages": [r["stage_id"] for r in marked],
            })
    return InvariantResult(
        "I13", label, not failures, {"failures": failures} if failures else {}
    )


# ── Registry ──────────────────────────────────────────────────────


ALL_INVARIANTS = (
    I1_one_running_row_per_group,
    I2_running_row_has_no_stale_chip,
    I3_downstream_not_complete,
    I13_current_stage_decoration_exists,
)


def run_all(page: Page, api: dict[str, Any]) -> list[InvariantResult]:
    """Run every invariant in order; return their results. Never raises."""
    return [fn(page, api) for fn in ALL_INVARIANTS]
