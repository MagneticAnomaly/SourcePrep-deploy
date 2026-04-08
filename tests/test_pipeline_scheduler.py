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

    def test_embedding_stages_use_separate_slot(self):
        sched = PipelineScheduler()
        sched.set_default_concurrency(1)
        sched.configure_embedding_concurrency(1)
        sched.acquire("proj-a", StageId.CATALOGUE)
        # NativeEmbedder: embedding uses dedicated __embedding__ slot,
        # not the LLM slot — so it can start even when LLM is full
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


# ── Phase 56: Endpoint-aware node resolution ─────────────────────

from codrag.services.pipeline.scheduler import CLOUD_PROVIDERS


class TestResolveNodeForModel:
    """Test the stage → slot → endpoint → node resolution chain."""

    def test_local_ollama_model(self):
        sched = PipelineScheduler()
        node = sched.resolve_node_for_model("ollama", "qwen3:4b", "ep-1")
        assert node == "local:ep-1"

    def test_cloud_via_ollama_kimi(self):
        sched = PipelineScheduler()
        node = sched.resolve_node_for_model("ollama", "kimi-k2.5", "ep-1")
        assert node == "cloud:ep-1"

    def test_cloud_via_ollama_gemini(self):
        sched = PipelineScheduler()
        node = sched.resolve_node_for_model("ollama", "gemini-2.5-pro", "ep-1")
        assert node == "cloud:ep-1"

    def test_direct_cloud_openai(self):
        sched = PipelineScheduler()
        node = sched.resolve_node_for_model("openai", "gpt-4.1", "ep-2")
        assert node == "cloud:ep-2"

    def test_direct_cloud_anthropic(self):
        sched = PipelineScheduler()
        node = sched.resolve_node_for_model("anthropic", "claude-sonnet-4-5", "ep-3")
        assert node == "cloud:ep-3"

    def test_lm_studio_local(self):
        sched = PipelineScheduler()
        node = sched.resolve_node_for_model("lm-studio", "qwen3:14b", "ep-4")
        assert node == "local:ep-4"


class TestEndpointAwareConcurrency:
    """Test multi-project concurrency with local/cloud nodes."""

    def test_local_serializes(self):
        """Two projects on local:ep-1 (max=1) — second blocks."""
        sched = PipelineScheduler()
        sched.configure_node("local:ep-1", 1)

        assert sched.acquire("proj-a", StageId.CATALOGUE, "local:ep-1")
        assert not sched.can_start("proj-b", StageId.CATALOGUE, "local:ep-1")

        sched.release("proj-a", StageId.CATALOGUE, "local:ep-1")
        assert sched.can_start("proj-b", StageId.CATALOGUE, "local:ep-1")

    def test_cloud_concurrent_three(self):
        """Three projects on cloud:ep-1 (max=3) run concurrently."""
        sched = PipelineScheduler()
        sched.configure_node("cloud:ep-1", 3)

        assert sched.acquire("proj-a", StageId.ENRICHMENT, "cloud:ep-1")
        assert sched.acquire("proj-b", StageId.ENRICHMENT, "cloud:ep-1")
        assert sched.acquire("proj-c", StageId.ENRICHMENT, "cloud:ep-1")
        assert not sched.can_start("proj-d", StageId.ENRICHMENT, "cloud:ep-1")

    def test_cloud_concurrent_ten(self):
        """Ollama Max plan: 10 concurrent cloud requests."""
        sched = PipelineScheduler()
        sched.configure_node("cloud:ep-1", 10)

        for i in range(10):
            assert sched.acquire(f"proj-{i}", StageId.ENRICHMENT, "cloud:ep-1")
        assert not sched.can_start("proj-10", StageId.ENRICHMENT, "cloud:ep-1")

    def test_mixed_local_and_cloud_independent(self):
        """Local and cloud slots on the same endpoint don't contend."""
        sched = PipelineScheduler()
        sched.configure_node("local:ep-1", 1)
        sched.configure_node("cloud:ep-1", 3)

        assert sched.acquire("proj-a", StageId.CATALOGUE, "local:ep-1")
        assert sched.acquire("proj-b", StageId.ENRICHMENT, "cloud:ep-1")

        assert sched._slots["local:ep-1"].current_load == 1
        assert sched._slots["cloud:ep-1"].current_load == 1

    def test_queue_fifo_across_nodes(self):
        """Releasing a local slot dequeues the next project on that node."""
        sched = PipelineScheduler()
        sched.configure_node("local:ep-1", 1)

        sched.acquire("proj-a", StageId.CATALOGUE, "local:ep-1")
        sched.enqueue("proj-b", StageId.CATALOGUE, "local:ep-1")
        sched.enqueue("proj-c", StageId.CATALOGUE, "local:ep-1")

        entry = sched.release("proj-a", StageId.CATALOGUE, "local:ep-1")
        assert entry is not None
        assert entry.project_id == "proj-b"


