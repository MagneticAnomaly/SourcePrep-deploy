# Phase 92: SQLite WAL Lock Prevention

**Date:** 2026-04-08
**Status:** Implemented
**Scope:** `src/codrag/services/settings_store.py`, `src/codrag/server.py`, `scripts/dev.sh`, and 6 sibling SQLite stores

---

## Problem Statement

After an unclean daemon shutdown (crash, SIGKILL, dev.sh port cleanup), the SQLite settings database (`codrag_settings.db`) was left with stale WAL/SHM lock files. The next daemon startup failed with `sqlite3.OperationalError: database is locked`, requiring manual intervention to kill orphaned processes and clean up lock files.

The failure chain:
1. Process A starts, opens `codrag_settings.db` with WAL mode
2. Process A is killed (SIGKILL, crash, or dev.sh `kill_port`)
3. WAL/SHM files remain; if A is stuck (not dead), its POSIX lock persists
4. `dev.sh` starts Process B, which can't write to the DB (lock held by A)
5. B hangs on startup, never binds port 8400
6. Dashboard polls `/health` and gets `ECONNREFUSED` indefinitely
7. Running `dev.sh` again can't find B via `kill_port` (B never bound a port)

## Root Cause Analysis

Three independent gaps:

1. **No WAL checkpoint on startup or shutdown.** The settings store opened SQLite in WAL mode but never checkpointed. After a crash, the WAL contained uncommitted data. After graceful shutdown, the WAL was never truncated, leaving stale state for the next startup.

2. **No store cleanup on server shutdown.** The FastAPI lifespan handler had no teardown logic — `settings.close()` was never called. Six stores (settings, journal, history, telemetry, observations, concepts) all held open connections to the same DB file.

3. **dev.sh only killed processes by port.** A daemon that failed before binding port 8400 was invisible to `lsof -ti :8400`, so `kill_port` couldn't find it.

## Industry Research

Researched how production apps handle SQLite WAL locking:

| App | Pattern |
|-----|---------|
| **Firefox** | Checkpoints on idle, `TRUNCATE` on shutdown, relies on SQLite auto-recovery for crashes |
| **VS Code** | `state.vscdb` with WAL mode, checkpoints on graceful exit, accepts stale WAL on crash |
| **Home Assistant** | `busy_timeout` of 30s, single-writer model, SQLite auto-recovers WAL on open |
| **Syncthing** | Opens with busy timeout, relies on SQLite crash recovery |

All follow the same three-part pattern:
1. **Startup:** Open with busy timeout, `PRAGMA wal_checkpoint(TRUNCATE)` to recover stale WAL
2. **Shutdown:** `PRAGMA wal_checkpoint(TRUNCATE)` then `close()` to zero the WAL
3. **Never delete WAL/SHM files** — let SQLite handle crash recovery

Key insight: Python's `sqlite3.connect()` default timeout is 5 seconds (not zero). The issue wasn't timeout length — it was a stuck process holding the lock indefinitely. The timeout was raised to 10s as resilience headroom.

## Changes

### 1. `src/codrag/services/settings_store.py`

**`init()` method:**
- Added `timeout=10` to `sqlite3.connect()` (up from default 5s)
- Added `PRAGMA wal_checkpoint(TRUNCATE)` after WAL mode — recovers stale WAL from prior crashes

**`close()` method:**
- Added `PRAGMA wal_checkpoint(TRUNCATE)` before `conn.close()`, wrapped in try/except for best-effort on shutdown

### 2. All sibling stores (6 files)

Added `timeout=10` to `sqlite3.connect()` in:
- `observation_store.py`
- `concept_store.py`
- `pipeline_journal.py`
- `pipeline_history.py`
- `token_telemetry.py`
- `antibody_store.py`

These stores share the same `codrag_settings.db` file. Without the timeout, any store could fail with "database is locked" during contended startup.

### 3. `src/codrag/server.py`

**Lifespan teardown:** Close all 6 SQLite stores on shutdown. The settings store is closed last so its `wal_checkpoint(TRUNCATE)` runs after all other connections are released — SQLite requires no active connections for WAL truncation to succeed.

### 4. `scripts/dev.sh`

Added `pkill -f "codrag.cli serve"` and `pkill -f "codrag serve"` before daemon startup. This catches orphaned daemon processes that aren't listening on a port (invisible to `kill_port`).

### 5. No Tauri or VSCode changes

Tauri's `child.kill()` sends SIGKILL (Rust `std::process::Child::kill()`). The lifespan teardown won't run, but the startup WAL checkpoint handles crash recovery. VSCode's daemon manager spawns detached processes that survive VS Code closing — no lock issue.

## Verification

| Test | Result |
|------|--------|
| Crash recovery (SIGKILL, restart) | Daemon recovers via WAL checkpoint on init |
| Graceful shutdown (SIGTERM) | WAL truncated to 0 bytes, "All SQLite stores closed" in log |
| `scripts/dev.sh` consecutive runs | No lock errors |
| `tests/test_settings_store.py` | 30/30 pass (3 new WAL-specific tests) |
| `tests/test_observation_store.py` | 34/34 pass |
| Data persistence across crashes | Settings survive unclean restart (WAL replay, not discard) |

## Commits

```
0591449d fix(settings): add WAL checkpoint on init/close to prevent stale locks
98bc7fa8 fix(server): close settings store on lifespan shutdown
82d67fc5 fix(dev): kill orphaned codrag processes by name before startup
0960d372 fix(server): close all SQLite stores on lifespan shutdown
9df9f480 fix(stores): add timeout=10 to all SQLite stores sharing settings DB
```

## Future Considerations

- **Tauri graceful shutdown:** Tauri could send SIGTERM before SIGKILL (with timeout fallback) to enable graceful checkpoint. Not needed for correctness — just avoids WAL replay on next start.
- **Single writer connection:** All 7 stores open independent connections to the same DB. A shared connection pool would simplify lifecycle management and eliminate multi-connection WAL contention. Out of scope for this fix.
