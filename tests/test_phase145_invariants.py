"""Pytest cases for the Phase 145 §8 UI invariant assertion library.

Uses real Playwright (sync API) with mock DOM via ``page.set_content``. No
daemon, no dashboard, no network. Each invariant gets at least one positive
case and one negative case; common edge cases (idle group, state synonyms,
selector absence) are covered too.

Run:
    .venv/bin/pytest tests/test_phase145_invariants.py -v

Per ``docs/Phase145_Pipeline-UI-Reliability/PROPOSAL_playwright-uat-harness-v1.md`` §5 T1.

Note on file location: the proposal text said ``tools/phase145_uat/test_invariants.py``
but ``pyproject.toml`` has ``testpaths = ["tests"]``. Living under ``tests/``
means a default ``pytest`` invocation picks these up as a regression net.
"""
from __future__ import annotations

from typing import Iterable

import pytest
from playwright.sync_api import Browser, Page, sync_playwright

from tools.phase145_uat.invariants import (
    ALL_INVARIANTS,
    I1_one_running_row_per_group,
    I2_running_row_has_no_stale_chip,
    I3_downstream_not_complete,
    I13_current_stage_decoration_exists,
    I14_no_not_run_text_against_completed_stage,
    I15_no_percent_chip_exceeds_100,
    run_all,
)


# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def browser() -> Iterable[Browser]:
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True)
        try:
            yield b
        finally:
            b.close()


@pytest.fixture
def page(browser: Browser) -> Iterable[Page]:
    p = browser.new_page()
    try:
        yield p
    finally:
        p.close()


# ── Mock DOM builders ─────────────────────────────────────────────


def _row(
    stage_id: str,
    state: str,
    *,
    current: bool = False,
    current_hidden: bool = False,
    last_run_chip: bool = False,
    secondary_text: str = "",
) -> str:
    """Render one mock stage row matching the dashboard's selector contract.

    ``current_hidden=True`` renders the indicator inside a display:none span —
    used to exercise the offsetParent visibility check in _scrape_rows.

    ``secondary_text`` lands inside the row as plain text — used by I14/I15
    tests to exercise the row's text/percent_values scrape path.
    """
    if current_hidden:
        deco = '<span style="display:none"><span data-testid="current-stage-indicator">●</span></span>'
    elif current:
        deco = '<span data-testid="current-stage-indicator">●</span>'
    else:
        deco = ""
    chip = (
        '<span data-testid="last-run-chip">yesterday 1384 chunks</span>'
        if last_run_chip
        else ""
    )
    body = f"<span>{secondary_text}</span>" if secondary_text else ""
    return (
        f'<div data-testid="pipeline-stage-row-{stage_id}" '
        f'data-stage-id="{stage_id}" data-stage-state="{state}">'
        f"{deco}{chip}{body}"
        f"</div>"
    )


def _html(*rows: str) -> str:
    return "<!doctype html><html><body>" + "".join(rows) + "</body></html>"


def _idle_api() -> dict:
    return {
        "fast_sync": {"phase": "idle"},
        "deep_enrichment": {"phase": "idle"},
        "finalize": {"phase": "idle"},
    }


# ── I1: at most one running row per active group ─────────────────


def test_I1_passes_with_one_running_row_per_group(page: Page) -> None:
    page.set_content(
        _html(
            _row("structural", "complete"),
            _row("inferred_edges", "running", current=True),
            _row("catalogue", "pending"),
            _row("validation", "pending"),
            _row("knowledge", "pending"),
        )
    )
    api = {"fast_sync": {"phase": "running", "current_stage": "inferred_edges"}}
    r = I1_one_running_row_per_group(page, api)
    assert r.passed, r.evidence
    assert r.evidence == {}


def test_I1_passes_when_group_idle_regardless_of_dom(page: Page) -> None:
    # A group that isn't running has no constraint on its row count.
    page.set_content(
        _html(
            _row("structural", "running"),
            _row("inferred_edges", "running"),
        )
    )
    api = _idle_api()
    assert I1_one_running_row_per_group(page, api).passed


def test_I1_fails_with_two_running_rows_in_active_group(page: Page) -> None:
    page.set_content(
        _html(
            _row("structural", "running"),
            _row("inferred_edges", "running"),
            _row("catalogue", "pending"),
        )
    )
    api = {"fast_sync": {"phase": "running", "current_stage": "structural"}}
    r = I1_one_running_row_per_group(page, api)
    assert not r.passed
    (fail,) = r.evidence["failures"]
    assert fail["group"] == "fast_sync"
    assert fail["running_count"] == 2
    assert set(fail["running_stages"]) == {"structural", "inferred_edges"}


def test_I1_treats_rerunning_and_rebuilding_as_running(page: Page) -> None:
    # All three terms canonicalize to "running" in playwright_smoke.py.
    page.set_content(
        _html(
            _row("structural", "running"),
            _row("inferred_edges", "rerunning"),
            _row("catalogue", "rebuilding"),
        )
    )
    api = {"fast_sync": {"phase": "running", "current_stage": "structural"}}
    r = I1_one_running_row_per_group(page, api)
    assert not r.passed
    assert r.evidence["failures"][0]["running_count"] == 3


