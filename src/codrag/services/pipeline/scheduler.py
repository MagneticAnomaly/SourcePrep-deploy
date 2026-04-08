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
    from codrag.services.pipeline.scheduler import pipeline_scheduler
    
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
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Literal, Optional, Set, Tuple

# Priority levels for the star system (three-tier)
PriorityLevel = Literal["none", "boost", "exclusive"]

from .stages import QueueType, STAGE_QUEUE_TYPE, StageId

logger = logging.getLogger(__name__)

# Stages that can use swarm orchestration (coordinator → fan-out → synthesis).
# Shared constant — imported by queue.py and llm.py routers to avoid duplication.
SWARM_CAPABLE_STAGES: frozenset = frozenset({"group_reasoning", "clustering", "atlas"})


def is_swarm_active_for_stage(stage: str, provider: str, model: str) -> bool:
    """Check if a stage would use swarm orchestration with the given model.

    Mirrors the decision in GroupReasoningEngine.run(), ClusterSynthesizer,
    and AtlasGenerator — minus the min_groups check (not available at query time).
    """
    if stage not in SWARM_CAPABLE_STAGES:
        return False
    try:
        from codrag.core.swarm_registry import get_swarm_tier
        from codrag.services.settings_store import settings
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

    # Latency-Aware AIMD (Phase 82)
    current_limit: int = 5
    mode: Literal["jumpstart", "congestion_avoidance"] = "jumpstart"
    success_streak: int = 0
    _last_backoff_time: float = 0.0

    def __post_init__(self):
        if self.max_concurrent < self.current_limit:
            self.current_limit = max(1, self.max_concurrent)
            self.mode = "congestion_avoidance"

    @property
    def current_load(self) -> int:
        return len(self.active_stages)

    @property
    def dynamic_capacity(self) -> int:
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


