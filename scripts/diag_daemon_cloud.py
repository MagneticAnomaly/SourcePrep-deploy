#!/usr/bin/env python3
"""
Diagnostic: Test cloud model LLM calls through the RUNNING DAEMON.

This is the critical test: does requests.post() hang when called from
inside the daemon process (FastAPI sync route → uvicorn worker thread)?

Test 1: Standalone (same machine, same model) — baseline
Test 2: Via daemon's /api/llm/proxy/test-model endpoint — tests the route
Test 3: Inject a direct LLM call into the daemon via a custom endpoint

Usage:
    Ensure daemon is running on :8400 and Ollama is running.
    .venv/bin/python scripts/diag_daemon_cloud.py
"""
import json
import os
import sys
import time
import threading
import requests

DAEMON_URL = "http://localhost:8400"
OLLAMA_URL = "http://localhost:11434"
CLOUD_MODEL = "kimi-k2.5:cloud"
LOCAL_MODEL = "qwen3:8b"


def test_standalone_cloud():
    """Test 1: Direct call from this script process (baseline)."""
    print("\n=== TEST 1: Standalone cloud call (baseline) ===")
    t0 = time.monotonic()
    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": CLOUD_MODEL,
                "prompt": "Say hello in JSON: {\"greeting\": \"...\"}",
                "stream": False,
                "think": False,
                "options": {"num_predict": 100, "temperature": 0.1},
            },
            timeout=(30, 60),
            stream=False,
        )
        elapsed = time.monotonic() - t0
        print(f"  Status: {resp.status_code}")
        print(f"  Elapsed: {elapsed:.1f}s")
        print(f"  Transfer-Encoding: {resp.headers.get('Transfer-Encoding', 'none')}")
        print(f"  Content-Length: {resp.headers.get('Content-Length', 'none')}")
        print(f"  Body size: {len(resp.content)} bytes")
        # Parse response
        for line in resp.text.splitlines():
            if not line.strip():
                continue
            try:
                chunk = json.loads(line)
                if chunk.get("done"):
                    print(f"  eval_count: {chunk.get('eval_count', '?')}")
                    break
            except json.JSONDecodeError:
                pass
        print(f"  RESULT: OK")
        return True
    except Exception as e:
        elapsed = time.monotonic() - t0
        print(f"  FAILED after {elapsed:.1f}s: {e}")
        return False


def test_daemon_test_model_cloud():
    """Test 2: Call daemon's test-model endpoint with cloud model."""
    print(f"\n=== TEST 2: Daemon /api/llm/proxy/test-model (cloud: {CLOUD_MODEL}) ===")
    t0 = time.monotonic()
    try:
        resp = requests.post(
            f"{DAEMON_URL}/api/llm/proxy/test-model",
            json={
                "url": OLLAMA_URL,
                "provider": "ollama",
                "model": CLOUD_MODEL,
                "kind": "generate",
            },
            timeout=90,
        )
        elapsed = time.monotonic() - t0
        print(f"  Status: {resp.status_code}")
        print(f"  Elapsed: {elapsed:.1f}s")
        try:
            data = resp.json()
            print(f"  Response: {json.dumps(data, indent=2)[:500]}")
        except Exception:
            print(f"  Body: {resp.text[:200]}")
        print(f"  RESULT: {'OK' if resp.status_code == 200 else 'FAILED'}")
        return resp.status_code == 200
    except requests.Timeout:
        elapsed = time.monotonic() - t0
        print(f"  TIMED OUT after {elapsed:.1f}s — DAEMON HANG CONFIRMED")
        return False
    except Exception as e:
        elapsed = time.monotonic() - t0
        print(f"  FAILED after {elapsed:.1f}s: {e}")
        return False


def test_daemon_test_model_local():
    """Test 3: Call daemon's test-model endpoint with local model."""
    print(f"\n=== TEST 3: Daemon /api/llm/proxy/test-model (local: {LOCAL_MODEL}) ===")
    t0 = time.monotonic()
    try:
        resp = requests.post(
            f"{DAEMON_URL}/api/llm/proxy/test-model",
            json={
                "url": OLLAMA_URL,
                "provider": "ollama",
                "model": LOCAL_MODEL,
                "kind": "generate",
            },
            timeout=90,
        )
        elapsed = time.monotonic() - t0
        print(f"  Status: {resp.status_code}")
        print(f"  Elapsed: {elapsed:.1f}s")
        try:
            data = resp.json()
            print(f"  Response: {json.dumps(data, indent=2)[:500]}")
        except Exception:
            print(f"  Body: {resp.text[:200]}")
        print(f"  RESULT: {'OK' if resp.status_code == 200 else 'FAILED'}")
        return resp.status_code == 200
    except requests.Timeout:
        elapsed = time.monotonic() - t0
        print(f"  TIMED OUT after {elapsed:.1f}s")
        return False
    except Exception as e:
        elapsed = time.monotonic() - t0
        print(f"  FAILED after {elapsed:.1f}s: {e}")
        return False


def test_daemon_thread_count():
    """Test 4: Check daemon thread count and Ollama connections."""
    print("\n=== TEST 4: Daemon process state ===")
    import subprocess
    # Find daemon PID
    result = subprocess.run(
        ["pgrep", "-f", "prep.cli serve"],
        capture_output=True, text=True,
    )
    pids = result.stdout.strip().split()
    if not pids:
        print("  Daemon not running!")
        return
    pid = pids[0]
    print(f"  Daemon PID: {pid}")

    # Thread count
    result = subprocess.run(
        ["ps", "-M", "-p", pid],
        capture_output=True, text=True,
    )
    thread_count = len(result.stdout.strip().split("\n")) - 1
    print(f"  Thread count: {thread_count}")

    # Ollama connections
    result = subprocess.run(
        ["lsof", "-a", "-p", pid, "-i", ":11434", "-P"],
        capture_output=True, text=True,
    )
    lines = [l for l in result.stdout.strip().split("\n") if l and "COMMAND" not in l]
    print(f"  Ollama connections: {len(lines)}")
    for l in lines:
        print(f"    {l}")

    # LISTEN socket
    result = subprocess.run(
        ["lsof", "-a", "-p", pid, "-i", ":8400", "-P"],
        capture_output=True, text=True,
    )
    has_listen = "LISTEN" in result.stdout
    print(f"  Has LISTEN socket on :8400: {has_listen}")


def main():
    print("=" * 60)
    print("DAEMON CLOUD MODEL HANG DIAGNOSTIC")
    print("=" * 60)

    # Preflight
    print(f"\nDaemon: {DAEMON_URL}")
    print(f"Ollama: {OLLAMA_URL}")
    print(f"Cloud model: {CLOUD_MODEL}")
    print(f"Local model: {LOCAL_MODEL}")

    test_daemon_thread_count()
    test_standalone_cloud()
    test_daemon_test_model_local()
    test_daemon_test_model_cloud()
    test_daemon_thread_count()

    print("\n" + "=" * 60)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