def test_I1_checks_each_group_independently(page: Page) -> None:
    # fast_sync clean, deep_enrichment has two running — only deep flagged.
    page.set_content(
        _html(
            _row("structural", "complete"),
            _row("knowledge", "complete"),
            _row("enrichment", "running"),
            _row("group_reasoning", "running"),
        )
    )
    api = {
        "fast_sync": {"phase": "completed"},
        "deep_enrichment": {"phase": "running", "current_stage": "enrichment"},
    }
    r = I1_one_running_row_per_group(page, api)
    assert not r.passed
    (fail,) = r.evidence["failures"]
    assert fail["group"] == "deep_enrichment"


def test_I1_fires_on_pausing_phase(page: Page) -> None:
    # The pausing phase still has a worker mid-stage — multi-running is still
    # a bug. Adversarial review (2026-06-22) lens A flagged this gap.
    page.set_content(
        _html(
            _row("structural", "running"),
            _row("inferred_edges", "running"),
        )
    )
    api = {"fast_sync": {"phase": "pausing", "current_stage": "structural"}}
    r = I1_one_running_row_per_group(page, api)
    assert not r.passed
    assert r.evidence["failures"][0]["phase"] == "pausing"


def test_I1_fires_on_paused_phase(page: Page) -> None:
    page.set_content(
        _html(
            _row("clustering", "running"),
            _row("deepening", "running"),
        )
    )
    api = {"deep_enrichment": {"phase": "paused", "current_stage": "clustering"}}
    r = I1_one_running_row_per_group(page, api)
    assert not r.passed
    assert r.evidence["failures"][0]["phase"] == "paused"


def test_I1_zero_running_in_active_group_passes_by_design(page: Page) -> None:
    # Documents the deliberate "at most one" weakening so a refactor to
    # "exactly one" doesn't silently slip past CI.
    page.set_content(_html(_row("structural", "pending")))
    api = {"fast_sync": {"phase": "running", "current_stage": "structural"}}
    assert I1_one_running_row_per_group(page, api).passed


def test_I1_handles_missing_current_stage_in_active_group(page: Page) -> None:
    # If the API drops current_stage during an active phase, I1 should still
    # count rows correctly without crashing or false-passing.
    page.set_content(
        _html(
            _row("structural", "running"),
            _row("inferred_edges", "running"),
        )
    )
    api = {"fast_sync": {"phase": "running"}}
    r = I1_one_running_row_per_group(page, api)
    assert not r.passed
    assert r.evidence["failures"][0]["running_count"] == 2


def test_I1_empty_dom_during_active_phase_passes(page: Page) -> None:
    # Panel not yet hydrated. _scrape_rows returns []; I1 counts 0 running
    # and passes. Documents the "row not rendered ≠ failure" semantic.
    page.set_content("<!doctype html><html><body></body></html>")
    api = {"fast_sync": {"phase": "running", "current_stage": "structural"}}
    assert I1_one_running_row_per_group(page, api).passed


# ── I2: running row has no stale last-run chip ───────────────────


def test_I2_passes_when_no_running_row_has_chip(page: Page) -> None:
    page.set_content(
        _html(
            _row("structural", "running", current=True),
            _row("inferred_edges", "complete", last_run_chip=True),
        )
    )
    assert I2_running_row_has_no_stale_chip(page, _idle_api()).passed


def test_I2_fails_when_running_row_has_chip(page: Page) -> None:
    # §2r symptom: row spinning while showing yesterday's count.
    page.set_content(_html(_row("knowledge", "running", last_run_chip=True)))
    r = I2_running_row_has_no_stale_chip(page, _idle_api())
    assert not r.passed
    (fail,) = r.evidence["failures"]
    assert fail["stage_id"] == "knowledge"
    assert fail["state"] == "running"


def test_I2_treats_rerunning_as_running_for_chip_check(page: Page) -> None:
    page.set_content(_html(_row("clustering", "rerunning", last_run_chip=True)))
    r = I2_running_row_has_no_stale_chip(page, _idle_api())
    assert not r.passed
    assert r.evidence["failures"][0]["stage_id"] == "clustering"


def test_I2_passes_when_dom_lacks_chip_selector_entirely(page: Page) -> None:
    # Live dashboard before the packages/ui PR lands: no chip selector exists.
    # Invariant should pass by default — no chip wrapper = nothing to compare.
    page.set_content(_html(_row("structural", "running")))
    assert I2_running_row_has_no_stale_chip(page, _idle_api()).passed


def test_I2_treats_rebuilding_as_running_for_chip_check(page: Page) -> None:
    # Adversarial review (2026-06-22) flagged that rebuilding was the one
    # RUNNING_DOM_STATES synonym never tested for I2.
    page.set_content(_html(_row("atlas", "rebuilding", last_run_chip=True)))
    r = I2_running_row_has_no_stale_chip(page, _idle_api())
    assert not r.passed
    assert r.evidence["failures"][0]["stage_id"] == "atlas"


# ── I3: no downstream row is complete ────────────────────────────


