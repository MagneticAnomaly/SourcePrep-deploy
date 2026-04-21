# Parallel Non-Swarm Fallback Paths Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore parallel fan-out for the non-swarm fallback paths in `cluster.py` and `concept_seeder.py` so Phase 82's AIMD per-request gate is fully exercised regardless of whether `swarm_enabled` is on.

**Architecture:** Both stages currently serialize work on their non-swarm paths: `cluster.py` runs a plain `for batch_start in range(...)` loop over batched cluster groups; `_seed_concepts_sequential` makes a single global-context LLM call. Rewrite both to submit work to the shared bounded `llm_pool` (`src/codrag/services/pipeline/thread_pool.py`) using the pattern established by `deepening.py` (lines 439-509): `pool.submit(...)` fan-out, `as_completed(futures, timeout=...)` collection, `FutureTimeoutError` branch, and an unconditional `finally` block that cancels any orphaned futures. The AIMD gate inside `LLMClient.generate` is the real throttle — submitting the full fan-out is fine because surplus submits block at the gate.

**Tech Stack:** Python 3.11, `concurrent.futures.ThreadPoolExecutor` (via shared `llm_pool`), pytest.

**Rollout order:** Tasks execute sequentially (1 → 2 → 3 → 4). Task 4 is live validation and depends on Tasks 1 and 2 being shipped.

**Constraints to preserve:**
- `cancel_token` cooperative cancellation semantics
- Periodic `_write_modules(modules)` checkpointing every 10 synthesized in `cluster.py`
- `_deduplicate_module_names(modules)` at end of cluster synthesis
- `progress_callback("cluster_synthesis", ...)` updates
- `failed` counter semantics on error
- Commit style: short conventional commit messages (`feat:`, `fix:`, `test:`), **no `Co-Authored-By` trailer**

**Testing convention:** At least one test per feature must not mock the seam under test — per Phase 112 Fix 8 lesson. For LLM-dispatch seams, tests may fake `llm.generate` but must exercise the real `llm_pool` + `as_completed` + `finally`-cancel flow.

---

## File Structure

**Will be modified:**
- `src/codrag/core/cluster.py` — Rewrite the batched-BYOK block at lines 1607-1700 to submit per-batch work to `llm_pool`.
- `src/codrag/core/concept_seeder.py` — Rewrite `_seed_concepts_sequential` (lines 95-192) to a per-module fan-out that reuses the swarm-path helpers (`_load_modules_for_swarm`, `_build_module_summary`, `_build_module_context`) without the coordinator/synthesizer overhead.

**Will be created:**
- `tests/test_cluster_parallel_batched.py` — exercises the rewritten batched path with a fake `LLMClient`.
- `tests/test_concept_seeder_parallel.py` — exercises the rewritten sequential/per-module path with `prefer_swarm=False`.

**Will NOT be touched (already parallel on non-swarm paths):**
- `src/codrag/core/atlas/` — already uses `ThreadPoolExecutor`
- `src/codrag/services/pipeline/workers.py` (group_reasoning / audit workers) — already uses pool submits
- `src/codrag/core/augmenter.py`, `epistemic_enrichment.py` — already parallel

---

## Task 1: Parallelize `cluster.py` batched-BYOK loop

**Files:**
- Modify: `src/codrag/core/cluster.py:1607-1700` (the `if use_batching:` block)
- Test: `tests/test_cluster_parallel_batched.py` (create)

**Context for the implementer (scene-setting):**

This is the first of two parallelization fixes. The current code takes a list of clusters to synthesize, chunks them into `batch_size`-sized batches, and calls `self.llm.generate(...)` once per batch — serially. With Phase 82's AIMD gate discovering a current_limit of ~29 on cloud providers, the serial loop means `in_flight_requests` stays at 1 for the entire clustering stage.

The fix: build all batch prompts up front, then submit each batch's `self.llm.generate(...)` call to `llm_pool`. Collect results with `as_completed(futures, timeout=batch_timeout_sec)`, apply the per-item result logic inside the callback, and cancel orphaned futures in a `finally` block.

The `_write_modules` checkpoint (every 10 synthesized) and `progress_callback` must still fire — they now fire from inside the result-collection loop instead of the submission loop.

- [ ] **Step 1: Write the failing test — parallel fan-out submits >1 future concurrently**