# ── Phase 56B: Adaptive batch concurrency ────────────────────────

class TestAvailableBatchWorkers:
    """Test dynamic batch worker allocation based on node load."""

    def test_single_project_gets_full_budget(self):
        """One project on cloud:ep-1 (max=3) gets 3 batch workers."""
        sched = PipelineScheduler()
        sched.configure_node("cloud:ep-1", 3)
        sched.acquire("proj-a", StageId.ENRICHMENT, "cloud:ep-1")

        assert sched.available_batch_workers("cloud:ep-1") == 3

    def test_two_projects_split_budget(self):
        """Two projects on cloud:ep-1 (max=3) get 1 worker each (3//2)."""
        sched = PipelineScheduler()
        sched.configure_node("cloud:ep-1", 3)
        sched.acquire("proj-a", StageId.ENRICHMENT, "cloud:ep-1")
        sched.acquire("proj-b", StageId.ENRICHMENT, "cloud:ep-1")

        assert sched.available_batch_workers("cloud:ep-1") == 1

    def test_single_project_ten_slots(self):
        """One project on cloud:ep-1 (max=10) gets 10 batch workers."""
        sched = PipelineScheduler()
        sched.configure_node("cloud:ep-1", 10)
        sched.acquire("proj-a", StageId.ENRICHMENT, "cloud:ep-1")

        assert sched.available_batch_workers("cloud:ep-1") == 10

    def test_unknown_node_returns_one(self):
        """Unknown node returns 1 (safe default)."""
        sched = PipelineScheduler()
        assert sched.available_batch_workers("nonexistent:node") == 1


# ── Phase 56C: Priority star ─────────────────────────────────────

class TestPriorityStar:
    """Test global priority project queue ordering."""

    def test_priority_dequeues_first(self):
        """Starred project jumps to front of queue."""
        sched = PipelineScheduler()
        sched.configure_node("cloud:ep-1", 1)
        sched.set_priority("proj-c")

        sched.acquire("proj-a", StageId.ENRICHMENT, "cloud:ep-1")
        sched.enqueue("proj-b", StageId.ENRICHMENT, "cloud:ep-1")
        sched.enqueue("proj-c", StageId.ENRICHMENT, "cloud:ep-1")  # ⭐ priority

        # Release → should dequeue proj-c (priority) not proj-b (FIFO)
        entry = sched.release("proj-a", StageId.ENRICHMENT, "cloud:ep-1")
        assert entry is not None
        assert entry.project_id == "proj-c"

    def test_no_priority_uses_fifo(self):
        """Without priority star, normal FIFO ordering."""
        sched = PipelineScheduler()
        sched.configure_node("cloud:ep-1", 1)

        sched.acquire("proj-a", StageId.ENRICHMENT, "cloud:ep-1")
        sched.enqueue("proj-b", StageId.ENRICHMENT, "cloud:ep-1")
        sched.enqueue("proj-c", StageId.ENRICHMENT, "cloud:ep-1")

        entry = sched.release("proj-a", StageId.ENRICHMENT, "cloud:ep-1")
        assert entry.project_id == "proj-b"


# ── Phase 72B: Multi-priority support ─────────────────────────────

