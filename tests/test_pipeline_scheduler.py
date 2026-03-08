"""
Tests for Pipeline Scheduler (Phase 45D)
==========================================

Tests the compute slot allocation and queuing logic independently
of the actual pipeline orchestrator. No LLM or server required.
"""

import pytest
import time

from codrag.services.pipeline.scheduler import (
    PipelineScheduler,
    ComputeSlot,
    QueueEntry,
)
from codrag.services.pipeline.stages import StageId, QueueType


# ── ComputeSlot unit tests ──────────────────────────────────────

class TestComputeSlot:

    def test_initial_state(self):
        slot = ComputeSlot(node_id="n1", max_concurrent=2)
        assert slot.current_load == 0
        assert slot.has_capacity is True

    def test_acquire_releases(self):
        slot = ComputeSlot(node_id="n1", max_concurrent=2)
        assert slot.acquire("proj-a", "catalogue") is True
        assert slot.current_load == 1
        assert slot.has_capacity is True

        assert slot.acquire("proj-b", "enrichment") is True
        assert slot.current_load == 2
        assert slot.has_capacity is False

    def test_acquire_full(self):
        slot = ComputeSlot(node_id="n1", max_concurrent=1)
        slot.acquire("proj-a", "catalogue")
        assert slot.acquire("proj-b", "enrichment") is False

    def test_release(self):
        slot = ComputeSlot(node_id="n1", max_concurrent=1)
        slot.acquire("proj-a", "catalogue")
        assert slot.release("proj-a") is True
        assert slot.current_load == 0
        assert slot.has_capacity is True

    def test_release_nonexistent(self):
        slot = ComputeSlot(node_id="n1", max_concurrent=1)
        assert slot.release("proj-x") is False


# ── Scheduler basic tests ───────────────────────────────────────

class TestSchedulerBasic:

    def test_rust_stages_always_allowed(self):
        sched = PipelineScheduler()
        sched.set_default_concurrency(1)
        # Fill the only slot
        sched.acquire("proj-a", StageId.CATALOGUE)
        # Rust stage should still be allowed
        assert sched.can_start("proj-b", StageId.STRUCTURAL) is True
        assert sched.can_start("proj-b", StageId.VALIDATION) is True

    def test_embedding_stages_bypass_by_default(self):
        sched = PipelineScheduler()
        sched.set_default_concurrency(1)
        sched.acquire("proj-a", StageId.CATALOGUE)
        # NativeEmbedder: embedding should bypass
        assert sched.can_start("proj-b", StageId.KNOWLEDGE) is True
        assert sched.can_start("proj-b", StageId.DEEP_KNOWLEDGE) is True

    def test_embedding_stages_compete_with_ollama_embedder(self):
        sched = PipelineScheduler()
        sched.set_default_concurrency(1)
        sched.set_embedding_uses_llm(True)
        sched.acquire("proj-a", StageId.CATALOGUE)
        # OllamaEmbedder: embedding should compete
        assert sched.can_start("proj-b", StageId.KNOWLEDGE) is False

    def test_llm_stages_respect_concurrency(self):
        sched = PipelineScheduler()
        sched.set_default_concurrency(2)
        assert sched.acquire("proj-a", StageId.CATALOGUE) is True
        assert sched.acquire("proj-b", StageId.ENRICHMENT) is True
        assert sched.can_start("proj-c", StageId.ATLAS) is False