def test_I3_passes_when_downstream_pending(page: Page) -> None:
    page.set_content(
        _html(
            _row("structural", "complete"),
            _row("inferred_edges", "running", current=True),
            _row("catalogue", "pending"),
            _row("validation", "pending"),
            _row("knowledge", "pending"),
        )
    )
    api = {"fast_sync": {"phase": "running", "current_stage": "inferred_edges"}}
    assert I3_downstream_not_complete(page, api).passed


def test_I3_fails_when_downstream_complete(page: Page) -> None:
    page.set_content(
        _html(
            _row("structural", "complete"),
            _row("inferred_edges", "running", current=True),
            _row("catalogue", "pending"),
            _row("validation", "complete"),  # downstream — illegal
            _row("knowledge", "pending"),
        )
    )
    api = {"fast_sync": {"phase": "running", "current_stage": "inferred_edges"}}
    r = I3_downstream_not_complete(page, api)
    assert not r.passed
    (fail,) = r.evidence["failures"]
    assert fail["downstream_stage"] == "validation"
    assert fail["current_stage"] == "inferred_edges"
    assert fail["downstream_state"] == "complete"


def test_I3_accepts_stage_alias_field(page: Page) -> None:
    # api_stage_verdict in playwright_smoke.py accepts either "current_stage"
    # or "stage" — invariants honor the same loose contract.
    page.set_content(
        _html(
            _row("enrichment", "running"),
            _row("group_reasoning", "pending"),
            _row("clustering", "complete"),  # downstream of enrichment — illegal
        )
    )
    api = {"deep_enrichment": {"phase": "running", "stage": "enrichment"}}
    r = I3_downstream_not_complete(page, api)
    assert not r.passed
    assert r.evidence["failures"][0]["downstream_stage"] == "clustering"


def test_I3_treats_stale_and_warning_as_complete(page: Page) -> None:
    # Both canonicalize to "complete" — they leak prior-run state too.
    page.set_content(
        _html(
            _row("structural", "running", current=True),
            _row("inferred_edges", "stale"),
            _row("catalogue", "warning"),
        )
    )
    api = {"fast_sync": {"phase": "running", "current_stage": "structural"}}
    r = I3_downstream_not_complete(page, api)
    assert not r.passed
    states = {f["downstream_stage"]: f["downstream_state"] for f in r.evidence["failures"]}
    assert states == {"inferred_edges": "stale", "catalogue": "warning"}


def test_I3_passes_when_group_idle(page: Page) -> None:
    # An idle group's complete rows are legitimate prior-run state.
    page.set_content(
        _html(
            _row("structural", "complete"),
            _row("inferred_edges", "complete"),
            _row("catalogue", "complete"),
        )
    )
    assert I3_downstream_not_complete(page, _idle_api()).passed


def test_I3_passes_when_current_stage_is_last_in_group(page: Page) -> None:
    page.set_content(
        _html(
            _row("structural", "complete"),
            _row("inferred_edges", "complete"),
            _row("catalogue", "complete"),
            _row("validation", "complete"),
            _row("knowledge", "running", current=True),
        )
    )
    api = {"fast_sync": {"phase": "running", "current_stage": "knowledge"}}
    assert I3_downstream_not_complete(page, api).passed


def test_I3_fires_with_current_stage_first_in_group(page: Page) -> None:
    # Pins the cur_pos == 0 boundary: a downstream-complete must still fail.
    page.set_content(
        _html(
            _row("structural", "running", current=True),
            _row("inferred_edges", "pending"),
            _row("catalogue", "complete"),  # downstream of position 0 — illegal
        )
    )
    api = {"fast_sync": {"phase": "running", "current_stage": "structural"}}
    r = I3_downstream_not_complete(page, api)
    assert not r.passed
    (fail,) = r.evidence["failures"]
    assert fail["current_stage_index"] == 0
    assert fail["downstream_stage"] == "catalogue"


def test_I3_passes_when_phase_active_but_current_stage_missing(page: Page) -> None:
    # Documented gap: no anchor for "downstream", so we silently pass.
    # See I3 docstring + PROPOSAL §9 known-gaps note.
    page.set_content(
        _html(
            _row("structural", "complete"),
            _row("inferred_edges", "complete"),
        )
    )
    api = {"fast_sync": {"phase": "running"}}  # no current_stage / stage
    assert I3_downstream_not_complete(page, api).passed


def test_I3_localizes_failure_to_correct_group(page: Page) -> None:
    # fast_sync running cleanly at inferred_edges; deep_enrichment running at
    # enrichment with a downstream-complete leak on clustering. Failure must
    # name deep_enrichment only — no cross-group bleed.
    page.set_content(
        _html(
            _row("structural", "complete"),
            _row("inferred_edges", "running", current=True),
            _row("catalogue", "pending"),
            _row("enrichment", "running"),
            _row("group_reasoning", "pending"),
            _row("clustering", "complete"),  # downstream of enrichment — illegal
        )
    )
    api = {
        "fast_sync": {"phase": "running", "current_stage": "inferred_edges"},
        "deep_enrichment": {"phase": "running", "current_stage": "enrichment"},
    }
    r = I3_downstream_not_complete(page, api)
    assert not r.passed
    (fail,) = r.evidence["failures"]
    assert fail["group"] == "deep_enrichment"
    assert fail["downstream_stage"] == "clustering"


