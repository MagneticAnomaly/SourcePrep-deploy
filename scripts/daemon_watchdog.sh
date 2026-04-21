#!/bin/bash
# daemon_watchdog.sh — respawn the Prep daemon if it exits, logging every
# start/exit with timestamp + exit code. Captures stdout+stderr per-run so
# the traceback that killed the previous run is available after the restart.
#
# Usage (from dev.sh or standalone):
#   PROJECT_ROOT=/path/to/Prep DAEMON_PORT=8400 scripts/daemon_watchdog.sh
#
# Stops: Ctrl-C, SIGTERM, or touch /tmp/prep_daemon_stop

set -u
PROJECT_ROOT="${PROJECT_ROOT:-/Volumes/4TB-BAD/HumanAI/Prep}"
DAEMON_PORT="${DAEMON_PORT:-8400}"
LOG_DIR="${LOG_DIR:-/tmp/prep_daemon_logs}"
STOP_FILE="/tmp/prep_daemon_stop"
HISTORY_LOG="$LOG_DIR/history.log"

mkdir -p "$LOG_DIR"
rm -f "$STOP_FILE"

STOP_REQUESTED=0
cleanup() {
  STOP_REQUESTED=1
  echo "[watchdog] shutting down, killing child PID ${CHILD_PID:-?}" | tee -a "$HISTORY_LOG"
  if [ -n "${CHILD_PID:-}" ]; then
    kill "$CHILD_PID" 2>/dev/null
    # Kill everything the watchdog spawned (daemon subshell + tee)
    pkill -P $$ 2>/dev/null
  fi
  exit 0
}
# F-81: Trap HUP too (parent dev.sh teardown sends SIGHUP to children)
trap cleanup INT TERM HUP

# Crash-loop guard: if the daemon dies within MIN_UPTIME seconds, we wait
# COOLDOWN before trying again, and bail after MAX_FAST_CRASHES consecutive
# fast crashes so we don't thrash a broken build.
MIN_UPTIME=30
COOLDOWN=5
MAX_FAST_CRASHES=5
fast_crashes=0

echo "[watchdog] started pid=$$ port=$DAEMON_PORT log_dir=$LOG_DIR" | tee -a "$HISTORY_LOG"

while true; do
  if [ -f "$STOP_FILE" ]; then
    echo "[watchdog] stop file present, exiting" | tee -a "$HISTORY_LOG"
    rm -f "$STOP_FILE"
    exit 0
  fi

  ts=$(date -u +%Y%m%d_%H%M%S)
  run_log="$LOG_DIR/daemon_${ts}.log"
  started_at=$(date -u +%s)
  echo "[watchdog] $(date -u +%Y-%m-%dT%H:%M:%SZ) spawning daemon → $run_log" | tee -a "$HISTORY_LOG"

  # Launch in its own process group so we can send signals cleanly.
  # Tee to both the per-run log and our own stdout for live monitoring.
  (
    cd "$PROJECT_ROOT"
    PYTHONPATH="$PROJECT_ROOT/src" exec python3.11 -m prep.cli serve --port "$DAEMON_PORT" 2>&1
  ) | tee "$run_log" &
  CHILD_PID=$!

  wait "$CHILD_PID"
  exit_code=$?
  ended_at=$(date -u +%s)
  uptime=$((ended_at - started_at))

  # If cleanup was triggered or stop file appeared while we were waiting,
  # don't respawn — exit cleanly.
  if [ "$STOP_REQUESTED" -eq 1 ] || [ -f "$STOP_FILE" ]; then
    echo "[watchdog] stop requested, not respawning" | tee -a "$HISTORY_LOG"
    rm -f "$STOP_FILE"
    exit 0
  fi

  tail_n=40
  tail_summary=$(tail -n "$tail_n" "$run_log" 2>/dev/null | sed 's/^/    /')

  {
    echo "[watchdog] $(date -u +%Y-%m-%dT%H:%M:%SZ) daemon exited code=$exit_code uptime=${uptime}s"
    echo "[watchdog] last ${tail_n} lines of $run_log:"
    printf '%s\n' "$tail_summary"
    echo "[watchdog] -----"
  } | tee -a "$HISTORY_LOG"

  if [ "$uptime" -lt "$MIN_UPTIME" ]; then
    fast_crashes=$((fast_crashes + 1))
    echo "[watchdog] fast crash #$fast_crashes (uptime=${uptime}s < ${MIN_UPTIME}s)" | tee -a "$HISTORY_LOG"
    if [ "$fast_crashes" -ge "$MAX_FAST_CRASHES" ]; then
      echo "[watchdog] $MAX_FAST_CRASHES fast crashes in a row — stopping to avoid thrash. Fix the issue and restart manually." | tee -a "$HISTORY_LOG"
      exit 1
    fi
    sleep "$COOLDOWN"
  else
    fast_crashes=0
    sleep 1
  fi
done