```python
# tests/test_cluster_parallel_batched.py
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


def _make_synthesizer_with_batch_profile(fake_llm, monkeypatch):
    """Build a ClusterSynthesizer instance with a batching-on profile."""
    from codrag.core.cluster import ClusterSynthesizer
    from codrag.core.batch_profiles import BatchProfile, ProfileName, BatchStage

    synth = ClusterSynthesizer.__new__(ClusterSynthesizer)
    synth.llm = fake_llm
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
    from codrag.core.cluster import ClusterSynthesizer  # noqa: F401
    import types

    fake_llm = _FakeLLM(latency=0.25)
    synth = _make_synthesizer_with_batch_profile(fake_llm, None)

    clusters = [_FakeCluster(i) for i in range(10)]
    epistemic: dict = {}  # empty — avg_conf will be 0
    edges: list = []

    modules: dict = {}
    progress_calls = []

    def progress_callback(stage, current, total, reused):
        progress_calls.append((stage, current, total, reused))

    # The method under test is the batched block of _synthesize_cluster_llm.
    # We exercise via the public entry point _synthesize_cluster_llm, but
    # to keep the test scope tight we call a helper that inlines just the
    # batched block. If no such helper exists, this test will need to go
    # through the full cluster synthesis path.
    synth._synthesize_batched(
        clusters=clusters,
        epistemic=epistemic,
        edges=edges,
        modules=modules,
        progress_callback=progress_callback,
        reused=0,
        total_work=len(clusters),
        synthesized_start=0,
        failed_start=0,
    )

    assert fake_llm.calls == 5, f"expected 5 batch calls, got {fake_llm.calls}"
    assert fake_llm._peak >= 2, (
        f"expected peak in-flight ≥2 (fan-out working); got {fake_llm._peak}"
    )
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/pytest tests/test_cluster_parallel_batched.py -v`
Expected: FAIL — either `AttributeError: _synthesize_batched` (helper doesn't exist yet) or `peak == 1` (current code is serial).

- [ ] **Step 3: Extract the batched block into a helper method `_synthesize_batched`**

This is a refactor with no behavior change — extract `cluster.py:1607-1700` into a method so the test can target it. Add the method signature:

```python
def _synthesize_batched(
    self,
    *,
    clusters: list,
    epistemic: dict,
    edges: list,
    modules: dict,
    progress_callback,
    reused: int,
    total_work: int,
    synthesized_start: int,
    failed_start: int,
    cancel_token=None,
) -> tuple[int, int]:
    """Run the batched-BYOK cluster synthesis. Returns (synthesized, failed) deltas.

    This is the non-swarm batched fallback path. Each batch is submitted to
    the shared llm_pool so that Phase 82's AIMD gate (the real throttle
    inside LLMClient.generate) sees concurrent submissions and discovers
    the provider's real rate-limit ceiling.
    """
    # ... (see Step 4 for the parallelized body)
```

And replace the inline `if use_batching:` block at line 1607 with a single call to this method:

```python
if use_batching:
    synth_delta, fail_delta = self._synthesize_batched(
        clusters=to_synthesize,
        epistemic=epistemic,
        edges=edges,
        modules=modules,
        progress_callback=progress_callback,
        reused=reused,
        total_work=total_work,
        synthesized_start=synthesized,
        failed_start=failed,
        cancel_token=cancel_token,
    )
    synthesized += synth_delta
    failed += fail_delta
else:
    # Local model: sequential or concurrent (unchanged — see line 1702)
    ...
```

- [ ] **Step 4: Write the parallel implementation inside `_synthesize_batched`**

Place the new method near the existing `synthesize_cluster` method in `cluster.py`. Full implementation:

```python
def _synthesize_batched(
    self,
    *,
    clusters: list,
    epistemic: dict,
    edges: list,
    modules: dict,
    progress_callback,
    reused: int,
    total_work: int,
    synthesized_start: int,
    failed_start: int,
    cancel_token=None,
) -> tuple[int, int]:
    """Parallel batched-BYOK cluster synthesis via shared llm_pool."""
    import os
    import threading
    from concurrent.futures import as_completed
    from concurrent.futures import TimeoutError as FutureTimeoutError
    from datetime import datetime, timezone

    from codrag.services.pipeline.thread_pool import llm_pool

    from .batch_profiles import BatchStage
    from .batch_prompts import (
        BATCHED_CLUSTER_SYSTEM,
        build_batched_cluster_prompt,
        get_structured_schema,
    )
    from .batch_strategy import BatchedResponseParser
    from .model_config import PipelineTask, compute_optimal_settings
    from .prompt_builder import batched_max_chars

    batch_size = self._batch_profile.batch_size(BatchStage.CLUSTERING)
    logger.info(
        "BATCHED cluster synthesis: %d clusters, batch_size=%d (%s profile) — parallel",
        len(clusters), batch_size, self._batch_profile.name.value,
    )
    schema = get_structured_schema("clustering")

    # Build per-batch work items up front
    batches: list[list[dict]] = []
    for batch_start in range(0, len(clusters), batch_size):
        batch = clusters[batch_start:batch_start + batch_size]
        items = []
        for cluster in batch:
            member_summaries = self._build_member_summaries(cluster, epistemic, max_files=30)
            external_deps = self._build_external_deps(cluster, edges, epistemic)
            items.append({
                "cluster_name": cluster.primary_tag.replace("_", " ").replace("-", " ").title(),
                "domain_tags": ", ".join(sorted(cluster.all_tags)),
                "file_count": len(cluster.member_node_ids),
                "member_summaries": member_summaries,
                "external_deps": external_deps,
                "_cluster": cluster,
            })
        batches.append(items)

    def _call_batch(items: list[dict]) -> tuple[list[dict], list[dict]]:
        """Run one batched LLM call. Returns (items, results_list)."""
        prompt = build_batched_cluster_prompt(items)
        try:
            prompt_tokens = len(prompt) // 4
            num_predict, num_ctx, _warnings = compute_optimal_settings(
                task=PipelineTask.CLUSTER,
                prompt_tokens=prompt_tokens,
                model=self.llm.model,
                think=False,
            )
            text, _tokens = self.llm.generate(
                prompt,
                system=BATCHED_CLUSTER_SYSTEM,
                num_predict=num_predict,
                num_ctx=num_ctx,
                response_schema=schema,
                max_chars=batched_max_chars("augmentation", len(items)),
            )
            results_list = BatchedResponseParser.parse(text, expected_count=len(items))
        except Exception as e:
            logger.warning("Batched cluster synthesis failed for %d items: %s", len(items), e)
            results_list = []
        return items, results_list

    lock = threading.Lock()
    synthesized_delta = 0
    failed_delta = 0
    done_count = 0

    batch_timeout_sec = float(
        os.environ.get("CODRAG_CLUSTER_BATCH_TIMEOUT", "900")
    )

    pool = llm_pool
    futures = {pool.submit(_call_batch, items): items for items in batches}

    try:
        for future in as_completed(futures, timeout=batch_timeout_sec):
            if cancel_token and cancel_token.is_cancelled:
                logger.info(
                    "Cluster synthesis cancelled after %d/%d batches — flushing partial results",
                    done_count, len(batches),
                )
                with lock:
                    self._write_modules(modules)
                cancel_token.raise_if_cancelled()

            try:
                items, results_list = future.result()
            except Exception as e:
                logger.warning("Batched cluster future failed: %s", e)
                with lock:
                    failed_delta += len(futures[future])
                    done_count += 1
                continue

            for idx, item in enumerate(items):
                cluster = item["_cluster"]
                cluster_name = item["cluster_name"]
                parsed = results_list[idx] if idx < len(results_list) else None
                if not parsed:
                    parsed = {
                        "name": f"{cluster_name} Subsystem",
                        "summary": (
                            f"Cluster of {len(cluster.member_node_ids)} files related to "
                            f"{cluster.primary_tag}. (Batch synthesis failed)"
                        ),
                        "component_status": "unknown",
                    }

                module_id = f"module:{cluster.cluster_id.replace('cluster:', '')}"
                confs = [
                    epistemic[nid].epistemic_confidence
                    for nid in cluster.member_node_ids
                    if nid in epistemic
                ]
                avg_conf = sum(confs) / len(confs) if confs else 0.0

                module = ModuleEntry(
                    module_id=module_id,
                    name=str(parsed.get("name", cluster_name))[:200],
                    summary=str(parsed.get("summary", ""))[:1000],
                    member_files=[nid.replace("file:", "", 1) for nid in cluster.member_node_ids],
                    domain_tags=sorted(cluster.all_tags),
                    architecture_layers=sorted(parsed.get("architecture_layers", [])),
                    component_status=parsed.get("component_status", "unknown"),
                    data_flow=parsed.get("data_flow"),
                    dependencies=parsed.get("dependencies"),
                    tech_debt_summary=parsed.get("tech_debt_summary"),
                    file_count=len(cluster.member_node_ids),
                    avg_epistemic_confidence=avg_conf,
                    synthesized_at=datetime.now(timezone.utc).isoformat(),
                    model=self.llm.model,
                )
                with lock:
                    modules[module.module_id] = module
                    synthesized_delta += 1
                    # Periodic checkpoint (every 10 synthesized, global count)
                    total_synth = synthesized_start + synthesized_delta
                    if total_synth > 0 and total_synth % 10 == 0:
                        self._write_modules(modules)
                        logger.info(
                            "Cluster checkpoint saved at %d/%d clusters",
                            total_synth, total_work,
                        )

            with lock:
                done_count += 1
                if progress_callback:
                    progress_callback(
                        "cluster_synthesis",
                        reused + synthesized_delta + failed_delta,
                        total_work,
                        reused,
                    )
    except FutureTimeoutError:
        pending = [futures[f] for f in futures if not f.done()]
        logger.error(
            "Cluster batched synthesis timed out after %.0fs: %d/%d batches pending, "
            "cancelling and continuing.",
            batch_timeout_sec, len(pending), len(futures),
        )
        with lock:
            failed_delta += sum(len(items) for items in pending)
    finally:
        # Cancel any pending futures so orphaned work doesn't hold pool slots
        # needed by later stages. Shared pool — do NOT shut it down.
        for f in futures:
            if not f.done():
                f.cancel()

    return synthesized_delta, failed_delta
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `.venv/bin/pytest tests/test_cluster_parallel_batched.py -v`
Expected: PASS — `fake_llm.calls == 5` and `fake_llm._peak >= 2`.

- [ ] **Step 6: Add a cancellation test**

```python
def test_batched_synthesis_respects_cancel_token():
    """When cancel_token fires mid-run, remaining futures are cancelled
    and _write_modules is called to flush partial progress."""
    from codrag.services.pipeline.cancellation import CancelToken

    fake_llm = _FakeLLM(latency=0.2)
    synth = _make_synthesizer_with_batch_profile(fake_llm, None)

    writes = []
    synth._write_modules = lambda modules: writes.append(len(modules))

    token = CancelToken()
    clusters = [_FakeCluster(i) for i in range(20)]

    # Cancel after 100ms — some batches will complete, others won't
    import threading as _t
    _t.Timer(0.1, token.cancel).start()

    modules: dict = {}
    with pytest.raises(Exception):  # CancelToken raises on cancel
        synth._synthesize_batched(
            clusters=clusters, epistemic={}, edges=[], modules=modules,
            progress_callback=None, reused=0, total_work=len(clusters),
            synthesized_start=0, failed_start=0, cancel_token=token,
        )

    assert len(writes) >= 1, "expected _write_modules to be called on cancel"
```

Run: `.venv/bin/pytest tests/test_cluster_parallel_batched.py -v`
Expected: Both tests PASS.

- [ ] **Step 7: Run the existing cluster test suite for regressions**

Run: `.venv/bin/pytest tests/ -k cluster -v`
Expected: All existing cluster tests still pass.

- [ ] **Step 8: Commit**

```bash
git add src/codrag/core/cluster.py tests/test_cluster_parallel_batched.py
git commit -m "feat(cluster): parallelize batched-BYOK cluster synthesis via llm_pool"
```

---

## Task 2: Parallelize `concept_seeder.py` non-swarm path

**Files:**
- Modify: `src/codrag/core/concept_seeder.py:95-192` (rewrite `_seed_concepts_sequential` + add per-module helper)
- Test: `tests/test_concept_seeder_parallel.py` (create)

**Context for the implementer (scene-setting):**

Unlike `cluster.py`, the current `_seed_concepts_sequential` is not a loop — it assembles a single global-context prompt and makes **one** LLM call. To give this path parallelism benefit we restructure it as a per-module fan-out: one `llm.generate` call per module, submitted to `llm_pool`, with results merged by simple title-based dedup (the swarm path's LLM-powered synthesizer is intentionally not included — that's what swarm is for).

The existing `_load_modules_for_swarm`, `_build_module_summary`, and `_build_module_context` helpers (lines 255-283 region, see `concept_seeder.py`) are reusable. The per-module worker prompt can be adapted from the swarm `worker_fn`.

**Edge case:** when the project has fewer than 2 modules meeting the threshold, preserve the original single-call behavior as a safety net (1 module = nothing to parallelize).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_concept_seeder_parallel.py
"""Task 2: verify non-swarm concept seeding fans out across modules via llm_pool."""
from __future__ import annotations

import json
import threading
import time
from unittest.mock import MagicMock, patch

import pytest


class _FakeConceptLLM:
    """Fake LLMClient for concept seeding. Records concurrent in-flight calls."""

    def __init__(self, latency: float = 0.1) -> None:
        self.model = "fake/concept-model"
        self.provider = "fake"
        self._latency = latency
        self._in_flight = 0
        self._peak = 0
        self._lock = threading.Lock()
        self.calls = 0

    def generate(self, prompt=None, **_kw):
        with self._lock:
            self._in_flight += 1
            if self._in_flight > self._peak:
                self._peak = self._in_flight
            self.calls += 1
        try:
            time.sleep(self._latency)
            return (
                json.dumps({
                    "concepts": [
                        {
                            "title": f"Concept-{self.calls}",
                            "content": "why this matters",
                            "category": "architecture",
                            "confidence": 0.8,
                            "anchors": [],
                            "tags": [],
                        }
                    ]
                }),
                {"in": 10, "out": 10},
            )
        finally:
            with self._lock:
                self._in_flight -= 1


def _fake_modules(n: int) -> list[dict]:
    return [
        {
            "module_id": f"mod{i}",
            "name": f"Module {i}",
            "member_files": [f"path/mod{i}/file{j}.py" for j in range(6)],
            "summary": f"module {i} summary",
        }
        for i in range(n)
    ]


def test_concept_seeding_parallel_fans_out_per_module(tmp_path, monkeypatch):
    """With 6 modules and prefer_swarm=False, the non-swarm path should
    submit 6 per-module LLM calls concurrently via llm_pool."""
    from codrag.core import concept_seeder

    fake_llm = _FakeConceptLLM(latency=0.25)

    # Fake the project + registry plumbing
    fake_project = MagicMock()
    fake_project.name = "FakeProj"
    fake_project.path = str(tmp_path)

    saves: list[dict] = []

    with patch.object(concept_seeder, "require_project", return_value=fake_project, create=True), \
         patch.object(concept_seeder, "project_index_dir", return_value=tmp_path, create=True), \
         patch.object(concept_seeder, "_get_seeder_llm", return_value=fake_llm), \
         patch.object(concept_seeder, "_load_modules_for_swarm",
                      return_value=_fake_modules(6)), \
         patch.object(concept_seeder, "concept_store") as cs_mock:

        cs_mock.save = MagicMock(side_effect=lambda **kw: saves.append(kw))
        cs_mock.save_question = MagicMock()

        result = concept_seeder.seed_concepts("proj-1", prefer_swarm=False)

    assert fake_llm.calls == 6, f"expected 6 per-module calls, got {fake_llm.calls}"
    assert fake_llm._peak >= 2, (
        f"expected peak in-flight ≥2 (fan-out working); got {fake_llm._peak}"
    )
    assert result["status"] == "success"
    assert result["concepts_created"] == len(saves)
    assert result["mode"] == "parallel"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/pytest tests/test_concept_seeder_parallel.py -v`
Expected: FAIL — either attribute errors from missing imports, or `calls == 1` / `mode != "parallel"` (current path makes one global call).

- [ ] **Step 3: Rewrite `_seed_concepts_sequential` as a per-module fan-out**

Replace the body of `_seed_concepts_sequential` in `src/codrag/core/concept_seeder.py`. Keep the function name (it is the named fallback target in `seed_concepts`) but change `"mode"` to `"parallel"` in the success path, and to `"single_call"` in the ≤1-module safety-net path.

```python
def _seed_concepts_sequential(project_id: str) -> dict[str, Any]:
    """Non-swarm concept seeding with per-module fan-out via llm_pool.

    Phase 82 follow-up: historically this was a single global-context LLM
    call. When swarm is off (or the model doesn't support swarm), that
    left the AIMD gate underused. Now we decompose by module and submit
    per-module LLM calls to the shared llm_pool, so the AIMD gate sees
    concurrent work regardless of swarm toggle state.

    Falls back to the original single-call behavior when there are fewer
    than 2 modules with ≥MIN_MODULE_FILES_FOR_SWARM files — not enough
    work to parallelize.
    """
    import os
    import threading
    from concurrent.futures import as_completed
    from concurrent.futures import TimeoutError as FutureTimeoutError

    from codrag.core.project_registry import project_index_dir
    from codrag.services.concept_store import concept_store
    from codrag.services.pipeline.thread_pool import llm_pool
    from codrag.services.project_helpers import require_project

    project = require_project(project_id)
    index_dir = project_index_dir(project)

    # 1. Get LLM client
    llm = _get_seeder_llm()
    if llm is None:
        return {
            "status": "no_model",
            "message": "No LLM model configured. Configure a thinking model "
                       "in Settings → AI Models to generate concepts.",
            "concepts_created": 0,
            "questions_created": 0,
        }

    # 2. Load modules (reuse swarm-path helper for consistency)
    modules = _load_modules_for_swarm(index_dir)
    if len(modules) < 2:
        # Not enough work to parallelize — preserve the original
        # single-call behavior as a safety net.
        return _seed_concepts_single_call(project_id, llm=llm, project=project, index_dir=index_dir)

    logger.info(
        "[Concepts/Parallel] Fan-out: %d modules via shared llm_pool (model=%s)",
        len(modules), llm.model,
    )

    # 3. Build per-module work items and submit to the pool
    project_name = project.name

    def _call_worker(module: dict) -> str | None:
        module_data = _build_module_context(module)
        worker_prompt = (
            'You are analyzing the "{name}" subsystem of the codebase "{project}".\n\n'
            'Module data:\n{ctx}\n\n'
            'Generate 3-8 concept seeds that capture the WHY of this subsystem. '
            'Focus on design rationale, hidden constraints, trade-offs, and '
            'business decisions that are not obvious from reading the code itself.\n\n'
            'Each concept must be SPECIFIC to this subsystem. Anchor concepts '
            'to specific files in member_files.\n\n'
            'Respond with JSON only:\n'
            '{{"concepts": [{{"title": "...", "content": "2-4 sentences", '
            '"category": "architecture|domain|product|epistemic|process|brand|'
            'security|technical|pattern|constraint|decision", '
            '"confidence": 0.5-1.0, "anchors": ["..."], "tags": ["..."]}}]}}'
        ).format(
            name=module.get("name", module.get("module_id", "unknown")),
            project=project_name,
            ctx=json.dumps(module_data)[:2500],
        )
        try:
            text, _tokens = llm.generate(
                prompt=worker_prompt,
                json_mode=True,
                temperature=0.3,
                num_predict=4000,
                think=False,
            )
            return text
        except Exception:
            logger.warning("Concept worker failed for %s",
                           module.get("module_id", module.get("name")), exc_info=True)
            return None

    lock = threading.Lock()
    raw_responses: list[tuple[str, str | None]] = []

    batch_timeout_sec = float(
        os.environ.get("CODRAG_CONCEPTS_BATCH_TIMEOUT", "900")
    )

    pool = llm_pool
    futures = {pool.submit(_call_worker, mod): mod for mod in modules}
    try:
        for future in as_completed(futures, timeout=batch_timeout_sec):
            mod = futures[future]
            try:
                text = future.result()
            except Exception as e:
                logger.warning("Concept seed future failed for %s: %s",
                               mod.get("module_id"), e)
                text = None
            with lock:
                raw_responses.append((mod.get("module_id", "unknown"), text))
    except FutureTimeoutError:
        pending = [futures[f].get("module_id") for f in futures if not f.done()]
        logger.error(
            "Concept seeding batch timed out after %.0fs: %d/%d modules pending. "
            "Pending: %s",
            batch_timeout_sec, len(pending), len(futures), pending[:5],
        )
    finally:
        for f in futures:
            if not f.done():
                f.cancel()

    # 4. Merge + dedup by title
    seen_titles: set[str] = set()
    all_concepts: list[dict] = []
    for _mid, text in raw_responses:
        if not text:
            continue
        parsed = _parse_llm_response(text)
        for c in parsed.get("concepts", []):
            title = (c.get("title") or "").strip().lower()
            if not title or title in seen_titles:
                continue
            seen_titles.add(title)
            all_concepts.append(c)

    if not all_concepts:
        return {
            "status": "no_concepts",
            "mode": "parallel",
            "message": "Per-module fan-out produced no concepts.",
            "concepts_created": 0,
            "questions_created": 0,
        }

    # 5. Save concepts
    concepts_created = 0
    for c in all_concepts:
        try:
            concept_store.save(
                project_id=project_id,
                title=c.get("title", "Untitled"),
                content=c.get("content", ""),
                category=c.get("category", "technical"),
                status="seed",
                confidence=c.get("confidence", 0.7),
                anchors=c.get("anchors", []),
                tags=c.get("tags", []),
            )
            concepts_created += 1
        except Exception as e:
            logger.warning("Failed to save concept '%s': %s", c.get("title"), e)

    logger.info(
        "Concept seeding (parallel) complete for %s: %d concepts from %d modules",
        project_id, concepts_created, len(modules),
    )

    return {
        "status": "success",
        "mode": "parallel",
        "concepts_created": concepts_created,
        "questions_created": 0,
        "message": f"Generated {concepts_created} concept seeds across "
                   f"{len(modules)} modules (parallel fan-out).",
    }
```

- [ ] **Step 4: Extract the original single-call body into `_seed_concepts_single_call`**

Preserve the original single-call path as a safety net for tiny projects. Place it alongside the rewritten function:

```python
def _seed_concepts_single_call(project_id: str, *, llm, project, index_dir) -> dict[str, Any]:
    """Original single-call concept seeding (pre-parallel behavior).

    Retained as a safety-net for projects with <2 modules meeting the
    module-files threshold, where per-module fan-out is not useful.
    """
    from codrag.services.concept_store import concept_store

    context_text = _assemble_seeding_context(index_dir, project.path)
    if not context_text or len(context_text) < 100:
        return {
            "status": "insufficient_data",
            "message": "Not enough pipeline data to seed concepts. "
                       "Run the knowledge pipeline first (Fast Sync + Deep Enrichment).",
            "concepts_created": 0,
            "questions_created": 0,
        }

    try:
        raw_response = _call_llm_for_concepts(llm, context_text, project.name)
    except Exception as e:
        logger.error("Concept seeding LLM call failed: %s", e, exc_info=True)
        return {
            "status": "llm_error",
            "message": f"LLM call failed: {e}",
            "concepts_created": 0,
            "questions_created": 0,
        }

    parsed = _parse_llm_response(raw_response)
    concepts_created = 0
    questions_created = 0

    for c in parsed.get("concepts", []):
        try:
            concept_store.save(
                project_id=project_id,
                title=c.get("title", "Untitled"),
                content=c.get("content", ""),
                category=c.get("category", "technical"),
                status="seed",
                confidence=c.get("confidence", 0.7),
                anchors=c.get("anchors", []),
                tags=c.get("tags", []),
            )
            concepts_created += 1
        except Exception as e:
            logger.warning("Failed to save concept '%s': %s", c.get("title"), e)

    for q in parsed.get("questions", []):
        try:
            concept_store.save_question(
                project_id=project_id,
                question=q.get("question", ""),
                context=q.get("context", ""),
                suggested_category=q.get("suggested_category", "technical"),
                target_module=q.get("target_module"),
            )
            questions_created += 1
        except Exception as e:
            logger.warning("Failed to save question: %s", e)

    return {
        "status": "success",
        "mode": "single_call",
        "concepts_created": concepts_created,
        "questions_created": questions_created,
        "message": f"Generated {concepts_created} concept seeds and "
                   f"{questions_created} clarifying questions.",
    }
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `.venv/bin/pytest tests/test_concept_seeder_parallel.py -v`
Expected: PASS — `fake_llm.calls == 6`, `peak >= 2`, `mode == "parallel"`.

- [ ] **Step 6: Add a safety-net test for ≤1 module**

```python
def test_concept_seeding_falls_back_to_single_call_for_tiny_project(tmp_path):
    """Projects with <2 modules should still work via the single-call path."""
    from codrag.core import concept_seeder
    from unittest.mock import patch, MagicMock

    fake_llm = _FakeConceptLLM(latency=0.05)
    fake_project = MagicMock()
    fake_project.name = "Tiny"
    fake_project.path = str(tmp_path)

    with patch.object(concept_seeder, "require_project", return_value=fake_project, create=True), \
         patch.object(concept_seeder, "project_index_dir", return_value=tmp_path, create=True), \
         patch.object(concept_seeder, "_get_seeder_llm", return_value=fake_llm), \
         patch.object(concept_seeder, "_load_modules_for_swarm", return_value=[]), \
         patch.object(concept_seeder, "_assemble_seeding_context",
                      return_value="x" * 500), \
         patch.object(concept_seeder, "_call_llm_for_concepts",
                      return_value='{"concepts": [], "questions": []}'), \
         patch.object(concept_seeder, "concept_store") as cs_mock:

        cs_mock.save = MagicMock()
        cs_mock.save_question = MagicMock()

        result = concept_seeder.seed_concepts("proj-tiny", prefer_swarm=False)

    assert result["status"] == "success"
    assert result["mode"] == "single_call"
```

Run: `.venv/bin/pytest tests/test_concept_seeder_parallel.py -v`
Expected: Both tests PASS.

- [ ] **Step 7: Run related test suites for regressions**

Run: `.venv/bin/pytest tests/ -k "concept" -v`
Expected: All existing concept-related tests still pass (including `test_concept_seeder_swarm*` if present).

- [ ] **Step 8: Commit**

```bash
git add src/codrag/core/concept_seeder.py tests/test_concept_seeder_parallel.py
git commit -m "feat(concepts): parallelize non-swarm concept seeding via per-module fan-out"
```

---

## Task 3: Scrutiny / regression review pass

**Files:** (review-only, fixups as needed)
- `src/codrag/core/cluster.py`
- `src/codrag/core/concept_seeder.py`
- `tests/test_cluster_parallel_batched.py`
- `tests/test_concept_seeder_parallel.py`

**Context:**

After Tasks 1 and 2 land, do a focused review pass for five categories of regression that parallelization can introduce. No subagent dispatch — this is a human/implementer read-through with mechanical checks. Fix anything flagged before proceeding to Task 4.

- [ ] **Step 1: Verify shared-state safety in both new code paths**

For each of `cluster.py:_synthesize_batched` and `concept_seeder.py:_seed_concepts_sequential`:

Read the function top-to-bottom and list every mutation of a shared dict/list/counter. For each one, confirm it is either:
- inside the `with lock:` block, or
- appending to a `list` that is only read after `as_completed` drains, or
- a thread-safe primitive (e.g. `dict.__setitem__` on the same key never races)

If any mutation is unlocked and could race, fix it and note the change in the commit.

**Expected findings:** none, but specifically check `modules[module.module_id] = module`, `synthesized_delta`, `failed_delta`, `done_count`, `raw_responses.append(...)`.

- [ ] **Step 2: Verify `llm_pool` is NOT shut down anywhere**

Run: `.venv/bin/python -c "import ast, pathlib; [print(p) for p in pathlib.Path('src/codrag/core').rglob('*.py') if 'llm_pool.shutdown' in p.read_text() or 'pool.shutdown' in p.read_text()]"`

Or simpler:

Run: Grep tool with pattern `llm_pool\.shutdown|pool\.shutdown` across `src/codrag/core/` and `src/codrag/services/pipeline/`.

Expected: No results OR the only results are in `thread_pool.py` itself (the proxy's own lifecycle).

- [ ] **Step 3: Verify `finally`-block cancel is present on both new paths**

Run: Grep tool for `for f in futures:` in `src/codrag/core/cluster.py` and `src/codrag/core/concept_seeder.py`.

Expected: Each parallel block has a `finally:` clause that iterates futures and calls `.cancel()` on incomplete ones. If missing, add it — it's the guardrail that prevents orphaned slot-holding on unexpected exceptions.

- [ ] **Step 4: Re-run existing pipeline smoke tests**

Run: `.venv/bin/pytest tests/test_pipeline_orchestrator.py tests/test_resume_strategy.py tests/test_selfheal_group.py -v`

Expected: PASS.

If any fail due to Task 1/2 changes, investigate the root cause (use systematic-debugging skill) rather than patching the test. The parallel paths must not change externally observable behavior of the pipeline orchestrator.

- [ ] **Step 5: Manual checkpoint-cadence review in `cluster.py`**

Read the `_synthesize_batched` `with lock:` block that increments `synthesized_delta`. Confirm:
- Checkpoint fires every 10 synthesized (using global `synthesized_start + synthesized_delta`), not every 10 per-batch.
- `_write_modules(modules)` is called under the lock so we don't checkpoint a half-mutated dict.
- Progress callback fires after each batch completes (not after each inner item).

If any of these are off, fix inline.

- [ ] **Step 6: If Steps 1-5 surfaced fixes, commit them**

```bash
git add <files-with-fixes>
git commit -m "fix(cluster,concepts): address review findings from parallel fan-out pass"
```

If no fixes, skip this step.

---

## Task 4: Live validation via playwright rebuild

**Files:** (validation only)
- Create (not committed): ad-hoc validation script in `/tmp/validate_parallel_bursts.py`
- Use: `tools/playwright_smoke.py` (existing harness)

**Context:**

The unit tests prove the code fans out against a fake LLM. The real question is whether a live rebuild on a real cloud provider (e.g. ollama cloud) shows `in_flight_requests` actually bursting beyond 1 during the clustering stage. This task executes a real rebuild and asserts the signal.

**Preconditions:**
- CoDRAG daemon running on :8400 (`curl -s localhost:8400/health`)
- Dashboard running on :5174 (`curl -sI localhost:5174`)
- A test project with ≥10 clusters and ≥6 modules (PowerMateReborn has both)
- `swarm_enabled` can be either on or off; the test explicitly disables it to exercise the non-swarm paths

- [ ] **Step 1: Toggle `swarm_enabled = false` in the settings DB**

Run:
```bash
sqlite3 ~/.local/share/codrag/codrag_settings.db \
  "UPDATE settings SET value='false' WHERE key='swarm_enabled';"
```

Confirm:
```bash
sqlite3 ~/.local/share/codrag/codrag_settings.db \
  "SELECT value FROM settings WHERE key='swarm_enabled';"
```
Expected: `false`

Rationale: This is the exact condition that caused the bug in the first place. Task 4 must prove the fix works *without* relying on swarm.

- [ ] **Step 2: Start the log watcher in the background**

Run (in a separate terminal or as a background task):
```bash
.venv/bin/python /tmp/watch_aimd.py
```

(The watcher from the prior session. `LOG_GLOB` should point at the test project's `.codrag/logs/pipeline_*.log`.)

- [ ] **Step 3: Run the playwright smoke rebuild**

Use the `playwright-smoke` skill. For PowerMateReborn:

```bash
.venv/bin/python -m tools.playwright_smoke \
  --project-id <powermate-id> \
  --modes rebuild
```

Wait for it to complete (or at least progress past the `clustering` and `concepts` stages).

- [ ] **Step 4: Assert `in_flight` bursts in the watcher log**

While the rebuild is running, confirm the watcher output contains lines like:

```
PEAK   --:--:--  in_flight=3
PEAK   --:--:--  in_flight=5
STAGE  HH:MM:SS  end clustering (peak=N, in_flight=0)
```

**Assertion:** Peak `in_flight` during the `clustering` stage must be ≥ 3 (pre-fix was 1).
**Assertion:** Peak `in_flight` during the `concepts` stage must be ≥ 3 (pre-fix was 1).

If peak is still 1 for either stage, the fix did not take effect at runtime. Re-read the stage's entry point (check whether it is actually calling the new parallel path) and use the systematic-debugging skill to trace.

- [ ] **Step 5: Spot-check the dashboard sidebar strip**

Open http://localhost:5174 in a browser (or use headed playwright). While clustering is running, the sidebar's pipeline queue strip for `cloud:default_ollama` should show an `in_flight_requests` value > 1 at least transiently (e.g. `3 / 23 (max 10)`).

Screenshot this for the record (the playwright harness does this automatically if used).

- [ ] **Step 6: Restore `swarm_enabled = true` (or leave off — user preference)**

If you want to return to the "swarm path when available" default:

```bash
sqlite3 ~/.local/share/codrag/codrag_settings.db \
  "UPDATE settings SET value='true' WHERE key='swarm_enabled';"
```

(This is a dev-machine state change only — no commit.)

- [ ] **Step 7: Document the validation result**

Append a brief note (2-3 lines) to the end of this plan file or a dated entry in `docs/Phase116_strategic-oversight/` (whichever is current) with:
- Project ID used
- Peak `in_flight` observed for clustering
- Peak `in_flight` observed for concepts
- Whether swarm was on or off

No commit required if just appending to a private log; commit if the note is to the plan file.

- [ ] **Step 8: If Task 4 passes, mark plan complete**

Use the `superpowers:finishing-a-development-branch` skill to close out (merge to main if you were on a worktree, otherwise it's already merged).

---

## Self-Review Checklist

Before dispatching implementation:

- [ ] **Spec coverage:** Every user-stated requirement has a task — parallelize `cluster.py` batched loop ✓, parallelize `concept_seeder.py` sequential path ✓, scrutiny pass ✓, live playwright validation ✓.
- [ ] **Placeholder scan:** No TBD, no "add error handling", no "similar to Task N". Every code step has complete code.
- [ ] **Type consistency:** `_synthesize_batched` signature, `_seed_concepts_sequential` return dict keys, `_seed_concepts_single_call` return dict keys all aligned.
- [ ] **Reference pattern:** `deepening.py:439-509` pattern reproduced in both new paths (shared pool, `as_completed(timeout)`, `FutureTimeoutError` branch, `finally:` cancel).
- [ ] **Non-goals explicit:** atlas, group_reasoning, audit, augmenter, epistemic_enrichment are out of scope (already parallel).
- [ ] **`llm_pool` path correct:** `src/codrag/services/pipeline/thread_pool.py` (not `llm_pool.py`).
- [ ] **Test convention honored:** Each task has ≥1 test that doesn't mock `as_completed`/`llm_pool` — the real pool is used, only `llm.generate` is faked.
- [ ] **Commit style:** Short conventional prefix, no `Co-Authored-By`.

---

## Execution Handoff

Plan saved to `docs/superpowers/plans/2026-04-20-parallel-non-swarm-fallbacks.md`. Two execution options:

1. **Subagent-Driven (recommended)** — fresh subagent per task, two-stage review (spec compliance then code quality) between tasks. Uses `superpowers:subagent-driven-development`.
2. **Inline Execution** — execute tasks in this session with checkpoints for human review. Uses `superpowers:executing-plans`.

Which approach?