class TestMultiPriority:
    """Test multi-project priority support (Phase 72B)."""

    def test_two_starred_projects_both_get_queue_jump(self):
        """Both starred projects should jump to front of queue."""
        sched = PipelineScheduler()
        sched.configure_node("cloud:ep-1", 1)
        sched.set_priority("proj-b")
        sched.set_priority("proj-c")

        sched.acquire("proj-a", StageId.ENRICHMENT, "cloud:ep-1")
        sched.enqueue("proj-d", StageId.ENRICHMENT, "cloud:ep-1")  # normal
        sched.enqueue("proj-b", StageId.ENRICHMENT, "cloud:ep-1")  # ⭐
        sched.enqueue("proj-c", StageId.ENRICHMENT, "cloud:ep-1")  # ⭐

        # Both starred projects should be at the front
        entry1 = sched.release("proj-a", StageId.ENRICHMENT, "cloud:ep-1")
        assert entry1 is not None
        assert entry1.project_id in ("proj-b", "proj-c")  # one of the starred

    def test_unstar_one_keeps_other(self):
        """Unstarring one project doesn't affect the other."""
        sched = PipelineScheduler()
        sched.set_priority("proj-a", "boost")
        sched.set_priority("proj-b", "boost")

        assert sched.get_priority("proj-a") == "boost"
        assert sched.get_priority("proj-b") == "boost"

        # Unstar proj-a
        sched.set_priority("proj-a", "none")

        assert sched.get_priority("proj-a") == "none"
        assert sched.get_priority("proj-b") == "boost"

    def test_clear_all_priorities(self):
        """Clearing all priorities with None removes everything."""
        sched = PipelineScheduler()
        sched.set_priority("proj-a", "boost")
        sched.set_priority("proj-b", "exclusive")
        sched.set_priority("proj-c", "boost")

        sched.clear_all_priorities()

        assert sched.get_priority("proj-a") == "none"
        assert sched.get_priority("proj-b") == "none"
        assert sched.get_priority("proj-c") == "none"
        assert sched.priority_project_id is None
        assert sched.priority_level == "none"

    def test_exclusive_demotes_existing_exclusive(self):
        """Setting exclusive on a new project demotes the old one to boost."""
        sched = PipelineScheduler()
        sched.set_priority("proj-a", "exclusive")

        assert sched.get_priority("proj-a") == "exclusive"

        sched.set_priority("proj-b", "exclusive")

        assert sched.get_priority("proj-a") == "boost"  # demoted
        assert sched.get_priority("proj-b") == "exclusive"

    def test_backward_compat_priority_project_id(self):
        """priority_project_id property returns exclusive first, then boost."""
        sched = PipelineScheduler()
        sched.set_priority("proj-a", "boost")
        sched.set_priority("proj-b", "boost")

        # Should return one of the boost projects
        assert sched.priority_project_id in ("proj-a", "proj-b")

        # Add an exclusive — it should take precedence
        sched.set_priority("proj-c", "exclusive")
        assert sched.priority_project_id == "proj-c"
        assert sched.priority_level == "exclusive"

    def test_priority_projects_property(self):
        """priority_projects returns a snapshot of all priorities."""
        sched = PipelineScheduler()
        sched.set_priority("proj-a", "boost")
        sched.set_priority("proj-b", "exclusive")

        projects = sched.priority_projects
        assert projects == {"proj-a": "boost", "proj-b": "exclusive"}

    def test_status_reports_multi_priority(self):
        """status() includes the full priority dict."""
        sched = PipelineScheduler()
        sched.set_default_concurrency(1)
        sched.set_priority("proj-a", "boost")
        sched.set_priority("proj-b", "boost")

        status = sched.status()
        assert "priority" in status
        assert "projects" in status["priority"]
        assert status["priority"]["projects"] == {
            "proj-a": "boost",
            "proj-b": "boost",
        }
        # Backward compat fields
        assert status["priority"]["project_id"] in ("proj-a", "proj-b")
        assert status["priority"]["level"] == "boost"


# ── Phase 72B: Weighted fair-share budget ────────────────────────