def test_I3_robust_to_dom_row_order(page: Page) -> None:
    # Position is computed from STAGE_ORDER, not DOM order.
    page.set_content(
        _html(
            _row("knowledge", "pending"),
            _row("validation", "complete"),  # downstream — illegal
            _row("catalogue", "pending"),
            _row("inferred_edges", "running", current=True),
            _row("structural", "complete"),
        )
    )
    api = {"fast_sync": {"phase": "running", "current_stage": "inferred_edges"}}
    r = I3_downstream_not_complete(page, api)
    assert not r.passed
    assert r.evidence["failures"][0]["downstream_stage"] == "validation"


def test_I3_fires_on_paused_phase(page: Page) -> None:
    # Adversarial review (2026-06-22) lens A: I3 must include non-running
    # active phases. Paused: worker stopped mid-stage, downstream must still
    # be pending. A complete downstream means leaked prior-run state.
    page.set_content(
        _html(
            _row("enrichment", "paused", current=True),
            _row("group_reasoning", "pending"),
            _row("clustering", "complete"),  # downstream — illegal even when paused
        )
    )
    api = {"deep_enrichment": {"phase": "paused", "current_stage": "enrichment"}}
    r = I3_downstream_not_complete(page, api)
    assert not r.passed
    assert r.evidence["failures"][0]["phase"] == "paused"


# ── I13: exactly one current-stage indicator per non-idle group ──


def test_I13_passes_when_exactly_one_indicator_per_active_group(page: Page) -> None:
    page.set_content(
        _html(
            _row("structural", "complete"),
            _row("inferred_edges", "running", current=True),
            _row("catalogue", "pending"),
        )
    )
    api = {"fast_sync": {"phase": "running", "current_stage": "inferred_edges"}}
    assert I13_current_stage_decoration_exists(page, api).passed


def test_I13_fails_when_no_indicator_in_active_group(page: Page) -> None:
    # §2u §6.2 recurrence: browser refresh wipes the current-stage decoration.
    page.set_content(
        _html(
            _row("structural", "complete"),
            _row("inferred_edges", "running"),  # no current=True
            _row("catalogue", "pending"),
        )
    )
    api = {"fast_sync": {"phase": "running", "current_stage": "inferred_edges"}}
    r = I13_current_stage_decoration_exists(page, api)
    assert not r.passed
    (fail,) = r.evidence["failures"]
    assert fail["group"] == "fast_sync"
    assert fail["marked_count"] == 0
    assert fail["phase"] == "running"


def test_I13_fails_when_two_indicators_in_one_group(page: Page) -> None:
    page.set_content(
        _html(
            _row("structural", "running", current=True),
            _row("inferred_edges", "running", current=True),
        )
    )
    api = {"fast_sync": {"phase": "running"}}
    r = I13_current_stage_decoration_exists(page, api)
    assert not r.passed
    fail = r.evidence["failures"][0]
    assert fail["marked_count"] == 2
    assert set(fail["marked_stages"]) == {"structural", "inferred_edges"}


def test_I13_passes_when_group_idle(page: Page) -> None:
    page.set_content(
        _html(
            _row("structural", "complete"),
            _row("inferred_edges", "complete"),
        )
    )
    assert I13_current_stage_decoration_exists(page, _idle_api()).passed


def test_I13_fires_for_non_running_non_idle_phases(page: Page) -> None:
    # Paused / recovering / queued groups still need a current-stage marker.
    page.set_content(
        _html(
            _row("structural", "paused"),
            _row("inferred_edges", "pending"),
        )
    )
    api = {"fast_sync": {"phase": "paused", "current_stage": "structural"}}
    r = I13_current_stage_decoration_exists(page, api)
    assert not r.passed
    assert r.evidence["failures"][0]["phase"] == "paused"


def test_I13_terminal_phases_are_na(page: Page) -> None:
    # completed/cancelled/failed groups have no active stage — no indicator
    # is expected. Only deep_enrichment (running) is subject to the invariant.
    page.set_content(
        _html(
            _row("structural", "complete"),
            _row("knowledge", "complete"),
            _row("enrichment", "running", current=True),
            _row("group_reasoning", "pending"),
        )
    )
    api = {
        "fast_sync": {"phase": "completed"},
        "deep_enrichment": {"phase": "running", "current_stage": "enrichment"},
        "finalize": {"phase": "idle"},
    }
    assert I13_current_stage_decoration_exists(page, api).passed


def test_I13_queued_is_na(page: Page) -> None:
    # Queued = work scheduled but no active stage yet → invariant is N/A.
    page.set_content(_html(_row("structural", "queued")))
    api = {"fast_sync": {"phase": "queued"}}
    assert I13_current_stage_decoration_exists(page, api).passed


def test_I13_failed_phase_is_na(page: Page) -> None:
    # Terminal failure — no current stage to mark.
    page.set_content(
        _html(
            _row("structural", "complete"),
            _row("inferred_edges", "error"),
        )
    )
    api = {"fast_sync": {"phase": "failed", "current_stage": "inferred_edges"}}
    assert I13_current_stage_decoration_exists(page, api).passed


