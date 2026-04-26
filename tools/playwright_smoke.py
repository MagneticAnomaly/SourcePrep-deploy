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

# Fast Sync → Deep Enrichment → Finalize, in the 15-stage order published
# by /pipeline/status. Kept as a list of (stage_id, group) pairs because
# the UI groups stages identically.
STAGE_ORDER: list[tuple[str, str]] = [
    ("structural", "fast_sync"),
    ("inferred_edges", "fast_sync"),
    ("catalogue", "fast_sync"),
    ("validation", "fast_sync"),
    ("knowledge", "fast_sync"),
    ("enrichment", "deep_enrichment"),
    ("group_reasoning", "deep_enrichment"),
    ("clustering", "deep_enrichment"),
    ("deepening", "deep_enrichment"),
    ("deep_knowledge", "deep_enrichment"),
    ("atlas", "finalize"),
    ("rules", "finalize"),
    ("concepts", "finalize"),
    ("audit", "finalize"),
    ("antibodies", "finalize"),
]
STAGE_TO_GROUP = dict(STAGE_ORDER)

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

# Canonical state vocabulary for desync comparison. Both API and DOM states
# are normalized into this set before diffing.
CANON_STATES = {"pending", "running", "complete", "failed"}

DOM_STATE_TO_CANON = {
    "running": "running",
    "rerunning": "running",
    "rebuilding": "running",  # promoteForRebuild outputs this during Danger Zone rebuilds
    "queued": "pending",
    "waiting": "pending",
    "idle": "pending",
    "not_built": "pending",
    "disabled": "pending",
    "paused": "pending",
    "complete": "complete",
    "stale": "complete",
    "warning": "complete",
    "error": "failed",
}

API_PHASE_TO_CANON = {
    "running": "running",
    "queued": "pending",
    "paused": "pending",
    "idle": "pending",
    "completed": "complete",
    "cancelled": "pending",
    "failed": "failed",
}