class TestWeightedFairShare:
    """Test weighted fair-share budget allocation (Phase 72B)."""

    def test_ten_concurrency_two_boost_two_normal(self):
        """10 concurrency, 2 boost + 2 normal → 3+3+1+1 (remainder to boost)."""
        sched = PipelineScheduler()
        sched.configure_node("cloud:ep-1", 10)
        sched.set_priority("proj-a", "boost")
        sched.set_priority("proj-b", "boost")

        sched.acquire("proj-a", StageId.ENRICHMENT, "cloud:ep-1")
        sched.acquire("proj-b", StageId.ENRICHMENT, "cloud:ep-1")
        sched.acquire("proj-c", StageId.ENRICHMENT, "cloud:ep-1")
        sched.acquire("proj-d", StageId.ENRICHMENT, "cloud:ep-1")

        # Boost projects (weight 2): floor(10 * 2 / 6) = 3
        assert sched.available_batch_workers("cloud:ep-1", project_id="proj-a") == 4  # 3 + remainder
        assert sched.available_batch_workers("cloud:ep-1", project_id="proj-b") == 4  # 3 + remainder
        # Normal projects (weight 1): floor(10 * 1 / 6) = 1
        assert sched.available_batch_workers("cloud:ep-1", project_id="proj-c") == 1
        assert sched.available_batch_workers("cloud:ep-1", project_id="proj-d") == 1

    def test_six_concurrency_two_boost_two_normal(self):
        """6 concurrency, 2 boost + 2 normal → 2+2+1+1 (clean split)."""
        sched = PipelineScheduler()
        sched.configure_node("cloud:ep-1", 6)
        sched.set_priority("proj-a", "boost")
        sched.set_priority("proj-b", "boost")

        sched.acquire("proj-a", StageId.ENRICHMENT, "cloud:ep-1")
        sched.acquire("proj-b", StageId.ENRICHMENT, "cloud:ep-1")
        sched.acquire("proj-c", StageId.ENRICHMENT, "cloud:ep-1")
        sched.acquire("proj-d", StageId.ENRICHMENT, "cloud:ep-1")

        assert sched.available_batch_workers("cloud:ep-1", project_id="proj-a") == 2
        assert sched.available_batch_workers("cloud:ep-1", project_id="proj-b") == 2
        assert sched.available_batch_workers("cloud:ep-1", project_id="proj-c") == 1
        assert sched.available_batch_workers("cloud:ep-1", project_id="proj-d") == 1

    def test_no_priority_equal_split(self):
        """No priority → even split among all projects."""
        sched = PipelineScheduler()
        sched.configure_node("cloud:ep-1", 10)

        sched.acquire("proj-a", StageId.ENRICHMENT, "cloud:ep-1")
        sched.acquire("proj-b", StageId.ENRICHMENT, "cloud:ep-1")

        # 10 / 2 = 5 each
        assert sched.available_batch_workers("cloud:ep-1", project_id="proj-a") == 5
        assert sched.available_batch_workers("cloud:ep-1", project_id="proj-b") == 5

    def test_exclusive_gets_full_budget(self):
        """Exclusive project gets entire budget regardless of others."""
        sched = PipelineScheduler()
        sched.configure_node("cloud:ep-1", 10)
        sched.set_priority("proj-a", "exclusive")

        sched.acquire("proj-a", StageId.ENRICHMENT, "cloud:ep-1")
        sched.acquire("proj-b", StageId.ENRICHMENT, "cloud:ep-1")

        assert sched.available_batch_workers("cloud:ep-1", project_id="proj-a") == 10

    def test_one_boost_three_normal(self):
        """10 concurrency, 1 boost + 3 normal → boost gets 4, normals get 2."""
        sched = PipelineScheduler()
        sched.configure_node("cloud:ep-1", 10)
        sched.set_priority("proj-a", "boost")

        sched.acquire("proj-a", StageId.ENRICHMENT, "cloud:ep-1")
        sched.acquire("proj-b", StageId.ENRICHMENT, "cloud:ep-1")
        sched.acquire("proj-c", StageId.ENRICHMENT, "cloud:ep-1")
        sched.acquire("proj-d", StageId.ENRICHMENT, "cloud:ep-1")

        # weight = 2+1+1+1 = 5
        # boost: floor(10*2/5) = 4
        assert sched.available_batch_workers("cloud:ep-1", project_id="proj-a") == 4
        # normal: floor(10*1/5) = 2
        assert sched.available_batch_workers("cloud:ep-1", project_id="proj-b") == 2
        assert sched.available_batch_workers("cloud:ep-1", project_id="proj-c") == 2
        assert sched.available_batch_workers("cloud:ep-1", project_id="proj-d") == 2




