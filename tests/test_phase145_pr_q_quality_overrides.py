"""PR-Q (§9.3 #32) — worker quality-block overrides in
orchestrator._write_stage_manifest_and_update_run.

The fix: aggregate_quality_metrics derives `total_items` from the
JSONL line count and `processed` from lines with valid confidence —
both meaningless when the JSONL is shared across stages
(trace_epistemic.jsonl is written by both ENRICHMENT and DEEPENING)
or accumulates across runs. Workers populate `_expected_total`
(authoritative denominator) and `_processed_count` (authoritative
numerator) in their result dict; the helper hoists those into the
manifest's quality block and clamps the result to enforce
`processed <= total_items` (the §9.3 #32 invariant).

Companion to PR-O's FINDING_catalogue-augmented-vs-total-semantic-
mismatch.md (catalogue stage analogue, closed by PR-P/P-fixup/
P-fixup-r2). Closes the enrichment surface (Deep Reasoning chip)
that produced the 2026-06-25 Applifier dogfood case (1,257 / 1,225
files) and the FINDING §2o §3a 20/2072 success_rate=1.0 case.
The DEEPENING surface (Continuous Deepening chip) shares
trace_epistemic.jsonl per stages.py:91/95 but the deepening worker
does not yet emit the override keys — follow-up tracked under
PRQ-CSI-002 from round-1 scrutiny.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import MagicMock

import pytest

from prep.services.pipeline.orchestrator import _apply_worker_quality_overrides


class TestApplyWorkerQualityOverridesBoolGuard:
    """PR-Q-fixup-r1 (scrutiny F1): Python's isinstance(True, int) is True,
    so without an explicit bool exclusion a buggy worker that emits
    `_expected_total = True` (e.g. a JSON serializer that turns 1 into
    True somewhere, or a typo) would have `True` written into
    manifest.total_items. Downstream consumers handle bool inconsistently.
    The helper is the safety net for buggy/migrating workers; reject
    bool explicitly.
    """

    def test_bool_true_expected_total_rejected(self):
        # Empirically demonstrated in scrutiny round 1: without the
        # bool guard this returned {'total_items': True, ...}.
        q = {"total_items": 5, "processed": 5, "success_rate": 1.0}
        out = _apply_worker_quality_overrides(q, {"_expected_total": True})
        assert out == {"total_items": 5, "processed": 5, "success_rate": 1.0}

    def test_bool_false_expected_total_rejected(self):
        q = {"total_items": 5, "processed": 5}
        out = _apply_worker_quality_overrides(q, {"_expected_total": False})
        assert out == {"total_items": 5, "processed": 5}

    def test_bool_processed_count_rejected_falls_back_to_jsonl_clamp(self):
        # With a valid _expected_total but bool _processed_count, the
        # processed override must NOT fire; the JSONL-derived value
        # (clamped at expected) is used instead.
        q = {"total_items": 5, "processed": 5, "success_rate": 1.0}
        out = _apply_worker_quality_overrides(
            q, {"_expected_total": 100, "_processed_count": True},
        )
        assert out is not None
        assert out["total_items"] == 100
        # processed is the JSONL value (5) clamped at expected (100) = 5,
        # NOT True (which would coerce to 1 in arithmetic but is
        # incoherent as a count).
        assert out["processed"] == 5
        assert out["success_rate"] == 0.05


class TestApplyWorkerQualityOverridesPassThrough:
    """Back-compat: when the worker hasn't migrated, the JSONL-derived
    quality block must come through unchanged."""

    def test_non_dict_worker_result_returns_quality_unchanged(self):
        q = {"total_items": 10, "processed": 10, "success_rate": 1.0}
        out = _apply_worker_quality_overrides(q, "not-a-dict")
        assert out == {"total_items": 10, "processed": 10, "success_rate": 1.0}

    def test_none_worker_result_returns_quality_unchanged(self):
        q = {"total_items": 10, "processed": 10}
        out = _apply_worker_quality_overrides(q, None)
        assert out == {"total_items": 10, "processed": 10}

    def test_worker_without_expected_total_returns_quality_unchanged(self):
        q = {"total_items": 10, "processed": 10, "success_rate": 1.0}
        out = _apply_worker_quality_overrides(q, {"some_other_key": 5})
        assert out == {"total_items": 10, "processed": 10, "success_rate": 1.0}

    def test_zero_expected_total_returns_quality_unchanged(self):
        # Zero denominator is meaningless — fall back to JSONL semantics.
        q = {"total_items": 10, "processed": 10}
        out = _apply_worker_quality_overrides(q, {"_expected_total": 0})
        assert out == {"total_items": 10, "processed": 10}

    def test_negative_expected_total_returns_quality_unchanged(self):
        q = {"total_items": 10, "processed": 10}
        out = _apply_worker_quality_overrides(q, {"_expected_total": -5})
        assert out == {"total_items": 10, "processed": 10}

    def test_non_int_expected_total_returns_quality_unchanged(self):
        q = {"total_items": 10, "processed": 10}
        out = _apply_worker_quality_overrides(q, {"_expected_total": "2072"})
        assert out == {"total_items": 10, "processed": 10}


class TestApplyWorkerQualityOverridesOverride:
    """When the worker provides _expected_total > 0, the helper must
    override total_items and recompute success_rate consistently."""

    def test_expected_total_overrides_total_items(self):
        q = {"total_items": 20, "processed": 20, "success_rate": 1.0}
        out = _apply_worker_quality_overrides(q, {"_expected_total": 2072})
        # FINDING §2o §3a: the 20/2072 case. Without override, success
        # appears 1.0 (jsonl had 20 lines, all with valid confidence).
        # With override, total_items reflects the real denominator and
        # success_rate drops to the real value.
        assert out is not None
        assert out["total_items"] == 2072
        # processed falls back to JSONL-derived value, clamped at
        # _expected_total (which it already satisfies here).
        assert out["processed"] == 20
        assert out["success_rate"] == round(20 / 2072, 3)

    def test_processed_count_overrides_processed_when_provided(self):
        q = {"total_items": 20, "processed": 20, "success_rate": 1.0}
        out = _apply_worker_quality_overrides(
            q, {"_expected_total": 2072, "_processed_count": 40},
        )
        assert out is not None
        assert out["total_items"] == 2072
        assert out["processed"] == 40
        assert out["success_rate"] == round(40 / 2072, 3)

    def test_processed_count_clamped_at_expected_total(self):
        # 2026-06-25 Applifier dogfood: Deep Reasoning chip read
        # '1,257 / 1,225 files'. With this override the manifest gets
        # processed=1225 (clamped), not 1257. The §9.3 #32 invariant
        # processed <= total_items holds even if the worker is buggy.
        q = {"total_items": 1257, "processed": 1257, "success_rate": 1.0}
        out = _apply_worker_quality_overrides(
            q, {"_expected_total": 1225, "_processed_count": 1257},
        )
        assert out is not None
        assert out["total_items"] == 1225
        assert out["processed"] == 1225  # clamped, NOT 1257
        assert out["success_rate"] == 1.0  # 1225/1225

    def test_jsonl_processed_also_clamped_when_processed_count_absent(self):
        # When the worker provides _expected_total but NOT
        # _processed_count, the JSONL-derived processed value is also
        # clamped — defense against a stale jsonl with more lines than
        # the worker expected (cross-stage write, partial cleanup, etc).
        q = {"total_items": 1500, "processed": 1257}
        out = _apply_worker_quality_overrides(q, {"_expected_total": 1225})
        assert out is not None
        assert out["total_items"] == 1225
        assert out["processed"] == 1225  # JSONL's 1257 clamped at 1225
        assert out["success_rate"] == 1.0

    def test_none_quality_creates_fresh_dict_when_override_fires(self):
        # If aggregate_quality_metrics produced no quality block (e.g.
        # the JSONL doesn't exist yet) but the worker DOES know the
        # expected total, the helper bootstraps a quality block from
        # nothing rather than dropping the worker's signal.
        out = _apply_worker_quality_overrides(
            None, {"_expected_total": 100, "_processed_count": 47},
        )
        assert out is not None
        assert out["total_items"] == 100
        assert out["processed"] == 47
        assert out["success_rate"] == 0.47

    def test_success_rate_recomputed_consistently(self):
        # The recomputation must use the final (post-clamp) processed
        # value, not the original. Otherwise success_rate could leak
        # the unclamped ratio.
        q = {"total_items": 0, "processed": 9999, "success_rate": 99.0}
        out = _apply_worker_quality_overrides(
            q, {"_expected_total": 100, "_processed_count": 50},
        )
        assert out is not None
        assert out["success_rate"] == 0.5  # 50/100, not 9999/100 or 99.0

    def test_zero_processed_count_yields_zero_success_rate(self):
        q = {"total_items": 0, "processed": 0}
        out = _apply_worker_quality_overrides(
            q, {"_expected_total": 100, "_processed_count": 0},
        )
        assert out is not None
        assert out["success_rate"] == 0.0


class TestApplyWorkerQualityOverridesProductionScenarios:
    """End-to-end scenarios drawn from FINDING evidence — pin the
    fix against the actual incidents we're trying to close."""

    def test_finding_2o_20_of_2072_no_longer_reports_success_rate_1(self):
        """FINDING_incremental-run-shows-50pct-work-after-interrupted-
        rebuild.md §3a: the 15:43 run wrote a manifest with
        total_items=20, processed=20, success_rate=1.0 after dispatching
        2072 files. Subsequent runs trusted that manifest. With PR-Q, the
        same scenario yields total_items=2072, success_rate=0.0097 —
        properly flagging the partial completion.
        """
        # Pre-PR-Q manifest shape (what aggregate_quality_metrics
        # produced from the 20-line trace_epistemic.jsonl):
        pre_pr_q_quality = {
            "total_items": 20,
            "processed": 20,
            "skipped": 0,
            "failed": 0,
            "success_rate": 1.0,
            "avg_confidence": 0.877,
        }
        worker_result = {
            "_expected_total": 2072,
            "_processed_count": 20,
            # Other fields the worker emits (ignored by the override).
            "total_file_nodes": 2072,
            "total_enriched": 20,
        }
        post = _apply_worker_quality_overrides(pre_pr_q_quality, worker_result)
        assert post is not None
        assert post["total_items"] == 2072
        assert post["processed"] == 20
        assert post["success_rate"] == round(20 / 2072, 3)
        # Subsequent runs reading this manifest see partial completion,
        # not the spurious 1.0 success_rate.
        assert post["success_rate"] < 0.05

    def test_finding_2j_dogfood_1257_of_1225_clamped_no_overshoot(self):
        """FINDING_stage-progress-non-monotonic.md §9 (2026-06-25):
        Applifier Deep Reasoning chip read '1,257 / 1,225 files'.
        With PR-Q's clamp the manifest is rewritten to 1225/1225 —
        the chip can no longer leak the inverted ratio.
        """
        # Pre-PR-Q: jsonl had grown past the expected total (cross-
        # stage write or stale-data accumulation).
        pre_pr_q_quality = {
            "total_items": 1257,
            "processed": 1257,
            "success_rate": 1.0,
        }
        worker_result = {
            "_expected_total": 1225,
            "_processed_count": 1257,
        }
        post = _apply_worker_quality_overrides(pre_pr_q_quality, worker_result)
        assert post is not None
        assert post["total_items"] == 1225
        assert post["processed"] == 1225
        # Never > 100% — the invariant the chip clamp PR-D shipped to
        # mask is now correct at the source.
        assert post["success_rate"] == 1.0
        assert post["processed"] <= post["total_items"]


