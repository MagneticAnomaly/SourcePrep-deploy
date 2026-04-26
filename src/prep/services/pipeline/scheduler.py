"""
Pipeline Scheduler — Phase 45D
================================

Manages concurrent pipeline runs across multiple projects, respecting
per-node concurrency limits and queue types.

Key concepts:
  - Each LLM stage competes for slots on a compute node
  - Embedding stages (NativeEmbedder) run independently — no slot needed
  - Rust stages are CPU-only — always allowed
  - When a node is full, the pipeline enters QUEUED state
  - When a slot frees up, the next queued pipeline resumes

Usage:
    from prep.services.pipeline.scheduler import pipeline_scheduler
    
    # Before starting an LLM stage:
    if pipeline_scheduler.can_start(project_id, stage):
        pipeline_scheduler.acquire(project_id, stage)
        # ... run the stage ...
    else:
        pipeline_scheduler.enqueue(project_id, stage)
    
    # After a stage completes:
    pipeline_scheduler.release(project_id, stage)
    next_waiting = pipeline_scheduler.dequeue_next()
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Callable, Deque, Dict, List, Literal, Optional, Set, Tuple

# Priority levels for the star system (three-tier)
PriorityLevel = Literal["none", "boost", "exclusive"]

from .stages import QueueType, STAGE_QUEUE_TYPE, StageId
from prep.services.pipeline import ollama_probe
from prep.services.pipeline.concurrency_store import concurrency_store

logger = logging.getLogger(__name__)

# Stages that can use swarm orchestration (coordinator → fan-out → synthesis).
# Shared constant — imported by queue.py and llm.py routers to avoid duplication.
# Phase 96F: concepts and audit join the swarm-capable set so the
# orchestrator opens a swarm window for them.  Their workers route
# internally to a SwarmOrchestrator-based path when the model supports
# swarm and there is enough work to fan out, falling back to sequential
# otherwise.
SWARM_CAPABLE_STAGES: frozenset = frozenset({
    "group_reasoning", "clustering", "atlas",
    "concepts", "audit",
})


def is_swarm_active_for_stage(stage: str, provider: str, model: str) -> bool:
    """Check if a stage would use swarm orchestration with the given model.

    Mirrors the decision in GroupReasoningEngine.run(), ClusterSynthesizer,
    and AtlasGenerator — minus the min_groups check (not available at query time).

    Phase 91: Returns False on low-resource systems (capacity ≤ 3) because
    swarm coordination overhead isn't worth it with so few workers.
    """
    if stage not in SWARM_CAPABLE_STAGES:
        return False
    try:
        # Phase 91: Low-resource guardrail — disable swarm when capacity ≤ 3.
        # Only applies when nodes are actually configured (capacity > 0).
        # At startup or in tests, nodes may not exist yet — allow swarm.
        node_capacity = pipeline_scheduler._get_max_dynamic_capacity()
        if 0 < node_capacity <= 3:
            return False
        from prep.core.swarm_registry import get_swarm_tier
        from prep.services.settings_store import settings
        tier = get_swarm_tier(provider, model)
        return tier.can_coordinate and bool(settings.get("swarm_enabled", True))
    except Exception:
        return False


# Providers that are always cloud — never compete for local VRAM.
CLOUD_PROVIDERS = {"openai", "anthropic", "google", "azure-openai"}


@dataclass
class ComputeSlot:
    """Tracks current load on a compute node."""
    node_id: str
    max_concurrent: int
    active_stages: Dict[str, str] = field(default_factory=dict)  # project_id -> stage_id

    # Latency-Aware AIMD (Phase 82 / 96B):
    # `current_limit` is the dynamically-adjustable cap used by AIMD.  It is
    # initialized to `max_concurrent` so a configured node starts at its full
    # capacity.  Backoffs shrink it, successful runs grow it back toward the
    # configured max.  The pre-Phase-96 default of `5` capped providers that
    # don't emit rate-limit headers (e.g. Ollama) at 5 forever.
    current_limit: int = 0  # sentinel — replaced in __post_init__
    # F-28: floor for AIMD multiplicative decrease.  Cloud nodes set this
    # to 3 so swarm fan-out (which needs ≥3 workers) keeps working even
    # after a single slow LLM call triggers backoff.  Local nodes default
    # to 1 since they're often single-GPU and can legitimately need to
    # serialize.
    min_limit: int = 1
    mode: Literal["jumpstart", "congestion_avoidance"] = "congestion_avoidance"
    success_streak: int = 0
    _last_backoff_time: float = 0.0
    # F-28: idle recovery — last time the slot's current_limit was
    # incremented by the recovery path (vs. by an LLM success).  Reset
    # whenever a backoff fires.  Used to gate recovery to ≥30s cadence.
    _last_recovery_time: float = 0.0
    # Phase 119: demand-gating for recovery. Stamped by acquire_request
    # when a waiter observes the gate is binding (in_flight >= limit).
    # _maybe_demand_recover() only grows current_limit if now < this stamp.
    _gate_binding_until: float = 0.0
    # Phase 119: discovered ceiling lock (mirrors ConcurrencyStore record).
    # Read by _maybe_demand_recover() to clamp growth at the locked ceiling.
    # Task 4 will add the writer (on backoff edge) and broaden enforcement
    # into the AIMD additive-increase / jumpstart paths. Until then this
    # field is declared but only enforced via demand-gated recovery.
    discovered_ceiling: Optional[int] = None
    ceiling_locked_until: float = 0.0

    # Phase 82 follow-up: per-request gate. `in_flight_requests` counts
    # LLM calls currently in flight against this slot. `_cond` is the
    # Condition new requests wait on when in_flight_requests >= current_limit.
    # Both are seeded lazily by PipelineScheduler.acquire_request — doing
    # it in __post_init__ creates a Condition per slot even when the gate
    # is never used (cheap but surprises tests that snapshot the slot).
    in_flight_requests: int = 0
    _cond: Any = None  # threading.Condition, lazy-initialized
    # Per-acquire monotonic counter for token stamping; stale tokens get
    # rejected by release_request via the _live_tokens set.
    _request_stamp_seq: int = 0
    _live_tokens: Set[int] = field(default_factory=set)

    def __post_init__(self):
        # Phase 82: cloud slots seed at jumpstart=5 per the Latency-Aware
        # Discovery spec. Local slots seed at max_concurrent — the VRAM
        # ceiling is known a priori and doesn't need discovery.
        is_cloud = self.node_id.startswith("cloud:")
        if self.current_limit <= 0:
            self.current_limit = 5 if is_cloud else max(1, self.max_concurrent)
        elif not is_cloud and self.current_limit > self.max_concurrent:
            self.current_limit = max(1, self.max_concurrent)
        if is_cloud and self.mode not in ("jumpstart", "congestion_avoidance"):
            self.mode = "jumpstart"
        if self.min_limit < 1:
            self.min_limit = 1
        if self.min_limit > self.max_concurrent and not is_cloud:
            self.min_limit = self.max_concurrent

    @property
    def current_load(self) -> int:
        return len(self.active_stages)

    @property
    def dynamic_capacity(self) -> int:
        """Phase 82: cloud slots discover their real ceiling at runtime;
        clipping by ``max_concurrent`` would defeat the discovery mechanism.
        Local slots keep the clamp — ``max_concurrent`` is a VRAM ceiling
        and a real hardware constraint.
        """
        if self.node_id.startswith("cloud:"):
            return max(1, self.current_limit)
        return min(self.max_concurrent, self.current_limit)

    @property
    def has_capacity(self) -> bool:
        return self.current_load < self.dynamic_capacity

    def acquire(self, project_id: str, stage_id: str) -> bool:
        """Try to acquire a slot. Returns True if successful."""
        if not self.has_capacity:
            return False
        self.active_stages[project_id] = stage_id
        return True

    def release(self, project_id: str, expected_stage: str | None = None) -> bool:
        """Release a slot. Returns True if it was held.

        Phase 89: When ``expected_stage`` is provided, only releases if
        the stored stage matches. This prevents a release for a completed
        stage from accidentally removing a newer stage's lock when
        ``active_stages`` was overwritten by ``acquire()`` during a
        same-node transition.
        """
        if expected_stage is not None:
            current = self.active_stages.get(project_id)
            if current != expected_stage:
                return False  # Stage was overwritten by advance — don't release
        return self.active_stages.pop(project_id, None) is not None


@dataclass
class QueueEntry:
    """A pipeline waiting for a compute slot."""
    project_id: str
    stage: StageId
    enqueued_at: float = field(default_factory=time.time)


def _derive_node_state(
    *,
    discovered_ceiling: Optional[int],
    ceiling_locked_until: float,
    last_backoff_time: float,
    backoff_cooldown_s: float,
) -> str:
    """Derive a presentation-layer state for a compute slot.

    Phase 119 — replaces the misleading raw-number triplet in the UI.

    Returns one of: ``probing``, ``locked``, ``backing_off``, ``recovering``.
    """
    now = time.time()
    if now - last_backoff_time < backoff_cooldown_s:
        return "backing_off"
    if discovered_ceiling is not None:
        if now < ceiling_locked_until:
            return "locked"
        return "recovering"
    return "probing"


class PipelineScheduler:
    """Manages compute slot allocation across multiple project pipelines.

    Thread-safe. Uses a simple FIFO queue per compute node.
    """

    # Dedicated embedding slot — separate from LLM nodes
    _EMBEDDING_NODE_ID = "__embedding__"

    def __init__(self) -> None:
        # F-74: MUST be RLock (reentrant), not Lock.
        # _broadcast_capacity_change() acquires self._lock internally
        # but is called from methods that already hold it (e.g. release(),
        # acquire()). With a non-reentrant Lock, this self-deadlocks.
        # This was the ROOT CAUSE of the "cloud model daemon hang" —
        # every LLM stage that completed tried to release its scheduler
        # slot, which called _broadcast_capacity_change, which deadlocked.
        self._lock = threading.RLock()
        # node_id -> ComputeSlot
        self._slots: Dict[str, ComputeSlot] = {}
        # node_id -> FIFO queue of waiting pipelines
        self._queues: Dict[str, Deque[QueueEntry]] = {}
        # Default node for when compute nodes aren't configured
        self._default_node_id = "__local__"
        self._default_max_concurrent = 1
        # Track which embedder is active (for OllamaEmbedder detection)
        self._embedding_uses_llm = False
        # Dedicated embedding concurrency (default: 1 = sequential)
        self._embedding_max_concurrent = 1
        self._init_embedding_slot()
        # Phase 72B: Multi-project priority support.
        # Maps project_id → PriorityLevel for ALL starred projects.
        # Previously only tracked a single project, causing starvation
        # when multiple projects were starred.
        self._priority_projects: Dict[str, PriorityLevel] = {}

        # Phase 91: Swarm window — temporary exclusive-like mode for
        # swarm-capable stages that need all resources for fan-out.
        self._swarm_window: Optional[Dict[str, Any]] = None
        # Unix timestamp: no swarm window can open before this time.
        self._swarm_cooldown_until: float = 0.0
        self._swarm_cooldown_seconds: float = 45.0
        # How long draining stages have before force-cancel (seconds).
        self._drain_timeout_seconds: int = 600  # 10 minutes

        # Phase 91: Capacity change event bus — batch engines subscribe
        # to get notified when their worker budget changes.
        self._capacity_listeners: Dict[str, Callable[[int], None]] = {}
        self._last_broadcast_times: Dict[str, float] = {}  # per-node debounce

    # ── Configuration ─────────────────────────────────────────────

    def configure_node(self, node_id: str, max_concurrent: int) -> None:
        """Register or update a compute node's concurrency limit.

        Phase 82: when reconfiguring an existing cloud slot, preserve the
        discovered ``current_limit`` and AIMD ``mode``. ``max_concurrent``
        for cloud slots is used only as a starting seed for NEW slots —
        live latency-aware discovery overrides it.  For local slots,
        ``max_concurrent`` is the real hardware (VRAM) ceiling and is
        always enforced.
        """
        with self._lock:
            new_max = max(1, max_concurrent)
            is_cloud = node_id.startswith("cloud:")
            if node_id in self._slots:
                slot = self._slots[node_id]
                slot.max_concurrent = new_max
                if not is_cloud:
                    if slot.current_limit > new_max:
                        # Local slots: VRAM ceiling is a real constraint — clamp.
                        slot.current_limit = new_max
                    elif slot.current_limit < new_max:
                        # Local slots: user raised the ceiling — grow immediately
                        # and wake any threads blocked at the gate.
                        slot.current_limit = new_max
                        self._wake_slot_waiters(slot)
                # Cloud slots: preserve discovered current_limit and mode.
                # Phase 96B grew the limit on reconfigure; Phase 82 drops
                # that because cloud discovery is unbounded and the user
                # editing a (legacy) UI slider shouldn't reset progress.
            else:
                # Phase 82: cloud slots seed at current_limit=5 (jumpstart),
                # but if the ConcurrencyStore has a previously-discovered
                # ceiling from a prior daemon run, hydrate with that value
                # so we don't replay the jumpstart from scratch. When we
                # hydrate we also switch mode to "congestion_avoidance":
                # the persisted value is a known probe point, and staying
                # in jumpstart would double 40→80→160 on the first
                # successes and overshoot the real ceiling. +1 additive
                # increase is the correct gentle probe around a known
                # ceiling.
                seed = 5 if is_cloud else new_max
                mode: Literal["jumpstart", "congestion_avoidance"] = (
                    "jumpstart" if is_cloud else "congestion_avoidance"
                )
                discovered_ceiling: Optional[int] = None
                ceiling_locked_until: float = 0.0
                if is_cloud:
                    try:
                        record = concurrency_store().load_full(node_id, "__default__")
                    except Exception as exc:  # pragma: no cover — best-effort
                        logger.debug(
                            "concurrency_store.load_full failed for %s: %s",
                            node_id, exc,
                        )
                        record = None
                    if record is not None:
                        seed = record["ceiling"]
                        mode = "congestion_avoidance"
                        # Phase 119: hydrate lock state when persisted.
                        if record["locked_until"] > 0:
                            discovered_ceiling = record["ceiling"]
                            ceiling_locked_until = record["locked_until"]
                            logger.info(
                                "Scheduler: restored locked ceiling %d for %s "
                                "until %.0f",
                                record["ceiling"], node_id, record["locked_until"],
                            )
                        else:
                            logger.info(
                                "Scheduler: hydrated unlocked ceiling %d for %s",
                                record["ceiling"], node_id,
                            )
                if is_cloud and record is None and node_id == "cloud:default_ollama":
                    # Phase 119: probe Ollama instead of the static 5 seed.
                    try:
                        from prep.services.settings_store import settings as _s
                        llm_config = _s.get("llm_config") or {}
                        host = ""
                        for ep in llm_config.get("saved_endpoints", []):
                            if ep.get("id") == "default_ollama":
                                host = ep.get("base_url") or "http://localhost:11434"
                                break
                        host = host or "http://localhost:11434"
                        probed = ollama_probe.probe_ollama_concurrency(host)
                        if probed > 0:
                            seed = probed
                            logger.info(
                                "Scheduler: Ollama probe seeded %s at %d "
                                "(host=%s)",
                                node_id, probed, host,
                            )
                    except Exception as exc:
                        logger.debug("Ollama probe error for seed: %s", exc)
                self._slots[node_id] = ComputeSlot(
                    node_id=node_id,
                    max_concurrent=new_max,
                    current_limit=seed,
                    min_limit=self._compute_min_limit(node_id, new_max),
                    mode=mode,
                    discovered_ceiling=discovered_ceiling,
                    ceiling_locked_until=ceiling_locked_until,
                )
                self._queues[node_id] = deque()
        logger.debug(
            "Scheduler: node %s configured with max_concurrent=%d",
            node_id, max_concurrent,
        )

    def remove_node(self, node_id: str) -> None:
        """Remove a compute node."""
        with self._lock:
            self._slots.pop(node_id, None)
            self._queues.pop(node_id, None)

    def set_default_concurrency(self, max_concurrent: int) -> None:
        """Set the default concurrency for the local node."""
        self._default_max_concurrent = max(1, max_concurrent)
        self.configure_node(self._default_node_id, self._default_max_concurrent)

    def set_embedding_uses_llm(self, uses_llm: bool) -> None:
        """Set whether embedding stages compete for LLM slots (OllamaEmbedder)."""
        self._embedding_uses_llm = uses_llm

    def _init_embedding_slot(self) -> None:
        """Create the dedicated embedding slot."""
        self._slots[self._EMBEDDING_NODE_ID] = ComputeSlot(
            node_id=self._EMBEDDING_NODE_ID,
            max_concurrent=self._embedding_max_concurrent,
        )
        self._queues[self._EMBEDDING_NODE_ID] = deque()

    def configure_embedding_concurrency(self, max_concurrent: int) -> None:
        """Set how many embedding stages can run simultaneously.

        Called automatically by ``load_from_settings()`` based on
        detected system memory.  Default is 1 (safe for all machines).
        """
        with self._lock:
            self._embedding_max_concurrent = max(1, max_concurrent)
            if self._EMBEDDING_NODE_ID in self._slots:
                slot = self._slots[self._EMBEDDING_NODE_ID]
                slot.max_concurrent = self._embedding_max_concurrent
                # Phase 96B: grow AIMD current_limit to match new max
                if slot.current_limit < self._embedding_max_concurrent:
                    slot.current_limit = self._embedding_max_concurrent
                    self._wake_slot_waiters(slot)
            else:
                self._init_embedding_slot()
        logger.info(
            "Scheduler: embedding concurrency set to %d",
            self._embedding_max_concurrent,
        )

    def set_priority(
        self,
        project_id: Optional[str],
        level: PriorityLevel = "boost",
    ) -> None:
        """Add, update, or remove priority for a project.

        Phase 72B: Now supports multiple concurrent priority projects.

        Levels:
          ``none``      — remove this project from the priority set.
          ``boost``     — queue-jump + proportional share of cloud budget.
          ``exclusive`` — queue-jump + FULL cloud budget; other projects'
                          LLM stages are queued until exclusive finishes.

        Multiple projects can hold ``boost`` simultaneously.  Only one
        project can hold ``exclusive`` — setting exclusive on a new project
        demotes all existing exclusive projects to ``boost``.

        Passing ``project_id=None`` with ``level='none'`` clears ALL priorities.
        """
        with self._lock:
            if project_id is None and level == "none":
                # Clear all priorities
                if self._priority_projects:
                    logger.info("Scheduler: clearing all priorities (%d projects)",
                                len(self._priority_projects))
                self._priority_projects.clear()
                return

            if project_id is None:
                return  # Nothing to do

            if level == "none":
                old = self._priority_projects.pop(project_id, None)
                if old:
                    logger.info("Scheduler: removed priority for %s (was %s)",
                                project_id, old)
                return

            # If setting exclusive, demote any existing exclusive projects to boost
            if level == "exclusive":
                for pid, plevel in list(self._priority_projects.items()):
                    if plevel == "exclusive" and pid != project_id:
                        self._priority_projects[pid] = "boost"
                        logger.info(
                            "Scheduler: demoting %s from exclusive → boost "
                            "(new exclusive: %s)", pid, project_id,
                        )

            old_level = self._priority_projects.get(project_id)
            self._priority_projects[project_id] = level
            broadcast_reason: Optional[str] = None
            if old_level != level:
                logger.info("Scheduler: priority %s → %s (%s)",
                            project_id, level,
                            f"was {old_level}" if old_level else "new")
                # Phase 91: Broadcast capacity changes for exclusive transitions
                if level == "exclusive":
                    broadcast_reason = "exclusive_start"
                elif old_level == "exclusive":
                    broadcast_reason = "exclusive_end"

        # Broadcast outside lock
        if broadcast_reason:
            for nid in list(self._slots.keys()):
                if nid != self._EMBEDDING_NODE_ID:
                    self._broadcast_capacity_change(nid, broadcast_reason)

    def clear_all_priorities(self) -> None:
        """Remove all project priorities."""
        self.set_priority(None, "none")

    def record_throughput(
        self,
        node_id: str,
        queue_time_ms: float = 0.0,
        rate_limit_remaining: Optional[int] = None,
        is_429_or_timeout: bool = False,
    ) -> None:
        """Phase 82: Latency-Aware AIMD step, called upon LLM completion.

        Adjusts `current_limit` dynamically based on LLM execution queue time
        or hard rate limits.
        """
        changed = False
        with self._lock:
            if node_id not in self._slots:
                return
            slot = self._slots[node_id]
            old_limit = slot.current_limit
            self._record_throughput_for_slot(slot, queue_time_ms, rate_limit_remaining, is_429_or_timeout)
            changed = slot.current_limit != old_limit
        # Phase 91: Broadcast capacity change if AIMD adjusted the limit
        if changed:
            self._broadcast_capacity_change(node_id, "aimd_adjust")

    def record_throughput_for_provider(
        self,
        provider: str,
        model: str,
        queue_time_ms: float = 0.0,
        rate_limit_remaining: Optional[int] = None,
        is_429_or_timeout: bool = False,
    ) -> None:
        """Helper for LLMClient: resolves node automatically based on provider/model."""
        is_cloud = provider in CLOUD_PROVIDERS
        if not is_cloud and model:
            try:
                from prep.core.batch_profiles import is_cloud_model_via_ollama
                if is_cloud_model_via_ollama(provider, model):
                    is_cloud = True
            except ImportError:
                pass
        prefix = "cloud:" if is_cloud else "local:"
        
        # F-74: Use non-blocking lock acquisition. This method is called from
        # the build thread after every LLM response. If the dashboard's polling
        # threads hold self._lock (via status() or available_batch_workers()),
        # a blocking acquire here deadlocks the entire pipeline — the build
        # thread waits for the lock, the polling thread waits for the build
        # thread to release the BuildOrchestrator, creating a circular wait.
        changed_nodes: List[str] = []
        acquired = self._lock.acquire(blocking=False)
        if not acquired:
            logger.debug("record_throughput: skipped (lock busy)")
            return
        try:
            for nid, slot in self._slots.items():
                if nid.startswith(prefix):
                    old_limit = slot.current_limit
                    self._record_throughput_for_slot(slot, queue_time_ms, rate_limit_remaining, is_429_or_timeout)
                    if slot.current_limit != old_limit:
                        changed_nodes.append(nid)
        finally:
            self._lock.release()
        # Phase 91: Broadcast capacity changes
        for nid in changed_nodes:
            self._broadcast_capacity_change(nid, "aimd_adjust")

    def _record_throughput_for_slot(
        self,
        slot: ComputeSlot,
        queue_time_ms: float = 0.0,
        rate_limit_remaining: Optional[int] = None,
        is_429_or_timeout: bool = False,
    ) -> None:
        """Internal helper to apply AIMD logic to a single slot.

        Signal model (Phase 82 follow-up, research-driven):
        - MD (backoff) fires on explicit failure signals only: 429, 5xx, timeout,
          connection error. This matches AWS adaptive-retry and the consensus
          from Netflix concurrency-limits / Envoy adaptive_concurrency that
          wall-clock latency thresholds are unreliable for heterogeneous LLM
          traffic (response length varies 10-1000x).
        - Ollama's `total_duration - (eval + prompt_eval + load)` gap was
          previously used as a latency signal but it measures unaccounted
          inference overhead, not queue time (Ollama issue #10860). Still
          passed through for observability / future tokens-per-second EWMA
          work, but no longer triggers MD.
        - Cloud APIs: rate_limit_remaining headers still clamp max concurrency.
        queue_time_ms is retained in the signature for logging and to leave
        the telemetry path open for per-token work-normalized signals.
        """
        # Step 1: Clamp hard limit from cloud rate-limit headers (when available)
        if rate_limit_remaining is not None and rate_limit_remaining >= 0:
            safe_limit = max(1, rate_limit_remaining - 2)
            if slot.max_concurrent > safe_limit:
                slot.max_concurrent = safe_limit
                if slot.current_limit > safe_limit:
                    slot.current_limit = safe_limit
                    self._persist_cloud_ceiling(slot)

        # Step 2: Congestion detection — rejection-primary (429/5xx/timeout).
        if is_429_or_timeout:
            now = time.time()
            # Cooldown so we don't back off 10 times for a single congested batch
            if now - slot._last_backoff_time > 2.0:
                old_mode = slot.mode

                # Multiplicative Decrease: Half limit, or current in-flight,
                # but never below the per-node floor (F-28).
                #
                # ``in_flight_requests`` is the gate-level count of currently
                # outstanding LLM requests.  ``current_load`` is the count of
                # active stages and is ~1 for any single-stage fan-out, so
                # using it here collapsed the cap to the floor on every MD
                # event regardless of actual request concurrency.
                in_flight = slot.in_flight_requests
                new_limit = max(slot.min_limit, min(slot.current_limit // 2, in_flight))

                if slot.current_limit > new_limit:
                    logger.warning(
                        "Scheduler: Node %s rejected request (429/5xx/timeout). "
                        "Backing off limit %d -> %d (floor=%d, observed queue_ms=%.1f)",
                        slot.node_id,
                        slot.current_limit, new_limit, slot.min_limit, queue_time_ms,
                    )
                    slot.current_limit = new_limit
                    self._persist_cloud_ceiling(slot)
                slot._last_backoff_time = now
                # Reset recovery clock — idle recovery shouldn't fire
                # immediately after a fresh backoff.
                slot._last_recovery_time = now
                # Phase 119: only mode==congestion_avoidance is a confirmed edge.
                if old_mode == "congestion_avoidance":
                    self._record_ceiling_edge(slot, now)
                slot.mode = "congestion_avoidance"
                slot.success_streak = 0
        else:
            # Step 3: Additive Increase or Jumpstart (no congestion detected).
            # Phase 82 completion: cloud slots are unbounded — the ceiling is
            # discovered via congestion signals, not configured. Local slots
            # still respect max_concurrent (VRAM).
            slot.success_streak += 1

            is_cloud = slot.node_id.startswith("cloud:")
            batch_size = max(1, slot.current_limit)
            if slot.success_streak >= batch_size:
                slot.success_streak = 0
                allow_increase = is_cloud or slot.current_limit < slot.max_concurrent
                # Phase 119: locked ceiling blocks growth above the discovered point
                # until TTL passes. After TTL, one cautious +1 probe is allowed.
                if (
                    is_cloud
                    and slot.discovered_ceiling is not None
                    and slot.current_limit >= slot.discovered_ceiling
                    and time.time() < slot.ceiling_locked_until
                ):
                    allow_increase = False
                if allow_increase:
                    if slot.mode == "jumpstart":
                        new_limit = slot.current_limit * 2
                        if not is_cloud:
                            new_limit = min(slot.max_concurrent, new_limit)
                        elif slot.discovered_ceiling is not None and time.time() < slot.ceiling_locked_until:
                            new_limit = min(slot.discovered_ceiling, new_limit)
                        logger.info(
                            "Scheduler: Node %s jumpstart %d -> %d",
                            slot.node_id, slot.current_limit, new_limit,
                        )
                        slot.current_limit = new_limit
                        self._persist_cloud_ceiling(slot)
                        self._wake_slot_waiters(slot)
                    else:
                        new_limit = slot.current_limit + 1
                        if not is_cloud:
                            new_limit = min(slot.max_concurrent, new_limit)
                        elif slot.discovered_ceiling is not None and time.time() < slot.ceiling_locked_until:
                            new_limit = min(slot.discovered_ceiling, new_limit)
                        logger.info(
                            "Scheduler: Node %s additive increase %d -> %d (mode=%s, max=%d, floor=%d)",
                            slot.node_id, slot.current_limit, new_limit,
                            slot.mode, slot.max_concurrent, slot.min_limit,
                        )
                        slot.current_limit = new_limit
                        self._persist_cloud_ceiling(slot)
                        self._wake_slot_waiters(slot)

    def get_priority(self, project_id: str) -> PriorityLevel:
        """Get the priority level for a specific project."""
        return self._priority_projects.get(project_id, "none")

    @property
    def priority_project_id(self) -> Optional[str]:
        """Backward-compat: return first exclusive project, or first boosted."""
        for pid, level in self._priority_projects.items():
            if level == "exclusive":
                return pid
        for pid, level in self._priority_projects.items():
            if level == "boost":
                return pid
        return None

    @property
    def priority_level(self) -> PriorityLevel:
        """Backward-compat: return the highest priority level currently set."""
        if any(l == "exclusive" for l in self._priority_projects.values()):
            return "exclusive"
        if any(l == "boost" for l in self._priority_projects.values()):
            return "boost"
        return "none"

    @property
    def priority_projects(self) -> Dict[str, PriorityLevel]:
        """Return a snapshot of all priority projects."""
        return dict(self._priority_projects)

    # ── Slot management ───────────────────────────────────────────

    def _get_slot(self, node_id: Optional[str] = None) -> ComputeSlot:
        """Get or create a compute slot for a node."""
        nid = node_id or self._default_node_id
        if nid not in self._slots:
            max_c = self._default_max_concurrent
            self._slots[nid] = ComputeSlot(
                node_id=nid,
                max_concurrent=max_c,
                min_limit=self._compute_min_limit(nid, max_c),
            )
            self._queues[nid] = deque()
        return self._slots[nid]

    def _persist_cloud_ceiling(self, slot: ComputeSlot) -> None:
        """Phase 82: write the current cloud ceiling to ConcurrencyStore.

        No-op for local slots — their ceiling is a known VRAM constraint,
        not something we discover at runtime. Best-effort: a failing
        persistence call must not disrupt the scheduler.
        """
        if not slot.node_id.startswith("cloud:"):
            return
        try:
            concurrency_store().save(
                slot.node_id, "__default__", ceiling=slot.current_limit,
            )
        except Exception as exc:  # pragma: no cover — persistence is best-effort
            logger.debug(
                "concurrency_store.save failed for %s: %s",
                slot.node_id, exc,
            )

    def _record_ceiling_edge(self, slot: ComputeSlot, now: float) -> None:
        """Persist a discovered ceiling with TTL after a confirmed edge.

        Phase 119: only called from the backoff path when ``mode`` is
        already ``congestion_avoidance`` — i.e., a real edge, not
        jumpstart exploration. Caller MUST hold ``self._lock``.
        """
        if not slot.node_id.startswith("cloud:"):
            return
        try:
            from prep.services.settings_store import settings as _settings
            ttl = float(_settings.get("concurrency_lock_ttl_s") or self._DEFAULT_LOCK_TTL_S)
        except Exception:
            ttl = self._DEFAULT_LOCK_TTL_S

        slot.discovered_ceiling = slot.current_limit
        slot.ceiling_locked_until = now + ttl
        try:
            concurrency_store().save_edge(
                slot.node_id, "__default__",
                ceiling=slot.current_limit,
                locked_until=slot.ceiling_locked_until,
                edge_observed_at=now,
            )
        except Exception as exc:  # pragma: no cover — best-effort
            logger.debug(
                "concurrency_store.save_edge failed for %s: %s",
                slot.node_id, exc,
            )

    def _compute_min_limit(self, node_id: str, max_concurrent: int) -> int:
        """F-28: per-node floor for AIMD.

        Cloud nodes get a floor of 3 (or max_concurrent if smaller) so
        a single slow LLM call cannot collapse the swarm budget below
        the SwarmOrchestrator min_workers threshold and force fallback
        to non-swarm execution.  Local nodes stay at 1 since they are
        often single-GPU and can legitimately need to serialize.
        """
        if node_id.startswith("cloud:"):
            return min(3, max(1, max_concurrent))
        return 1

    # F-28: idle recovery cadence and cooldown after a backoff before
    # recovery is allowed to fire.
    _IDLE_RECOVERY_INTERVAL_S = 30.0
    _BACKOFF_COOLDOWN_S = 30.0
    # Phase 119 demand window: when acquire_request observes the gate
    # binding, the next 60 s allow recovery to fire.
    _DEMAND_WINDOW_S = 60.0
    # Phase 119: how long a discovered ceiling stays locked. 24 h is
    # the project default; can be overridden via settings("concurrency_lock_ttl_s").
    _DEFAULT_LOCK_TTL_S = 24 * 3600

    def _maybe_demand_recover(self, slot: ComputeSlot) -> None:
        """Grow ``slot.current_limit`` by 1 if recent demand justifies it.

        Caller MUST hold ``self._lock``.

        Phase 119 supersedes Phase 96 F-28's idle recovery: the original
        version grew on every acquire() call regardless of demand, which
        produced an unbounded random walk on cloud slots. The new
        version requires that ``acquire_request`` recently observed the
        gate as binding (``slot._gate_binding_until`` > now) before
        growing.

        Local slots cap at ``max_concurrent`` (VRAM is a real ceiling).
        Cloud slots cap at ``discovered_ceiling`` when locked, otherwise
        unbounded per Phase 82.
        """
        is_cloud = slot.node_id.startswith("cloud:")

        # Cap check — local has VRAM; cloud has the optional locked ceiling.
        if not is_cloud and slot.current_limit >= slot.max_concurrent:
            return
        if is_cloud and slot.discovered_ceiling is not None:
            if slot.current_limit >= slot.discovered_ceiling:
                return

        now = time.time()
        if now - slot._last_backoff_time < self._BACKOFF_COOLDOWN_S:
            return
        if now - slot._last_recovery_time < self._IDLE_RECOVERY_INTERVAL_S:
            return

        # Phase 119 demand gate — must have been binding within the window.
        if now >= slot._gate_binding_until:
            return

        if is_cloud:
            new_limit = slot.current_limit + 1
            if slot.discovered_ceiling is not None:
                new_limit = min(new_limit, slot.discovered_ceiling)
        else:
            new_limit = min(slot.max_concurrent, slot.current_limit + 1)

        if new_limit > slot.current_limit:
            logger.info(
                "Scheduler: Node %s demand-gated recovery %d -> %d "
                "(max=%d, floor=%d, ceiling=%s)",
                slot.node_id, slot.current_limit, new_limit,
                slot.max_concurrent, slot.min_limit,
                slot.discovered_ceiling,
            )
            slot.current_limit = new_limit
            slot._last_recovery_time = now
            self._persist_cloud_ceiling(slot)
            self._wake_slot_waiters(slot)

    # ── Per-request gate (Phase 82 follow-up) ─────────────────────

    def _slot_condition(self, slot: ComputeSlot) -> threading.Condition:
        """Lazily attach a Condition to the slot, reusing the scheduler's lock.

        Caller MUST hold ``self._lock``. The Condition wraps ``self._lock``
        (which is an RLock) so ``wait()`` releases the scheduler lock while
        suspended, and reacquires it on wake. Reusing the scheduler lock
        keeps ``current_limit`` reads consistent across waiters.
        """
        if slot._cond is None:
            slot._cond = threading.Condition(self._lock)
        return slot._cond

    def _wake_slot_waiters(self, slot: ComputeSlot) -> None:
        """Notify every thread blocked on slot's per-request gate.

        Call this after ``current_limit`` grows (idle recovery, AIMD
        additive increase, jumpstart doubling) so waiters re-check the
        predicate instead of sleeping until their 120s timeout.
        Caller MUST hold ``self._lock``.
        """
        if slot._cond is not None:
            slot._cond.notify_all()

    def acquire_request(
        self, node_id: str, timeout: float = 120.0,
    ) -> Optional[Tuple[str, int]]:
        """Acquire one in-flight request slot on ``node_id``.

        Blocks up to ``timeout`` seconds waiting for
        ``in_flight_requests < current_limit``. Returns an opaque token
        (node_id, stamp) that must be passed to ``release_request``.
        Returns ``None`` on timeout or if the node doesn't exist.
        """
        deadline = time.monotonic() + max(0.0, timeout)
        with self._lock:
            slot = self._slots.get(node_id)
            if slot is None:
                return None
            cond = self._slot_condition(slot)

            # Phase 119: stamp gate-binding observations so demand-gated
            # recovery can fire later. Only stamp when the gate would
            # actually have been binding (in_flight at or above limit).
            if slot.in_flight_requests >= slot.dynamic_capacity:
                slot._gate_binding_until = time.time() + self._DEMAND_WINDOW_S

            while slot.in_flight_requests >= slot.dynamic_capacity:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                woke = cond.wait(timeout=remaining)
                if not woke:
                    continue

            slot.in_flight_requests += 1
            slot._request_stamp_seq += 1
            stamp = slot._request_stamp_seq
            slot._live_tokens.add(stamp)
            return (node_id, stamp)

    def release_request(self, token: Optional[Tuple[str, int]]) -> None:
        """Release a previously-acquired request slot.

        Safe to call with ``None`` (no-op) or a stale token (no-op — won't
        drive ``in_flight_requests`` negative or wake extra waiters).
        """
        if token is None:
            return
        node_id, stamp = token
        with self._lock:
            slot = self._slots.get(node_id)
            if slot is None:
                return
            if stamp not in slot._live_tokens:
                return
            slot._live_tokens.discard(stamp)
            if slot.in_flight_requests > 0:
                slot.in_flight_requests -= 1
            cond = self._slot_condition(slot)
            cond.notify_all()

    @contextmanager
    def acquire_request_ctx(
        self, node_id: str, timeout: float = 120.0,
    ):
        """Context-manager wrapper around acquire_request / release_request.

        Yields the token (or ``None`` on timeout). Always releases, even
        on exception.
        """
        token = self.acquire_request(node_id, timeout=timeout)
        try:
            yield token
        finally:
            self.release_request(token)

    def _get_queue(self, node_id: Optional[str] = None) -> Deque[QueueEntry]:
        """Get or create a queue for a node."""
        nid = node_id or self._default_node_id
        if nid not in self._queues:
            self._queues[nid] = deque()
        return self._queues[nid]

    def _get_max_dynamic_capacity(self) -> int:
        """Return the highest dynamic_capacity across all LLM nodes.

        Used by is_swarm_active_for_stage() for the low-resource check.
        """
        with self._lock:
            best = 0
            for nid, slot in self._slots.items():
                if nid == self._EMBEDDING_NODE_ID:
                    continue
                if slot.dynamic_capacity > best:
                    best = slot.dynamic_capacity
            return best

    def _needs_slot(self, stage: StageId) -> bool:
        """Check if a stage needs a compute slot."""
        queue_type = STAGE_QUEUE_TYPE.get(stage, QueueType.LLM)
        if queue_type == QueueType.RUST:
            return False
        # Embedding stages always need the embedding slot.
        # If OllamaEmbedder is active, they ALSO need an LLM slot
        # (handled by _resolve_node_for_stage).
        return True  # LLM or EMBEDDING

    def _resolve_node_for_stage(
        self, stage: StageId, node_id: Optional[str] = None,
    ) -> str:
        """Determine the correct compute node for a stage.

        Embedding stages use the dedicated ``__embedding__`` node.
        LLM/Rust stages use the caller-supplied or default node.
        """
        queue_type = STAGE_QUEUE_TYPE.get(stage, QueueType.LLM)
        if queue_type == QueueType.EMBEDDING and not self._embedding_uses_llm:
            return self._EMBEDDING_NODE_ID
        return node_id or self._default_node_id

    # ── Phase 91: Swarm Window Lifecycle ─────────────────────────

    def open_swarm_window(
        self,
        project_id: str,
        stage: "StageId",
        node_id: Optional[str] = None,
    ) -> bool:
        """Open an exclusive swarm window for a project's stage.

        Blocks all OTHER projects from acquiring new slots on the same
        node. Already-running stages on other projects continue until
        they finish naturally (drain) or hit the drain timeout.

        Returns True if the window was opened, False if cooldown is
        still active or a swarm window is already open.
        """
        resolved = self._resolve_node_for_stage(stage, node_id)
        with self._lock:
            # Cooldown check
            if time.time() < self._swarm_cooldown_until:
                logger.info(
                    "Scheduler: swarm window blocked by cooldown (%.1fs remaining) for %s",
                    self._swarm_cooldown_until - time.time(), project_id,
                )
                return False
            # Already open
            if self._swarm_window is not None:
                logger.warning(
                    "Scheduler: swarm window already open for %s, rejecting %s",
                    self._swarm_window["project_id"], project_id,
                )
                return False

            # Identify drain targets: other active projects on the same node
            slot = self._get_slot(resolved)
            drain_targets: Dict[str, float] = {}
            now = time.time()
            for pid in slot.active_stages:
                if pid != project_id:
                    drain_targets[pid] = now

            self._swarm_window = {
                "project_id": project_id,
                "stage": stage,
                "node_id": resolved,
                "started_at": now,
                "drain_targets": drain_targets,
            }
            logger.info(
                "Scheduler: ⚡ swarm window OPENED for %s/%s on %s "
                "(%d drain targets: %s)",
                project_id, stage.value if hasattr(stage, 'value') else stage,
                resolved, len(drain_targets),
                ", ".join(drain_targets.keys()) or "none",
            )
        # C2 fix: Broadcast outside lock so other projects learn their budget dropped
        self._broadcast_capacity_change(resolved, "swarm_start")
        return True

    def close_swarm_window(self) -> None:
        """Close the active swarm window and start cooldown."""
        with self._lock:
            if self._swarm_window is None:
                return
            window = self._swarm_window
            self._swarm_window = None
            self._swarm_cooldown_until = time.time() + self._swarm_cooldown_seconds
            logger.info(
                "Scheduler: ⚡ swarm window CLOSED for %s/%s — "
                "%.1fs cooldown started",
                window["project_id"],
                window["stage"].value if hasattr(window["stage"], 'value') else window["stage"],
                self._swarm_cooldown_seconds,
            )
        # Broadcast outside lock to avoid deadlock with listener callbacks
        self._broadcast_capacity_change(window["node_id"], "swarm_end")

    def is_swarm_window_active(self) -> bool:
        """Check if a swarm window is currently open."""
        return self._swarm_window is not None

    def get_swarm_window(self) -> Optional[Dict[str, Any]]:
        """Return a snapshot of the current swarm window state, or None.

        Returns a shallow copy to prevent callers from mutating internal state.
        """
        with self._lock:
            w = self._swarm_window
            if w is None:
                return None
            return {**w, "drain_targets": dict(w.get("drain_targets", {}))}

    def check_drain_timeouts(self) -> List[str]:
        """Check if any drain targets have exceeded the timeout.

        Returns list of project_ids that should be force-cancelled.
        Called periodically by the orchestrator.
        """
        with self._lock:
            if self._swarm_window is None:
                return []
            now = time.time()
            timed_out: List[str] = []
            drain_targets = self._swarm_window.get("drain_targets", {})
            for pid, started_at in list(drain_targets.items()):
                if now - started_at > self._drain_timeout_seconds:
                    timed_out.append(pid)
                    # Remove from drain targets so we don't re-report
                    del drain_targets[pid]
            if timed_out:
                logger.warning(
                    "Scheduler: drain timeout — %d project(s) exceeded %ds: %s",
                    len(timed_out), self._drain_timeout_seconds,
                    ", ".join(timed_out),
                )
            return timed_out

    def _is_blocked_by_swarm(self, project_id: str, node_id: str) -> bool:
        """Check if a project is blocked from acquiring by an active swarm window.

        Callers must hold ``self._lock``. Captures the window reference
        defensively to avoid TOCTOU races if called without the lock.
        """
        window = self._swarm_window
        if window is None:
            return False
        return window["node_id"] == node_id and window["project_id"] != project_id

    # ── Phase 91: Capacity Change Event Bus ──────────────────────

    def on_capacity_change(
        self,
        project_id: str,
        node_id: str,
        callback: Callable[[int], None],
    ) -> Callable[[], None]:
        """Register a listener for capacity changes on a node.

        The callback receives the new worker budget (int) whenever
        resource allocation changes (swarm, exclusive, AIMD, etc.).

        Returns a cleanup function that unregisters the listener.
        """
        key = f"{project_id}:{node_id}"
        with self._lock:
            self._capacity_listeners[key] = callback
        logger.debug("Scheduler: capacity listener registered for %s", key)

        def cleanup():
            with self._lock:
                self._capacity_listeners.pop(key, None)

        return cleanup

    def _broadcast_capacity_change(self, node_id: str, reason: str) -> None:
        """Notify all listeners on a node that their budget may have changed.

        Debounced: won't fire more than once per second per node.
        Callbacks are collected under the lock but invoked OUTSIDE it
        to prevent deadlocks if a callback re-enters the scheduler.
        """
        now = time.time()
        # I4: Per-node debounce instead of global
        last = self._last_broadcast_times.get(node_id, 0.0)
        if now - last < 1.0:
            return
        self._last_broadcast_times[node_id] = now

        # Collect (key, callback, budget) under lock
        to_notify: List[Tuple[str, Callable[[int], None], int]] = []
        with self._lock:
            slot = self._get_slot(node_id)
            for pid in list(slot.active_stages.keys()):
                key = f"{pid}:{node_id}"
                cb = self._capacity_listeners.get(key)
                if cb:
                    budget = self._weighted_share(slot, pid)
                    to_notify.append((key, cb, budget))

        # Invoke outside lock (C1 fix: prevents deadlock)
        for key, cb, budget in to_notify:
            try:
                cb(budget)
            except Exception:
                logger.debug(
                    "Scheduler: capacity listener error for %s",
                    key, exc_info=True,
                )

        logger.info(
            "Scheduler: capacity broadcast on %s (reason=%s, %d listeners)",
            node_id, reason, len(to_notify),
        )

    # ── Public API ────────────────────────────────────────────────

    def can_start(
        self,
        project_id: str,
        stage: StageId,
        node_id: Optional[str] = None,
    ) -> bool:
        """Check if a stage can start given current compute load.

        Returns True if:
          - Stage doesn't need a slot (Rust)
          - The compute node has available capacity
          - No exclusive project is occupying the node (unless we ARE
            the exclusive project)
        """
        if not self._needs_slot(stage):
            return True
        resolved = self._resolve_node_for_stage(stage, node_id)
        with self._lock:
            slot = self._get_slot(resolved)
            if not slot.has_capacity:
                return False
            # Phase 91: Swarm gate (highest priority)
            if self._is_blocked_by_swarm(project_id, resolved):
                return False
            # Exclusive gate: if another project holds exclusive priority
            # and is active on this node, queue us instead of starting.
            for exc_pid, exc_level in self._priority_projects.items():
                if (
                    exc_level == "exclusive"
                    and exc_pid != project_id
                    and exc_pid in slot.active_stages
                ):
                    return False
            return True

    def acquire(
        self,
        project_id: str,
        stage: StageId,
        node_id: Optional[str] = None,
    ) -> bool:
        """Acquire a compute slot for a stage.

        Returns True if the slot was acquired. False if the node is full
        or a swarm window / exclusive-priority project is blocking.
        Caller should enqueue the pipeline if this returns False.

        Phase 91: Tier hierarchy — Swarm > Exclusive > Boost > Normal.
        """
        if not self._needs_slot(stage):
            return True  # No slot needed
        resolved = self._resolve_node_for_stage(stage, node_id)
        with self._lock:
            slot = self._get_slot(resolved)
            # Phase 119: demand-gated recovery — if no backoff has fired
            # in the last 30s, the recovery interval has elapsed, AND
            # acquire_request recently observed the gate as binding,
            # grow current_limit by 1.  This piggybacks on natural
            # pipeline activity instead of needing a separate ticker
            # thread, and avoids the unbounded random walk that the
            # F-28 idle-recovery version produced on cloud slots.
            self._maybe_demand_recover(slot)
            # Phase 91: Swarm gate (highest priority) — blocks all other
            # projects from acquiring on the swarm node.
            if self._is_blocked_by_swarm(project_id, resolved):
                return False
            # Exclusive gate: if another project holds exclusive priority
            # and is active on this node, block.
            for exc_pid, exc_level in self._priority_projects.items():
                if (
                    exc_level == "exclusive"
                    and exc_pid != project_id
                    and exc_pid in slot.active_stages
                ):
                    return False
            ok = slot.acquire(project_id, stage.value)
            if ok:
                logger.info(
                    "Scheduler: %s acquired slot on %s for %s (%d/%d dynamic cap)",
                    project_id, slot.node_id, stage.value,
                    slot.current_load, slot.dynamic_capacity,
                )
            return ok

    def release(
        self,
        project_id: str,
        stage: StageId,
        node_id: Optional[str] = None,
    ) -> Optional[QueueEntry]:
        """Release a compute slot and return the next queued entry (if any).

        Returns a QueueEntry if there's a waiting pipeline that should be
        resumed, or None if the queue is empty.
        """
        if not self._needs_slot(stage):
            return None  # Nothing to release
        resolved = self._resolve_node_for_stage(stage, node_id)
        _close_swarm = False
        with self._lock:
            slot = self._get_slot(resolved)
            # Phase 89: Pass stage value so ComputeSlot.release() can verify
            # the stored stage matches. Prevents releasing a newer stage's
            # lock after a same-node advance overwrote active_stages.
            released = slot.release(project_id, expected_stage=stage.value)
            if released:
                logger.info(
                    "Scheduler: %s released slot on %s for %s (%d/%d dynamic cap)",
                    project_id, slot.node_id, stage.value,
                    slot.current_load, slot.dynamic_capacity,
                )
                # Phase 91: If the swarm window owner is releasing, close
                # the window. This triggers cooldown and broadcasts.
                _close_swarm = False
                if self._swarm_window and self._swarm_window["project_id"] == project_id:
                    _close_swarm = True
                # Remove from swarm drain targets if present
                elif self._swarm_window and project_id in self._swarm_window.get("drain_targets", {}):
                    del self._swarm_window["drain_targets"][project_id]
                    logger.info(
                        "Scheduler: %s drained naturally (swarm window for %s)",
                        project_id, self._swarm_window["project_id"],
                    )
                # Phase 91: Unregister capacity listener
                key = f"{project_id}:{resolved}"
                self._capacity_listeners.pop(key, None)

            # Check if there's a queued pipeline waiting for this node
            # Phase 91: Don't dequeue if swarm window blocks this node
            result: Optional[QueueEntry] = None
            queue = self._get_queue(resolved)
            if queue and slot.has_capacity:
                # Peek: if swarm window is active and next entry isn't the
                # swarm project, don't dequeue.
                next_entry = queue[0]
                if not self._is_blocked_by_swarm(next_entry.project_id, resolved):
                    result = queue.popleft()
                    logger.info(
                        "Scheduler: dequeuing %s for %s (waited %.1fs)",
                        result.project_id, result.stage.value,
                        time.time() - result.enqueued_at,
                    )

        # Phase 91: Close swarm window outside lock (triggers broadcast)
        if _close_swarm:
            self.close_swarm_window()
        return result

    def enqueue(
        self,
        project_id: str,
        stage: StageId,
        node_id: Optional[str] = None,
    ) -> None:
        """Add a pipeline to the wait queue for a compute node."""
        resolved = self._resolve_node_for_stage(stage, node_id)
        with self._lock:
            queue = self._get_queue(resolved)
            # Don't double-enqueue the same project+stage combination.
            # Previous check only compared project_id, which silently
            # dropped a second stage for the same project and allowed
            # duplicate entries when the same stage was enqueued twice.
            for entry in queue:
                if entry.project_id == project_id and entry.stage == stage:
                    logger.debug(
                        "Scheduler: %s/%s already queued on %s",
                        project_id, stage.value, resolved,
                    )
                    return
            entry = QueueEntry(project_id=project_id, stage=stage)
            # Priority projects (boost or exclusive) go to front of queue
            project_priority = self._priority_projects.get(project_id)
            if project_priority and project_priority != "none":
                queue.appendleft(entry)
                logger.info(
                    "Scheduler: ⭐ %s (%s) priority-queued on %s for %s (position 1)",
                    project_id, project_priority,
                    resolved, stage.value,
                )
            else:
                queue.append(entry)
                logger.info(
                    "Scheduler: %s queued on %s for %s (position %d)",
                    project_id, resolved,
                    stage.value, len(queue),
                )

    def cancel(self, project_id: str) -> None:
        """Remove a project from all queues (e.g., user cancelled the pipeline)."""
        with self._lock:
            for node_id, queue in self._queues.items():
                before = len(queue)
                self._queues[node_id] = deque(
                    e for e in queue if e.project_id != project_id
                )
                if len(self._queues[node_id]) < before:
                    logger.info("Scheduler: cancelled %s from queue %s", project_id, node_id)
            # Also release any held slots
            for slot in self._slots.values():
                slot.release(project_id)

    def clean_locks(self, project_id: Optional[str] = None) -> None:
        """Forcefully purge active tasks to self-heal from ghost locks."""
        with self._lock:
            for nid, slot in self._slots.items():
                if project_id:
                    if project_id in slot.active_stages:
                        logger.warning("Scheduler: forcefully clearing ghost lock %s from node %s", project_id, nid)
                        slot.active_stages.pop(project_id)
                else:
                    if slot.active_stages:
                        logger.warning("Scheduler: forcefully clearing ALL ghost locks from node %s", nid)
                        slot.active_stages.clear()
            # Phase 91: Clear stale swarm window
            if self._swarm_window:
                if project_id and self._swarm_window["project_id"] == project_id:
                    logger.warning("Scheduler: clearing ghost swarm window for %s", project_id)
                    self._swarm_window = None
                elif not project_id:
                    logger.warning("Scheduler: clearing ghost swarm window (full purge)")
                    self._swarm_window = None

    def is_held_by(self, project_id: str) -> bool:
        """Check if a project currently holds any scheduler slot."""
        with self._lock:
            for slot in self._slots.values():
                if project_id in slot.active_stages:
                    return True
            return False

    # ── Node resolution (Phase 56) ─────────────────────────────────

    def resolve_node_for_model(
        self, provider: str, model: str, endpoint_id: str,
    ) -> str:
        """Determine which compute node a model runs on.

        Cloud providers always route to ``cloud:<endpoint_id>``.
        For Ollama/LM Studio, ``is_cloud_model_via_ollama()`` decides
        whether the model is cloud-proxied (e.g. kimi, gemini) or local.
        """
        if provider.lower() in CLOUD_PROVIDERS:
            node = f"cloud:{endpoint_id}"
            logger.info(
                "Node resolution: %s/%s → %s (native cloud provider)",
                provider, model, node,
            )
            return node

        # Ollama / LM Studio: check if this model is cloud-proxied
        try:
            from prep.core.batch_profiles import is_cloud_model_via_ollama
            if is_cloud_model_via_ollama(provider, model):
                node = f"cloud:{endpoint_id}"
                logger.info(
                    "Node resolution: %s/%s → %s (cloud-proxied via Ollama)",
                    provider, model, node,
                )
                return node
        except ImportError:
            pass

        node = f"local:{endpoint_id}"
        logger.info(
            "Node resolution: %s/%s → %s (local VRAM-constrained)",
            provider, model, node,
        )
        return node

    # ── Batch concurrency budget (Phase 56B / 72B weighted) ────────

    def _weighted_share(
        self, slot: ComputeSlot, project_id: Optional[str],
    ) -> int:
        """Compute weighted fair-share budget for a project on a slot.

        Phase 72B weighted model:
          - Exclusive ⭐ gets the FULL budget — all other projects wait.
          - Boost ⭐ projects get 2× weight; normal projects get 1× weight.
          - Budget is divided proportionally, with remainders going to
            priority projects first.

        Examples (10 concurrency, 4 active):
          - 2 boost + 2 normal → weights = 2+2+1+1 = 6
            → boost: floor(10×2/6) = 3, normal: floor(10×1/6) = 1
            → total = 3+3+1+1 = 8, remainder 2 → boost gets 4+3+1+1 = 9, last 1 to normal
          - 0 boost + 4 normal → equal split: 10÷4 = 2 each, remainder 2 to first

        Examples (6 concurrency, 4 active):
          - 2 boost + 2 normal → weights = 6
            → boost: floor(6×2/6) = 2, normal: floor(6×1/6) = 1
            → total = 2+2+1+1 = 6 ✓

        Returns at least 1.
        """
        # Phase 96B: Use the full dynamic_capacity — no N-1 headroom reservation.
        # The earlier N-1 reservation for "interactive queries" was over-cautious
        # and halved concurrency in small-capacity cases (max=3 → budget=2).
        # The AIMD congestion control already handles overload via backoff, so
        # we don't need a static headroom reservation on top of it.
        full_budget = max(1, slot.dynamic_capacity)
        active_count = max(1, slot.current_load)

        proj_level = self._priority_projects.get(project_id, "none") if project_id else "none"

        # Exclusive gets everything
        if proj_level == "exclusive":
            return full_budget

        # Single project gets everything
        if active_count == 1:
            return full_budget

        # Phase 91: Low-resource guardrail — with ≤3 capacity, boost
        # weighting is meaningless (difference between 2 and 1 worker).
        # Just split equally. Exclusive still works above.
        if slot.dynamic_capacity <= 3:
            return max(1, full_budget // active_count)

        # Count how many active projects are boosted vs normal
        num_boost = 0
        num_normal = 0
        for pid in slot.active_stages:
            if self._priority_projects.get(pid, "none") in ("boost", "exclusive"):
                num_boost += 1
            else:
                num_normal += 1

        # If no boost projects, equal split
        if num_boost == 0:
            share = max(1, full_budget // active_count)
            return share

        # Weighted split: boost gets 2× weight, normal gets 1×
        total_weight = (2 * num_boost) + (1 * num_normal)
        if total_weight <= 0:
            return max(1, full_budget // active_count)

        is_boost = proj_level == "boost"
        weight = 2 if is_boost else 1
        share = max(1, (full_budget * weight) // total_weight)

        # Distribute remainder to boost projects
        allocated = (
            (full_budget * 2 // total_weight) * num_boost
            + (full_budget * 1 // total_weight) * num_normal
        )
        remainder = full_budget - allocated
        if remainder > 0 and is_boost:
            # Spread remainder across boost projects
            extra = max(0, remainder // num_boost)
            share += extra

        return max(1, share)

    def available_batch_workers(
        self, node_id: Optional[str] = None, *, project_id: Optional[str] = None,
    ) -> int:
        """How many concurrent batch API calls a project can use on a node.

        Phase 72B: Uses weighted fair-share.  Boost ⭐ projects get 2×
        the workers of non-priority projects.  Exclusive ⭐ gets the
        full budget.  Returns at least 1.
        """
        with self._lock:
            nid = node_id or self._default_node_id
            if nid not in self._slots:
                return 1
            slot = self._slots[nid]
            return self._weighted_share(slot, project_id)

    def available_batch_workers_for_provider(
        self, provider: str, model: str | None = None,
        *, project_id: Optional[str] = None,
    ) -> Optional[int]:
        """Auto-discover the batch worker budget for a provider.

        **Phase 72 fix**: First checks which node the ``project_id``
        has *actually* acquired (by scanning ``active_stages``), and
        returns the budget for that exact node.  This eliminates the
        prefix-guessing path that could silently downgrade a cloud
        model to local concurrency (= 1) when the model name didn't
        match ``is_cloud_model_via_ollama()`` heuristics.

        Falls back to prefix-based discovery only when the project
        isn't found in any active slot (e.g. pipeline hasn't called
        ``acquire()`` yet).

        If ``project_id`` matches the priority ⭐ project, returns the
        full node capacity instead of the shared budget.

        This enables ``get_batch_concurrency()`` to work without
        callers explicitly passing ``node_id``.
        """
        with self._lock:
            if not self._slots:
                return None

            proj_level = self._priority_projects.get(project_id, "none") if project_id else "none"

            # ── Fast path: find the exact node this project acquired ──
            if project_id:
                for nid, slot in self._slots.items():
                    if project_id not in slot.active_stages:
                        continue
                    # Found! Use weighted share on THIS node.
                    return self._weighted_share(slot, project_id)

            # ── Fallback: prefix-based discovery ──────────────────────
            # Used when project_id is unknown or hasn't acquired yet.
            is_cloud = provider in CLOUD_PROVIDERS
            if not is_cloud and model:
                try:
                    from prep.core.batch_profiles import is_cloud_model_via_ollama
                    if is_cloud_model_via_ollama(provider, model):
                        is_cloud = True
                except ImportError:
                    pass
            prefix = "cloud:" if is_cloud else "local:"

            # Find all matching nodes that have active work
            budget = None
            for nid, slot in self._slots.items():
                if not nid.startswith(prefix):
                    continue
                if proj_level == "exclusive":
                    # Phase 96B: no N-1 headroom
                    cap = max(1, slot.dynamic_capacity)
                    if budget is None or cap < budget:
                        budget = cap
                    continue
                if slot.current_load == 0:
                    continue  # No work on this node
                node_budget = self._weighted_share(slot, project_id)
                if budget is None or node_budget < budget:
                    budget = node_budget

            # If no active nodes found, check if any matching nodes exist
            # and return their full capacity (happens when pipeline
            # hasn't called acquire yet but batch is about to start)
            if budget is None:
                for nid, slot in self._slots.items():
                    if nid.startswith(prefix):
                        # Phase 96B: no N-1 headroom
                        cap = max(1, slot.dynamic_capacity)
                        if budget is None or cap < budget:
                            budget = cap

            return budget

    def full_budget_for_swarm(
        self, provider: str, model: str | None = None,
        *, project_id: str | None = None,
    ) -> int | None:
        """Return the FULL undivided concurrency budget for swarm stages.

        Phase 79: Swarm orchestration (coordinator → fan-out → synthesis)
        benefits from maximum parallelism.  This method bypasses the
        weighted fair-share division that ``available_batch_workers*``
        applies, returning ``slot.max_concurrent`` directly.

        The stage still occupies its scheduler slot and waits its turn
        in the queue — only the *concurrency division* is bypassed,
        not the *scheduling*.

        Falls back to the same node discovery as
        ``available_batch_workers_for_provider``.  Returns None if no
        matching node is found.

        Phase 91: Returns None if budget < 3 (min_workers gate).
        Swarm-capable stages need at least 3 workers for fan-out
        synthesis to be worthwhile. Caller should fall back to
        non-swarm sequential mode.
        """
        with self._lock:
            if not self._slots:
                return None

            # Fast path: find the exact node this project acquired
            if project_id:
                for nid, slot in self._slots.items():
                    if project_id in slot.active_stages:
                        # Phase 96B: no N-1 headroom — use full dynamic_capacity
                        budget = max(1, slot.dynamic_capacity)
                        # Phase 91: min_workers gate
                        if budget < 3:
                            logger.info(
                                "[Swarm] Budget %d < min_workers 3 for %s on %s — "
                                "falling back to non-swarm mode",
                                budget, project_id, nid,
                            )
                            return None
                        logger.info(
                            "[Swarm] Full budget for project %s on node %s: %d (bypassing fair-share)",
                            project_id, nid, budget,
                        )
                        return budget

            # Fallback: prefix-based discovery (same as available_batch_workers_for_provider)
            is_cloud = provider in CLOUD_PROVIDERS
            if not is_cloud and model:
                try:
                    from prep.core.batch_profiles import is_cloud_model_via_ollama
                    if is_cloud_model_via_ollama(provider, model):
                        is_cloud = True
                except ImportError:
                    pass
            prefix = "cloud:" if is_cloud else "local:"

            for nid, slot in self._slots.items():
                if nid.startswith(prefix):
                    # Phase 96B: no N-1 headroom
                    budget = max(1, slot.dynamic_capacity)
                    # Phase 91: min_workers gate
                    if budget < 3:
                        logger.info(
                            "[Swarm] Budget %d < min_workers 3 via prefix %s on %s — "
                            "falling back to non-swarm mode",
                            budget, prefix, nid,
                        )
                        return None
                    logger.info(
                        "[Swarm] Full budget via prefix %s on node %s: %d",
                        prefix, nid, budget,
                    )
                    return budget

            return None

    def max_llm_budget(self) -> int:
        """Max ``dynamic_capacity`` across non-embedding LLM slots.

        Phase 82 completion (2026-04-20): used by
        ``prep.core.llm_client._get_llm_concurrency`` to scale per-stage
        ``ThreadPoolExecutor`` sizing with the AIMD-discovered budget —
        the same signal ``get_batch_concurrency`` and
        ``full_budget_for_swarm`` consume.

        Returns 1 when no LLM slots exist yet (e.g. daemon startup before
        ``configure_node`` runs). The embedding slot is excluded because
        its capacity is memory-driven, not AIMD-driven.
        """
        with self._lock:
            budget = 1
            for nid, slot in self._slots.items():
                if nid == "__embedding__":
                    continue
                if slot.dynamic_capacity > budget:
                    budget = slot.dynamic_capacity
            return budget

    def concurrent_workers_for_project(
        self, project_id: str, stage: Optional[str] = None,
    ) -> Tuple[int, Optional[str]]:
        """Return (concurrent_worker_count, node_id) for a project.

        Used by the AI Gateway UI to display how many parallel LLM
        calls a stage is making.  Returns (1, None) if the project
        isn't found in any active slot.

        Phase 82: When ``stage`` is a swarm-capable stage and the
        model supports swarm, returns the full undivided budget
        instead of the weighted fair-share.
        """
        with self._lock:
            for nid, slot in self._slots.items():
                if project_id not in slot.active_stages:
                    continue
                # Phase 82: Check if this is an active swarm stage
                if stage and stage in SWARM_CAPABLE_STAGES:
                    try:
                        from prep.services.pipeline._model_resolution import resolve_model_for_stage
                        resolved = resolve_model_for_stage(project_id, stage)
                        if resolved and is_swarm_active_for_stage(stage, *resolved):
                            budget = max(1, slot.dynamic_capacity - 1)
                            return budget, nid
                    except Exception:
                        pass  # Fall through to weighted share
                return self._weighted_share(slot, project_id), nid
        return 1, None

    def status(self) -> Dict:
        """Return scheduler status for diagnostics/UI."""
        with self._lock:
            nodes = {}
            for nid, slot in self._slots.items():
                queue = self._queues.get(nid, deque())
                nodes[nid] = {
                    "max_concurrent": slot.max_concurrent,
                    "dynamic_capacity": slot.dynamic_capacity,
                    "current_load": slot.current_load,
                    "aimd_mode": slot.mode,
                    "current_limit": slot.current_limit,
                    "in_flight_requests": slot.in_flight_requests,
                    "discovered_ceiling": slot.discovered_ceiling,
                    "locked_until": slot.ceiling_locked_until or None,
                    "state": _derive_node_state(
                        discovered_ceiling=slot.discovered_ceiling,
                        ceiling_locked_until=slot.ceiling_locked_until,
                        last_backoff_time=slot._last_backoff_time,
                        backoff_cooldown_s=self._BACKOFF_COOLDOWN_S,
                    ),
                    "active": dict(slot.active_stages),
                    "queued": [
                        {
                            "project_id": e.project_id,
                            "stage": e.stage.value,
                            "waiting_seconds": round(time.time() - e.enqueued_at, 1),
                        }
                        for e in queue
                    ],
                }
            # Phase 72B: Report all priority projects, with backward-compat fields
            priority = {
                "project_id": self.priority_project_id,  # backward compat
                "level": self.priority_level,             # backward compat
                "projects": dict(self._priority_projects),
            }
            # Phase 91: Swarm window state
            swarm: Optional[Dict[str, Any]] = None
            if self._swarm_window:
                w = self._swarm_window
                now = time.time()
                swarm = {
                    "project_id": w["project_id"],
                    "stage": w["stage"].value if hasattr(w["stage"], 'value') else str(w["stage"]),
                    "node_id": w["node_id"],
                    "elapsed_seconds": round(now - w["started_at"], 1),
                    "drain_targets": {
                        pid: round(now - started, 1)
                        for pid, started in w.get("drain_targets", {}).items()
                    },
                }
            cooldown_remaining = max(0.0, self._swarm_cooldown_until - time.time())
            return {
                "nodes": nodes,
                "priority": priority,
                "swarm_window": swarm,
                "swarm_cooldown_remaining": round(cooldown_remaining, 1),
                "drain_timeout_seconds": self._drain_timeout_seconds,
            }

    def sync_endpoint_concurrency(self) -> None:
        """Live-sync endpoint concurrency from settings into the scheduler.

        Phase 72: Called whenever LLM config is saved (e.g. user edits
        endpoint concurrency in the UI).  Unlike ``load_from_settings()``,
        this only updates existing node concurrency limits — it doesn't
        rebuild priority, embedding, or legacy fallback config.

        This enables changing concurrency from 3→10 without restarting.
        """
        try:
            from prep.services.settings_store import settings
            llm_config = settings.get("llm_config") or {}
        except Exception:
            return

        endpoints = llm_config.get("saved_endpoints", [])
        if not endpoints:
            return

        updated = 0
        for ep in endpoints:
            ep_id = ep.get("id")
            if not ep_id:
                continue
            provider = ep.get("provider", "ollama").lower()
            local_c = max(1, int(ep.get("local_concurrency", 1)))
            cloud_c = max(0, int(ep.get("cloud_concurrency", 1)))

            if provider in CLOUD_PROVIDERS:
                self.configure_node(f"cloud:{ep_id}", max(1, cloud_c))
                updated += 1
            else:
                self.configure_node(f"local:{ep_id}", local_c)
                effective_cloud_c = cloud_c if cloud_c > 0 else 3
                self.configure_node(f"cloud:{ep_id}", effective_cloud_c)
                updated += 1

        if updated > 0:
            logger.info(
                "Scheduler: live-synced concurrency for %d endpoint(s)",
                updated,
            )

    def load_from_settings(self) -> None:
        """Load compute node configuration from the settings store.

        Phase 56: Auto-creates per-endpoint compute nodes from each
        saved endpoint's ``local_concurrency`` / ``cloud_concurrency``
        fields.  Falls back to legacy ``compute_nodes[]`` or the
        single ``llm_concurrency`` default.
        """
        try:
            from prep.services.settings_store import settings
            llm_config = settings.get("llm_config") or {}

            # Phase 56: endpoint-aware nodes from saved endpoints
            endpoints = llm_config.get("saved_endpoints", [])
            created = 0
            for ep in endpoints:
                ep_id = ep.get("id")
                if not ep_id:
                    continue
                provider = ep.get("provider", "ollama").lower()
                local_c = max(1, int(ep.get("local_concurrency", 1)))
                cloud_c = max(0, int(ep.get("cloud_concurrency", 1)))

                if provider in CLOUD_PROVIDERS:
                    # Native cloud: only has a cloud node
                    self.configure_node(f"cloud:{ep_id}", max(1, cloud_c))
                    created += 1
                else:
                    # Ollama / LM Studio: local node + cloud node for proxied models
                    self.configure_node(f"local:{ep_id}", local_c)
                    created += 1
                    # Always create a cloud node for Ollama endpoints — cloud-proxied
                    # models (kimi, gemini, etc.) need separate scheduling from local
                    # VRAM-constrained models.  Default to 3 if not explicitly set.
                    effective_cloud_c = cloud_c if cloud_c > 0 else 3
                    self.configure_node(f"cloud:{ep_id}", effective_cloud_c)
                    created += 1

            # Legacy fallback: explicit compute_nodes[] array
            nodes = llm_config.get("compute_nodes", [])

            if created > 0:
                logger.info(
                    "Scheduler: created %d compute node(s) from %d endpoint(s)",
                    created, len(endpoints),
                )
            elif nodes:
                for node in nodes:
                    self.configure_node(
                        node_id=node["id"],
                        max_concurrent=node.get("max_concurrent", 1),
                    )
                logger.info(
                    "Scheduler: loaded %d compute node(s) from settings",
                    len(nodes),
                )
            else:
                # Final fallback: single default node
                pipeline_cfg = settings.get("pipeline_config") or {}
                concurrency = max(1, int(
                    pipeline_cfg.get("llm_concurrency_fast",
                    pipeline_cfg.get("llm_concurrency", 1))
                ))
                self.set_default_concurrency(concurrency)

            # ── Auto-detect embedding concurrency from system memory ──
            try:
                from prep.core.context_config import detect_system_memory_gb
                mem_gb = detect_system_memory_gb()
                if mem_gb >= 65:
                    embed_concurrent = 2
                else:
                    embed_concurrent = 1  # Safe for all machines
                self.configure_embedding_concurrency(embed_concurrent)
                logger.info(
                    "Scheduler: detected %.0f GB RAM → embedding concurrency = %d",
                    mem_gb, embed_concurrent,
                )
            except Exception:
                self.configure_embedding_concurrency(1)
                logger.debug("Scheduler: memory detection failed, embedding concurrency = 1")

            # ── Restore saved priority from project configs ───────────
            # Phase 72B: Restore ALL starred projects, not just the first one.
            # The old `break` caused only one project to get priority on restart.
            #
            # Phase 96 follow-up: Only restore priority for ACTIVE projects.
            # An inactive project's exclusive flag was leaking through restart
            # and silently affecting active projects' acquisition behavior
            # (the holder isn't running anything, but its presence in
            # _priority_projects skews wave calculations and makes the user
            # think exclusive is "stuck on").
            try:
                from prep.core.project_registry import ProjectRegistry
                registry = ProjectRegistry()
                restored_count = 0
                skipped_inactive = 0
                for proj in registry.list_projects():
                    pcfg = proj.config if isinstance(proj.config, dict) else {}
                    level = pcfg.get("priority_level")
                    if not level and pcfg.get("is_starred"):
                        level = "boost"
                    if level and level != "none":
                        # Skip if the project is marked inactive — its
                        # priority shouldn't affect anyone else.
                        if pcfg.get("active") is False:
                            skipped_inactive += 1
                            continue
                        self.set_priority(proj.id, level)
                        restored_count += 1
                if restored_count > 0:
                    logger.info(
                        "Scheduler: restored priority for %d project(s): %s",
                        restored_count,
                        ", ".join(f"{pid}={lvl}" for pid, lvl in self._priority_projects.items()),
                    )
                if skipped_inactive > 0:
                    logger.info(
                        "Scheduler: skipped %d inactive project(s) during "
                        "priority restore (their priority is preserved in "
                        "config and will reapply on activation)",
                        skipped_inactive,
                    )
            except Exception:
                logger.debug("Scheduler: could not restore priority from project configs", exc_info=True)

        except Exception:
            logger.debug("Scheduler: failed to load settings (using defaults)", exc_info=True)
            self.set_default_concurrency(1)


# ── Module-level singleton ───────────────────────────────────────
pipeline_scheduler = PipelineScheduler()