class TestAutoDiscoveryBatchWorkers:
    """Test available_batch_workers_for_provider() auto-discovery."""

    def test_cloud_provider_finds_cloud_node(self):
        """Cloud provider auto-discovers cloud:* nodes."""
        sched = PipelineScheduler()
        sched.configure_node("cloud:ep-1", 3)
        sched.acquire("proj-a", StageId.CATALOGUE, "cloud:ep-1")

        result = sched.available_batch_workers_for_provider("openai")
        assert result == 3  # Single project gets full budget

    def test_cloud_provider_with_two_projects(self):
        """Cloud provider with 2 active projects splits budget."""
        sched = PipelineScheduler()
        sched.configure_node("cloud:ep-1", 3)
        sched.acquire("proj-a", StageId.CATALOGUE, "cloud:ep-1")
        sched.acquire("proj-b", StageId.ENRICHMENT, "cloud:ep-1")

        result = sched.available_batch_workers_for_provider("openai")
        assert result == 1  # 3 // 2 = 1

    def test_local_provider_finds_local_node(self):
        """Local Ollama provider auto-discovers local:* nodes."""
        sched = PipelineScheduler()
        sched.configure_node("local:ep-1", 1)
        sched.configure_node("cloud:ep-1", 3)
        sched.acquire("proj-a", StageId.CATALOGUE, "local:ep-1")

        result = sched.available_batch_workers_for_provider("ollama")
        assert result == 1  # Local node max_concurrent=1

    def test_empty_scheduler_returns_none(self):
        """No nodes configured returns None."""
        sched = PipelineScheduler()
        result = sched.available_batch_workers_for_provider("openai")
        assert result is None

    def test_inactive_node_returns_full_capacity(self):
        """Node exists but no projects active → returns full capacity."""
        sched = PipelineScheduler()
        sched.configure_node("cloud:ep-1", 5)

        result = sched.available_batch_workers_for_provider("anthropic")
        assert result == 5


# ── Embedding slot tests ─────────────────────────────────────────