# ── Data ──────────────────────────────────────────────────────────


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
            "error_count": self.error_count,
            "stages_seen": self.stages_seen,
            "trigger_reason": self.trigger_reason,
            "notes": self.notes,
        }


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
        return self._unwrap(self.http.delete(f"/projects/{pid}/index/destroy"))

    def run_all(self, pid: str) -> Any:
        return self._unwrap(self.http.post(f"/projects/{pid}/pipeline/all"))

    def rebuild(self, pid: str) -> Any:
        return self._unwrap(self.http.post(f"/projects/{pid}/pipeline/rebuild"))

    def cancel(self, pid: str) -> Any:
        return self._unwrap(self.http.post(f"/projects/{pid}/pipeline/cancel"))

    def set_active(self, pid: str, active: bool) -> Any:
        return self._unwrap(self.http.put(f"/projects/{pid}", json={"config": {"active": active}, "touch": True}))

    # Scoped rebuild/reset endpoints (Phase 117).
    def run_fast(self, pid: str, force_from_start: bool = False) -> Any:
        return self._unwrap(self.http.post(
            f"/projects/{pid}/pipeline/fast",
            json={"force_from_start": force_from_start},
        ))

    def run_deep(self, pid: str, force_from_start: bool = False) -> Any:
        return self._unwrap(self.http.post(
            f"/projects/{pid}/pipeline/deep",
            json={"force_from_start": force_from_start},
        ))

    def enrichment_full_reset(self, pid: str) -> Any:
        return self._unwrap(self.http.delete(f"/projects/{pid}/enrichment/full-reset"))

    def finalize_full_reset(self, pid: str) -> Any:
        return self._unwrap(self.http.delete(f"/projects/{pid}/finalize/full-reset"))

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

    We deliberately refuse to guess. Only three signals produce a verdict:
        1. The stage's group is `phase == "running"` AND it's the current stage → "running"
        2. The stage's group is `phase == "running"` AND it appears earlier than
           the current stage in the group's stage order → "complete" (already done this run)
        3. The stage's group is `phase == "running"` AND it appears later than
           the current stage → "pending" (this run)
        4. A group slot with phase in {failed, cancelled} for the stage → "failed"

    Returns (None, None) during idle — we don't compare against stale DOM
    state when no pipeline is running, because the whole point of
    Phase 96D.4 is that the panel IS allowed to show the last-known state
    between runs. We flag that separately (dom_says_running_while_api_idle)
    in the watch loop.
    """
    group = STAGE_TO_GROUP[stage_id]
    gslot = group_phase.get(group)
    if not gslot:
        return None, None

    phase = gslot.get("phase")
    current_stage = gslot.get("current_stage") or gslot.get("stage")
    if phase != "running":
        # Groups can report completed/failed/paused with a final stage, but
        # we only claim a verdict at transitions; let the idle-branch handle
        # stale displays.
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
    return {
        "fast_sync": status.get("fast_sync") or {},
        "deep_enrichment": status.get("deep_enrichment") or {},
        "finalize": status.get("finalize") or {},
    }


def is_any_running(status: dict[str, Any]) -> bool:
    gp = _group_phase(status)
    return any((g.get("phase") == "running") for g in gp.values())


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
        if not gslot or gslot.get("phase") != "running":
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
    """Phase 118 extra scrutiny: if a group's API phase is `completed`
    for this run, no stage row in that group should be DOM-rendered as
    `running`. Catches stale-spinner-after-group-finish bugs (the
    F-NEW-4 family).
    """
    for group_name, gslot in group_phase.items():
        if not gslot or gslot.get("phase") != "completed":
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
    """
    t0 = time.time()
    last_api_verdict: dict[str, Optional[str]] = {}
    last_desync_sig: dict[str, tuple[str, str]] = {}
    saw_running = False
    idle_since: Optional[float] = None
    next_poll = 0.0
    poll_interval = 2.0
    ok = True

    while True:
        now = time.time()
        elapsed = now - t0
        if elapsed > max_seconds:
            ctx.log(Event(now, "error", {"detail": "watch_until_idle timeout", "elapsed_s": round(elapsed, 1)}))
            ctx.summary.error_count += 1
            ctx.snap(page, "timeout")
            return False

        if now >= next_poll:
            next_poll = now + poll_interval
            try:
                status = api.status(pid)
            except Exception as e:
                ctx.log(Event(now, "error", {"where": "api.status", "detail": str(e)}))
                ctx.summary.error_count += 1
                time.sleep(poll_interval)
                continue

            # Multi-project safe queue observation. Tolerates other projects;
            # only logs the slice belonging to the project under test.
            qsnap = _queue_snapshot_for(api, pid)
            if qsnap is not None:
                ctx.log(Event(now, "queue", qsnap))

            dom = scrape_pipeline_dom(page)
            running = is_any_running(status)

            # Phase 118 extra scrutiny — non-blocking anomaly checks. Run
            # AFTER the canonical desync detector (below) so it remains
            # the authoritative pass/fail signal; these add depth without
            # changing existing pass criteria.
            api_stages = status.get("stages") or {}
            group_phase_for_extras = _group_phase(status)
            _check_group_phase_consistency(api_stages, group_phase_for_extras, dom, ctx, now)
            if repo_path is not None:
                _check_disk_consistency(repo_path, api_stages, group_phase_for_extras, ctx, now)
            _check_barrier_ui(api, pid, page, ctx, now)
            if running:
                saw_running = True
                idle_since = None
            elif idle_since is None:
                idle_since = now

            group_phase = _group_phase(status)

            for stage_id, group in STAGE_ORDER:
                api_state, api_progress = api_stage_verdict(status.get("stages", {}), stage_id, group_phase)
                prev = last_api_verdict.get(stage_id)

                # Log stage transitions.
                if api_state != prev:
                    if api_state == "running":
                        ctx.log(Event(now, "stage-start", {"stage": stage_id, "group": group}))
                        ctx.snap(page, f"{group}_{stage_id}_start")
                        if stage_id not in ctx.summary.stages_seen:
                            ctx.summary.stages_seen.append(stage_id)
                    elif prev == "running" and api_state in ("complete", "failed"):
                        ctx.log(Event(now, "stage-end", {"stage": stage_id, "state": api_state}))
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
                ctx.log(Event(now, "desync", {
                    "stage": stage_id,
                    "subtype": disagreement[0],
                    "api": {"state": api_state, "progress": api_progress},
                    "dom": {"state": dom_state_raw, "progress": dom_row.get("progress"), "canon": dom_canon},
                }))
                ctx.snap(page, f"desync_{stage_id}_{disagreement[0]}")
                ok = False

            if saw_running and idle_since and (now - idle_since) >= settle_seconds:
                ctx.log(Event(now, "note", {"detail": "settled_idle", "elapsed_s": round(elapsed, 1)}))
                ctx.snap(page, "settled_idle")
                return ok

            # If we never saw a running state and it's been >startup_grace_seconds,
            # treat that as a no-op run (e.g., incremental with nothing to do) —
            # not a failure.
            if not saw_running and elapsed > startup_grace_seconds * 2 and not running:
                ctx.log(Event(now, "note", {"detail": "no_activity_observed", "elapsed_s": round(elapsed, 1)}))
                ctx.snap(page, "no_activity")
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


def run_rebuild(api: Api, page: Page, pid: str, ctx: RunContext, repo_path: Path) -> bool:
    ctx.summary.trigger_reason = "POST /pipeline/rebuild"
    ctx.snap(page, "before_rebuild")
    try:
        api.rebuild(pid)
    except Exception as e:
        ctx.log(Event(time.time(), "error", {"where": "rebuild", "detail": str(e)}))
        ctx.summary.error_count += 1
        return False

    time.sleep(3)
    ctx.snap(page, "after_rebuild_trigger")
    return watch_until_idle(api, page, pid, ctx, max_seconds=60 * 60, repo_path=repo_path)


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
    return watch_until_idle(api, page, pid, ctx, max_seconds=60, startup_grace_seconds=10)


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
        "| Mode | Result | Duration | Stages | Desyncs | Anomalies | Errors |",
        "|---|---|---|---|---|---|---|",
    ]
    overall_pass = True
    for s in summaries:
        overall_pass = overall_pass and s.pass_ and s.error_count == 0
        dur = f"{round(s.ended_at - s.started_at, 1)}s" if s.ended_at else "—"
        lines.append(
            f"| {s.mode} | {'pass' if s.pass_ else 'fail'} | {dur} | "
            f"{len(s.stages_seen)} | {s.desync_count} | {s.anomaly_count} | {s.error_count} |"
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

    api = Api(args.api_url)
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
                        passed = run_rebuild(api, page, args.project_id, ctx, repo_path)
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


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
