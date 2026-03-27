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

# Providers that are always cloud — never compete for local VRAM.
CLOUD_PROVIDERS = {"openai", "anthropic", "google", "azure-openai"}


@dataclass
class ComputeSlot:
    """Tracks current load on a compute node."""
    node_id: str
    max_concurrent: int
    active_stages: Dict[str, str] = field(default_factory=dict)  # project_id -> stage_id

    @property
    def current_load(self) -> int:
        return len(self.active_stages)

    @property
    def has_capacity(self) -> bool:
        return self.current_load < self.max_concurrent

    def acquire(self, project_id: str, stage_id: str) -> bool:
        """Try to acquire a slot. Returns True if successful."""
        if not self.has_capacity:
            return False
        self.active_stages[project_id] = stage_id
        return True

    def release(self, project_id: str) -> bool:
        """Release a slot. Returns True if it was held."""
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
        # Three-tier priority: none → boost → exclusive
        self._priority_project_id: Optional[str] = None
        self._priority_level: PriorityLevel = "none"

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

    def set_priority(
        self,
        project_id: Optional[str],
        level: PriorityLevel = "boost",
    ) -> None:
        """Set the global priority project.

        Levels:
          ``none``      — no special treatment (clears priority).
          ``boost``     — queue-jump + proportional share of cloud budget.
          ``exclusive`` — queue-jump + FULL cloud budget; other projects'
                          LLM stages are queued until exclusive finishes.

        Only one project can hold priority at a time.  Setting a new
        project automatically clears the previous one.
        """
        with self._lock:
            old_id = self._priority_project_id
            old_level = self._priority_level
            if level == "none" or project_id is None:
                self._priority_project_id = None
                self._priority_level = "none"
            else:
                self._priority_project_id = project_id
                self._priority_level = level
            if (project_id, level) != (old_id, old_level):
                label = f"{project_id} ({level})" if project_id else "(none)"
                logger.info("Scheduler: priority → %s", label)

    @property
    def priority_project_id(self) -> Optional[str]:
        return self._priority_project_id

    @property
    def priority_level(self) -> PriorityLevel:
        return self._priority_level

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
        if queue_type == QueueType.EMBEDDING:
            return self._embedding_uses_llm
        return True  # LLM

    # ── Public API ────────────────────────────────────────────────

    def can_start(
        self,
        project_id: str,
        stage: StageId,
        node_id: Optional[str] = None,
    ) -> bool:
        """Check if a stage can start given current compute load.

        Returns True if:
          - Stage doesn't need a slot (Rust, or NativeEmbedder)
          - The compute node has available capacity
          - No exclusive project is occupying the node (unless we ARE
            the exclusive project)
        """
        if not self._needs_slot(stage):
            return True
        with self._lock:
            slot = self._get_slot(node_id)
            if not slot.has_capacity:
                return False
            # Exclusive gate: if another project holds exclusive priority
            # and is active on this node, queue us instead of starting.
            if (
                self._priority_level == "exclusive"
                and self._priority_project_id
                and self._priority_project_id != project_id
                and self._priority_project_id in slot.active_stages
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
        with self._lock:
            slot = self._get_slot(node_id)
            # Exclusive gate: if another project holds exclusive priority
            # and is active on this node, block.
            if (
                self._priority_level == "exclusive"
                and self._priority_project_id
                and self._priority_project_id != project_id
                and self._priority_project_id in slot.active_stages
            ):
                return False
            ok = slot.acquire(project_id, stage.value)
            if ok:
                logger.info(
                    "Scheduler: %s acquired slot on %s for %s (%d/%d)",
                    project_id, slot.node_id, stage.value,
                    slot.current_load, slot.max_concurrent,
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
        with self._lock:
            slot = self._get_slot(node_id)
            released = slot.release(project_id)
            if released:
                logger.info(
                    "Scheduler: %s released slot on %s (%d/%d)",
                    project_id, slot.node_id,
                    slot.current_load, slot.max_concurrent,
                )
            # Check if there's a queued pipeline waiting for this node
            queue = self._get_queue(node_id)
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
        with self._lock:
            queue = self._get_queue(node_id)
            # Don't double-enqueue
            for entry in queue:
                if entry.project_id == project_id:
                    logger.debug(
                        "Scheduler: %s already queued on %s",
                        project_id, node_id or self._default_node_id,
                    )
                    return
            entry = QueueEntry(project_id=project_id, stage=stage)
            # Priority projects (boost or exclusive) go to front of queue
            if self._priority_project_id and project_id == self._priority_project_id:
                queue.appendleft(entry)
                logger.info(
                    "Scheduler: ⭐ %s (%s) priority-queued on %s for %s (position 1)",
                    project_id, self._priority_level,
                    node_id or self._default_node_id, stage.value,
                )
            else:
                queue.append(entry)
                logger.info(
                    "Scheduler: %s queued on %s for %s (position %d)",
                    project_id, node_id or self._default_node_id,
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
            return f"cloud:{endpoint_id}"

        # Ollama / LM Studio: check if this model is cloud-proxied
        try:
            from codrag.core.batch_profiles import is_cloud_model_via_ollama
            if is_cloud_model_via_ollama(provider, model):
                return f"cloud:{endpoint_id}"
        except ImportError:
            pass

        return f"local:{endpoint_id}"

    # ── Batch concurrency budget (Phase 56B) ──────────────────────

    def available_batch_workers(
        self, node_id: Optional[str] = None, *, project_id: Optional[str] = None,
    ) -> int:
        """How many concurrent batch API calls a project can use on a node.

        Divides the node's ``max_concurrent`` by the number of active
        projects.  Boost priority gets proportional share; exclusive
        priority gets the full budget.

        Returns at least 1.
        """
        with self._lock:
            nid = node_id or self._default_node_id
            if nid not in self._slots:
                return 1
            slot = self._slots[nid]
            full_budget = max(1, slot.max_concurrent)
            active_count = max(1, slot.current_load)
            # Exclusive ⭐ project gets the full budget unconditionally
            if (
                project_id
                and self._priority_project_id == project_id
                and self._priority_level == "exclusive"
            ):
                return full_budget
            if active_count == 1:
                return full_budget
            return max(1, slot.max_concurrent // active_count)

    def available_batch_workers_for_provider(
        self, provider: str, model: str | None = None,
        *, project_id: Optional[str] = None,
    ) -> Optional[int]:
        """Auto-discover the batch worker budget for a provider.

        Searches active compute nodes for ones matching the provider
        prefix (``cloud:*`` for cloud providers, ``local:*`` for local).
        Returns the budget from the most constrained matching node,
        or None if no matching nodes are configured.

        If ``project_id`` matches the priority ⭐ project, returns the
        full node capacity instead of the shared budget.

        This enables ``get_batch_concurrency()`` to work without
        callers explicitly passing ``node_id``.
        """
        with self._lock:
            if not self._slots:
                return None

            # Determine which node prefix to match
            is_cloud = provider in CLOUD_PROVIDERS
            if not is_cloud and model:
                try:
                    from codrag.core.batch_profiles import is_cloud_model_via_ollama
                    if is_cloud_model_via_ollama(provider, model):
                        is_cloud = True
                except ImportError:
                    pass
            prefix = "cloud:" if is_cloud else "local:"

            # Exclusive ⭐ project gets the full capacity of any matching node
            is_exclusive = (
                project_id is not None
                and self._priority_project_id == project_id
                and self._priority_level == "exclusive"
            )

            # Find all matching nodes that have active work
            budget = None
            for nid, slot in self._slots.items():
                if not nid.startswith(prefix):
                    continue
                if is_exclusive:
                    cap = max(1, slot.max_concurrent)
                    if budget is None or cap < budget:
                        budget = cap
                    continue
                active_count = max(1, slot.current_load)
                if active_count == 0:
                    continue  # No work on this node
                node_budget = max(1, slot.max_concurrent // active_count)
                if budget is None or node_budget < budget:
                    budget = node_budget

            # If no active nodes found, check if any cloud nodes exist
            # and return their full capacity (happens when pipeline
            # hasn't called acquire yet but batch is about to start)
            if budget is None:
                for nid, slot in self._slots.items():
                    if nid.startswith(prefix):
                        cap = max(1, slot.max_concurrent)
                        if budget is None or cap < budget:
                            budget = cap

            return budget

    def status(self) -> Dict:
        """Return scheduler status for diagnostics/UI."""
        with self._lock:
            nodes = {}
            for nid, slot in self._slots.items():
                queue = self._queues.get(nid, deque())
                nodes[nid] = {
                    "max_concurrent": slot.max_concurrent,
                    "current_load": slot.current_load,
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
            priority = {
                "project_id": self._priority_project_id,
                "level": self._priority_level,
            }
            return {"nodes": nodes, "priority": priority}

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

            # ── Restore saved priority from project configs ───────────
            # Runs after ALL paths above so priority is always restored.
            try:
                from codrag.core.project_registry import ProjectRegistry
                registry = ProjectRegistry.from_default_config()
                for proj in registry.list_projects():
                    pcfg = proj.config if isinstance(proj.config, dict) else {}
                    level = pcfg.get("priority_level")
                    if not level and pcfg.get("is_starred"):
                        level = "boost"
                    if level and level != "none":
                        self.set_priority(proj.id, level)
                        break  # Only one priority project at a time
            except Exception:
                logger.debug("Scheduler: could not restore priority from project configs", exc_info=True)

        except Exception:
            logger.debug("Scheduler: failed to load settings (using defaults)", exc_info=True)
            self.set_default_concurrency(1)


# ── Module-level singleton ───────────────────────────────────────
pipeline_scheduler = PipelineScheduler()
