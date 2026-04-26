"""Phase 119: recovery only fires when the gate has recently been binding."""
from __future__ import annotations

from unittest.mock import patch

from prep.services.pipeline.scheduler import ComputeSlot, PipelineScheduler


def _cloud_slot(node_id: str = "cloud:ep-test", current_limit: int = 6) -> ComputeSlot:
    return ComputeSlot(
        node_id=node_id,
        max_concurrent=1,
        current_limit=current_limit,
        min_limit=3,
        mode="congestion_avoidance",
    )


def _set_slot(sched: PipelineScheduler, slot: ComputeSlot) -> ComputeSlot:
    sched._slots[slot.node_id] = slot
    return slot


def test_demand_recovery_skipped_when_idle() -> None:
    """If nothing was waiting on the gate, current_limit must NOT grow."""
    sched = PipelineScheduler()
    slot = _set_slot(sched, _cloud_slot(current_limit=6))

    fake_now = 10_000.0
    with patch("prep.services.pipeline.scheduler.time.time", return_value=fake_now):
        sched._maybe_demand_recover(slot)

    assert slot.current_limit == 6


def test_demand_recovery_grows_when_gate_was_binding() -> None:
    """When acquire_request observed the gate binding within the demand
    window, the next acquire after cooldown grows current_limit by 1."""
    sched = PipelineScheduler()
    slot = _set_slot(sched, _cloud_slot(current_limit=6))

    base = 10_000.0
    # Simulate gate having been binding 5 seconds ago.
    slot._gate_binding_until = base + 30   # within window from base
    slot._last_backoff_time = 0.0          # well past cooldown
    slot._last_recovery_time = 0.0         # well past recovery interval

    with patch("prep.services.pipeline.scheduler.time.time", return_value=base):
        sched._maybe_demand_recover(slot)

    assert slot.current_limit == 7


def test_demand_recovery_skipped_during_backoff_cooldown() -> None:
    sched = PipelineScheduler()
    slot = _set_slot(sched, _cloud_slot(current_limit=6))
    base = 10_000.0
    slot._gate_binding_until = base + 30
    slot._last_backoff_time = base - 5   # 5 s ago — still in 30 s cooldown
    slot._last_recovery_time = 0.0

    with patch("prep.services.pipeline.scheduler.time.time", return_value=base):
        sched._maybe_demand_recover(slot)

    assert slot.current_limit == 6


def test_demand_recovery_clamps_at_locked_ceiling() -> None:
    """When a discovered ceiling is locked, recovery cannot grow past it."""
    sched = PipelineScheduler()
    slot = _set_slot(sched, _cloud_slot(current_limit=11))
    slot.discovered_ceiling = 12
    slot.ceiling_locked_until = 99_999_999.0
    base = 10_000.0
    slot._gate_binding_until = base + 30
    slot._last_backoff_time = 0.0
    slot._last_recovery_time = 0.0

    with patch("prep.services.pipeline.scheduler.time.time", return_value=base):
        sched._maybe_demand_recover(slot)
    assert slot.current_limit == 12

    # Second tick — already at ceiling, no further growth.
    slot._last_recovery_time = 0.0
    with patch("prep.services.pipeline.scheduler.time.time", return_value=base):
        sched._maybe_demand_recover(slot)
    assert slot.current_limit == 12


def test_acquire_request_marks_gate_binding(monkeypatch) -> None:
    """Phase 119: acquire_request stamps slot._gate_binding_until when the
    waiter actually had to wait. We test the marking by directly setting
    in_flight to current_limit and checking the stamp."""
    sched = PipelineScheduler()
    slot = _set_slot(sched, _cloud_slot(current_limit=2))
    slot.in_flight_requests = 2  # gate is full

    base = 10_000.0
    monkeypatch.setattr("prep.services.pipeline.scheduler.time.time", lambda: base)
    monkeypatch.setattr(
        "prep.services.pipeline.scheduler.time.monotonic",
        lambda: 0.0,
    )

    # Acquire with timeout=0 (won't actually block, but must observe binding).
    token = sched.acquire_request("cloud:ep-test", timeout=0.0)
    assert token is None  # gate full, returned None

    # _gate_binding_until should have been stamped.
    assert slot._gate_binding_until > base


