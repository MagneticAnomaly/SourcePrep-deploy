"""
Prep dashboard pipeline smoke driver.

Exercises the pipeline UI against a chosen project across three modes:
    - initial     (destroy index, run from scratch)
    - incremental (touch a file, let the watcher trigger a re-run)
    - rebuild     (POST /pipeline/rebuild, equivalent to Danger Zone)

Polls /projects/{id}/pipeline/status every 2s while any mode is active and
scrapes the dashboard DOM in parallel. Any disagreement between API truth
and rendered DOM is logged as a desync event with a screenshot attached.

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
    kind: str  # stage-start | stage-end | desync | error | note
    data: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return {"ts": self.ts, "kind": self.kind, **self.data}


@dataclass
class ModeSummary:
    mode: str
    started_at: float
    ended_at: float = 0.0
    pass_: bool = False
    desync_count: int = 0
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


def watch_until_idle(
    api: Api,
    page: Page,
    pid: str,
    ctx: RunContext,
    *,
    max_seconds: int,
    startup_grace_seconds: int = 15,
    settle_seconds: int = 8,
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

            dom = scrape_pipeline_dom(page)
            running = is_any_running(status)
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
                    "kind": disagreement[0],
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


def run_initial(api: Api, page: Page, pid: str, ctx: RunContext) -> bool:
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

    return watch_until_idle(api, page, pid, ctx, max_seconds=60 * 60)


def run_incremental(repo_path: Path, api: Api, page: Page, pid: str, ctx: RunContext) -> bool:
    ctx.summary.trigger_reason = "write tick + POST /pipeline/all (incremental path)"
    tick = repo_path / "prep_smoke_tick.py"
    tick.write_text(f"# prep smoke tick {datetime.now(timezone.utc).isoformat()}\nTICK = 1\n")
    ctx.log(Event(time.time(), "note", {"detail": "tick_written", "path": str(tick)}))

    try:
        time.sleep(2)
        api.run_all(pid)
        ctx.snap(page, "after_run_all_trigger")
        return watch_until_idle(api, page, pid, ctx, max_seconds=60 * 30, startup_grace_seconds=20)
    finally:
        try:
            tick.unlink()
            ctx.log(Event(time.time(), "note", {"detail": "tick_deleted"}))
        except FileNotFoundError:
            pass


def run_rebuild(api: Api, page: Page, pid: str, ctx: RunContext) -> bool:
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
    return watch_until_idle(api, page, pid, ctx, max_seconds=60 * 60)


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
        "| Mode | Result | Duration | Stages Observed | Desyncs | Errors |",
        "|---|---|---|---|---|---|",
    ]
    overall_pass = True
    for s in summaries:
        overall_pass = overall_pass and s.pass_ and s.error_count == 0
        dur = f"{round(s.ended_at - s.started_at, 1)}s" if s.ended_at else "—"
        lines.append(
            f"| {s.mode} | {'✅ pass' if s.pass_ else '❌ fail'} | {dur} | "
            f"{len(s.stages_seen)} | {s.desync_count} | {s.error_count} |"
        )
    lines += ["", f"**Overall:** {'✅ pass' if overall_pass else '❌ fail'}", ""]
    (root / "report.md").write_text("\n".join(lines))


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1] if __doc__ else None)
    ap.add_argument("--project-id", required=True)
    ap.add_argument("--modes", default="initial,incremental,rebuild",
                    help="Comma-separated subset of initial,incremental,rebuild.")
    ap.add_argument("--iterations", type=int, default=1)
    ap.add_argument("--headed", action="store_true", help="Show the browser window.")
    ap.add_argument("--dashboard-url", default="http://localhost:5174")
    ap.add_argument("--api-url", default="http://localhost:8400")
    ap.add_argument("--out-root", default="tests/eval/ui_smoke")
    ap.add_argument("--verbose", "-v", action="store_true", default=True)
    args = ap.parse_args(argv)

    modes = [m.strip() for m in args.modes.split(",") if m.strip()]
    unknown = [m for m in modes if m not in {"initial", "incremental", "rebuild"}]
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
                        passed = run_initial(api, page, args.project_id, ctx)
                    elif mode == "incremental":
                        passed = run_incremental(repo_path, api, page, args.project_id, ctx)
                    elif mode == "rebuild":
                        passed = run_rebuild(api, page, args.project_id, ctx)
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
