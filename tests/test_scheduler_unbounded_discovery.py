"""Phase 82 completion: cloud AIMD is unbounded; local remains VRAM-capped."""
from __future__ import annotations

from prep.services.pipeline.scheduler import (
    ComputeSlot,
    PipelineScheduler,
)


def _cloud_slot(node_id: str = "cloud:ep-test", seed: int = 5) -> ComputeSlot:
    return ComputeSlot(
        node_id=node_id,
        max_concurrent=seed,
        current_limit=seed,
        min_limit=3,
    )


def _local_slot(node_id: str = "local:ep-test", max_c: int = 1) -> ComputeSlot:
    return ComputeSlot(
        node_id=node_id,
        max_concurrent=max_c,
        min_limit=1,
    )


def test_cloud_dynamic_capacity_ignores_max_concurrent() -> None:
    slot = _cloud_slot()
    slot.current_limit = 40  # AIMD discovered a higher ceiling than the seed
    assert slot.dynamic_capacity == 40


def test_local_dynamic_capacity_still_clamps_at_max_concurrent() -> None:
    """Local slots have a real hardware ceiling (VRAM). Must still clamp."""
    slot = _local_slot(max_c=2)
    slot.current_limit = 10  # should be impossible but verify clamp
    assert slot.dynamic_capacity == 2


def test_cloud_aimd_doubling_past_max_concurrent() -> None:
    """Cloud slot in jumpstart mode should double past its initial max_concurrent."""
    sched = PipelineScheduler()
    slot = _cloud_slot(seed=5)
    slot.mode = "jumpstart"
    sched._slots["cloud:ep-test"] = slot

    # Simulate 5 successful calls (batch_size = current_limit = 5) to trigger
    # a doubling step in jumpstart mode.
    for _ in range(5):
        sched._record_throughput_for_slot(slot, queue_time_ms=100.0)

    assert slot.current_limit == 10, (
        f"Expected doubling from 5→10, got current_limit={slot.current_limit}"
    )

    # Trigger another 10 successes — should double again (uncapped past
    # original max_concurrent=5). Use a loose >=20 assertion so this stays
    # robust if the batch_size formula is tweaked later.
    for _ in range(10):
        sched._record_throughput_for_slot(slot, queue_time_ms=100.0)

    assert slot.current_limit >= 20, (
        f"Expected second doubling to reach >=20 (past original max_concurrent=5), "
        f"got current_limit={slot.current_limit}"
    )


def test_cloud_congestion_avoidance_grows_past_max_concurrent() -> None:
    """Cloud slot's +1 additive-increase branch must also be uncapped.

    The jumpstart doubling path is covered above; this exercises the
    congestion_avoidance branch (`current_limit + 1`) to confirm the cloud
    carve-out applies there too.
    """
    sched = PipelineScheduler()
    slot = _cloud_slot(seed=5)
    slot.mode = "congestion_avoidance"
    sched._slots["cloud:ep-test"] = slot

    # With current_limit=5, batch_size=5 triggers the first +1 (→ 6).
    # With current_limit=6, batch_size=6 triggers the next +1 (→ 7), etc.
    # 60 successes is enough for multiple +1 increases past max_concurrent=5.
    for _ in range(60):
        sched._record_throughput_for_slot(slot, queue_time_ms=100.0)

    assert slot.mode == "congestion_avoidance", (
        f"Mode unexpectedly changed to {slot.mode!r}"
    )
    assert slot.current_limit > 5, (
        f"Cloud congestion_avoidance +1 should grow past max_concurrent=5, "
        f"got current_limit={slot.current_limit}"
    )


def test_local_aimd_does_not_exceed_max_concurrent() -> None:
    """Local VRAM ceiling must be respected — no doubling past max_concurrent."""
    sched = PipelineScheduler()
    slot = _local_slot(max_c=1)
    slot.mode = "congestion_avoidance"
    sched._slots["local:ep-test"] = slot

    for _ in range(50):
        sched._record_throughput_for_slot(slot, queue_time_ms=10.0)

    assert slot.current_limit == 1, (
        f"Local slot exceeded VRAM ceiling: current_limit={slot.current_limit}"
    )


def test_new_cloud_slot_seeds_at_five_jumpstart() -> None:
    """Phase 82 spec: cloud slots seed at current_limit=5, mode=jumpstart."""
    sched = PipelineScheduler()
    sched.configure_node("cloud:ep-new", max_concurrent=1)
    slot = sched._slots["cloud:ep-new"]
    assert slot.current_limit == 5
    assert slot.mode == "jumpstart"


def test_new_local_slot_keeps_max_concurrent_as_limit() -> None:
    """Local slots don't need discovery — VRAM ceiling is a hard known value."""
    sched = PipelineScheduler()
    sched.configure_node("local:ep-new", max_concurrent=2)
    slot = sched._slots["local:ep-new"]
    assert slot.current_limit == 2
    assert slot.mode in ("congestion_avoidance", "jumpstart")