class TestEmbeddingSlot:
    """Test dedicated embedding concurrency gate."""

    def test_embedding_stages_use_embedding_slot(self):
        """KNOWLEDGE and DEEP_KNOWLEDGE acquire from __embedding__, not __local__."""
        sched = PipelineScheduler()
        sched.set_default_concurrency(1)
        sched.configure_embedding_concurrency(1)

        # Fill the LLM slot
        sched.acquire("proj-a", StageId.CATALOGUE)
        # Embedding should still start (different slot)
        assert sched.can_start("proj-b", StageId.KNOWLEDGE) is True
        assert sched.acquire("proj-b", StageId.KNOWLEDGE) is True

        # But a second embedding should block (embedding slot full)
        assert sched.can_start("proj-c", StageId.KNOWLEDGE) is False

    def test_embedding_slot_independent_from_llm(self):
        """Filling embedding slot doesn't block LLM; filling LLM doesn't block embedding."""
        sched = PipelineScheduler()
        sched.set_default_concurrency(1)
        sched.configure_embedding_concurrency(1)

        # Fill embedding
        assert sched.acquire("proj-a", StageId.KNOWLEDGE) is True
        # LLM should still work
        assert sched.can_start("proj-b", StageId.ENRICHMENT) is True
        assert sched.acquire("proj-b", StageId.ENRICHMENT) is True

        # Both slots now full — second embedding blocked, second LLM blocked
        assert sched.can_start("proj-c", StageId.DEEP_KNOWLEDGE) is False
        assert sched.can_start("proj-c", StageId.CATALOGUE) is False

    def test_embedding_queue_fifo(self):
        """Second embedding project queues and dequeues after first finishes."""
        sched = PipelineScheduler()
        sched.configure_embedding_concurrency(1)

        assert sched.acquire("proj-a", StageId.KNOWLEDGE) is True
        assert sched.can_start("proj-b", StageId.KNOWLEDGE) is False
        sched.enqueue("proj-b", StageId.KNOWLEDGE)
        sched.enqueue("proj-c", StageId.DEEP_KNOWLEDGE)

        # Release proj-a → dequeue proj-b
        entry = sched.release("proj-a", StageId.KNOWLEDGE)
        assert entry is not None
        assert entry.project_id == "proj-b"

    def test_embedding_concurrency_two(self):
        """When set to 2, two embedding stages can run concurrently."""
        sched = PipelineScheduler()
        sched.configure_embedding_concurrency(2)

        assert sched.acquire("proj-a", StageId.KNOWLEDGE) is True
        assert sched.acquire("proj-b", StageId.DEEP_KNOWLEDGE) is True
        assert sched.can_start("proj-c", StageId.KNOWLEDGE) is False

    def test_ollama_embedder_routes_to_llm_slot(self):
        """When OllamaEmbedder is active, embedding stages use the LLM slot."""
        sched = PipelineScheduler()
        sched.set_default_concurrency(1)
        sched.set_embedding_uses_llm(True)

        # Fill the LLM slot
        sched.acquire("proj-a", StageId.CATALOGUE)
        # Embedding now competes for the same slot → blocked
        assert sched.can_start("proj-b", StageId.KNOWLEDGE) is False

    def test_cancel_removes_from_embedding_queue(self):
        """Cancelling a project removes it from the embedding queue."""
        sched = PipelineScheduler()
        sched.configure_embedding_concurrency(1)

        sched.acquire("proj-a", StageId.KNOWLEDGE)
        sched.enqueue("proj-b", StageId.KNOWLEDGE)
        sched.enqueue("proj-c", StageId.KNOWLEDGE)

        sched.cancel("proj-b")
        entry = sched.release("proj-a", StageId.KNOWLEDGE)
        assert entry is not None
        assert entry.project_id == "proj-c"

    def test_status_includes_embedding_slot(self):
        """status() reports the embedding slot state."""
        sched = PipelineScheduler()
        sched.configure_embedding_concurrency(1)
        sched.acquire("proj-a", StageId.KNOWLEDGE)

        status = sched.status()
        emb_node = status["nodes"].get("__embedding__")
        assert emb_node is not None
        assert emb_node["max_concurrent"] == 1
        assert emb_node["current_load"] == 1

    def test_rust_stages_still_bypass(self):
        """Rust stages remain slot-free even with embedding gate active."""
        sched = PipelineScheduler()
        sched.set_default_concurrency(1)
        sched.configure_embedding_concurrency(1)
        sched.acquire("proj-a", StageId.CATALOGUE)
        sched.acquire("proj-b", StageId.KNOWLEDGE)

        assert sched.can_start("proj-c", StageId.STRUCTURAL) is True
        assert sched.can_start("proj-c", StageId.VALIDATION) is True