def test_I13_cancelled_phase_is_na(page: Page) -> None:
    # Terminal cancellation — no current stage to mark.
    page.set_content(
        _html(
            _row("structural", "complete"),
            _row("inferred_edges", "pending"),
        )
    )
    api = {"fast_sync": {"phase": "cancelled"}}
    assert I13_current_stage_decoration_exists(page, api).passed


def test_I13_fires_for_recovering_phase(page: Page) -> None:
    # Adversarial review (2026-06-22): recovering was in the phase set but
    # had no test. Daemon restart mid-stage — current_stage points to the
    # stage being recovered; indicator must mark it.
    page.set_content(
        _html(
            _row("group_reasoning", "running"),  # no current indicator
            _row("clustering", "pending"),
        )
    )
    api = {"deep_enrichment": {"phase": "recovering", "current_stage": "group_reasoning"}}
    r = I13_current_stage_decoration_exists(page, api)
    assert not r.passed
    assert r.evidence["failures"][0]["phase"] == "recovering"


def test_I13_fires_for_pausing_phase(page: Page) -> None:
    page.set_content(_html(_row("structural", "pausing")))  # no current indicator
    api = {"fast_sync": {"phase": "pausing", "current_stage": "structural"}}
    r = I13_current_stage_decoration_exists(page, api)
    assert not r.passed
    assert r.evidence["failures"][0]["phase"] == "pausing"


def test_I13_fires_for_cancelling_phase(page: Page) -> None:
    page.set_content(_html(_row("atlas", "running")))  # no current indicator
    api = {"finalize": {"phase": "cancelling", "current_stage": "atlas"}}
    r = I13_current_stage_decoration_exists(page, api)
    assert not r.passed
    assert r.evidence["failures"][0]["phase"] == "cancelling"


def test_I13_hidden_indicator_does_not_count(page: Page) -> None:
    # Adversarial review (2026-06-22) lens B: a packages/ui implementation
    # that keeps the indicator node mounted but display:none-hides it must
    # NOT pass I13 — the user-visible affordance is gone, which is the
    # §6.2 bug class.
    page.set_content(
        _html(
            _row("structural", "complete"),
            _row("inferred_edges", "running", current_hidden=True),
            _row("catalogue", "pending"),
        )
    )
    api = {"fast_sync": {"phase": "running", "current_stage": "inferred_edges"}}
    r = I13_current_stage_decoration_exists(page, api)
    assert not r.passed
    assert r.evidence["failures"][0]["marked_count"] == 0


# ── run_all + registry ───────────────────────────────────────────


def test_run_all_returns_one_result_per_invariant(page: Page) -> None:
    page.set_content(_html(_row("structural", "running", current=True)))
    api = {"fast_sync": {"phase": "running", "current_stage": "structural"}}
    results = run_all(page, api)
    assert len(results) == len(ALL_INVARIANTS)
    assert {r.invariant_id for r in results} == {"I1", "I2", "I3", "I13", "I14", "I15"}


def test_run_all_against_clean_idle_state_all_pass(page: Page) -> None:
    page.set_content(
        _html(
            _row("structural", "complete"),
            _row("inferred_edges", "complete"),
            _row("catalogue", "complete"),
        )
    )
    results = run_all(page, _idle_api())
    failures = {r.invariant_id: r.evidence for r in results if not r.passed}
    assert not failures, failures


def test_run_all_returns_partial_failures(page: Page) -> None:
    # Multiple simultaneous failures (I1: two running, I3: stale-complete
    # downstream, I13: no indicator) must all be reported, not short-circuited.
    page.set_content(
        _html(
            _row("structural", "running"),
            _row("inferred_edges", "running"),       # I1 fires
            _row("catalogue", "pending"),
            _row("validation", "complete"),          # I3 fires (downstream)
            _row("knowledge", "pending"),
        )
    )
    api = {"fast_sync": {"phase": "running", "current_stage": "structural"}}
    results = {r.invariant_id: r for r in run_all(page, api)}
    assert set(results) == {"I1", "I2", "I3", "I13", "I14", "I15"}
    assert not results["I1"].passed
    assert results["I2"].passed  # no chip → I2 N/A
    assert not results["I3"].passed
    assert not results["I13"].passed  # neither row has indicator
    # I14/I15 N/A on this DOM (no "Not run" text, no >100% chips).
    assert results["I14"].passed
    assert results["I15"].passed


def test_to_json_round_trip(page: Page) -> None:
    page.set_content(_html(_row("structural", "running", current=True)))
    api = {"fast_sync": {"phase": "running", "current_stage": "structural"}}
    r = I1_one_running_row_per_group(page, api)
    payload = r.to_json()
    assert payload["invariant_id"] == "I1"
    assert payload["passed"] is True
    assert "label" in payload
    assert "evidence" in payload


# ── I13: collapsed-group (no rendered rows) skip — adversarial review fix ──