class TestEnrichmentWorkerEmitsOverrideKeys:
    """The EpistemicEnricher.run() stats dict must populate
    `_expected_total` and `_processed_count` so the orchestrator's
    override path actually fires for enrichment stage runs."""

    def test_stats_dict_includes_override_keys(self):
        # We don't run the full enricher (LLM dependency); we just
        # verify the keys are PRESENT in the stats dict shape by
        # reading the source — same pattern as packages/ui's
        # statsSafeState.test.ts pins the IIFE shape.
        from pathlib import Path
        src_path = Path(__file__).parent.parent / "src" / "prep" / "core" / "epistemic_enrichment.py"
        body = src_path.read_text(encoding="utf-8")
        # Pin: the stats dict construction (with `total_file_nodes`
        # as the first key) must include `_expected_total` and
        # `_processed_count` keys.
        assert '"_expected_total"' in body, (
            "§9.3 #32 contract regression: epistemic_enrichment.run()'s "
            "stats dict must include `_expected_total` so the orchestrator's "
            "_apply_worker_quality_overrides fires for enrichment-stage runs."
        )
        assert '"_processed_count"' in body, (
            "§9.3 #32 contract regression: epistemic_enrichment.run()'s "
            "stats dict must include `_processed_count` so the orchestrator's "
            "_apply_worker_quality_overrides can override the JSONL-derived "
            "numerator."
        )

    def test_orchestrator_helper_is_called_in_write_stage_manifest(self):
        """The override helper must be wired into the actual write path.
        Pin: orchestrator.py:_write_stage_manifest_and_update_run must
        call _apply_worker_quality_overrides.
        """
        from pathlib import Path
        src_path = Path(__file__).parent.parent / "src" / "prep" / "services" / "pipeline" / "orchestrator.py"
        body = src_path.read_text(encoding="utf-8")
        # Pin: the helper definition exists.
        assert "def _apply_worker_quality_overrides(" in body
        # Pin: the helper is called inside _write_stage_manifest_and_update_run.
        # Use a region grep — find the function header, then grep for the
        # call within the next ~500 lines (function body bound).
        idx = body.index("def _write_stage_manifest_and_update_run(")
        body_region = body[idx:idx + 8000]
        assert "_apply_worker_quality_overrides(" in body_region, (
            "§9.3 #32 wiring regression: _write_stage_manifest_and_update_run "
            "must call _apply_worker_quality_overrides on the manifest quality "
            "block. Without the call, worker-provided _expected_total / "
            "_processed_count are ignored and the JSONL-line-count semantics "
            "leak through to the dashboard."
        )