def test_reconfigure_cloud_slot_preserves_discovered_limit() -> None:
    """Calling configure_node again on an existing cloud slot should NOT
    reset current_limit — the scheduler has already discovered a real
    ceiling and resetting to 5 would throw that away on a UI slider edit."""
    sched = PipelineScheduler()
    sched.configure_node("cloud:ep-a", max_concurrent=1)
    slot = sched._slots["cloud:ep-a"]
    slot.current_limit = 40
    slot.mode = "congestion_avoidance"

    sched.configure_node("cloud:ep-a", max_concurrent=1)

    assert slot.current_limit == 40
    assert slot.mode == "congestion_avoidance"


def test_new_cloud_slot_hydrates_from_store(monkeypatch, tmp_path) -> None:
    """configure_node reads the persisted ceiling and uses it as current_limit."""
    from prep.core import paths as paths_mod
    monkeypatch.setattr(paths_mod, "data_dir", lambda: tmp_path)
    from prep.services.pipeline import concurrency_store as mod
    monkeypatch.setattr(mod, "_store", None)

    # Persist a ceiling BEFORE creating the slot.
    store = mod.concurrency_store()
    store.save("cloud:ep-persisted", "__default__", ceiling=40)

    sched = PipelineScheduler()
    sched.configure_node("cloud:ep-persisted", max_concurrent=1)
    slot = sched._slots["cloud:ep-persisted"]

    assert slot.current_limit == 40, (
        f"Expected hydrated ceiling=40, got current_limit={slot.current_limit}"
    )
    # Hydrating to a known ceiling means we're NOT in jumpstart —
    # doubling from 40 would overshoot. Start in congestion_avoidance
    # so +1 additive increase probes gently above the ceiling.
    assert slot.mode == "congestion_avoidance"
    assert slot.success_streak == 0


def test_aimd_backoff_writes_new_ceiling(monkeypatch, tmp_path) -> None:
    from prep.core import paths as paths_mod
    monkeypatch.setattr(paths_mod, "data_dir", lambda: tmp_path)
    from prep.services.pipeline import concurrency_store as mod
    monkeypatch.setattr(mod, "_store", None)

    sched = PipelineScheduler()
    sched.configure_node("cloud:ep-backoff", max_concurrent=1)
    slot = sched._slots["cloud:ep-backoff"]
    slot.current_limit = 80
    slot.mode = "congestion_avoidance"

    # Trigger a backoff via explicit rejection signal (429/5xx/timeout).
    sched._record_throughput_for_slot(slot, is_429_or_timeout=True)

    persisted = mod.concurrency_store().load("cloud:ep-backoff", "__default__")
    assert persisted is not None and persisted < 80, (
        f"Expected backoff to persist a reduced ceiling, got {persisted}"
    )
    assert persisted == slot.current_limit


def test_aimd_doubling_writes_new_ceiling(monkeypatch, tmp_path) -> None:
    from prep.core import paths as paths_mod
    monkeypatch.setattr(paths_mod, "data_dir", lambda: tmp_path)
    from prep.services.pipeline import concurrency_store as mod
    monkeypatch.setattr(mod, "_store", None)

    sched = PipelineScheduler()
    sched.configure_node("cloud:ep-grow", max_concurrent=1)
    slot = sched._slots["cloud:ep-grow"]

    # Force a jumpstart doubling step.
    for _ in range(5):
        sched._record_throughput_for_slot(slot, queue_time_ms=50.0)

    persisted = mod.concurrency_store().load("cloud:ep-grow", "__default__")
    assert persisted == 10, (
        f"Expected jumpstart doubling (5→10) to persist ceiling=10, got {persisted}"
    )


def test_rate_limit_header_clamp_persists(monkeypatch, tmp_path) -> None:
    """Rate-limit header clamp is an authoritative ceiling signal from the
    provider — must persist across restart (most important persist site)."""
    from prep.core import paths as paths_mod
    monkeypatch.setattr(paths_mod, "data_dir", lambda: tmp_path)
    from prep.services.pipeline import concurrency_store as mod
    monkeypatch.setattr(mod, "_store", None)

    sched = PipelineScheduler()
    sched.configure_node("cloud:ep-rl", max_concurrent=50)
    slot = sched._slots["cloud:ep-rl"]
    # Simulate scheduler has already grown past the seed
    slot.current_limit = 50
    slot.max_concurrent = 50

    # Provider returns rate_limit_remaining=10 → safe_limit=8, clamp both.
    sched._record_throughput_for_slot(
        slot, queue_time_ms=50.0, rate_limit_remaining=10,
    )

    assert slot.current_limit == 8
    persisted = mod.concurrency_store().load("cloud:ep-rl", "__default__")
    assert persisted == 8


def test_local_slot_does_not_persist(monkeypatch, tmp_path) -> None:
    """Local slots have a known hardware ceiling — no discovery, no persist."""
    from prep.core import paths as paths_mod
    monkeypatch.setattr(paths_mod, "data_dir", lambda: tmp_path)
    from prep.services.pipeline import concurrency_store as mod
    monkeypatch.setattr(mod, "_store", None)

    sched = PipelineScheduler()
    sched.configure_node("local:ep-gpu", max_concurrent=2)
    slot = sched._slots["local:ep-gpu"]

    for _ in range(10):
        sched._record_throughput_for_slot(slot, queue_time_ms=50.0)
    sched._record_throughput_for_slot(slot, is_429_or_timeout=True)

    persisted = mod.concurrency_store().load("local:ep-gpu", "__default__")
    assert persisted is None