def test_I13_passes_when_active_group_has_no_rendered_rows(page: Page) -> None:
    # B-MED-1 from the 2026-06-22 adversarial review: fast/deep/finalize
    # default to collapsed in the dashboard — CondensedGroupRow renders
    # instead of per-stage rows, so _scrape_rows returns no rows for that
    # group. Without this gate, every active collapsed group would fire
    # I13 with marked_count=0 → spammy noise on the default dashboard.
    # Now we treat "group has no rendered rows" as N/A.
    page.set_content(
        _html(
            # Only deep_enrichment has rows rendered; fast_sync is "collapsed".
            _row("enrichment", "running", current=True),
            _row("group_reasoning", "pending"),
        )
    )
    api = {
        # fast_sync is active but no rows for it → must not fire
        "fast_sync": {"phase": "running", "current_stage": "structural"},
        "deep_enrichment": {"phase": "running", "current_stage": "enrichment"},
        "finalize": {"phase": "idle"},
    }
    r = I13_current_stage_decoration_exists(page, api)
    assert r.passed, (
        "I13 must skip groups with no rendered rows (collapsed group); "
        f"evidence={r.evidence}"
    )


def test_I13_passes_when_all_active_groups_collapsed(page: Page) -> None:
    # Edge: ALL active groups are collapsed (extreme case — panel just
    # loaded with everything condensed). The invariant must pass
    # cleanly, not fire one failure per active group.
    page.set_content(_html())  # zero rows in DOM
    api = {
        "fast_sync": {"phase": "running", "current_stage": "structural"},
        "deep_enrichment": {"phase": "paused", "current_stage": "enrichment"},
        "finalize": {"phase": "recovering", "current_stage": "atlas"},
    }
    r = I13_current_stage_decoration_exists(page, api)
    assert r.passed
    assert r.evidence == {}


def test_I13_still_fires_when_group_has_rows_but_zero_indicators(page: Page) -> None:
    # Regression net for the collapsed-group fix: the new skip MUST NOT
    # accidentally suppress the real bug class. If rows ARE rendered but
    # none of them carries current-stage-indicator, the §2u §6.2 symptom
    # is present → I13 must still fire.
    page.set_content(
        _html(
            _row("structural", "complete"),  # post-refresh: states intact
            _row("inferred_edges", "complete"),  # but no row marked current
        )
    )
    api = {"fast_sync": {"phase": "running", "current_stage": "catalogue"}}
    r = I13_current_stage_decoration_exists(page, api)
    assert not r.passed
    assert r.evidence["failures"][0]["marked_count"] == 0


# ── Persistence-gate helper (lives in playwright_smoke.py) ────────


def test_persistence_gate_waits_for_two_consecutive_ticks() -> None:
    # The harness must NOT emit on the first observation of a failure —
    # absorbs pause→resume / recovering SSE-commit races. Emits on the
    # second consecutive tick with the same evidence signature.
    from tools.playwright_smoke import _should_emit_invariant_failure
    pending: dict = {}
    emitted: dict = {}
    ev = {"failures": [{"group": "deep_enrichment", "marked_count": 0}]}
    # tick 1: warm-up, no emit
    assert not _should_emit_invariant_failure(
        "I13", ev, pending=pending, last_emitted=emitted
    )
    # tick 2: persistence reached → emit
    assert _should_emit_invariant_failure(
        "I13", ev, pending=pending, last_emitted=emitted
    )
    # tick 3: identical evidence → suppressed by dedup
    assert not _should_emit_invariant_failure(
        "I13", ev, pending=pending, last_emitted=emitted
    )


def test_persistence_gate_resets_on_pass() -> None:
    # An intermittent flicker (fail → pass → fail) must NOT accumulate
    # toward the persistence threshold across the pass. Otherwise a
    # genuinely-transient bug would still emit on the second appearance
    # even though it cleared in between.
    from tools.playwright_smoke import (
        _clear_pending_invariant,
        _should_emit_invariant_failure,
    )
    pending: dict = {}
    emitted: dict = {}
    ev = {"failures": [{"group": "fast_sync", "running_count": 2}]}
    # tick 1: warm-up
    assert not _should_emit_invariant_failure(
        "I1", ev, pending=pending, last_emitted=emitted
    )
    # tick 2: passed → clear pending
    _clear_pending_invariant("I1", pending)
    assert "I1" not in pending
    # tick 3: same evidence — must NOT emit (count is back to 1)
    assert not _should_emit_invariant_failure(
        "I1", ev, pending=pending, last_emitted=emitted
    )
    # tick 4: persistence finally reached
    assert _should_emit_invariant_failure(
        "I1", ev, pending=pending, last_emitted=emitted
    )


def test_persistence_gate_evidence_change_restarts_counter() -> None:
    # If the failure mode changes signature between ticks (e.g. a
    # different set of running stages joined the I1 violation), the
    # counter must reset — the new signature gets its own warm-up
    # window, and the old emitted-signature is independent.
    from tools.playwright_smoke import _should_emit_invariant_failure
    pending: dict = {}
    emitted: dict = {}
    ev_a = {"failures": [{"group": "fast_sync", "running_stages": ["a", "b"]}]}
    ev_b = {"failures": [{"group": "fast_sync", "running_stages": ["a", "b", "c"]}]}
    # ev_a tick 1 — warm-up
    assert not _should_emit_invariant_failure(
        "I1", ev_a, pending=pending, last_emitted=emitted
    )
    # ev_b tick 1 (different sig) — counter reset, warm-up again
    assert not _should_emit_invariant_failure(
        "I1", ev_b, pending=pending, last_emitted=emitted
    )
    # ev_b tick 2 — emit
    assert _should_emit_invariant_failure(
        "I1", ev_b, pending=pending, last_emitted=emitted
    )
    # ev_a is no longer pending; if it reappears, it needs its own warm-up
    assert not _should_emit_invariant_failure(
        "I1", ev_a, pending=pending, last_emitted=emitted
    )
    assert _should_emit_invariant_failure(
        "I1", ev_a, pending=pending, last_emitted=emitted
    )