class PipelineScheduler:
    """Manages compute slot allocation across multiple project pipelines.

    Thread-safe. Uses a simple FIFO queue per compute node.
    """

    # Dedicated embedding slot — separate from LLM nodes
    _EMBEDDING_NODE_ID = "__embedding__"

    def __init__(self) -> None:
        self._lock = threading.Lock()
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

    # ── Configuration ─────────────────────────────────────────────

    def configure_node(self, node_id: str, max_concurrent: int) -> None:
        """Register or update a compute node's concurrency limit."""
        with self._lock:
            if node_id in self._slots:
                self._slots[node_id].max_concurrent = max(1, max_concurrent)
            else:
                self._slots[node_id] = ComputeSlot(
                    node_id=node_id,
                    max_concurrent=max(1, max_concurrent),
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
                self._slots[self._EMBEDDING_NODE_ID].max_concurrent = self._embedding_max_concurrent
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
            if old_level != level:
                logger.info("Scheduler: priority %s → %s (%s)",
                            project_id, level,
                            f"was {old_level}" if old_level else "new")

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
        with self._lock:
            if node_id not in self._slots:
                return
            self._record_throughput_for_slot(self._slots[node_id], queue_time_ms, rate_limit_remaining, is_429_or_timeout)

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
                from codrag.core.batch_profiles import is_cloud_model_via_ollama
                if is_cloud_model_via_ollama(provider, model):
                    is_cloud = True
            except ImportError:
                pass
        prefix = "cloud:" if is_cloud else "local:"
        
        with self._lock:
            # Report to all matching slots
            for nid, slot in self._slots.items():
                if nid.startswith(prefix):
                    self._record_throughput_for_slot(slot, queue_time_ms, rate_limit_remaining, is_429_or_timeout)

    def _record_throughput_for_slot(
        self,
        slot: ComputeSlot,
        queue_time_ms: float = 0.0,
        rate_limit_remaining: Optional[int] = None,
        is_429_or_timeout: bool = False,
    ) -> None:
        """Internal helper to apply AIMD logic to a single slot.

        Works for ALL providers:
        - Ollama: uses queue_time_ms (wall clock - eval/prompt/load durations)
        - Cloud APIs: uses rate_limit_remaining headers + 429/timeout signals
        - Both: queue_time_ms > 2000ms triggers congestion detection
        """
        # Step 1: Clamp hard limit from cloud rate-limit headers (when available)
        if rate_limit_remaining is not None and rate_limit_remaining >= 0:
            safe_limit = max(1, rate_limit_remaining - 2)
            if slot.max_concurrent > safe_limit:
                slot.max_concurrent = safe_limit
                if slot.current_limit > safe_limit:
                    slot.current_limit = safe_limit

        # Step 2: Congestion detection (works for ALL providers)
        if is_429_or_timeout or queue_time_ms > 2000.0:
            now = time.time()
            # Cooldown so we don't back off 10 times for a single congested batch
            if now - slot._last_backoff_time > 2.0:
                slot.mode = "congestion_avoidance"
                slot.success_streak = 0

                # Multiplicative Decrease: Half limit, or current in-flight
                in_flight = slot.current_load
                new_limit = max(1, min(slot.current_limit // 2, in_flight))

                if slot.current_limit > new_limit:
                    logger.warning(
                        "Scheduler: Node %s congested (queue_ms=%.1f, 429/timeout=%s). "
                        "Backing off limit %d -> %d",
                        slot.node_id, queue_time_ms, is_429_or_timeout,
                        slot.current_limit, new_limit,
                    )
                    slot.current_limit = new_limit
                slot._last_backoff_time = now
        else:
            # Step 3: Additive Increase or Jumpstart (no congestion detected)
            slot.success_streak += 1

            batch_size = max(1, slot.current_limit)
            if slot.success_streak >= batch_size:
                slot.success_streak = 0
                if slot.current_limit < slot.max_concurrent:
                    if slot.mode == "jumpstart":
                        new_limit = min(slot.max_concurrent, slot.current_limit * 2)
                        logger.info(
                            "Scheduler: Node %s jumpstart %d -> %d",
                            slot.node_id, slot.current_limit, new_limit,
                        )
                        slot.current_limit = new_limit
                    else:
                        new_limit = min(slot.max_concurrent, slot.current_limit + 1)
                        slot.current_limit = new_limit

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
            self._slots[nid] = ComputeSlot(
                node_id=nid,
                max_concurrent=self._default_max_concurrent,
            )
            self._queues[nid] = deque()
        return self._slots[nid]

    def _get_queue(self, node_id: Optional[str] = None) -> Deque[QueueEntry]:
        """Get or create a queue for a node."""
        nid = node_id or self._default_node_id
        if nid not in self._queues:
            self._queues[nid] = deque()
        return self._queues[nid]

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
        or an exclusive-priority project is blocking.
        Caller should enqueue the pipeline if this returns False.
        """
        if not self._needs_slot(stage):
            return True  # No slot needed
        resolved = self._resolve_node_for_stage(stage, node_id)
        with self._lock:
            slot = self._get_slot(resolved)
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
            # Check if there's a queued pipeline waiting for this node
            queue = self._get_queue(resolved)
            if queue and slot.has_capacity:
                entry = queue.popleft()
                logger.info(
                    "Scheduler: dequeuing %s for %s (waited %.1fs)",
                    entry.project_id, entry.stage.value,
                    time.time() - entry.enqueued_at,
                )
                return entry
            return None

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
            # Don't double-enqueue
            for entry in queue:
                if entry.project_id == project_id:
                    logger.debug(
                        "Scheduler: %s already queued on %s",
                        project_id, resolved,
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
            from codrag.core.batch_profiles import is_cloud_model_via_ollama
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
        # Phase 82: Reserve N-1 headroom for interactive queries when allocating batches
        # except when dynamic_capacity is merely 1, then we use 1.
        full_budget = max(1, slot.dynamic_capacity - 1)
        active_count = max(1, slot.current_load)

        proj_level = self._priority_projects.get(project_id, "none") if project_id else "none"

        # Exclusive gets everything
        if proj_level == "exclusive":
            return full_budget

        # Single project gets everything
        if active_count == 1:
            return full_budget

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
                    from codrag.core.batch_profiles import is_cloud_model_via_ollama
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
                    cap = max(1, slot.dynamic_capacity - 1)
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
                        cap = max(1, slot.dynamic_capacity - 1)
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
        """
        with self._lock:
            if not self._slots:
                return None

            # Fast path: find the exact node this project acquired
            if project_id:
                for nid, slot in self._slots.items():
                    if project_id in slot.active_stages:
                        budget = max(1, slot.dynamic_capacity - 1)
                        logger.info(
                            "[Swarm] Full budget for project %s on node %s: %d (bypassing fair-share)",
                            project_id, nid, budget,
                        )
                        return budget

            # Fallback: prefix-based discovery (same as available_batch_workers_for_provider)
            is_cloud = provider in CLOUD_PROVIDERS
            if not is_cloud and model:
                try:
                    from codrag.core.batch_profiles import is_cloud_model_via_ollama
                    if is_cloud_model_via_ollama(provider, model):
                        is_cloud = True
                except ImportError:
                    pass
            prefix = "cloud:" if is_cloud else "local:"

            for nid, slot in self._slots.items():
                if nid.startswith(prefix):
                    budget = max(1, slot.dynamic_capacity - 1)
                    logger.info(
                        "[Swarm] Full budget via prefix %s on node %s: %d",
                        prefix, nid, budget,
                    )
                    return budget

            return None

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
                        from codrag.services.pipeline._model_resolution import resolve_model_for_stage
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
            return {"nodes": nodes, "priority": priority}

    def sync_endpoint_concurrency(self) -> None:
        """Live-sync endpoint concurrency from settings into the scheduler.

        Phase 72: Called whenever LLM config is saved (e.g. user edits
        endpoint concurrency in the UI).  Unlike ``load_from_settings()``,
        this only updates existing node concurrency limits — it doesn't
        rebuild priority, embedding, or legacy fallback config.

        This enables changing concurrency from 3→10 without restarting.
        """
        try:
            from codrag.services.settings_store import settings
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
            from codrag.services.settings_store import settings
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
                from codrag.core.context_config import detect_system_memory_gb
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
            try:
                from codrag.core.project_registry import ProjectRegistry
                registry = ProjectRegistry()
                restored_count = 0
                for proj in registry.list_projects():
                    pcfg = proj.config if isinstance(proj.config, dict) else {}
                    level = pcfg.get("priority_level")
                    if not level and pcfg.get("is_starred"):
                        level = "boost"
                    if level and level != "none":
                        self.set_priority(proj.id, level)
                        restored_count += 1
                if restored_count > 0:
                    logger.info(
                        "Scheduler: restored priority for %d project(s): %s",
                        restored_count,
                        ", ".join(f"{pid}={lvl}" for pid, lvl in self._priority_projects.items()),
                    )
            except Exception:
                logger.debug("Scheduler: could not restore priority from project configs", exc_info=True)

        except Exception:
            logger.debug("Scheduler: failed to load settings (using defaults)", exc_info=True)
            self.set_default_concurrency(1)


# ── Module-level singleton ───────────────────────────────────────
pipeline_scheduler = PipelineScheduler()
