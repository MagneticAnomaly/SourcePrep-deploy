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
P-fixup-r2). Closes the deepening/enrichment surface that produced
the 2026-06-25 Applifier dogfood case (Deep Reasoning chip reading
'1,257 / 1,225 files') and the FINDING §2o §3a 20/2072 success_rate
=1.0 case.
"""
from __future__ import annotations

import pytest

from prep.services.pipeline.orchestrator import _apply_worker_quality_overrides


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