class TestFullBudgetForSwarm:
    """Phase 79: Swarm stages bypass fair-share and get full concurrency."""

    def test_single_project_gets_full_budget(self):
        sched = PipelineScheduler()
        sched.configure_node("cloud:ep-1", 10)
        sched.acquire("proj-a", StageId.GROUP_REASONING, "cloud:ep-1")

        result = sched.full_budget_for_swarm("openai", project_id="proj-a")
        assert result == 10

    def test_two_projects_still_gets_full_budget(self):
        """Swarm bypasses fair-share — even with 2 active projects, gets full budget."""
        sched = PipelineScheduler()
        sched.configure_node("cloud:ep-1", 10)
        sched.acquire("proj-a", StageId.GROUP_REASONING, "cloud:ep-1")
        sched.acquire("proj-b", StageId.ENRICHMENT, "cloud:ep-1")

        # Swarm should get 10, NOT 5 (the fair-share split)
        result = sched.full_budget_for_swarm("openai", project_id="proj-a")
        assert result == 10

        # For comparison, normal fair-share would give 5
        normal = sched.available_batch_workers_for_provider("openai", project_id="proj-a")
        assert normal == 5

    def test_three_projects_with_boost_still_gets_full(self):
        """Swarm ignores boost/normal weighting entirely."""
        sched = PipelineScheduler()
        sched.configure_node("cloud:ep-1", 10)
        sched.acquire("proj-a", StageId.GROUP_REASONING, "cloud:ep-1")
        sched.acquire("proj-b", StageId.ENRICHMENT, "cloud:ep-1")
        sched.acquire("proj-c", StageId.CATALOGUE, "cloud:ep-1")
        sched.set_priority("proj-b", "boost")

        # Swarm gets full 10 regardless of other projects' priority
        result = sched.full_budget_for_swarm("openai", project_id="proj-a")
        assert result == 10

    def test_prefix_fallback_when_no_project_id(self):
        """Without project_id, falls back to prefix discovery."""
        sched = PipelineScheduler()
        sched.configure_node("cloud:ep-1", 8)

        result = sched.full_budget_for_swarm("openai")
        assert result == 8

    def test_empty_scheduler_returns_none(self):
        sched = PipelineScheduler()
        result = sched.full_budget_for_swarm("openai")
        assert result is None

    def test_local_ollama_finds_local_node(self):
        sched = PipelineScheduler()
        sched.configure_node("local:ollama-1", 4)
        sched.configure_node("cloud:ep-1", 10)
        sched.acquire("proj-a", StageId.GROUP_REASONING, "local:ollama-1")

        result = sched.full_budget_for_swarm("ollama", project_id="proj-a")
        assert result == 4


# ── Phase 82: Shared swarm constant + helper ─────────────────────

from codrag.services.pipeline.scheduler import (
    SWARM_CAPABLE_STAGES,
    is_swarm_active_for_stage,
)


class TestSwarmCapableStages:

    def test_group_reasoning_in_set(self):
        assert "group_reasoning" in SWARM_CAPABLE_STAGES

    def test_clustering_in_set(self):
        assert "clustering" in SWARM_CAPABLE_STAGES

    def test_atlas_in_set(self):
        assert "atlas" in SWARM_CAPABLE_STAGES

    def test_enrichment_not_in_set(self):
        assert "enrichment" not in SWARM_CAPABLE_STAGES

    def test_catalogue_not_in_set(self):
        assert "catalogue" not in SWARM_CAPABLE_STAGES


class TestIsSwarmActiveForStage:

    def test_kimi_on_ollama_group_reasoning(self):
        assert is_swarm_active_for_stage("group_reasoning", "ollama", "kimi-k2.5:cloud") is True

    def test_kimi_on_ollama_clustering(self):
        assert is_swarm_active_for_stage("clustering", "ollama", "kimi-k2.5:cloud") is True

    def test_kimi_on_ollama_atlas(self):
        assert is_swarm_active_for_stage("atlas", "ollama", "kimi-k2.5:cloud") is True

    def test_kimi_on_ollama_non_swarm_stage(self):
        assert is_swarm_active_for_stage("enrichment", "ollama", "kimi-k2.5:cloud") is False

    def test_unsuitable_model_returns_false(self):
        assert is_swarm_active_for_stage("group_reasoning", "ollama", "llama3.3:70b") is False

    def test_claude_sonnet_on_anthropic(self):
        assert is_swarm_active_for_stage("group_reasoning", "anthropic", "claude-sonnet-4.6") is True

    def test_unknown_provider_returns_false(self):
        assert is_swarm_active_for_stage("group_reasoning", "lm-studio", "kimi-k2.5") is False

    def test_swarm_disabled_setting(self, monkeypatch):
        """When swarm_enabled=False in settings, always returns False."""
        from codrag.services import settings_store
        original_get = settings_store.settings.get

        def mock_get(key, default=None):
            if key == "swarm_enabled":
                return False
            return original_get(key, default)

        monkeypatch.setattr(settings_store.settings, "get", mock_get)
        assert is_swarm_active_for_stage("group_reasoning", "ollama", "kimi-k2.5:cloud") is False