def test_persistence_gate_evidence_sort_stability() -> None:
    # Evidence dicts with the same content but different key-insertion
    # order MUST produce the same signature. Without sort_keys=True the
    # gate would treat them as distinct evidence and start fresh
    # warm-ups every tick — defeating the dedup.
    from tools.playwright_smoke import _should_emit_invariant_failure
    pending: dict = {}
    emitted: dict = {}
    ev_alpha = {"failures": [{"a": 1, "b": 2, "c": 3}]}
    ev_beta = {"failures": [{"c": 3, "b": 2, "a": 1}]}  # same content, diff order
    # Both ticks count toward the same persistence window.
    assert not _should_emit_invariant_failure(
        "I3", ev_alpha, pending=pending, last_emitted=emitted
    )
    assert _should_emit_invariant_failure(
        "I3", ev_beta, pending=pending, last_emitted=emitted
    )


# ── I14: no "Not run" text against completed stage_results (§9.3 #30) ──


def _api_with_stage_results(group: str, results: dict[str, str]) -> dict:
    """Build an API status dict where one group reports completed
    stage_results — used by I14 tests to assert the failure is detected.
    """
    return {
        "fast_sync": None,
        "deep_enrichment": (
            {"phase": "completed", "current_stage": None, "stage_results": results}
            if group == "deep_enrichment"
            else None
        ),
        "finalize": (
            {"phase": "completed", "current_stage": None, "stage_results": results}
            if group == "finalize"
            else None
        ),
    }


def test_I14_fires_on_not_run_text_against_completed_stage(page: Page) -> None:
    """The §9.3 #30 row class — Deep Knowledge Embedding renders the
    literal text "Not run" while deep_enrichment.stage_results.
    deep_knowledge == "completed". This is the headline failure pattern
    I14 was added to catch.
    """
    page.set_content(
        _html(
            _row("enrichment", "complete", secondary_text="2,102 / 2,102 files"),
            _row("group_reasoning", "complete", secondary_text="156 groups analyzed"),
            _row("clustering", "complete", secondary_text="918 modules · 918 files"),
            _row("deepening", "complete", secondary_text="100% settled · avg 87%"),
            _row("deep_knowledge", "idle", secondary_text="Not run"),  # bug
        )
    )
    api = _api_with_stage_results("deep_enrichment", {
        "enrichment": "completed",
        "group_reasoning": "completed",
        "clustering": "completed",
        "deepening": "completed",
        "deep_knowledge": "completed",
    })
    r = I14_no_not_run_text_against_completed_stage(page, api)
    assert not r.passed
    assert len(r.evidence["failures"]) == 1
    f = r.evidence["failures"][0]
    assert f["stage_id"] == "deep_knowledge"
    assert f["api_stage_result"] == "completed"
    assert f["matched_marker"] == "Not run"


def test_I14_passes_when_stage_results_empty(page: Page) -> None:
    """If the API hasn't reported stage_results yet (e.g. group never
    completed in this run), I14 must short-circuit clean — there's no
    authoritative claim of completion to contradict, so "Not run" text
    is legitimate.
    """
    page.set_content(_html(_row("deep_knowledge", "idle", secondary_text="Not run")))
    api = _idle_api()
    r = I14_no_not_run_text_against_completed_stage(page, api)
    assert r.passed
    assert r.evidence == {}


def test_I14_passes_when_status_not_completed(page: Page) -> None:
    """If the API status for the stage is anything other than
    "completed" (e.g. "failed", "skipped"), the "Not run" text isn't
    contradicted — fail only on the completed vs. Not-run mismatch.
    """
    page.set_content(_html(_row("deep_knowledge", "failed", secondary_text="Not run")))
    api = _api_with_stage_results("deep_enrichment", {"deep_knowledge": "failed"})
    r = I14_no_not_run_text_against_completed_stage(page, api)
    assert r.passed


def test_I14_passes_when_row_text_does_not_contain_marker(page: Page) -> None:
    """A completed stage that renders WITHOUT the "Not run" fallback
    text (e.g. shows "Done · 1024 chunks") passes. I14 only fires on
    the specific text-vs-status mismatch.
    """
    page.set_content(_html(
        _row("deep_knowledge", "complete", secondary_text="Done · 1024 chunks")
    ))
    api = _api_with_stage_results("deep_enrichment", {"deep_knowledge": "completed"})
    r = I14_no_not_run_text_against_completed_stage(page, api)
    assert r.passed


def test_I14_passes_when_stage_id_has_no_api_entry(page: Page) -> None:
    """A stage row whose stage_id is absent from API stage_results
    (e.g. a different group) is not in scope for I14 — only contradicts
    when the API authoritatively claims the same stage is completed.
    """
    page.set_content(_html(_row("atlas", "idle", secondary_text="Not run")))
    api = _api_with_stage_results("deep_enrichment", {
        "deep_knowledge": "completed",  # different stage
    })
    r = I14_no_not_run_text_against_completed_stage(page, api)
    assert r.passed


