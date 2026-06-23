"""Phase 145 §8 UI invariants — callable assertions for the Playwright UAT harness.

Each invariant takes (page, api_status) and returns an InvariantResult. Called
from ``tools/playwright_smoke.py``'s ``watch_until_idle`` loop (T2, 2026-06-22)
AND from standalone pytest tests using mock DOM via ``page.set_content()``.

Per ``docs/Phase145_Pipeline-UI-Reliability/PROPOSAL_playwright-uat-harness-v1.md`` §3.

Selector contract — VERIFIED PRESENT in the dashboard, all four
attributes/testids land in
``packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx``:

    [data-testid="pipeline-stage-row-{stage_id}"]    (the row container)
        data-stage-id="{stage_id}"          e.g. "structural"
        data-stage-state="{state}"          one of: running, rerunning, rebuilding,
                                            queued, waiting, idle, not_built, disabled,
                                            paused, complete, stale, warning, error
        ↳ [data-testid="current-stage-indicator"]    (T2 add; attribute is conditionally
                                                      present on the spinner container —
                                                      mounted iff `isRunning || isPaused`,
                                                      i.e. this row is the group's
                                                      currently-active stage)
        ↳ [data-testid="last-run-chip"]              (T2 add; on the Phase 49 provenance
                                                      <p>, only rendered when the row's
                                                      state is in {complete, stale,
                                                      warning} AND showDetails AND
                                                      stage.provenance is set)

The source of truth for ``STAGE_ORDER`` / ``STAGE_TO_GROUP`` / ``DOM_STATE_TO_CANON``
is now ``tools/phase145_uat/constants.py`` (extracted T2 pre-work, 2026-06-22).
``tools/playwright_smoke.py`` re-imports from there. The extraction breaks the
circular dependency that would otherwise be created by ``playwright_smoke``
importing ``run_all`` from this module.

State vocabulary the invariants treat as "running": running, rerunning,
rebuilding (mirrors ``DOM_STATE_TO_CANON``).

Group phases the invariants treat as "active" (a current_stage exists):
    running, pausing, paused, recovering, cancelling.
See ``ACTIVE_PIPELINE_PHASES`` below for the canonical set + rationale.

Findings each invariant targets (per PROPOSAL §3 table + 2026-06-22 review):
    I1  → §2r (intra-group)
    I2  → defensive (NOT bug-derived — see I2 docstring)
    I3  → §2r (intra-group stale-state-leak only; see I3 docstring + §9.1)
    I13 → §2u §6.2 (refresh wipes the current-stage decoration)
    I14 → §9.3 #30 (literal "Not run" text against completed stage_results)
    I15 → §9.3 #31 (percent chip exceeds 100% — Fast Catalogue 5501% class)

Known gaps NOT covered by I1/I2/I3/I13 — track in PROPOSAL §9.1:
    - I3 CROSS-GROUP stale leak: if deep_enrichment is running while
      finalize rows show stale=complete from a prior run, I3 silently
      passes (finalize phase isn't ACTIVE so I3 short-circuits). The
      proposal §3 oversold I3's §2r coverage — needs a separate
      cross-group variant or a per-row "this-run-vs-prior-run"
      provenance attribute that doesn't exist today.
    - Progress overshoot (§2j, §2u §6.2: "1069 / 1058 files · 100%")
    - Spinner on pending-state row (§2u §6.2: "Deep Knowledge Embedding ...
      Not run with a spinner glyph")
    - Stage-completion-vs-manifest disagreement (§2n antibodies-never-complete)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from playwright.sync_api import Page

from tools.phase145_uat.constants import (
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

    Each record: {
        stage_id, state, has_last_run_chip, has_current_stage_indicator,
        text, percent_values
    }.
    Rows absent from the DOM are absent from the list (NOT returned as a stub)
    so callers can distinguish "row not rendered" from "row rendered with empty state."

    Visibility check: `has_last_run_chip` and `has_current_stage_indicator` use
    offsetParent !== null to reject display:none nodes. A node hidden via
    visibility:hidden or opacity:0 still counts as present — if those become
    a known false-pass pattern, tighten with getComputedStyle.

    `text` is the row's flattened innerText with whitespace collapsed — used by
    I14 to detect literal "Not run" against an API-completed stage.

    `percent_values` is every `N%` or `N.N%` token parsed from `text` as a
    float — used by I15 to fire on chips that exceed 100% (Fast Catalogue's
    5501% / §9.3 #31 class). Empty list when the row has no `%` characters.
    """
    raw = page.evaluate(
        """
        () => {
            const visible = el => !!el && el.offsetParent !== null;
            const rows = document.querySelectorAll('[data-testid^="pipeline-stage-row-"]');
            const PERCENT_RE = /(\\d+(?:\\.\\d+)?)\\s*%/g;
            const out = [];
            rows.forEach(row => {
                const id = row.getAttribute('data-stage-id');
                if (!id) return;
                const raw_text = (row.innerText || row.textContent || '');
                const text = raw_text.replace(/\\s+/g, ' ').trim();
                const percent_values = [];
                let m;
                PERCENT_RE.lastIndex = 0;
                while ((m = PERCENT_RE.exec(text)) !== null) {
                    const val = parseFloat(m[1]);
                    if (!isNaN(val)) percent_values.push(val);
                }
                out.push({
                    stage_id: id,
                    state: row.getAttribute('data-stage-state') || '',
                    has_last_run_chip:
                        visible(row.querySelector('[data-testid="last-run-chip"]')),
                    has_current_stage_indicator:
                        visible(row.querySelector('[data-testid="current-stage-indicator"]')),
                    text: text,
                    percent_values: percent_values,
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
    NOT detected here; flag as a known gap in PROPOSAL §9.1.

    Edge case: during phase=recovering the API's current_stage may be stale
    (it reflects the pre-crash stage). Including recovering catches real
    leaks at the cost of a possible false positive if recovery has already
    moved past the reported current_stage. The harness's persistence gate
    suppresses single-tick races; only failures that persist across the
    persistence window are emitted.

    KNOWN GAP — CROSS-GROUP STALE LEAK NOT COVERED. I3 only inspects rows
    in groups whose phase is in ACTIVE_PIPELINE_PHASES. If deep_enrichment
    is running while finalize-group rows still show stale=complete from a
    prior run, I3 silently passes (finalize's phase is idle/queued/
    completed, so the loop short-circuits). The §2r evidence-set contains
    BOTH intra-group leaks (caught) and cross-group leaks (NOT caught).
    Closing this gap needs a per-row provenance attribute distinguishing
    "this-run" vs "prior-run" state — out of scope for T2. See
    PROPOSAL §9.1.
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
    """For any group whose API phase is in ACTIVE_PIPELINE_PHASES AND whose
    rows are rendered in the DOM, exactly one stage row in that group has
    a VISIBLE [data-testid="current-stage-indicator"] descendant.

    The §2u §6.2 recurrence: after a browser refresh during an active build,
    the dashboard re-renders with the cumulative stage states intact but
    drops the "this is the current stage" decoration entirely. Users can no
    longer tell from the panel which stage is running.

    Terminal phases (completed, cancelled, failed) have no active stage so
    no indicator is expected — the invariant is N/A for those groups.
    Same for queued (work hasn't started) and idle (no work).

    Collapsed groups are N/A. The dashboard renders ``CondensedGroupRow``
    instead of per-stage rows when a group is collapsed (fast/deep/finalize
    each default to collapsed). In that case ``_scrape_rows`` returns no
    rows for the group and there is no indicator to find — we skip rather
    than fire a guaranteed-zero false positive. The harness is responsible
    for expanding the groups before running invariants if it wants live
    coverage of an active build.

    Visibility: ``_scrape_rows`` uses ``offsetParent !== null`` so a node
    that's technically in the DOM but hidden via display:none does NOT
    count. ``visibility:hidden`` / ``opacity:0`` still count; tighten if
    those become a known false-pass pattern (PROPOSAL §9.1).

    Persistence is enforced by the harness, not this function — the smoke
    driver requires the same failure to be observed across N consecutive
    polls before emitting an event, which absorbs pause→resume and
    recovering→running tick races.
    """
    label = "exactly one current-stage indicator per group with an active stage"
    failures = []
    by_group = _rows_by_group(_scrape_rows(page))
    for group, slot in _group_phases(api).items():
        phase = slot.get("phase")
        if phase not in ACTIVE_PIPELINE_PHASES:
            continue
        group_rows = by_group[group]
        if not group_rows:
            # Group is collapsed or panel hasn't hydrated this group yet.
            # No rows means no indicator to find — skip rather than emit a
            # guaranteed-zero failure that would noise out the report.
            continue
        marked = [r for r in group_rows if r["has_current_stage_indicator"]]
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


# ── I14 ───────────────────────────────────────────────────────────


# Literal text the dashboard renders for a stage that has never run. If the
# API authoritatively says the stage completed (stage_results entry exists
# AND == "completed"), this text is a stale UI render — exactly the §9.3 #30
# Deep Knowledge Embedding case from FINDING_dashboard-stale-deep-enrichment-
# after-completion.md. Conservative: case-sensitive match, only fires on the
# exact rendered fallback text. Subset matches (e.g. "Not running") are
# intentionally NOT matched here — they'd be a different bug class.
_NOT_RUN_TEXT_MARKERS: tuple[str, ...] = ("Not run",)


def _flat_stage_results(api: dict[str, Any]) -> dict[str, str]:
    """Flatten {group: {stage_results: {stage_id: status}}} → {stage_id: status}.

    Stage names are unique across the 15-stage pipeline so the flattening is
    safe. Groups missing the `stage_results` key contribute nothing. Non-string
    status values are skipped (defensive — API contract is string).
    """
    out: dict[str, str] = {}
    for g in GROUPS:
        slot = api.get(g) or {}
        results = slot.get("stage_results") or {}
        if not isinstance(results, dict):
            continue
        for sid, status in results.items():
            if isinstance(status, str):
                out[sid] = status
    return out


def I14_no_not_run_text_against_completed_stage(
    page: Page, api: dict[str, Any]
) -> InvariantResult:
    """No stage row may render the literal text "Not run" while the API's
    `stage_results` entry for that stage is "completed".

    Targets the §9.3 #30 class — Deep Knowledge Embedding showed "Not run"
    in the dashboard while `deep_enrichment.stage_results.deep_knowledge =
    "completed"`. The fallback text path in the stage card was being
    rendered without first consulting the group's `stage_results` map.

    Stateless predicate over (row text, stage_results map). Fires on any
    row where both conditions hold; quiet on rows where:
      - the API has no stage_results entry (stage never ran)
      - the API status is anything other than "completed"
      - the row's text doesn't contain the "Not run" marker

    If stage_results is empty (e.g. group never reached completion), the
    invariant short-circuits without false positives — there's no
    authoritative claim of completion to contradict.
    """
    label = "no row says 'Not run' against an API-completed stage_results entry"
    stage_results = _flat_stage_results(api)
    if not stage_results:
        return InvariantResult("I14", label, True, {})
    failures = []
    for row in _scrape_rows(page):
        sid = row["stage_id"]
        status = stage_results.get(sid)
        if status != "completed":
            continue
        text = row.get("text", "") or ""
        hit = next((m for m in _NOT_RUN_TEXT_MARKERS if m in text), None)
        if hit:
            failures.append({
                "stage_id": sid,
                "api_stage_result": status,
                "row_state": row["state"],
                "matched_marker": hit,
                "row_text_excerpt": text[:200],
            })
    return InvariantResult(
        "I14", label, not failures, {"failures": failures} if failures else {}
    )


# ── I15 ───────────────────────────────────────────────────────────


# Sanity ceiling for any percentage chip rendered inside a stage row. Catches
# Fast Catalogue's 7812 augmented / 142 total × 100 = 5501% display bug
# documented in §9.3 #31. The threshold is hard 100 — any chip > 100 indicates
# the numerator/denominator are inverted or the chip formatter mis-multiplied.
# Trades off a very narrow false-positive surface (a stage that legitimately
# displays >100% as part of a non-coverage chip) for catching every coverage /
# settle / completion percentage in the panel.
_PERCENT_CHIP_CEILING: float = 100.0


def I15_no_percent_chip_exceeds_100(
    page: Page, api: dict[str, Any]
) -> InvariantResult:
    """No `N%` token inside any pipeline-stage-row's visible text may
    exceed 100%.

    The §9.3 #31 case: Fast Catalogue's coverage chip showed `5501%`
    (`augmented_nodes=7812 / total_nodes=142 * 100 = 5501.4`). The chip
    formatter inverts the ratio or scopes `total_nodes` to a filtered
    subset while `augmented_nodes` carries the cumulative count.

    Stateless predicate over scraped row.percent_values. Fires once per
    out-of-range value (multiple per row possible — e.g. coverage + conf).

    Defensive design: a row with no `%` tokens contributes nothing. If a
    future stage legitimately renders >100% (e.g. a multiplier display),
    that stage should switch to a non-% glyph rather than relax this
    ceiling — percentages should always be in [0, 100].
    """
    label = "no percent chip in any pipeline-stage-row exceeds 100%"
    failures = []
    for row in _scrape_rows(page):
        for val in row.get("percent_values", []) or []:
            if val > _PERCENT_CHIP_CEILING:
                failures.append({
                    "stage_id": row["stage_id"],
                    "percent_value": val,
                    "ceiling": _PERCENT_CHIP_CEILING,
                    "row_text_excerpt": (row.get("text", "") or "")[:200],
                })
    return InvariantResult(
        "I15", label, not failures, {"failures": failures} if failures else {}
    )


# ── Registry ──────────────────────────────────────────────────────


ALL_INVARIANTS = (
    I1_one_running_row_per_group,
    I2_running_row_has_no_stale_chip,
    I3_downstream_not_complete,
    I13_current_stage_decoration_exists,
    I14_no_not_run_text_against_completed_stage,
    I15_no_percent_chip_exceeds_100,
)


def run_all(page: Page, api: dict[str, Any]) -> list[InvariantResult]:
    """Run every invariant in order; return their results. Never raises."""
    return [fn(page, api) for fn in ALL_INVARIANTS]