def test_first_backoff_records_ceiling_with_lock(monkeypatch, tmp_path) -> None:
    """A backoff in congestion_avoidance mode persists a 24 h-locked ceiling."""
    from prep.core import paths as paths_mod
    from prep.services.pipeline import concurrency_store as store_mod

    monkeypatch.setattr(paths_mod, "data_dir", lambda: tmp_path)
    store_mod._store = None

    sched = PipelineScheduler()
    sched.configure_node("cloud:ep-edge", max_concurrent=1)
    slot = sched._slots["cloud:ep-edge"]
    slot.current_limit = 16
    slot.in_flight_requests = 8
    slot.mode = "congestion_avoidance"

    base = 1_000_000.0
    monkeypatch.setattr("prep.services.pipeline.scheduler.time.time", lambda: base)

    sched._record_throughput_for_slot(slot, queue_time_ms=0.0, is_429_or_timeout=True)

    # In-memory state
    assert slot.discovered_ceiling is not None
    assert slot.discovered_ceiling == slot.current_limit
    assert slot.ceiling_locked_until == base + 24 * 3600

    # Persisted state
    record = store_mod.concurrency_store().load_full("cloud:ep-edge", "__default__")
    assert record is not None
    assert record["ceiling"] == slot.discovered_ceiling
    assert record["locked_until"] == slot.ceiling_locked_until
    assert record["edge_observed_at"] == base


def test_jumpstart_backoff_does_not_lock(monkeypatch, tmp_path) -> None:
    """Backoff during jumpstart is exploration, not a confirmed edge — no lock."""
    from prep.core import paths as paths_mod
    from prep.services.pipeline import concurrency_store as store_mod

    monkeypatch.setattr(paths_mod, "data_dir", lambda: tmp_path)
    store_mod._store = None

    sched = PipelineScheduler()
    sched.configure_node("cloud:ep-jump", max_concurrent=1)
    slot = sched._slots["cloud:ep-jump"]
    slot.mode = "jumpstart"
    slot.current_limit = 10
    slot.in_flight_requests = 5

    base = 1_000_000.0
    monkeypatch.setattr("prep.services.pipeline.scheduler.time.time", lambda: base)

    sched._record_throughput_for_slot(slot, queue_time_ms=0.0, is_429_or_timeout=True)

    # The backoff still happens, but no lock is recorded.
    assert slot.discovered_ceiling is None
    assert slot.ceiling_locked_until == 0.0
    record = store_mod.concurrency_store().load_full("cloud:ep-jump", "__default__")
    # save() may have been called for the backoff itself (legacy path) but
    # without a lock — assert the record reflects that.
    if record is not None:
        assert record["locked_until"] == 0.0


def test_locked_ceiling_blocks_growth_above(monkeypatch, tmp_path) -> None:
    """Once locked, congestion_avoidance AI cannot push current_limit past ceiling."""
    from prep.core import paths as paths_mod
    from prep.services.pipeline import concurrency_store as store_mod

    monkeypatch.setattr(paths_mod, "data_dir", lambda: tmp_path)
    store_mod._store = None

    sched = PipelineScheduler()
    sched.configure_node("cloud:ep-cap", max_concurrent=1)
    slot = sched._slots["cloud:ep-cap"]
    slot.mode = "congestion_avoidance"
    slot.current_limit = 9
    slot.discovered_ceiling = 10

    # Patch time so the lock is unambiguously in the future.
    base = 1_000_000.0
    slot.ceiling_locked_until = base + 3600
    monkeypatch.setattr("prep.services.pipeline.scheduler.time.time", lambda: base)

    # 9 successful calls = batch_size complete in CA → would normally grow.
    for _ in range(9):
        sched._record_throughput_for_slot(slot, queue_time_ms=10.0)

    # Allowed to climb to ceiling, not above.
    assert slot.current_limit == 10

    # Another full window — still capped.
    for _ in range(20):
        sched._record_throughput_for_slot(slot, queue_time_ms=10.0)
    assert slot.current_limit == 10