def test_I14_matches_substring_not_word_boundary(page: Page) -> None:
    """Marker match is substring-based. "Not run yet" still contains
    "Not run" and must fire. The opposite — "Cannot run" — must NOT
    fire (different leading word, no marker). Pin both.
    """
    page.set_content(_html(
        _row("deep_knowledge", "idle", secondary_text="Not run yet"),
    ))
    api = _api_with_stage_results("deep_enrichment", {"deep_knowledge": "completed"})
    r = I14_no_not_run_text_against_completed_stage(page, api)
    assert not r.passed

    page.set_content(_html(
        _row("deep_knowledge", "idle", secondary_text="Cannot run yet"),
    ))
    r2 = I14_no_not_run_text_against_completed_stage(page, api)
    assert r2.passed


# ── I15: percent chip ≤ 100% (§9.3 #31) ──────────────────────────


def test_I15_fires_on_5501_percent_coverage(page: Page) -> None:
    """The §9.3 #31 case verbatim — Fast Catalogue chip shows 5501%
    coverage (augmented_nodes=7812 / total_nodes=142 × 100 = 5501.4).
    """
    page.set_content(_html(
        _row("catalogue", "complete", secondary_text="5501% coverage · 98% conf"),
    ))
    api = _idle_api()  # I15 doesn't depend on API state — pure DOM check
    r = I15_no_percent_chip_exceeds_100(page, api)
    assert not r.passed
    failures = r.evidence["failures"]
    # 5501 fires once; 98 stays under the ceiling.
    assert len(failures) == 1
    assert failures[0]["stage_id"] == "catalogue"
    assert failures[0]["percent_value"] == 5501.0


def test_I15_passes_on_legitimate_progress_percentages(page: Page) -> None:
    """100% (exact ceiling), 87%, 0% — all legitimate. I15 must not
    fire false positives on the panel's normal progress + settle chips.
    """
    page.set_content(_html(
        _row("enrichment", "complete", secondary_text="100%"),
        _row("deepening", "complete", secondary_text="100% settled · avg 87%"),
        _row("catalogue", "complete", secondary_text="55% coverage · 98% conf"),
        _row("atlas", "pending", secondary_text="0%"),
    ))
    api = _idle_api()
    r = I15_no_percent_chip_exceeds_100(page, api)
    assert r.passed


def test_I15_fires_once_per_out_of_range_value(page: Page) -> None:
    """A single row with TWO out-of-range chips (e.g. 200% and 150%)
    must record both as separate failures so the reviewer sees the
    full scope of the bug, not just the first hit.
    """
    page.set_content(_html(
        _row("catalogue", "complete", secondary_text="200% coverage · 150% conf"),
    ))
    api = _idle_api()
    r = I15_no_percent_chip_exceeds_100(page, api)
    assert not r.passed
    failures = r.evidence["failures"]
    assert len(failures) == 2
    vals = sorted(f["percent_value"] for f in failures)
    assert vals == [150.0, 200.0]


def test_I15_passes_when_row_has_no_percent_chips(page: Page) -> None:
    """A row with no `%` token at all (e.g. only "1024 chunks
    embedded") must contribute zero failures — no chip to assert
    against.
    """
    page.set_content(_html(
        _row("knowledge", "complete", secondary_text="1024 chunks embedded"),
    ))
    api = _idle_api()
    r = I15_no_percent_chip_exceeds_100(page, api)
    assert r.passed


def test_I15_treats_100_exact_as_pass(page: Page) -> None:
    """Boundary: exactly 100% is fine (a stage at full progress). The
    ceiling is a > comparison, not >=, so legitimate 100% chips don't
    fire.
    """
    page.set_content(_html(_row("enrichment", "complete", secondary_text="100%")))
    api = _idle_api()
    r = I15_no_percent_chip_exceeds_100(page, api)
    assert r.passed


def test_I15_treats_100_01_as_failure(page: Page) -> None:
    """Boundary other side: a fractional overshoot like 100.01%
    indicates a chip-format bug and must fire. Catches near-100
    progress overshoot (§2j class) when it's reported as a percentage.
    """
    page.set_content(_html(_row("enrichment", "complete", secondary_text="100.01%")))
    api = _idle_api()
    r = I15_no_percent_chip_exceeds_100(page, api)
    assert not r.passed
    assert r.evidence["failures"][0]["percent_value"] == 100.01


# ── Registry includes the new invariants ─────────────────────────


def test_all_invariants_registry_includes_i14_and_i15() -> None:
    """ALL_INVARIANTS is what watch_until_idle iterates per poll. If a
    new invariant is added without updating the tuple, it never runs
    against live data. Pin the registry.
    """
    names = {fn.__name__ for fn in ALL_INVARIANTS}
    assert "I14_no_not_run_text_against_completed_stage" in names
    assert "I15_no_percent_chip_exceeds_100" in names
    assert len(ALL_INVARIANTS) == 6  # I1, I2, I3, I13, I14, I15
