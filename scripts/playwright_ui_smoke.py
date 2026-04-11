#!/usr/bin/env python3
"""Phase 96D: Playwright UI smoke driver.

Watches the CoDRAG dashboard during a pipeline rebuild cycle and compares
what the UI displays against what the backend API reports. Flags desyncs.

Requirements:
    - Daemon running at http://localhost:8400
    - Dashboard dev server running at http://localhost:5174
    - playwright + chromium installed (pip install playwright && playwright install chromium)

Usage:
    .venv/bin/python scripts/playwright_ui_smoke.py

    # Override project (default: SMOKE: rust_repo)
    .venv/bin/python scripts/playwright_ui_smoke.py --project 0c50e42e-6d0d-4938-85a4-e87c3f5dbdca

    # Don't actually trigger the rebuild (just observe current state)
    .venv/bin/python scripts/playwright_ui_smoke.py --no-trigger

    # Longer poll window for big projects
    .venv/bin/python scripts/playwright_ui_smoke.py --timeout 1800

Output:
    - Screenshots saved to tests/eval/ui_smoke/ with stage markers
    - JSON report with timeline of UI state vs API state
    - Exit code 0 if all checks pass, 1 if desyncs found
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

import httpx
from playwright.sync_api import Page, sync_playwright


# ── Configuration ─────────────────────────────────────────────────

DEFAULT_PROJECT_ID = "0c50e42e-6d0d-4938-85a4-e87c3f5dbdca"  # SMOKE: rust_repo
DAEMON_URL = "http://localhost:8400"
DASHBOARD_URL = "http://localhost:5174"
OUTPUT_DIR = Path("tests/eval/ui_smoke")


# ── Data structures ──────────────────────────────────────────────

@dataclass
class BackendState:
    """What the daemon says the pipeline state is."""
    timestamp: float
    fast_sync_phase: str | None
    fast_sync_stage: str | None
    fast_sync_idx: int | None
    deep_phase: str | None
    deep_stage: str | None
    deep_idx: int | None
    queue_items: list[dict[str, Any]]
    nodes: dict[str, dict[str, Any]]


@dataclass
class UiState:
    """What the dashboard is showing."""
    timestamp: float
    selected_project: str | None
    queue_items_visible: list[str]
    pipeline_panel_stages: list[dict[str, str]]
    toast_messages: list[str]


@dataclass
class Discrepancy:
    """A difference between UI and backend state."""
    timestamp: float
    kind: str  # "stale_queue", "selected_mismatch", "stage_mismatch", etc.
    ui_value: str
    api_value: str
    severity: str  # "error" or "warning"


@dataclass
class Report:
    project_id: str
    project_name: str
    trigger_mode: str
    start_ts: float
    end_ts: float = 0.0
    transitions: list[dict[str, Any]] = field(default_factory=list)
    discrepancies: list[Discrepancy] = field(default_factory=list)
    screenshots: list[str] = field(default_factory=list)
    final_status: str = "unknown"


# ── Backend polling ──────────────────────────────────────────────

def fetch_backend_state(client: httpx.Client, project_id: str) -> BackendState:
    now = time.time()
    fs_phase = fs_stage = None
    fs_idx = None
    dp_phase = dp_stage = None
    dp_idx = None
    queue_items: list[dict[str, Any]] = []
    nodes: dict[str, dict[str, Any]] = {}
    try:
        r = client.get(f"{DAEMON_URL}/projects/{project_id}/pipeline/status")
        s = r.json()["data"]
        fs = s.get("fast_sync") or {}
        fs_phase = fs.get("phase")
        fs_stage = fs.get("current_stage")
        fs_idx = fs.get("current_stage_index")
        de = s.get("deep_enrichment") or {}
        dp_phase = de.get("phase")
        dp_stage = de.get("current_stage")
        dp_idx = de.get("current_stage_index")
    except Exception as e:
        print(f"  [API] status error: {type(e).__name__}", file=sys.stderr)
    try:
        r = client.get(f"{DAEMON_URL}/system/pipeline-queue")
        d = r.json()["data"]
        queue_items = d.get("queue", [])
        nodes = d.get("nodes", {})
    except Exception as e:
        print(f"  [API] queue error: {type(e).__name__}", file=sys.stderr)
    return BackendState(
        timestamp=now,
        fast_sync_phase=fs_phase,
        fast_sync_stage=fs_stage,
        fast_sync_idx=fs_idx,
        deep_phase=dp_phase,
        deep_stage=dp_stage,
        deep_idx=dp_idx,
        queue_items=queue_items,
        nodes=nodes,
    )


# ── UI inspection ────────────────────────────────────────────────

def fetch_ui_state(page: Page) -> UiState:
    now = time.time()

    # Find the selected project by looking for the row with the active toggle
    selected = None
    try:
        # The selected project has a highlighted toggle or distinct styling.
        # We use the one showing the blue "on" toggle indicator or the active-ring class.
        rows = page.locator('div[title*="/"]').evaluate_all(
            "els => els.filter(e => e.offsetParent).map(e => ({ title: e.getAttribute('title'), text: e.textContent?.trim() || '' }))"
        )
        # Heuristic: the currently selected project is the one whose pipeline panel
        # is currently rendered. We read from the top-level viewed project breadcrumb
        # or from the sidebar highlight if present.
        # Fallback: take the project name from the Knowledge Base Status title bar.
        kbs = page.locator('text=Knowledge Base Status').locator('..').locator('..').inner_text() if page.locator('text=Knowledge Base Status').count() > 0 else ""
        for r in rows:
            if r.get("title") and r["title"] in kbs:
                selected = r.get("text", "").strip()
                break
    except Exception:
        pass

    # Queue panel items — look for the PIPELINE QUEUE section
    queue_items_visible: list[str] = []
    try:
        q_section = page.locator('text="PIPELINE QUEUE"').locator('..').locator('..')
        if q_section.count() > 0:
            raw = q_section.inner_text()
            # Parse into lines, drop "PIPELINE QUEUE" header
            lines = [ln.strip() for ln in raw.split("\n") if ln.strip() and ln.strip() != "PIPELINE QUEUE"]
            queue_items_visible = lines
    except Exception:
        pass

    # Pipeline panel stages
    pipeline_panel_stages: list[dict[str, str]] = []
    try:
        gp = page.locator('text="Graph Enrichment"').first
        if gp.count() > 0:
            # Walk up to the panel container, then find stage entries
            panel = gp.locator('..').locator('..').locator('..')
            # Stages have labels like "Structural Graph", "Edge Discovery", etc.
            stage_names = [
                "Structural Graph", "Edge Discovery", "Fast Catalogue",
                "Relationship Validation", "Knowledge Embedding",
                "Deep Reasoning", "Group Reasoning", "Module Synthesis",
                "Atlas Building", "Continuous Deepening", "Deep Knowledge Embedding",
            ]
            for name in stage_names:
                loc = panel.locator(f'text="{name}"').first
                if loc.count() > 0:
                    try:
                        # Get the parent row's full text to capture status
                        row = loc.locator('..').locator('..')
                        row_text = row.inner_text()[:200]
                        pipeline_panel_stages.append({"name": name, "text": row_text.replace("\n", " | ")})
                    except Exception:
                        pass
    except Exception:
        pass

    # Toast messages (warnings/errors shown to user)
    toast_messages: list[str] = []
    try:
        toasts = page.locator('[role="alert"], [class*="toast"]').all()
        for t in toasts[:5]:
            try:
                txt = t.inner_text().strip()
                if txt:
                    toast_messages.append(txt[:150])
            except Exception:
                pass
    except Exception:
        pass

    return UiState(
        timestamp=now,
        selected_project=selected,
        queue_items_visible=queue_items_visible,
        pipeline_panel_stages=pipeline_panel_stages,
        toast_messages=toast_messages,
    )


# ── Desync detection ─────────────────────────────────────────────

def detect_discrepancies(backend: BackendState, ui: UiState) -> list[Discrepancy]:
    discs: list[Discrepancy] = []
    ts = backend.timestamp

    # Check 1: Stale queue entries — terminal states shouldn't appear
    for item in backend.queue_items:
        phase = item.get("phase", "")
        if phase in ("cancelled", "failed", "completed"):
            discs.append(Discrepancy(
                timestamp=ts,
                kind="stale_queue",
                ui_value=f"queue shows {item.get('project_name')} [{phase}]",
                api_value=f"API returned terminal-state {phase} in queue",
                severity="error",
            ))

    # Check 2: UI queue count vs API queue count
    ui_count = len([q for q in ui.queue_items_visible if q and "PENDING" in q.upper() or "RUNNING" in q.upper() or "QUEUED" in q.upper()])
    api_count = len(backend.queue_items)
    if ui_count != api_count and api_count > 0:
        discs.append(Discrepancy(
            timestamp=ts,
            kind="queue_count_mismatch",
            ui_value=f"UI shows ~{ui_count} queue items",
            api_value=f"API returns {api_count} queue items",
            severity="warning",
        ))

    return discs


# ── Main ─────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="CoDRAG dashboard UI smoke driver")
    parser.add_argument("--project", default=DEFAULT_PROJECT_ID,
                        help="Project ID to drive (default: SMOKE: rust_repo)")
    parser.add_argument("--no-trigger", action="store_true",
                        help="Don't trigger rebuild — just observe current state")
    parser.add_argument("--trigger", choices=["rebuild", "fast", "deep", "all"], default="rebuild",
                        help="Which pipeline action to trigger (default: rebuild)")
    parser.add_argument("--timeout", type=int, default=900,
                        help="Max seconds to wait for pipeline completion (default: 900)")
    parser.add_argument("--poll-interval", type=float, default=3.0,
                        help="Seconds between polls (default: 3.0)")
    parser.add_argument("--headed", action="store_true",
                        help="Run with a visible browser window")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    run_id = int(time.time())
    run_dir = OUTPUT_DIR / f"run_{run_id}"
    run_dir.mkdir()

    print(f"[smoke] Run {run_id} → {run_dir}")
    print(f"[smoke] Project: {args.project}")
    print(f"[smoke] Trigger: {args.trigger if not args.no_trigger else 'none (observe only)'}")
    print()

    # Preflight: daemon up?
    with httpx.Client(timeout=5.0) as client:
        try:
            r = client.get(f"{DAEMON_URL}/health")
            assert r.status_code == 200
        except Exception as e:
            print(f"[smoke] ERROR: daemon unreachable at {DAEMON_URL}: {e}")
            return 2

        # Get project name for the report
        try:
            r = client.get(f"{DAEMON_URL}/projects")
            projects = r.json()["data"]["projects"]
            project_name = next(
                (p["name"] for p in projects if p["id"] == args.project),
                args.project[:8],
            )
        except Exception:
            project_name = args.project[:8]

        report = Report(
            project_id=args.project,
            project_name=project_name,
            trigger_mode=args.trigger if not args.no_trigger else "observe",
            start_ts=time.time(),
        )

        # Launch Playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=not args.headed)
            context = browser.new_context(viewport={"width": 1600, "height": 1000})
            page = context.new_page()

            print("[smoke] Opening dashboard...")
            try:
                page.goto(DASHBOARD_URL, wait_until='domcontentloaded', timeout=15000)
                page.wait_for_timeout(5000)
            except Exception as e:
                print(f"[smoke] ERROR: dashboard load failed: {e}")
                browser.close()
                return 2

            # Baseline screenshot
            p0 = run_dir / "00_baseline.png"
            page.screenshot(path=str(p0), full_page=True)
            report.screenshots.append(str(p0))
            print(f"[smoke] baseline → {p0}")

            # Trigger the pipeline
            if not args.no_trigger:
                print(f"[smoke] Triggering {args.trigger} via API...")
                endpoint_map = {
                    "rebuild": "rebuild",
                    "fast": "fast",
                    "deep": "deep",
                    "all": "all",
                }
                try:
                    r = client.post(
                        f"{DAEMON_URL}/projects/{args.project}/pipeline/{endpoint_map[args.trigger]}"
                    )
                    print(f"[smoke] trigger response: {r.status_code} {r.json()}")
                except Exception as e:
                    print(f"[smoke] trigger error: {e}")

            # Poll loop
            print(f"[smoke] Polling every {args.poll_interval}s (max {args.timeout}s)")
            deadline = time.time() + args.timeout
            last_snap_phase = None
            snap_n = 0
            terminal = False

            while time.time() < deadline and not terminal:
                backend = fetch_backend_state(client, args.project)
                ui = fetch_ui_state(page)
                discs = detect_discrepancies(backend, ui)

                fp = backend.fast_sync_phase or "none"
                fs = backend.fast_sync_stage or "-"
                dp = backend.deep_phase or "none"
                ds = backend.deep_stage or "-"
                elapsed = backend.timestamp - report.start_ts

                # Log each transition
                current_snap = f"fast={fp}/{fs} deep={dp}/{ds}"
                if current_snap != last_snap_phase:
                    snap_n += 1
                    snap_path = run_dir / f"{snap_n:02d}_{fp}_{fs}.png"
                    try:
                        page.screenshot(path=str(snap_path), full_page=True)
                        report.screenshots.append(str(snap_path))
                    except Exception:
                        pass
                    print(f"[{elapsed:5.1f}s] {current_snap} (queue={len(backend.queue_items)}, discs={len(discs)})")
                    if discs:
                        for d in discs:
                            marker = "❌" if d.severity == "error" else "⚠️ "
                            print(f"         {marker} {d.kind}: {d.ui_value} vs {d.api_value}")
                    report.transitions.append({
                        "elapsed": round(elapsed, 1),
                        "backend": asdict(backend),
                        "ui": asdict(ui),
                        "discrepancies": [asdict(d) for d in discs],
                        "screenshot": str(snap_path) if snap_n else None,
                    })
                    last_snap_phase = current_snap

                report.discrepancies.extend(discs)

                # Terminal check
                if fp in ("completed", "failed", "cancelled") and dp in ("completed", "failed", "cancelled", "none", None):
                    # If trigger was fast-only, fast completion is terminal
                    if args.trigger == "fast":
                        terminal = True
                    # If trigger was rebuild/all, wait for deep too
                    elif fp == "completed" and dp in ("completed", "failed", "cancelled"):
                        terminal = True

                time.sleep(args.poll_interval)

            report.end_ts = time.time()
            report.final_status = "completed" if terminal else "timeout"

            # Final snapshot
            p_final = run_dir / "zz_final.png"
            page.screenshot(path=str(p_final), full_page=True)
            report.screenshots.append(str(p_final))

            browser.close()

    # Write report
    report_path = run_dir / "report.json"
    with open(report_path, "w") as f:
        json.dump(asdict(report), f, indent=2, default=str)
    print(f"\n[smoke] Report → {report_path}")

    # Summary
    total_discs = len(set((d.kind, d.ui_value, d.api_value) for d in report.discrepancies))
    print(f"[smoke] Status: {report.final_status}")
    print(f"[smoke] Unique discrepancies: {total_discs}")
    print(f"[smoke] Screenshots: {len(report.screenshots)}")

    if total_discs > 0:
        print("\n[smoke] DESYNCS FOUND:")
        seen = set()
        for d in report.discrepancies:
            key = (d.kind, d.ui_value[:80])
            if key in seen:
                continue
            seen.add(key)
            marker = "❌" if d.severity == "error" else "⚠️ "
            print(f"  {marker} [{d.kind}] {d.ui_value} ↔ {d.api_value}")

    return 1 if total_discs > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