class TestSchedulerQueuing:

    def test_enqueue_dequeue(self):
        sched = PipelineScheduler()
        sched.set_default_concurrency(1)
        sched.acquire("proj-a", StageId.CATALOGUE)

        # Can't start, enqueue
        assert sched.can_start("proj-b", StageId.ENRICHMENT) is False
        sched.enqueue("proj-b", StageId.ENRICHMENT)

        # Release proj-a, dequeue proj-b
        entry = sched.release("proj-a", StageId.CATALOGUE)
        assert entry is not None
        assert entry.project_id == "proj-b"
        assert entry.stage == StageId.ENRICHMENT

    def test_fifo_order(self):
        sched = PipelineScheduler()
        sched.set_default_concurrency(1)
        sched.acquire("proj-a", StageId.CATALOGUE)

        sched.enqueue("proj-b", StageId.ENRICHMENT)
        sched.enqueue("proj-c", StageId.ATLAS)

        entry = sched.release("proj-a", StageId.CATALOGUE)
        assert entry.project_id == "proj-b"

    def test_no_double_enqueue(self):
        sched = PipelineScheduler()
        sched.set_default_concurrency(1)
        sched.acquire("proj-a", StageId.CATALOGUE)

        sched.enqueue("proj-b", StageId.ENRICHMENT)
        sched.enqueue("proj-b", StageId.ENRICHMENT)  # duplicate

        status = sched.status()
        node = status["nodes"]["__local__"]
        assert len(node["queued"]) == 1

    def test_cancel_removes_from_queue_and_slots(self):
        sched = PipelineScheduler()
        sched.set_default_concurrency(2)
        sched.acquire("proj-a", StageId.CATALOGUE)
        sched.enqueue("proj-b", StageId.ENRICHMENT)

        sched.cancel("proj-a")
        sched.cancel("proj-b")

        status = sched.status()
        node = status["nodes"]["__local__"]
        assert node["current_load"] == 0
        assert len(node["queued"]) == 0

    def test_release_with_empty_queue(self):
        sched = PipelineScheduler()
        sched.set_default_concurrency(1)
        sched.acquire("proj-a", StageId.CATALOGUE)

        entry = sched.release("proj-a", StageId.CATALOGUE)
        assert entry is None  # No one waiting


class TestSchedulerMultiNode:

    def test_separate_nodes(self):
        sched = PipelineScheduler()
        sched.configure_node("gpu-1", max_concurrent=1)
        sched.configure_node("gpu-2", max_concurrent=1)

        # Fill both nodes
        assert sched.acquire("proj-a", StageId.CATALOGUE, node_id="gpu-1") is True
        assert sched.acquire("proj-b", StageId.ENRICHMENT, node_id="gpu-2") is True

        # gpu-1 full, gpu-2 full
        assert sched.can_start("proj-c", StageId.ATLAS, node_id="gpu-1") is False
        assert sched.can_start("proj-c", StageId.ATLAS, node_id="gpu-2") is False

    def test_queue_per_node(self):
        sched = PipelineScheduler()
        sched.configure_node("gpu-1", max_concurrent=1)
        sched.configure_node("gpu-2", max_concurrent=1)

        sched.acquire("proj-a", StageId.CATALOGUE, node_id="gpu-1")
        sched.acquire("proj-b", StageId.ENRICHMENT, node_id="gpu-2")

        sched.enqueue("proj-c", StageId.ATLAS, node_id="gpu-1")
        sched.enqueue("proj-d", StageId.ATLAS, node_id="gpu-2")

        # Release gpu-1 -> dequeue proj-c
        entry = sched.release("proj-a", StageId.CATALOGUE, node_id="gpu-1")
        assert entry.project_id == "proj-c"

        # Release gpu-2 -> dequeue proj-d
        entry = sched.release("proj-b", StageId.ENRICHMENT, node_id="gpu-2")
        assert entry.project_id == "proj-d"


class TestSchedulerStatus:

    def test_status_reflects_state(self):
        sched = PipelineScheduler()
        sched.set_default_concurrency(2)
        sched.acquire("proj-a", StageId.CATALOGUE)
        sched.acquire("proj-b", StageId.ENRICHMENT)
        sched.enqueue("proj-c", StageId.ATLAS)

        status = sched.status()
        node = status["nodes"]["__local__"]
        assert node["max_concurrent"] == 2
        assert node["current_load"] == 2
        assert len(node["active"]) == 2
        assert len(node["queued"]) == 1
        assert node["queued"][0]["project_id"] == "proj-c"