# ─────────────────────────────────────────────────────────────────
# End-to-end integration: producer (EpistemicEnricher.run) +
# consumer (_apply_worker_quality_overrides) wired together.
# PR-Q-fixup-r1 addresses scrutiny PRQ-T-01 (source-regex tests
# can't catch partial renames) + PRQ-T-02 (no test exercises the
# real producer→consumer path).
# ─────────────────────────────────────────────────────────────────


def _write_trace_jsonl(
    idx: Path,
    nodes: List[Dict[str, Any]],
    edges: Optional[List[Dict[str, Any]]] = None,
) -> None:
    """Minimal trace files for EpistemicEnricher.run() to load."""
    edges = edges or []
    with open(idx / "trace_nodes.jsonl", "w") as f:
        for n in nodes:
            f.write(json.dumps(n) + "\n")
    with open(idx / "trace_edges.jsonl", "w") as f:
        for e in edges:
            f.write(json.dumps(e) + "\n")
    manifest = {
        "version": "1.0",
        "built_at": "2026-06-25T00:00:00Z",
        "counts": {"nodes": len(nodes), "edges": len(edges)},
    }
    with open(idx / "trace_manifest.json", "w") as f:
        json.dump(manifest, f)


def _write_epistemic_entries(idx: Path, node_ids: List[str]) -> None:
    """Write trace_epistemic.jsonl with one entry per node_id."""
    from prep.core.epistemic_score import EpistemicEntry
    path = idx / "trace_epistemic.jsonl"
    with open(path, "w", encoding="utf-8") as f:
        for nid in sorted(node_ids):
            entry = EpistemicEntry(
                node_id=nid,
                extended_summary="seed",
                domain_tags=[],
                architecture_layer="code",
            )
            f.write(json.dumps(entry.to_dict(), sort_keys=True) + "\n")


