# Clustering & Atlas Swarm Integration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add swarm orchestration (coordinator → fan-out → synthesis) to Stage 8 (Clustering) and Stage 9 (Atlas Generation), reusing the existing `SwarmOrchestrator`.

**Architecture:** Each stage gets: (1) a `_get_swarm_enabled()` check, (2) a `_run_swarm()` method that constructs WorkItems from stage data, defines coordinator/synthesis prompts, and bridges the worker callback to the stage's existing analysis method, (3) a swarm decision branch in the main `run()`/`generate_segmented()` method. Pattern is identical to Group Reasoning (`src/prep/core/group_reasoning.py:324-570`).

**Tech Stack:** Python 3.11+, `SwarmOrchestrator` from `src/prep/core/swarm_orchestrator.py`, `SwarmRegistry` from `src/prep/core/swarm_registry.py`, existing `ClusterSynthesizer` and `CodebaseAtlas` classes.

**Spec:** `docs/superpowers/specs/2026-04-07-clustering-atlas-swarm-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `src/prep/core/cluster.py` | Modify | Add swarm integration to `ClusterSynthesizer` |
| `src/prep/core/atlas/generator.py` | Modify | Add swarm integration to `CodebaseAtlas.generate_segmented()` |
| `tests/test_cluster_swarm.py` | Create | Swarm decision + integration tests for clustering |
| `tests/test_atlas_swarm.py` | Create | Swarm decision + integration tests for atlas |

---

### Task 1: Clustering Swarm — Decision Tests

**Files:**
- Create: `tests/test_cluster_swarm.py`

- [ ] **Step 1: Write swarm decision tests**

Write `tests/test_cluster_swarm.py`:

```python
"""Tests for swarm orchestration in Clustering (Stage 8)."""
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from prep.core.cluster import ClusterSynthesizer, Cluster, ModuleEntry
from prep.core.swarm_registry import SwarmTier


def _make_clusters(n: int) -> list[Cluster]:
    """Create n clusters with 3 files each."""
    clusters = []
    for i in range(n):
        clusters.append(Cluster(
            cluster_id=f"cluster:mod{i}:0",
            primary_tag=f"module_{i}",
            member_node_ids=[
                f"file:src/mod{i}/file{j}.py" for j in range(3)
            ],
            all_tags={f"module_{i}", "python"},
        ))
    return clusters


def _make_epistemic(clusters: list[Cluster]) -> dict:
    """Build minimal epistemic entries for all cluster members."""
    from prep.core.epistemic_score import EpistemicEntry
    entries = {}
    for cluster in clusters:
        for nid in cluster.member_node_ids:
            fp = nid.replace("file:", "", 1)
            entries[nid] = EpistemicEntry(
                node_id=nid,
                extended_summary=f"Module file at {fp}",
                architecture_layer="service",
                domain_tags=[cluster.primary_tag],
                tech_debt=[],
                confidence=0.8,
                model="test-model",
                analyzed_at="2026-04-07T00:00:00Z",
            )
    return entries


def _make_mock_llm():
    mock = MagicMock()
    mock.provider = "ollama"
    mock.model = "kimi-k2.5:cloud"
    mock.generate.return_value = (
        json.dumps({
            "name": "Test Module",
            "summary": "A test module.",
            "component_status": "complete",
            "data_flow": "A -> B",
            "dependencies": [],
            "tech_debt_summary": None,
        }),
        200,
    )
    return mock


class TestClusterSwarmDecision:
    @patch("prep.core.cluster.get_swarm_tier")
    def test_swarm_activated_when_eligible(self, mock_tier, tmp_path):
        mock_tier.return_value = SwarmTier.BOTH
        mock_llm = _make_mock_llm()
        synth = ClusterSynthesizer(llm=mock_llm, index_dir=tmp_path)

        clusters = _make_clusters(4)
        epistemic = _make_epistemic(clusters)

        with patch.object(synth, "_run_swarm", return_value={}) as mock_swarm:
            with patch.object(synth, "_get_swarm_enabled", return_value=True):
                with patch.object(synth, "load_epistemic", return_value=epistemic):
                    with patch.object(synth, "load_edges", return_value=[]):
                        with patch("prep.core.cluster.build_clusters", return_value=clusters):
                            synth.run()
                            mock_swarm.assert_called_once()

    @patch("prep.core.cluster.get_swarm_tier")
    def test_swarm_skipped_when_model_unsuitable(self, mock_tier, tmp_path):
        mock_tier.return_value = SwarmTier.UNSUITABLE
        mock_llm = _make_mock_llm()
        synth = ClusterSynthesizer(llm=mock_llm, index_dir=tmp_path)

        clusters = _make_clusters(4)
        epistemic = _make_epistemic(clusters)

        with patch.object(synth, "_run_swarm") as mock_swarm:
            with patch.object(synth, "_get_swarm_enabled", return_value=True):
                with patch.object(synth, "load_epistemic", return_value=epistemic):
                    with patch.object(synth, "load_edges", return_value=[]):
                        with patch("prep.core.cluster.build_clusters", return_value=clusters):
                            synth.run()
                            mock_swarm.assert_not_called()

    @patch("prep.core.cluster.get_swarm_tier")
    def test_swarm_skipped_when_disabled(self, mock_tier, tmp_path):
        mock_tier.return_value = SwarmTier.BOTH
        mock_llm = _make_mock_llm()
        synth = ClusterSynthesizer(llm=mock_llm, index_dir=tmp_path)

        clusters = _make_clusters(4)
        epistemic = _make_epistemic(clusters)

        with patch.object(synth, "_run_swarm") as mock_swarm:
            with patch.object(synth, "_get_swarm_enabled", return_value=False):
                with patch.object(synth, "load_epistemic", return_value=epistemic):
                    with patch.object(synth, "load_edges", return_value=[]):
                        with patch("prep.core.cluster.build_clusters", return_value=clusters):
                            synth.run()
                            mock_swarm.assert_not_called()

    @patch("prep.core.cluster.get_swarm_tier")
    def test_swarm_skipped_below_threshold(self, mock_tier, tmp_path):
        mock_tier.return_value = SwarmTier.BOTH
        mock_llm = _make_mock_llm()
        synth = ClusterSynthesizer(llm=mock_llm, index_dir=tmp_path)

        clusters = _make_clusters(2)  # Below threshold of 3
        epistemic = _make_epistemic(clusters)

        with patch.object(synth, "_run_swarm") as mock_swarm:
            with patch.object(synth, "_get_swarm_enabled", return_value=True):
                with patch.object(synth, "load_epistemic", return_value=epistemic):
                    with patch.object(synth, "load_edges", return_value=[]):
                        with patch("prep.core.cluster.build_clusters", return_value=clusters):
                            synth.run()
                            mock_swarm.assert_not_called()

    def test_get_swarm_enabled_defaults_true(self, tmp_path):
        mock_llm = _make_mock_llm()
        synth = ClusterSynthesizer(llm=mock_llm, index_dir=tmp_path)
        assert synth._get_swarm_enabled() is True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/pytest tests/test_cluster_swarm.py -v
