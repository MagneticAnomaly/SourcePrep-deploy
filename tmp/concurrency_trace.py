"""Continuous poller capturing live concurrency state.

Logs /llm/slots/status + /compute/scheduler every second to JSONL so we
can post-hoc verify whether the in-flight worker count actually reaches
the configured cap during fan-out, or stays low.

Usage:
    .venv/bin/python tmp/concurrency_trace.py [--seconds 600]

Output: tmp/concurrency_trace_<UTC>.jsonl
"""
from __future__ import annotations
import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
import urllib.request

DAEMON = "http://localhost:8400"


def fetch(path: str) -> dict:
    try:
        with urllib.request.urlopen(f"{DAEMON}{path}", timeout=2) as r:
            return json.load(r)
    except Exception as e:
        return {"_error": str(e)}


def snap() -> dict:
    slots = fetch("/llm/slots/status").get("data") or {}
    sched = fetch("/compute/scheduler").get("data") or {}
    out = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "running_tasks": [],
        "nodes": {},
    }
    for rt in slots.get("running_tasks", []) or []:
        out["running_tasks"].append({
            "task_id": rt.get("task_id"),
            "stage": rt.get("stage"),
            "model_slot": rt.get("model_slot"),
            "swarm_role": rt.get("swarm_role"),
            "is_swarm": rt.get("is_swarm"),
            "concurrent_workers": rt.get("concurrent_workers"),
            "scheduler_capacity": rt.get("scheduler_capacity"),
            "compute_node": rt.get("compute_node"),
        })
    for nid, n in (sched.get("nodes") or {}).items():
        out["nodes"][nid] = {
            "max_concurrent": n.get("max_concurrent"),
            "dynamic_capacity": n.get("dynamic_capacity"),
            "in_flight_requests": n.get("in_flight_requests"),
            "current_load": n.get("current_load"),
            "current_limit": n.get("current_limit"),
            "aimd_mode": n.get("aimd_mode"),
            "state": n.get("state"),
            "discovered_ceiling": n.get("discovered_ceiling"),
            "active_stages": n.get("active") or {},
        }
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=int, default=600)
    ap.add_argument("--interval", type=float, default=1.0)
    args = ap.parse_args()

    out_dir = Path("/Volumes/4TB-BAD/HumanAI/CoDRAG/tmp")
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = out_dir / f"concurrency_trace_{stamp}.jsonl"

    print(f"poller -> {out_path}")
    print(f"running for {args.seconds}s at {args.interval}s interval")
    deadline = time.time() + args.seconds
    last_summary = 0.0
    last_state_key = None
    with out_path.open("w") as fh:
        while time.time() < deadline:
            s = snap()
            fh.write(json.dumps(s, separators=(",", ":")) + "\n")
            fh.flush()

            # Compact one-line summary: stage + per-node in_flight
            tasks = s["running_tasks"]
            stage = tasks[0]["stage"] if tasks else "idle"
            slot = tasks[0]["model_slot"] if tasks else "-"
            swarm = "swarm" if (tasks and tasks[0].get("is_swarm")) else "fanout"
            workers = tasks[0]["concurrent_workers"] if tasks else 0
            cap = tasks[0]["scheduler_capacity"] if tasks else 0
            node_state = " ".join(
                f"{nid.replace('cloud:default_ollama', 'cloud').replace('local:default_ollama', 'local').replace('__embedding__', 'emb')}:{n['in_flight_requests']}/{n['dynamic_capacity']}"
                for nid, n in s["nodes"].items()
                if not nid.startswith("local:ep_") and n["dynamic_capacity"] > 1
            )
            state_key = f"{stage}/{slot}/{swarm}/{workers}/{cap}"
            now = time.time()
            if state_key != last_state_key or now - last_summary > 10:
                ts_short = s["ts"][11:19]
                print(f"{ts_short} stage={stage:18} slot={slot:12} {swarm} workers={workers}/{cap}  nodes[{node_state}]")
                last_state_key = state_key
                last_summary = now

            time.sleep(args.interval)

    print(f"done -> {out_path}")


if __name__ == "__main__":
    main()