def _write_augmentations(idx: Path, node_ids: List[str]) -> None:
    """Write trace_augmented.jsonl so load_augmentations finds the
    nodes (EpistemicEnricher._needs_enrichment uses this to determine
    whether a file is already augmented — affects to_enrich filter)."""
    path = idx / "trace_augmented.jsonl"
    with open(path, "w", encoding="utf-8") as f:
        for nid in sorted(node_ids):
            obj = {
                "node_id": nid,
                "summary": "seed augmentation",
                "role": "utility",
                "confidence": 0.9,
                "augmented_at": "2026-06-25T00:00:00Z",
                "model": "test",
            }
            f.write(json.dumps(obj, sort_keys=True) + "\n")


class TestPRQ1WorkerOrphanFilter:
    """PR-Q-fixup-r1 (scrutiny PRQ-1): EpistemicEnricher.run() emits
    `_processed_count` filtered against the current file_nodes set —
    NOT cumulative len(enriched). The cumulative count would include
    orphan entries (node_ids on disk that no longer match any
    current file_node due to file deletion, L3 policy changes, or
    cross-stage writes by DEEPENING which shares
    trace_epistemic.jsonl). The clamp at the orchestrator MASKS the
    inflated symptom but doesn't fix the semantic mismatch — this
    test pins that the worker stats are already coherent before the
    orchestrator clamp fires.
    """

    def test_processed_count_excludes_orphan_entries(self, tmp_path: Path):
        from prep.core.epistemic_enrichment import EpistemicEnricher

        idx = tmp_path / "idx"
        idx.mkdir()
        repo = tmp_path / "repo"
        repo.mkdir()

        # 3 in-scope files + 5 orphans on disk.
        in_scope_node_ids = [
            "file:a.py",
            "file:b.py",
            "file:c.py",
        ]
        orphan_node_ids = [
            "file:deleted-1.py",
            "file:deleted-2.py",
            "file:l3-filtered-1.py",
            "file:cross-stage-write-1.py",
            "file:cross-stage-write-2.py",
        ]
        for nid in in_scope_node_ids:
            fname = nid.split(":", 1)[1]
            (repo / fname).write_text("# real file content\nprint('hello')\n")

        nodes = [
            {
                "id": nid,
                "kind": "file",
                "name": nid.split(":", 1)[1],
                "file_path": nid.split(":", 1)[1],
                "span": None,
                "language": "python",
                "metadata": {},
            }
            for nid in in_scope_node_ids
        ]
        _write_trace_jsonl(idx, nodes)
        # Pre-existing augmentations for all in-scope nodes so
        # _needs_enrichment returns False for them (no actual LLM
        # work happens in this test — we only care about the stats
        # dict shape).
        _write_augmentations(idx, in_scope_node_ids)
        # On-disk epistemic entries: in-scope + orphans.
        _write_epistemic_entries(idx, in_scope_node_ids + orphan_node_ids)

        llm = MagicMock()
        llm.model = "test"
        llm.provider = "test"
        llm.endpoint_url = "http://localhost:11434"
        enricher = EpistemicEnricher(
            llm=llm,
            repo_root=repo,
            index_dir=idx,
            project_id="prq-orphan-filter-test",
        )

        stats = enricher.run()

        # The §9.3 #32 invariant: _processed_count <= _expected_total.
        # Pre-fixup the worker emitted _processed_count = len(enriched)
        # = 8 (3 in-scope + 5 orphans), with _expected_total = 3 — the
        # exact 5501% inversion shape. With the orphan filter,
        # _processed_count is the count of enriched entries whose
        # node_id is in current file_nodes = 3.
        assert "_expected_total" in stats, (
            "PR-Q producer regression: enricher stats must emit "
            "_expected_total for the orchestrator override to fire."
        )
        assert "_processed_count" in stats, (
            "PR-Q producer regression: enricher stats must emit "
            "_processed_count for the orchestrator override to fire."
        )
        assert stats["_expected_total"] == len(in_scope_node_ids)
        # PRQ-1 fix: processed must NOT include orphans.
        assert stats["_processed_count"] == len(in_scope_node_ids), (
            f"PRQ-1 regression: _processed_count ({stats['_processed_count']}) "
            f"includes orphan entries — should be filtered to current "
            f"file_node_ids only ({len(in_scope_node_ids)})."
        )
        # Invariant: numerator <= denominator already holds at the
        # worker level, no orchestrator clamp needed for this case.
        assert stats["_processed_count"] <= stats["_expected_total"]