def test_lock_expires_after_ttl(monkeypatch, tmp_path) -> None:
    """After locked_until passes, growth is permitted again (one cautious probe)."""
    from prep.core import paths as paths_mod
    from prep.services.pipeline import concurrency_store as store_mod

    monkeypatch.setattr(paths_mod, "data_dir", lambda: tmp_path)
    store_mod._store = None

    sched = PipelineScheduler()
    sched.configure_node("cloud:ep-ttl", max_concurrent=1)
    slot = sched._slots["cloud:ep-ttl"]
    slot.mode = "congestion_avoidance"
    slot.current_limit = 10
    slot.discovered_ceiling = 10
    slot.ceiling_locked_until = 100.0  # already in the past

    base = 100_000.0  # well after locked_until
    monkeypatch.setattr("prep.services.pipeline.scheduler.time.time", lambda: base)

    for _ in range(10):
        sched._record_throughput_for_slot(slot, queue_time_ms=10.0)
    # One cautious +1 probe permitted.
    assert slot.current_limit == 11


def test_configure_node_hydrates_lock_from_store(monkeypatch, tmp_path) -> None:
    """A daemon restart preserves the (ceiling, locked_until) record."""
    from prep.core import paths as paths_mod
    from prep.services.pipeline import concurrency_store as store_mod

    monkeypatch.setattr(paths_mod, "data_dir", lambda: tmp_path)
    store_mod._store = None
    base = 1_000_000.0
    store_mod.concurrency_store().save_edge(
        "cloud:ep-restart", "__default__",
        ceiling=12, locked_until=base + 1000, edge_observed_at=base - 60,
    )

    sched = PipelineScheduler()
    sched.configure_node("cloud:ep-restart", max_concurrent=1)
    slot = sched._slots["cloud:ep-restart"]

    assert slot.discovered_ceiling == 12
    assert slot.ceiling_locked_until == base + 1000
    # current_limit hydrates to the ceiling (we know it was achievable).
    assert slot.current_limit == 12
    # Mode is congestion_avoidance: we have a known edge, not exploration.
    assert slot.mode == "congestion_avoidance"


def test_configure_node_hydrates_ceiling_only_when_unlocked(monkeypatch, tmp_path) -> None:
    """A pre-Phase-119 record (or jumpstart-grown row) has locked_until=0.

    The slot should still seed current_limit from the persisted ceiling
    (it's a known-good operating point) and switch to congestion_avoidance,
    BUT should NOT hydrate the lock fields — that lets AIMD continue
    probing upward instead of being clamped at a phantom ceiling.
    """
    from prep.core import paths as paths_mod
    from prep.services.pipeline import concurrency_store as store_mod

    monkeypatch.setattr(paths_mod, "data_dir", lambda: tmp_path)
    store_mod._store = None

    # Use the legacy save() path: writes ceiling with locked_until=0.
    store_mod.concurrency_store().save("cloud:ep-legacy", "__default__", ceiling=8)

    sched = PipelineScheduler()
    sched.configure_node("cloud:ep-legacy", max_concurrent=1)
    slot = sched._slots["cloud:ep-legacy"]

    # Ceiling hydrated as starting point, but NO lock applied.
    assert slot.current_limit == 8
    assert slot.mode == "congestion_avoidance"
    assert slot.discovered_ceiling is None
    assert slot.ceiling_locked_until == 0.0


def test_new_cloud_slot_uses_ollama_probe_when_no_persistence(monkeypatch, tmp_path) -> None:
    """First-time configuration of a cloud-via-Ollama slot probes /api/ps."""
    from prep.core import paths as paths_mod
    from prep.services.pipeline import concurrency_store as store_mod
    from prep.services.pipeline import ollama_probe as probe_mod

    monkeypatch.setattr(paths_mod, "data_dir", lambda: tmp_path)
    store_mod._store = None
    monkeypatch.setattr(probe_mod, "probe_ollama_concurrency", lambda host, timeout=1.5: 12)

    sched = PipelineScheduler()
    sched.configure_node("cloud:default_ollama", max_concurrent=1)
    slot = sched._slots["cloud:default_ollama"]

    # Probe seeded the slot at 12 (not the legacy 5 default, not max_concurrent=1).
    assert slot.current_limit == 12
    assert slot.mode == "jumpstart"  # still exploring above the probe
