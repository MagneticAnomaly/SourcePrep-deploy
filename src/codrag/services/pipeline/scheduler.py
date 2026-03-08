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
from typing import Deque, Dict, List, Optional, Set, Tuple

from .stages import QueueType, STAGE_QUEUE_TYPE, StageId

logger = logging.getLogger(__name__)


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
        """
        if not self._needs_slot(stage):
            return True
        with self._lock:
            slot = self._get_slot(node_id)
            return slot.has_capacity

    def acquire(
        self,
        project_id: str,
        stage: StageId,
        node_id: Optional[str] = None,
    ) -> bool:
        """Acquire a compute slot for a stage.

        Returns True if the slot was acquired. False if the node is full.
        Caller should enqueue the pipeline if this returns False.
        """
        if not self._needs_slot(stage):
            return True  # No slot needed
        with self._lock:
            slot = self._get_slot(node_id)
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

    # ── Status / diagnostics ──────────────────────────────────────

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
            return {"nodes": nodes}

    def load_from_settings(self) -> None:
        """Load compute node configuration from the settings store."""
        try:
            from codrag.services.settings_store import settings
            llm_config = settings.get("llm_config") or {}
            nodes = llm_config.get("compute_nodes", [])

            if not nodes:
                # No explicit nodes — use pipeline config concurrency
                pipeline_cfg = settings.get("pipeline_config") or {}
                concurrency = max(1, int(
                    pipeline_cfg.get("llm_concurrency_fast",
                    pipeline_cfg.get("llm_concurrency", 1))
                ))
                self.set_default_concurrency(concurrency)
                return

            for node in nodes:
                self.configure_node(
                    node_id=node["id"],
                    max_concurrent=node.get("max_concurrent", 1),
                )
            logger.info(
                "Scheduler: loaded %d compute node(s) from settings",
                len(nodes),
            )
        except Exception:
            logger.debug("Scheduler: failed to load settings (using defaults)", exc_info=True)
            self.set_default_concurrency(1)


# ── Module-level singleton ───────────────────────────────────────
pipeline_scheduler = PipelineScheduler()
