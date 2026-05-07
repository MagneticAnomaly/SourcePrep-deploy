"""Lightweight structured event log for pipeline observability.

Workers and synthesizers emit ``record_event`` calls at key decision
points so a post-run audit can confirm WHAT actually fired, with rich
payloads, instead of inferring from artifact mtimes.

Append-only JSONL at ``<idx_dir>/pipeline_telemetry.jsonl``. Each
line is a single JSON object:

    {
        "ts": "2026-05-02T08:50:00.123456+00:00",
        "event": "concepts_synthesis_failed",  // free-form event name
        "stage": "concepts",                   // optional stage tag (StageId.value)
        "project_id": "...",                   // optional
        "payload": { ... }                     // rich event-specific data
    }

The file is best-effort and capped at ``MAX_BYTES`` (default 4 MiB).
When the cap is hit the file is renamed to
``pipeline_telemetry.jsonl.prev`` and a fresh file is started — so
queries always have at least the last ~4 MiB of recent activity.

Read patterns:

    from prep.services.pipeline_telemetry import iter_events
    for ev in iter_events(idx_dir, stage="concepts"):
        if ev["event"] == "synthesis_failed":
            print(ev["payload"])

Designed to be import-cheap, fail-quiet (telemetry must never break
a pipeline run), and stdlib-only.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

logger = logging.getLogger(__name__)

_FILENAME = "pipeline_telemetry.jsonl"
_PREV_FILENAME = "pipeline_telemetry.jsonl.prev"
MAX_BYTES = 4 * 1024 * 1024  # 4 MiB rotate threshold


def _path(idx_dir: Path | str) -> Path:
    return Path(idx_dir) / _FILENAME


def _rotate_if_needed(p: Path) -> None:
    try:
        if p.is_file() and p.stat().st_size > MAX_BYTES:
            prev = p.parent / _PREV_FILENAME
            if prev.exists():
                prev.unlink()
            p.rename(prev)
    except Exception as e:
        # Telemetry rotation must never raise
        logger.debug("telemetry rotate skipped: %s", e)


def record_event(
    idx_dir: Path | str,
    event: str,
    payload: Optional[dict[str, Any]] = None,
    *,
    phase: Optional[str] = None,  # accepted but no longer persisted; see note
    stage: Optional[str] = None,
    project_id: Optional[str] = None,
) -> None:
    """Append one event to the telemetry log. Fail-quiet.

    Args:
        idx_dir: Project index directory (where the log lives).
        event: Free-form event name. Recommended: snake_case verb,
            e.g. ``"md_links_extracted"`` or ``"synthesis_failed"``.
        payload: Event-specific data. Must be JSON-serializable.
        phase: Deprecated. Accepted for back-compat with existing call
            sites but not written to the log — internal phase numbers
            were leaking dev chronology into user-facing telemetry. Use
            ``stage`` for the meaningful taxonomy.
        stage: Optional StageId value (``"atlas"``, ``"concepts"``).
        project_id: Optional project identifier.
    """
    del phase  # accepted-but-ignored; see docstring
    try:
        idx = Path(idx_dir)
        idx.mkdir(parents=True, exist_ok=True)
        p = _path(idx)
        _rotate_if_needed(p)

        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": event,
        }
        if stage is not None:
            record["stage"] = stage
        if project_id is not None:
            record["project_id"] = project_id
        if payload:
            record["payload"] = payload

        with p.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, default=str) + "\n")
    except Exception as e:
        # Never break a pipeline run because of telemetry.
        logger.debug("record_event failed (non-fatal): %s", e)


def iter_events(
    idx_dir: Path | str,
    *,
    phase: Optional[str] = None,  # deprecated; see record_event
    event: Optional[str] = None,
    stage: Optional[str] = None,
    include_prev: bool = False,
) -> Iterable[dict[str, Any]]:
    """Yield events from the telemetry log. Filters are AND'd.

    Args:
        idx_dir: Project index directory.
        phase: Deprecated. Phase tags were removed from the on-disk
            schema; this filter still works for any legacy log lines
            that carry a ``phase`` field, but new lines never will.
        event: Filter to events with this ``event`` name (exact match).
        stage: Filter to events with this ``stage`` tag.
        include_prev: If True, also read the rotated ``.prev`` log.
    """
    idx = Path(idx_dir)
    files: list[Path] = []
    if include_prev:
        prev = idx / _PREV_FILENAME
        if prev.is_file():
            files.append(prev)
    cur = _path(idx)
    if cur.is_file():
        files.append(cur)
    for fp in files:
        try:
            with fp.open(encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        ev = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if phase is not None and ev.get("phase") != phase:
                        continue
                    if event is not None and ev.get("event") != event:
                        continue
                    if stage is not None and ev.get("stage") != stage:
                        continue
                    yield ev
        except Exception as e:
            logger.debug("iter_events skipped %s: %s", fp, e)


def latest_run_events(
    idx_dir: Path | str,
    *,
    phase: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Return events from the most-recent pipeline run.

    Heuristic: events are grouped by ``run_id`` if present in the
    payload. Otherwise we return all events whose timestamp is within
    1 hour of the most recent event in the log — a coarse but useful
    approximation when ``run_id`` plumbing isn't there yet.
    """
    events = list(iter_events(idx_dir, phase=phase))
    if not events:
        return []

    # Group by run_id if available
    by_run: dict[str, list[dict]] = {}
    for ev in events:
        run_id = (ev.get("payload") or {}).get("run_id")
        if run_id:
            by_run.setdefault(run_id, []).append(ev)
    if by_run:
        # Pick the run with the latest event timestamp
        latest = max(
            by_run.items(),
            key=lambda kv: max(e.get("ts", "") for e in kv[1]),
        )
        return latest[1]

    # Fallback: 1-hour window around the most recent event
    timestamps = [ev.get("ts", "") for ev in events if ev.get("ts")]
    if not timestamps:
        return events
    latest_ts = max(timestamps)
    try:
        latest_dt = datetime.fromisoformat(latest_ts.replace("Z", "+00:00"))
    except Exception:
        return events
    cutoff = latest_dt.timestamp() - 3600  # 1 hour window
    out: list[dict[str, Any]] = []
    for ev in events:
        try:
            t = datetime.fromisoformat(
                ev.get("ts", "").replace("Z", "+00:00"),
            ).timestamp()
            if t >= cutoff:
                out.append(ev)
        except Exception:
            continue
    return out
