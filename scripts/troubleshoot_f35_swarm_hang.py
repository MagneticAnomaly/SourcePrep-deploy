#!/usr/bin/env python3
"""F-35 investigation: daemon-runtime swarm call hang.

Reproduces the swarm hang in isolation against the troubleshoot harness
(no dashboard, no polling storm). Measures wall-clock per phase and
reports thread pool state at the end.

Usage:
    .venv/bin/python scripts/troubleshoot_f35_swarm_hang.py [--workers N] [--project ID]

Defaults:
    --workers 10        Match the SwarmOrchestrator default
    --project SMOKE: rust_repo

What it tests:
    1. Daemon /health responsiveness BEFORE the swarm trigger
    2. Trigger /pipeline/finalize on the chosen project
    3. Watch the daemon log for swarm activation lines
    4. Probe /health every 5s during the swarm to detect thread pool
       exhaustion (F-11 pattern)
    5. Report total elapsed, swarm fan-out time, and any timeouts
    6. py-spy dump if the daemon hangs

Hypothesis testing:
    --workers 2     → tests hypothesis #1 (urllib3 connection pool of 10)
    --workers 1     → eliminates parallelism entirely
    --workers 10    → reproduces baseline hang
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import httpx

DAEMON_URL = "http://localhost:8400"
LOG_FILE = "/tmp/codrag_troubleshoot.log"
DEFAULT_PROJECT_ID = "0c50e42e-6d0d-4938-85a4-e87c3f5dbdca"  # SMOKE: rust_repo
RUST_REPO_LOG_DIR = Path(
    "/Volumes/4TB-BAD/HumanAI/CoDRAG/tests/eval/sample_repos/generated/rust_repo/.codrag/logs"
)
MINI_REDIS_LOG_DIR = Path(
    "/Volumes/4TB-BAD/HumanAI/CoDRAG/tests/eval/real_repos/mini-redis-rust/.codrag/logs"
)


def log(msg: str) -> None:
    elapsed = time.time() - START
    print(f"[{elapsed:6.1f}s] {msg}", flush=True)


def probe_health(client: httpx.Client) -> tuple[bool, float]:
    t0 = time.time()
    try:
        r = client.get(f"{DAEMON_URL}/health", timeout=3.0)
        return r.status_code == 200, time.time() - t0
    except Exception:
        return False, time.time() - t0


def find_pipeline_log(project_id: str) -> Optional[Path]:
    """Find the most recent pipeline log file for the project."""
    log_dirs = []
    if "0c50e42e" in project_id:
        log_dirs.append(RUST_REPO_LOG_DIR)
    if "b1fd79e7" in project_id:
        log_dirs.append(MINI_REDIS_LOG_DIR)
    # Fallback: try both
    if not log_dirs:
        log_dirs = [RUST_REPO_LOG_DIR, MINI_REDIS_LOG_DIR]
    candidates = []
    for d in log_dirs:
        if d.exists():
            for f in d.glob("pipeline_*.log"):
                candidates.append(f)
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def grep_log(path: Path, patterns: list[str]) -> list[str]:
    """Return lines in path matching any of the patterns."""
    if not path.exists():
        return []
    out = []
    with open(path) as f:
        for line in f:
            if any(p in line for p in patterns):
                out.append(line.rstrip())
    return out


def daemon_pid() -> Optional[int]:
    try:
        out = subprocess.check_output(
            ["lsof", "-i", ":8400", "-sTCP:LISTEN", "-t"],
            text=True, timeout=3,
        ).strip()
        return int(out.split("\n")[0]) if out else None
    except Exception:
        return None


def py_spy_dump(pid: int) -> str:
    """Try to get a py-spy dump. Needs sudo on macOS — best effort."""
    try:
        out = subprocess.run(
            ["./.venv/bin/py-spy", "dump", "--pid", str(pid)],
            capture_output=True, text=True, timeout=15,
        )
        if out.returncode == 0:
            return out.stdout
        return f"py-spy failed (try with sudo): {out.stderr[:200]}"
    except Exception as e:
        return f"py-spy error: {e}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", default=DEFAULT_PROJECT_ID,
                        help="Project ID to test (default: SMOKE: rust_repo)")
    parser.add_argument("--swarm-cap", type=int, default=None,
                        help="Override max swarm workers via SwarmOrchestrator default. "
                             "Sets CODRAG_SWARM_WORKER_CAP env hint (only effective if "
                             "the daemon was started with this var). For now, used only "
                             "for test naming.")
    parser.add_argument("--max-wait", type=int, default=180,
                        help="Max seconds to wait for finalize completion (default: 180)")
    parser.add_argument("--probe-interval", type=int, default=5,
                        help="Health probe interval (default: 5s)")
    parser.add_argument("--label", default="baseline",
                        help="Label for this run (e.g., 'baseline', 'pool=2')")
    args = parser.parse_args()

    global START
    START = time.time()

    print("=" * 70)
    print(f"F-35 SWARM HANG TEST — label: {args.label}")
    print(f"  Project:        {args.project}")
    print(f"  Max wait:       {args.max_wait}s")
    print(f"  Probe interval: {args.probe_interval}s")
    print("=" * 70)
    print()

    pid = daemon_pid()
    if not pid:
        print("ERROR: no daemon listening on :8400")
        print("Start with: scripts/troubleshoot.sh up")
        return 2
    log(f"Daemon PID: {pid}")

    with httpx.Client() as c:
        # Step 1: Baseline health check
        ok, dt = probe_health(c)
        log(f"Baseline /health: {'OK' if ok else 'FAIL'} ({dt*1000:.0f}ms)")
        if not ok:
            print("Daemon not responding before test even started")
            return 2

        # Step 2: Activate project (idempotent)
        try:
            r = c.put(
                f"{DAEMON_URL}/projects/{args.project}",
                json={"config": {"active": True}},
                timeout=5.0,
            )
            log(f"Activate: {r.status_code}")
        except Exception as e:
            log(f"Activate error: {type(e).__name__}: {e}")

        # Step 3: Find current pipeline log path BEFORE trigger
        pre_log = find_pipeline_log(args.project)
        log(f"Pre-trigger log file: {pre_log}")
        pre_log_size = pre_log.stat().st_size if pre_log else 0

        # Step 4: Trigger finalize
        try:
            r = c.post(
                f"{DAEMON_URL}/projects/{args.project}/pipeline/finalize",
                timeout=10.0,
            )
            log(f"POST /finalize: {r.status_code}")
            if r.status_code != 200:
                log(f"  body: {r.text[:200]}")
                return 1
        except Exception as e:
            log(f"Trigger error: {type(e).__name__}: {e}")
            return 1

        # Step 5: Wait for new log file or growth
        time.sleep(2)
        cur_log = find_pipeline_log(args.project)
        if cur_log != pre_log or (cur_log and cur_log.stat().st_size > pre_log_size):
            log(f"New pipeline log: {cur_log}")
        else:
            log(f"No new log activity yet — still watching {cur_log}")

        # Step 6: Watch loop
        deadline = time.time() + args.max_wait
        last_probe = 0.0
        last_log_size = cur_log.stat().st_size if cur_log else 0
        last_log_change = time.time()
        completed = False
        terminal_marker_seen = False
        swarm_seen = False

        while time.time() < deadline:
            now = time.time()

            # Health probe
            if now - last_probe >= args.probe_interval:
                last_probe = now
                ok, dt = probe_health(c)
                marker = "OK " if ok else "TO "
                msg = f"probe: {marker} ({dt*1000:.0f}ms)"

                # Check log growth
                cur_log = find_pipeline_log(args.project)
                if cur_log and cur_log.exists():
                    sz = cur_log.stat().st_size
                    if sz != last_log_size:
                        last_log_size = sz
                        last_log_change = now
                        msg += f"  log+={sz}b"
                    else:
                        msg += f"  log STALE ({now - last_log_change:.0f}s)"

                    # Check for terminal events
                    tail_lines = grep_log(
                        cur_log,
                        ["run_end", "Swarm/Concepts] Fan-out", "Swarm/coordinator", "stage_end"],
                    )
                    for ln in tail_lines:
                        if "Fan-out" in ln and not swarm_seen:
                            log(f"  {ln[ln.index('[Swarm'):][:120]}")
                            swarm_seen = True
                        if "timed out" in ln:
                            log(f"  {ln[ln.index('['):][:120]}")
                        if '"result": "completed"' in ln:
                            terminal_marker_seen = True
                            completed = True

                log(msg)

                if completed:
                    log("FINALIZE COMPLETED")
                    break

                # Detect "stuck" — log hasn't grown in 60s
                if now - last_log_change > 60 and last_log_size > 0:
                    log("Log stale for 60s — daemon may be hung")

            time.sleep(1)

        # Final summary
        print()
        print("=" * 70)
        print("SUMMARY")
        print("=" * 70)
        elapsed = time.time() - START
        ok, dt = probe_health(c)
        print(f"Total elapsed:   {elapsed:.1f}s")
        print(f"Final /health:   {'OK' if ok else 'TIMEOUT'} ({dt*1000:.0f}ms)")
        print(f"Completed:       {completed}")
        print(f"Swarm activated: {swarm_seen}")
        print()

        # Final log lines for diagnosis
        cur_log = find_pipeline_log(args.project)
        if cur_log and cur_log.exists():
            print(f"Pipeline log: {cur_log}")
            print(f"Size: {cur_log.stat().st_size} bytes")
            print()
            print("Last 5 swarm/timeout/error lines:")
            tail = grep_log(
                cur_log,
                ["Swarm", "timed out", "ERROR", "Fan-out", "completed in"],
            )
            for ln in tail[-5:]:
                print(f"  {ln[:200]}")

        # If hung, try py-spy dump
        if not completed and not ok:
            print()
            print("=" * 70)
            print("DAEMON APPEARS HUNG — py-spy dump:")
            print("=" * 70)
            print(py_spy_dump(pid))

        return 0 if completed else 1


if __name__ == "__main__":
    sys.exit(main())
