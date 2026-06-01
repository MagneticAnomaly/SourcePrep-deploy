"""Task 1: verify batched-BYOK cluster synthesis fans out to llm_pool."""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from unittest.mock import MagicMock

import pytest


class _FakeLLM:
    """Fake LLMClient that records concurrent in-flight calls to .generate()."""

    def __init__(self, latency: float = 0.1) -> None:
        self.model = "fake/test-model"
        self.provider = "fake"
        self._latency = latency
        self._in_flight = 0
        self._peak = 0
        self._lock = threading.Lock()
        self.calls = 0

    def generate(self, prompt, system=None, num_predict=None, num_ctx=None,
                 response_schema=None, max_chars=None, **_kw):
        with self._lock:
            self._in_flight += 1
            if self._in_flight > self._peak:
                self._peak = self._in_flight
            self.calls += 1
        try:
            time.sleep(self._latency)
            # Minimal valid batched clustering JSON: one item per batch
            return (
                '{"results":[{"name":"Fake","summary":"fake","component_status":"unknown"}]}',
                {"in": 10, "out": 10},
            )
        finally:
            with self._lock:
                self._in_flight -= 1


def _make_synthesizer_with_batch_profile(fake_llm):
    """Build a ClusterSynthesizer instance with a batching-on profile."""
    from prep.core.cluster import ClusterSynthesizer
    from prep.core.batch_profiles import BatchProfile

    synth = ClusterSynthesizer.__new__(ClusterSynthesizer)
    synth.llm = fake_llm
    # P127-F2: ClusterSynthesizer reads self.project_id before each
    # LLM dispatch (hold check).  Tests that bypass __init__ must set
    # the attr so the soft-hold check short-circuits cleanly at None.
    synth.project_id = None
    # Minimal profile that forces batching on with batch_size=2
    profile = MagicMock(spec=BatchProfile)
    profile.name = MagicMock()
    profile.name.value = "fast"
    profile.batch_size = MagicMock(return_value=2)
    synth._batch_profile = profile
    # Stub the helper methods the batched path calls
    synth._build_member_summaries = lambda cluster, epi, max_files=30: "members"
    synth._build_external_deps = lambda cluster, edges, epi: "deps"
    synth._write_modules = lambda modules: None
    return synth


@dataclass
class _FakeCluster:
    cluster_id: str
    primary_tag: str
    all_tags: frozenset
    member_node_ids: list

    def __init__(self, idx: int):
        self.cluster_id = f"cluster:{idx}"
        self.primary_tag = f"tag_{idx}"
        self.all_tags = frozenset({self.primary_tag})
        self.member_node_ids = [f"file:f{idx}.py"]


def test_batched_synthesis_fans_out_concurrently():
    """With 10 clusters and batch_size=2, we expect 5 batches running
    concurrently in llm_pool, so peak in-flight should exceed 1."""
    fake_llm = _FakeLLM(latency=0.25)
    synth = _make_synthesizer_with_batch_profile(fake_llm)

    clusters = [_FakeCluster(i) for i in range(10)]
    epistemic: dict = {}
    edges: list = []

    modules: dict = {}
    progress_calls = []

    def progress_callback(stage, current, total, reused):
        progress_calls.append((stage, current, total, reused))

    synth._synthesize_batched(
        clusters=clusters,
        epistemic=epistemic,
        edges=edges,
        modules=modules,
        progress_callback=progress_callback,
        reused=0,
        total_work=len(clusters),
        synthesized_start=0,
    )

    assert fake_llm.calls == 5, f"expected 5 batch calls, got {fake_llm.calls}"
    assert fake_llm._peak >= 2, (
        f"expected peak in-flight >=2 (fan-out working); got {fake_llm._peak}"
    )


def test_batched_synthesis_respects_cancel_token():
    from prep.services.cancellation import CancellationToken, PipelineCancelledError

    fake_llm = _FakeLLM(latency=0.2)
    synth = _make_synthesizer_with_batch_profile(fake_llm)

    writes = []
    synth._write_modules = lambda modules: writes.append(len(modules))

    token = CancellationToken()
    clusters = [_FakeCluster(i) for i in range(20)]

    import threading as _t
    _t.Timer(0.1, token.cancel).start()

    modules: dict = {}
    with pytest.raises(PipelineCancelledError):
        synth._synthesize_batched(
            clusters=clusters, epistemic={}, edges=[], modules=modules,
            progress_callback=None, reused=0, total_work=len(clusters),
            synthesized_start=0, cancel_token=token,
        )

    assert len(writes) >= 1, "expected _write_modules to be called on cancel"