from unittest.mock import patch


class TestConcurrentWorkersSwarmAware:

    def test_swarm_stage_returns_full_budget(self):
        """When stage is swarm-capable and model supports swarm,
        return full dynamic_capacity - 1, not weighted share."""
        sched = PipelineScheduler()
        sched.configure_node("cloud:ep-1", 12)
        # Set AIMD limit to match max_concurrent for this test
        with sched._lock:
            sched._slots["cloud:ep-1"].current_limit = 12
        sched.acquire("proj-a", StageId.GROUP_REASONING, "cloud:ep-1")

        mock_config = {
            "large_model": {"endpoint_id": "ep-1", "model": "kimi-k2.5:cloud"},
            "saved_endpoints": [{"id": "ep-1", "provider": "ollama"}],
        }
        with patch("codrag.services.pipeline._model_resolution.settings") as mock_settings:
            mock_settings.get.return_value = mock_config
            workers, node_id = sched.concurrent_workers_for_project(
                "proj-a", stage="group_reasoning",
            )
        assert node_id == "cloud:ep-1"
        # full budget = dynamic_capacity - 1 = 12 - 1 = 11
        assert workers == 11

    def test_non_swarm_stage_returns_weighted_share(self):
        """Non-swarm stages still use weighted share."""
        sched = PipelineScheduler()
        sched.configure_node("cloud:ep-1", 10)
        sched.acquire("proj-a", StageId.ENRICHMENT, "cloud:ep-1")

        workers, node_id = sched.concurrent_workers_for_project(
            "proj-a", stage="enrichment",
        )
        assert node_id == "cloud:ep-1"
        assert workers >= 1

    def test_no_stage_returns_weighted_share(self):
        """When stage is None (backward compat), use weighted share."""
        sched = PipelineScheduler()
        sched.configure_node("cloud:ep-1", 10)
        sched.acquire("proj-a", StageId.CATALOGUE, "cloud:ep-1")

        workers, _ = sched.concurrent_workers_for_project("proj-a")
        assert workers >= 1

    def test_unsuitable_model_on_swarm_stage_returns_weighted_share(self):
        """Swarm stage with unsuitable model falls back to weighted share."""
        sched = PipelineScheduler()
        sched.configure_node("local:ep-1", 1)
        sched.acquire("proj-a", StageId.GROUP_REASONING, "local:ep-1")

        mock_config = {
            "large_model": {"endpoint_id": "ep-1", "model": "llama3.3:70b"},
            "saved_endpoints": [{"id": "ep-1", "provider": "ollama"}],
        }
        with patch("codrag.services.pipeline._model_resolution.settings") as mock_settings:
            mock_settings.get.return_value = mock_config
            workers, _ = sched.concurrent_workers_for_project(
                "proj-a", stage="group_reasoning",
            )
        assert workers == 1


class TestSchedulerStatusAIMD:

    def test_status_includes_aimd_fields(self):
        sched = PipelineScheduler()
        sched.configure_node("cloud:ep-1", 10)
        status = sched.status()
        node = status["nodes"]["cloud:ep-1"]
        assert "aimd_mode" in node
        assert "current_limit" in node
        assert node["aimd_mode"] == "jumpstart"
        assert node["current_limit"] == 5  # default


class TestIsHeldBy:

    def test_returns_true_when_held(self):
        sched = PipelineScheduler()
        sched.configure_node("cloud:ep-1", 10)
        sched.acquire("proj-a", StageId.ENRICHMENT, "cloud:ep-1")
        assert sched.is_held_by("proj-a") is True

    def test_returns_false_when_not_held(self):
        sched = PipelineScheduler()
        sched.configure_node("cloud:ep-1", 10)
        assert sched.is_held_by("proj-a") is False

    def test_returns_false_after_release(self):
        sched = PipelineScheduler()
        sched.configure_node("cloud:ep-1", 10)
        sched.acquire("proj-a", StageId.ENRICHMENT, "cloud:ep-1")
        sched.release("proj-a", StageId.ENRICHMENT, "cloud:ep-1")
        assert sched.is_held_by("proj-a") is False
