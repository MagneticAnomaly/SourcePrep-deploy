"""Tests for prep.services.pipeline_telemetry — Phase 124 verbose log."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from prep.services.pipeline_telemetry import (
    iter_events,
    latest_run_events,
    record_event,
)


def test_record_event_writes_jsonl(tmp_path: Path):
    record_event(tmp_path, "test_event", {"k": 1}, phase="124")
    log = tmp_path / "pipeline_telemetry.jsonl"
    assert log.is_file()
    lines = log.read_text().strip().splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["event"] == "test_event"
    assert rec["payload"] == {"k": 1}
    assert rec["phase"] == "124"
    assert "ts" in rec


def test_record_event_appends(tmp_path: Path):
    for i in range(3):
        record_event(tmp_path, "evt", {"i": i})
    lines = (tmp_path / "pipeline_telemetry.jsonl").read_text().strip().splitlines()
    assert len(lines) == 3


def test_record_event_creates_idx_dir(tmp_path: Path):
    new_dir = tmp_path / "fresh"
    assert not new_dir.exists()
    record_event(new_dir, "evt", {"k": 1})
    assert (new_dir / "pipeline_telemetry.jsonl").is_file()


def test_record_event_fail_quiet_on_unserializable_payload(tmp_path: Path):
    """Non-JSON-serializable values use ``default=str`` and don't raise."""
    class Custom:
        def __str__(self):
            return "<custom>"
    record_event(tmp_path, "evt", {"obj": Custom()})
    rec = json.loads((tmp_path / "pipeline_telemetry.jsonl").read_text())
    assert rec["payload"]["obj"] == "<custom>"


def test_iter_events_filters_by_phase(tmp_path: Path):
    record_event(tmp_path, "a", phase="124")
    record_event(tmp_path, "b", phase="123")
    record_event(tmp_path, "c", phase="124")
    out = list(iter_events(tmp_path, phase="124"))
    assert [e["event"] for e in out] == ["a", "c"]


def test_iter_events_filters_by_event_name(tmp_path: Path):
    record_event(tmp_path, "alpha")
    record_event(tmp_path, "beta")
    record_event(tmp_path, "alpha")
    out = list(iter_events(tmp_path, event="alpha"))
    assert len(out) == 2


def test_iter_events_filters_by_stage(tmp_path: Path):
    record_event(tmp_path, "a", stage="atlas")
    record_event(tmp_path, "b", stage="concepts")
    out = list(iter_events(tmp_path, stage="atlas"))
    assert len(out) == 1


def test_iter_events_skips_malformed_lines(tmp_path: Path):
    record_event(tmp_path, "good")
    log = tmp_path / "pipeline_telemetry.jsonl"
    log.write_text(log.read_text() + "{ not json }\n")
    out = list(iter_events(tmp_path))
    assert len(out) == 1
    assert out[0]["event"] == "good"


def test_iter_events_returns_empty_when_log_missing(tmp_path: Path):
    out = list(iter_events(tmp_path))
    assert out == []


def test_latest_run_events_groups_by_run_id(tmp_path: Path):
    record_event(tmp_path, "a", {"run_id": "r1"})
    record_event(tmp_path, "b", {"run_id": "r1"})
    record_event(tmp_path, "c", {"run_id": "r2"})
    record_event(tmp_path, "d", {"run_id": "r2"})
    out = latest_run_events(tmp_path)
    # r2 is the latest run; should return its 2 events
    assert len(out) == 2
    assert {e["event"] for e in out} == {"c", "d"}


def test_latest_run_events_falls_back_to_time_window(tmp_path: Path):
    """No run_id → events within 1h of the most recent are returned."""
    log = tmp_path / "pipeline_telemetry.jsonl"
    now = datetime.now(timezone.utc)
    old = now - timedelta(hours=3)
    recent = now - timedelta(minutes=10)
    lines = [
        json.dumps({"ts": old.isoformat(), "event": "old"}),
        json.dumps({"ts": recent.isoformat(), "event": "fresh1"}),
        json.dumps({"ts": now.isoformat(), "event": "fresh2"}),
    ]
    log.write_text("\n".join(lines) + "\n")
    out = latest_run_events(tmp_path)
    events = [e["event"] for e in out]
    assert "fresh1" in events and "fresh2" in events
    assert "old" not in events
