# SQLite WAL Lock Prevention

**Date:** 2026-04-08
**Status:** Draft
**Problem:** Unclean daemon shutdown leaves SQLite WAL/SHM lock files, blocking subsequent startups with `sqlite3.OperationalError: database is locked`.

## Root Cause

The settings store (`settings_store.py`) never checkpoints or closes its SQLite connection on shutdown. The FastAPI lifespan handler has no teardown logic for the DB. When the process is killed (dev.sh port cleanup, Tauri `child.kill()`, crash), the WAL and SHM files remain with stale POSIX advisory locks. The next process that tries to open the DB with a write (`_create_tables` via `executescript`) times out after the default 5 seconds because the stale lock holder is still alive (stuck, not crashed), so the busy timeout can never succeed.

## Industry Pattern (Firefox, VS Code, Home Assistant)

All follow the same three-part pattern:

1. **Startup:** Open with busy timeout, then `PRAGMA wal_checkpoint(TRUNCATE)` to replay any stale WAL from a prior crash.
2. **Shutdown:** `PRAGMA wal_checkpoint(TRUNCATE)` then `close()` to zero the WAL so future crashes leave nothing to replay.
3. **Never delete WAL/SHM files** — deletion while another process holds a connection corrupts the database. Let SQLite's built-in crash recovery handle it.

## Changes

### 1. `src/prep/services/settings_store.py`

**`init()` method (line 62):**

- Make `timeout=10` explicit on `sqlite3.connect()`. The Python default is 5 seconds, which wasn't enough when a stuck process held the lock. 10 seconds gives more headroom for slow startups while still failing fast enough to be useful. (The real fix is preventing the stuck process via shutdown cleanup and dev.sh, but a longer timeout adds resilience.)
- Add `PRAGMA wal_checkpoint(TRUNCATE)` after setting WAL mode. This replays any pending WAL entries from a prior crash into the main DB file and truncates the WAL to zero bytes. Safe to call even when there's nothing to recover.

**`close()` method (line 72):**

- Before calling `self._conn.close()`, execute `PRAGMA wal_checkpoint(TRUNCATE)` wrapped in a try/except (best-effort — if the process is being killed, the checkpoint may not complete, which is fine because the next startup's checkpoint will handle it).

### 2. `src/prep/server.py`

**Lifespan teardown (line 74):**

- After `yield`, import and call `settings.close()`. This is the standard FastAPI pattern for cleaning up resources on shutdown. Currently the comment says "nothing to clean up" — this replaces that.
- No separate signal handler needed — uvicorn already catches SIGTERM/SIGINT and runs the lifespan shutdown. The only signal that bypasses this is SIGKILL (kill -9), which can't be caught by any handler anyway. The startup WAL checkpoint handles that recovery path.

### 3. `scripts/dev.sh`

**Before daemon startup (line 108):**

- Add `pkill -f "prep.cli serve" 2>/dev/null || true` to kill any orphaned daemon processes that aren't listening on a port (the current `kill_port` approach misses processes that failed to bind). This is dev-only belt-and-suspenders — the settings_store fixes are the real solution.

### 4. No Tauri changes needed

Tauri's `child.kill()` calls Rust's `std::process::Child::kill()`, which sends **SIGKILL** (not SIGTERM) on macOS/Linux. SIGKILL cannot be caught, so the lifespan teardown will NOT run when Tauri closes. This is acceptable because the startup `wal_checkpoint(TRUNCATE)` in `init()` recovers any uncommitted WAL entries on next launch. This is the same crash-recovery path that Firefox and VS Code rely on.

**Future improvement (out of scope):** Tauri could send SIGTERM first and fall back to SIGKILL after a timeout, enabling graceful checkpoint. This is not needed for correctness — just a minor optimization to avoid WAL replay on next start.

## What This Does NOT Change

- No WAL/SHM file deletion anywhere. SQLite handles crash recovery.
- No changes to the Rust engine or Tauri main.rs.
- No changes to the VSCode extension's daemon.ts. It spawns the daemon detached (`unref()`), so it intentionally survives VS Code closing. `stopDaemon()` sends SIGTERM via `.kill()`, which triggers uvicorn's graceful shutdown. If VS Code just closes without explicitly stopping the daemon, the daemon keeps running (by design) and the DB stays open — no lock issue.
- No new dependencies.

## Testing

1. Start daemon, kill -9 it, verify restart succeeds (WAL checkpoint on startup recovers).
2. Start daemon, kill -15 (SIGTERM) it, verify WAL/SHM files are zeroed (graceful checkpoint).
3. Run `scripts/dev.sh` twice in a row, verify no lock errors.
4. Verify existing settings persist across unclean restarts (checkpoint replays, not discards).