class TestPRQEndToEndProducerConsumer:
    """PR-Q-fixup-r1 (scrutiny PRQ-T-02 + PRQ-T-01): pin the actual
    producer→consumer key contract via real enricher.run() output
    fed into _apply_worker_quality_overrides. Catches partial
    renames that source-regex tests miss because this test fails if
    EITHER side breaks the contract.
    """

    def test_enricher_stats_drive_orchestrator_override_end_to_end(
        self, tmp_path: Path,
    ):
        from prep.core.epistemic_enrichment import EpistemicEnricher

        idx = tmp_path / "idx"
        idx.mkdir()
        repo = tmp_path / "repo"
        repo.mkdir()

        # Production-like incremental shape: small in-scope set, lots
        # of orphans on disk from prior runs. The FINDING §2j §9
        # 2026-06-25 dogfood case had 1257 jsonl entries vs 1225
        # file_nodes; this test uses the same RATIO at smaller scale.
        in_scope = [f"file:f{i}.py" for i in range(10)]
        orphans = [f"file:orphan-{i}.py" for i in range(15)]
        for nid in in_scope:
            fname = nid.split(":", 1)[1]
            (repo / fname).write_text("# real file content\nprint('hello')\n")
        nodes = [
            {
                "id": nid,
                "kind": "file",
                "name": nid.split(":", 1)[1],
                "file_path": nid.split(":", 1)[1],
                "span": None,
                "language": "python",
                "metadata": {},
            }
            for nid in in_scope
        ]
        _write_trace_jsonl(idx, nodes)
        _write_augmentations(idx, in_scope)
        _write_epistemic_entries(idx, in_scope + orphans)

        llm = MagicMock()
        llm.model = "test"
        llm.provider = "test"
        llm.endpoint_url = "http://localhost:11434"
        enricher = EpistemicEnricher(
            llm=llm,
            repo_root=repo,
            index_dir=idx,
            project_id="prq-e2e-test",
        )

        # Step 1 — Producer: run() emits stats with the override keys.
        stats = enricher.run()

        # Step 2 — Consumer: orchestrator helper hoists those keys
        # into the manifest quality block. Simulate the JSONL-derived
        # quality block aggregate_quality_metrics would produce
        # (jsonl has 25 lines, all with valid confidence).
        jsonl_quality = {
            "total_items": 25,  # jsonl line count (in_scope + orphans)
            "processed": 25,
            "skipped": 0,
            "failed": 0,
            "success_rate": 1.0,
            "avg_confidence": 0.85,
        }
        merged = _apply_worker_quality_overrides(jsonl_quality, stats)

        # Step 3 — Assert the producer→consumer contract holds.
        assert merged is not None
        # Denominator from the worker (10 in-scope file_nodes),
        # NOT the jsonl line count (25).
        assert merged["total_items"] == 10, (
            "Producer/consumer regression: orchestrator override did "
            "not pick up the enricher's _expected_total. Either the "
            "producer key was renamed (worker side) or the consumer "
            "isn't reading it (helper side)."
        )
        # Numerator: enricher emits 10 (filtered to in-scope),
        # consumer clamps at 10. Result: coherent 10/10.
        assert merged["processed"] == 10
        # Invariant: numerator <= denominator, success_rate <= 1.0.
        assert merged["processed"] <= merged["total_items"]
        assert merged["success_rate"] == 1.0
        # The jsonl-derived 25/25 quality is GONE — no leak.
        assert merged["total_items"] != 25

