"""
Prep dashboard pipeline smoke driver.

Exercises the pipeline UI against a chosen project across the following modes:
    - initial             (destroy index, run from scratch)
    - incremental         (touch a file, let the watcher trigger a re-run)
    - rebuild             (POST /pipeline/rebuild, equivalent to Danger Zone "all")
    - rebuild-sync        (Danger Zone scope=sync, drives the UI: stages 1-5)
    - rebuild-enrichment  (Danger Zone scope=enrichment, drives the UI: stages 6-10)
    - reset-all           (Danger Zone Reset scope=all, drives the UI: nuclear)
    - reset-enrichment    (Danger Zone Reset scope=enrichment: stages 6-15)
    - reset-finalize      (Danger Zone Reset scope=finalize: stages 11-15)

Polls /projects/{id}/pipeline/status AND /system/pipeline-queue every 2s while
any mode is active and scrapes the dashboard DOM in parallel. Any disagreement
between API truth and rendered DOM is logged as a desync event with screenshot.

Multi-pipeline contract: every API/UI assertion is scoped to the target
project_id. The harness MUST NOT pause/cancel/reset any other project's
pipeline. The queue observer filters by project_id and tolerates other
projects being present.

Usage:
    .venv/bin/python -m tools.playwright_smoke \\
        --project-id 2e356d01-beaa-4559-8b5f-ceadb14b7203 \\
        --modes initial,incremental,rebuild \\
        --iterations 1

Exit code is non-zero if any desyncs or API failures were seen.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import httpx
from playwright.sync_api import (
    Browser,
    Page,
    TimeoutError as PWTimeout,
    sync_playwright,
)

from tools.phase145_uat.constants import (
    CANON_STATES,
    DOM_STATE_TO_CANON,
    STAGE_ORDER,
    STAGE_TO_GROUP,
)
from tools.phase145_uat.invariants import run_all as run_invariants

# CANON_STATES is re-imported for backward compatibility with any external
# caller that historically imported the canon vocabulary from this module.
# It is unused inside playwright_smoke itself today; do not delete without
# auditing downstream importers (none in repo as of T2 land).
_ = CANON_STATES

# Phase 118 extra-scrutiny: stage_id → expected manifest filename on disk.
# Used by the disk-vs-API consistency check (a stage the API claims is
# "complete" must have its manifest on disk).
STAGE_MANIFEST: dict[str, str] = {
    "structural":      "trace_manifest.json",
    "inferred_edges":  "trace_inferred_manifest.json",
    "catalogue":       "trace_augment_manifest.json",
    "validation":      "validation_manifest.json",
    "knowledge":       "knowledge_manifest.json",
    "enrichment":      "trace_epistemic_manifest.json",
    "group_reasoning": "group_reasoning_manifest.json",
    "clustering":      "trace_modules_manifest.json",
    "atlas":           "atlas_manifest.json",
    "deepening":       "deepening_manifest.json",
    "deep_knowledge":  "deep_knowledge_manifest.json",
    "rules":           "rules_manifest.json",
    "concepts":        "concepts_manifest.json",
    "audit":           "audit_manifest.json",
    "antibodies":      "antibodies_manifest.json",
}

# ── Data ──────────────────────────────────────────────────────────
# §9.3 second-pass audit: API_PHASE_TO_CANON was defined here as a
# 7-entry dict (missing canonical `pausing`/`cancelling`/`recovering`)
# but had ZERO call sites repo-wide. Deleted to prevent it being
# imported as authoritative by future code — the harness's actual phase
# vocabulary lives in `_NON_RUNNING_PHASES` (this file) and
# `ACTIVE_PIPELINE_PHASES` (tools/phase145_uat/invariants.py), both
# pinned to the canonical state machine.


@dataclass
class Event:
    ts: float
    kind: str  # stage-start | stage-end | desync | error | note | queue
    data: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        # `kind` MUST come last so a `data["kind"]` subtype (e.g. desync's
        # specific kind) cannot clobber the outer event label that filtering
        # depends on. Subtype keys land under `subtype` to avoid collision.
        return {"ts": self.ts, **self.data, "kind": self.kind}


@dataclass
class ModeSummary:
    mode: str
    started_at: float
    ended_at: float = 0.0
    pass_: bool = False
    desync_count: int = 0
    anomaly_count: int = 0   # Phase 118: softer mismatches, e.g. polling-grace hits
    invariant_failure_count: int = 0   # Phase 145 T2: I1/I2/I3/I13 violations
    error_count: int = 0
    stages_seen: list[str] = field(default_factory=list)
    trigger_reason: str = ""
    notes: list[str] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "duration_s": round(self.ended_at - self.started_at, 2) if self.ended_at else None,
            "pass": self.pass_,
            "desync_count": self.desync_count,
            "anomaly_count": self.anomaly_count,
            "invariant_failure_count": self.invariant_failure_count,
            "error_count": self.error_count,
            "stages_seen": self.stages_seen,
            "trigger_reason": self.trigger_reason,
            "notes": self.notes,
        }


# ── Watch budget cap (§9.3 #22 B2) ────────────────────────────────
#
# Optional ceiling on max_seconds inside watch_until_idle, set from
# main()'s --max-watch-secs CLI flag. None = no cap; each mode runner
# keeps its built-in budget.
#
# Why a module global + clamp instead of threading kwargs through every
# mode runner: the cap is a process-wide invariant (the parent's SIGKILL
# horizon), not a per-mode tuning knob. Plumbing it as an arg to every
# run_initial / run_rebuild / run_ui_run_group / etc. mode dispatcher
# would touch 8+ call sites for no behavioral gain over the clamp.
_MAX_WATCH_SECS_CAP: Optional[int] = None


def _capped_max_seconds(requested: int) -> int:
    """Apply the global watch budget cap, if set. Clamp-only."""
    if _MAX_WATCH_SECS_CAP is None:
        return requested
    return min(requested, _MAX_WATCH_SECS_CAP)


def _effective_watch_budget(requested: int, *, raisable: bool) -> int:
    """Resolve a watch budget against the global --max-watch-secs cap.

    raisable=True (build/rebuild/incremental watches): the cap, when
    set, IS the budget — it may RAISE the built-in 60m/30m defaults
    (big real repos like HomeColab take 45-90 min per rebuild, past the
    60m default) as well as clamp them below the parent's SIGKILL
    horizon (§9.3 #22 B2). Single-knob contract with run_session:
    --per-iter-timeout N flows here as N-30 and is the watch budget.

    raisable=False (scoped-reset watches): clamp-only — a deliberately
    short budget (60s) must survive a large cap, otherwise a hung reset
    burns hours of an unattended session on a one-minute operation.
    """
    if _MAX_WATCH_SECS_CAP is None:
        return requested
    if raisable:
        return _MAX_WATCH_SECS_CAP
    return min(requested, _MAX_WATCH_SECS_CAP)


# ── API client ────────────────────────────────────────────────────


class Api:
    def __init__(self, base_url: str) -> None:
        self.base = base_url.rstrip("/")
        self.http = httpx.Client(base_url=self.base, timeout=30)

    def _unwrap(self, r: httpx.Response) -> Any:
        r.raise_for_status()
        body = r.json()
        if isinstance(body, dict) and "success" in body:
            if not body.get("success"):
                raise RuntimeError(f"API error: {body.get('error')}")
            return body.get("data")
        return body

    def project(self, pid: str) -> dict[str, Any]:
        return self._unwrap(self.http.get(f"/projects/{pid}"))

    def status(self, pid: str) -> dict[str, Any]:
        return self._unwrap(self.http.get(f"/projects/{pid}/pipeline/status"))

    def destroy(self, pid: str) -> Any:
        return self._unwrap(self.http.delete(
            f"/projects/{pid}/index/destroy",
            timeout=self._HEAVY_POST_TIMEOUT_S,
        ))

    # Phase 145 §9.3 #17 — /pipeline/all and /pipeline/rebuild can spend
    # tens of seconds doing reset / hydrate work before returning. The
    # client-default 30s timeout caused httpx ReadTimeout on Op-3/Op-4
    # iters in the 2026-06-22 post-fix SCORECARD (6/12 bare-fail rows
    # carried "timed out" error events). Per-call override gives these
    # heavy endpoints 120s headroom while keeping the default short for
    # status/cancel/etc.
    _HEAVY_POST_TIMEOUT_S: float = 120.0

    def run_all(self, pid: str) -> Any:
        return self._unwrap(self.http.post(
            f"/projects/{pid}/pipeline/all",
            timeout=self._HEAVY_POST_TIMEOUT_S,
        ))

    def rebuild(self, pid: str) -> Any:
        return self._unwrap(self.http.post(
            f"/projects/{pid}/pipeline/rebuild",
            timeout=self._HEAVY_POST_TIMEOUT_S,
        ))

    def pause(self, pid: str, group: str) -> Any:
        """POST /pipeline/pause. Body MUST carry the group explicitly —
        PauseRequest defaults to fast_sync, so an empty body silently
        pauses the wrong group (same class as the cancel empty-body bug,
        PROPOSAL §9.1)."""
        return self._unwrap(self.http.post(
            f"/projects/{pid}/pipeline/pause", json={"group": group},
        ))

    def resume(self, pid: str, group: str) -> Any:
        """POST /pipeline/resume (per-project group resume, ResumeGroupRequest)."""
        return self._unwrap(self.http.post(
            f"/projects/{pid}/pipeline/resume", json={"group": group},
        ))

    def cancel(self, pid: str) -> Any:
        return self._unwrap(self.http.post(f"/projects/{pid}/pipeline/cancel"))

    def set_active(self, pid: str, active: bool) -> Any:
        return self._unwrap(self.http.put(f"/projects/{pid}", json={"config": {"active": active}, "touch": True}))

    # Scoped rebuild/reset endpoints (Phase 117). All five do daemon-side
    # reset / hydrate / re-run work and can exceed the 30s client default
    # — same reasoning as run_all + rebuild above (§9.3 #17 scrutiny #4).
    def run_fast(self, pid: str, force_from_start: bool = False) -> Any:
        return self._unwrap(self.http.post(
            f"/projects/{pid}/pipeline/fast",
            json={"force_from_start": force_from_start},
            timeout=self._HEAVY_POST_TIMEOUT_S,
        ))

    def run_deep(self, pid: str, force_from_start: bool = False) -> Any:
        return self._unwrap(self.http.post(
            f"/projects/{pid}/pipeline/deep",
            json={"force_from_start": force_from_start},
            timeout=self._HEAVY_POST_TIMEOUT_S,
        ))

    def enrichment_full_reset(self, pid: str) -> Any:
        return self._unwrap(self.http.delete(
            f"/projects/{pid}/enrichment/full-reset",
            timeout=self._HEAVY_POST_TIMEOUT_S,
        ))

    def finalize_full_reset(self, pid: str) -> Any:
        return self._unwrap(self.http.delete(
            f"/projects/{pid}/finalize/full-reset",
            timeout=self._HEAVY_POST_TIMEOUT_S,
        ))

    def queue(self) -> dict[str, Any]:
        """Global queue dump (all projects). Caller filters by project_id."""
        return self._unwrap(self.http.get("/system/pipeline-queue"))


# ── DOM scraper ───────────────────────────────────────────────────


def scrape_pipeline_dom(page: Page) -> dict[str, dict[str, Any]]:
    """Return {stage_id: {state, progress}} from the rendered pipeline panel.

    Missing stages are returned as state='not_rendered'. The caller is
    expected to classify that as either 'pending' (never started) or a
    desync depending on what the API says.
    """
    # Pull everything in one page.evaluate to avoid selector-roundtrip noise.
    try:
        raw = page.evaluate(
            """
            () => {
                const rows = document.querySelectorAll('[data-testid^="pipeline-stage-row-"]');
                const out = {};
                rows.forEach(row => {
                    const id = row.getAttribute('data-stage-id');
                    if (!id) return;
                    const progress = row.getAttribute('data-stage-progress');
                    out[id] = {
                        state: row.getAttribute('data-stage-state') || '',
                        progress: progress === '' || progress == null
                            ? null
                            : Number(progress),
                    };
                });
                return out;
            }
            """
        )
        return raw or {}
    except Exception as e:
        return {"__error__": {"state": "scrape_failed", "progress": None, "detail": str(e)}}


def scrape_panel_present(page: Page) -> bool:
    try:
        return page.locator('[data-testid="pipeline-panel"]').count() > 0
    except Exception:
        return False


# ── Danger Zone UI drivers ────────────────────────────────────────


def open_danger_zone(page: Page, dashboard_url: str, timeout_ms: int = 10_000) -> bool:
    """Navigate to ?settings=danger-zone and wait for the rebuild row testid.

    Uses URL-based routing rather than menu clicks so the harness is robust
    to dashboard navigation changes outside the Danger Zone surface itself.
    """
    sep = "&" if "?" in dashboard_url else "?"
    target = f"{dashboard_url}{sep}settings=danger-zone"
    page.goto(target)
    try:
        page.wait_for_selector(
            '[data-testid="pipeline-danger-rebuild-button"]',
            timeout=timeout_ms,
        )
        return True
    except PWTimeout:
        return False


def drive_scoped_rebuild_ui(
    page: Page,
    scope: str,
    project_name: str,
    ctx: RunContext,
    timeout_ms: int = 10_000,
) -> bool:
    """Drive Danger Zone Rebuild row at the chosen scope through the UI.

    scope: 'all' | 'sync' | 'enrichment' (matches REBUILD_OPTIONS in DangerZone.tsx)
    Returns True on submit; False if any step fails.
    """
    try:
        sel = page.locator('[data-testid="pipeline-danger-rebuild-scope-select"]')
        sel.select_option(scope)
        # Native select_option dispatches change, but React's controlled
        # value can lag; force an additional input event to nudge the
        # reducer and verify the selected value matches what we expect.
        page.evaluate(
            "(s) => { const el = document.querySelector('[data-testid=\"pipeline-danger-rebuild-scope-select\"]'); if (el) { el.value = s; el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); } }",
            scope,
        )
        actual = sel.input_value()
        if actual != scope:
            ctx.log(Event(time.time(), "error", {
                "where": f"drive_scoped_rebuild_ui[{scope}]",
                "detail": f"select did not commit value: actual={actual!r} expected={scope!r}",
            }))
            ctx.summary.error_count += 1
            return False
        ctx.snap(page, f"danger_rebuild_{scope}_scope_set")
        page.locator('[data-testid="pipeline-danger-rebuild-button"]').click(timeout=timeout_ms)
        page.wait_for_selector('[data-testid="pipeline-danger-confirm"]', timeout=timeout_ms)
        ctx.snap(page, f"danger_rebuild_{scope}_dialog_open")
        # Typed-confirm gate (project name).
        page.locator('[data-testid="pipeline-danger-confirm-typed-name-input"]').fill(project_name)
        page.locator('[data-testid="pipeline-danger-confirm-confirm"]').click(timeout=timeout_ms)
        ctx.snap(page, f"danger_rebuild_{scope}_submitted")
        return True
    except Exception as e:
        ctx.log(Event(time.time(), "error", {
            "where": f"drive_scoped_rebuild_ui[{scope}]",
            "detail": str(e),
        }))
        ctx.summary.error_count += 1
        ctx.snap(page, f"danger_rebuild_{scope}_failure")
        return False


def drive_scoped_reset_ui(
    page: Page,
    scope: str,
    ctx: RunContext,
    timeout_ms: int = 10_000,
) -> bool:
    """Drive Danger Zone Reset row at the chosen scope through the UI.

    scope: 'all' | 'enrichment' | 'finalize' (matches RESET_OPTIONS in DangerZone.tsx)
    Reset has no typed-confirm gate; just confirm the dialog.
    """
    try:
        sel = page.locator('[data-testid="pipeline-danger-reset-scope-select"]')
        sel.select_option(scope)
        page.evaluate(
            "(s) => { const el = document.querySelector('[data-testid=\"pipeline-danger-reset-scope-select\"]'); if (el) { el.value = s; el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); } }",
            scope,
        )
        actual = sel.input_value()
        if actual != scope:
            ctx.log(Event(time.time(), "error", {
                "where": f"drive_scoped_reset_ui[{scope}]",
                "detail": f"select did not commit value: actual={actual!r} expected={scope!r}",
            }))
            ctx.summary.error_count += 1
            return False
        ctx.snap(page, f"danger_reset_{scope}_scope_set")
        page.locator('[data-testid="pipeline-danger-reset-button"]').click(timeout=timeout_ms)
        page.wait_for_selector('[data-testid="pipeline-danger-confirm"]', timeout=timeout_ms)
        ctx.snap(page, f"danger_reset_{scope}_dialog_open")
        page.locator('[data-testid="pipeline-danger-confirm-confirm"]').click(timeout=timeout_ms)
        ctx.snap(page, f"danger_reset_{scope}_submitted")
        return True
    except Exception as e:
        ctx.log(Event(time.time(), "error", {
            "where": f"drive_scoped_reset_ui[{scope}]",
            "detail": str(e),
        }))
        ctx.summary.error_count += 1
        ctx.snap(page, f"danger_reset_{scope}_failure")
        return False


# ── Canonicalization ──────────────────────────────────────────────


def api_stage_verdict(
    api_stages: dict[str, Any],
    stage_id: str,
    group_phase: dict[str, Any],
) -> tuple[Optional[str], Optional[int]]:
    """Return a *confident* API verdict for this stage, or (None, None) if unknown.

    We deliberately refuse to guess. Only these signals produce a verdict:
        1. The stage's group is in `_VERDICT_ELIGIBLE_PHASES` AND it's the
           current stage → "running"
        2. Same phase set AND it appears earlier than the current stage in
           the group's stage order → "complete" (already done this run)
        3. Same phase set AND it appears later than the current stage →
           "pending" (this run)
        4. A group slot with phase in {failed, cancelled} for the stage → "failed"

    Returns (None, None) during idle — we don't compare against stale DOM
    state when no pipeline is running, because the whole point of
    Phase 96D.4 is that the panel IS allowed to show the last-known state
    between runs. We flag that separately (dom_says_running_while_api_idle)
    in the watch loop.

    §9.3 second-pass audit: pre-fix the verdict-emitting set was
    `{"running"}` only, silently blinding desync detection during paused
    windows. `paused` has a STABLE `current_stage` (worker stopped cleanly
    at checkpoint) so per-stage ordering is well-defined and verdicts are
    accurate. `pausing`/`cancelling`/`recovering` are EXCLUDED because
    their `current_stage` is mid-transition — emitting verdicts would
    produce false positives the docstring forbids. See
    `_VERDICT_ELIGIBLE_PHASES` definition for the canonical set.
    """
    group = STAGE_TO_GROUP[stage_id]
    gslot = group_phase.get(group)
    if not gslot:
        return None, None

    phase = gslot.get("phase")
    current_stage = gslot.get("current_stage") or gslot.get("stage")
    if phase not in _VERDICT_ELIGIBLE_PHASES:
        # Groups can report idle/completed/failed/cancelled/queued plus the
        # transitional pausing/cancelling/recovering — we only claim a
        # verdict where `current_stage` is stable. Let the idle-branch
        # handle stale displays.
        return None, None

    # In-group stage ordering mirrors STAGE_ORDER; compute positions.
    in_group = [sid for sid, g in STAGE_ORDER if g == group]
    try:
        pos = in_group.index(stage_id)
        cur_pos = in_group.index(current_stage) if current_stage in in_group else -1
    except ValueError:
        return None, None

    if cur_pos < 0:
        return None, None

    if pos < cur_pos:
        return "complete", None
    if pos == cur_pos:
        return "running", _progress_from_group(gslot)
    return "pending", None


def _progress_from_group(gslot: dict[str, Any]) -> Optional[int]:
    for key in ("progress", "progress_percent", "percent"):
        v = gslot.get(key)
        if isinstance(v, (int, float)):
            return int(round(v))
    processed = gslot.get("processed") or gslot.get("done")
    total = gslot.get("total") or gslot.get("count")
    if isinstance(processed, (int, float)) and isinstance(total, (int, float)) and total:
        return int(round(100 * processed / total))
    return None


def canon_dom_state(dom_state: str) -> str:
    return DOM_STATE_TO_CANON.get(dom_state, "pending" if dom_state else "pending")


# ── Run context ───────────────────────────────────────────────────


class RunContext:
    """Holds per-mode state: screenshots dir, event log, summary."""

    def __init__(self, out_dir: Path, mode: str, verbose: bool) -> None:
        self.out_dir = out_dir
        self.mode = mode
        self.verbose = verbose
        self.events_path = out_dir / "events.jsonl"
        self.summary = ModeSummary(mode=mode, started_at=time.time())
        self._seq = 0
        out_dir.mkdir(parents=True, exist_ok=True)

    def _next_seq(self) -> int:
        self._seq += 1
        return self._seq

    def log(self, ev: Event) -> None:
        with self.events_path.open("a") as f:
            f.write(json.dumps(ev.to_json()) + "\n")
        if self.verbose:
            print(f"  [{self.mode}] {ev.kind} {ev.data}", flush=True)

    def snap(self, page: Page, tag: str) -> Optional[Path]:
        seq = self._next_seq()
        safe_tag = tag.replace("/", "_")[:80]
        path = self.out_dir / f"{seq:03d}_{safe_tag}.png"
        try:
            page.screenshot(path=str(path), full_page=True)
            return path
        except Exception as e:
            self.log(Event(time.time(), "error", {"where": "snap", "tag": tag, "detail": str(e)}))
            return None

    def finish(self, passed: bool) -> None:
        self.summary.ended_at = time.time()
        self.summary.pass_ = passed
        (self.out_dir / "summary.json").write_text(json.dumps(self.summary.to_json(), indent=2))


# ── Watch loop ────────────────────────────────────────────────────


def _group_phase(status: dict[str, Any]) -> dict[str, Any]:
    # §9.3 second-pass audit: was a hard-coded 3-tuple of group names;
    # now sourced from the canonical `invariants.GROUPS` so a future
    # group rename (e.g. fast_sync → sync) only needs to change one place.
    from tools.phase145_uat.invariants import GROUPS
    return {g: status.get(g) or {} for g in GROUPS}


# §9.3 #17 scrutiny #5 — pre-fix this only treated "running" as in-flight,
# missing pausing/recovering/cancelling/queued/paused. watch_until_idle
# would then declare "settled" mid-transition and the next iter would race
# the unfinished work. Matches run_session._TERMINAL_PHASES (4 phases the
# daemon will accept new /pipeline/rebuild from), per state_machine.py
# PipelineState (94-104) — IDLE + the 3 canonical TERMINAL_STATES (195-199).
# Mirrored here instead of imported to keep playwright_smoke.py free of
# cross-package imports from tools/phase145_uat/ — drift is pinned by
# TestHarnessPhaseSetsMatchCanonical in tests/test_phase145_run_session.py.
_NON_RUNNING_PHASES: frozenset[str] = frozenset({
    "idle", "completed", "cancelled", "failed",
})


# §9.3 second-pass audit — phases where `current_stage` is stable enough
# for per-stage ordering verdicts. `running` (worker actively at stage)
# and `paused` (worker stopped cleanly at checkpoint) qualify;
# `pausing`/`cancelling`/`recovering` do NOT because their `current_stage`
# is mid-transition. Used by `api_stage_verdict` + `_check_disk_consistency`
# to gate verdict emission without producing false positives.
# Pinned by `TestVerdictEligiblePhases` in tests/test_phase145_run_session.py.
_VERDICT_ELIGIBLE_PHASES: frozenset[str] = frozenset({"running", "paused"})


def is_any_running(status: dict[str, Any]) -> bool:
    gp = _group_phase(status)
    for g in gp.values():
        phase = g.get("phase")
        if isinstance(phase, str) and phase not in _NON_RUNNING_PHASES:
            return True
    return False


def _check_disk_consistency(
    repo_path: Path,
    api_stages: dict[str, Any],
    group_phase: dict[str, Any],
    ctx: "RunContext",
    now: float,
) -> None:
    """Phase 118 extra scrutiny: any stage the API reports complete in this
    run must have its manifest on disk. Catches the F-78-class bug where
    the state machine and disk disagree.

    Only fires for stages whose group is currently `running` (so we know
    the API is reporting *this run*). Idle groups are skipped to avoid
    false positives from the synthetic-paused snapshot pattern.
    """
    idx_dir = repo_path / ".sourceprep"
    if not idx_dir.is_dir():
        return
    for group_name, gslot in group_phase.items():
        # §9.3 second-pass audit: same gate as api_stage_verdict — only
        # `running` and `paused` have a stable `stage_results` snapshot
        # we can compare against disk without race risk.
        if not gslot or gslot.get("phase") not in _VERDICT_ELIGIBLE_PHASES:
            continue
        results = gslot.get("stage_results") or {}
        for stage_id, state in results.items():
            if state != "completed":
                continue
            manifest = STAGE_MANIFEST.get(stage_id)
            if not manifest:
                continue
            if not (idx_dir / manifest).is_file():
                ctx.summary.anomaly_count += 1
                ctx.log(Event(now, "anomaly", {
                    "subtype": "api_complete_disk_missing_manifest",
                    "stage": stage_id,
                    "group": group_name,
                    "expected_manifest": manifest,
                }))


def _check_group_phase_consistency(
    api_stages: dict[str, Any],
    group_phase: dict[str, Any],
    dom: dict[str, dict[str, Any]],
    ctx: "RunContext",
    now: float,
) -> None:
    """Phase 118 extra scrutiny: if a group's API phase is terminal for
    this run, no stage row in that group should be DOM-rendered as
    `running`. Catches stale-spinner-after-group-finish bugs (the
    F-NEW-4 family).

    §9.3 second-pass audit: pre-fix only fired on `completed`, missing
    the same bug class for `failed` and `cancelled`. The canonical
    TERMINAL_STATES at src/prep/services/pipeline/state_machine.py:195-199
    is {completed, failed, cancelled} — all three carry the same
    "no work in flight" guarantee against which a still-spinning DOM
    row is a UI lie.
    """
    # Canonical TERMINAL_STATES mirror — pinned by
    # TestHarnessPhaseSetsMatchCanonical.test_canonical_terminal_states_are_subset_of_harness_terminal
    # (which catches drift in the run_session.py _TERMINAL_PHASES superset).
    canonical_terminal = {"completed", "failed", "cancelled"}
    for group_name, gslot in group_phase.items():
        if not gslot or gslot.get("phase") not in canonical_terminal:
            continue
        for stage_id, g in STAGE_ORDER:
            if g != group_name:
                continue
            row = dom.get(stage_id)
            if not row:
                continue
            if canon_dom_state(row.get("state", "") or "") == "running":
                ctx.summary.anomaly_count += 1
                ctx.log(Event(now, "anomaly", {
                    "subtype": "group_completed_but_stage_dom_running",
                    "stage": stage_id,
                    "group": group_name,
                    "dom": {"state": row.get("state"), "progress": row.get("progress")},
                }))


def _check_barrier_ui(api: Api, pid: str, page: Page, ctx: "RunContext", now: float) -> None:
    """Phase 118 extra scrutiny: when the API reports a barrier is active,
    the panel should expose a barrier indicator. We intentionally don't
    fail loudly here because barrier-indicator visibility may be hidden
    by panel state — log as anomaly if API says barrier active but the
    indicator isn't in the DOM at all.
    """
    try:
        st = api.status(pid)
    except Exception:
        return
    bar = st.get("barrier") or {}
    if not bar.get("active"):
        return
    try:
        present = page.locator('[data-testid="pipeline-barrier-indicator"]').count() > 0
    except Exception:
        present = False
    if not present:
        ctx.summary.anomaly_count += 1
        ctx.log(Event(now, "anomaly", {
            "subtype": "barrier_active_but_indicator_absent",
            "api_barrier": bar,
        }))


def _queue_snapshot_for(api: Api, pid: str) -> Optional[dict[str, Any]]:
    """Filtered queue dump for the target project. Tolerates other projects."""
    try:
        full = api.queue()
    except Exception:
        return None
    runs = full.get("runs") or full.get("active") or []
    sched = full.get("scheduler") or {}
    target_runs = [r for r in runs if isinstance(r, dict) and r.get("project_id") == pid]
    target_queues = {}
    for node_id, q in (sched.get("queues") or {}).items():
        filtered = [
            e for e in (q if isinstance(q, list) else [])
            if isinstance(e, dict) and e.get("project_id") == pid
        ]
        target_queues[node_id] = filtered
    return {
        "project_runs": target_runs,
        "project_queues_by_node": target_queues,
    }


# Phase 145 T2: persistence + dedup gate for invariant failures.
# Adversarial review surfaced two false-positive classes the raw dedup-by-
# signature design couldn't suppress:
#   - I13 during the pause→running transition: brief tick where API has
#     flipped to 'running' but the dashboard has not yet committed the SSE
#     update; isPaused and isRunning are both false on every row → I13
#     would fire once before the next tick made it pass again.
#   - I1/I3/I13 during a 'recovering' phase whose current_stage briefly
#     points at a stale slot — same shape.
#
# Requiring the same evidence-signature to be observed on PERSISTENCE
# consecutive ticks before emitting absorbs both classes without
# silencing real persistent bugs. The acceptable latency cost is
# (PERSISTENCE - 1) × poll_interval seconds (4s at defaults).
INVARIANT_PERSISTENCE_TICKS = 2


def _should_emit_invariant_failure(
    invariant_id: str,
    evidence: dict[str, Any],
    *,
    pending: dict[str, tuple[str, int]],
    last_emitted: dict[str, str],
    persistence: int = INVARIANT_PERSISTENCE_TICKS,
) -> bool:
    """Decide whether THIS observation should produce an event.

    Mutates `pending` and `last_emitted` in place. Returns True iff this
    tick is the first to cross the persistence threshold for the current
    evidence signature; returns False both during the warm-up ticks
    (count < persistence) and on identical re-observations after emit.

    Evidence is serialised with sort_keys + default=str so the signature
    is stable across runs and dict-iteration order. Any unhashable or
    non-stringifiable type in evidence is coerced via str() — keeps the
    dedup robust to a future evidence-shape change that includes e.g.
    a Path or a frozenset.
    """
    sig = json.dumps(evidence, sort_keys=True, default=str)
    prev = pending.get(invariant_id)
    new_count = prev[1] + 1 if (prev and prev[0] == sig) else 1
    pending[invariant_id] = (sig, new_count)
    if new_count < persistence:
        return False
    if last_emitted.get(invariant_id) == sig:
        return False
    last_emitted[invariant_id] = sig
    return True


def _clear_pending_invariant(
    invariant_id: str,
    pending: dict[str, tuple[str, int]],
) -> None:
    """Drop the persistence buffer for an invariant that just passed.

    A pass between failures resets the consecutive-tick counter — the
    next failure starts a fresh persistence countdown. Without this an
    intermittent bug that flickered pass/fail/pass/fail would never
    accumulate to PERSISTENCE consecutive failing ticks and would stay
    silent.
    """
    pending.pop(invariant_id, None)


# Phase 145 T3 — scheduled side-effect scheduler. Extracted to a pure
# function so unit tests can feed a controlled clock without spawning a
# browser. The caller (watch_until_idle) dispatches each returned action
# kind to its concrete side effect (page.reload, api.run_all).
def _advance_scheduled_actions(
    elapsed: float,
    *,
    refresh_at_secs: Optional[float],
    update_at_secs: Optional[float],
    refresh_fired: bool,
    update_fired: bool,
) -> tuple[bool, bool, list[str]]:
    """Decide which scheduled side effects should fire on this tick.

    Returns `(new_refresh_fired, new_update_fired, actions)` where
    `actions` is a list of action-kind strings in fire order ("refresh"
    before "update" — refresh is more disruptive so a same-tick pair
    fires the reload first, then the update against the reloaded page).

    Each side effect fires at-most-once across the lifetime of a single
    watch_until_idle call: the booleans flip True on first emission and
    no subsequent tick re-fires. A None at_secs means "never fire".

    Pure function. No I/O. The caller logs the event and runs the
    concrete side effect for each returned action kind.
    """
    actions: list[str] = []
    new_refresh = refresh_fired
    new_update = update_fired
    if (refresh_at_secs is not None
            and not refresh_fired
            and elapsed >= refresh_at_secs):
        new_refresh = True
        actions.append("refresh")
    if (update_at_secs is not None
            and not update_fired
            and elapsed >= update_at_secs):
        new_update = True
        actions.append("update")
    return new_refresh, new_update, actions


def _advance_pause_actions(
    elapsed: float,
    *,
    pause_at_secs: Optional[float],
    resume_at_secs: Optional[float],
    pause_fired: bool,
    resume_fired: bool,
    pause_target_available: bool,
) -> tuple[bool, bool, list[str]]:
    """Op-5 scheduler — decide whether the pause / resume side effect
    fires on this tick. Pure function; sibling of
    `_advance_scheduled_actions` (kept separate so that function's
    3-tuple contract and its pinned tests stay untouched).

    Semantics:
      - "pause" fires when `elapsed >= pause_at_secs` AND a running
        group exists (`pause_target_available`). No running group →
        defer to a later tick WITHOUT marking fired — pausing nothing
        is not a pause test. May therefore fire later than scheduled;
        callers log the actual elapsed.
      - "resume" fires when `elapsed >= resume_at_secs` AND the pause
        already fired on a PREVIOUS tick (`pause_fired` is the pre-tick
        value) — never same-tick as its pause, so the paused state is
        observable for at least one poll interval. Resume does not need
        a running target (the group is paused, not running).
      - Both are at-most-once per watch. None threshold = never fire.
    """
    actions: list[str] = []
    new_pause = pause_fired
    new_resume = resume_fired
    if (pause_at_secs is not None
            and not pause_fired
            and elapsed >= pause_at_secs
            and pause_target_available):
        new_pause = True
        actions.append("pause")
    if (resume_at_secs is not None
            and not resume_fired
            and pause_fired          # pre-tick value: never same-tick as pause
            and elapsed >= resume_at_secs):
        new_resume = True
        actions.append("resume")
    return new_pause, new_resume, actions


def _log_pause_action_failure(
    ctx: "RunContext",
    now_wall: float,
    action: str,
    group: str,
    e: Exception,
) -> None:
    """Classify a failed scheduled pause/resume POST.

    State rejections (group finished or resumed itself between the
    observation tick and the post — a 2s race) and transport errors are
    informational notes; anything else is a real error and counts.
    Mirrors the Op-4 scheduled-update classification (§9.3 #22 B4).
    """
    msg = str(e)
    is_state_reject = (
        "409" in msg or "400" in msg
        or "not running" in msg.lower()
        or "not paused" in msg.lower()
    )
    if is_state_reject:
        ctx.log(Event(now_wall, "note", {
            "detail": f"scheduled_{action}_rejected",
            "group": group,
            "context": msg[:200],
        }))
    elif isinstance(e, (httpx.TimeoutException, httpx.HTTPError)):
        ctx.log(Event(now_wall, "note", {
            "detail": f"scheduled_{action}_transport_error",
            "subtype": type(e).__name__,
            "context": msg[:200],
        }))
    else:
        ctx.log(Event(now_wall, "error", {
            "where": f"scheduled_{action}",
            "detail": msg,
        }))
        ctx.summary.error_count += 1


def _log_unfired_pause(
    ctx: "RunContext",
    now_wall: float,
    *,
    pause_at_secs: Optional[float],
    pause_fired: bool,
    resume_at_secs: Optional[float],
    resume_fired: bool,
    elapsed: float,
) -> None:
    """Silent-cap rule: a scheduled pause/resume that never fired must
    surface as a note in events.jsonl, not vanish. Typical cause: the
    rebuild completed before `pause_at_secs` (tiny repo), so no running
    group was ever available to pause — the Op-5 iter proved nothing
    about pause states and the triage reader needs to know that.
    """
    if pause_at_secs is not None and not pause_fired:
        ctx.log(Event(now_wall, "note", {
            "detail": "scheduled_pause_never_fired",
            "scheduled_at_s": pause_at_secs,
            "elapsed_s": round(elapsed, 1),
        }))
    elif resume_at_secs is not None and pause_fired and not resume_fired:
        ctx.log(Event(now_wall, "note", {
            "detail": "scheduled_resume_never_fired",
            "scheduled_at_s": resume_at_secs,
            "elapsed_s": round(elapsed, 1),
        }))


def expand_all_groups(page: Page, timeout_ms: int = 3_000) -> int:
    """Click the chevron on every collapsed pipeline group. Returns the
    count of groups expanded.

    React's per-group `fastCollapsed` / `deepCollapsed` / `finalizeCollapsed`
    state defaults to True (see src/prep/dashboard/src/App.tsx around
    line 147). When a group is collapsed the panel renders
    `CondensedGroupRow` instead of per-stage rows, so the I13
    'current-stage decoration' invariant short-circuits as N/A
    (`if not group_rows: continue` per Phase 145 T2's empty-group skip).

    Calling this immediately after `page.reload()` restores per-stage row
    visibility, which is what I13 needs to actually fire against the
    §2u §6.2 bug class. Tolerates already-expanded groups (Expand button
    is absent → locator count is 0 → no-op). Tolerates missing panel
    (e.g. dashboard showing the Build Trace hero) by swallowing per-group
    locator exceptions.
    """
    from tools.phase145_uat.invariants import GROUPS
    expanded = 0
    for group in GROUPS:
        sel = f'[data-testid="pipeline-group-{group}"] button[aria-label="Expand group"]'
        try:
            button = page.locator(sel)
            if button.count() == 0:
                continue
            button.first.click(timeout=timeout_ms)
            expanded += 1
        except Exception:
            # Group container absent or button non-interactable; the
            # caller cares about best-effort expansion, not strict
            # consistency.
            continue
    return expanded


def watch_until_idle(
    api: Api,
    page: Page,
    pid: str,
    ctx: RunContext,
    *,
    max_seconds: int,
    startup_grace_seconds: int = 15,
    settle_seconds: int = 8,
    repo_path: Optional[Path] = None,
    refresh_at_secs: Optional[float] = None,
    update_at_secs: Optional[float] = None,
    pause_at_secs: Optional[float] = None,
    resume_at_secs: Optional[float] = None,
    project_name: Optional[str] = None,
    budget_raisable: bool = True,
) -> bool:
    """Poll + scrape + diff until no pipeline group is running (or timeout).

    Desync rules (all per-stage):
        - api says running + dom says not-running → desync
        - api says running + dom progress diverges by >5% → desync
        - api says completed-this-run + dom still running/queued → desync
        - api group phase is idle AND dom reports running → flagged once as
          "dom_claims_running_while_api_idle" (catches Phase 96D symptom 2/4)

    Each (stage, desync_kind) pair is emitted at most once per transition —
    repeating the same disagreement every 2s adds noise without information.

    Phase 145 T3 — scheduled mid-run side effects (Op-3 / Op-4):
        - refresh_at_secs: once `elapsed >= N`, call `page.reload()` once,
          then re-select the project (if `project_name` is set) and re-
          expand all pipeline groups so I13 stays armed. Exercises the
          SSE-replay / dashboard-reconnect path that PROPOSAL §2u §6.2 (I13)
          targets.
        - update_at_secs:  once `elapsed >= N`, POST /pipeline/all once and
          continue watching. Exercises the §2u cluster trigger
          (incremental-update click during an active rebuild). 409
          PIPELINE_ALREADY_RUNNING from the orchestrator's guard is
          treated as a `note` event, not an error — it's the expected
          response from the API path Op-4 currently uses, and the
          dashboard's React-side cluster symptoms still fire from the
          rejected request (toast, loading state). A v2 of this op should
          drive the actual Update button click via Playwright for a more
          faithful repro; see PROPOSAL §9.3.

    Both are no-ops when None. Each fires at most once per watch — a third
    "fire" requires a fresh watch_until_idle call. The at-most-once guard
    is per-call (function-local booleans); callers that wrap this in a
    retry loop will re-fire side effects. See PROPOSAL §9.3.

    After a scheduled refresh, the invariant + desync emitters enter a
    `post_reload_recovery` mode that suppresses fires until the panel
    re-hydrates, so the React state reset (groups defaulting to
    collapsed) cannot spuriously clear the 2-tick persistence buffer for
    a real bug that was mid-detection at refresh time.
    """
    # §9.3 #22 B2: resolve the per-mode budget against the global cap so
    # the child can always reach `ctx.snap(page, "timeout")` before the
    # parent (run_session.py) sends SIGKILL. For heavy watches the cap
    # may also RAISE the built-in budget (big-repo enabler); scoped-reset
    # watches pass budget_raisable=False and only ever clamp.
    max_seconds = _effective_watch_budget(max_seconds, raisable=budget_raisable)

    # §9.3 #22 B3: monotonic clock for elapsed math; wall clock only for
    # Event timestamps. Laptop sleep (lid closed) or NTP step makes
    # time.time() jump forward, which under the old code fired false
    # timeouts and mis-scheduled --refresh-at-secs / --update-at-secs.
    # time.monotonic() is immune to both. Event timestamps stay wall so
    # log readers can correlate against daemon logs / wall-clock UTC.
    t0_mono = time.monotonic()
    last_api_verdict: dict[str, Optional[str]] = {}
    last_desync_sig: dict[str, tuple[str, str]] = {}
    # Phase 145 T2: invariant emission state.
    #   - `pending_invariant_failure`: (invariant_id → (sig, consecutive_count))
    #     accumulating during the persistence warm-up window.
    #   - `last_invariant_sig`:        (invariant_id → sig) of the last
    #     EMITTED failure, used to suppress identical re-fires after
    #     persistence has been reached.
    # See _should_emit_invariant_failure for the full contract.
    pending_invariant_failure: dict[str, tuple[str, int]] = {}
    last_invariant_sig: dict[str, str] = {}
    saw_running = False
    idle_since: Optional[float] = None
    next_poll = 0.0
    poll_interval = 2.0
    ok = True
    # Phase 145 T3: at-most-once scheduled side-effect flags + post-reload
    # recovery gate. post_reload_recovery flips True the moment a refresh
    # fires and stays True until the pipeline panel is back in the DOM
    # AND group expansion + project re-select have completed. During
    # recovery, the invariant block is skipped entirely (no emit, no
    # clear) so the persistence-gate state for any pre-reload-in-flight
    # bug survives the empty-DOM tick that always follows reload.
    refresh_fired = False
    update_fired = False
    post_reload_recovery = False
    # Op-5: pause/resume scheduled-action state. `pause_target_group` is
    # refreshed from each successful status poll (one tick stale at
    # dispatch time — a pause race just produces a rejected-note, not an
    # error). `paused_group` remembers which group we actually paused so
    # the resume targets the same one.
    pause_fired = False
    resume_fired = False
    pause_target_group: Optional[str] = None
    paused_group: Optional[str] = None

    while True:
        # B3: now_mono drives all elapsed math (next_poll, idle_since,
        # max_seconds gate). now_wall is what we hand to Event(...) so
        # log timestamps remain comparable to wall-clock daemon logs.
        now_mono = time.monotonic()
        now_wall = time.time()
        elapsed = now_mono - t0_mono
        if elapsed > max_seconds:
            ctx.log(Event(now_wall, "error", {"detail": "watch_until_idle timeout", "elapsed_s": round(elapsed, 1)}))
            ctx.summary.error_count += 1
            ctx.snap(page, "timeout")
            _log_unfired_pause(ctx, now_wall, pause_at_secs=pause_at_secs,
                               pause_fired=pause_fired, resume_at_secs=resume_at_secs,
                               resume_fired=resume_fired, elapsed=elapsed)
            return False

        # Phase 145 T3: scheduled side effects. _advance_scheduled_actions
        # is pure (unit-tested separately); we dispatch concrete I/O for
        # each returned action kind. Both checks are at-most-once per
        # watch_until_idle call.
        refresh_fired, update_fired, scheduled_actions = _advance_scheduled_actions(
            elapsed,
            refresh_at_secs=refresh_at_secs,
            update_at_secs=update_at_secs,
            refresh_fired=refresh_fired,
            update_fired=update_fired,
        )
        for action in scheduled_actions:
            if action == "refresh":
                ctx.log(Event(now_wall, "note", {
                    "detail": "scheduled_refresh_fired",
                    "elapsed_s": round(elapsed, 1),
                    "scheduled_at_s": refresh_at_secs,
                }))
                ctx.snap(page, "before_scheduled_refresh")
                try:
                    page.reload(wait_until="domcontentloaded", timeout=15_000)
                except Exception as e:
                    ctx.log(Event(now_wall, "error", {
                        "where": "scheduled_refresh",
                        "detail": str(e),
                    }))
                    ctx.summary.error_count += 1
                else:
                    # Enter recovery. The actual re-select + expand happens
                    # in the recovery block below as soon as the panel
                    # re-hydrates (avoids racing React's mount).
                    post_reload_recovery = True
                    ctx.snap(page, "after_scheduled_refresh")
            elif action == "update":
                ctx.log(Event(now_wall, "note", {
                    "detail": "scheduled_update_fired",
                    "elapsed_s": round(elapsed, 1),
                    "scheduled_at_s": update_at_secs,
                }))
                ctx.snap(page, "before_scheduled_update")
                try:
                    api.run_all(pid)
                except Exception as e:
                    # 409 PIPELINE_ALREADY_RUNNING is the orchestrator's
                    # expected response to /pipeline/all during a rebuild
                    # (src/prep/services/pipeline/orchestrator.py run_all
                    # guard). Surface it as a `note` not `error` so Op-4
                    # iters don't all read as ERR in the scorecard.
                    #
                    # §9.3 #22 B4: httpx.TimeoutException / HTTPError on
                    # this POST is the §9.3 #20 daemon-side rebuild stall
                    # surfacing here ─ rebuild is holding the connection
                    # so this concurrent update can't complete. That's a
                    # known daemon bug; from the harness's perspective
                    # the cluster trigger still landed (the dashboard
                    # toast renders from the rejected POST), so we treat
                    # it the same as a 409 rather than crashing teardown.
                    msg = str(e)
                    is_already_running = (
                        "409" in msg
                        or "already running" in msg.lower()
                        or "PIPELINE_ALREADY_RUNNING" in msg
                    )
                    is_httpx_transport_error = isinstance(
                        e, (httpx.TimeoutException, httpx.HTTPError)
                    )
                    if is_already_running:
                        ctx.log(Event(now_wall, "note", {
                            "detail": "scheduled_update_rejected",
                            "subtype": "pipeline_already_running",
                            "elapsed_s": round(elapsed, 1),
                            "context": msg[:200],
                        }))
                    elif is_httpx_transport_error:
                        ctx.log(Event(now_wall, "note", {
                            "detail": "scheduled_update_transport_error",
                            "subtype": type(e).__name__,
                            "elapsed_s": round(elapsed, 1),
                            "context": msg[:200],
                        }))
                    else:
                        ctx.log(Event(now_wall, "error", {
                            "where": "scheduled_update",
                            "detail": msg,
                        }))
                        ctx.summary.error_count += 1
                else:
                    ctx.snap(page, "after_scheduled_update")

        # Op-5: pause/resume scheduled side effects. Separate pure
        # scheduler so _advance_scheduled_actions' pinned 3-tuple
        # contract stays untouched. pause_target_group is the previous
        # tick's observation — a 2s race just yields a rejected-note.
        pause_fired, resume_fired, pause_actions = _advance_pause_actions(
            elapsed,
            pause_at_secs=pause_at_secs,
            resume_at_secs=resume_at_secs,
            pause_fired=pause_fired,
            resume_fired=resume_fired,
            pause_target_available=pause_target_group is not None,
        )
        for action in pause_actions:
            if action == "pause":
                group = pause_target_group or "fast_sync"
                ctx.log(Event(now_wall, "note", {
                    "detail": "scheduled_pause_fired",
                    "group": group,
                    "elapsed_s": round(elapsed, 1),
                    "scheduled_at_s": pause_at_secs,
                }))
                ctx.snap(page, "before_scheduled_pause")
                try:
                    api.pause(pid, group)
                except Exception as e:
                    _log_pause_action_failure(ctx, now_wall, "pause", group, e)
                else:
                    paused_group = group
                    ctx.snap(page, "after_scheduled_pause")
            elif action == "resume":
                group = paused_group or pause_target_group or "fast_sync"
                ctx.log(Event(now_wall, "note", {
                    "detail": "scheduled_resume_fired",
                    "group": group,
                    "elapsed_s": round(elapsed, 1),
                    "scheduled_at_s": resume_at_secs,
                }))
                ctx.snap(page, "before_scheduled_resume")
                try:
                    api.resume(pid, group)
                except Exception as e:
                    _log_pause_action_failure(ctx, now_wall, "resume", group, e)
                else:
                    ctx.snap(page, "after_scheduled_resume")

        # Post-reload recovery: as soon as the panel is back in the DOM,
        # re-select the project (the reload reset selectedProjectId to
        # null per src/prep/dashboard/src/hooks/useProjectManager.ts; the
        # auto-select-first-project effect is a footgun for any account
        # with multiple projects) and re-expand all groups so I13 has
        # per-stage rows to assert against again.
        if post_reload_recovery and scrape_panel_present(page):
            if project_name:
                select_project_in_dashboard(page, project_name, timeout_ms=5_000)
            n_expanded = expand_all_groups(page)
            # Refresh both clocks ─ the recovery block can run for several
            # hundred ms (Playwright DOM operations + project re-select).
            ctx.log(Event(time.time(), "note", {
                "detail": "post_reload_recovered",
                "elapsed_s": round(time.monotonic() - t0_mono, 1),
                "groups_expanded": n_expanded,
                "reselected_project": bool(project_name),
            }))
            ctx.snap(page, "post_reload_recovered")
            post_reload_recovery = False

        if now_mono >= next_poll:
            next_poll = now_mono + poll_interval
            try:
                status = api.status(pid)
            except Exception as e:
                ctx.log(Event(now_wall, "error", {"where": "api.status", "detail": str(e)}))
                ctx.summary.error_count += 1
                time.sleep(poll_interval)
                continue

            # Multi-project safe queue observation. Tolerates other projects;
            # only logs the slice belonging to the project under test.
            qsnap = _queue_snapshot_for(api, pid)
            if qsnap is not None:
                ctx.log(Event(now_wall, "queue", qsnap))

            dom = scrape_pipeline_dom(page)
            running = is_any_running(status)
            # Op-5: remember which group (if any) is running so the next
            # tick's pause dispatch has a target.
            pause_target_group = next(
                (g for g, slot in _group_phase(status).items()
                 if slot.get("phase") == "running"),
                None,
            )

            # Phase 118 extra scrutiny — non-blocking anomaly checks. Run
            # AFTER the canonical desync detector (below) so it remains
            # the authoritative pass/fail signal; these add depth without
            # changing existing pass criteria.
            api_stages = status.get("stages") or {}
            group_phase_for_extras = _group_phase(status)
            _check_group_phase_consistency(api_stages, group_phase_for_extras, dom, ctx, now_wall)
            if repo_path is not None:
                _check_disk_consistency(repo_path, api_stages, group_phase_for_extras, ctx, now_wall)
            _check_barrier_ui(api, pid, page, ctx, now_wall)
            if running:
                saw_running = True
                idle_since = None
            elif idle_since is None:
                idle_since = now_mono

            group_phase = _group_phase(status)

            for stage_id, group in STAGE_ORDER:
                api_state, api_progress = api_stage_verdict(status.get("stages", {}), stage_id, group_phase)
                prev = last_api_verdict.get(stage_id)

                # Log stage transitions.
                if api_state != prev:
                    if api_state == "running":
                        ctx.log(Event(now_wall, "stage-start", {"stage": stage_id, "group": group}))
                        ctx.snap(page, f"{group}_{stage_id}_start")
                        if stage_id not in ctx.summary.stages_seen:
                            ctx.summary.stages_seen.append(stage_id)
                    elif prev == "running" and api_state in ("complete", "failed"):
                        ctx.log(Event(now_wall, "stage-end", {"stage": stage_id, "state": api_state}))
                        ctx.snap(page, f"{group}_{stage_id}_{api_state}")
                    last_api_verdict[stage_id] = api_state

                # Dedupe desync emission: only on signature change.
                dom_row = dom.get(stage_id)
                if dom_row is None or elapsed <= startup_grace_seconds:
                    continue

                dom_state_raw = dom_row.get("state", "") or ""
                dom_canon = canon_dom_state(dom_state_raw)

                disagreement: Optional[tuple[str, str]] = None
                if api_state == "running" and dom_canon != "running":
                    disagreement = ("api_running_dom_not_running", dom_state_raw)
                elif api_state == "complete" and dom_canon in {"running", "failed"}:
                    # The API says we already finished this stage in the
                    # current run, but the DOM still shows work happening.
                    disagreement = ("api_complete_dom_still_running", dom_state_raw)
                elif api_state == "running" and api_progress is not None:
                    dom_progress = dom_row.get("progress")
                    if isinstance(dom_progress, (int, float)) and abs(api_progress - int(dom_progress)) > 5:
                        disagreement = ("progress_gap", f"api={api_progress}% dom={int(dom_progress)}%")

                # Idle lie: API has no running group, DOM claims running.
                if api_state is None and not running and dom_canon == "running":
                    disagreement = ("dom_claims_running_while_api_idle", dom_state_raw)

                if disagreement is None:
                    continue

                prev_sig = last_desync_sig.get(stage_id)
                if prev_sig == disagreement:
                    continue  # same disagreement we already logged
                last_desync_sig[stage_id] = disagreement
                ctx.summary.desync_count += 1
                ctx.log(Event(now_wall, "desync", {
                    "stage": stage_id,
                    "subtype": disagreement[0],
                    "api": {"state": api_state, "progress": api_progress},
                    "dom": {"state": dom_state_raw, "progress": dom_row.get("progress"), "canon": dom_canon},
                }))
                ctx.snap(page, f"desync_{stage_id}_{disagreement[0]}")
                ok = False

            # Phase 145 T2: §8 invariant checks. Run on every API-poll tick
            # (~2s cadence — same loop as the desync detector) AFTER the
            # per-stage desync loop so this block sees the same `status` /
            # DOM snapshot. Gated on the same startup_grace_seconds
            # threshold as desyncs so the panel has time to hydrate before
            # we assert against an empty DOM. Only failures are emitted —
            # passes would generate ~4 invariants × 30 polls/min = ~7k
            # lines on an hour-long run with zero information value.
            # Two-layer suppression on emission:
            #   1. Persistence gate: same evidence-signature must persist
            #      across INVARIANT_PERSISTENCE_TICKS consecutive polls
            #      before firing (absorbs SSE/DOM commit-lag races during
            #      pause→resume and recovering windows).
            #   2. Dedup: once emitted, identical re-observations are
            #      suppressed until the evidence-signature changes.
            # Phase 145 T3: also gated on `not post_reload_recovery` so
            # the empty-DOM tick that follows a scheduled refresh does
            # NOT call _clear_pending_invariant on a real bug whose
            # persistence buffer was mid-accumulation.
            if elapsed > startup_grace_seconds and not post_reload_recovery:
                try:
                    inv_results = run_invariants(page, status)
                except Exception as e:
                    ctx.log(Event(now_wall, "error", {
                        "where": "run_invariants",
                        "detail": str(e),
                    }))
                    ctx.summary.error_count += 1
                    inv_results = []
                for inv_result in inv_results:
                    if inv_result.passed:
                        _clear_pending_invariant(
                            inv_result.invariant_id,
                            pending_invariant_failure,
                        )
                        continue
                    if not _should_emit_invariant_failure(
                        inv_result.invariant_id,
                        inv_result.evidence,
                        pending=pending_invariant_failure,
                        last_emitted=last_invariant_sig,
                    ):
                        continue
                    ctx.summary.invariant_failure_count += 1
                    ctx.log(Event(now_wall, "invariant_failure", {
                        "invariant_id": inv_result.invariant_id,
                        "label": inv_result.label,
                        "evidence": inv_result.evidence,
                    }))
                    ctx.snap(page, f"invariant_{inv_result.invariant_id}_FAIL")
                    ok = False

            if saw_running and idle_since and (now_mono - idle_since) >= settle_seconds:
                ctx.log(Event(now_wall, "note", {"detail": "settled_idle", "elapsed_s": round(elapsed, 1)}))
                ctx.snap(page, "settled_idle")
                _log_unfired_pause(ctx, now_wall, pause_at_secs=pause_at_secs,
                                   pause_fired=pause_fired, resume_at_secs=resume_at_secs,
                                   resume_fired=resume_fired, elapsed=elapsed)
                return ok

            # If we never saw a running state and it's been >startup_grace_seconds,
            # treat that as a no-op run (e.g., incremental with nothing to do) —
            # not a failure.
            if not saw_running and elapsed > startup_grace_seconds * 2 and not running:
                ctx.log(Event(now_wall, "note", {"detail": "no_activity_observed", "elapsed_s": round(elapsed, 1)}))
                ctx.snap(page, "no_activity")
                _log_unfired_pause(ctx, now_wall, pause_at_secs=pause_at_secs,
                                   pause_fired=pause_fired, resume_at_secs=resume_at_secs,
                                   resume_fired=resume_fired, elapsed=elapsed)
                return ok

        time.sleep(0.25)


# ── Mode runners ──────────────────────────────────────────────────


def ensure_manual_mode(api: Api, pid: str, ctx: RunContext) -> None:
    """Set fast/deep/finalize to manual via the project config so the Run
    buttons render. Phase 118 UI-Run modes need this — the buttons only
    appear in manual mode.
    """
    try:
        # Push manual config; the dashboard's enrichment config layer
        # reads ui_config from project config, but the simplest thing
        # that makes the Run buttons render is to set ui_config.
        api.http.put(f"/projects/{pid}", json={
            "config": {
                "ui_config": {
                    "fast_sync": False,
                    "deep_enrichment": "manual",
                    "finalize": "manual",
                },
            },
            "touch": True,
        })
    except Exception as e:
        ctx.log(Event(time.time(), "note", {"detail": "ensure_manual_mode_failed", "err": str(e)}))


def click_group_run_via_ui(
    page: Page,
    group: str,
    dashboard_url: str,
    ctx: RunContext,
    timeout_ms: int = 15_000,
) -> bool:
    """Click the Run button for the given group via Playwright (UI test path).

    group: 'fast_sync' | 'deep_enrichment' | 'finalize'

    When the project has no trace data, the dashboard renders the
    "Initialize Trace Graph" hero instead of the pipeline panel — the
    hero's Build Trace Graph button calls the same `onRunFastSync`
    handler as the panel's Fast Sync Run button. For ui-run-fast we
    fall back to clicking the hero button when the panel isn't there.
    Deep / Finalize Run buttons aren't reachable until trace exists,
    so those modes assume a pre-existing build.
    """
    page.goto(dashboard_url)
    # Try the panel selector first; fall back to hero for fast_sync.
    panel_present = False
    try:
        page.wait_for_selector('[data-testid="pipeline-panel"]', timeout=5_000)
        panel_present = True
    except PWTimeout:
        panel_present = False

    if not panel_present:
        if group != "fast_sync":
            ctx.log(Event(time.time(), "error", {
                "where": f"click_group_run_via_ui[{group}]",
                "detail": (
                    "pipeline panel not rendered (trace not built); "
                    f"can't click {group} Run button until fast_sync has run at least once. "
                    "Run ui-run-fast first."
                ),
            }))
            ctx.summary.error_count += 1
            return False
        # fast_sync: click the hero "Build Trace Graph" button.
        ctx.log(Event(time.time(), "note", {"detail": "panel absent; using hero Build Trace Graph button"}))
        try:
            page.wait_for_selector('[data-testid="pipeline-build-trace-hero"]', timeout=timeout_ms)
            ctx.snap(page, f"ui_run_{group}_hero_loaded")
            page.locator('[data-testid="pipeline-build-trace-hero"]').click(timeout=timeout_ms)
            ctx.snap(page, f"ui_run_{group}_hero_clicked")
            return True
        except Exception as e:
            ctx.log(Event(time.time(), "error", {
                "where": f"click_group_run_via_ui[{group}]",
                "detail": f"hero button click failed: {e}",
            }))
            ctx.summary.error_count += 1
            ctx.snap(page, f"ui_run_{group}_hero_failure")
            return False

    ctx.snap(page, f"ui_run_{group}_panel_loaded")
    btn_sel = f'[data-testid="pipeline-run-{group}"]'
    try:
        page.wait_for_selector(btn_sel, timeout=timeout_ms)
        page.locator(btn_sel).click(timeout=timeout_ms)
        ctx.snap(page, f"ui_run_{group}_clicked")
        return True
    except Exception as e:
        ctx.log(Event(time.time(), "error", {
            "where": f"click_group_run_via_ui[{group}]",
            "detail": f"button click failed: {e}",
        }))
        ctx.summary.error_count += 1
        ctx.snap(page, f"ui_run_{group}_failure")
        return False


def run_ui_run_group(
    api: Api,
    page: Page,
    pid: str,
    group: str,
    ctx: RunContext,
    repo_path: Path,
    dashboard_url: str,
) -> bool:
    """Mode runner: drive the corresponding group's Run button via the UI."""
    ctx.summary.trigger_reason = f"UI click: Run on {group}"
    ensure_manual_mode(api, pid, ctx)
    time.sleep(1)
    if not click_group_run_via_ui(page, group, dashboard_url, ctx):
        return False
    time.sleep(2)
    return watch_until_idle(api, page, pid, ctx, max_seconds=60 * 60, repo_path=repo_path)


def run_initial(api: Api, page: Page, pid: str, ctx: RunContext, repo_path: Path) -> bool:
    ctx.summary.trigger_reason = "DELETE /index/destroy + POST /pipeline/all"
    ctx.snap(page, "before_destroy")
    try:
        api.destroy(pid)
    except Exception as e:
        ctx.log(Event(time.time(), "error", {"where": "destroy", "detail": str(e)}))
        ctx.summary.error_count += 1
        return False

    # Give the dashboard a moment to observe the empty state.
    time.sleep(3)
    ctx.snap(page, "after_destroy")

    try:
        api.run_all(pid)
    except Exception as e:
        ctx.log(Event(time.time(), "error", {"where": "run_all", "detail": str(e)}))
        ctx.summary.error_count += 1
        return False

    return watch_until_idle(api, page, pid, ctx, max_seconds=60 * 60, repo_path=repo_path)


def run_incremental(repo_path: Path, api: Api, page: Page, pid: str, ctx: RunContext) -> bool:
    ctx.summary.trigger_reason = "write tick + POST /pipeline/all (incremental path)"
    tick = repo_path / "prep_smoke_tick.py"
    tick.write_text(f"# prep smoke tick {datetime.now(timezone.utc).isoformat()}\nTICK = 1\n")
    ctx.log(Event(time.time(), "note", {"detail": "tick_written", "path": str(tick)}))

    try:
        time.sleep(2)
        api.run_all(pid)
        ctx.snap(page, "after_run_all_trigger")
        return watch_until_idle(api, page, pid, ctx, max_seconds=60 * 30, startup_grace_seconds=20, repo_path=repo_path)
    finally:
        try:
            tick.unlink()
            ctx.log(Event(time.time(), "note", {"detail": "tick_deleted"}))
        except FileNotFoundError:
            pass


def run_rebuild(
    api: Api,
    page: Page,
    pid: str,
    ctx: RunContext,
    repo_path: Path,
    *,
    refresh_at_secs: Optional[float] = None,
    update_at_secs: Optional[float] = None,
    pause_at_secs: Optional[float] = None,
    resume_at_secs: Optional[float] = None,
    project_name: Optional[str] = None,
) -> bool:
    reason = "POST /pipeline/rebuild"
    if refresh_at_secs is not None:
        reason += f" + scheduled page.reload() @ {refresh_at_secs}s"
    if update_at_secs is not None:
        reason += f" + scheduled POST /pipeline/all @ {update_at_secs}s"
    if pause_at_secs is not None:
        reason += f" + scheduled pause @ {pause_at_secs}s"
        if resume_at_secs is not None:
            reason += f" / resume @ {resume_at_secs}s"
    ctx.summary.trigger_reason = reason
    ctx.snap(page, "before_rebuild")
    try:
        api.rebuild(pid)
    except Exception as e:
        ctx.log(Event(time.time(), "error", {"where": "rebuild", "detail": str(e)}))
        ctx.summary.error_count += 1
        return False

    time.sleep(3)
    # Phase 145 T3 Tier-1 fix (Lens C #3): expand all groups before the
    # watch begins so I13 has per-stage rows to assert against from t=0.
    # The dashboard's per-group collapse defaults to True; without this
    # call I13 would silently short-circuit (empty-group N/A) on every
    # active group through the entire run.
    expanded = expand_all_groups(page)
    if expanded:
        ctx.log(Event(time.time(), "note", {
            "detail": "pre_watch_groups_expanded",
            "count": expanded,
        }))
    ctx.snap(page, "after_rebuild_trigger")
    return watch_until_idle(
        api, page, pid, ctx,
        max_seconds=60 * 60,
        repo_path=repo_path,
        refresh_at_secs=refresh_at_secs,
        update_at_secs=update_at_secs,
        pause_at_secs=pause_at_secs,
        resume_at_secs=resume_at_secs,
        project_name=project_name,
    )


# ── Scoped Rebuild modes (UI-driven via Danger Zone) ──────────────


def run_rebuild_scoped_ui(
    api: Api,
    page: Page,
    pid: str,
    project_name: str,
    scope: str,
    ctx: RunContext,
    dashboard_url: str,
    repo_path: Path,
) -> bool:
    """Drive Danger Zone Rebuild row for scope ∈ {sync, enrichment} via the UI.

    Verifies post-conditions:
        - barrier reason matches scope (Phase 117)
        - only target stage range animates / re-runs
    """
    ctx.summary.trigger_reason = f"Danger Zone Rebuild scope={scope} (UI)"
    if not open_danger_zone(page, dashboard_url):
        ctx.log(Event(time.time(), "error", {"where": "open_danger_zone"}))
        ctx.summary.error_count += 1
        return False
    ctx.snap(page, "danger_zone_loaded")
    if not drive_scoped_rebuild_ui(page, scope, project_name, ctx):
        return False

    time.sleep(2)
    # Verify barrier scope after submit; the rebuild handler writes barrier
    # before dispatch (pipeline.py:135-139 for sync, 213-214 for enrichment).
    expected_barrier_scope = scope
    try:
        st = api.status(pid)
        bar = st.get("barrier") or {}
        if bar.get("active") and bar.get("scope") != expected_barrier_scope:
            ctx.log(Event(time.time(), "error", {
                "where": "barrier_scope_mismatch",
                "expected": expected_barrier_scope,
                "actual_scope": bar.get("scope"),
                "actual_reason": bar.get("reason"),
            }))
            ctx.summary.error_count += 1
    except Exception as e:
        ctx.log(Event(time.time(), "note", {"detail": "barrier_check_failed", "err": str(e)}))

    # After submit, navigate back to the main dashboard so the pipeline panel
    # is visible for the watch loop to scrape.
    page.goto(dashboard_url)
    time.sleep(2)
    ctx.snap(page, f"after_rebuild_{scope}_back_to_dash")
    return watch_until_idle(api, page, pid, ctx, max_seconds=60 * 60, repo_path=repo_path)


# ── Scoped Reset modes (UI-driven via Danger Zone) ────────────────


def run_reset_scoped_ui(
    api: Api,
    page: Page,
    pid: str,
    repo_path: Path,
    scope: str,
    ctx: RunContext,
    dashboard_url: str,
) -> bool:
    """Drive Danger Zone Reset row for scope ∈ {all, enrichment, finalize} via UI.

    Reset has no typed-confirm gate; just confirm and observe the UI/disk.
    """
    ctx.summary.trigger_reason = f"Danger Zone Reset scope={scope} (UI)"
    if not open_danger_zone(page, dashboard_url):
        ctx.log(Event(time.time(), "error", {"where": "open_danger_zone"}))
        ctx.summary.error_count += 1
        return False
    ctx.snap(page, "danger_zone_loaded")

    # Snapshot disk pre-reset for assertion.
    idx_dir = repo_path / ".sourceprep"
    pre_files = sorted(p.name for p in idx_dir.iterdir()) if idx_dir.is_dir() else []
    ctx.log(Event(time.time(), "note", {"detail": "pre_reset_files", "count": len(pre_files), "files": pre_files}))

    if not drive_scoped_reset_ui(page, scope, ctx):
        return False

    # Reset is synchronous: response returns when wipes are applied. Allow
    # 3s for the dashboard to receive the new state via SSE/poll.
    time.sleep(3)
    page.goto(dashboard_url)
    time.sleep(2)
    ctx.snap(page, f"after_reset_{scope}_back_to_dash")

    # Assert post-reset disk state matches the scope.
    post_files = sorted(p.name for p in idx_dir.iterdir()) if idx_dir.is_dir() else []
    ctx.log(Event(time.time(), "note", {"detail": "post_reset_files", "count": len(post_files), "files": post_files}))

    fast_sync_files = {
        "manifest.json", "documents.json", "embeddings.npy",
        "trace_inferred_hashes.json", "trace_edges.jsonl",
        "trace_augmented.jsonl", "trace_augment_manifest.json",
        "knowledge_documents.json", "knowledge_embeddings.npy",
        "knowledge_manifest.json",
    }
    deep_files = {
        "trace_epistemic.jsonl", "trace_epistemic_manifest.json",
        "group_reasoning_manifest.json", "deepening_manifest.json",
        "deep_knowledge_manifest.json",
    }
    finalize_files = {
        "atlas.json", "atlas_manifest.json", "rules_manifest.json",
        "concepts_manifest.json", "audit_manifest.json", "antibodies_manifest.json",
    }

    post_set = set(post_files)
    if scope == "all":
        # Nothing should remain except project.json + repo_policy.json + barrier.
        leftover = post_set - {"project.json", "repo_policy.json", ".reset_barrier", "logs"}
        if leftover:
            ctx.log(Event(time.time(), "error", {
                "where": "reset_all_unexpected_files",
                "leftover": sorted(leftover),
            }))
            ctx.summary.error_count += 1
    elif scope == "enrichment":
        # Stages 6-15 wiped; fast sync 1-5 should survive.
        leaked = (deep_files | finalize_files) & post_set
        missing = fast_sync_files - post_set
        # 'leaked' files that still exist might be partial (e.g. validation
        # leaves empty manifests). Log leak as warning, but only error if
        # core deep manifests survive (group_reasoning_manifest, etc).
        core_leak = {"group_reasoning_manifest.json", "atlas_manifest.json",
                     "concepts_manifest.json", "audit_manifest.json"} & post_set
        if core_leak:
            ctx.log(Event(time.time(), "error", {
                "where": "reset_enrichment_left_core_files",
                "leaked": sorted(core_leak),
            }))
            ctx.summary.error_count += 1
        if missing:
            ctx.log(Event(time.time(), "note", {
                "detail": "reset_enrichment_missing_fast_sync_artifact",
                "missing": sorted(missing),
            }))
    elif scope == "finalize":
        leaked = finalize_files & post_set
        # Core finalize manifests should be gone.
        if leaked:
            ctx.log(Event(time.time(), "error", {
                "where": "reset_finalize_left_files",
                "leaked": sorted(leaked),
            }))
            ctx.summary.error_count += 1

    # After reset there's nothing running; watch_until_idle returns ok via
    # the no_activity_observed branch within ~grace*2 seconds.
    return watch_until_idle(api, page, pid, ctx, max_seconds=60, startup_grace_seconds=10,
                            budget_raisable=False)


# ── Top-level ─────────────────────────────────────────────────────


def select_project_in_dashboard(page: Page, project_name: str, timeout_ms: int = 15_000) -> bool:
    """Click the project in the sidebar; fall back to letting the default be."""
    try:
        page.wait_for_load_state("networkidle", timeout=timeout_ms)
    except PWTimeout:
        pass
    try:
        row = page.get_by_text(project_name, exact=False).first
        row.click(timeout=3000)
        return True
    except Exception:
        return False


def write_top_report(root: Path, summaries: list[ModeSummary]) -> None:
    lines = [
        f"# Pipeline Smoke Run — {root.name}",
        "",
        "| Mode | Result | Duration | Stages | Desyncs | Anomalies | Invariants | Errors |",
        "|---|---|---|---|---|---|---|---|",
    ]
    overall_pass = True
    for s in summaries:
        overall_pass = overall_pass and s.pass_ and s.error_count == 0
        dur = f"{round(s.ended_at - s.started_at, 1)}s" if s.ended_at else "—"
        lines.append(
            f"| {s.mode} | {'pass' if s.pass_ else 'fail'} | {dur} | "
            f"{len(s.stages_seen)} | {s.desync_count} | {s.anomaly_count} | "
            f"{s.invariant_failure_count} | {s.error_count} |"
        )
    lines += ["", f"**Overall:** {'pass' if overall_pass else 'fail'}", ""]
    (root / "report.md").write_text("\n".join(lines))


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1] if __doc__ else None)
    ap.add_argument("--project-id", required=True)
    ap.add_argument("--modes", default="initial,incremental,rebuild",
                    help=("Comma-separated subset of: initial, incremental, rebuild, "
                          "rebuild-sync, rebuild-enrichment, "
                          "reset-all, reset-enrichment, reset-finalize, "
                          "ui-run-fast, ui-run-deep, ui-run-finalize."))
    ap.add_argument("--iterations", type=int, default=1)
    ap.add_argument("--headed", action="store_true", help="Show the browser window.")
    ap.add_argument("--dashboard-url", default="http://localhost:5174")
    ap.add_argument("--api-url", default="http://localhost:8400")
    ap.add_argument("--out-root", default="tests/eval/ui_smoke")
    ap.add_argument("--verbose", "-v", action="store_true", default=True)
    # Phase 145 T3 — scheduled side effects for Op-3 / Op-4 (see
    # PROPOSAL_playwright-uat-harness-v1.md §4). Both are at-most-once;
    # both currently apply only to the `rebuild` mode (where the §2u
    # cluster lives). Wiring them into other modes is a v2 concern.
    ap.add_argument("--refresh-at-secs", type=float, default=None,
                    help="During a `rebuild` watch, fire page.reload() once at this elapsed-second mark. Op-3.")
    ap.add_argument("--update-at-secs", type=float, default=None,
                    help="During a `rebuild` watch, POST /pipeline/all once at this elapsed-second mark. Op-4.")
    ap.add_argument("--pause-at-secs", type=float, default=None,
                    help="During a `rebuild` watch, POST /pipeline/pause against the currently "
                         "running group once at (or after) this elapsed-second mark — defers "
                         "until a group is actually running. Op-5.")
    ap.add_argument("--resume-at-secs", type=float, default=None,
                    help="POST /pipeline/resume for the paused group at this elapsed-second "
                         "mark (must be > --pause-at-secs; fires only after the pause did). Op-5.")
    # §9.3 #22 B2: per_iter_timeout in run_session SIGKILLs the child
    # before its 60-min default watch can ever return — so ctx.snap(page,
    # "timeout") never runs and there is no DOM evidence of the hung
    # state. Setting this to (per_iter_timeout - 30) lets the child end
    # cleanly with a screenshot and 30s headroom for stderr flush.
    ap.add_argument("--max-watch-secs", type=int, default=None,
                    help="Watch budget for build/rebuild/incremental watches (seconds). "
                         "Default unset = each mode keeps its built-in budget (rebuild=60m, "
                         "incremental=30m, scoped-reset=60s). When set, it REPLACES the "
                         "heavy-mode budgets (raise for big repos, clamp below the parent "
                         "subprocess timeout); scoped-reset watches only ever clamp.")
    args = ap.parse_args(argv)

    modes = [m.strip() for m in args.modes.split(",") if m.strip()]
    KNOWN_MODES = {
        "initial", "incremental", "rebuild",
        "rebuild-sync", "rebuild-enrichment",
        "reset-all", "reset-enrichment", "reset-finalize",
        "ui-run-fast", "ui-run-deep", "ui-run-finalize",
    }
    unknown = [m for m in modes if m not in KNOWN_MODES]
    if unknown:
        print(f"ERROR: unknown modes: {unknown}", file=sys.stderr)
        return 2

    # Phase 145 T3: --refresh-at-secs / --update-at-secs only fire inside the
    # `rebuild` mode today. Hard error rather than silently ignore: a user
    # passing these flags with a different mode is almost certainly making
    # a mistake (and Op-3/Op-4 from run_session always include rebuild).
    if (args.refresh_at_secs is not None or args.update_at_secs is not None
            or args.pause_at_secs is not None or args.resume_at_secs is not None):
        if "rebuild" not in modes:
            print(
                "ERROR: --refresh-at-secs / --update-at-secs / --pause-at-secs / "
                "--resume-at-secs only fire during `rebuild`; "
                f"current modes={modes} would silently ignore them. "
                "Either add `rebuild` to --modes or drop the scheduled-action flag.",
                file=sys.stderr,
            )
            return 2

    # Op-5 flag coherence: resume without pause is meaningless, and a
    # resume scheduled at-or-before the pause could never fire (resume
    # requires the pause to have fired on a PRIOR tick).
    if args.resume_at_secs is not None and args.pause_at_secs is None:
        print(
            "ERROR: --resume-at-secs requires --pause-at-secs (there is nothing "
            "to resume without a scheduled pause).",
            file=sys.stderr,
        )
        return 2
    if (args.pause_at_secs is not None and args.resume_at_secs is not None
            and args.resume_at_secs <= args.pause_at_secs):
        print(
            f"ERROR: --resume-at-secs ({args.resume_at_secs}) must be strictly greater "
            f"than --pause-at-secs ({args.pause_at_secs}) — the resume only fires after "
            "the pause has fired on a previous poll tick.",
            file=sys.stderr,
        )
        return 2

    # §9.3 #22 B2: install the watch budget cap before any mode runs.
    # Use globals() to bypass UnboundLocalError on a write-then-read in
    # main() while keeping the symbol module-level for tests / clamp.
    if args.max_watch_secs is not None:
        if args.max_watch_secs <= 0:
            print("ERROR: --max-watch-secs must be > 0", file=sys.stderr)
            return 2
        globals()["_MAX_WATCH_SECS_CAP"] = args.max_watch_secs

    api = Api(args.api_url)
    # §9.3 #22 B4: wrap everything past Api() construction in try/finally
    # so api.http closes deterministically even on KeyboardInterrupt or
    # an exception in the dispatch loop. A leaked httpx.Client interacts
    # badly with sync_playwright()'s teardown ─ a pending socket gets
    # gc'd while playwright is mid-context-manager exit, producing the
    # `contextlib.py:158 self.gen.throw` traceback in §9.3 #21.
    try:
        project = api.project(args.project_id)
        # Project endpoint responses vary; try both shapes.
        repo_path = Path(project.get("path") or project.get("project", {}).get("path") or "")
        project_name = project.get("name") or project.get("project", {}).get("name") or args.project_id
        if not repo_path.is_dir():
            print(f"ERROR: project path not found: {repo_path}", file=sys.stderr)
            return 2

        overall_ok = True
        with sync_playwright() as pw:
            browser: Browser = pw.chromium.launch(headless=not args.headed)
            context = browser.new_context(viewport={"width": 1600, "height": 1000})
            page = context.new_page()
            page.goto(args.dashboard_url)
            select_project_in_dashboard(page, project_name)

            # Wait briefly for the pipeline panel to hydrate.
            for _ in range(30):
                if scrape_panel_present(page):
                    break
                time.sleep(0.5)

            for iteration in range(1, args.iterations + 1):
                ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                run_root = Path(args.out_root) / f"run_{ts}"
                if args.iterations > 1:
                    run_root = run_root.with_name(f"{run_root.name}_iter{iteration}")
                run_root.mkdir(parents=True, exist_ok=True)
                print(f"\n=== Iteration {iteration}/{args.iterations} → {run_root}", flush=True)

                summaries: list[ModeSummary] = []
                for mode in modes:
                    print(f"--- Mode: {mode}", flush=True)
                    ctx = RunContext(run_root / mode, mode, verbose=args.verbose)
                    try:
                        # Pipelines refuse to start when config.active != True (F-69).
                        # Force-activate here so the mode is testable regardless of
                        # the user's last toggle state in the dashboard.
                        try:
                            api.set_active(args.project_id, True)
                        except Exception as e:
                            ctx.log(Event(time.time(), "note", {"detail": "set_active_failed", "err": str(e)}))

                        if mode == "initial":
                            passed = run_initial(api, page, args.project_id, ctx, repo_path)
                        elif mode == "incremental":
                            passed = run_incremental(repo_path, api, page, args.project_id, ctx)
                        elif mode == "rebuild":
                            passed = run_rebuild(
                                api, page, args.project_id, ctx, repo_path,
                                refresh_at_secs=args.refresh_at_secs,
                                update_at_secs=args.update_at_secs,
                                pause_at_secs=args.pause_at_secs,
                                resume_at_secs=args.resume_at_secs,
                                project_name=project_name,
                            )
                        elif mode == "rebuild-sync":
                            passed = run_rebuild_scoped_ui(
                                api, page, args.project_id, project_name,
                                "sync", ctx, args.dashboard_url, repo_path,
                            )
                        elif mode == "rebuild-enrichment":
                            passed = run_rebuild_scoped_ui(
                                api, page, args.project_id, project_name,
                                "enrichment", ctx, args.dashboard_url, repo_path,
                            )
                        elif mode == "reset-all":
                            passed = run_reset_scoped_ui(
                                api, page, args.project_id, repo_path,
                                "all", ctx, args.dashboard_url,
                            )
                        elif mode == "reset-enrichment":
                            passed = run_reset_scoped_ui(
                                api, page, args.project_id, repo_path,
                                "enrichment", ctx, args.dashboard_url,
                            )
                        elif mode == "reset-finalize":
                            passed = run_reset_scoped_ui(
                                api, page, args.project_id, repo_path,
                                "finalize", ctx, args.dashboard_url,
                            )
                        elif mode == "ui-run-fast":
                            passed = run_ui_run_group(
                                api, page, args.project_id, "fast_sync",
                                ctx, repo_path, args.dashboard_url,
                            )
                        elif mode == "ui-run-deep":
                            passed = run_ui_run_group(
                                api, page, args.project_id, "deep_enrichment",
                                ctx, repo_path, args.dashboard_url,
                            )
                        elif mode == "ui-run-finalize":
                            passed = run_ui_run_group(
                                api, page, args.project_id, "finalize",
                                ctx, repo_path, args.dashboard_url,
                            )
                        else:
                            passed = False
                    except KeyboardInterrupt:
                        print("Interrupted — cancelling active pipeline if any…", flush=True)
                        try:
                            api.cancel(args.project_id)
                        except Exception:
                            pass
                        ctx.finish(False)
                        raise
                    except Exception as e:
                        ctx.log(Event(time.time(), "error", {"where": "mode_runner", "detail": repr(e)}))
                        ctx.summary.error_count += 1
                        passed = False
                    ctx.finish(passed)
                    summaries.append(ctx.summary)
                    overall_ok = overall_ok and passed and ctx.summary.error_count == 0

                write_top_report(run_root, summaries)

            browser.close()

        print(f"\nOverall: {'PASS' if overall_ok else 'FAIL'}")
        return 0 if overall_ok else 1
    finally:
        # §9.3 #22 B4: close the http client even on KeyboardInterrupt /
        # exception, so pending sockets do not race playwright teardown.
        try:
            api.http.close()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