```

Expected: FAIL — `AttributeError: 'ClusterSynthesizer' object has no attribute '_run_swarm'`

- [ ] **Step 3: Commit test file**

```bash
git add tests/test_cluster_swarm.py
git commit -m "test(swarm): add clustering swarm decision tests

Phase 79 — tests for swarm activation/skip logic in ClusterSynthesizer.
Tests verify swarm activates when model is capable, enabled, and 3+ clusters;
skips otherwise."
```

---

### Task 2: Clustering Swarm — Implementation

**Files:**
- Modify: `src/prep/core/cluster.py`

- [ ] **Step 1: Add imports**

Add after the existing imports at the top of `cluster.py` (after line 33):

```python
from .swarm_registry import get_swarm_tier, get_min_groups_threshold
from .swarm_orchestrator import SwarmOrchestrator, WorkItem, WorkerAssignment, SwarmResult
```

- [ ] **Step 2: Add `_get_swarm_enabled` method**

Add to `ClusterSynthesizer` class, after the `__init__` method (after line 949):

```python
    def _get_swarm_enabled(self) -> bool:
        """Check if swarm is enabled in pipeline settings."""
        try:
            from prep.services.settings_store import settings
            return bool(settings.get("swarm_enabled", True))
        except Exception:
            return True
```

- [ ] **Step 3: Add `synthesize_cluster_with_angle` method**

Add after `synthesize_cluster` (after line 1148):

```python
    def synthesize_cluster_with_angle(
        self,
        cluster: Cluster,
        epistemic: Dict[str, EpistemicEntry],
        edges: List[Dict[str, Any]],
        naming_guidance: str,
        analysis_angle: str,
        naming_constraints: List[str],
    ) -> Optional[ModuleEntry]:
        """Synthesize a cluster with coordinator-assigned scoping."""
        member_summaries = self._build_member_summaries(cluster, epistemic, max_files=30)
        external_deps = self._build_external_deps(cluster, edges, epistemic)

        prompt = MODULE_SYNTHESIS_PROMPT.format(
            cluster_name=cluster.primary_tag.replace("_", " ").replace("-", " ").title(),
            domain_tags=", ".join(sorted(cluster.all_tags)),
            file_count=len(cluster.member_node_ids),
            member_summaries=member_summaries,
            external_deps=external_deps,
        )

        # Append coordinator guidance
        constraints_text = ", ".join(naming_constraints) if naming_constraints else "none"
        prompt += (
            f"\n\n## Coordinator Guidance\n"
            f"Naming direction: {naming_guidance}\n"
            f"Analysis focus: {analysis_angle}\n"
            f"Names to AVOID (already used by other modules): {constraints_text}"
        )

        prompt_tokens = len(prompt) // 4
        num_predict, num_ctx, warnings = compute_optimal_settings(
            task=PipelineTask.CLUSTER,
            prompt_tokens=prompt_tokens,
            model=self.llm.model,
            think=False,
        )

        try:
            text, tokens = self.llm.generate(
                prompt, system=MODULE_SYNTHESIS_SYSTEM,
                num_predict=num_predict, num_ctx=num_ctx,
                json_mode=False, think=False,
                max_chars=TASK_MAX_CHARS["augmentation"],
            )
        except Exception as e:
            logger.warning("[Cluster/Swarm] Worker failed for %s: %s", cluster.cluster_id, e)
            return None

        parsed = _parse_json_response(text)
        if parsed is None:
            logger.warning("[Cluster/Swarm] Unparseable response for %s", cluster.cluster_id)
            return None

        module_id = f"module:{cluster.cluster_id.replace('cluster:', '')}"
        confs = [
            epistemic[nid].epistemic_confidence
            for nid in cluster.member_node_ids
            if nid in epistemic
        ]
        avg_conf = sum(confs) / len(confs) if confs else 0.0

        return ModuleEntry(
            module_id=module_id,
            name=str(parsed.get("name", cluster.primary_tag))[:200],
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
```

- [ ] **Step 4: Add `_run_swarm` method**

Add after `synthesize_cluster_with_angle`:

```python
    def _run_swarm(
        self,
        to_synthesize: List[Cluster],
        epistemic: Dict[str, EpistemicEntry],
        edges: List[Dict[str, Any]],
        progress_callback: Optional[Callable[..., None]] = None,
    ) -> Dict[str, ModuleEntry]:
        """Run swarm-orchestrated cluster synthesis.

        Returns dict of module_id -> ModuleEntry.
        Empty dict signals the caller to fall back to standard path.
        """
        # Get full swarm concurrency budget
        concurrency = 1
        try:
            from prep.services.pipeline.scheduler import pipeline_scheduler
            full = pipeline_scheduler.full_budget_for_swarm(
                self.llm.provider, self.llm.model,
            )
            if full is not None:
                concurrency = full
        except (ImportError, Exception) as exc:
            logger.debug("Swarm full budget unavailable: %s", exc)
        if concurrency <= 1:
            try:
                from prep.core.batch_profiles import get_batch_concurrency
                concurrency = get_batch_concurrency(self.llm.provider, model=self.llm.model)
            except Exception:
                concurrency = 1
        logger.info("[Cluster/Swarm] Using concurrency=%d for fan-out", concurrency)

        # TODO(Phase79-DualModel): When dual-model swarm is implemented,
        # use large_llm for coordinator/synthesis, small_llm for workers.
        # For now, single model handles all three phases.
        orch = SwarmOrchestrator(llm=self.llm, concurrency=concurrency)

        # Build WorkItems
        items: List[WorkItem] = []
        cluster_by_id: Dict[str, Cluster] = {}
        for cluster in to_synthesize:
            cluster_by_id[cluster.cluster_id] = cluster

            # Summary: primary tag + file paths (capped at 5)
            paths = [
                nid.replace("file:", "", 1)
                for nid in cluster.member_node_ids[:5]
            ]
            summary = f"{cluster.primary_tag}: {', '.join(paths)}"
            if len(cluster.member_node_ids) > 5:
                summary += f" (+{len(cluster.member_node_ids) - 5} more)"

            # Full context for worker
            member_summaries = self._build_member_summaries(cluster, epistemic, max_files=30)
            external_deps = self._build_external_deps(cluster, edges, epistemic)
            full_context = json.dumps({
                "cluster_name": cluster.primary_tag,
                "domain_tags": sorted(cluster.all_tags),
                "file_count": len(cluster.member_node_ids),
                "member_summaries": member_summaries,
                "external_deps": external_deps,
            })

            items.append(WorkItem(id=cluster.cluster_id, summary=summary, full_context=full_context))

        coordinator_prompt = (
            "You are coordinating parallel module synthesis for {n} code clusters.\n"
            "Each cluster is a group of related files that should become one named module.\n\n"
            "Clusters:\n{{group_summaries}}\n\n"
            "For EACH cluster, assign:\n"
            '- "naming_guidance": suggest a specific, descriptive module name direction\n'
            '- "analysis_angle": what aspect to emphasize in the synthesis\n'
            '- "naming_constraints": names the OTHER clusters should avoid (to prevent overlap)\n\n'
            "Respond with JSON:\n"
            '{{"assignments": [{{"item_id": "cluster:...", '
            '"analysis_angle": "...", '
            '"priority_concerns": ["naming_guidance: ...", "avoid_names: ..."]'
            "}}]}}"
        ).format(n=len(items))

        synthesis_prompt = (
            "Below are module synthesis results from {n} parallel cluster analyses.\n\n"
            "{{worker_outputs}}\n\n"
            "Assess the set of modules as a whole:\n"
            '{{"naming_consistency": "are module names coherent as a set?", '
            '"cross_cluster_deps": ["shared dependencies across clusters"], '
            '"architectural_layering": "do clusters map cleanly to layers?", '
            '"redundancy_flags": ["any clusters that seem to be the same module"], '
            '"key_insight": "most important observation about the module structure"}}'
        ).format(n=len(items))

        def worker_fn(item: WorkItem, assignment: WorkerAssignment) -> Optional[str]:
            cluster = cluster_by_id.get(item.id)
            if cluster is None:
                return None

            # Parse coordinator concerns into naming_guidance and naming_constraints
            naming_guidance = assignment.analysis_angle
            naming_constraints = []
            for concern in assignment.priority_concerns:
                if concern.startswith("naming_guidance:"):
                    naming_guidance = concern.replace("naming_guidance:", "").strip()
                elif concern.startswith("avoid_names:"):
                    naming_constraints.append(concern.replace("avoid_names:", "").strip())

            module = self.synthesize_cluster_with_angle(
                cluster, epistemic, edges,
                naming_guidance=naming_guidance,
                analysis_angle=assignment.analysis_angle,
                naming_constraints=naming_constraints,
            )
            if module is None:
                return None
            return json.dumps(module.to_dict())

        def progress_fn(done: int, total: int) -> None:
            if progress_callback:
                progress_callback("cluster_synthesis", done, len(to_synthesize), 0)

        result = orch.execute(
            items=items,
            coordinator_prompt=coordinator_prompt,
            worker_fn=worker_fn,
            synthesis_prompt=synthesis_prompt,
            progress_fn=progress_fn,
        )

        if result is None:
            return {}

        # Convert worker results to ModuleEntry objects
        modules: Dict[str, ModuleEntry] = {}
        for wr in result.worker_results:
            if wr.success and wr.parsed:
                try:
                    entry = ModuleEntry.from_dict(wr.parsed)
                    modules[entry.module_id] = entry
                except (KeyError, ValueError) as exc:
                    logger.warning("Failed to parse cluster worker result for %s: %s", wr.item_id, exc)

        # Write synthesis artifact
        if result.synthesis:
            self._write_cluster_synthesis(result)

        return modules

    def _write_cluster_synthesis(self, result: SwarmResult) -> None:
        """Write swarm synthesis artifact to disk."""
        artifact = {
            "stage": "cluster_synthesis_swarm",
            "model": self.llm.model,
            "clusters_analyzed": result.stats.total_items,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "synthesis": result.synthesis,
            "stats": {
                "workers_succeeded": result.stats.workers_succeeded,
                "workers_failed": result.stats.workers_failed,
                "wall_clock_seconds": round(result.stats.wall_clock_seconds, 1),
            },
        }
        path = self.index_dir / "trace_cluster_swarm_synthesis.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(artifact, f, indent=2, ensure_ascii=False)
        logger.info("[Cluster/Swarm] Synthesis written to %s", path)
```

- [ ] **Step 5: Add swarm decision branch to `run()`**

Insert into `ClusterSynthesizer.run()` after the reuse loop (after line 1259, before the `use_batching` decision at line 1262). The swarm check goes BEFORE the batching/concurrent decision:

```python
        # ── Swarm decision ──────────────────────────────────────────
        swarm_tier = get_swarm_tier(self.llm.provider, self.llm.model)
        swarm_enabled = self._get_swarm_enabled()
        min_threshold = get_min_groups_threshold()
        use_swarm = (
            swarm_tier.can_coordinate
            and swarm_enabled
            and len(to_synthesize) >= min_threshold
        )

        if use_swarm:
            logger.info(
                "Cluster synthesis: using SWARM orchestration (%s, %d clusters, tier=%s)",
                self.llm.model, len(to_synthesize), swarm_tier.value,
            )
            swarm_modules = self._run_swarm(
                to_synthesize, epistemic, edges, progress_callback,
            )
            if swarm_modules:
                modules.update(swarm_modules)
                synthesized = len(swarm_modules)
                failed = len(to_synthesize) - synthesized

                # Deduplicate and write
                _deduplicate_module_names(modules)
                self._write_modules(modules)

                duration_ms = (time.monotonic() - start) * 1000
                if progress_callback:
                    progress_callback("cluster_complete", total_work, total_work, reused)
                return {
                    "clusters": total_work,
                    "synthesized": synthesized,
                    "reused": reused,
                    "failed": failed,
                    "total_files_clustered": sum(
                        len(m.member_files) for m in modules.values()
                    ),
                    "duration_ms": round(duration_ms, 1),
                    "swarm": True,
                }
            else:
                logger.info("Cluster swarm coordinator failed — falling back to standard path")
                # Fall through to existing batched/concurrent logic
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_cluster_swarm.py -v
```

Expected: All 5 tests PASS.

- [ ] **Step 7: Run existing cluster tests for regression**

```bash
.venv/bin/pytest tests/ -k "cluster" -v
```

Expected: All existing + new tests PASS.

- [ ] **Step 8: Commit**

```bash
git add src/prep/core/cluster.py
git commit -m "feat(swarm): integrate swarm orchestration into Clustering stage

Stage 8 now uses coordinator → fan-out → synthesis when:
- Model is swarm-capable (registry check)
- swarm_enabled setting is true
- 3+ clusters to synthesize

Coordinator assigns naming guidance and analysis angles per cluster.
Synthesis checks naming consistency and cross-cluster dependencies.
Falls back to standard concurrent/batched path if coordinator fails."
```

---

### Task 3: Atlas Swarm — Decision Tests

**Files:**
- Create: `tests/test_atlas_swarm.py`

- [ ] **Step 1: Write swarm decision tests**

Write `tests/test_atlas_swarm.py`:

```python
"""Tests for swarm orchestration in Atlas Generation (Stage 9)."""
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

from prep.core.atlas.generator import CodebaseAtlas
from prep.core.atlas.models import Segment, AtlasDocument, SegmentDocument
from prep.core.swarm_registry import SwarmTier


def _make_segments(n: int) -> list[Segment]:
    """Create n segments with some files each."""
    segments = []
    for i in range(n):
        segments.append(Segment(
            id=f"seg:pkg{i}",
            name=f"Package {i}",
            dir_path=f"packages/pkg{i}",
            file_paths=[f"packages/pkg{i}/file{j}.py" for j in range(5)],
            module_ids=[f"module:pkg{i}:0"],
            domain_tags=[f"domain_{i}"],
        ))
    return segments


def _make_mock_llm():
    mock = MagicMock()
    mock.provider = "ollama"
    mock.model = "kimi-k2.5:cloud"
    mock.generate.return_value = (
        "SEGMENT: Test (test/, 5 files)\nROLE: Test segment.\nKEY FILES: file0.py: main entry.",
        200,
    )
    return mock


def _make_root_doc():
    return AtlasDocument(
        content="IDENTITY: Test project.\nSTACK: Python.",
        generated_at="2026-04-07T00:00:00Z",
        model="test",
        fingerprint="abc123",
        file_count=50,
        mode="segmented",
        segment_ids=["seg:pkg0", "seg:pkg1", "seg:pkg2", "seg:pkg3"],
    )


class TestAtlasSwarmDecision:
    @patch("prep.core.atlas.generator.get_swarm_tier")
    @patch("prep.core.atlas.generator.compute_segments")
    def test_swarm_activated_when_eligible(self, mock_segments, mock_tier, tmp_path):
        mock_tier.return_value = SwarmTier.BOTH
        segments = _make_segments(4)
        mock_segments.return_value = segments

        mock_llm = _make_mock_llm()
        atlas = CodebaseAtlas(index_dir=tmp_path, llm=mock_llm)

        with patch.object(atlas, "_run_swarm", return_value=([], None)) as mock_swarm:
            with patch.object(atlas, "_get_swarm_enabled", return_value=True):
                with patch.object(atlas, "_load_modules", return_value=[]):
                    with patch.object(atlas, "_load_epistemic_summary", return_value={}):
                        with patch.object(atlas, "_load_graph_stats", return_value={"file_count": 50}):
                            with patch.object(atlas, "_identify_hubs", return_value=[]):
                                with patch.object(atlas, "_generate_root_atlas", return_value=_make_root_doc()):
                                    atlas.generate_segmented()
                                    mock_swarm.assert_called_once()

    @patch("prep.core.atlas.generator.get_swarm_tier")
    @patch("prep.core.atlas.generator.compute_segments")
    def test_swarm_skipped_when_model_unsuitable(self, mock_segments, mock_tier, tmp_path):
        mock_tier.return_value = SwarmTier.UNSUITABLE
        segments = _make_segments(4)
        mock_segments.return_value = segments

        mock_llm = _make_mock_llm()
        atlas = CodebaseAtlas(index_dir=tmp_path, llm=mock_llm)

        with patch.object(atlas, "_run_swarm") as mock_swarm:
            with patch.object(atlas, "_get_swarm_enabled", return_value=True):
                with patch.object(atlas, "_load_modules", return_value=[]):
                    with patch.object(atlas, "_load_epistemic_summary", return_value={}):
                        with patch.object(atlas, "_load_graph_stats", return_value={"file_count": 50}):
                            with patch.object(atlas, "_identify_hubs", return_value=[]):
                                with patch.object(atlas, "_generate_root_atlas", return_value=_make_root_doc()):
                                    with patch.object(atlas, "_generate_segment_atlas") as mock_seg:
                                        mock_seg.return_value = SegmentDocument(
                                            content="test", generated_at="2026-04-07", model="test",
                                            fingerprint="x", file_count=5, segment_id="seg:pkg0",
                                            dir_path="packages/pkg0",
                                        )
                                        atlas.generate_segmented()
                                        mock_swarm.assert_not_called()

    @patch("prep.core.atlas.generator.get_swarm_tier")
    @patch("prep.core.atlas.generator.compute_segments")
    def test_swarm_skipped_when_disabled(self, mock_segments, mock_tier, tmp_path):
        mock_tier.return_value = SwarmTier.BOTH
        segments = _make_segments(4)
        mock_segments.return_value = segments

        mock_llm = _make_mock_llm()
        atlas = CodebaseAtlas(index_dir=tmp_path, llm=mock_llm)

        with patch.object(atlas, "_run_swarm") as mock_swarm:
            with patch.object(atlas, "_get_swarm_enabled", return_value=False):
                with patch.object(atlas, "_load_modules", return_value=[]):
                    with patch.object(atlas, "_load_epistemic_summary", return_value={}):
                        with patch.object(atlas, "_load_graph_stats", return_value={"file_count": 50}):
                            with patch.object(atlas, "_identify_hubs", return_value=[]):
                                with patch.object(atlas, "_generate_root_atlas", return_value=_make_root_doc()):
                                    with patch.object(atlas, "_generate_segment_atlas") as mock_seg:
                                        mock_seg.return_value = SegmentDocument(
                                            content="test", generated_at="2026-04-07", model="test",
                                            fingerprint="x", file_count=5, segment_id="seg:pkg0",
                                            dir_path="packages/pkg0",
                                        )
                                        atlas.generate_segmented()
                                        mock_swarm.assert_not_called()

    @patch("prep.core.atlas.generator.get_swarm_tier")
    @patch("prep.core.atlas.generator.compute_segments")
    def test_swarm_skipped_below_threshold(self, mock_segments, mock_tier, tmp_path):
        mock_tier.return_value = SwarmTier.BOTH
        segments = _make_segments(2)  # Below threshold of 3
        mock_segments.return_value = segments

        mock_llm = _make_mock_llm()
        atlas = CodebaseAtlas(index_dir=tmp_path, llm=mock_llm)

        with patch.object(atlas, "_run_swarm") as mock_swarm:
            with patch.object(atlas, "_get_swarm_enabled", return_value=True):
                with patch.object(atlas, "_load_modules", return_value=[]):
                    with patch.object(atlas, "_load_epistemic_summary", return_value={}):
                        with patch.object(atlas, "_load_graph_stats", return_value={"file_count": 50}):
                            with patch.object(atlas, "_identify_hubs", return_value=[]):
                                with patch.object(atlas, "_generate_root_atlas", return_value=_make_root_doc()):
                                    with patch.object(atlas, "_generate_segment_atlas") as mock_seg:
                                        mock_seg.return_value = SegmentDocument(
                                            content="test", generated_at="2026-04-07", model="test",
                                            fingerprint="x", file_count=5, segment_id="seg:pkg0",
                                            dir_path="packages/pkg0",
                                        )
                                        atlas.generate_segmented()
                                        mock_swarm.assert_not_called()

    def test_get_swarm_enabled_defaults_true(self, tmp_path):
        mock_llm = _make_mock_llm()
        atlas = CodebaseAtlas(index_dir=tmp_path, llm=mock_llm)
        assert atlas._get_swarm_enabled() is True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/pytest tests/test_atlas_swarm.py -v
```

Expected: FAIL — `AttributeError: 'CodebaseAtlas' object has no attribute '_run_swarm'`

- [ ] **Step 3: Commit test file**

```bash
git add tests/test_atlas_swarm.py
git commit -m "test(swarm): add atlas swarm decision tests

Phase 79 — tests for swarm activation/skip logic in CodebaseAtlas.
Tests verify swarm activates when model is capable, enabled, and 3+ segments;
skips otherwise."
```

---

### Task 4: Atlas Swarm — Implementation

**Files:**
- Modify: `src/prep/core/atlas/generator.py`

- [ ] **Step 1: Add imports**

Add after the existing imports near the top of `generator.py`:

```python
from prep.core.swarm_registry import get_swarm_tier, get_min_groups_threshold
from prep.core.swarm_orchestrator import SwarmOrchestrator, WorkItem, WorkerAssignment, SwarmResult
```

- [ ] **Step 2: Add `_get_swarm_enabled` method**

Add to `CodebaseAtlas` class, after the `__init__` method:

```python
    def _get_swarm_enabled(self) -> bool:
        """Check if swarm is enabled in pipeline settings."""
        try:
            from prep.services.settings_store import settings
            return bool(settings.get("swarm_enabled", True))
        except Exception:
            return True
```

- [ ] **Step 3: Add `_generate_segment_atlas_with_angle` method**

Add after `_generate_segment_atlas` (after line ~630):

```python
    def _generate_segment_atlas_with_angle(
        self,
        segment: Segment,
        all_modules: List[Dict[str, Any]],
        epistemic: Dict[str, Any],
        graph_stats: Dict[str, Any],
        hub_files: List[Tuple[str, int]],
        all_segments: List[Segment],
        analysis_focus: str,
        cross_segment_hints: List[str],
    ) -> SegmentDocument:
        """Generate atlas for one segment with coordinator-assigned scoping.

        Appends coordinator guidance to the standard segment atlas prompt.
        """
        # Build the standard prompt (same as _generate_segment_atlas)
        target_chars = min(
            SEGMENT_ATLAS_MAX_CHARS,
            max(SEGMENT_ATLAS_MIN_CHARS, int(segment.file_count * 8)),
        )
        max_chars = int(target_chars * 1.3)

        seg_file_set = set(segment.file_paths)
        seg_modules = [
            m for m in all_modules
            if any(fp in seg_file_set for fp in m.get("member_files", []))
        ]
        seg_hubs = [(p, d) for p, d in hub_files if p in seg_file_set]
        seg_to_other = self._compute_external_deps(segment, all_segments)

        module_text = self._format_modules(seg_modules) if seg_modules else "(no module data)"

        seg_layers: Counter = Counter()
        epi_path = self.index_dir / "trace_epistemic.jsonl"
        if epi_path.exists():
            try:
                with open(epi_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            d = json.loads(line)
                            nid = d.get("node_id", "")
                            fp = nid.replace("file:", "", 1) if nid.startswith("file:") else ""
                            if fp in seg_file_set:
                                layer = d.get("architecture_layer", "unknown")
                                seg_layers[layer] += 1
                        except json.JSONDecodeError:
                            continue
            except OSError:
                pass
        layer_text = ", ".join(f"{l}: {c}" for l, c in seg_layers.most_common(5)) if seg_layers else "(no layer data)"

        hub_text = self._format_hubs(seg_hubs) if seg_hubs else "(no hub data)"
        ext_deps_text = seg_to_other if seg_to_other else "(no cross-segment dependencies)"

        file_lines = segment.file_paths[:50]
        if len(segment.file_paths) > 50:
            file_lines.append(f"... +{len(segment.file_paths) - 50} more files")
        file_listing = "\n".join(file_lines) if file_lines else "(no files)"

        system = SEGMENT_ATLAS_SYSTEM.format(target_chars=target_chars, max_chars=max_chars)
        prompt = SEGMENT_ATLAS_PROMPT.format(
            segment_name=segment.name,
            segment_dir=segment.dir_path,
            segment_file_count=segment.file_count,
            module_summaries=module_text,
            architecture_layers=layer_text,
            hub_files=hub_text,
            file_listing=file_listing,
            external_deps=ext_deps_text,
            target_chars=target_chars,
            max_chars=max_chars,
        )

        # Append coordinator guidance
        hints_text = "\n".join(f"- {h}" for h in cross_segment_hints) if cross_segment_hints else "None specified"
        prompt += (
            f"\n\n## Coordinator Guidance\n"
            f"Analysis focus: {analysis_focus}\n"
            f"Cross-segment connections to highlight:\n{hints_text}"
        )

        prompt_tokens = len(prompt) // 4
        num_predict, num_ctx, warnings = compute_optimal_settings(
            task=PipelineTask.ATLAS,
            prompt_tokens=prompt_tokens,
            model=self.llm.model,
            think=False,
        )

        try:
            text, tokens = self.llm.generate(
                prompt, system=system, num_predict=num_predict, num_ctx=num_ctx,
                json_mode=False, temperature=0.3, think=False,
            )
            content = self._postprocess(text, max_chars)
        except Exception as e:
            logger.warning("[Atlas/Swarm] Worker failed for %s: %s", segment.name, e)
            content = ""

        if len(content) < SEGMENT_ATLAS_MIN_CHARS // 2:
            parts = [f"SEGMENT: {segment.name} ({segment.dir_path}, {segment.file_count} files)"]
            if seg_modules:
                mod_names = [m.get("name", "?") for m in seg_modules[:10]]
                parts.append(f"Modules: {', '.join(mod_names)}")
            content = ". ".join(parts)

        fp = self._compute_segment_fingerprint(segment, seg_modules)

        return SegmentDocument(
            content=content,
            generated_at=datetime.now(timezone.utc).isoformat(),
            model=self.llm.model if self.llm else "structural",
            fingerprint=fp,
            file_count=segment.file_count,
            segment_id=segment.id,
            dir_path=segment.dir_path,
        )
```

- [ ] **Step 4: Add `_run_swarm` method**

Add after `_generate_segment_atlas_with_angle`:

```python
    def _run_swarm(
        self,
        segments: List[Segment],
        all_modules: List[Dict[str, Any]],
        epistemic: Dict[str, Any],
        graph_stats: Dict[str, Any],
        hub_files: List[Tuple[str, int]],
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> Tuple[List[SegmentDocument], Optional[Dict[str, Any]]]:
        """Run swarm-orchestrated segment atlas generation.

        Returns (segment_docs, synthesis_dict).
        Empty list signals the caller to fall back to standard path.
        """
        concurrency = 1
        try:
            from prep.services.pipeline.scheduler import pipeline_scheduler
            full = pipeline_scheduler.full_budget_for_swarm(
                self.llm.provider, self.llm.model,
            )
            if full is not None:
                concurrency = full
        except (ImportError, Exception) as exc:
            logger.debug("Swarm full budget unavailable: %s", exc)
        if concurrency <= 1:
            try:
                from prep.core.batch_profiles import get_batch_concurrency
                concurrency = get_batch_concurrency(self.llm.provider, model=self.llm.model)
            except Exception:
                concurrency = 1
        logger.info("[Atlas/Swarm] Using concurrency=%d for fan-out", concurrency)

        # TODO(Phase79-DualModel): When dual-model swarm is implemented,
        # use large_llm for coordinator/synthesis, small_llm for workers.
        # For now, single model handles all three phases.
        orch = SwarmOrchestrator(llm=self.llm, concurrency=concurrency)

        # Build WorkItems
        items: List[WorkItem] = []
        seg_by_id: Dict[str, Segment] = {}
        for seg in segments:
            seg_by_id[seg.id] = seg
            summary = f"{seg.dir_path} ({seg.file_count} files, domains: {', '.join(seg.domain_tags[:5])})"
            full_context = json.dumps({
                "segment_id": seg.id,
                "name": seg.name,
                "dir_path": seg.dir_path,
                "file_count": seg.file_count,
                "domain_tags": seg.domain_tags[:10],
                "module_ids": seg.module_ids[:10],
                "key_files": seg.file_paths[:10],
            })
            items.append(WorkItem(id=seg.id, summary=summary, full_context=full_context))

        coordinator_prompt = (
            "You are coordinating parallel atlas generation for {n} workspace segments.\n"
            "Each segment is a directory subtree of a larger codebase.\n\n"
            "Segments:\n{{group_summaries}}\n\n"
            "For EACH segment, assign:\n"
            '- "analysis_angle": what aspect to emphasize (e.g., component architecture, data pipeline, API surface)\n'
            '- "priority_concerns": cross-segment connections to highlight\n\n'
            "Respond with JSON:\n"
            '{{"assignments": [{{"item_id": "seg:...", '
            '"analysis_angle": "...", '
            '"priority_concerns": ["connects to seg:X via shared config", ...]'
            "}}]}}"
        ).format(n=len(items))

        synthesis_prompt = (
            "Below are atlas documents from {n} workspace segments analyzed in parallel.\n\n"
            "{{worker_outputs}}\n\n"
            "Synthesize cross-segment insights:\n"
            '{{"cross_segment_data_flows": ["data flows from segment A to B via ..."], '
            '"shared_dependencies": ["dependency shared across N segments"], '
            '"architectural_coherence": "assessment of consistency across segments", '
            '"key_insight": "most important cross-cutting observation"}}'
        ).format(n=len(items))

        def worker_fn(item: WorkItem, assignment: WorkerAssignment) -> Optional[str]:
            seg = seg_by_id.get(item.id)
            if seg is None:
                return None
            try:
                seg_doc = self._generate_segment_atlas_with_angle(
                    seg, all_modules, epistemic, graph_stats, hub_files, segments,
                    analysis_focus=assignment.analysis_angle,
                    cross_segment_hints=assignment.priority_concerns,
                )
                return json.dumps({
                    "segment_id": seg_doc.segment_id,
                    "dir_path": seg_doc.dir_path,
                    "content": seg_doc.content,
                    "file_count": seg_doc.file_count,
                })
            except Exception as e:
                logger.warning("[Atlas/Swarm] Worker failed for %s: %s", seg.name, e)
                return None

        def progress_fn(done: int, total: int) -> None:
            if progress_callback:
                progress_callback("atlas_segmented", 1 + done, 1 + len(segments))

        result = orch.execute(
            items=items,
            coordinator_prompt=coordinator_prompt,
            worker_fn=worker_fn,
            synthesis_prompt=synthesis_prompt,
            progress_fn=progress_fn,
        )

        if result is None:
            return [], None

        # Convert worker results to SegmentDocument objects
        segment_docs: List[SegmentDocument] = []
        for wr in result.worker_results:
            if wr.success and wr.parsed:
                try:
                    seg = seg_by_id[wr.parsed["segment_id"]]
                    seg_modules_filtered = [
                        m for m in all_modules
                        if any(fp in set(seg.file_paths) for fp in m.get("member_files", []))
                    ]
                    fp = self._compute_segment_fingerprint(seg, seg_modules_filtered)
                    segment_docs.append(SegmentDocument(
                        content=wr.parsed.get("content", ""),
                        generated_at=datetime.now(timezone.utc).isoformat(),
                        model=self.llm.model,
                        fingerprint=fp,
                        file_count=wr.parsed.get("file_count", seg.file_count),
                        segment_id=seg.id,
                        dir_path=seg.dir_path,
                    ))
                except (KeyError, ValueError) as exc:
                    logger.warning("Failed to reconstruct segment doc for %s: %s", wr.item_id, exc)

        # Write synthesis artifact
        synthesis = result.synthesis
        if synthesis:
            self._write_atlas_synthesis(result)

        return segment_docs, synthesis

    def _write_atlas_synthesis(self, result: SwarmResult) -> None:
        """Write swarm synthesis artifact to disk."""
        artifact = {
            "stage": "atlas_swarm",
            "model": self.llm.model,
            "segments_analyzed": result.stats.total_items,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "synthesis": result.synthesis,
            "stats": {
                "workers_succeeded": result.stats.workers_succeeded,
                "workers_failed": result.stats.workers_failed,
                "wall_clock_seconds": round(result.stats.wall_clock_seconds, 1),
            },
        }
        path = self.index_dir / "atlas_swarm_synthesis.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(artifact, f, indent=2, ensure_ascii=False)
        logger.info("[Atlas/Swarm] Synthesis written to %s", path)
```

- [ ] **Step 5: Add swarm decision branch to `generate_segmented()`**

Insert into `generate_segmented()` after root atlas generation (after line 320, before the concurrency check at line 323). The swarm check replaces the per-segment parallel loop when active:

```python
        # ── Swarm decision ──────────────────────────────────────────
        swarm_tier = get_swarm_tier(self.llm.provider, self.llm.model)
        swarm_enabled = self._get_swarm_enabled()
        min_threshold = get_min_groups_threshold()
        use_swarm = (
            swarm_tier.can_coordinate
            and swarm_enabled
            and len(segments) >= min_threshold
        )

        if use_swarm:
            logger.info(
                "Atlas: using SWARM orchestration (%s, %d segments, tier=%s)",
                self.llm.model, len(segments), swarm_tier.value,
            )
            swarm_docs, synthesis = self._run_swarm(
                segments, modules, epistemic, graph_stats, hub_files,
                progress_callback,
            )
            if swarm_docs:
                segment_docs = swarm_docs

                duration_s = time.monotonic() - start
                logger.info(
                    "Segmented atlas (swarm): root + %d segments in %.1fs",
                    len(segment_docs), duration_s,
                )

                if progress_callback:
                    progress_callback("atlas_complete", total_steps, total_steps)

                return root_doc, segment_docs
            else:
                logger.info("Atlas swarm coordinator failed — falling back to standard path")
                # Fall through to existing concurrent/sequential logic
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_atlas_swarm.py -v
```

Expected: All 5 tests PASS.

- [ ] **Step 7: Run existing atlas tests for regression**

```bash
.venv/bin/pytest tests/ -k "atlas" -v
```

Expected: All existing + new tests PASS.

- [ ] **Step 8: Commit**

```bash
git add src/prep/core/atlas/generator.py
git commit -m "feat(swarm): integrate swarm orchestration into Atlas generation

Stage 9 now uses coordinator → fan-out → synthesis when:
- Model is swarm-capable (registry check)
- swarm_enabled setting is true
- 3+ workspace segments

Coordinator assigns per-segment analysis focus and cross-segment hints.
Synthesis produces cross-segment data flows and architectural coherence.
Falls back to standard concurrent path if coordinator fails."
```

---

### Task 5: Full Test Suite & Lint

**Files:**
- All swarm files

- [ ] **Step 1: Run full swarm test suite**

```bash
.venv/bin/pytest tests/test_swarm_registry.py tests/test_swarm_orchestrator.py tests/test_group_reasoning_swarm.py tests/test_cluster_swarm.py tests/test_atlas_swarm.py -v
```

Expected: All tests PASS (33 existing + 10 new = 43 total).

- [ ] **Step 2: Run linting**

```bash
.venv/bin/ruff check src/prep/core/cluster.py src/prep/core/atlas/generator.py
```

Expected: No errors. Fix any issues.

- [ ] **Step 3: Commit any lint fixes**

```bash
git add -A
git commit -m "chore(swarm): fix lint issues in clustering and atlas swarm"
```

(Skip this commit if no lint issues found.)

- [ ] **Step 4: Final commit — update Phase 79 docs**

Add a note to `docs/Phase79_Swarm/06_Pipeline_Stage_Execution_Profiles.md` updating the summary matrix to show Stages 8 and 9 as implemented:

In the Summary Matrix, change Stage 8 Swarm Priority from `Future` to `Phase 79` and Stage 9 from `Future` to `Phase 79`.

```bash
git add docs/Phase79_Swarm/06_Pipeline_Stage_Execution_Profiles.md
git commit -m "docs(swarm): mark Clustering and Atlas swarm as implemented in stage profiles"
```

---

## Summary

| Task | What | Files | Tests |
|------|------|-------|-------|
| 1 | Clustering swarm decision tests | `tests/test_cluster_swarm.py` | 5 tests |
| 2 | Clustering swarm implementation | `src/prep/core/cluster.py` | — |
| 3 | Atlas swarm decision tests | `tests/test_atlas_swarm.py` | 5 tests |
| 4 | Atlas swarm implementation | `src/prep/core/atlas/generator.py` | — |
| 5 | Full suite + lint + docs | All swarm files | 43 total |

**Total: 10 new tests, 2 modified files, 2 new test files, 5 commits.**
